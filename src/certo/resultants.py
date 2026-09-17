"""Eliminate a variable from two polynomials, with the identity that proves it.

`ideal` answers membership: does this follow from those equations? This
answers a different question, and one people ask constantly while setting a
problem up:

    I have f(s, t) = 0 and g(s, t) = 0. Get rid of t and tell me what has to
    be true of s.

The answer is the RESULTANT, `Res_t(f, g)`: a polynomial in the remaining
variables that vanishes exactly when f and g have a common root in t. It is
the determinant of the Sylvester matrix, and computing it is not the hard
part -- believing it is.

So it comes with the Bezout identity:

    Res_t(f, g) = A*f + B*g

with A and B polynomials the construction produces. Checking that is expanding
two products and subtracting, in exact rational arithmetic, with no solver and
no trust in this file. It is the same move `ideal` makes with its cofactors,
and it is available here for the same reason: a determinant nobody can check
is a number somebody has to take on faith.

WHAT THE RESULTANT DOES AND DOES NOT SAY, because the difference has bitten
people who knew the theorem:

  `Res = 0` is NECESSARY for a common root, always, over any field.

  It is SUFFICIENT over an algebraically closed field, and only when the
  leading coefficients in t do not both vanish. Over the reals a vanishing
  resultant may mean a common COMPLEX root and nothing more. The certificate
  says which case it is in, every time.

  A resultant that is a NON-ZERO CONSTANT is conclusive in the useful
  direction: there is no common root, for any values of the other variables,
  over any extension field. That is a refutation, and it is exact.

The determinant is computed by Bareiss -- fraction-free elimination, where
every division is exact by construction and performed as a polynomial
division whose remainder is asserted to be zero. No rational functions ever
appear, so nothing has to be cleared at the end.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t
from .polynomials import Budget, Poly, divide


class NotEliminable(ValueError):
    """Raised with the reason, because "it failed" helps nobody."""


def _index_of(variables, name) -> int:
    try:
        return list(variables).index(name)
    except ValueError:
        raise NotEliminable(_t("resultant.unknown_var", name=name,
                               names=", ".join(variables)))


def coefficients_in(f: Poly, k: int) -> list:
    """f as a list of coefficients in variable k: `[c0, c1, ...]` for `sum ci t^i`.

    Each coefficient stays a `Poly` over the SAME ring, with exponent zero in
    the eliminated variable. Keeping one ring throughout means nothing has to
    be renamed or re-based, and the Bezout identity is checkable in the ring
    the user stated the problem in.
    """
    deg = max((e[k] for e in f.terms), default=0)
    out = [Poly(f.vars) for _ in range(deg + 1)]
    for e, c in f.terms.items():
        stripped = list(e)
        d = stripped[k]
        stripped[k] = 0
        out[d] = out[d] + Poly(f.vars, {tuple(stripped): c})
    return out


def _degree_in(f: Poly, k: int) -> int:
    return max((e[k] for e in f.terms), default=-1)


def sylvester(fc: list, gc: list) -> list:
    """The Sylvester matrix of two coefficient lists, as rows of polynomials.

    Rows are the coefficient vectors of `t^(m-1) f, ..., f, t^(n-1) g, ..., g`
    written in the basis `t^(n+m-1), ..., t, 1`, which is the arrangement that
    makes the determinant the resultant and the last row of the adjugate the
    Bezout cofactors.
    """
    n, m = len(fc) - 1, len(gc) - 1        # degrees in t
    size = n + m
    ring = fc[0].vars
    rows = []
    for i in range(m):                      # t^(m-1-i) * f
        row = [Poly(ring)] * size
        row = list(row)
        for d, c in enumerate(fc):
            row[i + (n - d)] = c
        rows.append(row)
    for j in range(n):                      # t^(n-1-j) * g
        row = list([Poly(ring)] * size)
        for d, c in enumerate(gc):
            row[j + (m - d)] = c
        rows.append(row)
    return rows


def _exact_div(a: Poly, b: Poly) -> Poly:
    """`a / b` where the division is exact by construction. Verified anyway."""
    if not b:
        raise NotEliminable(_t("resultant.zero_pivot"))
    quots, rem, _ = divide(a, [b])
    if rem:
        # Bareiss guarantees exactness; if that ever fails the answer is
        # wrong, not slow, so it stops rather than rounding.
        raise NotEliminable(_t("resultant.inexact"))
    return quots[0]


def determinant(matrix: list, max_terms: int = 200_000) -> Poly:
    """Bareiss fraction-free elimination over the polynomial ring.

    Every intermediate entry stays a polynomial -- the divisions are exact by
    a theorem, and `_exact_div` checks each one rather than assuming it.
    """
    n = len(matrix)
    if n == 0:
        return Poly(("",), {(0,): Fraction(1)})
    ring = matrix[0][0].vars
    M = [list(row) for row in matrix]
    sign = 1
    prev = Poly.const(ring, 1)

    for k in range(n - 1):
        if not M[k][k]:
            swap = next((i for i in range(k + 1, n) if M[i][k]), None)
            if swap is None:
                return Poly(ring)           # a zero column: singular
            M[k], M[swap] = M[swap], M[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                num = M[i][j] * M[k][k] - M[i][k] * M[k][j]
                M[i][j] = _exact_div(num, prev)
                if len(M[i][j].terms) > max_terms:
                    raise Budget(_t("resultant.too_big", n=max_terms))
            M[i][k] = Poly(ring)
        prev = M[k][k]

    out = M[n - 1][n - 1]
    return out.scaled(Fraction(sign)) if sign < 0 else out


def _minor(matrix: list, drop_row: int, drop_col: int) -> list:
    return [[v for j, v in enumerate(row) if j != drop_col]
            for i, row in enumerate(matrix) if i != drop_row]


def eliminate(f: Poly, g: Poly, var: str):
    """Res_t(f, g), with A and B such that `Res = A*f + B*g`.

    Returns a dict carrying everything the certificate needs, including the
    two facts that decide how much the answer is worth: whether either leading
    coefficient in t can vanish, and whether the resultant is constant.
    """
    ring = f.vars
    k = _index_of(ring, var)
    n, m = _degree_in(f, k), _degree_in(g, k)
    if n < 1 or m < 1:
        raise NotEliminable(_t("resultant.degree_zero", var=var,
                               n=max(n, 0), m=max(m, 0)))

    fc, gc = coefficients_in(f, k), coefficients_in(g, k)
    S = sylvester(fc, gc)
    res = determinant(S)

    # The last row of the adjugate: u_i = (-1)^(i+N-1) * minor(S, i, N-1).
    # `u . (S v) = det(S)` with `v = (t^(N-1), ..., t, 1)`, and `S v` is
    # exactly the shifted copies of f and g -- which IS the Bezout identity.
    size = n + m
    u = []
    for i in range(size):
        minor = determinant(_minor(S, i, size - 1))
        u.append(minor if (i + size - 1) % 2 == 0 else minor.scaled(-1))

    tvar = Poly.var(ring, var)

    def _shifted(coeffs, top):
        out = Poly(ring)
        for idx, c in enumerate(coeffs):
            power = top - 1 - idx
            term = c
            for _ in range(power):
                term = term * tvar
            out = out + term
        return out

    A = _shifted(u[:m], m)
    B = _shifted(u[m:], n)

    return {
        "resultant": res,
        "A": A, "B": B,
        "deg_f": n, "deg_g": m,
        # Sufficiency needs a non-vanishing leading coefficient. When both can
        # vanish, `Res = 0` stops being enough and the certificate says so.
        "lead_f": fc[-1], "lead_g": gc[-1],
        "lead_f_constant": _is_constant(fc[-1]),
        "lead_g_constant": _is_constant(gc[-1]),
        "constant": _is_constant(res),
        "identically_zero": not res,
    }


def _is_constant(p: Poly) -> bool:
    return all(sum(e) == 0 for e in p.terms)


def check_identity(f: Poly, g: Poly, A: Poly, B: Poly, res: Poly) -> bool:
    """`Res == A*f + B*g`, by expanding. This is the whole verification."""
    return not (A * f + B * g - res)
