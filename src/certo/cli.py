"""Command-line interface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .certificate import Certificate
from .certificate import verify as verify_cert
from .i18n import available, set_lang, t
from .limits import Limits
from .status import Result, Status, Verdict

# Some consoles (Windows in particular) default to a legacy codepage that
# mangles accented output. Translations should not depend on that.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

# The scope of a result matters as much as the result. A bare "PROVED"
# invites reading a bounded synthesis as a theorem, so commands whose scope
# is narrower than the word suggests get their own banner.
SCOPED = {
    ("synth", Verdict.PROVED), ("synth", Verdict.UNSATISFIABLE),
    ("prove", Verdict.PROVED), ("core", Verdict.PROVED),
    ("sweep", Verdict.PROVED), ("cases", Verdict.PROVED),
    ("bisect", Verdict.PROVED),
}
SCOPE_NOTE = {("synth", Verdict.PROVED), ("sweep", Verdict.PROVED)}


def banner(res: Result) -> str:
    if (res.command, res.verdict) in SCOPED:
        return t("scope.{}.{}".format(res.command, res.verdict.value))
    return t("verdict." + res.verdict.value)


def scope_note(res: Result):
    if (res.command, res.verdict) in SCOPE_NOTE:
        return t("note.{}.{}".format(res.command, res.verdict.value))
    return None


# ---------------------------------------------------------------------------
# salida
# ---------------------------------------------------------------------------


_HIDDEN_META = ("trace", "errors", "describe", "counterexamples", "solution",
                "errors_detail", "inconclusive_detail", "implementation",
                "domain", "evaluations", "calibration", "table", "multipliers",
                "hint", "lemmas", "used", "unused", "bridges", "lo", "hi",
                "width", "ladder", "lo_float", "hi_float", "vacuous")


def print_calibration(cal, worst_k=3):
    """Refuting says it is false; calibrating says how much, and where."""
    if not cal:
        return
    print("  " + t("cli.calibration", count=cal["count"], min=cal["min"],
                   max=cal["max"], mean=cal["mean"]))
    worst = cal["worst"][:worst_k]
    if worst:
        label = t("cli.label.lowest" if cal["worst_sense"] == "min"
                  else "cli.label.highest")
        print("  " + t("cli.calibration.worst", k=worst_k, label=label,
                       items=" | ".join("{} {}".format(v["g6"], v["value"])
                                        for v in worst)))


def emit(res: Result, args) -> int:
    # Provenance: tie the certificate to the spec and version that made it.
    if res.certificate is not None:
        res.certificate.stamp(getattr(args, "spec", None))

    if getattr(args, "json", False):
        print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("{}  [{}]".format(banner(res), res.status.value))
        if res.detail:
            print("  " + res.detail)

        impl = res.meta.get("implementation")
        if impl:
            print("  " + t("cli.synthesised_object"))
            for k, v in impl.items():
                print("    {} = {}".format(k, v))
        if res.meta.get("domain"):
            print("  " + t("cli.domain", domain=res.meta["domain"]))

        for k, v in sorted(res.meta.items()):
            if k in _HIDDEN_META:
                continue
            print("  {}: {}".format(k, v))

        if res.meta.get("vacuous"):
            print("  !! " + t("cli.vacuous"))

        note = scope_note(res)
        if getattr(args, "prove_candidate", False):
            note = None   # the universal step follows immediately
        if note:
            print("  " + note)

        if res.certificate is not None:
            c = res.certificate
            tag = t("cli.cert.solver_free" if c.solver_free
                    else "cli.cert.needs_solver")
            print("  " + t("cli.certificate", kind=c.kind, tag=tag,
                           digest=c.digest()))
        else:
            print("  " + t("cli.certificate.none"))
        print("  " + t("cli.engine", engine=res.engine, ms=res.elapsed_ms))

    out = getattr(args, "cert", None)
    if out and res.certificate is not None:
        Path(out).write_text(
            json.dumps(res.certificate.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if not getattr(args, "json", False):
            print("  " + t("cli.cert.written", path=out))

    log = getattr(args, "log", None)
    if log:
        from . import ledger

        path = log if isinstance(log, str) and log != "-" else ledger.default_path()
        ledger.append(path, res, cert_path=out, spec_path=getattr(args, "spec", None),
                      note=getattr(args, "note", "") or "",
                      tags=getattr(args, "tag", None))
        if not getattr(args, "json", False):
            print("  " + t("cli.ledger.logged", path=path))

    return 0 if res.status.conclusive else 2


def limits_from(args) -> Limits:
    return Limits(
        timeout_ms=args.timeout_ms,
        rlimit=args.rlimit,
        max_memory_mb=args.max_memory_mb,
        seed=args.seed,
        max_iterations=getattr(args, "max_iterations", 10_000),
        conflict_budget=getattr(args, "conflict_budget", 1_000_000),
    )


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------


def cmd_prove(args):
    from .engines import smt
    from .spec import Spec, load_spec

    return emit(smt.prove(load_spec(args.spec, Spec), limits_from(args)), args)


def cmd_check(args):
    from .engines import smt
    from .spec import Spec, load_spec

    return emit(smt.check(load_spec(args.spec, Spec), limits_from(args)), args)


def cmd_core(args):
    from .engines import smt
    from .spec import MultiSpec, Spec, load_spec

    spec = load_spec(args.spec)
    if isinstance(spec, MultiSpec):
        res = smt.core_matrix(spec, limits_from(args))
        rc = emit(res, args)
        if not args.json:
            _print_matrix(res.meta.get("table"), spec.goal_names,
                          res.meta.get("never_used", []))
        return rc
    if not isinstance(spec, Spec):
        print("core needs a Spec or a MultiSpec; spec() returned "
              + type(spec).__name__, file=sys.stderr)
        return 1
    return emit(smt.core(spec, limits_from(args)), args)


def _print_matrix(table, goals, never):
    """The hypothesis-by-goal table. The comparison IS the result."""
    if not table:
        return
    cells = {True: "yes", False: "no", None: "?"}
    width = max([len(t("cli.matrix.header"))] + [len(h) for h in table])
    print("  {:<{w}}  {}".format(t("cli.matrix.header"), "  ".join(
        "{:>8}".format(g[:8]) for g in goals), w=width))
    for h, row in table.items():
        print("  {:<{w}}  {}".format(h, "  ".join(
            "{:>8}".format(cells[row[g]]) for g in goals), w=width))
    print("  " + t("cli.matrix.legend"))
    if never:
        print("  " + t("cli.matrix.never", names=", ".join(never)))


def cmd_farkas(args):
    from .engines import farkas
    from .spec import Spec, load_spec

    spec = load_spec(args.spec, Spec)
    res = farkas.farkas(spec, limits_from(args), nonlinear=args.nonlinear,
                        spec_path=args.spec)
    rc = emit(res, args)
    if not args.json and res.meta.get("multipliers"):
        print("  " + t("cli.farkas.multipliers"))
        for name, lam in res.meta["multipliers"].items():
            print("    {:<22} {}".format(name, lam))
        print("  " + t("cli.farkas.hint", hint=res.meta.get("hint", "")))
    return rc


def cmd_compose(args):
    from pathlib import Path

    from .engines import compose
    from .spec import ProofSpec, load_spec

    spec = load_spec(args.spec, ProofSpec)
    res = compose.compose(spec, limits_from(args), spec_path=args.spec,
                          base_dir=Path.cwd())
    rc = emit(res, args)
    if not args.json and res.meta.get("lemmas"):
        _print_lemmas(res)
    return rc


def _print_lemmas(res):
    """Which lemmas are linked, which are asserted, which are not needed.

    The distinction is the whole point: a linked lemma is checked against its
    own certificate, a bridge is a claim about what that certificate means.
    """
    bridges = set(res.meta.get("bridges", []))
    used = set(res.meta.get("used", []))
    print("  " + t("cli.compose.lemmas"))
    for name in res.meta["lemmas"]:
        mark = t("cli.compose.bridge") if name in bridges             else t("cli.compose.derived")
        print("    {:<24} {:<10} {}".format(
            name, mark, "*" if name in used else ""))
    if res.meta.get("unused"):
        print("  " + t("cli.compose.unused",
                       names=", ".join(res.meta["unused"])))


def cmd_bounds(args):
    from .engines import bounds
    from .spec import BoundSpec, load_spec

    spec = load_spec(args.spec, BoundSpec)
    if args.prec:
        spec.prec = args.prec
    if args.max_prec:
        spec.max_prec = args.max_prec
    res = bounds.bounds(spec, limits_from(args), spec_path=args.spec)
    rc = emit(res, args)
    if not args.json and res.meta.get("lo"):
        print("  " + t("cli.bounds.enclosure", lo=res.meta["lo_float"],
                       hi=res.meta["hi_float"], width=res.meta["width"]))
        print("  " + t("cli.bounds.ladder",
                       ladder=", ".join(str(p) for p in res.meta["ladder"])))
    return rc


def cmd_synth(args):
    from .engines import cegis
    from .spec import SynthSpec, load_spec

    def on_round(r):
        print("  " + t("cli.round", round=r["round"],
                        impl={k: v[1] for k, v in r["implementation"].items()},
                        ce={k: v[1] for k, v in r["counterexample"].items()}),
              file=sys.stderr)

    spec = load_spec(args.spec, SynthSpec)
    lim = limits_from(args)
    res = cegis.synth(spec, lim, on_round if args.trace else None)
    if not args.prove_candidate or res.verdict is not Verdict.PROVED:
        return emit(res, args)

    # Paso 2: fijar el candidato y demostrar el enunciado GENERAL.
    from .certificate import synth_proved_certificate

    synth_cert = res.certificate
    rc = emit(res, args)
    print()
    try:
        uni = cegis.prove_candidate(spec, synth_cert.payload["implementation"], lim)
    except ValueError as e:
        print(t("cli.universal.unavailable"))
        print("  " + str(e))
        return rc

    if uni.verdict is Verdict.PROVED:
        print(t("cli.universal.pass", status=uni.status.value))
    elif uni.verdict is Verdict.REFUTED:
        print(t("cli.universal.fail", status=uni.status.value))
        print("  " + t("cli.universal.fail.detail"))
    else:
        print(t("cli.universal.unknown", status=uni.status.value))
    print("  " + uni.detail)

    combo = synth_proved_certificate(
        candidate=res.meta.get("implementation"),
        synth_cert=synth_cert.to_dict(),
        universal_cert=uni.certificate.to_dict() if uni.certificate else None,
    ).stamp(args.spec)
    if args.cert:
        Path(args.cert).write_text(
            json.dumps(combo.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8")
        print("  " + t("cli.combined.written", path=args.cert))
    return rc if uni.verdict is Verdict.PROVED else 2


def _is_zero(v) -> bool:
    from fractions import Fraction

    try:
        return Fraction(str(v)) == 0
    except (ValueError, ZeroDivisionError):
        try:
            return abs(float(v)) < 1e-9
        except (TypeError, ValueError):
            return False


def cmd_opt(args):
    from .engines import lp
    from .packing import PackingSpec
    from .spec import LPSpec, load_spec

    spec = load_spec(args.spec)
    if isinstance(spec, PackingSpec):
        if args.by_type and spec.kinds:
            return _opt_by_type(args, spec)
        spec = spec.to_lp()
    elif not isinstance(spec, LPSpec):
        print("opt needs an LPSpec or a PackingSpec; spec() returned "
              + type(spec).__name__, file=sys.stderr)
        return 1

    res = lp.opt(spec, limits_from(args), use_exact=not args.no_exact)
    rc = emit(res, args)
    if not args.json:
        sol = res.meta.get("solution") or {}
        nz = [(k, v) for k, v in sol.items() if not _is_zero(v)]
        print("  " + t("cli.solution", total=len(sol), nonzero=len(nz)))
        for name, val in nz[:args.top]:
            print("    {} = {}".format(name, val))
        if len(nz) > args.top:
            print("    " + t("cli.solution.more", n=len(nz) - args.top))
    return rc


def _opt_by_type(args, packing):
    """The mixed optimum and each type alone.

    Whether mixing buys anything is exactly the gap between the mixed optimum
    and the best single type, and that comparison is the usual question.
    """
    from .engines import lp

    rows = [("mixed", lp.opt(packing.to_lp(), limits_from(args),
                             use_exact=not args.no_exact))]
    for kind in packing.kinds:
        rows.append((kind, lp.opt(packing.restricted({kind}).to_lp(),
                                  limits_from(args),
                                  use_exact=not args.no_exact)))
    for label, r in rows:
        print("  {:<10} {:<14} {}".format(label, str(r.meta.get("objective")),
                                          r.detail[:56]))
    return emit(rows[0][1], args)


def cmd_enum(args):
    from .engines import graphsearch

    res = graphsearch.enum(args.n, args.filter, limits_from(args),
                           use_geng=not args.no_geng)
    if args.out and res.certificate is not None:
        Path(args.out).write_text(
            "\n".join(res.certificate.payload["graph6"]) + "\n", encoding="utf-8"
        )
        print(t("cli.graph6.written", path=args.out))
    return emit(res, args)


def cmd_sweep(args):
    from .engines import domain, graphsearch
    from .spec import DomainSpec, SweepSpec, load_spec

    mode = "all" if args.cert_all else ("none" if args.cert_none else "failures")
    spec = load_spec(args.spec)
    if args.n_range:
        return _sweep_range(args, spec, mode)
    if isinstance(spec, DomainSpec):
        res = domain.sweep_domain(spec, limits_from(args), cert_mode=mode)
    elif isinstance(spec, SweepSpec):
        res = graphsearch.sweep(spec, limits_from(args),
                                use_geng=not args.no_geng, cert_mode=mode)
    else:
        print("sweep needs a SweepSpec (graphs) or a DomainSpec (any finite "
              "domain); spec() returned " + type(spec).__name__, file=sys.stderr)
        return 1
    rc = emit(res, args)
    if args.json:
        return rc

    print_calibration(res.meta.get("calibration"), args.worst)

    if res.verdict is Verdict.REFUTED:
        print("  " + t("cli.counterexamples"))
        for s in res.meta.get("counterexamples", [])[:10]:
            print("    " + s)
        for d in res.meta.get("describe", []):
            print("    -> " + str(d))

    miss = res.meta.get("predicate_uncertified", 0)
    if miss:
        print("  " + t("cli.sweep.uncertified", n=miss))
    for label, key in ((t("cli.sweep.errors"), "errors_detail"),
                       (t("cli.sweep.inconclusive"), "inconclusive_detail")):
        for e in res.meta.get(key, [])[:3]:
            print("  {}: {} -> {}".format(label, e["g6"], e["detail"][:70]))
    return rc


def cmd_cases(args):
    from .cnf import CNF, CNFSpec
    from .engines import sat
    from .spec import load_spec

    p = Path(args.spec)
    if p.suffix.lower() in (".cnf", ".dimacs"):
        obj = CNF.from_dimacs(p.read_text(encoding="utf-8"))
    else:
        obj = load_spec(args.spec)
    spec = obj if isinstance(obj, CNFSpec) else CNFSpec(cnf=obj, title=obj.title)

    backend = args.solver
    if args.solver_binary:
        backend = "binary:" + args.solver_binary
    res = sat.cases(spec, limits_from(args), backend=backend,
                    check_proof=not args.no_check)

    if args.proof and res.certificate is not None and res.certificate.kind == "drat":
        Path(args.proof).write_text(
            "\n".join(res.certificate.payload["proof"]) + "\n", encoding="utf-8")
        print(t("cli.proof.written", path=args.proof))

    rc = emit(res, args)
    if not args.json:
        pc = res.meta.get("proof_check", {})
        for checker, rep in pc.items():
            print("  " + t("cli.checker", name=checker,
                            verdict="OK" if rep.get("ok") else "FAIL",
                            detail=rep.get("detail", "")))
        w = res.meta.get("witness")
        if w:
            true_ = [k for k, v in sorted(w.items()) if v]
            print("  " + t("cli.witness", n=len(true_),
                            names=", ".join(true_[:20])
                            + (" ..." if len(true_) > 20 else "")))
    return rc


def cmd_shrink(args):
    from .cnf import CNF, CNFSpec
    from .engines import domain, graphsearch, shrink
    from .graphs import Graph
    from .spec import DomainSpec, SweepSpec, load_spec

    obj = load_spec(args.spec)

    if isinstance(obj, (CNF, CNFSpec)):
        spec = obj if isinstance(obj, CNFSpec) else CNFSpec(cnf=obj, title=obj.title)
        return emit(shrink.shrink_cnf(spec, limits_from(args)), args)

    if isinstance(obj, DomainSpec):
        items = {obj.id_of(i): i for i in obj.enumerate()}
        if args.item:
            start = items.get(args.item)
            if start is None:
                print("no item with id " + args.item, file=sys.stderr)
                return 1
        else:
            sw = domain.sweep_domain(obj, limits_from(args))
            ces = sw.meta.get("counterexamples", [])
            if not ces:
                print(t("cli.no_counterexample", n=sw.meta.get("examined")),
                      file=sys.stderr)
                return 2
            start = items[ces[0]]
            if not args.json:
                print(t("cli.starting_from", g6=ces[0]))
        return emit(shrink.shrink_domain(obj, start, limits_from(args),
                                         spec_path=args.spec,
                                         use_objective=args.objective), args)

    if not isinstance(obj, SweepSpec):
        print("shrink needs a SweepSpec (graphs), a DomainSpec (any finite "
              "domain) or a CNFSpec (MUS); spec() returned "
              + type(obj).__name__, file=sys.stderr)
        return 1

    if args.from_cert:
        start = Graph.from_graph6(
            _worst_from_cert(args.from_cert, getattr(obj, "worst", "min")))
    elif args.graph:
        start = Graph.from_graph6(args.graph)
    else:
        sw = graphsearch.sweep(obj, limits_from(args), use_geng=not args.no_geng)
        ces = sw.meta.get("counterexamples", [])
        if not ces:
            print(t("cli.no_counterexample", n=sw.meta.get("examined")),
                  file=sys.stderr)
            return 2
        start = Graph.from_graph6(ces[0])
        if not args.json:
            print(t("cli.starting_from", g6=start.to_graph6()))

    res = shrink.shrink_graph(obj, start, limits_from(args), spec_path=args.spec,
                              keep_filters=not args.no_keep_filters,
                              use_objective=args.objective)
    rc = emit(res, args)
    if not args.json and res.meta.get("trace"):
        print("  " + t("cli.reductions"))
        for st in res.meta["trace"][:12]:
            print("    {:>2}. {:<16} {} -> {}".format(
                st["step"], st["op"], st["from"], st["to"]))
        if len(res.meta["trace"]) > 12:
            print("    " + t("cli.reductions.more",
                              n=len(res.meta["trace"]) - 12))
    return rc


def cmd_bisect(args):
    from .engines import bisect
    from .spec import BisectSpec, load_spec

    def on_probe(e):
        print("  " + t("cli.probe", t=e["t"], status=e["status"]),
              file=sys.stderr)

    spec = load_spec(args.spec, BisectSpec)
    res = bisect.bisect(spec, limits_from(args), on_probe if args.trace else None)
    return emit(res, args)


def _sweep_range(args, spec, mode):
    from .engines import graphsearch
    from .spec import SweepSpec

    if not isinstance(spec, SweepSpec):
        print("--n-range only applies to a SweepSpec", file=sys.stderr)
        return 1
    try:
        lo, hi = (int(x) for x in args.n_range.split(".."))
    except ValueError:
        print(t("cli.range.bad"), file=sys.stderr)
        return 1

    def on_size(row):
        if not args.json:
            print(t("cli.range.row", n=row["n"], verdict=row["verdict"],
                    detail=row["detail"][:70]))

    res = graphsearch.sweep_range(spec, lo, hi, limits_from(args),
                                  stop_on_first=args.stop_on_first,
                                  cert_mode=mode,
                                  use_geng=not args.no_geng, on_size=on_size)
    return emit(res, args)


def _worst_from_cert(path, obj_sense="min") -> str:
    """Start from the WORST counterexample of a sweep, not the first one.

    Re-running the sweep to find a starting point doubles the cost when the
    predicate is expensive, and the first counterexample is rarely the
    interesting one. If the sweep collected a value, the worst is picked by it.
    """
    from fractions import Fraction

    data = json.loads(_resolve_read(path))
    p = data.get("payload", {})
    # sweep and domain_sweep share the entry shape on purpose, so the same
    # "start from the worst one" works for graphs and for anything else.
    failures = [e["g6"] for e in p.get("entries", [])]
    if not failures:
        raise ValueError("that certificate carries no counterexample: " + str(path))
    values = {v["g6"]: Fraction(v["value"]) for v in p.get("values", [])
              if v["g6"] in failures}
    if not values:
        return failures[0]
    pick = (min if obj_sense == "min" else max)(values, key=values.get)
    return pick


def _resolve_read(path) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_ledger(args):
    from . import ledger

    path = args.file or ledger.default_path()

    if args.action == "list":
        rows = ledger.read(path)
        if not rows:
            print(t("cli.ledger.empty", path=path))
            return 2
        for e in rows[-args.limit:]:
            if e.get("_corrupt"):
                print("  ?? corrupt line {}".format(e["_line"]))
                continue
            c = e.get("certificate") or {}
            print("  {}  {:<8} {:<14} {:<12} {}".format(
                e["ts"][:19], e["command"], e["verdict"],
                c.get("kind", "-"), (e.get("note") or e["detail"])[:44]))
        print(t("cli.ledger.count", n=len(rows), path=path))
        return 0

    rep = ledger.verify_all(path, limits_from(args))
    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0 if rep["counts"]["failed"] == 0 else 1
    for r in rep["rows"]:
        mark = {"ok": "ok", "failed": "XX", "missing": "??",
                "changed": "!!", "no_cert": "--", "corrupt": "??"}[r["state"]]
        print("  [{}] {}  {:<8} {}".format(mark, r["ts"][:19],
                                           r.get("command", "-"),
                                           r["detail"][:60]))
    c = rep["counts"]
    print(t("cli.ledger.summary", total=rep["total"], **c))
    bad = c["failed"] + c["tampered"] + c["corrupt"]
    return 0 if bad == 0 else 1


def cmd_verify(args):
    data = json.loads(Path(args.certificate).read_text(encoding="utf-8"))
    rep = verify_cert(Certificate.from_dict(data), limits_from(args))
    if args.json:
        print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(t("cli.verify.header",
                state=t("cli.verify.valid" if rep.ok else "cli.verify.invalid"),
                kind=rep.kind,
                how=t("cli.verify.solver_free" if rep.solver_free
                      else "cli.verify.with_solver")))
        for name, ok, detail in rep.checks:
            print("  [{}] {}{}".format("ok" if ok else "XX", name,
                                       "  ({})".format(detail) if detail else ""))
        for w in rep.warnings:
            print("  " + t("cli.warning", text=w))
        if rep.detail:
            print("  " + rep.detail)
    return 0 if rep.ok else 1


def cmd_export(args):
    if args.lean:
        return _export_lean(args)

    from .cnf import CNF, CNFSpec
    from .spec import Spec, SynthSpec, load_spec
    from . import z3util
    import z3

    obj = load_spec(args.spec)
    if isinstance(obj, (CNF, CNFSpec)):
        print((obj.cnf if isinstance(obj, CNFSpec) else obj).to_dimacs(), end="")
    elif isinstance(obj, Spec):
        parts = list(obj.formulas)
        if obj.goal is not None:
            parts.append(z3.Not(obj.goal) if args.negate_goal else obj.goal)
        print(z3util.smt2(*parts))
    elif isinstance(obj, SynthSpec):
        impl, behav, corr = obj.normalized()
        print("; ---- impl_constraints ----")
        print(z3util.smt2(impl))
        print("; ---- behavior ----")
        print(z3util.smt2(behav))
        print("; ---- correctness ----")
        print(z3util.smt2(corr))
    else:
        print("export does not support " + type(obj).__name__, file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------


def _export_lean(args):
    """A counterexample as Lean data. Never compiled here, and it says so."""
    from . import lean
    from .graphs import Graph

    if args.graph:
        graphs, source = [Graph.from_graph6(args.graph)], "graph6 " + args.graph
    else:
        data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        graphs = lean.graphs_from_certificate(data)
        source = "{} (certificate {})".format(
            args.spec, Certificate.from_dict(data).digest())

    text = lean.graphs_to_lean(graphs, source)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(t("cli.lean.written", path=args.out, n=len(graphs)))
        print("  " + t("cli.lean.unverified"))
    else:
        print(text, end="")
    return 0


def build_parser():
    # Opciones comunes: van en un parent para que se escriban DESPUES del
    # subcomando, que es el orden natural (`certo synth spec.py --cert c.json`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("--lang", choices=available(),
                        help="output language (default: en, or $CERTO_LANG)")
    common.add_argument("--cert", metavar="FILE", help="write the certificate there")
    common.add_argument("--timeout-ms", type=int, default=10_000, dest="timeout_ms")
    common.add_argument("--rlimit", type=int, default=20_000_000,
                        help="DETERMINISTIC work limit for z3")
    common.add_argument("--max-memory-mb", type=int, default=2048,
                        dest="max_memory_mb")
    common.add_argument("--seed", type=int, default=0)
    common.add_argument("--log", nargs="?", const="-", metavar="FILE",
                        help="append this run to the audit ledger "
                             "(default: ./ledger.jsonl)")
    common.add_argument("--note", help="note to store with the ledger entry")
    common.add_argument("--tag", action="append", metavar="TAG",
                        help="repeatable tag for the ledger entry")

    p = argparse.ArgumentParser(
        prog="certo",
        description="Proof support: decide, enumerate, optimise and synthesise. "
                    "Everything with a certificate.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, helptext):
        return sub.add_parser(name, help=helptext, parents=[common])

    for name, fn, helptext in (
        ("prove", cmd_prove, "negate the claim and look for unsat -> unsat core"),
        ("check", cmd_check, "satisfiability -> model or core"),
        ("core", cmd_core, "MUS: which hypotheses are actually needed "
                           "(a MultiSpec gives the hypothesis-by-goal table)"),
    ):
        sp = add(name, helptext)
        sp.add_argument("spec", help=".py file with a spec() function")
        sp.set_defaults(func=fn)

    sp = add("opt", "LP/ILP -> dual certificate in EXACT rationals")
    sp.add_argument("spec", help=".py file with a spec() function")
    sp.add_argument("--no-exact", action="store_true", dest="no_exact",
                    help="skip rational reconstruction; leaves a floating-point "
                         "certificate (faster, NOT citable)")
    sp.add_argument("--top", type=int, default=10, metavar="K",
                    help="how many non-zero variables to show (default 10)")
    sp.add_argument("--by-type", action="store_true", dest="by_type",
                    help="with a PackingSpec: also report the optimum of each "
                         "item kind on its own, to see if mixing buys anything")
    sp.set_defaults(func=cmd_opt)

    sp = add("farkas", "linarith/nlinarith: non-negative multipliers that "
                       "close the system, in exact rationals")
    sp.add_argument("spec", help=".py file with a spec() function")
    sp.add_argument("--nonlinear", action="store_true",
                    help="add products and squares of the hypotheses first "
                         "(this is exactly what nlinarith does)")
    sp.set_defaults(func=cmd_farkas)

    sp = add("bounds", "settle a numeric inequality with rigorous interval "
                       "arithmetic: e, log, pi and friends, with a certificate")
    sp.add_argument("spec", help=".py file returning a BoundSpec")
    sp.add_argument("--prec", type=int, metavar="BITS",
                    help="starting precision (default: the spec's, 128)")
    sp.add_argument("--max-prec", type=int, metavar="BITS", dest="max_prec",
                    help="give up above this instead of doubling forever")
    sp.set_defaults(func=cmd_bounds)

    sp = add("compose", "assemble lemmas and their certificates into one "
                        "proof, with the link between them checked")
    sp.add_argument("spec", help=".py file returning a ProofSpec")
    sp.set_defaults(func=cmd_compose)

    sp = add("synth", "CEGIS: there exists an object, for every input...")
    sp.add_argument("spec")
    sp.add_argument("--trace", action="store_true", help="print every round")
    sp.add_argument("--prove-candidate", action="store_true",
                    dest="prove_candidate",
                    help="once found, fix the candidate and prove the "
                         "UNIVERSAL statement (the spec must carry "
                         "universal= or universal_behavior=)")
    sp.add_argument("--max-iterations", type=int, default=10_000, dest="max_iterations")
    sp.set_defaults(func=cmd_synth)

    sp = add("enum", "enumerate non-isomorphic graphs with filters")
    sp.add_argument("--n", type=int, required=True)
    sp.add_argument("--filter", action="append", default=[],
                    help="repeatable: chordal, connected, k4_free, min_degree=2, ...")
    sp.add_argument("--out", help="write the list in graph6")
    sp.add_argument("--no-geng", action="store_true", help="force the python engine")
    sp.set_defaults(func=cmd_enum)

    sp = add("sweep", "run a predicate and/or collect a value over a family")
    sp.add_argument("spec")
    sp.add_argument("--no-geng", action="store_true")
    sp.add_argument("--cert-all", action="store_true", dest="cert_all",
                    help="store the predicate certificate for EVERY graph, "
                         "not just the counterexamples (expensive)")
    sp.add_argument("--cert-none", action="store_true", dest="cert_none",
                    help="do not store predicate certificates")
    sp.add_argument("--n-range", metavar="LO..HI", dest="n_range",
                    help="sweep every size in the range and report the first "
                         "one that fails (overrides the spec's n)")
    sp.add_argument("--stop-on-first", action="store_true", dest="stop_on_first",
                    help="stop at the first size that fails")
    sp.add_argument("--worst", type=int, default=3, metavar="K",
                    help="how many extremes to list when the spec collects a "
                         "value (default 3)")
    sp.set_defaults(func=cmd_sweep)

    sp = add("cases", "SAT with a verified DRAT proof -> citable finite case")
    sp.add_argument("spec", help=".py file with spec(), or a .cnf/.dimacs")
    sp.add_argument("--solver", default="internal",
                    help="internal (default, always with a proof) | "
                         "pysat:cadical153 | binary:PATH")
    sp.add_argument("--solver-binary", metavar="RUTA", dest="solver_binary",
                    help="external cadical/kissat: `solver input.cnf proof.drat`")
    sp.add_argument("--conflict-budget", type=int, default=1_000_000,
                    dest="conflict_budget", help="DETERMINISTIC budget")
    sp.add_argument("--proof", metavar="FILE", help="write the DRAT proof there")
    sp.add_argument("--no-check", action="store_true",
                    help="do not verify the proof (not recommended)")
    sp.set_defaults(func=cmd_cases)

    sp = add("shrink", "minimise a counterexample: a graph, or the MUS of a CNF")
    sp.add_argument("spec", help="SweepSpec (graphs) or CNFSpec (MUS)")
    sp.add_argument("--graph", "--from", metavar="G6", dest="graph",
                    help="starting graph in graph6; if absent, sweep finds one")
    sp.add_argument("--from-cert", metavar="FILE", dest="from_cert",
                    help="start from the WORST counterexample of a stored sweep "
                         "certificate instead of re-running the sweep")
    sp.add_argument("--item", metavar="ID",
                    help="with a DomainSpec: start from this item id")
    sp.add_argument("--objective", action="store_true",
                    help="reduce lexicographically: stay a counterexample "
                         "first, improve the spec's `collect` value second")
    sp.add_argument("--no-keep-filters", action="store_true",
                    help="allow leaving the family while reducing")
    sp.add_argument("--no-geng", action="store_true")
    sp.set_defaults(func=cmd_shrink)

    sp = add("bisect", "certified bisection on a constant")
    sp.add_argument("spec", help=".py file returning a BisectSpec")
    sp.add_argument("--trace", action="store_true", help="print every probe")
    sp.set_defaults(func=cmd_bisect)

    sp = add("ledger", "audit log: what was run and whether it still checks out")
    sp.add_argument("action", choices=["list", "verify"])
    sp.add_argument("--file", metavar="FILE", help="ledger path (default ./ledger.jsonl)")
    sp.add_argument("--limit", type=int, default=20, help="rows to list (default 20)")
    sp.set_defaults(func=cmd_ledger)

    sp = add("verify", "re-verify a stored certificate")
    sp.add_argument("certificate", help="the certificate .json file")
    sp.set_defaults(func=cmd_verify)

    sp = add("export", "dump the spec to SMT-LIB2 or DIMACS, or a "
                       "counterexample to Lean")
    sp.add_argument("spec", help=".py spec, or a .json certificate with --lean")
    sp.add_argument("--lean", action="store_true",
                    help="emit a graph counterexample as Lean 4 data "
                         "(checked against Lean/Mathlib v4.28.0)")
    sp.add_argument("--graph", metavar="G6",
                    help="with --lean: export this graph6 instead of a certificate")
    sp.add_argument("--out", metavar="FILE", help="write to a file")
    sp.add_argument("--negate-goal", action="store_true",
                    help="export the refutation form (hypotheses + not claim)")
    sp.set_defaults(func=cmd_export)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "lang", None):
        set_lang(args.lang)
    try:
        return args.func(args)
    except Exception as e:  # noqa: BLE001
        print(t("cli.error", type=type(e).__name__, message=e),
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
