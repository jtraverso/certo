"""Aritmetica racional exacta.

Los solvers LP trabajan en punto flotante y no hay forma de evitarlo: CBC
devuelve 10.66666656003499 donde la respuesta es 32/3, con un error de 2.5e-7
que es su tolerancia por defecto. Con eso no se puede afirmar igualdad
primal-dual, ni citar una constante en un paper, ni exportar a Lean.

La salida no es un solver exacto, es esta:

    1. resolver en flotante (rapido, aproximado);
    2. RECONSTRUIR racionales a partir de la solucion flotante;
    3. VERIFICAR exactamente en Fraction, y aceptar solo si verifica.

El paso 3 es lo que hace que el paso 2 pueda ser una heuristica sin que eso
comprometa nada: una reconstruccion mala no verifica y se rechaza. El
certificado resultante no depende de confiar en CBC.
"""
from __future__ import annotations

from fractions import Fraction

# Denominadores que se prueban, de menor a mayor. Los primeros cubren lo que
# aparece de verdad en combinatoria (tercios, doceavos, 71/600...); los
# ultimos son la red de seguridad.
DENOM_LADDER = (1, 2, 3, 4, 6, 8, 12, 24, 60, 120, 360, 720,
                10**3, 10**4, 10**5, 10**6)


def to_fraction(v) -> Fraction:
    """Cualquier numero -> Fraction exacta. Los float se toman tal cual."""
    if isinstance(v, Fraction):
        return v
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, str):
        return Fraction(v)
    return Fraction(v).limit_denominator(10**12)


def reconstruct(values, denom: int):
    """Redondea cada valor al racional mas cercano con denominador <= denom."""
    return [Fraction(v).limit_denominator(denom) for v in values]


def dot(u, v) -> Fraction:
    return sum((Fraction(a) * Fraction(b) for a, b in zip(u, v)), Fraction(0))


def serialize(x) -> str:
    """Fraction -> '32/3'. Exacto y legible; se relee con Fraction(s)."""
    f = to_fraction(x)
    return str(f.numerator) if f.denominator == 1 else "{}/{}".format(
        f.numerator, f.denominator)


def serialize_all(xs):
    return [serialize(x) for x in xs]


def parse_all(xs):
    return [Fraction(s) for s in xs]


# ---------------------------------------------------------------------------
# certificacion exacta de un LP:  max c.x  s.a.  A x <= b,  x >= 0
# ---------------------------------------------------------------------------


def check_lp(A, b, c, x, y, tol_free: bool = True) -> dict:
    """Comprueba optimalidad en Fraction. Sin tolerancias, sin epsilon.

    Devuelve los cuatro veredictos por separado para poder decir QUE falla.
    Si los cuatro son ciertos, x e y son optimos y el objetivo es exacto:
    dualidad debil da c.x <= b.y siempre, y la igualdad cierra el sandwich.
    """
    A = [[to_fraction(v) for v in row] for row in A]
    b = [to_fraction(v) for v in b]
    c = [to_fraction(v) for v in c]
    x = [to_fraction(v) for v in x]
    y = [to_fraction(v) for v in y]

    primal_nonneg = all(v >= 0 for v in x)
    primal_feasible = all(dot(A[i], x) <= b[i] for i in range(len(A)))
    dual_nonneg = all(v >= 0 for v in y)
    dual_feasible = all(
        sum((A[i][j] * y[i] for i in range(len(A))), Fraction(0)) >= c[j]
        for j in range(len(c))
    )
    cx, by = dot(c, x), dot(b, y)
    strong = cx == by

    return {
        "primal_nonneg": primal_nonneg,
        "primal_feasible": primal_feasible,
        "dual_nonneg": dual_nonneg,
        "dual_feasible": dual_feasible,
        "strong_duality": strong,
        "objective": cx,
        "dual_bound": by,
        "ok": all((primal_nonneg, primal_feasible, dual_nonneg,
                   dual_feasible, strong)),
    }


def solve_exact(rows, rhs):
    """Solve `M z = rhs` in Fraction, or None if it is singular.

    Gaussian elimination with partial pivoting on a non-zero entry -- with
    rationals there is no numerical reason to prefer a large pivot, only the
    need for a non-zero one. Returns one solution; an underdetermined system
    gets zeros in the free positions, which is what complementary slackness
    wants for a variable nothing pins down.
    """
    n = len(rows)
    if not n:
        return []
    m = len(rows[0])
    aug = [[Fraction(v) for v in row] + [Fraction(r)] for row, r in zip(rows, rhs)]

    where = [-1] * m          # which row ended up pivoting on each column
    r = 0
    for col in range(m):
        piv = next((i for i in range(r, n) if aug[i][col] != 0), None)
        if piv is None:
            continue
        aug[r], aug[piv] = aug[piv], aug[r]
        inv = Fraction(1) / aug[r][col]
        aug[r] = [v * inv for v in aug[r]]
        for i in range(n):
            if i != r and aug[i][col] != 0:
                f = aug[i][col]
                aug[i] = [a - f * b for a, b in zip(aug[i], aug[r])]
        where[col] = r
        r += 1
        if r == n:
            break

    # A row that reduced to `0 = c` with c non-zero means no solution at all.
    for i in range(n):
        if all(v == 0 for v in aug[i][:m]) and aug[i][m] != 0:
            return None
    return [aug[where[j]][m] if where[j] >= 0 else Fraction(0)
            for j in range(m)]


#: How many candidate bases to try before giving up. Degeneracy in practice
#: means a handful of tight rows; this is the guard against the case where it
#: does not, and hitting it is reported as "not certified", never as "wrong".
MAX_BASES = 400


def dual_candidates(A, b, c, x, cap=MAX_BASES):
    """Exact duals that complementary slackness allows, given an exact primal.

    For `max c.x` subject to `Ax <= b, x >= 0` at an optimal `x`:

      * a row with slack (`A_i . x < b_i`) has `y_i = 0`;
      * a variable off its bound (`x_j > 0`) has `sum_i A_ij y_i = c_j`.

    Those two do not always pin `y` down. On a DEGENERATE vertex -- more tight
    rows than active variables, which is exactly what symmetry produces -- the
    system is underdetermined, and the freedom left over IS the set of optimal
    duals CBC picks from arbitrarily. So this yields candidates: the full
    system first, then each choice of which tight rows carry the weight.

    None of them is trusted. `check_lp` decides, exactly, the same as it does
    for a rounded one. What changes is where candidates come from -- the
    structure of the problem instead of whatever a float solver landed on.
    """
    import itertools

    A = [[to_fraction(v) for v in row] for row in A]
    b = [to_fraction(v) for v in b]
    c = [to_fraction(v) for v in c]
    x = [to_fraction(v) for v in x]

    tight = [i for i in range(len(A)) if dot(A[i], x) == b[i]]
    active = [j for j in range(len(c)) if x[j] > 0]
    if not tight:
        # Nothing binds. The dual is zero, which is right when the optimum is
        # interior and rejected by check_lp when it is not.
        yield [Fraction(0)] * len(A)
        return

    def solve_over(rows_used):
        eqs = [[A[i][j] for i in rows_used] for j in active]
        rhs = [c[j] for j in active]
        sol = (solve_exact(eqs, rhs) if eqs
               else [Fraction(0)] * len(rows_used))
        if sol is None:
            return None
        y = [Fraction(0)] * len(A)
        for pos, i in enumerate(rows_used):
            y[i] = sol[pos]
        return y

    seen = set()

    def offer(y):
        if y is None:
            return None
        key = tuple(y)
        if key in seen:
            return None
        seen.add(key)
        return y

    first = offer(solve_over(tight))
    if first is not None:
        yield first

    # The degenerate case: choose which tight rows carry non-zero weight. A
    # basis has as many rows as there are active variables.
    k = len(active)
    if 0 < k < len(tight):
        for n, rows_used in enumerate(itertools.combinations(tight, k)):
            if n >= cap:
                break
            y = offer(solve_over(list(rows_used)))
            if y is not None:
                yield y


def dual_from_primal(A, b, c, x):
    """The first dual complementary slackness allows, or None.

    Thin wrapper over `dual_candidates` for callers that want one answer.
    It is a CANDIDATE: feasibility is not checked here.
    """
    return next(iter(dual_candidates(A, b, c, x)), None)


def certify(A, b, c, x_float, y_float, ladder=DENOM_LADDER):
    """Reconstruct and verify. Returns (x, y, report, denom) or (None, ...).

    Three passes, cheapest first, and every one of them ends at the same
    `check_lp`: a candidate is never trusted for where it came from.

      1. BOTH AT ONE RUNG. The common case, and the one that gives the
         simplest denominators -- which is what anyone citing the constant in
         a paper wants.

      2. DERIVE THE DUAL. On a degenerate vertex -- which is what symmetry
         produces -- CBC returns an arbitrary one of many optimal duals, and
         rounding that particular one need not be dual-feasible at all.
         Complementary slackness determines the dual from the primal instead,
         and where it underdetermines it, the choices ARE the optimal duals.

    Pass 1 runs first so nothing that already worked changes, digests
    included.

    Not here, deliberately: reconstructing `x` and `y` at INDEPENDENT rungs.
    It looks like an obvious win and it is not one. `limit_denominator` is
    monotone in accuracy, so a rung high enough for the harder of the two is
    high enough for both, and pass 1 already climbs to it. Measured before
    writing it off, on primals needing 1/3, 1/7 and 2/7 against duals needing
    1/2 and 3/11: every pair was exact at one shared rung.
    """
    last = None
    for denom in ladder:
        x = reconstruct(x_float, denom)
        y = reconstruct(y_float, denom)
        rep = check_lp(A, b, c, x, y)
        last = rep
        if rep["ok"]:
            return x, y, rep, denom

    # The primals worth pairing a dual against: feasibility is cheap and it
    # keeps the search below from running on a problem that is simply
    # infeasible.
    primals = []
    for dx in ladder:
        x = reconstruct(x_float, dx)
        if all(v >= 0 for v in x) and            all(dot(A[i], x) <= to_fraction(b[i]) for i in range(len(A))):
            primals.append((dx, x))

    # 2. Stop asking CBC what the dual is, and work it out. On a degenerate
    # vertex there are several optimal duals and CBC returns an arbitrary one;
    # here they are enumerated, and the exact check picks.
    for dx, x in primals:
        for y in dual_candidates(A, b, c, x):
            rep = check_lp(A, b, c, x, y)
            if rep["ok"]:
                return x, y, rep, dx
            last = rep

    return None, None, last, None


def fmt(x, max_denom: int = 10**6) -> str:
    """Muestra un racional como fraccion si es legible, si no como decimal.

    Una razon exacta como 25/27 se lee mucho mejor asi que 0.9259...; pero un
    valor que venia de un float tiene denominador astronomico y ahi la
    fraccion no dice nada.
    """
    f = to_fraction(x)
    if f.denominator <= max_denom:
        return serialize(f)
    return "{:.6g}".format(float(f))


def stats(values):
    """min, max, media y suma, en Fraction. Devuelve None si no hay valores."""
    if not values:
        return None
    fs = [to_fraction(v) for v in values]
    total = sum(fs, Fraction(0))
    return {"count": len(fs), "min": min(fs), "max": max(fs),
            "mean": total / len(fs), "sum": total}
