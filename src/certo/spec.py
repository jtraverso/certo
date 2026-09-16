"""The input DSL: Python as the host language.

Design decision: we do not invent a language. A .py file defines a `spec()`
function returning one of the objects below. An LLM writes Python far better
than SMT-LIB, and validation sits on top.
"""
from __future__ import annotations

import hashlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import t


# ---------------------------------------------------------------------------
# prove / check / core
# ---------------------------------------------------------------------------


@dataclass
class Spec:
    """Named hypotheses and one claim.

        s = Spec()
        s.assume("positive", x > 0)
        s.claim(x*x >= 0)
    """

    assumptions: list = field(default_factory=list)  # [(name, expr)]
    goal: object = None
    title: str = ""

    def assume(self, name: str, expr):
        if any(n == name for n, _ in self.assumptions):
            raise ValueError(t("spec.duplicate_hypothesis", name=name))
        self.assumptions.append((name, expr))
        return self

    def claim(self, expr):
        self.goal = expr
        return self

    @property
    def names(self):
        return [n for n, _ in self.assumptions]

    @property
    def formulas(self):
        return [f for _, f in self.assumptions]


# ---------------------------------------------------------------------------
# synth (CEGIS)
# ---------------------------------------------------------------------------


@dataclass
class SynthSpec:
    """There exists an impl. For every input. There exist helpers. All hold.

    impl_vars       what we are looking for (fixed once)
    input_vars      universally quantified (these generate counterexamples)
    helper_vars     existential per input (a fresh copy each round)
    """

    impl_vars: list
    input_vars: list
    helper_vars: list = field(default_factory=list)
    impl_constraints: object = None
    behavior: object = None
    correctness: object = None
    title: str = ""

    # --- universal obligation (for `synth --prove-candidate`) --------------
    # `behavior` is the BOUNDED domain the search runs over. The general
    # statement lives in another domain and often another sort: the search
    # runs over bounded integers, the proof over the reals, which IS
    # decidable for polynomials. So dropping the bounds is not enough.
    #
    #   universal_behavior  expression replacing `behavior`. The simple case.
    #   universal           callable(values: dict) -> Spec. Full control: it
    #                       can change sort and name the hypotheses, so that
    #                       `core` works on them.
    universal_behavior: object = None
    universal: object = None

    def normalized(self):
        import z3

        t = z3.BoolVal(True)
        return (
            self.impl_constraints if self.impl_constraints is not None else t,
            self.behavior if self.behavior is not None else t,
            self.correctness if self.correctness is not None else t,
        )


# ---------------------------------------------------------------------------
# opt (LP / ILP)
# ---------------------------------------------------------------------------


@dataclass
class LPSpec:
    """A linear program in explicit form, so the dual can be emitted.

        lp = LPSpec(sense="max")
        lp.variable("x"); lp.variable("y")
        lp.objective({"x": 3, "y": 5})
        lp.constraint({"x": 1, "y": 1}, "<=", 10, name="capacity")
    """

    sense: str = "max"
    integer: bool = False          # every variable integer; see `kind` below
    title: str = ""
    var_names: list = field(default_factory=list)
    bounds: dict = field(default_factory=dict)
    obj: dict = field(default_factory=dict)
    cons: list = field(default_factory=list)  # [(name, {var: coef}, sense, rhs)]
    kinds: dict = field(default_factory=dict)  # name -> continuous|integer|binary
    target: object = None          # a value `mixed` compares the result against

    KINDS = ("continuous", "integer", "binary")

    def variable(self, name, lo=0.0, hi=None, kind="continuous"):
        """A variable, and what kind of number it is.

        `integer=True` on the spec makes EVERY variable integer, which is the
        wrong shape for a genuinely mixed problem: a design where the discrete
        part chooses a structure and the continuous part packs inside it has
        both, and forcing the continuous variables to be integers changes the
        problem rather than restricting it.
        """
        if name in self.var_names:
            raise ValueError(t("spec.duplicate_variable", name=name))
        if kind not in LPSpec.KINDS:
            raise ValueError(t("spec.bad_kind", kind=kind,
                               known=", ".join(LPSpec.KINDS)))
        self.var_names.append(name)
        if kind == "binary":
            lo, hi = 0, 1 if hi is None else hi
        self.bounds[name] = (lo, hi)
        self.kinds[name] = kind
        return self

    def kind_of(self, name) -> str:
        """`integer=True` still means what it used to: all of them."""
        if self.integer:
            return "integer"
        return self.kinds.get(name, "continuous")

    @property
    def discrete(self) -> list:
        return [v for v in self.var_names
                if self.kind_of(v) in ("integer", "binary")]

    @property
    def continuous(self) -> list:
        return [v for v in self.var_names if self.kind_of(v) == "continuous"]

    @property
    def is_mixed(self) -> bool:
        return bool(self.discrete) and bool(self.continuous)

    def frozen(self, assignment: dict):
        """The residual LP: the discrete variables fixed, the rest free.

        Returns (LPSpec, constant) where `constant` is the objective the frozen
        variables already contribute. An LPSpec has no constant term, so it
        travels separately rather than being folded in and lost.
        """
        from .exact import to_fraction

        out = LPSpec(sense=self.sense, title=self.title)
        for v in self.continuous:
            lo, hi = self.bounds[v]
            out.variable(v, lo, hi)
        out.objective({v: c for v, c in self.obj.items()
                       if v in set(self.continuous)})
        const = sum((to_fraction(self.obj.get(v, 0)) * to_fraction(assignment[v])
                     for v in self.discrete), to_fraction(0))
        for name, coeffs, sense, rhs in self.cons:
            moved = sum((to_fraction(c) * to_fraction(assignment[v])
                         for v, c in coeffs.items() if v in set(self.discrete)),
                        to_fraction(0))
            rest = {v: c for v, c in coeffs.items()
                    if v not in set(self.discrete)}
            out.constraint(rest, sense, to_fraction(rhs) - moved, name=name)
        return out, const

    def relaxed(self):
        """Every variable continuous. The bound over ALL discrete choices."""
        out = LPSpec(sense=self.sense, title=self.title)
        for v in self.var_names:
            lo, hi = self.bounds[v]
            out.variable(v, lo, hi)
        out.objective(dict(self.obj))
        for name, coeffs, sense, rhs in self.cons:
            out.constraint(dict(coeffs), sense, rhs, name=name)
        return out

    def objective(self, coeffs: dict):
        from .exact import to_fraction

        self.obj = {k: to_fraction(v) for k, v in coeffs.items()}
        return self

    def constraint(self, coeffs: dict, sense: str, rhs, name=None):
        """Coefficients and rhs accept int, Fraction, the string '7/12' or float.

        Stored as Fraction: exact in, exact out.
        """
        from .exact import to_fraction

        if sense not in ("<=", ">=", "=="):
            raise ValueError(t("spec.bad_sense", sense=sense))
        name = name or "c{}".format(len(self.cons))
        self.cons.append((name, {k: to_fraction(v) for k, v in coeffs.items()},
                          sense, to_fraction(rhs)))
        return self

    def as_leq_system(self):
        """Normalise to max c.x subject to A x <= b, x >= 0.

        Variable bounds are materialised as rows of A: otherwise the standard
        dual does not see them and the certificate would be invalid.
        """
        from .exact import to_fraction

        A, b, names = [], [], []
        Z = to_fraction(0)

        def row_of(coeffs):
            return [to_fraction(coeffs.get(v, Z)) for v in self.var_names]

        for name, coeffs, sense, rhs in self.cons:
            row = row_of(coeffs)
            if sense == "<=":
                A.append(row); b.append(rhs); names.append(name)
            elif sense == ">=":
                A.append([-x for x in row]); b.append(-rhs); names.append(name + "_geq")
            else:
                A.append(row); b.append(rhs); names.append(name + "_le")
                A.append([-x for x in row]); b.append(-rhs); names.append(name + "_ge")

        for v in self.var_names:
            lo, hi = self.bounds.get(v, (0.0, None))
            if hi is not None:
                A.append(row_of({v: 1})); b.append(to_fraction(hi))
                names.append("bound_{}_hi".format(v))
            if lo is not None and lo > 0:
                A.append(row_of({v: -1})); b.append(-to_fraction(lo))
                names.append("bound_{}_lo".format(v))

        c = [to_fraction(self.obj.get(v, Z)) for v in self.var_names]
        if self.sense == "min":
            c = [-x for x in c]
        return A, b, c, names


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    """What a sweep predicate may return instead of a bare bool.

        def pred(g):
            ...
            return Outcome(False, cert=dual_cert, detail="ratio 0.9259")

    `ok=None` means "did not conclude": neither true nor false. The sweep
    counts those apart and can no longer claim the property holds family-wide.
    """

    ok: object = None           # True / False / None
    cert: object = None         # the predicate's Certificate, if any
    detail: str = ""
    errored: bool = False
    value: object = None        # value to collect (Fraction, int or float)


@dataclass
class SweepSpec:
    """A predicate and/or a value over an enumerated family of graphs.

    The predicate returns a bool or an `Outcome`. If it returns an Outcome
    carrying a certificate, `sweep` aggregates it and the sweep becomes
    citable.

    CALIBRATION MODE. Often the question is not "does it fail?" but "HOW MUCH
    does it fail, and where is it worst?". For that:

        SweepSpec(n=6, collect=lambda g: ratio(g), worst="min")

    `collect` returns a value per graph (use Fraction so it stays exact) and
    `sweep` reports min, max, mean and the extremes with their graph.
    `predicate` becomes optional: you can calibrate without refuting anything.
    You can also return `Outcome(..., value=...)` from the predicate so
    nothing is computed twice.
    """

    n: int
    predicate: object = None             # callable(Graph) -> bool | Outcome
    filters: list = field(default_factory=list)
    title: str = ""
    describe: object = None              # callable(Graph) -> str, optional
    collect: object = None               # callable(Graph) -> number
    worst: str = "min"                   # which end counts as "worst": min or max
    # `canonicalize(g) -> hashable`, or "auto" for graph isomorphism. The
    # enumerator already returns one graph per isomorphism class, so "auto"
    # buys nothing there -- it is for a FINER symmetry than isomorphism, which
    # is what a coloured, rooted or otherwise decorated sweep has, and for a
    # sweep over a family the enumerator did not produce.
    canonicalize: object = None


# ---------------------------------------------------------------------------
# bisect
# ---------------------------------------------------------------------------


@dataclass
class BisectSpec:
    """Find a parameter's threshold.

    `build(t)` returns a Spec (evaluated with prove) or a CNFSpec (with cases,
    where "holds" means UNSAT: no counterexample exists).

    direction:
      "min_true"  the statement holds for LARGE t -> find the smallest t
      "max_true"  it holds for SMALL t -> find the largest t

    Assumes monotonicity in t. That is not verified; if the endpoints do not
    behave as `direction` says, the command says so instead of inventing a
    threshold.
    """

    build: object          # callable(t) -> Spec | CNFSpec
    lo: float
    hi: float
    direction: str = "min_true"
    tol: float = 1e-6
    integer: bool = False
    title: str = ""


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_spec(path, expected=None):
    """Import a .py file and return whatever its `spec()` function returns.

    Two things this does NOT do the usual way, both of them on purpose.

    It compiles the source it just read instead of going through the import
    machinery, because that machinery caches bytecode keyed on mtime and size:
    a spec edited within the same second to the same length comes back as the
    OLD code. For a tool whose certificates carry a hash of the spec, running
    something other than the bytes that were hashed is not a performance
    detail -- it is the certificate describing a different program. Verifying
    a sweep by replaying its predicate is exactly where that would bite.

    And it puts the spec's own directory on `sys.path`, the way Python does
    for a script it runs, so a spec can import a helper sitting next to it.
    Without that, splitting a growing spec across two files fails in a way
    that looks like a bug in `certo`.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(t("spec.not_found", path=p))

    here = str(p.parent)
    if here not in sys.path:
        sys.path.insert(0, here)

    source = p.read_bytes()
    name = "certo_spec_" + hashlib.sha256(str(p).encode()).hexdigest()[:12]
    mod = types.ModuleType(name)
    mod.__file__ = str(p)
    mod.__dict__["__builtins__"] = __builtins__
    sys.modules[name] = mod            # so dataclasses and typing resolve
    try:
        exec(compile(source, str(p), "exec"), mod.__dict__)
    finally:
        sys.modules.pop(name, None)

    if not hasattr(mod, "spec"):
        raise AttributeError(t("spec.no_function", name=p.name))
    obj = mod.spec()
    if expected is not None and not isinstance(obj, expected):
        raise TypeError(t("spec.wrong_type", got=type(obj).__name__,
                          want=expected.__name__))
    return obj


# ---------------------------------------------------------------------------
# sweep over an arbitrary finite domain
# ---------------------------------------------------------------------------


@dataclass
class DomainSpec:
    """A predicate and/or a value over ANY finite domain, not just graphs.

    Graphs are one domain among many. The same exhaustive pattern applies to
    parameter pairs, residue classes, separator sizes, multiplicity vectors --
    anything you can enumerate:

        DomainSpec(
            items=[(s, r) for s in range(2, 8) for r in range(2, 8)],
            predicate=lambda p: bound_holds(*p),
            collect=lambda p: ratio(*p),
            key=lambda p: "s={},r={}".format(*p),
        )

    `key` turns an item into a stable string id: it is what lands in the
    certificate, so it has to identify the item unambiguously.

    `reduce` is what `shrink` needs: given an item, the items one step
    "smaller". Pass a callable, or the name of a standard reducer:

        reduce="auto"          pick from the item's type, or refuse
        reduce="sets"          drop one element
        reduce="sequences"     drop one element of a list or tuple
        reduce="decrement"     lower one integer coordinate by one
        reduce="graphs"        delete one vertex
        reduce="masks"         clear one set bit
        reduce=lambda p: [(p[0] - 1, p[1]), (p[0], p[1] - 1)]

    `auto` refuses on a type it does not recognise instead of inventing a
    reduction: a witness that is minimal for the wrong relation looks exactly
    like one that is minimal for the right one.

    The reduced items do not have to be inside `items`: the sweep domain is
    often a window, and the interesting reduction may leave it.
    """

    # `canonicalize(item) -> hashable`, equal exactly for items in the same
    # orbit of whatever symmetry the domain has. Nothing needs to know the
    # group; it needs to know when two items are the same object relabelled.
    # With it, a sweep reports labelled count, orbit count and a
    # representative per orbit -- and `--by-orbit` will evaluate one item per
    # orbit instead of all of them.
    items: object                        # iterable, or callable() -> iterable
    predicate: object = None             # callable(item) -> bool | Outcome
    collect: object = None               # callable(item) -> number
    key: object = None                   # callable(item) -> str (default: str)
    describe: object = None              # callable(item) -> str, optional
    reduce: object = None                # callable(item) -> iterable, or a name
    canonicalize: object = None          # callable(item) -> hashable orbit key
    worst: str = "min"
    title: str = ""

    def enumerate(self):
        it = self.items() if callable(self.items) else self.items
        return list(it)

    def id_of(self, item) -> str:
        """The item's id: the spec's `key`, or the item's own.

        A native type knows how to name itself, so a DomainSpec over one needs
        no `key` at all -- and asking the item beats a registry keyed on type,
        because anyone's class can join by having the method.
        """
        if self.key is not None:
            return str(self.key(item))
        own = getattr(item, "key", None)
        return str(own()) if callable(own) else str(item)

    def reducer(self):
        """The reduce function, resolving a catalogue name if that is what it is."""
        from .reducers import resolve

        return None if self.reduce is None else resolve(self.reduce)


# ---------------------------------------------------------------------------
# core over several goals at once
# ---------------------------------------------------------------------------


@dataclass
class MultiSpec:
    """The same named hypotheses against SEVERAL named goals.

        s = MultiSpec()
        s.assume("r_ge_3", r >= 3)
        s.assume("d_ge_1", d >= 1)
        s.claim("identity",   lhs == rhs)
        s.claim("positivity", lhs >= 0)

    `core` then reports a hypothesis-by-goal table: which hypotheses each goal
    actually needs. A hypothesis irrelevant to the identity but necessary for
    positivity is the kind of thing that decides how small a Lean interface
    can be, and it is invisible when the goals are checked one at a time.
    """

    assumptions: list = field(default_factory=list)   # [(name, expr)]
    goals: list = field(default_factory=list)         # [(name, expr)]
    title: str = ""

    def assume(self, name: str, expr):
        if any(n == name for n, _ in self.assumptions):
            raise ValueError(t("spec.duplicate_hypothesis", name=name))
        self.assumptions.append((name, expr))
        return self

    def claim(self, name: str, expr):
        if any(n == name for n, _ in self.goals):
            raise ValueError(t("spec.duplicate_goal", name=name))
        self.goals.append((name, expr))
        return self

    def single(self, goal_name: str) -> "Spec":
        """The Spec for one goal, so each column is an ordinary `core` run."""
        s = Spec(title="{} [{}]".format(self.title, goal_name))
        for n, f in self.assumptions:
            s.assume(n, f)
        for n, f in self.goals:
            if n == goal_name:
                return s.claim(f)
        raise KeyError("no goal named " + goal_name)

    @property
    def names(self):
        return [n for n, _ in self.assumptions]

    @property
    def goal_names(self):
        return [n for n, _ in self.goals]


# ---------------------------------------------------------------------------
# bounds: a numeric quantity, rigorously enclosed
# ---------------------------------------------------------------------------


@dataclass
class BoundSpec:
    """A real quantity and the bound claimed about it, computed rigorously.

        BoundSpec(
            value=lambda m: m.exp(1) / m.pi,
            claim=("<", "0.866"),
        )

    `value` receives a namespace of RIGOROUS constants and functions: every
    operation returns an enclosure, so an inequality that holds for the whole
    enclosure holds for the number. Python floats raise rather than quietly
    narrowing the claim to a nearby dyadic -- write `m("0.1")`, which is one
    tenth, not `0.1`, which is not.

    `claim` is a relation against an EXACT rational, written as a string:
    ("<", "1/3"), ("<=", "0.5"), (">", "0"), (">=", ...), ("!=", "0") for a
    sign determination, or ("in", lo, hi). Leave it out to measure rather than
    decide: the certificate then records the enclosure that was reached.

    Precision is the work budget here, the way rlimit is for z3: the search
    doubles it until the enclosure settles the claim or `max_prec` is hit, and
    hitting it is reported as "did not settle", never as "false".
    """

    value: object                    # callable(m) -> an enclosure
    claim: object = None             # (rel, rational) | ("in", lo, hi) | None
    prec: int = 128                  # starting precision, in bits
    max_prec: int = 16_384
    describe: str = ""               # what the quantity IS, for the write-up
    title: str = ""


# ---------------------------------------------------------------------------
# compose: lemmas, each backed by a certificate, and the theorem they prove
# ---------------------------------------------------------------------------


@dataclass
class Lemma:
    """One step of a proof, and the certificate that discharges it.

    Either `proves` (a Spec to discharge right now) or `certificate` (a path
    to one already on disk) plus `states` (what it licenses you to assume).
    """

    name: str
    proves: object = None            # a Spec, discharged now
    via: str = "prove"               # "prove" | "farkas" | "nlinarith"
    certificate: str = ""            # a certificate already on disk
    states: object = None            # the formula this lemma contributes
    bridge: str = ""                 # prose: why that certificate says that

    @property
    def is_bridge(self) -> bool:
        return self.proves is None


@dataclass
class ProofSpec:
    """Lemmas, the theorem, and the step that joins them.

        p = ProofSpec(title="...")
        p.assume("x_pos", x > 0)                 # hypothesis of the THEOREM
        p.lemma("amgm", proves=sub_spec)         # discharged now, by `prove`
        p.lemma("tight", proves=other, via="farkas")
        p.lemma("k6", certificate="certs/drat-1a2b.json",
                states=phi,                      # what it licenses
                bridge="every 2-colouring of K6 has a mono triangle")
        p.conclude(theorem)

    The point is not that the lemmas hold -- each certificate already says
    that. It is that **the statement used downstream is the statement the
    certificate establishes**, which is where hand-assembled proofs go wrong:
    a lemma proved under one hypothesis and used under another.

    A lemma given by `certificate=` is a BRIDGE: the certificate is verified,
    but nothing can check that it licenses `states`, because a finite sweep or
    a DRAT proof is not a first-order formula. Bridges are recorded by name
    and reported every time the proof is verified. Making them visible is the
    whole reason they are allowed at all.
    """

    lemmas: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)   # [(name, expr)]
    goal: object = None
    title: str = ""

    def lemma(self, name, proves=None, via="prove", certificate="",
              states=None, bridge=""):
        if any(l.name == name for l in self.lemmas):
            raise ValueError(t("spec.duplicate_lemma", name=name))
        if proves is None and not certificate:
            raise ValueError(t("spec.lemma_no_source", name=name))
        if proves is None and states is None:
            raise ValueError(t("spec.lemma_no_statement", name=name))
        self.lemmas.append(Lemma(name=name, proves=proves, via=via,
                                 certificate=certificate, states=states,
                                 bridge=bridge))
        return self

    def assume(self, name: str, expr):
        if any(n == name for n, _ in self.assumptions):
            raise ValueError(t("spec.duplicate_hypothesis", name=name))
        self.assumptions.append((name, expr))
        return self

    def conclude(self, expr):
        self.goal = expr
        return self

    @property
    def names(self):
        return [n for n, _ in self.assumptions]

    @property
    def lemma_names(self):
        return [l.name for l in self.lemmas]


# ---------------------------------------------------------------------------
# induct: base cases plus a step, and the join between them
# ---------------------------------------------------------------------------


@dataclass
class InductSpec:
    """Finite base cases, an inductive step, and the chain they form.

        p = InductSpec(
            k0=3, base_upto=8,
            base=lambda k: SweepSpec(n=k, predicate=...),   # or a cert path
            step=step_spec,          # assume P(k), k >= step_from; claim P(k+1)
            step_from=3,
            bridge="the sweep checks every graph on k vertices; reading that "
                   "as P(k) is what the encoding means",
        )

    `base` is a callable k -> spec, a dict {k: spec}, or a path to a stored
    certificate. Anything finite -- a sweep, a DRAT proof, a plain `prove`.

    `step` is an ordinary `Spec` over a FREE k. A proof with a free variable
    is a proof for every value of it, which is what the schema needs; there is
    no quantifier to give a solver.

    What this buys over running the two halves separately is the join: that
    the base cases are exactly k0..base_upto with no gap, and that the step
    starts no later than the base ends. A base covering 3..8 with a step valid
    only from k >= 10 proves nothing, and reads identically in prose.
    """

    k0: int
    base_upto: int
    base: object                     # callable(k) -> spec | {k: spec} | path
    step: object                     # a Spec over a free k
    step_from: object = None         # defaults to k0
    bridge: str = ""                 # how a finite check becomes P(k)
    describe: str = ""               # the conclusion, in words
    title: str = ""


# ---------------------------------------------------------------------------
# polynomial ideals, sums of squares, and integers
# ---------------------------------------------------------------------------


@dataclass
class IdealSpec:
    """Polynomial equations, and what follows from them.

        IdealSpec(
            variables=["x", "y"],
            equations=[x*x + y*y - 1, x - 2],     # z3 terms, or Poly
            claim=None,                           # None = "no solution at all"
        )

    With `claim=None` the question is whether the system is INCONSISTENT, and
    the certificate is cofactors with `1 = sum h_i g_i`. With a claim `f`, the
    question is whether `f` vanishes on every common root, certified the same
    way: `f = sum h_i g_i`.

    The field matters and the certificate says so. `1 = sum h_i g_i` refutes
    solutions over the COMPLEX numbers, hence over the reals, the rationals
    and the integers. The converse does not hold: a proper ideal does not mean
    a real solution exists, only that a complex one might.
    """

    variables: list
    equations: list                  # z3 terms or Poly, each meaning "= 0"
    claim: object = None             # a z3 term or Poly, or None
    max_pairs: int = 20_000
    title: str = ""


@dataclass
class SOSSpec:
    """A polynomial claimed non-negative everywhere, certified as a sum of
    squares.

        SOSSpec(variables=["x", "y"], poly=x**4 + y**4 - x**2 * y**2)

    The search is numeric and the certificate is exact: rational coefficients
    and rational linear forms, checked by expanding. Nothing approximate
    survives into the certificate.

    Incomplete, and in a way worth knowing: every sum of squares is
    non-negative, but from degree 4 in 3 variables there are non-negative
    polynomials that are not sums of squares (Motzkin's is the standard one).
    So no certificate found is `unknown_solver`, never "it goes negative".
    """

    variables: list
    poly: object                     # a z3 term or Poly
    half_degree: object = None       # default: deg(p)/2
    iterations: int = 600
    title: str = ""


@dataclass
class NumberSpec:
    """An integer question with a certificate anyone can redo by hand.

        NumberSpec(n=2 ** 31 - 1, question="prime")
        NumberSpec(n=600851475143, question="factor")

    `prime` emits a Pratt certificate: a witness generating (Z/n)^*, plus a
    certificate for each prime factor of n-1, recursively. Checking it is
    modular exponentiation. `factor` emits the factors, each with its own
    primality certificate, so "and these are prime" is not left hanging.
    """

    n: int
    question: str = "prime"          # "prime" | "factor"
    title: str = ""
