"""Does each hypothesis earn its place? Drop it and go looking.

`core` answers the other half. It says WHICH hypotheses an unsat core needed
and drops the rest, which catches a theorem stated with slack. It cannot
catch the opposite mistake, and the opposite mistake is the expensive one:

    a theorem stated TOO STRONGLY, formalised, and only then found to have
    been about a smaller class than anybody wanted

So this drops each hypothesis in turn and hunts a counterexample to what
remains. Three answers per hypothesis, and they are genuinely different:

  NEEDED, with a witness. Without it the claim is false, and here is the
  assignment that breaks it. That witness is the useful artefact: it says not
  only that the hypothesis matters but HOW, which is what tells you whether
  you wrote the right one.

  REDUNDANT. The claim still follows without it, so the theorem is weaker than
  it looks and can be stated without it. `core` finds these too; they appear
  here because a per-hypothesis report that silently omitted them would read
  as "all needed".

  UNKNOWN. The solver did not settle it inside the budget. Never folded into
  either of the other two -- "we did not find a counterexample" is not
  "there is none", and that distinction is the whole discipline here.

WHAT THIS IS FOR is the step before formalisation. Formalising a theorem whose
hypotheses were never tested is how a month goes into proving something that
is true of a smaller class than the paper claims, and the test is cheap: one
satisfiability query per hypothesis.

WHAT IT IS NOT is a proof that the hypothesis set is minimal. Dropping them ONE
at a time says nothing about dropping two -- a pair can be jointly redundant
with neither redundant alone. Said in the certificate, every time.
"""
from __future__ import annotations

from .i18n import t as _t


class NotAuditable(ValueError):
    """Raised with the reason, because a bare failure helps nobody."""


NEEDED, REDUNDANT, UNKNOWN = "needed", "redundant", "unknown"


def audit(spec, limits=None) -> dict:
    """One satisfiability query per hypothesis: what breaks without it."""
    import z3

    from .limits import Limits
    from .status import Status

    if spec.goal is None:
        raise NotAuditable(_t("audit.no_goal"))
    if not spec.assumptions:
        raise NotAuditable(_t("audit.no_hypotheses"))

    lim = limits or Limits()
    rows = []
    for dropped, _formula in spec.assumptions:
        keep = [(n, f) for n, f in spec.assumptions if n != dropped]
        s = z3.Solver()
        lim.apply_to(s)
        for _n, f in keep:
            s.add(f)
        # A counterexample to the claim, under everything EXCEPT this one.
        s.add(z3.Not(spec.goal))
        got = s.check()

        if got == z3.sat:
            model = s.model()
            assignment = {str(d): [d.range().name() if d.arity() == 0 else "?",
                                   str(model[d])]
                          for d in model.decls()}
            rows.append({"hypothesis": dropped, "verdict": NEEDED,
                         "witness": assignment})
        elif got == z3.unsat:
            rows.append({"hypothesis": dropped, "verdict": REDUNDANT,
                         "witness": None})
        else:
            rows.append({"hypothesis": dropped, "verdict": UNKNOWN,
                         "witness": None,
                         "why": str(s.reason_unknown() or "")})
        _ = Status

    counts = {v: sum(1 for r in rows if r["verdict"] == v)
              for v in (NEEDED, REDUNDANT, UNKNOWN)}
    return {"rows": rows, "counts": counts,
            "ok": counts[UNKNOWN] == 0,
            "redundant": [r["hypothesis"] for r in rows
                          if r["verdict"] == REDUNDANT]}


def recheck(payload, limits=None) -> dict:
    """Re-run every witness against the formulas it claims to break.

    The witness is the whole content of a NEEDED verdict, and checking one is
    evaluation rather than search: substitute the assignment, and the kept
    hypotheses must hold while the goal must not. A verdict with a witness
    that does not do that is a verdict about nothing.
    """
    import z3

    from .limits import Limits

    lim = limits or Limits()
    formulas = {}
    for name, smt2 in (payload.get("hypotheses_smt2") or {}).items():
        formulas[name] = z3.And(*z3.parse_smt2_string(smt2))
    goal = z3.And(*z3.parse_smt2_string(payload["goal_smt2"]))

    bad, checked = [], 0
    for row in payload["rows"]:
        if row["verdict"] != NEEDED or not row.get("witness"):
            continue
        checked += 1
        subs = []
        for name, (sort, value) in row["witness"].items():
            try:
                var = {"Real": z3.Real, "Int": z3.Int,
                       "Bool": z3.Bool}[sort](name)
                lit = {"Real": z3.RealVal, "Int": z3.IntVal,
                       "Bool": lambda v: z3.BoolVal(v == "True")}[sort](value)
            except (KeyError, ValueError):
                bad.append(row["hypothesis"])
                break
            subs.append((var, lit))
        else:
            kept = [f for n, f in formulas.items()
                    if n != row["hypothesis"]]
            claim = z3.And(*kept) if kept else z3.BoolVal(True)
            s = z3.Solver()
            lim.apply_to(s)
            # The witness must satisfy what was KEPT and break the goal.
            s.add(z3.Not(z3.And(z3.substitute(claim, *subs),
                                z3.Not(z3.substitute(goal, *subs)))))
            if s.check() != z3.unsat:
                bad.append(row["hypothesis"])
    return {"checked": checked, "bad": sorted(set(bad))}
