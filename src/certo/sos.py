"""Sums of squares: a floating-point search, an exact certificate.

I argued twice in this project's own notes that SOS was not worth having
because an SDP is solved in floating point and an inexact certificate is not
citable. That objection was wrong, or rather it was aimed at the wrong half.
It is the same objection that would rule out `opt`, and `opt` answers it:
solve numerically, RECONSTRUCT rationals, and re-verify exactly. The floating
point is a search heuristic. The certificate is exact or it is not emitted.

So the pipeline is:

  1. Write `p = z^T G z` for the monomial vector z. That is a LINEAR condition
     on G, an affine subspace; `p` is a sum of squares iff some G in it is
     positive semidefinite.
  2. Find a numeric G by alternating projections -- project onto the affine
     subspace, project onto the PSD cone by clipping eigenvalues, repeat.
     Slow and dumb next to an interior-point method, and it needs no SDP
     solver, which matters because there is not one here.
  3. Round G to rationals and project back onto the affine subspace EXACTLY,
     in `Fraction`. The rounding usually breaks positive semidefiniteness,
     which is why the next step is not optional.
  4. Exact LDL^T with symmetric pivoting. If every pivot is >= 0, the
     decomposition IS the sum of squares: `p = sum d_i (l_i . z)^2`.
  5. Expand it and compare with `p`, coefficient by coefficient.

Step 5 is the certificate. Steps 1-4 are how it was found, and a reader never
has to care. What travels is a list of rational coefficients and rational
linear forms, and checking it is multiplying polynomials.

Where it stops: an SOS decomposition proves `p >= 0` everywhere. The converse
fails from degree 4 in 3 variables (Motzkin), so "no SOS found" is never
"p takes a negative value" -- it is `unknown_solver`, like everything else
here that searched and came back empty.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations_with_replacement

from .i18n import t
from .polynomials import Poly


class NoBackend(RuntimeError):
    """numpy is not installed, so there is nothing to search with."""


def monomial_basis(nvars: int, half_degree: int) -> list:
    """Every monomial of degree <= d, as exponent tuples. The vector z."""
    out = [tuple([0] * nvars)]
    for deg in range(1, half_degree + 1):
        for combo in combinations_with_replacement(range(nvars), deg):
            e = [0] * nvars
            for i in combo:
                e[i] += 1
            out.append(tuple(e))
    return sorted(set(out), key=lambda e: (sum(e), e))


def _pairs(basis):
    """Which (i, j) contribute to each monomial of z z^T."""
    index = {}
    for i, a in enumerate(basis):
        for j, b in enumerate(basis):
            key = tuple(x + y for x, y in zip(a, b))
            index.setdefault(key, []).append((i, j))
    return index


# ---------------------------------------------------------------------------
# the numeric search
# ---------------------------------------------------------------------------


def search(p: Poly, basis, iterations=600, tol=1e-9):
    """Alternating projections onto {G : z^T G z = p} and the PSD cone.

    Not an SDP solver and not pretending to be one: no optimality, no duality,
    no certificate of infeasibility. It only has to land close enough that
    rounding survives, and for the sizes a write-up contains it does.
    """
    try:
        import numpy as np
    except ImportError:
        raise NoBackend(t("sos.no_numpy"))

    index = _pairs(basis)
    n = len(basis)
    target = {e: float(c) for e, c in p.terms.items()}

    def to_affine(G):
        """Spread each monomial's required coefficient over its cells."""
        H = G.copy()
        for mono, cells in index.items():
            want = target.get(mono, 0.0)
            got = sum(H[i, j] for i, j in cells)
            delta = (want - got) / len(cells)
            for i, j in cells:
                H[i, j] += delta
        return (H + H.T) / 2

    def to_psd(G):
        w, V = np.linalg.eigh((G + G.T) / 2)
        return (V * np.clip(w, 0.0, None)) @ V.T

    G = to_affine(np.zeros((n, n)))
    for _ in range(iterations):
        H = to_psd(G)
        G2 = to_affine(H)
        if np.max(np.abs(G2 - G)) < tol:
            G = G2
            break
        G = G2
    return to_psd(G)


# ---------------------------------------------------------------------------
# exact rounding and decomposition
# ---------------------------------------------------------------------------


def _round(G, denom: int):
    n = len(G)
    return [[Fraction(round(float(G[i][j]) * denom), denom) for j in range(n)]
            for i in range(n)]


def project_exact(M, basis, p: Poly):
    """Push a rounded matrix back onto `z^T G z = p`, in exact arithmetic.

    Rounding almost never lands on the affine subspace, and a Gram matrix that
    is off by 1e-9 does not represent `p` -- it represents something else. The
    correction is spread evenly over the cells of each monomial, which keeps
    the matrix symmetric and is the same move the numeric step makes.
    """
    index = _pairs(basis)
    out = [row[:] for row in M]
    for mono, cells in index.items():
        want = p.terms.get(mono, Fraction(0))
        got = sum(out[i][j] for i, j in cells)
        delta = Fraction(want - got, len(cells))
        for i, j in cells:
            out[i][j] += delta
    n = len(out)
    return [[(out[i][j] + out[j][i]) / 2 for j in range(n)] for i in range(n)]


def ldl(M):
    """Exact LDL^T with the rows in order. Returns (D, L) or None if not PSD.

    Bailing out on the first negative pivot rather than continuing is the
    point: the question is whether this matrix is a sum of squares, and one
    negative pivot answers it.
    """
    n = len(M)
    A = [row[:] for row in M]
    L = [[Fraction(1) if i == j else Fraction(0) for j in range(n)]
         for i in range(n)]
    D = [Fraction(0)] * n
    for k in range(n):
        D[k] = A[k][k]
        if D[k] < 0:
            return None
        if D[k] == 0:
            # A zero pivot is fine only if its whole column is zero; otherwise
            # the matrix is indefinite and no amount of pivoting saves it.
            if any(A[i][k] != 0 for i in range(k + 1, n)):
                return None
            continue
        for i in range(k + 1, n):
            L[i][k] = A[i][k] / D[k]
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                A[i][j] -= L[i][k] * D[k] * L[j][k]
    return D, L


def decomposition(D, L, basis, variables):
    """(coefficient, linear form) per square, dropping the zero pivots."""
    n = len(D)
    out = []
    for k in range(n):
        if D[k] == 0:
            continue
        form = Poly(variables)
        for i in range(k, n):
            if L[i][k]:
                form = form + Poly(variables, {basis[i]: L[i][k]})
        if form:
            out.append((D[k], form))
    return out


def expand(terms, variables) -> Poly:
    """sum d_i * q_i^2. The whole verification, in one line."""
    out = Poly(variables)
    for d, q in terms:
        out = out + (q * q).scaled(d)
    return out


DENOMS = (1, 2, 6, 12, 60, 360, 2520, 10**4, 10**6, 10**8)


def certify(p: Poly, half_degree=None, iterations=600):
    """Find an exact SOS decomposition of `p`, or None.

    The denominator ladder is the same idea as `opt`'s rational
    reconstruction: try the simple denominators first, because a certificate
    with 1/2 in it is one a person can read and a certificate with
    1/99991 in it is one they will not check.
    """
    if p.degree % 2:
        return None, t("sos.odd_degree", d=p.degree)
    d = half_degree if half_degree is not None else max(p.degree // 2, 1)
    basis = monomial_basis(len(p.vars), d)

    G = search(p, basis, iterations=iterations)
    for denom in DENOMS:
        M = project_exact(_round(G, denom), basis, p)
        res = ldl(M)
        if res is None:
            continue
        terms = decomposition(res[0], res[1], basis, p.vars)
        if expand(terms, p.vars) == p:
            return (terms, basis, denom), ""
    return None, t("sos.no_rounding", n=len(DENOMS))


def serialize(terms) -> list:
    return [{"coef": str(d), "form": q.serialize()} for d, q in terms]


def parse(variables, data) -> list:
    return [(Fraction(x["coef"]), Poly.parse(variables, x["form"]))
            for x in data]
