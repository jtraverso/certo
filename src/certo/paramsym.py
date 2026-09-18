"""The symbolic quotient: "by symmetry" for a FAMILY, not for an instance.

`reduce` checks the averaging argument on one program. That closes the bridge
where it stands, and leaves the one that matters open: a write-up does not
symmetrise `S(6,3)`, it symmetrises `S(p,q)` and writes the answer as a
formula. Between "I checked it for the instances I ran" and "the symbolic
identity the proof uses" there is a step, and it is exactly where a finite
check stops being evidence for the general statement.

WHAT IS DECLARED. A family is given as orbits with MULTIPLICITIES that are
polynomials in the parameters, and rows that exist only under stated
conditions:

    orbits = {"clique": C(p,2), "cross": p*q}
    rows   = [("KKK", {"clique": 3},            ">=", 1, [p - 3]),
              ("KKI", {"clique": 1, "cross": 2}, ">=", 1, [p - 2, q - 1])]

The objective is then not a separate declaration: it is the multiplicities.
Substituting one variable per orbit into `sum_e z_e` gives `sum_o |o| . x_o`,
and `|o|` is what the multiplicity polynomial says. Getting that wrong is an
accounting error that no amount of solving catches, which is why it is a
check here rather than an input.

AN ORBIT IS PRESENT EXACTLY WHERE ITS MULTIPLICITY IS POSITIVE, and that is
not a convention, it is the measurement. The split family has two edge orbits
for `q >= 1` and ONE for `q = 0`, because there are no cross edges to be an
orbit of. Writing "two orbits" and meaning it for every `q` is how a
degenerate case gets a constraint it has no right to.

THE SAME GOES FOR ROWS, and this is the part the corpus cares about most. A
triangle type that does not exist contributes no constraint, so the program's
SHAPE changes at the boundary -- and the value function changes with it. The
conditions are declared, the rows present at each parameter value are derived
from them, and a row appearing where its condition fails is refused. A tool
that carried `3x >= 1` into `p = 2` would report a value for a program with a
constraint about triangles that are not there.

TWO LEVELS, AND SAYING WHICH IS WHICH IS THE POINT.

  SYMBOLIC, for every parameter value in the region. The quotient's shape:
  which orbits, which rows, with what coefficients. The objective as the sum
  of the multiplicities. The regimes, as the distinct row sets the conditions
  cut parameter space into. None of this needs an instance.

  PER INSTANCE, on a declared finite window. That the declared group really
  has these orbits, that they really have these sizes, and that the quotient
  the averaging argument produces really is the symbolic one evaluated there.
  This is the part that needs the objects, and it is finite.

The second does not become the first by running more points. What it does is
make the first FALSIFIABLE: a multiplicity that is wrong, a condition that is
off by one, a regime boundary in the wrong place -- each one shows up as a
disagreement at some parameter value, and the window is where you look. The
step from the window to the region is named in the certificate and is not
claimed to be proved.
"""
from __future__ import annotations

from fractions import Fraction

from .i18n import t as _t
from .polynomials import Poly


class NotParametricSymmetry(ValueError):
    """Raised with what was wrong: a bare failure helps nobody."""


def as_poly(x, ring) -> Poly:
    """A coefficient, as a polynomial over the parameter ring."""
    if isinstance(x, Poly):
        if x.vars != tuple(ring):
            raise NotParametricSymmetry(
                _t("paramsym.wrong_ring", got=", ".join(x.vars),
                   want=", ".join(ring)))
        return x
    if isinstance(x, (int, Fraction)):
        return Poly.const(tuple(ring), x)
    raise NotParametricSymmetry(_t("paramsym.not_a_coefficient",
                                   value=repr(x)[:40]))


def evaluate(poly: Poly, values: dict) -> Fraction:
    """A polynomial at a parameter point, exactly."""
    out = Fraction(0)
    for exps, coef in poly.terms.items():
        term = Fraction(coef)
        for name, e in zip(poly.vars, exps):
            term *= Fraction(values[name]) ** e
        out += term
    return out


def _values(point, parameters) -> dict:
    if isinstance(point, dict):
        missing = [p for p in parameters if p not in point]
        if missing:
            raise NotParametricSymmetry(
                _t("paramsym.point_missing", names=", ".join(missing)))
        return {p: int(point[p]) for p in parameters}
    if len(point) != len(parameters):
        raise NotParametricSymmetry(
            _t("paramsym.point_arity", got=len(point), want=len(parameters)))
    return {p: int(v) for p, v in zip(parameters, point)}


# --- what the declaration says at one parameter value ----------------------


def sizes_at(spec, values) -> dict:
    """Every orbit's multiplicity at this point, whether or not it vanishes."""
    ring = tuple(spec.parameters)
    return {name: evaluate(as_poly(m, ring), values)
            for name, m in spec.orbits.items()}


def live_orbits(spec, values) -> list:
    """The orbits that are actually there: multiplicity strictly positive.

    A multiplicity that comes out NEGATIVE is not a small orbit, it is a wrong
    polynomial, and it is refused rather than clamped -- silently reading it
    as zero would hide exactly the accounting error this is here to catch.
    """
    out = []
    for name, size in sorted(sizes_at(spec, values).items()):
        if size < 0:
            raise NotParametricSymmetry(
                _t("paramsym.negative_multiplicity", orbit=name,
                   at=_point_text(values), value=str(size)))
        if size > 0:
            out.append(name)
    return out


def live_rows(spec, values) -> list:
    """The rows whose existence conditions all hold here.

    A row is also dropped when every orbit it mentions has vanished: a
    constraint over no variables is not a constraint, and keeping it would
    make an empty program infeasible instead of trivial.
    """
    ring = tuple(spec.parameters)
    present = set(live_orbits(spec, values))
    out = []
    for name, coeffs, sense, rhs, when in normalised_rows(spec):
        if any(evaluate(as_poly(g, ring), values) < 0 for g in when):
            continue
        if not any(o in present for o in coeffs):
            continue
        out.append(name)
    return out


def normalised_rows(spec) -> list:
    """Every row as `(name, coeffs, sense, rhs, conditions)`.

    A condition is a polynomial meant to be `>= 0`, which is the shape the
    corpus uses -- "present only when `p >= 3`" is `p - 3 >= 0`, and a
    condition on a derived quantity like `o = p - s` is written the same way.
    """
    out = []
    for row in spec.rows:
        if len(row) == 4:
            name, coeffs, sense, rhs = row
            when = ()
        elif len(row) == 5:
            name, coeffs, sense, rhs, when = row
        else:
            raise NotParametricSymmetry(
                _t("paramsym.bad_row", row=repr(row)[:60]))
        if sense not in (">=", "<="):
            raise NotParametricSymmetry(
                _t("paramsym.bad_sense", name=name, sense=sense))
        unknown = [o for o in coeffs if o not in spec.orbits]
        if unknown:
            raise NotParametricSymmetry(
                _t("paramsym.unknown_orbit", name=name,
                   names=", ".join(sorted(unknown))))
        out.append((name, dict(coeffs), sense, rhs,
                    tuple(when) if not isinstance(when, Poly) else (when,)))
    return out


def program_at(spec, values):
    """The symbolic quotient, evaluated at one parameter point.

    One variable per LIVE orbit, the objective coefficient of each being its
    multiplicity -- which is what substituting `z_e = x_orbit(e)` into the
    original objective does, and the reason the objective is derived here
    rather than declared.
    """
    from .spec import LPSpec

    ring = tuple(spec.parameters)
    sizes = sizes_at(spec, values)
    orbits = live_orbits(spec, values)
    keep = set(live_rows(spec, values))

    out = LPSpec(sense=spec.sense,
                 title="{} at {}".format(spec.title or "quotient",
                                         _point_text(values)))
    for name in orbits:
        out.variable("orbit_" + name, 0, None)
    out.objective({"orbit_" + n: sizes[n] for n in orbits if sizes[n]})

    for name, coeffs, sense, rhs, _when in normalised_rows(spec):
        if name not in keep:
            continue
        row = {"orbit_" + o: evaluate(as_poly(c, ring), values)
               for o, c in coeffs.items() if o in set(orbits)}
        row = {k: v for k, v in row.items() if v}
        out.constraint(row, sense, evaluate(as_poly(rhs, ring), values),
                       name=name)
    return out


def _point_text(values) -> str:
    return ", ".join("{}={}".format(k, v) for k, v in sorted(values.items()))


# --- the regimes: how the conditions cut parameter space --------------------


def regimes(spec, window) -> dict:
    """The distinct row sets the conditions produce, and where each holds.

    A piecewise closed form has one branch per regime, and the branches of the
    write-up should BE these -- so listing them is the first thing to compare
    a formula against.
    """
    out: dict = {}
    for point in window:
        values = _values(point, spec.parameters)
        key = ",".join(live_rows(spec, values)) or "(none)"
        out.setdefault(key, []).append(values)
    return out


# --- the instance side ------------------------------------------------------


def orbit_sizes_of(cert_payload) -> dict:
    """The real orbit sizes, read off a `reduce` certificate."""
    return {i: len(part) for i, part in
            enumerate(cert_payload["orbits"])}


def compare_at(spec, values, limits=None) -> dict:
    """Build the instance, symmetrise it, and see whether the declaration
    describes what came out.

    Three things can disagree and they are reported apart, because they are
    three different mistakes: the orbits could be the wrong SHAPE, the
    multiplicities could be the wrong SIZE, and the rows present could be the
    wrong SET.
    """
    from . import symmetry, tree
    from .engines import algebra
    from .spec import SymmetrySpec

    if spec.instance is None:
        raise NotParametricSymmetry(_t("paramsym.no_instance"))

    built = spec.instance(**values)
    try:
        program, generators = built
    except (TypeError, ValueError):
        raise NotParametricSymmetry(
            _t("paramsym.instance_shape", at=_point_text(values))) from None

    out = {"point": values, "notes": []}
    want_sizes = {o: int(s) for o, s in sizes_at(spec, values).items()}
    want_rows = live_rows(spec, values)
    out["declared_sizes"] = want_sizes
    out["declared_rows"] = want_rows

    if not generators:
        # The trivial group has every orbit a singleton. Sound and useless,
        # and reporting it as agreement would be worse than refusing.
        out["ok"] = False
        out["notes"].append(_t("paramsym.trivial_group",
                               at=_point_text(values)))
        return out

    res = algebra.reduce_symmetry(
        SymmetrySpec(lp=program, generators=generators), limits)
    if res.certificate is None:
        out["ok"] = False
        out["notes"].append(res.detail)
        return out

    payload = res.certificate.payload
    got_sizes = sorted(len(part) for part in payload["orbits"])
    out["actual_sizes"] = got_sizes
    out["actual_orbits"] = len(payload["orbits"])
    # The instance was built from the OBJECTS, so its variable count is an
    # independent number: the multiplicities have to add up to it. Comparing
    # the polynomial sum against itself would be a check with no content.
    out["objects"] = len(program.var_names)

    # 1. the multiplicities, as a multiset of sizes and as a total
    total = sum(want_sizes.values())
    if total != out["objects"]:
        out["notes"].append(_t("paramsym.objects_differ",
                               at=_point_text(values), want=str(total),
                               got=out["objects"]))
    expected = sorted(s for s in want_sizes.values() if s > 0)
    if expected != got_sizes:
        out["notes"].append(_t("paramsym.sizes_differ",
                               at=_point_text(values),
                               want=", ".join(map(str, expected)) or "-",
                               got=", ".join(map(str, got_sizes)) or "-"))

    # 2. the rows: the symbolic program against the one averaging produced
    quotient = tree.spec_of(payload["quotient"])
    symbolic = program_at(spec, values)
    same, why = _same_program(symbolic, quotient)
    out["actual_rows"] = len(quotient.cons)
    if not same:
        out["notes"].append(_t("paramsym.program_differs",
                               at=_point_text(values), why=why))

    out["ok"] = not out["notes"]
    _ = symmetry
    return out


def _same_program(symbolic, actual):
    """Two programs are the same when their rows are, as multisets.

    Variable NAMES cannot be compared -- `reduce` names an orbit by its
    position and the declaration names it by what it is -- so what travels is
    the shape: the objective coefficients and the rows, each as a sorted tuple
    of coefficients against the same ordering of the objective.
    """
    def fingerprint(prog):
        order = sorted(prog.var_names,
                       key=lambda v: (Fraction(prog.obj.get(v, 0)), v))
        pos = {v: i for i, v in enumerate(order)}
        obj = tuple(Fraction(prog.obj.get(v, 0)) for v in order)
        rows = sorted(
            (tuple(sorted((pos[v], str(Fraction(c)))
                          for v, c in coeffs.items() if Fraction(c))),
             sense, str(Fraction(rhs)))
            for _n, coeffs, sense, rhs in prog.cons)
        return obj, rows

    def render(row):
        coeffs, sense, rhs = row
        body = " + ".join("{}*x{}".format(c, i) for i, c in coeffs) or "0"
        return "{} {} {}".format(body, sense, rhs)

    a_obj, a_rows = fingerprint(symbolic)
    b_obj, b_rows = fingerprint(actual)
    if a_obj != b_obj:
        return False, _t("paramsym.objective_differs",
                         want=", ".join(str(c) for c in a_obj),
                         got=", ".join(str(c) for c in b_obj))
    if a_rows != b_rows:
        # Saying HOW MANY rows differ is no help when the counts match and the
        # coefficients do not, which is the commonest way to mistype a row.
        only_declared = [r for r in a_rows if r not in b_rows]
        only_actual = [r for r in b_rows if r not in a_rows]
        return False, _t(
            "paramsym.rows_differ",
            want=len(a_rows), got=len(b_rows),
            declared="; ".join(map(render, only_declared[:2])) or "-",
            actual="; ".join(map(render, only_actual[:2])) or "-")
    return True, ""


# --- the whole thing --------------------------------------------------------


def certify(spec, limits=None) -> dict:
    """The symbolic quotient, and the window that makes it falsifiable."""
    if not spec.parameters:
        raise NotParametricSymmetry(_t("paramsym.no_parameters"))
    if not spec.orbits:
        raise NotParametricSymmetry(_t("paramsym.no_orbits"))
    if not spec.window:
        raise NotParametricSymmetry(_t("paramsym.no_window"))

    ring = tuple(spec.parameters)
    rows = normalised_rows(spec)
    window = [_values(p, spec.parameters) for p in spec.window]

    points = []
    for values in window:
        got = compare_at(spec, values, limits)
        points.append({
            "point": values,
            "ok": got["ok"],
            "sizes": got["declared_sizes"],
            "rows": got["declared_rows"],
            "orbits": got.get("actual_orbits"),
            "objects": got.get("objects"),
            "notes": got["notes"],
        })

    by_regime = regimes(spec, spec.window)
    total = Poly(ring)
    for m in spec.orbits.values():
        total = total + as_poly(m, ring)

    return {
        "parameters": list(ring),
        "orbits": {n: as_poly(m, ring).serialize()
                   for n, m in spec.orbits.items()},
        "rows": [{"name": n,
                  "coefficients": {o: as_poly(c, ring).serialize()
                                   for o, c in coeffs.items()},
                  "sense": sense,
                  "rhs": as_poly(rhs, ring).serialize(),
                  "when": [as_poly(g, ring).serialize() for g in when]}
                 for n, coeffs, sense, rhs, when in rows],
        "sense": spec.sense,
        "objects": total.serialize(),
        "objects_text": str(total),
        "points": points,
        "regimes": {key: len(vals) for key, vals in sorted(by_regime.items())},
        "checked": len(points),
        "failed": [p["point"] for p in points if not p["ok"]],
        "ok": all(p["ok"] for p in points),
    }
