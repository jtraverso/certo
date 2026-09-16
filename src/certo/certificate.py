"""Certificates.

Cross-cutting rule 1: every command returns a certificate, or says why not.

Each certificate stores enough to be re-verified WITHOUT the original session
and without trusting the LLM that proposed the statement. `solver_free` says
whether verification needs a solver at all; those are the strong ones.

Notes are stored as CATALOGUE KEYS rather than rendered text, so a certificate
issued in one language reads correctly in another. What travels must not be
tied to the language of whoever produced it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .i18n import t

SCHEMA_VERSION = 3


@dataclass
class Certificate:
    kind: str
    solver_free: bool
    payload: dict = field(default_factory=dict)
    note_key: str = ""
    note_args: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        # Version and date ALWAYS, whether issued from the CLI or the API.
        # Only the caller knows the spec path: stamp() adds it.
        if not self.provenance:
            from . import __version__

            self.provenance = {
                "certo_version": __version__,
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }

    @property
    def note(self) -> str:
        """Rendered in the reader's language, not the writer's."""
        return t(self.note_key, **self.note_args) if self.note_key else ""

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA_VERSION,
            "kind": self.kind,
            "solver_free": self.solver_free,
            "note_key": self.note_key,
            "note_args": self.note_args,
            "note": self.note,          # rendered copy, for reading the raw JSON
            "provenance": self.provenance,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        return cls(
            kind=d["kind"],
            solver_free=d.get("solver_free", False),
            payload=d.get("payload", {}),
            note_key=d.get("note_key", ""),
            note_args=d.get("note_args", {}),
            provenance=d.get("provenance") or {"legacy": True},
        )

    def digest(self) -> str:
        """Content addressing: kind and payload only.

        Provenance carries a timestamp, so including it would give two
        identical runs different digests. The digest identifies the
        MATHEMATICAL CONTENT, not the run.
        """
        blob = json.dumps({"kind": self.kind, "payload": self.payload},
                          sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def stamp(self, spec_path=None, extra=None) -> "Certificate":
        """Tie the certificate to the spec that produced it, and the version."""
        from . import __version__

        prov = {"certo_version": __version__,
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if spec_path:
            p = Path(spec_path)
            prov["spec_path"] = str(p)
            if p.exists():
                prov["spec_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        prov.update(extra or {})
        self.provenance = prov
        return self


@dataclass
class VerifyReport:
    ok: bool
    kind: str
    solver_free: bool
    checks: list = field(default_factory=list)  # [(name, ok, detail)]
    detail: str = ""
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "solver_free": self.solver_free,
            "checks": [{"check": c, "ok": o, "detail": d} for c, o, d in self.checks],
            "warnings": self.warnings,
            "detail": self.detail,
        }


def _provenance_warnings(cert: Certificate) -> list:
    """Provenance does not invalidate the mathematics, but a mismatch matters.

    A certificate stays valid even if the spec changed: it verifies on its
    own. What stops being true is the ASSOCIATION between the two, and that
    has to be said out loud.
    """
    prov = cert.provenance or {}
    out = []
    sp, want = prov.get("spec_path"), prov.get("spec_sha256")
    if sp and want:
        p = Path(sp)
        if not p.exists():
            out.append(t("verify.provenance.gone", path=sp))
        elif hashlib.sha256(p.read_bytes()).hexdigest() != want:
            out.append(t("verify.provenance.changed", path=sp))
    if prov.get("legacy"):
        out.append(t("verify.provenance.legacy"))
    return out


# ---------------------------------------------------------------------------
# constructores
# ---------------------------------------------------------------------------


def model_certificate(smt2: str, assignment: dict) -> Certificate:
    return Certificate(
        kind="model",
        solver_free=True,
        payload={"smt2": smt2, "assignment": assignment},
        note_key="cert.note.model",
    )


def unsat_core_certificate(core_smt2: str, names: list, dropped: list,
                           vacuous: bool = False) -> Certificate:
    """`vacuous` means the hypotheses contradict each other.

    The proof is still valid -- anything follows from a contradiction -- so
    this is not an error and does not change the verdict. It travels in the
    payload because it is exactly the kind of thing that looks like success
    and must keep being said out loud, long after the run.
    """
    return Certificate(
        kind="unsat_core",
        solver_free=False,
        payload={"core_smt2": core_smt2, "names": names, "dropped": dropped,
                 "vacuous": bool(vacuous)},
        note_key="cert.note.unsat_core",
    )


def lp_dual_certificate(sense, objective, dual, A, b, c, names,
                        primal=None, var_names=None, is_exact=False) -> Certificate:
    return Certificate(
        kind="lp_dual",
        solver_free=True,
        payload={
            "sense": sense, "objective": objective, "dual": dual,
            "primal": primal, "A": A, "b": b, "c": c,
            "names": names, "var_names": var_names, "exact": is_exact,
        },
        note_key="cert.note.lp_dual.exact" if is_exact else "cert.note.lp_dual.float",
    )


def cegis_certificate(impl, counterexamples, smt2, iterations) -> Certificate:
    return Certificate(
        kind="cegis",
        solver_free=False,
        payload={
            "implementation": impl,
            "counterexamples": counterexamples,
            "smt2": smt2,
            "iterations": iterations,
        },
        note_key="cert.note.cegis",
    )


def cnf_model_certificate(dimacs: str, true_vars) -> Certificate:
    return Certificate(
        kind="cnf_model",
        solver_free=True,
        payload={"dimacs": dimacs, "true_vars": sorted(true_vars)},
        note_key="cert.note.cnf_model",
    )


def drat_certificate(dimacs: str, proof: list, nvars: int, nclauses: int) -> Certificate:
    return Certificate(
        kind="drat",
        solver_free=True,
        payload={"dimacs": dimacs, "proof": proof,
                 "nvars": nvars, "nclauses": nclauses},
        note_key="cert.note.drat",
    )


def shrink_graph_certificate(spec_path, spec_sha256, original, minimal,
                             filters, blocked, steps) -> Certificate:
    return Certificate(
        kind="shrink_graph",
        solver_free=True,
        payload={"spec_path": str(spec_path), "spec_sha256": spec_sha256,
                 "original": original, "minimal": minimal, "filters": filters,
                 "blocked": blocked, "steps": steps},
        note_key="cert.note.shrink_graph",
    )


def mus_certificate(nvars, original, mus_indices, mus, proof,
                    witnesses, var_names) -> Certificate:
    return Certificate(
        kind="mus",
        solver_free=True,
        payload={"nvars": nvars, "original": original, "mus_indices": mus_indices,
                 "mus": mus, "proof": proof, "witnesses": witnesses,
                 "var_names": var_names},
        note_key="cert.note.mus",
    )


def bisect_certificate(direction, integer, tol, good_t, bad_t,
                       good_cert, bad_cert, evaluations) -> Certificate:
    free = all(c is not None and c.get("solver_free", False)
               for c in (good_cert, bad_cert))
    return Certificate(
        kind="bisect",
        solver_free=free,
        payload={"direction": direction, "integer": integer, "tol": tol,
                 "good_t": good_t, "bad_t": bad_t,
                 "good_cert": good_cert, "bad_cert": bad_cert,
                 "evaluations": evaluations},
        note_key="cert.note.bisect",
    )


def sweep_certificate(n, filters, family_g6, entries, mode, counts,
                      values=None, stats=None) -> Certificate:
    """The examined family PLUS whatever certificates the predicate supplied.

    Without the second part, a sweep whose predicate solves an LP in floating
    point is not citable however impeccable the first part is.
    """
    h = hashlib.sha256("\n".join(sorted(family_g6)).encode()).hexdigest()
    certified = sum(1 for e in entries if e.get("cert"))
    free = all(e["cert"].get("solver_free") for e in entries if e.get("cert"))
    return Certificate(
        kind="sweep",
        solver_free=bool(free),
        payload={"n": n, "filters": filters, "family_sha256": h,
                 "family_count": len(family_g6), "family_graph6": family_g6,
                 "entries": entries, "mode": mode, "counts": counts,
                 "values": values or [], "stats": stats},
        note_key="cert.note.sweep",
        note_args={"certified": certified, "total": len(entries)},
    )


def synth_proved_certificate(candidate, synth_cert, universal_cert) -> Certificate:
    """Los dos pasos juntos: se encontro acotado, se demostro universal.

    Separados dicen cosas distintas y conviene que se vea: el primero es un
    DESCUBRIMIENTO sobre un dominio acotado, el segundo una PRUEBA simbolica
    del candidato. Solo el segundo es un teorema.
    """
    free = all(c is not None and c.get("solver_free", False)
               for c in (synth_cert, universal_cert))
    return Certificate(
        kind="synth_proved",
        solver_free=free,
        payload={"candidate": candidate, "synth": synth_cert,
                 "universal": universal_cert},
        note_key="cert.note.synth_proved",
    )


def domain_sweep_certificate(ids, entries, mode, counts, values=None,
                             stats=None, title="") -> Certificate:
    """Same contract as `sweep`, for a domain the spec defines itself."""
    h = hashlib.sha256(chr(10).join(sorted(ids)).encode()).hexdigest()
    free = all(e["cert"].get("solver_free") for e in entries if e.get("cert"))
    return Certificate(
        kind="domain_sweep", solver_free=bool(free),
        payload={"title": title, "ids": ids, "ids_sha256": h,
                 "count": len(ids), "entries": entries, "mode": mode,
                 "counts": counts, "values": values or [], "stats": stats},
        note_key="cert.note.domain_sweep",
    )


def sweep_range_certificate(entries, first_failure, stopped_early) -> Certificate:
    """One sub-certificate per size. The answer to "from which n does it fail?"

    Each n is verified on its own; what this adds is the ORDER and the claim
    that nothing failed below `first_failure`. With --stop-on-first the sizes
    above it were never run, and that is recorded.
    """
    free = all(e["cert"].get("solver_free") for e in entries if e.get("cert"))
    return Certificate(
        kind="sweep_range", solver_free=bool(free),
        payload={"entries": entries, "first_failure": first_failure,
                 "stopped_early": stopped_early,
                 "sizes": [e["n"] for e in entries]},
        note_key="cert.note.sweep_range",
    )


def core_matrix_certificate(hypotheses, goals, table, subcerts,
                            inconclusive) -> Certificate:
    """One core per goal plus the table they induce."""
    return Certificate(
        kind="core_matrix", solver_free=False,
        payload={"hypotheses": hypotheses, "goals": goals, "table": table,
                 "cores": subcerts, "inconclusive": inconclusive},
        note_key="cert.note.core_matrix",
    )


def shrink_domain_certificate(spec_path, spec_sha256, original, minimal,
                              trace, blocked, steps) -> Certificate:
    """The descent, recorded as indices so it can be replayed exactly."""
    return Certificate(
        kind="shrink_domain", solver_free=True,
        payload={"spec_path": str(spec_path), "spec_sha256": spec_sha256,
                 "original": original, "minimal": minimal, "trace": trace,
                 "blocked": blocked, "steps": steps},
        note_key="cert.note.shrink_domain",
    )


def farkas_certificate(rows, multipliers, constant, strict, nonlinear,
                       base_rows, sorts=None, vacuous=False,
                       spec_path="") -> Certificate:
    """Non-negative multipliers that close the system. Checked by arithmetic.

    This is what `linarith` emits, and what `nlinarith` emits once its
    preprocessing rows are counted as hypotheses of their own.
    """
    return Certificate(
        kind="farkas", solver_free=True,
        payload={"rows": rows, "multipliers": multipliers,
                 "constant": constant, "strict": strict,
                 "nonlinear": nonlinear, "base_rows": base_rows,
                 "sorts": sorts or {}, "vacuous": bool(vacuous),
                 "spec_path": str(spec_path)},
        note_key="cert.note.farkas",
    )



def proof_certificate(theorem_smt2, assumptions, assumptions_smt2, lemmas,
                      step, used, unused, vacuous=False, title="") -> Certificate:
    """A proof assembled from lemmas, each with its own certificate.

    What this adds over a pile of certificates in a directory is the LINK: for
    every lemma discharged here, the certificate records that the statement
    used downstream is entailed by what that lemma's certificate actually
    establishes. That is the join a human makes silently, and it is where
    assembled proofs break -- a lemma proved under one hypothesis and then
    used under another.

    Lemmas supplied as an existing certificate are BRIDGES: verified on their
    own, but the step from "these 156 graphs all satisfy P" to a first-order
    formula is a modelling decision no checker can make. They are listed by
    name and reported on every verification.
    """
    bridges = [l["name"] for l in lemmas if not l.get("derived")]
    return Certificate(
        kind="proof", solver_free=False,
        payload={"title": title, "theorem_smt2": theorem_smt2,
                 "assumptions": assumptions,
                 "assumptions_smt2": assumptions_smt2,
                 "lemmas": lemmas, "step": step,
                 "used": used, "unused": unused, "bridges": bridges,
                 "vacuous": bool(vacuous)},
        note_key="cert.note.proof",
    )



def ball_certificate(describe, backend, prec, lo, hi, claim, spec_path="",
                     spec_sha256="", title="") -> Certificate:
    """A rigorous enclosure, and the claim it settles.

    The enclosure travels as EXACT rationals, so the half that matters -- does
    this interval settle the inequality -- is decided by comparing fractions,
    with no library involved at all. Reproducing the interval needs the spec
    and the same backend, and that half is checked separately and reported
    separately, because it is the half that can go stale.
    """
    return Certificate(
        kind="ball", solver_free=True,
        payload={"describe": describe, "backend": backend, "prec": prec,
                 "lo": str(lo), "hi": str(hi), "claim": list(claim) if claim else None,
                 "spec_path": str(spec_path), "spec_sha256": spec_sha256,
                 "title": title},
        note_key="cert.note.ball",
    )


def graph_set_certificate(n: int, filters: list, g6: list) -> Certificate:
    h = hashlib.sha256("\n".join(sorted(g6)).encode()).hexdigest()
    return Certificate(
        kind="graph_set",
        solver_free=True,
        payload={
            "n": n,
            "filters": filters,
            "count": len(g6),
            "sha256": h,
            "graph6": g6,
        },
        note_key="cert.note.graph_set",
    )


# ---------------------------------------------------------------------------
# verificacion
# ---------------------------------------------------------------------------


def verify(cert: Certificate, limits=None) -> VerifyReport:
    fn = {
        "model": _verify_model,
        "unsat_core": _verify_unsat_core,
        "lp_dual": _verify_lp_dual,
        "cegis": _verify_cegis,
        "graph_set": _verify_graph_set,
        "cnf_model": _verify_cnf_model,
        "drat": _verify_drat,
        "shrink_graph": _verify_shrink_graph,
        "mus": _verify_mus,
        "bisect": _verify_bisect,
        "sweep": _verify_sweep,
        "domain_sweep": _verify_domain_sweep,
        "sweep_range": _verify_sweep_range,
        "core_matrix": _verify_core_matrix,
        "shrink_domain": _verify_shrink_domain,
        "farkas": _verify_farkas,
        "synth_proved": _verify_synth_proved,
        "proof": _verify_proof,
        "ball": _verify_ball,
    }.get(cert.kind)
    if fn is None:
        return VerifyReport(
            False, cert.kind, cert.solver_free,
            detail=t("verify.unknown_kind", kind=cert.kind),
        )
    try:
        rep = fn(cert, limits)
        rep.warnings = _provenance_warnings(cert) + list(rep.warnings)
        return rep
    except Exception as e:  # noqa: BLE001
        return VerifyReport(
            False, cert.kind, cert.solver_free,
            detail=t("verify.failed", type=type(e).__name__, message=e),
        )



# --- the link between a lemma and its certificate --------------------------


def obligations_of(sub: dict):
    """The formulas a sub-certificate establishes are JOINTLY UNSATISFIABLE.

    This is the only thing `compose` needs from a sub-certificate, and it is
    what makes the link checkable: if the negated statement entails these, and
    these are contradictory, the statement is valid. Returns None for kinds
    that establish something which is not a formula set at all -- a finite
    sweep, a DRAT proof over propositional variables -- and those become
    bridges rather than silent assumptions.
    """
    import z3

    kind, p = sub.get("kind"), sub.get("payload", {})
    if kind == "unsat_core":
        return list(z3.parse_smt2_string(p["core_smt2"]))
    if kind == "farkas":
        from fractions import Fraction

        from . import linarith

        rows = linarith.parse_rows(p["rows"])
        lams = [Fraction(x) for x in p["multipliers"]]
        sorts = p.get("sorts") or {}
        return [linarith.row_to_z3(poly, rel, sorts)
                for (_, poly, rel), lam in zip(rows, lams) if lam > 0]
    return None


def entails(negated_statement, obligations, limits) -> bool:
    """Does `not statement` imply everything the certificate closed?

    Together with the sub-certificate's own verification (those obligations
    are contradictory) this gives: `not statement` is unsatisfiable, i.e. the
    statement is valid. Checking the implication rather than syntactic
    equality is what lets a certificate be reused for any statement it is
    strong enough to support.
    """
    import z3

    from .limits import Limits

    s = z3.Solver()
    (limits or Limits()).apply_to(s)
    s.add(negated_statement)
    s.add(z3.Not(z3.And(*obligations)) if len(obligations) > 1
          else z3.Not(obligations[0]))
    return s.check() == z3.unsat


def _parse_one(smt2: str):
    """An smt2 blob back into a single formula."""
    import z3

    fs = list(z3.parse_smt2_string(smt2))
    if not fs:
        return z3.BoolVal(True)
    return fs[0] if len(fs) == 1 else z3.And(*fs)


def _verify_proof(cert, limits) -> VerifyReport:
    import z3

    p = cert.payload
    checks, warnings = [], []
    statements = []

    for lem in p["lemmas"]:
        name = lem["name"]
        phi = _parse_one(lem["statement_smt2"])
        statements.append(phi)
        sub = lem.get("cert")
        if sub is None:
            checks.append((t("verify.proof.lemma", name=name), False,
                           t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        checks.append((t("verify.proof.lemma", name=name), rep.ok,
                       "{}: {}".format(sub["kind"], rep.detail)))
        warnings.extend("{}: {}".format(name, w) for w in rep.warnings)

        if not lem.get("derived"):
            warnings.append(t("verify.proof.bridge", name=name,
                              why=lem.get("bridge") or sub["kind"]))
            continue
        obl = obligations_of(sub)
        linked = bool(obl) and entails(z3.Not(phi), obl, limits)
        checks.append((t("verify.proof.link", name=name), linked,
                       t("verify.proof.link_detail", n=len(obl or []))))

    # The final step: the lemmas and the theorem's own hypotheses close it.
    ambient = list(z3.parse_smt2_string(p["assumptions_smt2"])) \
        if p.get("assumptions_smt2") else []
    theorem = _parse_one(p["theorem_smt2"])
    step = p.get("step")
    if step is None:
        checks.append((t("verify.proof.step"), False, t("verify.bisect.no_cert")))
    else:
        rep = verify(Certificate.from_dict(step), limits)
        checks.append((t("verify.proof.step"), rep.ok, rep.detail))
        premises = statements + ambient
        neg = z3.And(*(premises + [z3.Not(theorem)])) if premises \
            else z3.Not(theorem)
        obl = obligations_of(step)
        linked = bool(obl) and entails(neg, obl, limits)
        checks.append((t("verify.proof.step_link"), linked,
                       t("verify.proof.link_detail", n=len(obl or []))))
        # Nothing may enter the final step that was not declared.
        declared = set(p["assumptions"]) | {l["name"] for l in p["lemmas"]}
        smuggled = [n for n in step.get("payload", {}).get("names", [])
                    if n != "__goal__" and n not in declared]
        checks.append((t("verify.proof.declared"), not smuggled,
                       ", ".join(smuggled)))

    if p.get("vacuous"):
        warnings.append(t("verify.proof.vacuous"))
    if p.get("unused"):
        warnings.append(t("verify.proof.unused",
                          names=", ".join(p["unused"])))

    return VerifyReport(
        all(c[1] for c in checks), "proof", False, checks=checks,
        warnings=warnings,
        detail=t("verify.proof.detail", lemmas=len(p["lemmas"]),
                 bridges=len(p.get("bridges", []))),
    )



def _verify_ball(cert, limits) -> VerifyReport:
    """Two halves, and they fail differently.

    Whether the interval settles the claim is pure rational arithmetic and
    always runs. Whether the interval is the right interval needs the spec and
    the same backend; when that cannot be redone here it is reported as
    unchecked rather than quietly passed.
    """
    from fractions import Fraction

    from . import numerics

    p = cert.payload
    lo, hi = Fraction(p["lo"]), Fraction(p["hi"])
    claim = tuple(p["claim"]) if p.get("claim") else None
    checks, warnings = [], []

    checks.append((t("verify.ball.ordered"), lo <= hi,
                   "[{}, {}]".format(float(lo), float(hi))))
    settled = numerics.settle(claim, lo, hi)
    checks.append((t("verify.ball.settles"), settled is True,
                   numerics.render(claim) or t("verify.ball.no_claim")))

    path = Path(p.get("spec_path") or "")
    if not p.get("spec_path") or not path.exists():
        warnings.append(t("verify.ball.no_spec", path=p.get("spec_path") or "-"))
        return VerifyReport(
            all(c[1] for c in checks), "ball", True, checks=checks,
            warnings=warnings,
            detail=t("verify.ball.detail", prec=p["prec"], backend=p["backend"]))

    try:
        from .spec import load_spec

        sp = load_spec(path)
        rig = numerics.Rig(int(p["prec"]), p["backend"])
        got_lo, got_hi = sp.value(rig).enclosure()
        inside = lo <= got_lo and got_hi <= hi
        checks.append((t("verify.ball.reproduced"), inside,
                       "[{}, {}]".format(float(got_lo), float(got_hi))))
    except Exception as e:  # noqa: BLE001
        warnings.append(t("verify.ball.not_redone", reason=str(e)))

    return VerifyReport(
        all(c[1] for c in checks), "ball", True, checks=checks,
        warnings=warnings,
        detail=t("verify.ball.detail", prec=p["prec"], backend=p["backend"]))


def _verify_model(cert, limits) -> VerifyReport:
    import z3

    p = cert.payload
    formula = z3.And(*z3.parse_smt2_string(p["smt2"]))
    subs = []
    for name, pair in p["assignment"].items():
        sort, val = pair
        subs.append((_const(z3, name, sort), _value(z3, sort, val)))
    got = z3.simplify(z3.substitute(formula, *subs)) if subs else z3.simplify(formula)
    ok = z3.is_true(got)
    return VerifyReport(
        ok, "model", True,
        checks=[(t("verify.model.satisfies"), ok, str(got))],
        detail="" if ok else t("verify.model.fails"),
    )


def _verify_unsat_core(cert, limits) -> VerifyReport:
    import z3

    from .limits import Limits

    lim = limits or Limits()
    s = z3.Solver()
    lim.apply_to(s)
    for f in z3.parse_smt2_string(cert.payload["core_smt2"]):
        s.add(f)
    r = s.check()
    ok = r == z3.unsat
    n = len(cert.payload["names"])
    return VerifyReport(
        ok, "unsat_core", False,
        checks=[(t("verify.core.unsat"), ok, str(r))],
        warnings=[t("verify.core.vacuous")] if cert.payload.get("vacuous") else [],
        detail=t("verify.core.detail", n=n),
    )


def _verify_lp_dual(cert, limits) -> VerifyReport:
    p = cert.payload
    if p.get("exact"):
        return _verify_lp_dual_exact(p)
    return _verify_lp_dual_float(p)


def _verify_lp_dual_exact(p) -> VerifyReport:
    """No tolerances. If this passes, that is the optimum and there is no more to say."""
    from . import exact

    A = [exact.parse_all(r) for r in p["A"]]
    b, c = exact.parse_all(p["b"]), exact.parse_all(p["c"])
    x, y = exact.parse_all(p["primal"]), exact.parse_all(p["dual"])
    rep = exact.check_lp(A, b, c, x, y)

    checks = [
        (t("verify.lp.primal_nonneg"), rep["primal_nonneg"], ""),
        (t("verify.lp.primal_feasible"), rep["primal_feasible"], ""),
        (t("verify.lp.dual_nonneg"), rep["dual_nonneg"],
         "min(y)={}".format(exact.serialize(min(y)) if y else "-")),
        (t("verify.lp.dual_feasible"), rep["dual_feasible"], ""),
        (t("verify.lp.strong"), rep["strong_duality"],
         "c.x={} | b.y={}".format(exact.serialize(rep["objective"]),
                                  exact.serialize(rep["dual_bound"]))),
        (t("verify.lp.objective"),
         exact.to_fraction(p["objective"]) == rep["objective"],
         "declarado {}".format(p["objective"])),
    ]
    return VerifyReport(
        all(k[1] for k in checks), "lp_dual", True, checks=checks,
        detail=t("verify.lp.exact.detail", value=exact.serialize(rep["objective"])),
    )


def _verify_lp_dual_float(p) -> VerifyReport:
    A, b, c, y = p["A"], p["b"], p["c"], p["dual"]
    tol = 1e-6
    checks = []

    nonneg = all(v >= -tol for v in y)
    checks.append(
        (t("verify.lp.dual_nonneg"), nonneg,
         "min(y)={:.6g}".format(min(y) if y else 0))
    )

    m, ncols = len(A), len(c)
    feas, worst = True, 0.0
    for j in range(ncols):
        s = sum(A[i][j] * y[i] for i in range(m))
        if s < c[j] - tol:
            feas = False
            worst = max(worst, c[j] - s)
    checks.append(
        (t("verify.lp.dual_feasible"), feas, "max violation={:.3g}".format(worst))
    )

    bound = sum(b[i] * y[i] for i in range(m))
    tight = abs(bound - p["objective"]) <= 1e-4 * max(1.0, abs(p["objective"]))
    checks.append(
        (t("verify.lp.bound"), tight,
         "b.y={:.6g} vs obj={:.6g}".format(bound, p["objective"]))
    )

    ok = nonneg and feas and tight
    return VerifyReport(
        ok, "lp_dual", True, checks=checks,
        warnings=[t("verify.lp.float.warning")],
        detail=t("verify.lp.float.detail"),
    )


def _verify_cegis(cert, limits) -> VerifyReport:
    import z3

    from .limits import Limits

    lim = limits or Limits()
    p = cert.payload
    checks = []

    decls: dict = {}
    impl_cons = z3.And(*z3.parse_smt2_string(p["smt2"]["impl_constraints"], decls=decls))
    behav = z3.And(*z3.parse_smt2_string(p["smt2"]["behavior"], decls=decls))
    corr = z3.And(*z3.parse_smt2_string(p["smt2"]["correctness"], decls=decls))

    fix = []
    for name, pair in p["implementation"].items():
        sort, val = pair
        fix.append(_const(z3, name, sort) == _value(z3, sort, val))

    s = z3.Solver()
    lim.apply_to(s)
    s.add(impl_cons, *fix)
    r1 = s.check()
    ok1 = r1 == z3.sat
    checks.append((t("verify.cegis.impl_ok"), ok1, str(r1)))

    s = z3.Solver()
    lim.apply_to(s)
    s.add(behav, z3.Not(corr), *fix)
    r2 = s.check()
    ok2 = r2 == z3.unsat
    checks.append((t("verify.cegis.no_ce"), ok2, str(r2)))

    return VerifyReport(
        ok1 and ok2, "cegis", False, checks=checks,
        detail=t("verify.cegis.detail", iterations=p["iterations"],
                 ces=len(p["counterexamples"])),
    )


def _verify_cnf_model(cert, limits) -> VerifyReport:
    from .cnf import CNF

    p = cert.payload
    cnf = CNF.from_dimacs(p["dimacs"])
    true = set(p["true_vars"])

    def lit_true(l):
        return (abs(l) in true) == (l > 0)

    bad = [c for c in cnf.clauses if not any(lit_true(l) for l in c)]
    ok = not bad
    return VerifyReport(
        ok, "cnf_model", True,
        checks=[(t("verify.cnf.satisfies", n=len(cnf.clauses)), ok,
                 t("verify.cnf.unsatisfied", n=len(bad)))],
        detail="" if ok else t("verify.cnf.first_failure", clause=bad[0]),
    )


def _verify_drat(cert, limits) -> VerifyReport:
    from . import drup
    from .cnf import CNF
    from .limits import Limits

    lim = limits or Limits()
    p = cert.payload
    cnf = CNF.from_dimacs(p["dimacs"])
    checks = [(
        t("verify.drat.formula", n=p["nclauses"]),
        len(cnf.clauses) == p["nclauses"],
        "read {}".format(len(cnf.clauses)),
    )]
    rep = drup.check(cnf.clauses, p["proof"],
                     timeout_s=max(1.0, lim.timeout_ms / 1000))
    checks.append((t("verify.drat.steps"), rep.ok, rep.detail))
    checks.append((t("verify.drat.empty"), rep.derived_empty, ""))
    if drup.drat_trim_available():
        ext = drup.check_with_drat_trim(p["dimacs"], p["proof"])
        checks.append((t("verify.drat.external"), ext.ok, ext.detail))

    ok = all(c[1] for c in checks)
    return VerifyReport(
        ok, "drat", True, checks=checks,
        detail=t("verify.drat.detail", steps=rep.steps, rup=rep.rup_steps,
                 rat=rep.rat_steps, **{"del": rep.deletions},
                 ms=rep.elapsed_ms),
    )


def _verify_shrink_graph(cert, limits) -> VerifyReport:
    from pathlib import Path

    from .engines.shrink import _reductions
    from .graphs import Graph, compile_filters
    from .spec import load_spec

    p = cert.payload
    checks = []

    src = Path(p["spec_path"])
    if not src.exists():
        return VerifyReport(False, "shrink_graph", True,
                            detail=t("verify.shrink.spec_missing", path=src))
    got = hashlib.sha256(src.read_bytes()).hexdigest()
    checks.append((t("verify.shrink.spec_same"), got == p["spec_sha256"], got[:16]))

    spec = load_spec(src)
    fns = compile_filters(p["filters"])
    minimal = Graph.from_graph6(p["minimal"])

    def is_ce(g):
        if g.n == 0:
            return False
        if any(not f(g) for _, f in fns):
            return False
        try:
            return not spec.predicate(g)
        except Exception:  # noqa: BLE001
            return False

    checks.append((t("verify.shrink.still_ce"), is_ce(minimal),
                   "n={} m={}".format(minimal.n, minimal.m)))

    recomputed = list(_reductions(minimal))
    checks.append((t("verify.shrink.complete"),
                   len(recomputed) == len(p["blocked"]),
                   t("verify.shrink.computed", computed=len(recomputed),
                     declared=len(p["blocked"]))))
    survivors = [op for op, cand in recomputed if is_ce(cand)]
    checks.append((t("verify.shrink.none_survive"), not survivors,
                   t("verify.shrink.survivors", names=survivors[:5])))

    ok = all(c[1] for c in checks)
    return VerifyReport(ok, "shrink_graph", True, checks=checks,
                        detail=t("verify.shrink.detail"))


def _verify_mus(cert, limits) -> VerifyReport:
    from . import drup

    p = cert.payload
    checks = []

    orig = {tuple(sorted(c)) for c in p["original"]}
    subset = all(tuple(sorted(c)) in orig for c in p["mus"])
    checks.append((t("verify.mus.subset"), subset,
                   t("verify.mus.subset.detail", mus=len(p["mus"]),
                     total=len(p["original"]))))

    rep = drup.check([list(c) for c in p["mus"]], p["proof"],
                     timeout_s=60.0)
    checks.append((t("verify.mus.proof"), rep.ok and rep.derived_empty,
                   rep.detail))

    # minimalidad: un modelo por clausula, que satisface el MUS sin ella
    bad = []
    idx_by_pos = list(p["mus_indices"])
    for pos, gi in enumerate(idx_by_pos):
        w = set(p["witnesses"].get(str(gi), []))
        rest = [c for k, c in enumerate(p["mus"]) if k != pos]
        for c in rest:
            if not any((abs(l) in w) == (l > 0) for l in c):
                bad.append(gi)
                break
    checks.append((t("verify.mus.minimal"), not bad,
                   t("verify.mus.no_witness", n=len(bad))))

    ok = all(c[1] for c in checks)
    return VerifyReport(ok, "mus", True, checks=checks,
                        detail=t("verify.mus.detail"))


def _verify_bisect(cert, limits) -> VerifyReport:
    p = cert.payload
    checks, free = [], True

    for side, label in (("good_cert", t("verify.bisect.good", t=p["good_t"])),
                        ("bad_cert", t("verify.bisect.bad", t=p["bad_t"]))):
        sub = p.get(side)
        if sub is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        free = free and rep.solver_free
        checks.append((label + " ({})".format(sub["kind"]), rep.ok, rep.detail))

    width = abs(p["good_t"] - p["bad_t"])
    tight = width <= p["tol"] + 1e-12
    checks.append((t("verify.bisect.brackets"), tight,
                   t("verify.bisect.width", width=width, tol=p["tol"])))

    up = p["direction"] == "min_true"
    oriented = (p["good_t"] > p["bad_t"]) if up else (p["good_t"] < p["bad_t"])
    checks.append((t("verify.bisect.orientation", direction=p["direction"]),
                   oriented, t("verify.bisect.sides", good=p["good_t"],
                              bad=p["bad_t"])))

    ok = all(c[1] for c in checks)
    return VerifyReport(ok, "bisect", free, checks=checks,
                        detail=t("verify.bisect.detail"))


def _verify_family(g6, n, filters, want_hash) -> list:
    """Checks shared by graph_set and sweep."""
    from .graphs import FILTERS, Graph, is_isomorphic, wl_signature

    checks = []
    h = hashlib.sha256("\n".join(sorted(g6)).encode()).hexdigest()
    checks.append((t("verify.family.hash"), h == want_hash, h[:16]))

    graphs = [Graph.from_graph6(s) for s in g6]
    bad_n = [g for g in graphs if g.n != n]
    checks.append((t("verify.family.n", n=n), not bad_n,
                   t("verify.family.count", n=len(bad_n))))

    bad_f, unverifiable = [], []
    for name in filters:
        if name.startswith("fn:"):
            # A programmable filter lives in the spec, not in the catalogue:
            # it cannot be re-checked from the certificate alone.
            unverifiable.append(name)
            continue
        f = FILTERS.get(name)
        if f is None:
            bad_f.append("unknown filter: " + name)
            continue
        bad_f += [name + " fails" for g in graphs if not f(g)]
    detail = t("verify.family.failures", n=len(bad_f))
    if unverifiable:
        detail += "; " + t("verify.family.programmable",
                           names=", ".join(unverifiable))
    checks.append((t("verify.family.filters"), not bad_f, detail))

    buckets: dict = {}
    for g in graphs:
        buckets.setdefault(wl_signature(g), []).append(g)
    dup = 0
    for grp in buckets.values():
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                if is_isomorphic(grp[i], grp[j]):
                    dup += 1
    checks.append((t("verify.family.iso"), dup == 0,
                   t("verify.family.duplicates", n=dup)))
    return checks


def _verify_synth_proved(cert, limits) -> VerifyReport:
    p = cert.payload
    checks, free = [], True
    for key, label in (("synth", t("verify.synth.bounded")),
                       ("universal", t("verify.synth.universal"))):
        sub = p.get(key)
        if sub is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        free = free and rep.solver_free
        checks.append((label + " ({})".format(sub["kind"]), rep.ok, rep.detail))
    return VerifyReport(
        all(k[1] for k in checks), "synth_proved", free, checks=checks,
        detail=t("verify.synth.detail", candidate=p.get("candidate")),
    )


def _verify_farkas(cert, limits) -> VerifyReport:
    """Multiply, add, look. No solver, no search -- this is the good kind."""
    from fractions import Fraction

    from . import exact, linarith

    p = cert.payload
    rows = linarith.parse_rows(p["rows"])
    lams = [Fraction(x) for x in p["multipliers"]]
    checks = []

    checks.append((t("verify.farkas.nonneg"), all(l >= 0 for l in lams),
                   t("verify.farkas.count",
                     n=sum(1 for l in lams if l > 0), total=len(lams))))

    total = linarith.combination(rows, lams)
    leftover = {m: c for m, c in total.items()
                if m != linarith.CONST and c != 0}
    checks.append((t("verify.farkas.cancels"), not leftover,
                   t("verify.farkas.leftover",
                     names=", ".join(" ".join(m) for m in list(leftover)[:3]))))

    ok, const, strict = linarith.is_contradiction(rows, lams)
    checks.append((t("verify.farkas.closes"), ok,
                   t("verify.farkas.closing", const=exact.serialize(const),
                     rel="<" if strict else "<=")))
    checks.append((t("verify.farkas.declared"),
                   exact.to_fraction(p["constant"]) == const
                   and bool(p["strict"]) == bool(strict),
                   p["constant"]))

    warnings = []
    if p.get("vacuous"):
        warnings.append(t("verify.farkas.vacuous"))
    if p.get("nonlinear"):
        warnings.append(t("verify.farkas.derived",
                          n=len(rows) - p.get("base_rows", len(rows))))
    return VerifyReport(
        all(c[1] for c in checks), "farkas", True, checks=checks,
        warnings=warnings,
        detail=t("verify.farkas.detail", n=len(rows)),
    )


def _verify_shrink_domain(cert, limits) -> VerifyReport:
    from .spec import Outcome, load_spec

    p = cert.payload
    checks = []

    src = Path(p["spec_path"])
    if not src.exists():
        return VerifyReport(False, "shrink_domain", True,
                            detail=t("verify.shrink.spec_missing", path=src))
    got = hashlib.sha256(src.read_bytes()).hexdigest()
    checks.append((t("verify.shrink.spec_same"), got == p["spec_sha256"],
                   got[:16]))

    spec = load_spec(src)
    by_id = {spec.id_of(i): i for i in spec.enumerate()}
    start = by_id.get(p["original"])
    if start is None:
        checks.append((t("verify.shrink.replay"), False,
                       t("verify.shrink.item_missing", id=p["original"])))
        return VerifyReport(False, "shrink_domain", True, checks=checks)

    # Replay the recorded descent rather than redoing the search.
    item = start
    for step in p["trace"]:
        options = list(spec.reduce(item))
        if step["index"] >= len(options):
            item = None
            break
        item = options[step["index"]]
        if spec.id_of(item) != step["to"]:
            item = None
            break
    replayed = item is not None and spec.id_of(item) == p["minimal"]
    checks.append((t("verify.shrink.replay"), replayed,
                   t("verify.shrink.replay_detail", steps=len(p["trace"]),
                     item=p["minimal"])))

    def is_ce(x):
        try:
            r = spec.predicate(x) if spec.predicate else True
        except Exception:  # noqa: BLE001
            return False
        ok = r.ok if isinstance(r, Outcome) else bool(r)
        return ok is False

    if replayed:
        checks.append((t("verify.shrink.still_ce_item"), is_ce(item),
                       p["minimal"]))
        survivors = [spec.id_of(c) for c in spec.reduce(item) if is_ce(c)]
        checks.append((t("verify.shrink.none_survive"), not survivors,
                       t("verify.shrink.survivors", names=survivors[:5])))

    return VerifyReport(
        all(c[1] for c in checks), "shrink_domain", True, checks=checks,
        detail=t("verify.shrink.detail"),
    )


def _verify_core_matrix(cert, limits) -> VerifyReport:
    p = cert.payload
    checks, free = [], True

    # Each column is an ordinary core; verifying them is verifying the table.
    for goal, sub in p.get("cores", {}).items():
        rep = verify(Certificate.from_dict(sub), limits)
        free = free and rep.solver_free
        checks.append((t("verify.matrix.goal", goal=goal, kind=sub["kind"]),
                       rep.ok, rep.detail))

    # The table must say exactly what the cores say.
    bad = 0
    for goal, sub in p.get("cores", {}).items():
        used = set(sub["payload"]["names"]) - {"__goal__"}
        for h in p["hypotheses"]:
            if p["table"][h][goal] != (h in used):
                bad += 1
    checks.append((t("verify.matrix.agrees"), bad == 0,
                   t("verify.matrix.mismatch", n=bad)))

    warnings = []
    if p.get("inconclusive"):
        warnings.append(t("verify.matrix.inconclusive", n=len(p["inconclusive"])))

    return VerifyReport(
        all(c[1] for c in checks), "core_matrix", free, checks=checks,
        warnings=warnings,
        detail=t("verify.matrix.detail", goals=len(p["goals"]),
                 hyps=len(p["hypotheses"])),
    )


def _verify_sweep_range(cert, limits) -> VerifyReport:
    p = cert.payload
    checks, free, warnings = [], True, []

    sizes = p["sizes"]
    checks.append((t("verify.range.ordered"), sizes == sorted(sizes),
                   "n = {}".format(sizes)))

    for e in p["entries"]:
        sub = e.get("cert")
        label = t("verify.range.size", n=e["n"], verdict=e["verdict"])
        if sub is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        free = free and rep.solver_free
        checks.append((label, rep.ok, rep.detail))

    first = p.get("first_failure")
    below = [e for e in p["entries"]
             if first is not None and e["n"] < first and e["verdict"] == "refuted"]
    checks.append((t("verify.range.nothing_below"), not below,
                   "" if first is None else "first failure at n={}".format(first)))

    if p.get("stopped_early"):
        warnings.append(t("verify.range.stopped"))

    return VerifyReport(
        all(c[1] for c in checks), "sweep_range", free, checks=checks,
        warnings=warnings,
        detail=t("verify.range.detail", sizes=len(sizes),
                 first="n={}".format(first) if first is not None else "-"),
    )


def _verify_domain_sweep(cert, limits) -> VerifyReport:
    p = cert.payload
    ids = p["ids"]
    h = hashlib.sha256(chr(10).join(sorted(ids)).encode()).hexdigest()
    checks = [(t("verify.family.hash"), h == p["ids_sha256"], h[:16]),
              (t("verify.domain.unique"), len(set(ids)) == len(ids),
               t("verify.domain.duplicates", n=len(ids) - len(set(ids))))]
    checks += _verify_entries_and_stats(p, limits)
    return VerifyReport(
        all(c[1] for c in checks), "domain_sweep", cert.solver_free,
        checks=checks, warnings=_sweep_warnings(p),
        detail=t("verify.domain.detail", n=p["count"]),
    )


def _verify_entries_and_stats(p, limits) -> list:
    """Predicate certificates and calibration: shared by both sweep kinds."""
    checks = []
    entries = p.get("entries", [])
    with_cert = [e for e in entries if e.get("cert")]
    bad = [e["g6"] for e in with_cert
           if not verify(Certificate.from_dict(e["cert"]), limits).ok]
    checks.append(
        (t("verify.sweep.predicate"), not bad,
         t("verify.sweep.entries", certified=len(with_cert), total=len(entries),
           failing="" if not bad else t("verify.sweep.failing",
                                        names=", ".join(bad[:3]))))
    )
    vals = p.get("values") or []
    if vals and p.get("stats"):
        from . import exact

        recomputed = exact.stats([v["value"] for v in vals])
        declared = {k: exact.to_fraction(v) for k, v in p["stats"].items()}
        checks.append((t("verify.sweep.stats"),
                       all(recomputed[k] == declared[k] for k in declared),
                       t("verify.sweep.values", n=len(vals))))
    return checks


def _sweep_warnings(p) -> list:
    out = []
    entries = p.get("entries", [])
    missing = len(entries) - sum(1 for e in entries if e.get("cert"))
    if missing:
        out.append(t("verify.sweep.missing", missing=missing, total=len(entries)))
    c = p.get("counts", {})
    if c.get("errors") or c.get("inconclusive"):
        out.append(t("verify.sweep.unevaluated",
                     n=c.get("errors", 0) + c.get("inconclusive", 0)))
    return out


def _verify_sweep(cert, limits) -> VerifyReport:
    p = cert.payload
    checks = _verify_family(p["family_graph6"], p["n"], p["filters"],
                            p["family_sha256"])

    entries = p.get("entries", [])
    with_cert = [e for e in entries if e.get("cert")]
    bad = []
    for e in with_cert:
        rep = verify(Certificate.from_dict(e["cert"]), limits)
        if not rep.ok:
            bad.append(e["g6"])
    checks.append(
        (t("verify.sweep.predicate"), not bad,
         t("verify.sweep.entries", certified=len(with_cert), total=len(entries),
           failing="" if not bad else t("verify.sweep.failing",
                                        names=", ".join(bad[:3]))))
    )

    vals = p.get("values") or []
    if vals and p.get("stats"):
        from . import exact

        recomputed = exact.stats([v["value"] for v in vals])
        declared = {k: exact.to_fraction(v) for k, v in p["stats"].items()}
        agree = all(recomputed[k] == declared[k] for k in declared)
        checks.append((t("verify.sweep.stats"), agree,
                       t("verify.sweep.values", n=len(vals))))

    warnings = []
    missing = len(entries) - len(with_cert)
    if missing:
        warnings.append(t("verify.sweep.missing", missing=missing,
                          total=len(entries)))
    c = p.get("counts", {})
    if c.get("errors") or c.get("inconclusive"):
        warnings.append(t("verify.sweep.unevaluated",
                          n=c.get("errors", 0) + c.get("inconclusive", 0)))

    return VerifyReport(
        all(k[1] for k in checks), "sweep", cert.solver_free, checks=checks,
        warnings=warnings,
        detail=t("verify.sweep.detail", n=p["family_count"]),
    )


def _verify_graph_set(cert, limits) -> VerifyReport:
    p = cert.payload
    g6 = p["graph6"]
    checks = _verify_family(g6, p["n"], p["filters"], p["sha256"])
    return VerifyReport(
        all(c[1] for c in checks), "graph_set", True, checks=checks,
        detail=t("verify.sweep.detail", n=len(g6)),
    )


# ---------------------------------------------------------------------------


def _const(z3, name, sort):
    return {"Int": z3.Int, "Real": z3.Real, "Bool": z3.Bool}[sort](name)


def _value(z3, sort, val):
    if sort == "Int":
        return z3.IntVal(val)
    if sort == "Real":
        return z3.RealVal(val)
    if sort == "Bool":
        return z3.BoolVal(val)
    raise ValueError("sort no soportado: " + str(sort))
