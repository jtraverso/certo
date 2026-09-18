"""Which command answers which question, as data rather than as a print.

Forty commands and twenty-one spec types is a lot of choosing for somebody
-- or something -- that just wants to know whether a claim holds. The routing
knowledge existed and lived inside a terminal renderer, which meant the only
way to use it was to read it.

So it lives here, and three things consume it: the terminal table, an MCP tool
that a model calls FIRST when it knows what it wants to establish but not
which tool establishes it, and `certo ask`, which takes a spec and routes on
its type.

THE ORDER OF THE COLUMNS IS THE POINT. Read the question, not the name. A
command called `peak` tells you nothing; "which integer is best for every n"
tells you whether it is yours.

Each row also carries what the answer COSTS to re-check -- whether the
certificate stands on its own arithmetic or needs a solver again -- because
for a model choosing between two routes to the same fact, that is usually the
deciding difference and it is invisible from the name.
"""
from __future__ import annotations

from .i18n import t as _t

#: command -> the spec class it loads, for `ask` and for the table. A command
#: with no spec type takes a directory or a file instead.
SPEC_OF = {
    "prove": "Spec", "check": "Spec", "core": "Spec", "farkas": "Spec",
    "induct": "InductSpec", "synth": "SynthSpec", "opt": "LPSpec",
    "mixed": "LPSpec", "bisect": "BisectSpec", "bounds": "BoundSpec",
    "order": "OrderSpec", "parametric": "ParametricSpec", "peak": "PeakSpec",
    "entry": "EntrySpec", "moment": "MomentSpec", "ratio": "RatioSpec",
    "family": "FamilySpec", "cover": "CoverSpec", "exists": "CoverSpec",
    "sweep": "SweepSpec", "cases": "CNFSpec", "shrink": "SweepSpec",
    "ideal": "IdealSpec", "eliminate": "EliminateSpec", "sos": "SOSSpec",
    "number": "NumberSpec", "compose": "ProofSpec", "lint": "*",
    "audit": "*", "reduce": "SymmetrySpec", "matrix": "MatrixSpec", "solve": "LinearSystemSpec",
    "quotient": "EquitableQuotientSpec", "cone": "ConeSpec",
}

#: Which commands leave a certificate that re-checks with NO solver.
SOLVER_FREE = {
    "cone", "quotient", "solve", "matrix", "reduce", "farkas", "parametric", "peak", "entry", "moment", "ratio", "exists",
    "cover", "ideal", "eliminate", "sos", "number", "order", "bounds",
    "cases",
}

BY_QUESTION = (
    ("commands.group.true", (
        ("commands.q.prove", "prove"),
        ("commands.q.core", "core"),
        ("commands.q.farkas", "farkas"),
        ("commands.q.induct", "induct"),
    )),
    ("commands.group.sane", (
        ("commands.q.regime", "check --hypotheses-only"),
        ("commands.q.lint", "lint"),
        ("commands.q.audit", "audit"),
        ("commands.q.status", "status"),
        ("commands.q.doctor", "doctor"),
    )),
    ("commands.group.size", (
        ("commands.q.opt", "opt"),
        ("commands.q.optimal", "mixed --prove-optimal"),
        ("commands.q.bisect", "bisect"),
        ("commands.q.bounds", "bounds"),
        ("commands.q.order", "order"),
        ("commands.q.reduce", "reduce"),
        ("commands.q.quotient", "quotient"),
        ("commands.q.matrix", "matrix"),
        ("commands.q.cone", "cone"),
        ("commands.q.solve", "solve"),
        ("commands.q.parametric", "parametric"),
        ("commands.q.peak", "peak"),
        ("commands.q.entry", "entry"),
        ("commands.q.moment", "moment"),
        ("commands.q.ratio", "ratio"),
        ("commands.q.family", "family"),
        ("commands.q.exists", "exists"),
    )),
    ("commands.group.every", (
        ("commands.q.sweep", "sweep"),
        ("commands.q.cases", "cases"),
        ("commands.q.shrink", "shrink"),
        ("commands.q.witnesses", "sweep --witnesses"),
        ("commands.q.enum", "enum"),
    )),
    ("commands.group.algebra", (
        ("commands.q.ideal", "ideal"),
        ("commands.q.eliminate", "eliminate"),
        ("commands.q.sos", "sos"),
        ("commands.q.number", "number"),
        ("commands.q.cover", "cover"),
    )),
    ("commands.group.keep", (
        ("commands.q.synth", "synth"),
        ("commands.q.compose", "compose"),
        ("commands.q.verify", "verify"),
        ("commands.q.export", "export --lean"),
        ("commands.q.ledger", "ledger"),
    )),
)


def table() -> dict:
    """The routing table, translated, with the cost of re-checking attached."""
    groups = []
    for group, rows in BY_QUESTION:
        out = []
        for question, command in rows:
            base = command.split()[0]
            out.append({
                "question": _t(question),
                "command": command,
                "spec": SPEC_OF.get(base),
                "certificate_rechecks_without_a_solver": base in SOLVER_FREE,
            })
        groups.append({"group": _t(group), "rows": out})
    return {"header": _t("commands.header"), "groups": groups,
            "footer": _t("commands.footer")}


#: Spec types that ARE a question but arrive in a different shape: a packing
#: is a linear program once it is written out, a finite domain is a sweep. The
#: CLI has always converted these; the routing table had not, so `ask` refused
#: two of the most used spec types in the corpus.
ALSO = {"PackingSpec": "opt", "DomainSpec": "sweep",
        "ParametricSymmetrySpec": "reduce"}


def command_for(spec) -> str | None:
    """The command that runs this spec object, by its type.

    What `ask` routes on. A spec knows what it is, so the choice of command
    is not a choice -- which is the point: the friction was never the routing,
    it was having to know the routing.
    """
    name = type(spec).__name__
    for command, wants in SPEC_OF.items():
        if wants == name:
            return command
    return ALSO.get(name)


def prepared(spec):
    """The spec in the shape its runner wants.

    A `PackingSpec` becomes the linear program it describes; everything else
    is already what it is. Kept beside the routing rather than inside each
    caller, so `ask`, the MCP tool and the tests cannot disagree about it.
    """
    if type(spec).__name__ == "PackingSpec":
        return spec.to_lp()
    return spec


#: command -> (module, function). Only the commands `ask` can run with no
#: flags: a question that needs a mode -- which variable to eliminate, whether
#: to prove optimality -- is a question with a missing piece, and guessing the
#: piece would answer something else.
RUNNERS = {
    "prove": ("certo.engines.smt", "prove"),
    "check": ("certo.engines.smt", "check"),
    "core": ("certo.engines.smt", "core"),
    "farkas": ("certo.engines.farkas", "farkas"),
    "induct": ("certo.engines.induct", "induct"),
    "opt": ("certo.engines.lp", "opt"),
    "bisect": ("certo.engines.bisect", "bisect"),
    "bounds": ("certo.engines.bounds", "bounds"),
    "order": ("certo.engines.order", "order"),
    "parametric": ("certo.engines.algebra", "parametric"),
    "peak": ("certo.engines.algebra", "peak"),
    "entry": ("certo.engines.algebra", "entry"),
    "moment": ("certo.engines.algebra", "moment"),
    "ratio": ("certo.engines.algebra", "ratio"),
    "reduce": ("certo.engines.algebra", "reduce_symmetry"),
    "reduce_parametric": ("certo.engines.algebra", "reduce_parametric"),
    "matrix": ("certo.engines.algebra", "integer_matrix"),
    "solve": ("certo.engines.algebra", "linear_system"),
    "quotient": ("certo.engines.algebra", "equitable_quotient"),
    "cone": ("certo.engines.algebra", "toric_cone"),
    "family": ("certo.engines.algebra", "family_max"),
    # `CoverSpec` answers two questions: `cover` checks one you have, and
    # `exists` asks whether any does. `ask` takes the first as the default,
    # because "is this a cover" is the question somebody writing a CoverSpec
    # has already decided to ask; `exists` is a different question about the
    # same object and is asked by name.
    "cover": ("certo.engines.algebra", "cover"),
    "exists": ("certo.engines.algebra", "exists"),
    "ideal": ("certo.engines.algebra", "ideal"),
    "eliminate": ("certo.engines.algebra", "eliminate"),
    "sos": ("certo.engines.algebra", "sos"),
    "number": ("certo.engines.algebra", "number"),
    "sweep": ("certo.engines.graphsearch", "sweep"),
    "shrink": ("certo.engines.shrink", "shrink_domain"),
    "sweep_domain": ("certo.engines.domain", "sweep_domain"),
    "cases": ("certo.engines.sat", "cases"),
    "synth": ("certo.engines.cegis", "synth"),
}


def runner_for(spec):
    """The (command, callable) that answers this spec, or (command, None).

    `None` means the command exists but needs a decision `ask` will not make
    for you -- `mixed` without knowing whether you want optimality proved,
    `compose` over a proof rather than a question.
    """
    import importlib

    command = command_for(spec)
    if command is None:
        return None, None
    # One command, two engines underneath, twice over: a finite domain and a
    # family of graphs are both `sweep` to a reader, and one program and a
    # whole family are both `reduce`. Routing on the command alone would hand
    # a parametric spec to the single-instance engine, which is how `ask`
    # would quietly answer a weaker question than the one it was asked.
    name = type(spec).__name__
    key = command
    if command == "sweep" and name == "DomainSpec":
        key = "sweep_domain"
    elif command == "reduce" and name == "ParametricSymmetrySpec":
        key = "reduce_parametric"
    where = RUNNERS.get(key)
    if where is None:
        return command, None
    return command, getattr(importlib.import_module(where[0]), where[1])
