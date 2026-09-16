"""Rigorous numerics: every value is an enclosure, never a float.

The gap this fills. `farkas` and `opt` are exact but algebraic; the moment a
proof says "this constant is below 0.4" and the constant involves `e`, `log`,
`pi` or a special function, there was nothing to reach for. And "I computed it
and it came out 0.397" is not citable: a float result carries no claim about
the true value at all.

Ball (or interval) arithmetic does carry one. Every operation returns an
enclosure guaranteed to contain the true value, so an inequality that holds
for the whole enclosure holds for the number. The enclosure comes out as
EXACT dyadic rationals, which is what makes the certificate checkable by
arithmetic afterwards rather than by rerunning the same library and hoping.

Two backends, both genuinely rigorous, in this order:

  * python-flint (Arb). Ball arithmetic, fast, and the reference for this
    kind of work.
  * mpmath.iv. Interval arithmetic with directed rounding. Slower and looser,
    but pure Python and almost always already installed.

The backend is recorded in the certificate, because a bound is only as good as
the thing that produced it.

FLOATS ARE REFUSED. `0.1` is not one tenth -- it is 3602879701896397/2^55, and
an enclosure built from it is rigorous about the wrong number. So `Ball`
refuses arithmetic with Python floats and asks for a string or a Fraction
instead. It is the one way the guarantee could quietly be lost, so it is the
one thing that raises.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t


class NoBackend(RuntimeError):
    """Neither python-flint nor mpmath is installed."""


class NotRigorous(TypeError):
    """A Python float got into an expression that claims to be rigorous."""


def backend_name() -> str:
    try:
        import flint  # noqa: F401
        return "python-flint (Arb)"
    except ImportError:
        pass
    try:
        import mpmath  # noqa: F401
        return "mpmath.iv"
    except ImportError:
        raise NoBackend(t("numerics.no_backend"))


# ---------------------------------------------------------------------------
# the value that travels through a user's expression
# ---------------------------------------------------------------------------


class Ball:
    """An enclosure of a real number, with arithmetic that keeps it one.

    Wrapping the backend value rather than exposing it does two things: the
    same expression runs unchanged on either backend, and a Python float
    raises instead of silently narrowing the claim to a nearby dyadic.
    """

    __slots__ = ("_v", "_rig")

    def __init__(self, v, rig):
        self._v = v
        self._rig = rig

    # --- coercion ---------------------------------------------------------

    def _co(self, other):
        if isinstance(other, Ball):
            return other._v
        if isinstance(other, float):
            raise NotRigorous(t("numerics.float", value=repr(other)))
        return self._rig._raw(other)

    def __add__(self, o):
        return Ball(self._v + self._co(o), self._rig)

    def __radd__(self, o):
        return Ball(self._co(o) + self._v, self._rig)

    def __sub__(self, o):
        return Ball(self._v - self._co(o), self._rig)

    def __rsub__(self, o):
        return Ball(self._co(o) - self._v, self._rig)

    def __mul__(self, o):
        return Ball(self._v * self._co(o), self._rig)

    def __rmul__(self, o):
        return Ball(self._co(o) * self._v, self._rig)

    def __truediv__(self, o):
        return Ball(self._v / self._co(o), self._rig)

    def __rtruediv__(self, o):
        return Ball(self._co(o) / self._v, self._rig)

    def __pow__(self, o):
        return Ball(self._v ** self._co(o), self._rig)

    def __neg__(self):
        return Ball(-self._v, self._rig)

    def __abs__(self):
        return self._rig._abs(self)

    # Comparisons are deliberately absent. Two enclosures that overlap cannot
    # be ordered, and returning False would read as "not less than". The
    # claim is settled once, at the end, against exact rationals.

    def enclosure(self):
        """(lo, hi) as EXACT Fractions. This is what lands in the certificate."""
        return self._rig._enclosure(self._v)

    def __repr__(self):
        lo, hi = self.enclosure()
        return "Ball[{}, {}]".format(float(lo), float(hi))


# ---------------------------------------------------------------------------
# the namespace handed to the spec
# ---------------------------------------------------------------------------


class Rig:
    """Rigorous constants and functions at a fixed precision.

        BoundSpec(value=lambda m: m.exp(1) / m.pi)

    `m(x)` turns an int, a Fraction or a decimal STRING into an enclosure.
    A string is read as an exact rational, so `m("0.1")` is one tenth --
    unlike `0.1`, which is not, and which raises.
    """

    # Arb has the lot. mpmath.iv covers the elementary ones and gamma, and
    # nothing else -- so asking for `zeta` there says so instead of falling
    # back to a non-rigorous evaluation.
    FUNCS = ("exp log sqrt sin cos tan asin acos atan sinh cosh tanh "
             "gamma lgamma digamma zeta erf erfc").split()
    MPMATH_FUNCS = "exp log sqrt sin cos tan gamma".split()

    @property
    def functions(self) -> list:
        return list(Rig.FUNCS if self._flint else Rig.MPMATH_FUNCS)

    def __init__(self, prec: int, backend: str | None = None):
        self.prec = int(prec)
        self.backend = backend or backend_name()
        self._flint = self.backend.startswith("python-flint")
        if self._flint:
            import flint
            self._m = flint
            flint.ctx.prec = self.prec
        else:
            from mpmath import iv
            self._m = iv
            iv.prec = self.prec

    # --- building values --------------------------------------------------

    def _raw(self, x):
        """int / Fraction / str / Decimal -> a backend value, exactly."""
        if isinstance(x, float):
            raise NotRigorous(t("numerics.float", value=repr(x)))
        if isinstance(x, str):
            x = Fraction(x)
        if isinstance(x, Fraction):
            if self._flint:
                return self._m.arb(x.numerator) / self._m.arb(x.denominator)
            return self._m.mpf(x.numerator) / self._m.mpf(x.denominator)
        if isinstance(x, int):
            return self._m.arb(x) if self._flint else self._m.mpf(x)
        raise NotRigorous(t("numerics.not_a_number", value=repr(x)))

    def __call__(self, x) -> Ball:
        return Ball(self._raw(x), self)

    num = __call__

    # --- constants --------------------------------------------------------

    @property
    def pi(self) -> Ball:
        return Ball(self._m.arb.pi() if self._flint else self._m.pi, self)

    @property
    def e(self) -> Ball:
        return Ball(self._m.arb.const_e() if self._flint
                    else self._m.exp(self._m.mpf(1)), self)

    @property
    def euler(self) -> Ball:
        """The Euler-Mascheroni constant."""
        if self._flint:
            return Ball(self._m.arb.const_euler(), self)
        from mpmath import mp
        mp.prec = self.prec + 20
        return Ball(self._m.mpf(mp.euler), self)

    # --- functions --------------------------------------------------------

    def _apply(self, name, x):
        b = x if isinstance(x, Ball) else self(x)
        if self._flint:
            return Ball(getattr(b._v, name)(), self)
        return Ball(getattr(self._m, name)(b._v), self)

    def _abs(self, x) -> Ball:
        return Ball(abs(x._v), self)

    def __getattr__(self, name):
        if name in Rig.FUNCS:
            if not self._flint and name not in Rig.MPMATH_FUNCS:
                raise NotRigorous(t("numerics.unsupported", name=name,
                                    backend=self.backend))
            return lambda x: self._apply(name, x)
        raise AttributeError(name)

    # --- reading the answer back ------------------------------------------

    def _enclosure(self, v):
        if self._flint:
            man, exp = v.mid().man_exp()
            rman, rexp = v.rad().man_exp()
            mid = Fraction(int(man)) * Fraction(2) ** int(exp)
            rad = Fraction(int(rman)) * Fraction(2) ** int(rexp)
            return mid - rad, mid + rad
        lo, hi = v._mpi_
        return _mpf_fraction(lo), _mpf_fraction(hi)


def _mpf_fraction(raw) -> Fraction:
    """An mpmath raw float (sign, man, exp, bc) as an exact Fraction."""
    sign, man, exp, _bc = raw
    f = Fraction(int(man)) * Fraction(2) ** int(exp)
    return -f if sign else f


# ---------------------------------------------------------------------------
# settling a claim against an enclosure
# ---------------------------------------------------------------------------

RELATIONS = ("<", "<=", ">", ">=", "!=", "in")


def settle(claim, lo: Fraction, hi: Fraction):
    """True, False, or None when the enclosure is too wide to decide.

    None is the honest third answer and the reason precision is a budget: it
    means "this computation did not settle it", never "it is false".
    """
    if claim is None:
        return None
    rel = claim[0]
    if rel == "in":
        a, b = Fraction(str(claim[1])), Fraction(str(claim[2]))
        if a <= lo and hi <= b:
            return True
        if hi < a or lo > b:
            return False
        return None
    c = Fraction(str(claim[1]))
    if rel == "<":
        return True if hi < c else (False if lo >= c else None)
    if rel == "<=":
        return True if hi <= c else (False if lo > c else None)
    if rel == ">":
        return True if lo > c else (False if hi <= c else None)
    if rel == ">=":
        return True if lo >= c else (False if hi < c else None)
    if rel == "!=":
        return True if (hi < c or lo > c) else None   # never provably equal
    raise ValueError(t("numerics.bad_relation", rel=rel,
                       known=", ".join(RELATIONS)))


def render(claim) -> str:
    if claim is None:
        return ""
    if claim[0] == "in":
        return t("numerics.render.in", lo=claim[1], hi=claim[2])
    return t("numerics.render.rel", rel=claim[0], c=claim[1])
