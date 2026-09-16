"""Packings and hypergraphs: items competing for shared resources.

The same shape keeps reappearing -- cliques competing for edges, blocks
competing for points, anything competing for anything -- and rebuilding the LP
by hand each time is both tedious and a place for mistakes to hide.

    PackingSpec(items=[("T012", {"e01","e02","e12"}, 2), ...], capacities=1)

`to_lp()` hands back an `LPSpec`, so everything the exact machinery already
does comes for free: rational coefficients in, exact dual out, a certificate
that verifies without a solver.

THE DUAL IS THE LOAD CERTIFICATE. Constraint names are resource names, so
`y_r` reads directly as "the load carried by resource r" -- which is usually
the object you actually wanted, not the primal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .exact import to_fraction


@dataclass
class PackingSpec:
    """items: (name, resources, gain[, kind]). capacities: dict or a scalar.

    `kind` is free-form and only used to split the optimum by type:
    `restricted({"K3"})` gives the best you can do with triangles alone,
    which is what tells you whether mixing actually buys anything.
    """

    items: list
    capacities: object = 1              # dict resource -> cap, or one number
    sense: str = "max"
    integer: bool = False
    title: str = ""
    _kinds: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        norm = []
        for it in self.items:
            name, resources, gain = it[0], list(it[1]), it[2]
            kind = it[3] if len(it) > 3 else ""
            if not resources:
                raise ValueError("item {} uses no resource".format(name))
            norm.append((str(name), resources, to_fraction(gain), str(kind)))
        names = [i[0] for i in norm]
        if len(set(names)) != len(names):
            raise ValueError("duplicate item names in the packing")
        self.items = norm
        self._kinds = {i[0]: i[3] for i in norm}

    # -- structure ---------------------------------------------------------

    @property
    def resources(self) -> list:
        seen, out = set(), []
        for _, res, _, _ in self.items:
            for r in res:
                if r not in seen:
                    seen.add(r)
                    out.append(str(r))
        return out

    @property
    def kinds(self) -> list:
        return sorted({k for k in self._kinds.values() if k})

    def capacity_of(self, resource):
        if isinstance(self.capacities, dict):
            return to_fraction(self.capacities.get(resource, 1))
        return to_fraction(self.capacities)

    def restricted(self, kinds) -> "PackingSpec":
        """Only items of these kinds. This is the 'optimum by type'."""
        keep = {str(k) for k in kinds}
        return PackingSpec(
            items=[(n, r, g, k) for n, r, g, k in self.items if k in keep],
            capacities=self.capacities, sense=self.sense,
            integer=self.integer,
            title="{} [{}]".format(self.title, ", ".join(sorted(keep))),
        )

    # -- to the LP ---------------------------------------------------------

    def to_lp(self):
        """An LPSpec. Constraint names are resource names, so the dual reads
        as a load per resource."""
        from .spec import LPSpec

        lp = LPSpec(sense=self.sense, integer=self.integer,
                    title=self.title or "packing")
        for name, _, _, _ in self.items:
            lp.variable(name)
        lp.objective({name: gain for name, _, gain, _ in self.items})

        by_resource: dict = {}
        for name, res, _, _ in self.items:
            for r in res:
                by_resource.setdefault(str(r), []).append(name)
        for r in self.resources:
            lp.constraint({n: 1 for n in by_resource[r]}, "<=",
                          self.capacity_of(r), name=r)
        return lp

    # -- convenience for graphs -------------------------------------------

    @classmethod
    def cliques_in_graph(cls, g, gains: dict, capacities=1,
                         title: str = "") -> "PackingSpec":
        """Pack cliques of the given sizes, with edges as the resources.

            PackingSpec.cliques_in_graph(g, {3: 2, 4: 5})

        `gains` maps clique size to its worth. Sizes and weights stay explicit
        because "edges minus one" is one convention among several.
        """
        items = []
        for size in sorted(gains):
            for s in combinations(range(g.n), size):
                if all(g.has_edge(a, b) for a, b in combinations(s, 2)):
                    res = ["e{}_{}".format(a, b) for a, b in combinations(s, 2)]
                    items.append(("K{}_{}".format(size, "".join(map(str, s))),
                                  res, gains[size], "K{}".format(size)))
        return cls(items=items, capacities=capacities,
                   title=title or "clique packing on n={}".format(g.n))


def loads_from_dual(cert) -> dict:
    """Read a packing dual back as {resource: load}.

    The dual of a packing is not a by-product: it is the load assignment that
    proves the bound, and it is usually what you want to quote.
    """
    p = cert.payload if hasattr(cert, "payload") else cert.get("payload", {})
    names, dual = p.get("names", []), p.get("dual", [])
    return {n: v for n, v in zip(names, dual) if str(v) not in ("0", "0.0")}
