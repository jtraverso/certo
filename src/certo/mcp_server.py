"""MCP server: every command, exposed to the LLM directly.

Three design decisions that matter:

1. CERTIFICATES DO NOT COME BACK IN THE RESPONSE. A DIMACS file with its DRAT
   proof is tens of thousands of characters; putting that in the model's
   context throws the window away and buys nothing, because the model cannot
   verify it by reading it. They are written to disk and the path, kind and
   digest come back. To check one, there is `verify`.

2. SPECS ARE PYTHON AND THEY GET EXECUTED. That is inherent to the DSL. The
   server confines paths and generated files to the workspace, but it is not
   a sandbox: do not point it at third-party specs.

3. `dsl_guide` FIRST. The model cannot write a valid spec without seeing the
   shape. The guide is both a tool and a resource.

Tool names, parameters and descriptions are API surface, like the CLI command
names: they stay in English whatever --lang says. What follows the user's
language is the rendered output of each result.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer

from . import __version__
from .limits import Limits

INSTRUCTIONS = """\
certo: a laboratory for supporting mathematical proofs, with certificates.

ALWAYS start with `dsl_guide` if you are going to write a spec.

Every command returns a verdict and a certificate saved to disk. The
certificate does not travel in the response: use `verify` with the path you
are given.

Only `unsat` and `sat` are conclusive. `unknown_solver`, `timeout`,
`resource_exhausted` and `out_of_theory` all mean "no answer", each for a
different reason -- none of them means "does not exist".

Mind the scope: `synth` DISCOVERS over a bounded domain, it does not prove a
theorem; `sweep` and `cases` settle a FINITE CASE, not the general statement.

Specs are Python code and are executed when loaded.
"""

DSL_GUIDE = '''\
# The certo DSL

Python as the host language. A .py file with a `spec()` function returning one
of these objects. You can pass the file (`spec_path`) or the code itself
(`spec_source`).

## Spec -> prove / check / core / farkas
    import z3
    from certo import Spec
    def spec():
        a, b = z3.Reals("a b")
        s = Spec(title="optional")
        s.assume("a_pos", a > 0)      # NAMED hypotheses: core and farkas use them
        s.assume("b_pos", b > 0)
        s.claim((a + b) * (a + b) >= 4 * a * b)
        return s

    prove:  negate the claim, look for unsat. PROVED / REFUTED (with a
            counterexample). Z3, complete for real arithmetic: this is the
            tool that DECIDES.
    core:   MUS, which hypotheses are really needed.

    prove, core, farkas and compose all check for a VACUOUS proof: if the
    hypotheses contradict each other, every goal follows and the proof says
    nothing. The verdict stays PROVED -- it really is a proof -- but the
    response and the certificate both say so. Treat it as a bug in the spec.
    farkas: the same proof, but with the REASON attached -- non-negative
            rational multipliers that combine the hypotheses with the negated
            goal until everything cancels. Checked by adding fractions, no
            solver. A hypothesis with multiplier 0 is absent, so this says
            which ones the proof uses. This is Lean's `linarith`, and the
            response carries the tactic line to paste.
            farkas(nonlinear=True) is `nlinarith`: products and squares of the
            hypotheses are added first. HEURISTIC -- finding nothing does not
            mean the claim is false; that is what `prove` is for.

## IdealSpec / SOSSpec / NumberSpec -> ideal, sos, number (no SMT at all)
    from certo import IdealSpec, SOSSpec, NumberSpec
    IdealSpec(variables=["x","y"], equations=[x*x+y*y-1, x-y, x+y-3],
              claim=None)        # None: is the system INCONSISTENT?
    # Cofactors with 1 = sum h_i g_i refute it over C, hence over R, Q and Z.
    # With claim=f it certifies f = sum h_i g_i. Groebner DECIDES membership,
    # so a negative answer is conclusive, not a timeout. Checking a cofactor
    # certificate is expanding a product: no solver, no algebra system.

    SOSSpec(variables=["x","y"], poly=x**4 + y**4 - x**2*y**2)
    # p = sum d_i q_i^2, exact rationals. Searched in floating point, rounded
    # and re-verified exactly. NOT complete: a non-negative polynomial need
    # not be a sum of squares, so nothing found is unknown_solver.

    NumberSpec(n=2**31 - 1, question="prime")   # or "factor"
    # A Pratt tree. Checking it is modular exponentiation and nothing else.

## BoundSpec -> bounds (numbers, rigorously)
    from certo import BoundSpec
    def spec():
        return BoundSpec(
            value=lambda m: m.e / m.pi,      # m = RIGOROUS constants/functions
            claim=("<", "0.866"),            # against an EXACT rational string
            describe="e / pi",
            prec=64,                         # bits; it doubles until settled
        )
    # m: pi, e, euler, and exp log sqrt sin cos tan asin acos atan sinh cosh
    #    tanh gamma lgamma digamma zeta erf erfc. m("1/3") or m(7) builds a
    #    number EXACTLY; a Python float like 0.1 RAISES, because 0.1 is not
    #    one tenth and the enclosure would be rigorous about the wrong number.
    # claim: ("<", r) ("<=", r) (">", r) (">=", r) ("!=", r) ("in", lo, hi),
    #    or leave it out to MEASURE: the certificate records the enclosure.
    # An enclosure can never prove a quantity EQUALS something, only that it
    # differs; and resource_exhausted means "did not settle it", not "false".

## ProofSpec -> compose (the lemmas AND the join between them)
    import z3
    from certo import ProofSpec, Spec
    def spec():
        p = ProofSpec(title="the theorem")
        p.assume("n_ge_6", n >= 6)              # hypothesis of the THEOREM
        p.lemma("arith", proves=sub_spec)       # discharged now, by `prove`
        p.lemma("tight", proves=other, via="nlinarith")
        p.lemma("finite", certificate="certs/drat-1a2b.json",
                states=(R33 <= 6),              # what it licenses you to use
                bridge="the DRAT proof closes the K6 encoding; reading that "
                       "as R(3,3) <= 6 is what the encoding means")
        p.conclude(theorem)
        return p

    A lemma given by `proves=` is DISCHARGED and LINKED: compose checks that
    what its certificate closes entails the statement used downstream. If it
    does not, nothing is emitted -- that gap is the whole reason to compose
    rather than to keep certificates in a folder.

    A lemma given by `certificate=` is a BRIDGE: verified on its own, but the
    step from "this CNF is unsatisfiable" or "these 156 graphs all satisfy P"
    to a formula cannot be checked by anything. Declare it in `bridge=`; it is
    reported by name every time the proof is verified.

    The response also says which lemmas the theorem actually NEEDED.

## SynthSpec -> synth (CEGIS: THERE EXISTS obj, FOR ALL inputs)
    import z3
    from certo import SynthSpec
    def spec():
        a, b = z3.Ints("a b")             # what we are looking for
        x = z3.Int("x")                   # universally quantified
        return SynthSpec(
            impl_vars=[a, b], input_vars=[x], helper_vars=[],
            impl_constraints=z3.And(a >= 0, a <= 40, b >= 0, b <= 40),
            behavior=z3.And(x >= 1, x <= 20),   # BOUNDED search domain
            correctness=(a * x + b >= x * x),
            # For `synth(prove_candidate=True)`: the GENERAL statement. It
            # usually changes both the domain AND the sort (search over
            # bounded integers, prove over the reals, which is decidable).
            universal=lambda vals: Spec().claim(...),   # full control
            # or, the simple case:  universal_behavior=<expr replacing behavior>
        )

## InductSpec -> induct (base cases + a step, and the join between them)
    from certo import InductSpec, Spec
    k = z3.Int("k")
    def spec():
        step = Spec()
        step.assume("k_ge_3", k >= 3)        # a FREE k: valid for every k
        step.assume("P_k", <property at k>)
        step.claim(<property at k+1>)
        return InductSpec(k0=3, base_upto=8,
                          base=lambda j: <Spec|SweepSpec|DomainSpec|cert path>,
                          step=step, step_from=3,
                          bridge="how a finite check becomes P(k)")
    # Z3 has NO induction schema. The principle is applied by the tool and
    # recorded in the certificate; it is not a solver result. What is checked:
    # the base cases are exactly k0..base_upto with no gap, the step starts no
    # later than the base ends, and the step certificate really entails the
    # step statement. The first two are where induction proofs break.

## SetFamily -> the native combinatorial type (structures.py)
    from certo import SetFamily
    f = SetFamily(7, [(0,1,2), (0,3,4), ...])     # hypergraph, design, code...
    f.is_design(2, 1)  f.is_regular(3)  f.is_uniform(3)  f.intersecting()
    SetFamily.all_families(n, k, size)            # the domain to sweep
    # It supplies key(), canonical() and reductions() itself, so a DomainSpec
    # over these can leave key, canonicalize="auto" and reduce="auto".
    # canonical() is EXACT and RAISES on a family too symmetric to do exactly,
    # rather than returning a cheaper invariant that could merge two orbits.

## LPSpec -> opt, and `mixed` when some variables are discrete
    lp.variable("y", kind="binary")     # or kind="integer"
    lp.variable("q")                    # continuous, the default
    # `integer=True` on the SPEC makes every variable integer, which is the
    # wrong shape for a design whose discrete part chooses a structure and
    # whose continuous part packs inside it. Declare kinds per variable and
    # use `mixed`, which certifies the construction and says plainly that it
    # does not claim MILP optimality.

## LPSpec -> opt (the certificate is the DUAL)
    from certo import LPSpec
    def spec():
        lp = LPSpec(sense="max")          # variables >= 0, mandatory
        lp.variable("x"); lp.variable("y")
        lp.objective({"x": 3, "y": 5})
        lp.constraint({"x": 1, "y": 1}, "<=", 10, name="capacity")
        return lp

## CNF / CNFSpec -> cases (DRAT proof) and shrink (MUS)
    from itertools import combinations
    from certo import CNF, CNFSpec
    def spec():
        cnf = CNF(title="R(3,3) on K6")
        def x(i, j): return cnf.var("e%d_%d" % (min(i,j), max(i,j)))
        for t in combinations(range(6), 3):
            a, b, c = x(t[0],t[1]), x(t[0],t[2]), x(t[1],t[2])
            cnf.add(-a, -b, -c); cnf.add(a, b, c)
        return CNFSpec(cnf=cnf)
    # helpers: cnf.at_most_one(lits), cnf.exactly_one(lits), cnf.lex_leq(xs, ys),
    #          cnf.break_vertex_symmetry(edge_var_fn, n)

## SweepSpec -> sweep (predicate over a whole family) and shrink (minimise)
    from certo import Outcome, SweepSpec
    from certo.graphs import is_chordal
    def spec():
        return SweepSpec(n=6, filters=["connected"], predicate=is_chordal)

    # A BARE BOOL predicate makes the sweep REPRODUCIBLE, not certified: the
    # certificate records the verdict vector so `verify` can re-run the
    # predicate and confirm it answers the same, which is NOT the same as
    # establishing those answers are right. `predicate_level` in the response
    # says which of the three you got: certified / reproducible / recorded.
    # The predicate may return an Outcome instead of a bool:
    #   Outcome(ok=False, cert=<Certificate>, detail="...", value=Fraction(25,27))
    #   ok=None  -> inconclusive (counted apart, does not sink the sweep)
    #   cert=... -> makes the sweep CITABLE; verify checks them in cascade
    #   value=...-> the magnitude to calibrate
    # CALIBRATION: SweepSpec(n=6, collect=lambda g: ratio(g), worst="min")
    # returns min, max, mean and the extremes WITH their graph. `predicate` is
    # optional: you can measure without refuting anything. Use Fraction so the
    # statistics stay exact.
    # filters: connected, chordal, triangle_free, k4_free, regular,
    #          has_triangle, min_degree=K, max_degree=K, edges=K
    #          (a callable of your own works too)
    # Graph: .n .m .edges() .neighbors(v) .degree(v) .has_edge(i,j) .to_graph6()

## DomainSpec -> sweep and shrink over ANY finite domain
    from certo import DomainSpec
    def spec():
        return DomainSpec(
            items=[(s, r) for s in range(2, 8) for r in range(2, 8)],
            predicate=lambda p: holds(*p),
            key=lambda p: "s=%d,r=%d" % p,       # stable id for the certificate
            reduce="auto",                       # or a callable, for shrink
            canonicalize=lambda p: tuple(sorted(p)),   # the symmetry, optional
        )
    # With `canonicalize`, a REFUTED sweep reports labelled count, orbit count
    # and a representative per orbit -- 1400 counterexamples that are four
    # objects relabelled is one answer told 1400 times. Every item is still
    # evaluated; the quotient happens on the way out.
    # reduce: "auto" | sets | sequences | decrement | graphs | masks, or your
    # own. "auto" refuses on a type it does not know rather than inventing a
    # reduction that would make a witness minimal for the wrong relation.

## BisectSpec -> bisect (a constant's threshold)
    from certo import BisectSpec
    def spec():
        def build(t):                     # returns a Spec or a CNFSpec
            ...
        return BisectSpec(build=build, lo=0, hi=10, direction="min_true",
                          integer=False, tol=1e-6)
    # direction="min_true": holds for LARGE t -> look for the smallest t.
    # With a CNFSpec, "holds" = UNSAT = no counterexample exists.
    # ASSUMES MONOTONICITY in t. It checks the endpoints and warns if they
    # do not line up.

## Limits (every command)
    timeout_ms, rlimit (z3's deterministic work unit), conflict_budget (SAT),
    max_iterations (synth). Determinism comes from rlimit/conflict_budget,
    not from the clock.
'''


# ---------------------------------------------------------------------------
# workspace
# ---------------------------------------------------------------------------


def _workspace() -> Path:
    p = Path(os.environ.get("CERTO_WORKSPACE", Path.cwd())).resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / "certs").mkdir(exist_ok=True)
    (p / "specs").mkdir(exist_ok=True)
    return p


def _resolve(path: str) -> Path:
    """Confine the path inside the workspace."""
    ws = _workspace()
    p = (ws / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if ws not in p.parents and p != ws:
        raise ValueError(
            "path outside the workspace ({}): {}".format(ws, path))
    return p


def _spec_file(spec_path: str | None, spec_source: str | None) -> Path:
    if (spec_path is None) == (spec_source is None):
        raise ValueError("give exactly one: spec_path or spec_source")
    if spec_path is not None:
        p = _resolve(spec_path)
        if not p.exists():
            raise FileNotFoundError("spec file does not exist: " + str(p))
        return p
    digest = hashlib.sha256(spec_source.encode()).hexdigest()[:12]
    p = _workspace() / "specs" / "inline_{}.py".format(digest)
    p.write_text(spec_source, encoding="utf-8")
    return p


def _limits(timeout_ms=10_000, rlimit=20_000_000, conflict_budget=1_000_000,
            max_iterations=10_000) -> Limits:
    return Limits(timeout_ms=timeout_ms, rlimit=rlimit,
                  conflict_budget=conflict_budget, max_iterations=max_iterations)


# ---------------------------------------------------------------------------
# summary: what DOES come back to the model
# ---------------------------------------------------------------------------

_CAP = 10
_BIG = ("trace", "counterexamples", "graph6", "witness", "solution",
        "blocked", "errors", "describe")


def _trim(meta: dict) -> dict:
    out = {}
    for k, v in meta.items():
        if k == "solution" and isinstance(v, dict):
            nz = {a: b for a, b in v.items() if b}
            out[k] = dict(list(nz.items())[:_CAP])
            if len(nz) > _CAP:
                out[k + "_omitted"] = len(nz) - _CAP
        elif k in _BIG and isinstance(v, (list, dict)):
            items = list(v.items()) if isinstance(v, dict) else v
            out[k] = dict(items[:_CAP]) if isinstance(v, dict) else items[:_CAP]
            if len(items) > _CAP:
                out[k + "_omitted"] = len(items) - _CAP
        elif k == "proof_check" and isinstance(v, dict):
            out[k] = {c: {"ok": r.get("ok"), "detail": r.get("detail")}
                      for c, r in v.items()}
        else:
            out[k] = v
    return out


def _emit(res, save_cert: bool = True, spec_file=None) -> dict:
    """Render a Result for the model, stamping provenance on the way out.

    Stamping here rather than in each tool: without it a certificate produced
    over MCP carries no spec path, so `ledger verify` cannot find what made it
    and a sweep cannot be replayed -- it silently drops from `reproducible` to
    `recorded` between the run and its own verification.
    """
    if spec_file is not None and res.certificate is not None:
        res.certificate.stamp(spec_file)
    out: dict[str, Any] = {
        "command": res.command,
        "verdict": res.verdict.value,
        "status": res.status.value,
        "conclusive": res.status.conclusive,
        "detail": res.detail,
        "engine": res.engine,
        "elapsed_ms": round(res.elapsed_ms, 1),
        "meta": _trim(res.meta),
    }
    # A vacuous proof looks exactly like a good one in a summary, so it does
    # not get to hide inside `meta`.
    if res.meta.get("vacuous"):
        out["vacuous"] = True
    # Same reason: a sweep that establishes nothing about its predicate must
    # not summarise as a plain PROVED.
    if res.meta.get("level"):
        out["predicate_level"] = res.meta["level"]
    if res.certificate is None:
        out["certificate"] = None
        out["certificate_note"] = "no certificate: nothing to audit here"
        return out
    c = res.certificate
    info = {"kind": c.kind, "solver_free": c.solver_free,
            "digest": c.digest(), "note": c.note}
    if save_cert:
        p = _workspace() / "certs" / "{}-{}.json".format(res.command, c.digest())
        p.write_text(json.dumps(c.to_dict(), indent=2, ensure_ascii=False),
                     encoding="utf-8")
        info["path"] = str(p.relative_to(_workspace())).replace("\\", "/")
        info["verify_with"] = "verify(certificate_path='{}')".format(info["path"])
    out["certificate"] = info
    return out


_HINTS = (
    ("does not define a spec",
     "your file must define `def spec():` returning one of the DSL objects"),
    ("expected",
     "you are calling the wrong command for that spec type; see dsl_guide"),
    ("needs",
     "you are calling the wrong command for that spec type; see dsl_guide"),
    ("outside the workspace",
     "paths are relative to the workspace and cannot escape it"),
    ("spec file does not exist",
     "write the file first, or pass the code in spec_source"),
    ("exactly one",
     "give spec_path OR spec_source, not both and not neither"),
    ("unknown filter",
     "valid filters: connected, chordal, triangle_free, k4_free, regular, "
     "has_triangle, min_degree=K, max_degree=K, edges=K"),
    ("negative lower bound",
     "the dual certificate requires variables >= 0; reformulate the LP"),
    ("universal obligation",
     "add universal= or universal_behavior= to the SynthSpec; see dsl_guide"),
)


def _emit_f(f, res):
    """`_emit` with the spec file, for the tools that return in one line."""
    return _emit(res, spec_file=f)


def _hint(e: Exception) -> str:
    msg = str(e).lower()
    for needle, hint in _HINTS:
        if needle in msg:
            return hint
    if isinstance(e, (SyntaxError, NameError, ImportError)):
        return "your spec does not even run; check dsl_guide and the imports"
    return "see dsl_guide"


def _guard(fn):
    """Return the error as data, not as an exception.

    The SDK turns any exception into "Error executing tool X" and swallows the
    reason; a model reading that cannot fix its spec. This way it sees what
    happened and what to correct.
    """
    @functools.wraps(fn)
    async def wrapper(*a, **kw):
        try:
            return await fn(*a, **kw)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error_type": type(e).__name__,
                    "error": str(e), "hint": _hint(e)}

    return wrapper


async def _off(fn, *a, **kw):
    """Off the protocol thread: solving can take a while."""
    return await anyio.to_thread.run_sync(lambda: fn(*a, **kw))


# ---------------------------------------------------------------------------
# servidor
# ---------------------------------------------------------------------------

mcp = MCPServer(name="certo", version=__version__, instructions=INSTRUCTIONS)


@mcp.resource("certo://dsl", mime_type="text/markdown",
              description="certo DSL reference")
def dsl_resource() -> str:
    return DSL_GUIDE


@mcp.tool(description="DSL reference. Read this BEFORE writing a spec.")
def dsl_guide() -> str:
    return DSL_GUIDE


def _spec_tool(engine_call, expected=None):
    async def run(spec_path=None, spec_source=None, timeout_ms=10_000,
                  rlimit=20_000_000, **kw):
        from .spec import load_spec

        f = _spec_file(spec_path, spec_source)
        obj = await _off(load_spec, f, expected)
        lim = _limits(timeout_ms, rlimit, kw.pop("conflict_budget", 1_000_000),
                      kw.pop("max_iterations", 10_000))
        return _emit_f(f, await _off(engine_call, obj, lim, **kw))

    return run


@mcp.tool(description=(
    "Prove the claim of a Spec: negate it and look for unsat. Returns PROVED "
    "with the unsat core (which hypotheses were used), or REFUTED with a "
    "counterexample that verifies without a solver."))
@_guard
async def prove(spec_path: str | None = None, spec_source: str | None = None,
                timeout_ms: int = 10_000, rlimit: int = 20_000_000) -> dict:
    from .engines import smt
    from .spec import Spec

    return await _spec_tool(smt.prove, Spec)(spec_path, spec_source,
                                             timeout_ms, rlimit)


@mcp.tool(description=(
    "Satisfiability of a Spec's hypotheses plus claim. SAT returns a model; "
    "UNSAT returns the core that explains it."))
@_guard
async def check(spec_path: str | None = None, spec_source: str | None = None,
                timeout_ms: int = 10_000, rlimit: int = 20_000_000) -> dict:
    from .engines import smt
    from .spec import Spec

    return await _spec_tool(smt.check, Spec)(spec_path, spec_source,
                                             timeout_ms, rlimit)


@mcp.tool(description=(
    "MUS over a Spec's hypotheses: which are actually needed and which are "
    "redundant. This is the tool for simplifying a proof. Given a MultiSpec "
    "it returns the hypothesis-by-goal TABLE instead: which hypotheses each "
    "goal needs, which is what decides how small a Lean interface can be."))
@_guard
async def core(spec_path: str | None = None, spec_source: str | None = None,
               timeout_ms: int = 10_000, rlimit: int = 20_000_000) -> dict:
    from .engines import smt
    from .spec import MultiSpec, Spec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f)
    lim = _limits(timeout_ms, rlimit)

    if isinstance(sp, MultiSpec):
        res = await _off(smt.core_matrix, sp, lim)
        out = _emit(res, spec_file=f)
        out["table"] = res.meta.get("table")
        out["never_used"] = res.meta.get("never_used")
        return out
    if not isinstance(sp, Spec):
        raise TypeError("core needs a Spec or a MultiSpec; spec() returned "
                        + type(sp).__name__)
    return _emit_f(f, await _off(smt.core, sp, lim))


@mcp.tool(description=(
    "Settle a NUMERIC inequality rigorously: e, pi, log, gamma, zeta and "
    "friends, with interval/ball arithmetic. Every operation returns an "
    "enclosure that provably contains the true value, so an inequality that "
    "holds for the whole enclosure holds for the number -- which is what a "
    "float computation can never claim. The enclosure comes back as EXACT "
    "rationals. Precision is the work budget: it doubles until the enclosure "
    "settles the claim, and running out is reported as resource_exhausted, "
    "meaning THIS DID NOT SETTLE IT, never 'it is false'. Use it whenever a "
    "proof needs 'this constant is below 0.4' and the constant is not "
    "algebraic; `prove` and `farkas` cannot see transcendental functions at "
    "all. Python floats in the expression are REFUSED, because a float is not "
    "the decimal it is written as."))
@_guard
async def bounds(spec_path: str | None = None, spec_source: str | None = None,
                 timeout_ms: int = 30_000, prec: int = 0,
                 max_prec: int = 0) -> dict:
    from .engines import bounds as bd
    from .spec import BoundSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, BoundSpec)
    if prec:
        sp.prec = prec
    if max_prec:
        sp.max_prec = max_prec
    res = await _off(bd.bounds, sp, _limits(timeout_ms), str(f))
    out = _emit(res, spec_file=f)
    for k in ("lo", "hi", "width", "prec", "backend"):
        out[k] = res.meta.get(k)
    return out


@mcp.tool(description=(
    "A MIXED design: a discrete skeleton found by search, with the continuous "
    "part certified exactly. This is NOT MILP optimality and does not claim "
    "to be. CBC chooses the discrete structure (uncertified); the assignment "
    "is then rounded and CHECKED exactly, the residual LP over the continuous "
    "variables is solved with an exact rational dual, and every original "
    "constraint is re-checked at the full point. Use it for EXISTENCE proofs, "
    "where exhibiting a construction that reaches a target is the whole job. "
    "The spec declares kinds per variable: lp.variable('y', kind='binary') "
    "next to lp.variable('q'). Three numbers come back and they differ: what "
    "the design achieves, the conditional optimum given that skeleton, and "
    "the relaxation bound over all skeletons -- and if the first meets the "
    "third, global optimality is certified for free."))
@_guard
async def mixed(spec_path: str | None = None, spec_source: str | None = None,
                target: str | None = None, timeout_ms: int = 120_000) -> dict:
    from .engines import mixed as mx
    from .spec import LPSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, LPSpec)
    res = await _off(mx.mixed, sp, _limits(timeout_ms), str(f),
                     target if target is not None else sp.target)
    out = _emit(res, spec_file=f)
    for k in ("achieved", "conditional", "bound", "target", "deficit",
              "globally_optimal", "selected"):
        out[k] = res.meta.get(k)
    return out


@mcp.tool(description=(
    "POLYNOMIAL equations, decided algebraically -- no SMT involved. With "
    "claim=None it asks whether the system is INCONSISTENT and returns "
    "cofactors h_i with 1 = sum h_i g_i, which refutes it over the COMPLEX "
    "numbers and hence over the reals, rationals and integers. With a claim f "
    "it certifies f = sum h_i g_i, i.e. f vanishes on every common root. "
    "Finding the cofactors is a Groebner basis computation; CHECKING them is "
    "expanding a product in exact rationals, so the certificate needs neither "
    "a solver nor an algebra system. Groebner DECIDES membership: a negative "
    "answer is conclusive, not a timeout. Reach for this when `prove` is "
    "grinding on polynomial equalities."))
@_guard
async def ideal(spec_path: str | None = None, spec_source: str | None = None,
                timeout_ms: int = 60_000) -> dict:
    from .engines import algebra
    from .spec import IdealSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, IdealSpec)
    res = await _off(algebra.ideal, sp, _limits(timeout_ms), str(f))
    out = _emit(res, spec_file=f)
    out["cofactors"] = res.meta.get("cofactors")
    return out


@mcp.tool(description=(
    "Certify a polynomial NON-NEGATIVE everywhere as an exact sum of squares: "
    "p = sum d_i q_i^2 with rational d_i and rational linear forms. The Gram "
    "matrix is searched for in floating point and never reaches the "
    "certificate -- it is rounded, re-projected and re-verified in exact "
    "rationals, the same way `opt` reconstructs its dual. INCOMPLETE on "
    "purpose: from degree 4 in 3 variables there are non-negative polynomials "
    "that are not sums of squares (Motzkin), so finding nothing is "
    "unknown_solver and NEVER 'it goes negative'. For degree 2, `farkas "
    "--nonlinear` is cheaper."))
@_guard
async def sos(spec_path: str | None = None, spec_source: str | None = None,
              timeout_ms: int = 60_000) -> dict:
    from .engines import algebra
    from .spec import SOSSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, SOSSpec)
    res = await _off(algebra.sos, sp, _limits(timeout_ms), str(f))
    out = _emit(res, spec_file=f)
    out["squares"] = res.meta.get("squares")
    return out


@mcp.tool(description=(
    "PRIMALITY with a certificate, or a factorisation whose factors carry "
    "one. `n.is_prime()` is true, fast and unciteable; a Pratt certificate is "
    "the same fact with the evidence: a witness generating (Z/n)^*, plus a "
    "certificate for each prime factor of n-1, recursively down to 2. "
    "Checking the whole tree is modular exponentiation and nothing else. A "
    "composite n comes back REFUTED, which is a real answer rather than a "
    "failure to find one."))
@_guard
async def number(n: int, question: str = "prime",
                 timeout_ms: int = 60_000) -> dict:
    from .engines import algebra
    from .spec import NumberSpec

    res = await _off(algebra.number, NumberSpec(n=n, question=question),
                     _limits(timeout_ms), "")
    out = _emit(res)
    for k in ("witness", "factors", "checks", "nodes", "depth"):
        if res.meta.get(k) is not None:
            out[k] = res.meta[k]
    return out


@mcp.tool(description=(
    "Finite base cases plus an inductive step, chained by INDUCTION, with the "
    "join checked. Z3 has no induction schema: the principle is applied by "
    "this tool and the certificate's structure is the application -- it is "
    "recorded, not verified by a solver. What IS checked is the part that "
    "goes wrong: the base cases are exactly k0..base_upto with no gap, the "
    "step starts no later than the base ends, the step is proved with the "
    "index FREE (so universally valid), and every base case has its own "
    "certificate. A base covering 3..8 with a step valid only from k>=10 "
    "proves nothing about 9, and reads identically in prose."))
@_guard
async def induct(spec_path: str | None = None, spec_source: str | None = None,
                 timeout_ms: int = 60_000) -> dict:
    from .engines import induct as ind
    from .spec import InductSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, InductSpec)
    res = await _off(ind.induct, sp, _limits(timeout_ms), str(f))
    out = _emit(res, spec_file=f)
    for k in ("base_cases", "step_from", "bridges"):
        out[k] = res.meta.get(k)
    return out


@mcp.tool(description=(
    "Assemble lemmas and their certificates into ONE proof, with the join "
    "between them checked. Every other tool produces a leaf; this produces "
    "the proof. For each lemma discharged here it verifies the LINK -- that "
    "what the lemma's certificate actually closes entails the statement used "
    "downstream -- which is where hand-assembled arguments break (a lemma "
    "proved under one hypothesis, used under another). A lemma supplied as a "
    "stored certificate instead (a sweep, a DRAT proof) is a BRIDGE: verified "
    "on its own, but the step to a first-order formula is a modelling "
    "decision, so it is recorded by name and reported on every verification. "
    "The response says which lemmas the theorem needed and which it did not."))
@_guard
async def compose(spec_path: str | None = None, spec_source: str | None = None,
                  timeout_ms: int = 60_000) -> dict:
    from .engines import compose as cp
    from .spec import ProofSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, ProofSpec)
    res = await _off(cp.compose, sp, _limits(timeout_ms), str(f), _workspace())
    out = _emit(res, spec_file=f)
    for k in ("lemmas", "used", "unused", "bridges"):
        out[k] = res.meta.get(k)
    return out


@mcp.tool(description=(
    "linarith/nlinarith with the certificate attached: non-negative rational "
    "multipliers that combine the hypotheses with the negated goal until "
    "everything cancels and what is left is false. Checked by adding "
    "fractions, no solver. Hypotheses with multiplier 0 are absent, so this "
    "also says which ones the proof really uses. nonlinear=true is nlinarith: "
    "products and squares of the hypotheses are added first, which is a "
    "HEURISTIC -- finding nothing does NOT mean the claim is false, and "
    "`prove` (Z3 nlsat, complete for real arithmetic) is the tool that "
    "decides. The response carries the Lean tactic line this corresponds to."))
@_guard
async def farkas(spec_path: str | None = None, spec_source: str | None = None,
                 timeout_ms: int = 20_000, nonlinear: bool = False) -> dict:
    from .engines import farkas as fk
    from .spec import Spec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, Spec)
    res = await _off(fk.farkas, sp, _limits(timeout_ms), nonlinear, str(f))
    out = _emit(res, spec_file=f)
    out["multipliers"] = res.meta.get("multipliers")
    out["lean"] = res.meta.get("hint")
    return out


@mcp.tool(description=(
    "CEGIS over a SynthSpec: THERE EXISTS an object such that FOR ALL inputs "
    "of the BOUNDED domain. Returns the object found and the counterexamples "
    "that forced it. CAREFUL: this is a bounded DISCOVERY, not a theorem. "
    "With prove_candidate=True it fixes the object and additionally proves "
    "the universal statement (the spec must supply universal= or "
    "universal_behavior=)."))
@_guard
async def synth(spec_path: str | None = None, spec_source: str | None = None,
                timeout_ms: int = 10_000, max_iterations: int = 10_000,
                prove_candidate: bool = False) -> dict:
    from .certificate import synth_proved_certificate
    from .engines import cegis
    from .spec import SynthSpec, load_spec
    from .status import Verdict

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f, SynthSpec)
    lim = _limits(timeout_ms, max_iterations=max_iterations)
    res = await _off(cegis.synth, sp, lim)

    if not prove_candidate or res.verdict is not Verdict.PROVED:
        out = _emit(res, spec_file=f)
        out["scope"] = ("BOUNDED synthesis: the object holds in the spec's "
                        "domain; this is not a theorem")
        return out

    uni = await _off(cegis.prove_candidate, sp,
                     res.certificate.payload["implementation"], lim)
    combo = synth_proved_certificate(
        candidate=res.meta.get("implementation"),
        synth_cert=res.certificate.to_dict(),
        universal_cert=uni.certificate.to_dict() if uni.certificate else None,
    ).stamp(f)
    res.certificate = combo
    out = _emit(res, spec_file=f)
    out["candidate"] = res.meta.get("implementation")
    out["universal_proof"] = {"verdict": uni.verdict.value,
                              "status": uni.status.value, "detail": uni.detail}
    out["scope"] = ("UNIVERSAL PROOF: PASS" if uni.verdict is Verdict.PROVED
                    else "the candidate does NOT generalise: " + uni.detail)
    return out


@mcp.tool(description=(
    "Solve an LPSpec (LP or ILP). The certificate is the DUAL, checked with "
    "pure EXACT rational arithmetic. For an ILP the dual certifies the "
    "relaxation bound, not integer optimality."))
@_guard
async def opt(spec_path: str | None = None, spec_source: str | None = None,
              timeout_ms: int = 10_000, by_type: bool = False) -> dict:
    from .engines import lp
    from .packing import PackingSpec
    from .spec import LPSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f)
    if isinstance(sp, PackingSpec):
        packing, sp = sp, sp.to_lp()
    elif isinstance(sp, LPSpec):
        packing = None
    else:
        raise TypeError("opt needs an LPSpec or a PackingSpec; spec() returned "
                        + type(sp).__name__)

    res = await _off(lp.opt, sp, _limits(timeout_ms))
    out = _emit(res, spec_file=f)
    if packing is not None:
        from .packing import loads_from_dual

        out["loads"] = dict(list(loads_from_dual(res.certificate).items())[:_CAP])
        if by_type:
            out["by_type"] = {}
            for kind in packing.kinds:
                sub = await _off(lp.opt, packing.restricted({kind}).to_lp(),
                                 _limits(timeout_ms))
                out["by_type"][kind] = sub.meta.get("objective")
    return out


@mcp.tool(description=(
    "SAT over a CNFSpec with a verified DRAT proof. UNSAT with a proof is a "
    "citable FINITE CASE -- not the general theorem: it is checked without "
    "running any code and without trusting the solver. SAT returns the witness."))
@_guard
async def cases(spec_path: str | None = None, spec_source: str | None = None,
                timeout_ms: int = 10_000, conflict_budget: int = 1_000_000,
                solver: str = "internal") -> dict:
    from .cnf import CNF, CNFSpec
    from .engines import sat
    from .spec import load_spec

    f = _spec_file(spec_path, spec_source)
    obj = await _off(load_spec, f)
    if not isinstance(obj, (CNF, CNFSpec)):
        raise TypeError("cases needs a CNF or CNFSpec; spec() returned "
                        + type(obj).__name__)
    s = obj if isinstance(obj, CNFSpec) else CNFSpec(cnf=obj, title=obj.title)
    lim = _limits(timeout_ms, conflict_budget=conflict_budget)
    return _emit_f(f, await _off(sat.cases, s, lim, solver))


@mcp.tool(description=(
    "Enumerate every graph on n vertices up to isomorphism, filtered. "
    "Filters: connected, chordal, triangle_free, k4_free, regular, "
    "has_triangle, min_degree=K, max_degree=K, edges=K. n<=8 without nauty."))
@_guard
async def enum(n: int, filters: list[str] | None = None,
               timeout_ms: int = 60_000) -> dict:
    from .engines import graphsearch

    # No spec here: enum takes n and filters directly, so there is no file
    # to stamp against.
    res = await _off(graphsearch.enum, n, filters or [], _limits(timeout_ms))
    out = _emit(res)
    g6 = res.certificate.payload["graph6"] if res.certificate else []
    out["graphs_sample"] = g6[:_CAP]
    out["graphs_total"] = len(g6)
    return out


@mcp.tool(description=(
    "Run a SweepSpec's predicate over the whole enumerated family. PROVED "
    "settles the FINITE CASE, not the theorem. REFUTED lists counterexamples; "
    "pass them to `shrink` to minimise them. If the spec sets `collect`, the "
    "response also carries min/max/mean and the extremes with their graph. "
    "With n_range=\"4..8\" it sweeps every size and reports the first one that "
    "fails; stop_on_first stops there. Also accepts a DomainSpec for any "
    "finite domain, not just graphs."))
@_guard
async def sweep(spec_path: str | None = None, spec_source: str | None = None,
                by_orbit: bool = False,
                timeout_ms: int = 60_000, cert_mode: str = "failures",
                n_range: str | None = None,
                stop_on_first: bool = False) -> dict:
    from .engines import domain, graphsearch
    from .spec import DomainSpec, SweepSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    sp = await _off(load_spec, f)
    if n_range:
        if not isinstance(sp, SweepSpec):
            raise TypeError("n_range only applies to a SweepSpec")
        try:
            lo, hi = (int(x) for x in n_range.split(".."))
        except ValueError:
            raise ValueError("n_range expects LO..HI, for example 4..8")
        res = await _off(graphsearch.sweep_range, sp, lo, hi,
                         _limits(timeout_ms), stop_on_first, cert_mode)
    elif isinstance(sp, DomainSpec):
        res = await _off(domain.sweep_domain, sp, _limits(timeout_ms),
                         cert_mode, by_orbit)
    elif isinstance(sp, SweepSpec):
        res = await _off(graphsearch.sweep, sp, _limits(timeout_ms), True,
                         cert_mode)
    else:
        raise TypeError("sweep needs a SweepSpec (graphs) or a DomainSpec "
                        "(any finite domain); spec() returned "
                        + type(sp).__name__)
    out = _emit(res, spec_file=f)
    if res.meta.get("calibration"):
        out["calibration"] = res.meta["calibration"]
    return out


@mcp.tool(description=(
    "Minimise a counterexample. With a SweepSpec it reduces a graph (deleting "
    "vertices and edges); with a CNFSpec it extracts a MUS. The result is "
    "1-MINIMAL, not minimum: no ONE-step reduction is still a counterexample."))
@_guard
async def shrink(spec_path: str | None = None, spec_source: str | None = None,
                 graph: str | None = None, timeout_ms: int = 60_000,
                 keep_filters: bool = True) -> dict:
    from .cnf import CNF, CNFSpec
    from .engines import graphsearch, shrink as shr
    from .graphs import Graph
    from .spec import SweepSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    obj = await _off(load_spec, f)
    lim = _limits(timeout_ms)

    if isinstance(obj, (CNF, CNFSpec)):
        s = obj if isinstance(obj, CNFSpec) else CNFSpec(cnf=obj, title=obj.title)
        return _emit_f(f, await _off(shr.shrink_cnf, s, lim))

    if not isinstance(obj, SweepSpec):
        raise TypeError("shrink needs a SweepSpec or CNFSpec; spec() returned "
                        + type(obj).__name__)

    if graph:
        start = Graph.from_graph6(graph)
    else:
        sw = await _off(graphsearch.sweep, obj, lim)
        ces = sw.meta.get("counterexamples", [])
        if not ces:
            return {"command": "shrink", "verdict": "inconclusive",
                    "detail": "the sweep found no counterexample to minimise",
                    "meta": _trim(sw.meta), "certificate": None}
        start = Graph.from_graph6(ces[0])

    return _emit_f(f, await _off(shr.shrink_graph, obj, start, lim,
                            str(f), keep_filters))


@mcp.tool(description=(
    "Certified bisection over a BisectSpec: find a constant's threshold. The "
    "certificate is the PAIR that brackets it (a proof on the good side, a "
    "refutation on the bad one). ASSUMES MONOTONICITY in the parameter."))
@_guard
async def bisect(spec_path: str | None = None, spec_source: str | None = None,
                 timeout_ms: int = 60_000) -> dict:
    from .engines import bisect as bis
    from .spec import BisectSpec

    return await _spec_tool(bis.bisect, BisectSpec)(
        spec_path, spec_source, timeout_ms)


@mcp.tool(description=(
    "Audit ledger: 'list' shows what was run, 'verify' re-reads every "
    "certificate the log points at and re-verifies it. A certificate that "
    "changed since it was logged comes back as 'changed', which is different "
    "from failing verification. Append to it by passing log=true to a command."))
@_guard
async def ledger(action: str = "list", file: str | None = None,
                 limit: int = 20, timeout_ms: int = 60_000) -> dict:
    from . import ledger as _ledger

    path = _resolve(file) if file else (_workspace() / _ledger.DEFAULT_NAME)
    if action == "list":
        rows = _ledger.read(path)
        return {"path": str(path), "total": len(rows), "entries": rows[-limit:]}
    if action == "verify":
        rep = _ledger.verify_all(path, _limits(timeout_ms))
        rep["path"] = str(path)
        rep["rows"] = rep["rows"][-limit:]
        return rep
    raise ValueError("action must be 'list' or 'verify'")


@mcp.tool(description=(
    "Re-verify a stored certificate. Those marked solver_free are checked "
    "without any solver: arithmetic, evaluation or unit propagation. ALWAYS "
    "use this before taking a result as settled."))
@_guard
async def verify(certificate_path: str, timeout_ms: int = 60_000) -> dict:
    from .certificate import Certificate
    from .certificate import verify as vc

    p = _resolve(certificate_path)
    cert = Certificate.from_dict(json.loads(p.read_text(encoding="utf-8")))
    rep = await _off(vc, cert, _limits(timeout_ms))
    # rep.to_dict() and not a hand-built subset: this used to drop `warnings`,
    # which is where every "this says less than it looks like" lives -- a
    # bridge that is asserted rather than derived, a vacuous proof, a sweep
    # whose predicate nothing certified. An ok=True with those removed is the
    # overclaim this tool exists to prevent.
    return rep.to_dict()


@mcp.tool(description=(
    "Export a graph counterexample as Lean 4 DATA plus a skeleton, read from "
    "a stored shrink/sweep/graph_set certificate or from a graph6 string. "
    "Compiles against Lean/Mathlib v4.28.0 (including its `decide` sanity "
    "checks); another version may need adjusting. The edge list is exact "
    "either way."))
@_guard
async def export_lean(certificate_path: str | None = None,
                      graph: str | None = None) -> dict:
    from . import lean
    from .certificate import Certificate
    from .graphs import Graph

    if graph:
        graphs, source = [Graph.from_graph6(graph)], "graph6 " + graph
    elif certificate_path:
        p = _resolve(certificate_path)
        data = json.loads(p.read_text(encoding="utf-8"))
        graphs = lean.graphs_from_certificate(data)
        source = "{} (certificate {})".format(
            certificate_path, Certificate.from_dict(data).digest())
    else:
        raise ValueError("give exactly one: certificate_path or graph")

    text = lean.graphs_to_lean(graphs, source)
    out = _workspace() / "certs" / "lean_{}.lean".format(
        hashlib.sha256(text.encode()).hexdigest()[:12])
    out.write_text(text, encoding="utf-8")
    return {"graphs": len(graphs),
            "path": str(out.relative_to(_workspace())).replace("\\", "/"),
            "compiled": False,
            "warning": "checked against Lean/Mathlib v4.28.0; another version "
                       "may need adjusting. The edge list is exact either way."}


@mcp.tool(description=(
    "Dump a spec to its textual form: SMT-LIB2 for Spec/SynthSpec, DIMACS "
    "for CNF. Useful for archiving or handing to another tool."))
@_guard
async def export(spec_path: str | None = None, spec_source: str | None = None,
                 negate_goal: bool = False, max_chars: int = 4000) -> dict:
    import z3

    from . import z3util
    from .cnf import CNF, CNFSpec
    from .spec import Spec, SynthSpec, load_spec

    f = _spec_file(spec_path, spec_source)
    obj = await _off(load_spec, f)

    if isinstance(obj, (CNF, CNFSpec)):
        text = (obj.cnf if isinstance(obj, CNFSpec) else obj).to_dimacs()
        fmt = "dimacs"
    elif isinstance(obj, Spec):
        parts = list(obj.formulas)
        if obj.goal is not None:
            parts.append(z3.Not(obj.goal) if negate_goal else obj.goal)
        text, fmt = z3util.smt2(*parts), "smt2"
    elif isinstance(obj, SynthSpec):
        impl, behav, corr = obj.normalized()
        text = "\n".join("; ---- {} ----\n{}".format(n, z3util.smt2(e))
                         for n, e in (("impl", impl), ("behavior", behav),
                                      ("correctness", corr)))
        fmt = "smt2"
    else:
        raise TypeError("export does not support " + type(obj).__name__)

    out = {"format": fmt, "chars": len(text), "truncated": len(text) > max_chars}
    out["text"] = text[:max_chars]
    return out


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
