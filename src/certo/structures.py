"""Set families, hypergraphs, designs and mask systems.

These shapes recur constantly and were being re-encoded by hand in every spec:
a tuple of frozensets here, a list of bitmasks there, a `key` function to turn
them into ids, a `canonicalize` to quotient by relabelling, a `reduce` to
shrink them. Four pieces of boilerplate per problem, each a place to get it
subtly wrong.

The point of a native type here is not that it holds data -- a tuple does that.
It is that it supplies the three things the rest of the tool asks for:

    key            a stable id, so the certificate names the object
    canonical()    a canonical form under relabelling the ground set
    reductions()   what "one step smaller" means

so a `DomainSpec` over these needs none of them spelled out, and `reduce`,
`canonicalize` and `key` can all be left at "auto".

On the canonical form. It is EXACT, not a heuristic invariant: two families
get the same canonical form exactly when a relabelling of the ground set
carries one to the other. It is computed by refining the points into classes
that no relabelling can mix -- degree, then the multiset of sizes of the
blocks through each point, then the same again on the refined classes -- and
minimising over the permutations that respect the refinement. On anything with
structure that is a handful of permutations. On a highly regular family it
degenerates towards n!, so there is a cap, and hitting it RAISES rather than
returning a cheaper invariant: a "canonical form" that merges two
non-isomorphic objects would silently merge two orbits, and nothing
downstream would notice.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations

from .i18n import t

#: Above this many candidate permutations, `canonical()` raises instead of
#: guessing. See the module docstring for why it is not a soft failure.
PERM_CAP = 200_000


@dataclass(frozen=True)
class SetFamily:
    """A family of subsets of the ground set {0, ..., n-1}.

    A hypergraph is this; so is a block design, a covering, a code, a
    collection of arms around a separator. The name is the neutral one.

    Blocks are stored sorted and deduplicated, so two families that differ
    only in how they were written are the same object -- `==`, `hash` and the
    id all agree, which is what lets a domain be deduplicated at all.
    """

    n: int
    blocks: tuple

    def __init__(self, n: int, blocks):
        norm = sorted({tuple(sorted(set(b))) for b in blocks})
        object.__setattr__(self, "n", int(n))
        object.__setattr__(self, "blocks", tuple(norm))

    # --- reading ----------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self.blocks)

    def degree(self, p: int) -> int:
        return sum(1 for b in self.blocks if p in b)

    def degrees(self) -> tuple:
        return tuple(self.degree(p) for p in range(self.n))

    def pair_degree(self, p: int, q: int) -> int:
        return sum(1 for b in self.blocks if p in b and q in b)

    def is_uniform(self, k=None):
        sizes = {len(b) for b in self.blocks}
        if len(sizes) != 1:
            return False
        return True if k is None else sizes == {k}

    def is_regular(self, r=None):
        ds = set(self.degrees())
        if len(ds) != 1:
            return False
        return True if r is None else ds == {r}

    def is_design(self, t_: int, lam: int) -> bool:
        """Every t-subset of points lies in exactly `lam` blocks."""
        if self.n < t_:
            return False
        for sub in combinations(range(self.n), t_):
            hit = sum(1 for b in self.blocks if all(p in b for p in sub))
            if hit != lam:
                return False
        return True

    def covers(self) -> bool:
        """Is every point in some block?"""
        return all(self.degree(p) > 0 for p in range(self.n))

    def intersecting(self) -> bool:
        """Do all pairs of blocks meet? The Erdos-Ko-Rado shape."""
        return all(set(a) & set(b)
                   for a, b in combinations(self.blocks, 2))

    # --- identity ---------------------------------------------------------

    #: Above this many points, an id separates them. At or below it a point is
    #: one character and juxtaposition is unambiguous, so ids stay exactly
    #: what they have always been -- which is what every stored certificate
    #: contains.
    SEPARATE_ABOVE = 10

    def key(self) -> str:
        """A stable, readable id. This is what lands in a certificate.

        Juxtaposing point numbers is unambiguous only while a point is one
        digit. On eleven points or more it is not: `{1,2,13}` and `{12,13}`
        both read as "1213", so two DIFFERENT families shared an id and the
        round trip returned a third family. Above ten points the id separates
        its points; at or below, nothing changes.
        """
        sep = "." if self.n > self.SEPARATE_ABOVE else ""
        return "{}:{}".format(
            self.n, "|".join(sep.join(str(p) for p in b) for b in self.blocks))

    def __str__(self) -> str:
        return self.key()

    @classmethod
    def from_key(cls, s: str) -> "SetFamily":
        """The inverse of `key`, reading the point count to know which form."""
        n, _, rest = s.partition(":")
        n = int(n)
        parts = [p for p in rest.split("|") if p]
        if n > cls.SEPARATE_ABOVE:
            blocks = [tuple(int(x) for x in part.split(".")) for part in parts]
        else:
            blocks = [tuple(int(c) for c in part) for part in parts]
        return cls(n, blocks)

    # --- symmetry ---------------------------------------------------------

    def relabelled(self, perm) -> "SetFamily":
        return SetFamily(self.n, [tuple(perm[p] for p in b)
                                  for b in self.blocks])

    def _classes(self) -> list:
        """Point classes no relabelling can mix, refined until stable.

        A relabelling permutes points but preserves how a point sits in the
        family, so points with different signatures can never be swapped.
        Each round makes the signature depend on the previous round's classes,
        which is the same refinement idea as 1-WL on graphs.
        """
        sig = [(self.degree(p),
                tuple(sorted(len(b) for b in self.blocks if p in b)))
               for p in range(self.n)]
        colour = {s: i for i, s in enumerate(sorted(set(sig)))}
        cols = [colour[s] for s in sig]

        for _ in range(self.n):
            fresh = []
            for p in range(self.n):
                around = tuple(sorted(
                    tuple(sorted(cols[q] for q in b)) for b in self.blocks
                    if p in b))
                fresh.append((cols[p], around))
            colour = {s: i for i, s in enumerate(sorted(set(fresh)))}
            new = [colour[s] for s in fresh]
            if new == cols:
                break
            cols = new

        groups: dict = {}
        for p, c in enumerate(cols):
            groups.setdefault(c, []).append(p)
        return [groups[c] for c in sorted(groups)]

    def canonical(self) -> tuple:
        """The lexicographically smallest relabelling. EXACT, or it raises."""
        classes = self._classes()
        total = 1
        for cl in classes:
            for i in range(2, len(cl) + 1):
                total *= i
            if total > PERM_CAP:
                raise ValueError(t("structures.too_symmetric", n=self.n,
                                   cap=PERM_CAP))

        best = None
        for combo in _class_permutations(classes):
            # `combo` is the order in which the original points take the
            # labels 0, 1, 2, ... Permuting points WITHIN their classes and
            # keeping their old labels is not enough: two isomorphic families
            # whose classes sit at different labels would keep them and come
            # out different. The labels have to be reassigned canonically.
            perm = {src: idx for idx, src in enumerate(combo)}
            form = self.relabelled(perm).blocks
            if best is None or form < best:
                best = form
        return (self.n, best)

    # --- reductions -------------------------------------------------------

    def without_block(self, i: int) -> "SetFamily":
        return SetFamily(self.n, self.blocks[:i] + self.blocks[i + 1:])

    def without_point(self, p: int) -> "SetFamily":
        """Delete a point and renumber, so the ground set stays {0..n-2}."""
        shift = {q: (q if q < p else q - 1) for q in range(self.n) if q != p}
        return SetFamily(self.n - 1,
                         [tuple(shift[q] for q in b if q != p)
                          for b in self.blocks if any(q != p for q in b)])

    def reductions(self) -> list:
        """Blocks first, then points.

        Dropping a block is the smaller step and usually the informative one:
        it answers "is this block needed?", which is the question a minimal
        counterexample is meant to settle. Deleting a point changes the ground
        set and can only be judged afterwards.
        """
        return ([self.without_block(i) for i in range(self.size)]
                + [self.without_point(p) for p in range(self.n)])

    # --- construction -----------------------------------------------------

    @classmethod
    def uniform(cls, n: int, k: int, blocks) -> "SetFamily":
        f = cls(n, blocks)
        if not f.is_uniform(k):
            raise ValueError(t("structures.not_uniform", k=k))
        return f

    @classmethod
    def complete(cls, n: int, k: int) -> "SetFamily":
        """Every k-subset. The full k-uniform hypergraph."""
        return cls(n, combinations(range(n), k))

    @classmethod
    def all_families(cls, n: int, k: int, size: int):
        """Every k-uniform family of exactly `size` blocks on n points.

        The domain a `DomainSpec` sweeps. Not deduplicated by isomorphism --
        that is `canonicalize`'s job, and doing it here would hide how many
        labelled objects there were, which is half the answer.
        """
        for chosen in combinations(list(combinations(range(n), k)), size):
            yield cls(n, chosen)


def _class_permutations(classes):
    """Every relabelling that respects the point classes."""
    if not classes:
        yield ()
        return
    head, rest = classes[0], classes[1:]
    for first in permutations(head):
        for tail in _class_permutations(rest):
            yield first + tail


# ---------------------------------------------------------------------------
# masks
# ---------------------------------------------------------------------------


def mask_to_set(m: int, n: int) -> tuple:
    return tuple(i for i in range(n) if m >> i & 1)


def set_to_mask(s) -> int:
    out = 0
    for i in s:
        out |= 1 << i
    return out


def family_from_masks(n: int, masks) -> SetFamily:
    """A mask system as a set family, so it gets the id and the canonical form.

    Masks are a representation, not a type: keeping them as integers all the
    way through is what leaves a certificate saying `[7, 11, 13]` with nothing
    to say which points those are.
    """
    return SetFamily(n, [mask_to_set(m, n) for m in masks])
