"""`A x = b` exactly, with a witness either way.

The certificate for a solved linear system is almost embarrassing: it is the
solution, and checking it is one matrix-vector product. That is the point.
Anything a numerical library reports about `A x = b` is a number somebody has
to trust; `x` with `A` and `b` beside it is a number somebody can multiply.

WHAT MAKES IT WORTH A COMMAND is not the solving, which is undergraduate. It
is three things that a bare `x` handed over in a chat message does not have:

  THE SYSTEM TRAVELS WITH THE ANSWER. `A` and `b` are in the payload, so
  re-checking is against the system that was stated, not against the one
  somebody remembers stating. A solution to a slightly different matrix is
  the failure mode here, and it is invisible without this.

  UNSOLVABLE IS ALSO CERTIFIED. "No solution" is a claim, and it has a
  witness: `y` with `y.A = 0` and `y.b != 0`. That is a row operation the
  elimination already performed, kept instead of thrown away, and it turns a
  negative result into something checkable by two more products.

  UNDERDETERMINED IS NOT ROUNDED TO "A SOLUTION". A particular solution plus
  a basis of the kernel says what the solution SET is. Reporting one point of
  an affine subspace as though it were the answer is how a free parameter
  disappears from a write-up.

WHAT IT DOES NOT ESTABLISH, and `verify` repeats it every time: that `x` is
NON-NEGATIVE, and over the rationals that it is INTEGRAL. A rational solution
to the equations of a packing is not a packing. Those are different questions
with different commands -- `opt` and `farkas` for the first, `domain="integer"`
here or `matrix` for the second -- and letting a solved system stand in for
either is the substitution this note exists to prevent.

OVER THE INTEGERS it is the Smith normal form that decides it. `U A V = S`
with `S` diagonal turns `A x = b` into `S w = U b`, which is solvable exactly
when each `s_i` divides its entry and the entries past the rank vanish. The
answer is then `x = V w`, and the check is the same single product -- the
transforms do not even have to travel, because the solution stands on its own.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t

UNIQUE, MANY, NONE = "unique", "underdetermined", "none"


class NotSolvable(ValueError):
    """Raised with what was wrong, never bare."""


def parse_vector(values, name="rhs") -> list:
    out = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or isinstance(v, float):
            raise NotSolvable(_t("linsolve.not_exact", name=name, index=i))
        try:
            out.append(Fraction(v))
        except (TypeError, ValueError):
            raise NotSolvable(
                _t("linsolve.not_exact", name=name, index=i)) from None
    return out


def parse_matrix(rows) -> list:
    if not rows:
        raise NotSolvable(_t("linsolve.empty"))
    out, width = [], None
    for i, row in enumerate(rows):
        vals = parse_vector(row, name="row {}".format(i))
        if width is None:
            width = len(vals)
        elif len(vals) != width:
            raise NotSolvable(_t("linsolve.ragged", row=i, got=len(vals),
                                 want=width))
        out.append(vals)
    if not width:
        raise NotSolvable(_t("linsolve.empty"))
    return out


def multiply(A, x) -> list:
    """`A x`, exactly. The operation every check here reduces to."""
    return [sum((a * v for a, v in zip(row, x)), Fraction(0)) for row in A]


def _rref(A, b):
    """Reduced row echelon form of `[A | b]`, with the transform kept.

    The transform is the whole reason to write this rather than call the
    elimination that already exists: a row of `T` that kills a row of `A`
    while leaving `b` alive IS the proof that there is no solution, and it is
    computed for free on the way past.
    """
    n, m = len(A), len(A[0])
    aug = [list(row) + [rhs] for row, rhs in zip(A, b)]
    T = [[Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]

    pivots, r = [], 0
    for col in range(m):
        piv = next((i for i in range(r, n) if aug[i][col]), None)
        if piv is None:
            continue
        aug[r], aug[piv] = aug[piv], aug[r]
        T[r], T[piv] = T[piv], T[r]
        scale = Fraction(1) / aug[r][col]
        aug[r] = [v * scale for v in aug[r]]
        T[r] = [v * scale for v in T[r]]
        for i in range(n):
            if i != r and aug[i][col]:
                f = aug[i][col]
                aug[i] = [v - f * w for v, w in zip(aug[i], aug[r])]
                T[i] = [v - f * w for v, w in zip(T[i], T[r])]
        pivots.append(col)
        r += 1
        if r == n:
            break
    return aug, T, pivots


def solve_rational(A, b) -> dict:
    """The solution SET, not a solution: status, a point, and the kernel."""
    n, m = len(A), len(A[0])
    aug, T, pivots = _rref(A, b)
    rank = len(pivots)

    # A row that is zero across A but not at the right-hand side is the
    # contradiction, and the matching row of T is the witness for it.
    for i in range(n):
        if not any(aug[i][:m]) and aug[i][m]:
            return {"status": NONE, "rank": rank, "solution": None,
                    "kernel": [], "witness": list(T[i])}

    x = [Fraction(0)] * m
    for r, col in enumerate(pivots):
        x[col] = aug[r][m]

    free = [c for c in range(m) if c not in set(pivots)]
    kernel = []
    for f in free:
        k = [Fraction(0)] * m
        k[f] = Fraction(1)
        for r, col in enumerate(pivots):
            k[col] = -aug[r][f]
        kernel.append(k)

    return {"status": UNIQUE if not free else MANY, "rank": rank,
            "solution": x, "kernel": kernel, "witness": None}


def solve_integer(A, b) -> dict:
    """`A x = b` over Z, decided by the Smith normal form.

    `U A V = S` with `S` diagonal turns the system into `S w = U b`: solvable
    exactly when each diagonal entry divides its own right-hand side and
    everything past the rank vanishes. The answer is `x = V w`, and it is
    checked the same way as any other -- one product against the original `A`,
    with the transforms not needed for that at all.
    """
    from . import lattice

    if any(v.denominator != 1 for v in b):
        raise NotSolvable(_t("linsolve.rhs_not_integer"))
    ints = [[int(v) for v in row] for row in A]
    if any(v.denominator != 1 for row in A for v in row):
        raise NotSolvable(_t("linsolve.matrix_not_integer"))

    out = lattice.smith(ints)
    S, U, V = out["s"], out["u"], out["v"]
    n, m = lattice.shape(ints)
    c = [sum(u * int(v) for u, v in zip(row, b)) for row in U]

    diag = [S[i][i] for i in range(min(n, m))]
    blocked = []
    for i in range(n):
        d = diag[i] if i < len(diag) else 0
        if d == 0:
            if c[i]:
                blocked.append(i)          # 0 = nonzero
        elif c[i] % d:
            blocked.append(i)              # d does not divide it
    if blocked:
        return {"status": NONE, "rank": out["rank"], "solution": None,
                "kernel": [], "witness": None,
                "blocked_rows": blocked,
                "invariants": out["invariants"]}

    w = [0] * m
    for i in range(min(n, m)):
        if diag[i]:
            w[i] = c[i] // diag[i]
    x = [sum(V[r][k] * w[k] for k in range(m)) for r in range(m)]

    # The kernel over Z is spanned by the columns of V past the rank: `S` has
    # nothing there, so `A (V e_k) = 0`, and V is unimodular so they are a
    # basis of the LATTICE and not merely of the space it spans. That
    # distinction is the reason to go through Smith at all.
    kernel = [[Fraction(V[r][k]) for r in range(m)]
              for k in range(out["rank"], m)]

    return {"status": UNIQUE if out["rank"] == m else MANY,
            "rank": out["rank"], "solution": [Fraction(v) for v in x],
            "kernel": kernel, "witness": None,
            "invariants": out["invariants"]}


def certify(spec) -> dict:
    """Solve, and keep whatever makes the answer checkable."""
    A = parse_matrix(spec.matrix)
    b = parse_vector(spec.rhs)
    if len(b) != len(A):
        raise NotSolvable(_t("linsolve.shape", rows=len(A), rhs=len(b)))

    domain = getattr(spec, "domain", "rational")
    if domain not in ("rational", "integer"):
        raise NotSolvable(_t("linsolve.bad_domain", domain=domain))

    out = (solve_integer(A, b) if domain == "integer"
           else solve_rational(A, b))
    out["domain"] = domain
    out["matrix"] = [[str(v) for v in row] for row in A]
    out["rhs"] = [str(v) for v in b]
    out["columns"] = len(A[0])
    if out["solution"] is not None:
        out["solution"] = [str(v) for v in out["solution"]]
    out["kernel"] = [[str(v) for v in k] for k in out["kernel"]]
    if out["witness"] is not None:
        out["witness"] = [str(v) for v in out["witness"]]
    return out
