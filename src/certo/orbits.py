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

OR HAND OVER THE LABELLING INSTEAD, and that boundary moves.

`canonicalize` returns a form and asks to be believed. `labelling` returns the
PERMUTATION that produced it, and asks to be checked:

    labelling=lambda item: {source_point: label, ...}

certo applies it -- `item.relabelled(perm)` -- and the result IS the canonical
form. So "these two items are the same object relabelled" stops being the
spec's claim and becomes an arithmetic fact with a witness attached, and the
witness travels in the certificate for anyone to re-apply.

This is the same division of labour as everywhere else. Computing a canonical
labelling well is a hard search that a dedicated tool does far better than
this one ever will -- certo's own canonical form refuses outright on a
vertex-transitive object, where 15 points already means 15! candidate
relabellings and the automorphism group is too small to dent it. So: nauty
finds the labelling, certo checks it, and the artefact carries both.

WHAT IS STILL NOT ESTABLISHED, and is said rather than implied: that two
DIFFERENT representatives are non-isomorphic. Every witness here shows two
items are the same; nothing here shows two items are different. A labelling
that is isomorphism-invariant gives that too, and whether the one handed over
is invariant is exactly what certo cannot check.

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

    __slots__ = ("items", "ids", "canon", "groups", "order", "witness")

    def __init__(self, items, ids, canonical, witness=None):
        self.items = list(items)
        self.ids = list(ids)
        self.canon = list(canonical)
        #: index -> the permutation that carried this item to its canonical
        #: form, when the spec handed one over. Empty when it did not.
        self.witness = dict(witness or {})
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
            row = {
                "representative": self.ids[rep],
                "size": len(members),
                "members": [self.ids[i] for i in members[:5]],
                "canonical": str(c)[:120],
            }
            if self.witness:
                # EVERY member, not the five that are listed for reading. A
                # witness for some of them would make the orbit checkable in
                # part, which is the same as not checkable.
                row["witnesses"] = [
                    [self.ids[i], _pairs(self.witness[i])] for i in members
                    if i in self.witness]
            out.append(row)
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


def _pairs(perm) -> list:
    """A permutation as sorted `[source, label]` pairs, so JSON keeps it exact."""
    return [[int(k), int(v)] for k, v in sorted(perm.items())]


def apply_labelling(item, perm):
    """`item` relabelled by `perm`, with `perm` checked to be a permutation.

    A labelling that is not a bijection of the ground set is not a relabelling
    of anything, and the form it produces would be a different object rather
    than the same one renamed. Refused rather than applied.
    """
    n = getattr(item, "n", None)
    if n is None:
        raise TypeError(t("orbits.no_relabel", got=type(item).__name__))
    perm = {int(k): int(v) for k, v in dict(perm).items()}
    if sorted(perm) != list(range(n)) or sorted(perm.values()) != list(range(n)):
        raise ValueError(t("orbits.not_a_permutation", n=n, got=len(perm)))
    relabel = getattr(item, "relabelled", None)
    if not callable(relabel):
        raise TypeError(t("orbits.no_relabel", got=type(item).__name__))
    return relabel(perm), perm


def build(spec, items, ids) -> Orbits | None:
    """Apply the spec's `canonicalize` or `labelling`, or None for no symmetry.

    `canonicalize` gives a form and asks to be believed. `labelling` gives the
    permutation, certo applies it, and the form is what comes out -- so the
    orbit is a fact with a witness rather than a claim.
    """
    fn = getattr(spec, "canonicalize", None)
    label_fn = getattr(spec, "labelling", None)
    if fn is not None and label_fn is not None:
        raise TypeError(t("orbits.both"))
    if label_fn is not None:
        canon, witness = [], {}
        for i, item in enumerate(items):
            form, perm = apply_labelling(item, label_fn(item))
            try:
                hash(form)
            except TypeError:
                raise TypeError(t("orbits.unhashable",
                                  got=type(form).__name__))
            canon.append(form)
            witness[i] = perm
        return Orbits(items, ids, canon, witness)

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

    checks.extend(_check_witnesses(rows))
    return checks


def _decode(item_id: str):
    """The object a stored id came from, recognised by its own round trip.

    A type that cannot round-trip through its id leaves its witnesses carried
    but not re-applied, and `check` reports that count rather than passing
    quietly over it.
    """
    from .structures import SetFamily

    for cls in (SetFamily,):
        try:
            back = cls.from_key(item_id)
        except Exception:                                   # noqa: BLE001
            continue
        if back.key() == item_id:
            return back
    return None


def _witness_of(row, member_id):
    """The stored permutation for one member, or None."""
    for mid, perm in row.get("witnesses") or []:
        if mid == member_id:
            return dict(perm)
    return None


def _check_witnesses(rows) -> list:
    """Re-apply every stored permutation. This is the whole point.

    A witness says "this member is the representative, relabelled, and here is
    the relabelling". Re-applying it is arithmetic: no canonical form is
    computed, nothing about certo's own algorithm is trusted, and no cap can
    be hit. What it does NOT show is that two different representatives are
    different objects, and the warning beside it says so.
    """
    witnessed = [r for r in rows if r.get("witnesses")]
    if not witnessed:
        return []

    total = sum(len(r["witnesses"]) for r in witnessed)
    partial = [r["representative"] for r in witnessed
               if len(r["witnesses"]) != r["size"]]
    checks = [(t("verify.orbits.all_witnessed"), not partial,
               t("verify.orbits.witness_counts", n=total,
                 names=", ".join(map(str, partial[:3])) or "-"))]

    bad, skipped = [], 0
    for row in witnessed:
        target = _decode(row["representative"])
        rep_perm = _witness_of(row, row["representative"])
        if target is None or rep_perm is None:
            skipped += len(row["witnesses"])
            continue
        try:
            want, _ = apply_labelling(target, rep_perm)
        except (TypeError, ValueError):
            bad.append(row["representative"])
            continue
        for member_id, perm in row["witnesses"]:
            item = _decode(member_id)
            if item is None:
                skipped += 1
                continue
            try:
                got, _ = apply_labelling(item, dict(perm))
            except (TypeError, ValueError):
                bad.append(member_id)
                continue
            if got != want:
                bad.append(member_id)

    checks.append((t("verify.orbits.witnessed"), not bad,
                   t("verify.orbits.reapplied", n=total - skipped,
                     skipped=skipped,
                     names=", ".join(map(str, bad[:3])) or "-")))
    return checks
