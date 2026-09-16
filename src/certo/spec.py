"""The input DSL: Python as the host language.

Design decision: we do not invent a language. A .py file defines a `spec()`
function returning one of the objects below. An LLM writes Python far better
than SMT-LIB, and validation sits on top.
"""
from __future__ import annotations

import importlib.util
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
    integer: bool = False
    title: str = ""
    var_names: list = field(default_factory=list)
    bounds: dict = field(default_factory=dict)
    obj: dict = field(default_factory=dict)
    cons: list = field(default_factory=list)  # [(name, {var: coef}, sense, rhs)]

    def variable(self, name, lo=0.0, hi=None):
        if name in self.var_names:
            raise ValueError(t("spec.duplicate_variable", name=name))
        self.var_names.append(name)
        self.bounds[name] = (lo, hi)
        return self

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
    """Import a .py file and return whatever its spec() function returns."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(t("spec.not_found", path=p))
    mod_spec = importlib.util.spec_from_file_location("certo_userspec", p)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
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
    "smaller". It is domain-specific and there is no sensible default, so
    without it `shrink` says what to add rather than guessing:

        reduce=lambda p: [(p[0] - 1, p[1]), (p[0], p[1] - 1)]

    The reduced items do not have to be inside `items`: the sweep domain is
    often a window, and the interesting reduction may leave it.
    """

    items: object                        # iterable, or callable() -> iterable
    predicate: object = None             # callable(item) -> bool | Outcome
    collect: object = None               # callable(item) -> number
    key: object = None                   # callable(item) -> str (default: str)
    describe: object = None              # callable(item) -> str, optional
    reduce: object = None                # callable(item) -> iterable of items
    worst: str = "min"
    title: str = ""

    def enumerate(self):
        it = self.items() if callable(self.items) else self.items
        return list(it)

    def id_of(self, item) -> str:
        return str(self.key(item)) if self.key else str(item)


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
