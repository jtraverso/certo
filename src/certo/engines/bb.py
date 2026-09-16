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

ENGINE = "certo/branch-and-bound"


def _values(spec, var):
    """Every integer a discrete variable may take. Finite, or there is no tree."""
    lo, hi = spec.bounds[var]
    lo = int(lo or 0)
    if hi is None:
        return None
    return list(range(lo, int(hi) + 1))


def _node_lp(spec, fixed):
    """The relaxation at a node: the fixed variables gone, the rest free."""
    from ..spec import LPSpec

    out = LPSpec(sense=spec.sense, title=spec.title)
    free = [v for v in spec.var_names if v not in fixed]
    for v in free:
        lo, hi = spec.bounds[v]
        out.variable(v, lo, hi)
    out.objective({v: c for v, c in spec.obj.items() if v in set(free)})
    const = sum((exact.to_fraction(spec.obj.get(v, 0)) * Fraction(val)
                 for v, val in fixed.items()), Fraction(0))
    for name, coeffs, sense, rhs in spec.cons:
        moved = sum((exact.to_fraction(c) * Fraction(fixed[v])
                     for v, c in coeffs.items() if v in fixed), Fraction(0))
        rest = {v: c for v, c in coeffs.items() if v not in fixed}
        out.constraint(rest, sense, exact.to_fraction(rhs) - moved, name=name)
    return out, const


def prove_optimal(spec, limits: Limits | None = None, spec_path: str = "",
                  max_nodes: int = 5_000) -> Result:
    from . import lp, mixed

    lim = limits or Limits()
    t0 = time.perf_counter()

    def ms():
        return (time.perf_counter() - t0) * 1000

    if not spec.discrete:
        return Result("bb", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE, ENGINE,
                      ms(), None, detail=t("engine.bb.no_discrete"))
    if spec.sense != "max":
        return Result("bb", Status.OUT_OF_THEORY, Verdict.INCONCLUSIVE, ENGINE,
                      ms(), None, detail=t("engine.bb.only_max"))
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

    while stack:
        fixed, depth = stack.pop()
        seen += 1
        if seen > max_nodes:
            return Result("bb", Status.RESOURCE_EXHAUSTED,
                          Verdict.INCONCLUSIVE, ENGINE, ms(), None,
                          detail=t("engine.bb.budget", n=max_nodes,
                                   value=exact.serialize(incumbent)))

        node_spec, const = _node_lp(spec, fixed)
        res = lp.opt(node_spec, lim)
        key = _key(order, fixed)

        if res.status is Status.UNSAT or res.verdict is Verdict.UNSATISFIABLE \
                or res.certificate is None:
            # Infeasible: the subtree is empty, and the ray says why.
            ray = lp.infeasible_certificate(node_spec, lim)
            nodes.append({"fixed": key, "why": "infeasible",
                          "cert": ray.to_dict() if ray else None})
            continue

        if not res.meta.get("exact"):
            return Result("bb", Status.UNKNOWN_SOLVER, Verdict.INCONCLUSIVE,
                          ENGINE, ms(), None, detail=t("engine.bb.inexact"))

        bound = const + exact.to_fraction(res.meta["objective"])
        remaining = [v for v in order if v not in fixed]

        if bound <= incumbent:
            # Nothing in this subtree beats what we already have.
            nodes.append({"fixed": key, "why": "bound",
                          "bound": exact.serialize(bound),
                          "cert": res.certificate.to_dict()})
            continue

        if not remaining:
            # Every discrete variable fixed: this LP IS that design's answer.
            nodes.append({"fixed": key, "why": "leaf",
                          "bound": exact.serialize(bound),
                          "cert": res.certificate.to_dict()})
            if bound > incumbent:
                incumbent = bound
                incumbent_cert = _design(spec, fixed, lim)
            continue

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
    ).stamp(spec_path or None)

    closed = sum(1 for n in nodes if n["why"] != "branch")
    return Result(
        "bb", Status.UNSAT, Verdict.PROVED, ENGINE, ms(), cert,
        detail=t("engine.bb.optimal", value=exact.serialize(incumbent),
                 nodes=len(nodes), leaves=closed),
        meta={"optimum": exact.serialize(incumbent), "nodes": len(nodes),
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
