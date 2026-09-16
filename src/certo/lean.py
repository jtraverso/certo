"""Lean 4 export.

Scope, stated up front: this emits a counterexample as DATA plus the
definitions around it. It does not emit a proof of anything about the
counterexample -- only the object itself, ready to state things about.

The output compiles: it was checked against Lean v4.28.0 with Mathlib at the
matching revision, including the two `example` sanity checks, which are real
proofs by `decide`. Getting there took three rounds against a real compiler
(`loopless` could not be `decide`d, and `edgeFinset` is not in
`SimpleGraph.Basic`), which is precisely why guessing at Lean output without
compiling it is a bad idea.

`SimpleGraph.fromRel` is used rather than the anonymous-constructor form
because it symmetrises and drops loops itself, leaving no obligations to
discharge -- and therefore nothing to break when Mathlib moves `Irreflexive`
around.

It exists because transcribing a counterexample into Lean by hand is
mechanical and is exactly where errors creep in.
"""
from __future__ import annotations

from . import __version__
from .graphs import Graph

HEADER = """\
/-
  Counterexample exported by certo {version}.
  {source}

  Checked against Lean v4.28.0 with Mathlib at v4.28.0; other versions may
  need adjusting. The edge list is transcribed from the certificate and is
  exact whatever your toolchain says.
-/
import Mathlib.Combinatorics.SimpleGraph.Basic

namespace Certo
"""

BODY = """
/-- graph6 `{g6}` : n = {n}, m = {m}. -/
def {name}Edges : List (Fin {n} × Fin {n}) :=
  [{edges}]

/-- The counterexample as a `SimpleGraph`.

`fromRel` symmetrises the relation and drops loops on its own, so there are
no `symm` or `loopless` obligations to discharge -- which also keeps this
robust across the Mathlib versions that have moved `Irreflexive` around. -/
def {name} : SimpleGraph (Fin {n}) :=
  SimpleGraph.fromRel (fun a b => (a, b) ∈ {name}Edges)

instance : DecidableRel {name}.Adj := fun a b => by
  unfold {name} SimpleGraph.fromRel; infer_instance

/-- Sanity check: the first edge really is there, and no vertex is adjacent to
itself. Kept to what `SimpleGraph.Basic` alone provides, so the file needs no
further imports. -/
example : {name}.Adj {a} {b} := by decide
example : ¬ {name}.Adj {a} {a} := by decide
"""

FOOTER = """
end Certo
"""


def _first_edge(g: Graph) -> dict:
    """An edge to assert in the sanity check. Isolated graphs have none."""
    for a, b in g.edges():
        return {"a": a, "b": b}
    return {"a": 0, "b": 0}


def graph_to_lean(g: Graph, name: str = "cex", source: str = "") -> str:
    edges = ", ".join("({}, {})".format(a, b) for a, b in g.edges())
    return (
        HEADER.format(version=__version__,
                      source="Source: " + source if source else "")
        + BODY.format(name=name, n=g.n, m=g.m, g6=g.to_graph6(), edges=edges,
                      **_first_edge(g))
        + FOOTER
    )


def graphs_to_lean(graphs, source: str = "") -> str:
    """Several counterexamples in one file, named cex0, cex1, ..."""
    if len(graphs) == 1:
        return graph_to_lean(graphs[0], "cex", source)
    parts = [HEADER.format(version=__version__,
                           source="Source: " + source if source else "")]
    for i, g in enumerate(graphs):
        edges = ", ".join("({}, {})".format(a, b) for a, b in g.edges())
        parts.append(BODY.format(name="cex{}".format(i), n=g.n, m=g.m,
                                 g6=g.to_graph6(), edges=edges,
                                 **_first_edge(g)))
    parts.append(FOOTER)
    return "".join(parts)


def graphs_from_certificate(data: dict) -> list:
    """Pull the counterexamples out of whatever certificate kind it is."""
    kind, p = data.get("kind"), data.get("payload", {})
    if kind == "shrink_graph":
        return [Graph.from_graph6(p["minimal"])]
    if kind == "sweep":
        return [Graph.from_graph6(e["g6"]) for e in p.get("entries", [])]
    if kind == "graph_set":
        return [Graph.from_graph6(s) for s in p.get("graph6", [])]
    raise ValueError(
        "no graph counterexample in a {} certificate; --lean reads "
        "shrink_graph, sweep or graph_set".format(kind))
