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

# FROZEN AT 0.4. From this version an existing payload's fields do not move:
# no renames, no removals, no changes of meaning. Adding a NEW certificate
# kind stays allowed and always will -- that is additive and breaks nothing --
# and so does adding an OPTIONAL field that readers may ignore. Anything else
# needs a bump here and a migration note in CHANGELOG.md.
#
# What this buys: a certificate produced for a paper today still verifies
# against a later certo, which is the only way "re-verifiable" survives
# contact with time.
SCHEMA_VERSION = 4


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

    @staticmethod
    def unwrap(d: dict) -> dict:
        """The certificate, whether it arrived alone or inside a run.

        `--cert FILE` writes the certificate; `--json` writes the RUN, which
        contains one under `certificate`. Both shapes are right and a reader
        who guesses wrong loses an afternoon, so anything that expects a
        certificate accepts either. They are told apart by what is at the
        root: a certificate has `kind`, a run has `command`.
        """
        if isinstance(d, dict) and "kind" not in d and "certificate" in d:
            inner = d["certificate"]
            if isinstance(inner, dict):
                return inner
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Certificate":
        d = cls.unwrap(d)
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
    # How the checking was done. `solver_free` says a solver was not needed,
    # which is not the same as saying nothing was run: replaying a sweep runs
    # the user's own predicate. Naming the method keeps the header honest.
    method_key: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "solver_free": self.solver_free,
            "method": self.method_key,
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
                           vacuous: bool = False, clash=None) -> Certificate:
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
                 # `clash` is optional, which the frozen schema allows: a
                 # reader that does not know it simply ignores it.
                 "vacuous": bool(vacuous), "clash": clash or []},
        note_key="cert.note.unsat_core",
    )


def lp_dual_certificate(sense, objective, dual, A, b, c, names,
                        primal=None, var_names=None, is_exact=False,
                        integer=False, integral_point=None,
                        integral_objective=None, kinds=None,
                        target=None) -> Certificate:
    return Certificate(
        kind="lp_dual",
        solver_free=True,
        payload={
            "sense": sense, "objective": objective, "dual": dual,
            "primal": primal, "A": A, "b": b, "c": c,
            "names": names, "var_names": var_names, "exact": is_exact,
            # For an ILP the dual certifies the RELAXATION, which is a bound.
            # The integral point is the other side of it.
            "integer": bool(integer), "integral_point": integral_point,
            "integral_objective": integral_objective,
            # Which variables are discrete, by name. `integer: true` says a
            # discrete part exists; this says WHICH, so a reader of the
            # certificate alone can tell a design from a relaxation.
            "kinds": kinds or {}, "target": target,
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
                      values=None, stats=None, outcomes="",
                      orbits=None, labelled=0, by_orbit=False,
                      spot_checks=None, evaluated=0) -> Certificate:
    """The examined family, the VERDICT VECTOR, and whatever certificates the
    predicate supplied.

    Three things, and they establish three different amounts. The family and
    its hash say which objects were looked at. The verdict vector says what
    the predicate answered for each, and lets a later run confirm it answers
    the same -- reproducible, not certified. Only the third part, a
    certificate per evaluation, establishes the answers themselves without
    trusting the predicate.

    `evaluations` and `certified` are counted over the WHOLE sweep, not over
    the stored entries. A passing sweep stores no entries, and reporting
    "0 of 0 certified" for eleven thousand unchecked evaluations is how a
    certificate ends up claiming more than it holds.
    """
    h = hashlib.sha256("\n".join(sorted(family_g6)).encode()).hexdigest()
    certified = sum(1 for e in entries if e.get("cert"))
    free = all(e["cert"].get("solver_free") for e in entries if e.get("cert"))
    evaluations = counts.get("examined", len(family_g6))
    return Certificate(
        kind="sweep",
        solver_free=bool(free),
        payload={"n": n, "filters": filters, "family_sha256": h,
                 "family_count": len(family_g6), "family_graph6": family_g6,
                 "entries": entries, "mode": mode, "counts": counts,
                 "values": values or [], "stats": stats,
                 "evaluations": evaluations, "certified": certified,
                 "outcomes": outcomes,
                 "outcomes_sha256": outcomes_digest(outcomes) if outcomes else "",
                 "orbits": orbits, "labelled": labelled,
                 "by_orbit": by_orbit, "spot_checks": spot_checks,
                 "evaluated": evaluated},
        note_key="cert.note.sweep",
        note_args={"certified": certified, "total": evaluations},
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
                             stats=None, title="", outcomes="",
                             orbits=None, labelled=0, by_orbit=False,
                             spot_checks=None, evaluated=0) -> Certificate:
    """Same contract as `sweep`, for a domain the spec defines itself.

    Including the same three levels: the domain and its hash, the verdict
    vector that makes the run replayable, and the per-evaluation certificates
    that would make it certified.
    """
    h = hashlib.sha256(chr(10).join(sorted(ids)).encode()).hexdigest()
    free = all(e["cert"].get("solver_free") for e in entries if e.get("cert"))
    certified = sum(1 for e in entries if e.get("cert"))
    evaluations = counts.get("examined", len(ids))
    return Certificate(
        kind="domain_sweep", solver_free=bool(free),
        payload={"title": title, "ids": ids, "ids_sha256": h,
                 "count": len(ids), "entries": entries, "mode": mode,
                 "counts": counts, "values": values or [], "stats": stats,
                 "evaluations": evaluations, "certified": certified,
                 "outcomes": outcomes,
                 "outcomes_sha256": outcomes_digest(outcomes) if outcomes else "",
                 "orbits": orbits, "labelled": labelled,
                 "by_orbit": by_orbit, "spot_checks": spot_checks,
                 "evaluated": evaluated},
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
                       derived=None, spec_path="") -> Certificate:
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
                 "derived": derived or {}, "spec_path": str(spec_path)},
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



def induction_certificate(k0, base_upto, step_from, base, step, step_smt2,
                          conclusion, bridge="", title="") -> Certificate:
    """The induction schema, applied, with both halves attached.

    The schema itself is not a solver result and is not pretending to be one.
    What travels is: a certificate per base case, a certificate for the step
    proved with the index FREE, and the two numbers that decide whether the
    chain actually joins up. Those numbers are the part a write-up gets wrong
    and a pile of certificates cannot expose.
    """
    return Certificate(
        kind="induction", solver_free=False,
        payload={"k0": k0, "base_upto": base_upto, "step_from": step_from,
                 "base": base, "step": step, "step_smt2": step_smt2,
                 "conclusion": conclusion, "bridge": bridge, "title": title},
        note_key="cert.note.induction",
    )



def orbit_witnesses_certificate(sweep_cert, witnesses, labelled,
                                title="") -> Certificate:
    """A refuted sweep, quotiented, and one minimal witness per orbit.

    The three steps a combinatorial refutation actually wants -- how many
    counterexamples there are, how many objects that really is, and what the
    smallest version of each looks like -- travel as one artefact instead of
    three files someone has to line up by hand.

    Nothing new is proved here: each part carries its own certificate and
    verification cascades into all of them. What this adds is that they are
    about THE SAME RUN, which a directory of certificates cannot say.
    """
    return Certificate(
        kind="orbit_witnesses", solver_free=False,
        payload={"title": title, "sweep": sweep_cert, "witnesses": witnesses,
                 "labelled": labelled, "orbits": len(witnesses)},
        note_key="cert.note.orbit_witnesses",
    )



def ideal_certificate(variables, equations, claim, cofactors, inconsistent,
                      title="") -> Certificate:
    """`f = sum h_i g_i`, with the cofactors attached.

    Finding them is a Groebner basis computation; checking them is expanding a
    product. That gap is the whole reason this travels as a certificate rather
    than as "the algebra system agreed".

    With `claim` absent the left-hand side is 1, and the certificate refutes
    the system outright -- over the complex numbers, hence over everything
    smaller. It does NOT say a real solution exists when it fails.
    """
    return Certificate(
        kind="ideal", solver_free=True,
        payload={"variables": list(variables), "equations": equations,
                 "claim": claim, "cofactors": cofactors,
                 "inconsistent": bool(inconsistent), "title": title},
        note_key="cert.note.ideal",
    )


def sos_certificate(variables, poly, terms, basis_size, denom,
                    title="") -> Certificate:
    """`p = sum d_i q_i^2` in exact rationals.

    The Gram matrix was found in floating point and is not here: it was the
    search. What is here are rational coefficients and rational linear forms,
    and checking them is multiplying polynomials out.
    """
    return Certificate(
        kind="sos", solver_free=True,
        payload={"variables": list(variables), "poly": poly, "terms": terms,
                 "squares": len(terms), "basis_size": basis_size,
                 "denominator": denom, "title": title},
        note_key="cert.note.sos",
    )


def number_certificate(kind, tree, title="") -> Certificate:
    """A Pratt primality tree, or a factorisation whose factors carry one.

    `n.is_prime()` is true, fast and unciteable. This is the same fact with
    the evidence attached, and the evidence is a handful of `pow(a, e, n)`.
    """
    return Certificate(
        kind="number", solver_free=True,
        payload={"question": kind, "tree": tree, "n": tree["n"],
                 "title": title},
        note_key="cert.note.number",
    )



def mixed_design_certificate(assignment, continuous, kinds, system, objective,
                             sense, discrete_gain, conditional, achieved,
                             residual_cert, relaxation_cert, bound, target,
                             globally_optimal, level="conditional_optimum",
                             skeleton_from="CBC", title="") -> Certificate:
    """A discrete skeleton, the exact packing inside it, and what that reaches.

    Three numbers that are not the same number, kept apart on purpose:

      achieved     what this construction attains. Exact, and a genuine LOWER
                   bound on the true optimum, because the thing exists.
      conditional  the best the continuous part can do WITH THIS SKELETON,
                   from the residual LP's exact dual.
      bound        the relaxation over ALL skeletons: an UPPER bound.

    What is certified: the assignment is integral and in range, the full point
    satisfies every original constraint exactly, the residual LP really is the
    original problem with that assignment substituted, and its dual is exact.

    What is NOT certified, unless `achieved` meets `bound`: that this skeleton
    is the best one. The search was CBC and nothing here re-does it. For an
    existence proof that is the right amount to claim -- exhibiting a
    construction that reaches the target is the whole job.
    """
    return Certificate(
        kind="mixed_design", solver_free=True,
        payload={"assignment": assignment, "continuous": continuous,
                 "kinds": kinds, "system": system, "objective": objective,
                 "sense": sense, "discrete_gain": discrete_gain,
                 "conditional": conditional, "achieved": achieved,
                 "residual": residual_cert, "relaxation": relaxation_cert,
                 "bound": bound, "target": target,
                 "globally_optimal": bool(globally_optimal),
                 "level": level, "skeleton_from": skeleton_from,
                 "title": title},
        note_key="cert.note.mixed_design",
    )



def gap_certificate(fractional, integral, mu, nu, gap, tight, level,
                    title="") -> Certificate:
    """The integrality gap of a packing, with both sides attached.

    `nu` against `mu*` used to be two runs someone subtracted afterwards --
    two artefacts, and two chances to line up the wrong pair. Here they travel
    together and verification checks they are about THE SAME packing, which a
    folder of certificates cannot say.

    `tight` names the resources carrying positive load in the fractional dual:
    the obstruction, in the language of the problem rather than of the LP.
    """
    return Certificate(
        kind="gap", solver_free=False,
        payload={"fractional": fractional, "integral": integral,
                 "mu": mu, "nu": nu, "gap": gap, "tight": tight,
                 "level": level, "title": title},
        note_key="cert.note.gap",
    )



def farkas_ray_certificate(A, b, y, names) -> Certificate:
    """`Ax <= b, x >= 0` has no solution, and here is why.

    A ray `y >= 0` with `A^T y >= 0` and `b.y < 0`. For any feasible x this
    gives `0 <= (A^T y).x = y.(Ax) <= y.b < 0`, so there is no feasible x.
    Checking it is three dot products in exact rationals -- no solver, and no
    trusting the one that said "infeasible".
    """
    return Certificate(
        kind="farkas_ray", solver_free=True,
        payload={"A": A, "b": b, "y": y, "names": names},
        note_key="cert.note.farkas_ray",
    )


def branch_bound_certificate(incumbent, incumbent_cert, nodes, order, sense,
                             title="") -> Certificate:
    """The optimum, and the account of every design that was not taken.

    To say "no design does better" you have to account for all of them. Each
    node here is closed by a certificate -- an exact dual bounding its subtree
    below the incumbent, a Farkas ray showing it is empty, or the residual LP
    of a fully fixed design -- and the tree is checked to COVER the integer
    domain, node by node. A tree with a missing child is a proof that some
    designs were never looked at, and it reads exactly like a complete one.
    """
    return Certificate(
        kind="branch_bound", solver_free=False,
        payload={"incumbent": incumbent, "incumbent_cert": incumbent_cert,
                 "nodes": nodes, "order": order, "sense": sense,
                 "title": title},
        note_key="cert.note.branch_bound",
    )



def order_certificate(laurent, orders, var, terms, collected, degree, verdict,
                      expect, cancelled, title="") -> Certificate:
    """The exponent of `var`, and the substitution that produced it.

    The Laurent polynomial travels, so re-checking this needs neither z3 nor
    the spec: substitute the orders, collect, read the leading exponent. Pure
    exact arithmetic.

    What it certifies is the EXPONENT, not the constant in front of it. `≍`
    hides a factor, so a Theta(1) term with a coefficient of 1e-9 may be
    perfectly fine in practice. What the certificate says is that it does not
    shrink with `var`, and it says only that.
    """
    return Certificate(
        kind="asymptotic", solver_free=True,
        payload={"laurent": laurent, "orders": orders, "var": var,
                 "terms": terms, "collected": collected, "degree": degree,
                 "verdict": verdict, "expect": expect, "cancelled": cancelled,
                 "title": title},
        note_key="cert.note.asymptotic",
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
# how much a sweep actually establishes
# ---------------------------------------------------------------------------
#
# Three levels, and the distance between them is the whole point. A sweep
# whose predicate returns a bare `bool` establishes far less than one whose
# predicate returns certificates, and the difference used to be invisible:
# both printed "FINITE CASE VERIFIED". These names exist so it cannot be.

CERTIFIED = "certified"        # every evaluation carries its own certificate
REPRODUCIBLE = "reproducible"  # no certificates, but the run can be replayed
RECORDED = "recorded"          # neither: only the domain and its hash
NO_PREDICATE = "no_predicate"  # a calibration run: nothing to certify


def outcome_code(out) -> str:
    """One character per item. T true, F false, ? inconclusive, E error.

    Lower case means INFERRED from an orbit representative rather than
    computed -- `--by-orbit`. A reader can see at a glance how much of a
    verdict vector was actually run.
    """
    if getattr(out, "errored", False):
        return "E"
    if out.ok is None:
        return "?"
    return "T" if out.ok else "F"


def outcomes_digest(codes: str) -> str:
    """The whole verdict vector in 64 hex characters.

    Storing the vector itself would be megabytes on a large sweep and would
    add nothing: on a mismatch the verifier holds both vectors anyway and can
    name the first item that disagrees.
    """
    return hashlib.sha256(codes.encode()).hexdigest()


def sweep_strength(payload: dict, spec_replayable: bool) -> str:
    """What this certificate establishes about the PREDICATE, right now.

    Deliberately computed rather than stored: `reproducible` depends on the
    spec still being there, which is true at issue time and may not be true at
    verification time. A stored label would quietly become a lie.
    """
    ev = payload.get("evaluations", 0)
    if ev and payload.get("certified", 0) >= ev:
        return CERTIFIED
    if payload.get("outcomes_sha256") and spec_replayable:
        return REPRODUCIBLE
    return RECORDED


def _spec_from(cert):
    """The spec that produced a certificate, if it is still the same file."""
    prov = cert.provenance or {}
    sp, want = prov.get("spec_path"), prov.get("spec_sha256")
    if not sp:
        return None, "no_path"
    p = Path(sp)
    if not p.exists():
        return None, "gone"
    if want and hashlib.sha256(p.read_bytes()).hexdigest() != want:
        return None, "changed"
    return p, ""


# ---------------------------------------------------------------------------
# verificacion
# ---------------------------------------------------------------------------

def _replay(cert, limits, kind):
    """Re-run the predicate and compare the verdict vector.

    This is the honest middle ground between "we checked every evaluation" and
    "we checked nothing about the predicate". It does NOT verify the predicate
    -- it verifies that running it again gives the same answers, which makes
    the sweep reproducible rather than merely recorded. The difference is
    named everywhere it is reported.

    Returns (ok, detail) with ok=None when the replay could not be done at
    all, so that "not checked" never renders as "checked and fine".
    """
    import time

    from .limits import Limits

    p = cert.payload
    want = p.get("outcomes_sha256")
    if not want:
        return None, t("verify.sweep.replay.no_vector")

    path, why = _spec_from(cert)
    if path is None:
        return None, t("verify.sweep.replay." + (why if why else "no_path"))

    lim = limits or Limits()
    t0 = time.perf_counter()
    from .spec import load_spec

    spec = load_spec(path)

    if kind == "sweep":
        from .engines.graphsearch import _evaluate, orbit_codes
        from .graphs import Graph

        items = [Graph.from_graph6(s) for s in p.get("family_graph6", [])]
        ids = list(p.get("family_graph6", []))
        if p.get("by_orbit"):
            from . import orbits as orb

            groups = orb.build(spec, items, ids)
            if groups is None:
                return False, t("verify.sweep.replay.no_symmetry")
            got = "".join(orbit_codes(spec, items, groups)[1])
            if outcomes_digest(got) == want:
                return True, t("verify.sweep.replay.agrees", n=len(got))
            old = p.get("outcomes", "")
            where = next((i for i, c in enumerate(got)
                          if i < len(old) and c != old[i]), 0)
            return False, t("verify.sweep.replay.differs",
                            item=ids[where] if where < len(ids) else "?",
                            index=where)
    else:
        from .engines.domain import _evaluate

        items = spec.enumerate()
        ids = [spec.id_of(i) for i in items]
        if ids != list(p.get("ids", [])):
            return False, t("verify.sweep.replay.domain_moved")

        if p.get("by_orbit"):
            # Reproduce the INFERENCE, not a full evaluation: a --by-orbit run
            # never computed the non-representatives, so re-computing them here
            # would disagree with the stored vector by construction.
            from . import orbits as orb
            from .engines.domain import orbit_codes

            groups = orb.build(spec, items, ids)
            if groups is None:
                return False, t("verify.sweep.replay.no_symmetry")
            got = "".join(orbit_codes(spec, items, groups)[1])
            if outcomes_digest(got) == want:
                return True, t("verify.sweep.replay.agrees", n=len(got))
            old = p.get("outcomes", "")
            where = next((i for i, c in enumerate(got)
                          if i < len(old) and c != old[i]), 0)
            return False, t("verify.sweep.replay.differs",
                            item=ids[where] if where < len(ids) else "?",
                            index=where)

    codes = []
    for item in items:
        codes.append(outcome_code(_evaluate(spec, item)))
        if (time.perf_counter() - t0) * 1000 > lim.timeout_ms:
            return None, t("verify.sweep.replay.timeout", done=len(codes),
                           total=len(items))

    got = "".join(codes)
    if outcomes_digest(got) == want:
        return True, t("verify.sweep.replay.agrees", n=len(got))

    # Both vectors are in hand, so say WHICH item moved rather than "differs".
    old = p.get("outcomes", "")
    where = next((i for i, c in enumerate(got) if i < len(old) and c != old[i]),
                 min(len(got), len(old)))
    name = ids[where] if where < len(ids) else "?"
    return False, t("verify.sweep.replay.differs", item=name, index=where)



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
        "induction": _verify_induction,
        "orbit_witnesses": _verify_orbit_witnesses,
        "ideal": _verify_ideal,
        "sos": _verify_sos,
        "number": _verify_number,
        "mixed_design": _verify_mixed_design,
        "gap": _verify_gap,
        "farkas_ray": _verify_farkas_ray,
        "branch_bound": _verify_branch_bound,
        "asymptotic": _verify_asymptotic,
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



def _verify_induction(cert, limits) -> VerifyReport:
    import z3

    p = cert.payload
    checks, warnings = [], []
    k0, upto, step_from = p["k0"], p["base_upto"], p["step_from"]

    # --- the chain joins up ------------------------------------------------
    ks = [b["k"] for b in p["base"]]
    want = list(range(k0, upto + 1))
    checks.append((t("verify.induction.covered"), ks == want,
                   t("verify.induction.range", k0=k0, upto=upto,
                     got=len(ks))))
    checks.append((t("verify.induction.joins"), step_from <= upto,
                   t("verify.induction.step_from", step=step_from, upto=upto)))

    # --- every base case ---------------------------------------------------
    for b in p["base"]:
        sub = b.get("cert")
        label = t("verify.induction.base", k=b["k"])
        if sub is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        checks.append((label, rep.ok, "{}: {}".format(sub["kind"], rep.detail)))
        warnings.extend("k={}: {}".format(b["k"], w) for w in rep.warnings)
        if not b.get("derived") and p.get("bridge"):
            warnings.append(t("verify.induction.bridge", k=b["k"],
                              why=p["bridge"]))

    # --- the step ----------------------------------------------------------
    step = p.get("step")
    if step is None:
        checks.append((t("verify.induction.step"), False,
                       t("verify.bisect.no_cert")))
    else:
        rep = verify(Certificate.from_dict(step), limits)
        checks.append((t("verify.induction.step"), rep.ok, rep.detail))
        phi = _parse_one(p["step_smt2"])
        obl = obligations_of(step)
        linked = bool(obl) and entails(z3.Not(phi), obl, limits)
        checks.append((t("verify.induction.step_link"), linked,
                       t("verify.proof.link_detail", n=len(obl or []))))

    warnings.append(t("verify.induction.schema"))
    return VerifyReport(
        all(c[1] for c in checks), "induction", False, checks=checks,
        warnings=warnings,
        detail=t("verify.induction.detail", n=len(ks), k0=k0, upto=upto),
    )



def _verify_orbit_witnesses(cert, limits) -> VerifyReport:
    p = cert.payload
    checks, warnings, free = [], [], True

    sub = p.get("sweep")
    if sub is None:
        checks.append((t("verify.witness.sweep"), False,
                       t("verify.bisect.no_cert")))
    else:
        rep = verify(Certificate.from_dict(sub), limits)
        checks.append((t("verify.witness.sweep"), rep.ok, rep.detail))
        warnings.extend(rep.warnings)
        free = free and rep.solver_free

        # The representatives minimised here must be the representatives the
        # sweep found. Otherwise this is three certificates about three runs.
        want = {row["representative"] for row in (sub["payload"].get("orbits") or [])}
        got = {w["representative"] for w in p["witnesses"]}
        checks.append((t("verify.witness.same_run"), got <= want,
                       t("verify.witness.stray",
                         names=", ".join(sorted(got - want)[:3]) or "-")))

    for w in p["witnesses"]:
        label = t("verify.witness.one", rep=w["representative"])
        wc = w.get("cert")
        if wc is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(wc), limits)
        checks.append((label, rep.ok, "{} -> {}".format(w["minimal"], rep.detail)))
        warnings.extend("{}: {}".format(w["representative"], x)
                        for x in rep.warnings)
        free = free and rep.solver_free

    return VerifyReport(
        all(c[1] for c in checks), "orbit_witnesses", free, checks=checks,
        warnings=warnings,
        detail=t("verify.witness.detail", labelled=p["labelled"],
                 orbits=p["orbits"]),
    )



def _verify_ideal(cert, limits) -> VerifyReport:
    """Expand the combination and compare. No solver, no algebra system."""
    from .polynomials import Poly, combination

    p = cert.payload
    variables = tuple(p["variables"])
    gs = [Poly.parse(variables, g) for g in p["equations"]]
    hs = [Poly.parse(variables, h) for h in p["cofactors"]]
    lhs = (Poly.const(variables, 1) if p["inconsistent"]
           else Poly.parse(variables, p["claim"]))

    checks = [(t("verify.ideal.count"), len(hs) == len(gs),
               t("verify.ideal.n", h=len(hs), g=len(gs)))]
    if len(hs) == len(gs):
        got = combination(hs, gs)
        checks.append((t("verify.ideal.expands"), got == lhs,
                       t("verify.ideal.difference", d=str(got - lhs)[:60])))

    warnings = []
    if p["inconsistent"]:
        warnings.append(t("verify.ideal.field"))
    return VerifyReport(
        all(c[1] for c in checks), "ideal", True, checks=checks,
        warnings=warnings,
        detail=t("verify.ideal.detail", n=len(gs),
                 what=t("verify.ideal.inconsistent") if p["inconsistent"]
                 else t("verify.ideal.member")),
    )


def _verify_sos(cert, limits) -> VerifyReport:
    """Square the forms, add them up, compare coefficients."""
    from . import sos as sosmod
    from .polynomials import Poly

    p = cert.payload
    variables = tuple(p["variables"])
    target = Poly.parse(variables, p["poly"])
    terms = sosmod.parse(variables, p["terms"])

    checks = [(t("verify.sos.nonneg"), all(d >= 0 for d, _ in terms),
               t("verify.sos.count", n=len(terms)))]
    got = sosmod.expand(terms, variables)
    checks.append((t("verify.sos.expands"), got == target,
                   t("verify.ideal.difference", d=str(got - target)[:60])))
    return VerifyReport(
        all(c[1] for c in checks), "sos", True, checks=checks,
        detail=t("verify.sos.detail", n=len(terms)),
    )


def _verify_number(cert, limits) -> VerifyReport:
    """Modular exponentiation, and nothing else."""
    from . import numbers

    p = cert.payload
    tree = p["tree"]
    if p["question"] == "factor":
        checks = numbers.verify_factorisation(tree)
    else:
        checks = numbers.verify_pratt(tree)
    return VerifyReport(
        all(c[1] for c in checks), "number", True, checks=checks,
        detail=t("verify.number.detail", n=p["n"], checks=len(checks)),
    )



def _verify_mixed_design(cert, limits) -> VerifyReport:
    """The construction, checked; the optimality, not claimed."""
    from fractions import Fraction

    from . import exact

    p = cert.payload
    kinds = p["kinds"]
    assign = {k: exact.to_fraction(v) for k, v in p["assignment"].items()}
    cont = {k: exact.to_fraction(v) for k, v in p["continuous"].items()}
    point = dict(assign)
    point.update(cont)
    checks, warnings = [], []

    # 1. the discrete part really is discrete
    off = [k for k, v in assign.items() if v.denominator != 1]
    binary_off = [k for k, v in assign.items()
                  if kinds.get(k) == "binary" and v not in (0, 1)]
    checks.append((t("verify.mixed.integral"), not off and not binary_off,
                   t("verify.mixed.offenders",
                     names=", ".join((off + binary_off)[:3]) or "-")))

    # 2. every ORIGINAL constraint, at the full point
    bad = []
    for row in p["system"]:
        lhs = sum((exact.to_fraction(c) * point.get(v, Fraction(0))
                   for v, c in row["coeffs"].items()), Fraction(0))
        rhs = exact.to_fraction(row["rhs"])
        ok = (lhs <= rhs if row["sense"] == "<=" else
              lhs >= rhs if row["sense"] == ">=" else lhs == rhs)
        if not ok:
            bad.append(row["name"])
    checks.append((t("verify.mixed.feasible"), not bad,
                   t("verify.mixed.violated", names=", ".join(bad[:3]) or "-",
                     n=len(p["system"]))))

    # 3. the value it claims to attain
    got = sum((exact.to_fraction(c) * point.get(v, Fraction(0))
               for v, c in p["objective"].items()), Fraction(0))
    checks.append((t("verify.mixed.value"),
                   got == exact.to_fraction(p["achieved"]),
                   t("verify.lp.declared", value=p["achieved"])))

    # 4. the residual LP is the original with THIS assignment substituted.
    #    Without this the sub-certificate could be about a different problem,
    #    which is the same gap `compose` closes between a lemma and its use.
    sub = p.get("residual")
    if sub is None:
        checks.append((t("verify.mixed.residual"), False,
                       t("verify.bisect.no_cert")))
    else:
        rep = verify(Certificate.from_dict(sub), limits)
        checks.append((t("verify.mixed.residual"), rep.ok, rep.detail))
        warnings.extend(rep.warnings)
        checks.append((t("verify.mixed.substituted"),
                       _residual_matches(p, assign, sub), ""))

    # 5. the target, compared exactly.
    #    A design that falls short is not an INVALID certificate -- it is a
    #    valid certificate for a design that falls short, and saying otherwise
    #    would read as "something is broken" when nothing is. So the shortfall
    #    is a warning and what gets CHECKED is that the arithmetic is right.
    if p.get("target") is not None:
        want = exact.to_fraction(p["target"])
        got = exact.to_fraction(p["achieved"])
        if got < want:
            warnings.append(t("verify.mixed.short",
                              value=p["achieved"], target=p["target"],
                              deficit=exact.serialize(want - got)))
        else:
            checks.append((t("verify.mixed.target"), True,
                           t("verify.mixed.margin", value=p["achieved"],
                             target=p["target"],
                             margin=exact.serialize(got - want))))

    # 6. optimality: claimed only when the two bounds meet
    if p.get("globally_optimal"):
        bound = p.get("bound")
        checks.append((t("verify.mixed.optimal"),
                       bound is not None
                       and exact.to_fraction(bound) == exact.to_fraction(p["achieved"]),
                       t("verify.lp.declared", value=bound or "-")))
    else:
        warnings.append(t("verify.mixed.not_optimal",
                          bound=p.get("bound") or "-"))
    if p.get("skeleton_from") == "external":
        warnings.append(t("verify.mixed.external"))

    level = p.get("level", "conditional_optimum")
    return VerifyReport(
        all(c[1] for c in checks), "mixed_design", True, checks=checks,
        warnings=warnings,
        detail=t("verify.mixed.level." + level) + " -- "
        + t("verify.mixed.detail", value=p["achieved"],
            n=len([k for k, v in assign.items() if v])),
    )


def _residual_matches(p, assign, sub) -> bool:
    """Is the sub-certificate's system the original one, frozen at `assign`?"""
    from fractions import Fraction

    from . import exact

    names = sub["payload"].get("names") or []
    var_names = sub["payload"].get("var_names") or []
    A = [exact.parse_all(r) for r in sub["payload"]["A"]]
    b = exact.parse_all(sub["payload"]["b"])
    by_name = dict(zip(names, zip(A, b)))

    for row in p["system"]:
        if row["name"] not in by_name:
            return False
        got_row, got_rhs = by_name[row["name"]]
        moved = sum((exact.to_fraction(c) * assign[v]
                     for v, c in row["coeffs"].items() if v in assign),
                    Fraction(0))
        want_rhs = exact.to_fraction(row["rhs"]) - moved
        # `as_leq_system` flips a >= row, so compare up to that sign.
        flip = -1 if row["sense"] == ">=" else 1
        if got_rhs != flip * want_rhs:
            return False
        for j, v in enumerate(var_names):
            want = exact.to_fraction(row["coeffs"].get(v, 0)) * flip
            if got_row[j] != want:
                return False
    return True



def _verify_gap(cert, limits) -> VerifyReport:
    from . import exact

    p = cert.payload
    checks, warnings = [], []

    for key, label in (("fractional", t("verify.gap.fractional")),
                       ("integral", t("verify.gap.integral"))):
        sub = p.get(key)
        if sub is None:
            checks.append((label, False, t("verify.bisect.no_cert")))
            continue
        rep = verify(Certificate.from_dict(sub), limits)
        checks.append((label, rep.ok, rep.detail))
        warnings.extend(rep.warnings)

    # The two halves must be about the SAME packing. Without this the gap is
    # a subtraction of two numbers that were never compared.
    same = _same_packing(p)
    checks.append((t("verify.gap.same"), same, ""))

    mu, nu = exact.to_fraction(p["mu"]), exact.to_fraction(p["nu"])
    checks.append((t("verify.gap.arithmetic"),
                   mu - nu == exact.to_fraction(p["gap"]),
                   "{} - {} = {}".format(p["mu"], p["nu"], p["gap"])))
    checks.append((t("verify.gap.order"), nu <= mu,
                   t("verify.gap.relaxation")))

    if p.get("level") != "global_optimum":
        warnings.append(t("verify.gap.nu_not_optimal"))

    return VerifyReport(
        all(c[1] for c in checks), "gap", False, checks=checks,
        warnings=warnings,
        detail=t("verify.gap.detail", mu=p["mu"], nu=p["nu"], gap=p["gap"]),
    )


def _same_packing(p) -> bool:
    """Both sides must carry the same constraint matrix and objective."""
    frac = (p.get("fractional") or {}).get("payload") or {}
    whole = (p.get("integral") or {}).get("payload") or {}
    system = whole.get("system")
    if not system or not frac.get("names"):
        return False
    # The mixed certificate keeps the original rows by name; the lp_dual one
    # keeps them positionally. Same names, same count, is what can be checked
    # from the two payloads alone.
    return [r["name"] for r in system] == list(frac["names"])



def _verify_farkas_ray(cert, limits) -> VerifyReport:
    """Three dot products. That is the whole thing."""
    from fractions import Fraction

    from . import exact

    p = cert.payload
    A = [exact.parse_all(r) for r in p["A"]]
    b, y = exact.parse_all(p["b"]), exact.parse_all(p["y"])
    cols = len(A[0]) if A else 0

    checks = [
        (t("verify.ray.nonneg"), all(v >= 0 for v in y),
         "min(y) = {}".format(exact.serialize(min(y)) if y else "-")),
        (t("verify.ray.columns"),
         all(sum(A[i][j] * y[i] for i in range(len(A))) >= 0
             for j in range(cols)), "A^T y >= 0"),
    ]
    dot = sum(bi * yi for bi, yi in zip(b, y))
    checks.append((t("verify.ray.negative"), dot < 0,
                   "b.y = {}".format(exact.serialize(dot))))
    return VerifyReport(
        all(c[1] for c in checks), "farkas_ray", True, checks=checks,
        detail=t("verify.ray.detail", n=len(y)),
    )


def _verify_branch_bound(cert, limits) -> VerifyReport:
    """Every leaf closed, and the tree covering everything it should."""
    from fractions import Fraction

    from . import exact

    p = cert.payload
    incumbent = exact.to_fraction(p["incumbent"])
    nodes = p["nodes"]
    checks, warnings = [], []

    by_key = {_node_id(n["fixed"]): n for n in nodes}
    checks.append((t("verify.bb.unique"), len(by_key) == len(nodes),
                   t("verify.bb.duplicates", n=len(nodes) - len(by_key))))

    # The incumbent is a design that exists and attains the claimed value.
    sub = p.get("incumbent_cert")
    if sub is None:
        checks.append((t("verify.bb.incumbent"), False,
                       t("verify.bisect.no_cert")))
    else:
        rep = verify(Certificate.from_dict(sub), limits)
        reached = exact.to_fraction(
            (sub.get("payload") or {}).get("achieved") or p["incumbent"])
        checks.append((t("verify.bb.incumbent"), rep.ok and reached == incumbent,
                       t("verify.lp.declared", value=p["incumbent"])))

    # Every node is closed, or branches and its children are all present.
    bad_close, missing, open_nodes = [], [], []
    for n in nodes:
        why = n["why"]
        if why == "branch":
            for val in n["values"]:
                child = list(n["fixed"]) + [[n["on"], val]]
                if _node_id(child) not in by_key:
                    missing.append("{}={}".format(n["on"], val))
            continue
        if why == "infeasible":
            if n.get("cert") is None:
                open_nodes.append(_node_id(n["fixed"]) or "root")
                continue
            r = verify(Certificate.from_dict(n["cert"]), limits)
            if not r.ok:
                bad_close.append(_node_id(n["fixed"]) or "root")
            continue
        # bound and leaf both close by an exact dual that must not exceed the
        # incumbent -- otherwise the subtree was pruned on a false promise.
        if n.get("cert") is None or n.get("bound") is None:
            open_nodes.append(_node_id(n["fixed"]) or "root")
            continue
        r = verify(Certificate.from_dict(n["cert"]), limits)
        if not r.ok or exact.to_fraction(n["bound"]) > incumbent:
            bad_close.append(_node_id(n["fixed"]) or "root")

    checks.append((t("verify.bb.covered"), not missing,
                   t("verify.bb.missing", names=", ".join(missing[:3]) or "-",
                     n=len(missing))))
    checks.append((t("verify.bb.closed"), not bad_close and not open_nodes,
                   t("verify.bb.open", names=", ".join(
                       (bad_close + open_nodes)[:3]) or "-",
                     n=len(bad_close) + len(open_nodes))))

    kinds = {}
    for n in nodes:
        kinds[n["why"]] = kinds.get(n["why"], 0) + 1
    return VerifyReport(
        all(c[1] for c in checks), "branch_bound", False, checks=checks,
        warnings=warnings,
        detail=t("verify.bb.detail", value=p["incumbent"], n=len(nodes),
                 bound=kinds.get("bound", 0), inf=kinds.get("infeasible", 0),
                 leaf=kinds.get("leaf", 0)),
    )


def _node_id(fixed) -> str:
    return ",".join("{}={}".format(v, x) for v, x in fixed)



def _verify_asymptotic(cert, limits) -> VerifyReport:
    """Substitute, collect, read off the exponent. No solver, no spec."""
    from fractions import Fraction

    from . import asymptotics

    p = cert.payload
    orders = {k: Fraction(v) for k, v in p["orders"].items()}
    poly = asymptotics.Laurent({
        tuple((s, int(e)) for s, e in row["monomial"]): Fraction(row["coefficient"])
        for row in p["laurent"]})

    checks, warnings = [], []
    try:
        got = asymptotics.order(poly, orders, p["var"])
    except asymptotics.NotAsymptotic as e:
        return VerifyReport(False, "asymptotic", True,
                            detail=str(e))

    checks.append((t("verify.order.degree"), got["degree"] == p["degree"],
                   t("verify.order.recomputed", degree=got["degree"] or "-",
                     declared=p["degree"] or "-")))
    checks.append((t("verify.order.verdict"), got["verdict"] == p["verdict"],
                   t("order." + got["verdict"])))
    checks.append((t("verify.order.cancelled"),
                   got["cancelled"] == p.get("cancelled", 0),
                   t("verify.order.cancelled_n", n=got["cancelled"])))

    if p.get("expect") is not None and p["expect"] != p["verdict"]:
        warnings.append(t("verify.order.disagrees",
                          want=t("order." + p["expect"]),
                          got=t("order." + p["verdict"])))
    # Said every time, because it is the one thing a reader will forget.
    warnings.append(t("verify.order.constants", var=p["var"]))

    return VerifyReport(
        all(c[1] for c in checks), "asymptotic", True, checks=checks,
        warnings=warnings,
        detail=t("verify.order.detail", degree=p["degree"] or "-",
                 var=p["var"], verdict=t("order." + p["verdict"])),
    )


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
        warnings=([t("verify.core.vacuous_named",
                     names=", ".join(cert.payload.get("clash") or []))]
                  if cert.payload.get("clash")
                  else [t("verify.core.vacuous")]
                  if cert.payload.get("vacuous") else []),
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
         t("verify.lp.declared", value=p["objective"])),
    ]

    warnings = []
    if p.get("integer"):
        # The dual is a bound on the integer optimum, never the optimum
        # itself. Whether the two coincide is a separate, checkable fact.
        pt = p.get("integral_point")
        if pt is None:
            warnings.append(t("verify.lp.ilp_bound"))
        else:
            xi = exact.parse_all(pt)
            feasible = all(v >= 0 for v in xi) and all(
                sum(a * v for a, v in zip(row, xi)) <= rhs
                for row, rhs in zip(A, b))
            value = sum(ci * v for ci, v in zip(c, xi))

            # The point is called integral, so check that it IS. Feasibility
            # and the objective say nothing about it: `x = 3/2` satisfies
            # `x <= 3` and hits its declared value perfectly well, and used to
            # pass. Per-variable, against the DECLARED kind, because a mixed
            # problem's continuous weights are fractional on purpose.
            kinds = p.get("kinds") or {}
            names = p.get("var_names") or []
            off, binary_off = [], []
            for j, v in enumerate(xi):
                name = names[j] if j < len(names) else str(j)
                kind = kinds.get(name, "integer" if p.get("integer")
                                 else "continuous")
                if kind == "continuous":
                    continue
                if v.denominator != 1:
                    off.append(name)
                elif kind == "binary" and v not in (0, 1):
                    binary_off.append(name)
            checks.append((t("verify.lp.integral_integral"),
                           not off and not binary_off,
                           t("verify.lp.offenders",
                             names=", ".join((off + binary_off)[:3]) or "-")))
            checks.append((t("verify.lp.integral_feasible"), feasible,
                           t("verify.lp.declared",
                             value=exact.serialize(value))))
            checks.append((t("verify.lp.integral_declared"),
                           exact.to_fraction(p["integral_objective"]) == value,
                           p["integral_objective"]))
            if value != rep["objective"]:
                warnings.append(t("verify.lp.ilp_gap",
                                  value=exact.serialize(value),
                                  bound=exact.serialize(rep["objective"])))

    # A target turns "here is the optimum" into "here is a bound that meets
    # what you needed", which for an existence proof is the whole question.
    if p.get("target") is not None:
        want = exact.to_fraction(p["target"])
        value = exact.to_fraction(p.get("integral_objective")
                                  or p["objective"])
        if value >= want:
            checks.append((t("verify.lp.target"), True,
                           t("verify.lp.margin", value=exact.serialize(value),
                             target=p["target"],
                             margin=exact.serialize(value - want))))
        else:
            warnings.append(t("verify.lp.short", value=exact.serialize(value),
                              target=p["target"],
                              deficit=exact.serialize(want - value)))

    detail = (t("verify.lp.exact.detail", value=exact.serialize(rep["objective"]))
              if not p.get("integer")
              else t("verify.lp.ilp.detail",
                     value=p.get("integral_objective") or "-",
                     bound=exact.serialize(rep["objective"])))
    return VerifyReport(
        all(k[1] for k in checks), "lp_dual", True, checks=checks,
        warnings=warnings, detail=detail,
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

    src = Path(p["spec_path"] or "")
    if not p["spec_path"] or not src.is_file():
        return VerifyReport(False, "shrink_graph", True,
                            detail=t("verify.shrink.spec_missing",
                                     path=p["spec_path"] or "-"))
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

    # `Path("")` is `.`, which exists and is a directory: without the first
    # test this reads a folder and dies with a permission error instead of
    # saying the certificate never recorded where its spec was.
    src = Path(p["spec_path"] or "")
    if not p["spec_path"] or not src.is_file():
        return VerifyReport(False, "shrink_domain", True,
                            detail=t("verify.shrink.spec_missing",
                                     path=p["spec_path"] or "-"))
    got = hashlib.sha256(src.read_bytes()).hexdigest()
    checks.append((t("verify.shrink.spec_same"), got == p["spec_sha256"],
                   got[:16]))

    spec = load_spec(src)
    # Resolve a named reducer the same way the engine did, or the replay
    # would walk a different descent than the one recorded.
    reduce = spec.reducer()
    if reduce is None:
        return VerifyReport(False, "shrink_domain", True, checks=checks,
                            detail=t("engine.shrink.no_reduce"))
    by_id = {spec.id_of(i): i for i in spec.enumerate()}
    start = by_id.get(p["original"])
    if start is None:
        checks.append((t("verify.shrink.replay"), False,
                       t("verify.shrink.item_missing", id=p["original"])))
        return VerifyReport(False, "shrink_domain", True, checks=checks)

    # Replay the recorded descent rather than redoing the search.
    item = start
    for step in p["trace"]:
        options = list(reduce(item))
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
        survivors = [spec.id_of(c) for c in reduce(item) if is_ce(c)]
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
    if p.get("orbits"):
        from . import orbits as orb

        checks += orb.check(p)

    pchecks, pwarn, level = _predicate_level(cert, limits, "domain")
    if p.get("by_orbit"):
        pchecks, pwarn = _by_orbit_checks(p, pchecks, pwarn)
    checks += pchecks
    free = cert.solver_free and level is not REPRODUCIBLE

    return VerifyReport(
        all(c[1] for c in checks), "domain_sweep", free, checks=checks,
        method_key=_method(level), warnings=_sweep_warnings(p) + pwarn,
        detail=t("verify.sweep.level." + level) + " -- "
        + t("verify.domain.detail", n=p["count"]),
    )


def _verify_entries_and_stats(p, limits) -> list:
    """The stored certificates and the calibration. Shared by both sweep kinds.

    Note what is NOT here: any claim about evaluations that stored no
    certificate. That belongs to `_predicate_level`, because it is a warning
    and not a check -- there is nothing to tick.
    """
    checks = []
    entries = p.get("entries", [])
    with_cert = [e for e in entries if e.get("cert")]
    if with_cert:
        bad = [_entry_id(e) for e in with_cert
               if not verify(Certificate.from_dict(e["cert"]), limits).ok]
        checks.append(
            (t("verify.sweep.predicate"), not bad,
             t("verify.sweep.entries", certified=len(with_cert),
               total=p.get("evaluations", len(entries)),
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


def _entry_id(e) -> str:
    """The item's id.

    `id` is the field. `g6` is what it used to be called, back when the only
    domain was graphs -- which is how a DomainSpec ended up labelling triples
    of sets as "graph6". Certificates issued before the rename are still read.
    """
    return e.get("id") or e.get("g6") or "?"


def _predicate_level(cert, limits, kind):
    """What this sweep establishes about the predicate, said out loud.

    Returns (checks, warnings, level). The warning fires on a PASSING sweep
    exactly as it does on a refuted one -- that symmetry is the point. A pass
    over eleven thousand uncertified booleans is the case where a green banner
    does the most damage, because there is no counterexample to go and look at.
    """
    p = cert.payload
    checks, warnings = [], []

    if p.get("no_predicate"):
        # A calibration run measures; it refutes nothing, so there is no
        # predicate to certify and saying "fully certified" would be as wrong
        # as saying "uncertified". The stats are checked exactly, elsewhere.
        return checks, warnings, NO_PREDICATE

    ok, detail = _replay(cert, limits, kind)
    if ok is None:
        warnings.append(t("verify.sweep.replay.skipped", reason=detail))
    else:
        checks.append((t("verify.sweep.replay"), ok, detail))

    level = sweep_strength(p, ok is True)
    evaluations = p.get("evaluations", 0)
    uncertified = max(0, evaluations - p.get("certified", 0))
    # When the replay DISAGREED, the failed check is the headline. Adding
    # "only the domain was checked" underneath would read as a lesser problem
    # than "this certificate no longer describes what the spec does".
    if uncertified and ok is not False:
        warnings.append(t("verify.sweep.uncertified." + level,
                          n=uncertified, total=evaluations))
    return checks, warnings, level


def _by_orbit_checks(p, checks, warnings):
    """What a --by-orbit run has to say, the same for both sweep kinds.

    The degenerate case is not a failure. When every orbit is a singleton --
    which is exactly what happens on a graph sweep quotiented by isomorphism,
    since the enumerator already did that -- nothing was inferred, there are
    no non-representatives to look at, and the invariance assumption was never
    used. That run IS a full sweep and says so.
    """
    spot = p.get("spot_checks") or []
    inferred = max(0, p.get("evaluations", 0) - p.get("evaluated", 0))
    if not inferred:
        warnings.insert(0, t("verify.orbits.nothing_inferred"))
        return checks, warnings

    checks.append((t("verify.orbits.spot"),
                   bool(spot) and all(s_.get("agreed") for s_ in spot),
                   t("verify.orbits.spot_n", n=len(spot))))
    warnings.insert(0, t("verify.orbits.assumed",
                         evaluated=p.get("evaluated", "?"), n=len(spot)))
    return checks, warnings


def _method(level) -> str:
    return "cli.verify.by_replay" if level == REPRODUCIBLE else ""


def _sweep_warnings(p) -> list:
    """Only what `_predicate_level` does not already say, and better.

    The old "N of M stored entries lack a certificate" warning is gone: it
    counted the stored counterexamples, so it was silent on a passing sweep
    and, on a refuted one, it said less than the level warning that replaced
    it. Two warnings about the same gap make readers skim both.
    """
    out = []
    c = p.get("counts", {})
    if c.get("errors") or c.get("inconclusive"):
        out.append(t("verify.sweep.unevaluated",
                     n=c.get("errors", 0) + c.get("inconclusive", 0)))
    return out


def _verify_sweep(cert, limits) -> VerifyReport:
    p = cert.payload
    checks = _verify_family(p["family_graph6"], p["n"], p["filters"],
                            p["family_sha256"])
    checks += _verify_entries_and_stats(p, limits)
    if p.get("orbits"):
        from . import orbits as orb

        checks += orb.check(p)

    pchecks, pwarn, level = _predicate_level(cert, limits, "sweep")
    if p.get("by_orbit"):
        pchecks, pwarn = _by_orbit_checks(p, pchecks, pwarn)
    checks += pchecks

    # Replaying means running the spec's predicate, which is arbitrary Python
    # and may well call a solver. Claiming "verified without a solver" after
    # that would be the same overclaim in a different place.
    free = cert.solver_free and level is not REPRODUCIBLE

    return VerifyReport(
        all(k[1] for k in checks), "sweep", free, checks=checks,
        method_key=_method(level), warnings=_sweep_warnings(p) + pwarn,
        detail=t("verify.sweep.level." + level) + " -- "
        + t("verify.sweep.detail", n=p["family_count"]),
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
