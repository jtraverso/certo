"""Get rid of a variable, and see what that leaves you.

Two equations, two unknowns, and only one of them interesting:

    t^3 + s*t + 1 = 0
    t^2 - s       = 0

`t` is scaffolding. What you want is the condition on `s` for the pair to have
a common solution at all -- and that is the RESULTANT.

    $ certo eliminate examples/eliminate_parameter.py
    SATISFIABLE  [sat]
      eliminated t. A common root exists only where this vanishes: -4*s^3 + 1

You can check this one by hand in a minute, which is the point of choosing it.
Substitute `t^2 = s` into the first equation:

    t^3 + s*t + 1 = t * t^2 + s*t + 1 = t*s + s*t + 1 = 2*s*t + 1

so a common root needs `t = -1/(2s)`. Feed that back into `t^2 = s`:

    1/(4*s^2) = s      hence      4*s^3 = 1

which is what came out, up to the sign convention on the determinant. Nobody
had to trust the tool to get there -- and for a pair of degree 7 it would not
have been a minute.

WHAT THE CERTIFICATE CARRIES is not the number but the identity:

    Res(f, g) = A*f + B*g

with A and B polynomials. Computing a resultant is a determinant over a
polynomial ring; checking one is expanding two products and subtracting. That
gap is the whole reason this travels as a certificate rather than as "the
algebra system agreed". `certo verify` does the expansion, in exact rationals,
with no solver.

AND WHAT IT DOES NOT SAY, which `verify` repeats every time:

  `Res = 0` is NECESSARY for a common root, over any field.

  It is SUFFICIENT over an algebraically closed field, and only where the
  leading coefficients in `t` do not both vanish. Over the REALS a vanishing
  resultant can mean a common complex root and nothing more. Here the leading
  coefficients are 1 and 1, so that caveat is inert -- and the certificate
  records that, rather than leaving you to notice.

For more than two equations this is the wrong command: iterating resultants
pairwise introduces extraneous factors that nothing here could certify away.
`certo ideal` is the right one, and it answers a different question -- what
follows from the system, rather than what is left when a variable goes.
"""
import z3

from certo import EliminateSpec


def spec():
    s, t = z3.Reals("s t")
    return EliminateSpec(
        variables=["s", "t"],
        equations=[t ** 3 + s * t + 1, t ** 2 - s],
        eliminate="t",
        title="what must hold of s for these two to share a root in t",
    )
