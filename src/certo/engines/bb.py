"""Branch and bound, with every leaf carrying its own certificate.

`mixed` certifies a construction and says plainly it does not claim the
skeleton is optimal. This claims it, and pays the price: to say "no design
does better" you have to account for EVERY design, and the only honest way to
do that is to exhibit the search tree and certify each leaf.

A leaf is closed for exactly one of three reasons, and each has a certificate
that checks by arithmetic:

  bound        its LP relaxation is worth no more than the incumbent, by an
               exact dual. Nothing in that subtree can beat what we have.
  infeasible   its LP has no solution at all, by a Farkas ray: y >= 0 with
               A^T y >= 0 and b.y < 0. Checking it is three dot products.
  leaf         every discrete variable is fixed, so the residual LP IS the
               answer for that design, by its exact dual.

And then the part that is easy to forget and fatal to omit: the tree must
COVER the integer domain. Branching fixes one variable to each of its values,
so the children of a node partition it -- and verification checks that, node
by node, rather than trusting that the search was exhaustive. A tree with a
missing child is a proof that some designs were never looked at.

The budget is real and the failure is honest: branch and bound is exponential,
and a run that will not finish reports `resource_exhausted` rather than
returning the incumbent as though it were the optimum.
"""
from __future__ import annotations

import time
from fractions import Fraction

from .. import exact
from ..certificate import branch_bound_certificate
from ..i18n import t
from ..limits import Limits
from ..status import Result, Status, Verdict
from ..tree import system_of

ENGINE = "certo/branch-and-bound"


def _values(spec, var):
    """Every integer a discrete variable may take. Finite, or there is no tree."""
    lo, hi = spec.bounds[var]
    lo = int(lo or 0)
    if hi is None:
        return None
    return list(range(lo, int(hi) + 1))


def _node_lp(spec, fixed):
    """The relaxation at a node. ONE definition, shared with `verify`.

    It lives in `tree` rather than here because the verifier derives every
    node's problem with it too. Two readings of "the node's LP" is exactly the
    gap a forged tree fits through, and the producer and the verifier
    disagreeing is the failure mode this project has already had once.
    """
    from ..tree import restrict

    return restrict(spec, fixed)


def _closed(key, why, bound, cert):
    """A node closed by an exact dual: the two vectors, not the whole thing.

    The dual and the primal are what close it. Everything else in an `lp_dual`
    certificate -- the matrix, the right-hand side, the objective, the names --
    is the node's LP, which is derived from the root system rather than stored,
    so carrying a copy would be carrying an UNCHECKED copy.
    """
    p = cert.payload
    return {"fixed": key, "why": why, "bound": exact.serialize(bound),
            "dual": list(p["dual"]), "primal": list(p["primal"] or [])}


def _negated(spec):
    """`min c.x` as `max -c.x`, with everything else untouched."""
    import copy

    from .. import exact

    out = copy.copy(spec)
    out.sense = "max"
    out.obj = {v: -exact.to_fraction(c) for v, c in spec.obj.items()}
    return out


def _partial(nodes, seen, incumbent, best_bound, minimising):
    """What a stopped search knows. Not a certificate -- a status report.

    An exhausted budget is not "no answer": there is a design, a bound, a node
    count and therefore a gap, and every one of them tells the user whether to
    raise the budget or change the model.
    """
    from .. import exact

    sign = -1 if minimising else 1
    out = {"nodes_opened": seen,
           "incumbent": exact.serialize(sign * incumbent),
           "closed": len(nodes)}
    if best_bound is not None:
        out["best_bound"] = exact.serialize(sign * best_bound)
        out["gap"] = exact.serialize(abs(best_bound - incumbent))
    return out


def prove_optimal(spec, limits: Limits | None = None, spec_path: str = "",
                  max_nodes: int = 5_000, wall_ms=None) -> Result:
    from . import lp, mixed

    lim = limits or Limits()
    t0 = time.perf_counter()

    def ms():
        return (time.perf_counter() - t0) * 1000

    if not spec.discrete:
        return Result("bb", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE, ENGINE,
                      ms(), None, detail=t("engine.bb.no_discrete"))
    # A minimisation is searched as `max -c.x`. Exact and mechanical, and
    # doing it here rather than telling the user to is what keeps the
    # certificate describing the problem they wrote: the payload records the
    # maximisation that was searched AND the minimum in their own sign.
    minimising = spec.sense == "min"
    if minimising:
        spec = _negated(spec)
    for v in spec.discrete:
        if _values(spec, v) is None:
            return Result("bb", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE,
                          ENGINE, ms(), None,
                          detail=t("engine.bb.unbounded", var=v))

    # An incumbent to prune against. `mixed` already knows how to find one and
    # certify it, so the search starts from a design that is real.
    start = mixed.mixed(spec, lim)
    if start.verdict not in (Verdict.SATISFIABLE, Verdict.REFUTED) \
            or start.certificate is None:
        return Result("bb", start.status, Verdict.INCONCLUSIVE, ENGINE, ms(),
                      None, detail=t("engine.bb.no_incumbent",
                                     detail=start.detail))
    incumbent = exact.to_fraction(start.meta["achieved"])
    incumbent_cert = start.certificate.to_dict()

    order = list(spec.discrete)
    nodes, stack = [], [({}, 0)]
    seen = 0
    best_bound = None

    while stack:
        fixed, depth = stack.pop()
        seen += 1
        over_nodes = seen > max_nodes
        over_clock = wall_ms is not None and ms() > wall_ms
        if over_nodes or over_clock:
            part = _partial(nodes, seen - 1, incumbent, best_bound, minimising)
            return Result("bb", Status.RESOURCE_EXHAUSTED,
                          Verdict.INCONCLUSIVE, ENGINE, ms(), None,
                          detail=t("engine.bb.stopped_clock" if over_clock
                                   else "engine.bb.stopped_nodes",
                                   limit=wall_ms if over_clock else max_nodes,
                                   value=part["incumbent"],
                                   bound=part.get("best_bound", "?"),
                                   gap=part.get("gap", "?"),
                                   nodes=part["nodes_opened"]),
                          meta=dict(part, stopped=True))

        node_spec, const = _node_lp(spec, fixed)
        res = lp.opt(node_spec, lim)
        key = _key(order, fixed)

        if res.status is Status.UNSAT or res.verdict is Verdict.UNSATISFIABLE:
            # Infeasible: the subtree is empty, and the ray says why.
            ray = lp.infeasible_certificate(node_spec, lim)
            nodes.append({"fixed": key, "why": "infeasible",
                          # The ray alone. The system it refutes is derived
                          # from the root, so a ray for another node's LP does
                          # not fit here.
                          "ray": (list(ray.payload["y"]) if ray else None)})
            continue

        # "No certificate" used to be read here as "infeasible", and it is not
        # the same fact. A node whose LP was not solved, or was solved and
        # could not be certified, is a node we know NOTHING about -- and
        # closing it as empty prunes a subtree that may hold the optimum,
        # which is how a branch-and-bound tree comes out looking complete and
        # is not. The whole run stops instead.
        if res.certificate is None or not res.meta.get("exact"):
            return Result("bb", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                          ENGINE, ms(), None, detail=t("engine.bb.inexact"))

        bound = const + exact.to_fraction(res.meta["objective"])
        remaining = [v for v in order if v not in fixed]

        if bound <= incumbent:
            # Nothing in this subtree beats what we already have.
            nodes.append(_closed(key, "bound", bound, res.certificate))
            continue

        if not remaining:
            # Every discrete variable fixed: this LP IS that design's answer.
            nodes.append(_closed(key, "leaf", bound, res.certificate))
            if bound > incumbent:
                incumbent = bound
                incumbent_cert = _design(spec, fixed, lim)
            continue

        # The best bound still open anywhere: with it, a stopped search can
        # report a GAP rather than just a design.
        best_bound = bound if best_bound is None else max(best_bound, bound)

        var = remaining[0]
        vals = _values(spec, var)
        nodes.append({"fixed": key, "why": "branch", "on": var,
                      "values": vals,
                      "bound": exact.serialize(bound)})
        for val in vals:
            child = dict(fixed)
            child[var] = val
            stack.append((child, depth + 1))

    cert = branch_bound_certificate(
        incumbent=exact.serialize(incumbent), incumbent_cert=incumbent_cert,
        nodes=nodes, order=order, sense=spec.sense, title=spec.title,
        system=system_of(spec),
        # The tree searched a maximisation. When the user wrote a
        # minimisation, BOTH go in: hiding the negation would leave the
        # certificate describing a problem nobody posed.
        original_sense="min" if minimising else spec.sense,
        original_optimum=exact.serialize(-incumbent if minimising
                                         else incumbent),
    ).stamp(spec_path or None)

    closed = sum(1 for n in nodes if n["why"] != "branch")
    # Back into the sign the user wrote. The tree is over `max -c.x` and the
    # certificate says so; the number on screen is their minimum.
    shown = exact.serialize(-incumbent if minimising else incumbent)
    return Result(
        "bb", Status.UNSAT, Verdict.PROVED, ENGINE, ms(), cert,
        detail=t("engine.bb.optimal_min" if minimising else "engine.bb.optimal",
                 value=shown, nodes=len(nodes), leaves=closed),
        meta={"optimum": shown, "minimising": minimising, "nodes": len(nodes),
              "closed": closed,
              "by_bound": sum(1 for n in nodes if n["why"] == "bound"),
              "infeasible": sum(1 for n in nodes if n["why"] == "infeasible"),
              "leaves": sum(1 for n in nodes if n["why"] == "leaf")},
    )


def _design(spec, fixed, lim):
    """The incumbent as a mixed_design certificate, so it carries its own proof."""
    from . import mixed

    res = mixed.mixed(spec, lim, freeze={v: fixed[v] for v in spec.discrete})
    return res.certificate.to_dict() if res.certificate else None


def _key(order, fixed) -> list:
    """A node's identity: the fixings, in a fixed variable order."""
    return [[v, int(fixed[v])] for v in order if v in fixed]
