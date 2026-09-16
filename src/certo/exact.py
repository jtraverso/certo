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


def certify(A, b, c, x_float, y_float, ladder=DENOM_LADDER):
    """Reconstruye y verifica. Devuelve (x, y, informe, denom) o (None,...).

    Sube por la escalera de denominadores y se queda con el PRIMERO que
    verifica exactamente: asi el resultado sale con el denominador mas simple
    que funciona, que suele ser el que uno quiere citar.
    """
    last = None
    for denom in ladder:
        x = reconstruct(x_float, denom)
        y = reconstruct(y_float, denom)
        rep = check_lp(A, b, c, x, y)
        last = rep
        if rep["ok"]:
            return x, y, rep, denom
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
