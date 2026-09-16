"""Quotienting a finite domain by a symmetry.

Combinatorial searches produce relabelled copies of the same object by the
hundred. A sweep that reports 1,400 counterexamples where there are four
structural ones has not told you four things and buried them -- it has told
you one thing, 1,400 times, and left the reading to you.

What a spec declares is a `canonicalize` function: item -> a hashable
canonical form, equal exactly for items in the same orbit. Nothing here knows
what the group is, and it does not need to; it needs to know when two items
are the same.

The honest boundary, stated once and repeated in the certificate. Two items
sharing a canonical form is a CLAIM of the spec, not something checkable
here -- `canonicalize` is arbitrary Python. What IS checkable, and is checked,
is that the decomposition is internally consistent: every item lands in
exactly one orbit, every representative belongs to the orbit it represents,
and the counts add up. A decomposition whose parts do not add up is wrong
whatever the group was.

Every item is still EVALUATED. Quotienting happens on the way out, not on the
way in: evaluating one representative per orbit would need the predicate to be
invariant under the symmetry, which nothing here can establish.
"""
from __future__ import annotations

from .i18n import t


class Orbits:
    """A domain split into orbits, with a chosen representative for each.

    The representative is the item with the smallest id, compared as a string.
    An arbitrary rule, but a DETERMINISTIC one: the certificate names a
    representative, and two runs that disagreed about which item that is would
    produce certificates that look contradictory while saying the same thing.
    """

    __slots__ = ("items", "ids", "canon", "groups", "order")

    def __init__(self, items, ids, canonical):
        self.items = list(items)
        self.ids = list(ids)
        self.canon = list(canonical)
        self.groups = {}
        self.order = []
        for i, c in enumerate(self.canon):
            if c not in self.groups:
                self.groups[c] = []
                self.order.append(c)
            self.groups[c].append(i)

    @property
    def labelled(self) -> int:
        return len(self.items)

    @property
    def count(self) -> int:
        return len(self.order)

    def representative(self, c) -> int:
        """Index of the smallest id in the orbit. Deterministic, not minimal."""
        return min(self.groups[c], key=lambda i: (self.ids[i], i))

    def representatives(self) -> list:
        return [self.representative(c) for c in self.order]

    def summary(self, only=None) -> list:
        """One row per orbit: representative, size, and a few members.

        `only` restricts to a set of item indices -- the counterexamples --
        because the orbit structure of the things that FAILED is the answer,
        and the structure of the whole domain rarely is.
        """
        keep = None if only is None else set(only)
        out = []
        for c in self.order:
            members = self.groups[c] if keep is None else [
                i for i in self.groups[c] if i in keep]
            if not members:
                continue
            rep = min(members, key=lambda i: (self.ids[i], i))
            out.append({
                "representative": self.ids[rep],
                "size": len(members),
                "members": [self.ids[i] for i in members[:5]],
                "canonical": str(c)[:120],
            })
        out.sort(key=lambda r: (-r["size"], r["representative"]))
        return out


def _auto(item):
    """The canonical form a native type supplies for itself.

    Graphs have one under isomorphism; so do the combinatorial types. Asking
    the item beats a registry keyed on type, because a user's own class can
    join simply by having the method.
    """
    fn = getattr(item, "canonical", None)
    if callable(fn):
        return fn()
    from .graphs import Graph, canonical_form

    if isinstance(item, Graph):
        return canonical_form(item)
    raise TypeError(t("orbits.no_auto", got=type(item).__name__))


def build(spec, items, ids) -> Orbits | None:
    """Apply the spec's `canonicalize`, or None if it declares no symmetry."""
    fn = getattr(spec, "canonicalize", None)
    if fn == "auto":
        fn = _auto
    if fn is None:
        return None
    canon = []
    for item in items:
        c = fn(item)
        try:
            hash(c)
        except TypeError:
            raise TypeError(t("orbits.unhashable", got=type(c).__name__))
        canon.append(c)
    return Orbits(items, ids, canon)


SPOT_CHECKS = 12


def infer(evaluate, items, groups, outcome_code):
    """Evaluate one item per orbit; infer the rest, marked in lower case.

    Shared by both sweeps rather than written twice: two copies of "what a
    --by-orbit run produces" that drifted apart would make a replay disagree
    with the vector it is replaying.
    """
    reps = {c: groups.representative(c) for c in groups.order}
    evaluated = {c: evaluate(items[i]) for c, i in reps.items()}
    outcomes, codes = [], []
    for i in range(len(items)):
        c = groups.canon[i]
        out = evaluated[c]
        outcomes.append(out)
        code = outcome_code(out)
        codes.append(code if i == reps[c] else code.lower())
    return outcomes, codes, reps, evaluated


def spot_check(evaluate, items, groups, reps, evaluated, ids, outcome_code,
               rng, n=SPOT_CHECKS):
    """Go and look at real non-representatives.

    `--by-orbit` reports a representative's verdict for its whole orbit, which
    is sound only if the predicate cannot tell members apart -- and nothing
    can prove that, since `canonicalize` and the predicate are both arbitrary
    Python. This cannot make the sweep sound. It can make a wrong symmetry
    surface immediately instead of in a referee's report.
    """
    pool = [(c, i) for c, members in groups.groups.items() for i in members
            if i != reps[c]]
    done, clash = [], None
    if not pool:
        return done, clash
    for c, idx in rng.sample(pool, min(n, len(pool))):
        got = outcome_code(evaluate(items[idx]))
        want = outcome_code(evaluated[c])
        done.append({"index": idx, "id": ids[idx],
                     "representative": ids[reps[c]], "agreed": got == want})
        if got != want:
            clash = (ids[idx], ids[reps[c]])
            break
    return done, clash


def check(payload) -> list:
    """What a stored decomposition can be checked for, without the spec.

    Not that the orbits are right -- that is the spec's claim -- but that the
    arithmetic of the decomposition holds together. A certificate whose parts
    do not add up is wrong whatever the group was.
    """
    rows = payload.get("orbits") or []
    labelled = payload.get("labelled", 0)
    checks = []

    total = sum(r["size"] for r in rows)
    checks.append((t("verify.orbits.partition"), total == labelled,
                   t("verify.orbits.counts", orbits=len(rows), items=total,
                     labelled=labelled)))

    reps = [r["representative"] for r in rows]
    checks.append((t("verify.orbits.distinct"), len(set(reps)) == len(reps),
                   t("verify.orbits.repeated",
                     n=len(reps) - len(set(reps)))))

    inside = all(not r["members"] or r["representative"] <= max(r["members"])
                 for r in rows)
    checks.append((t("verify.orbits.representative"), inside, ""))
    return checks
