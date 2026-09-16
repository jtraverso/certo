"""number: a Mersenne prime, with the evidence attached.

2^31 - 1 is prime. `flint` will tell you that in microseconds and you will
have nothing to show for it. A Pratt certificate is the same fact plus the
reason: a witness generating (Z/n)^*, and a certificate for each prime factor
of n-1, recursively down to 2.

Checking the whole tree is 53 calls to `pow(a, e, n)`. That is the shape this
tool is built around -- expensive to find, trivial to verify.

Try n = 561, a Carmichael number: it passes the Fermat condition for most
bases, the order condition catches it, and `number` comes back REFUTED with no
certificate rather than a weaker one.

    certo number examples/number_mersenne.py --cert out/prime.json
    certo verify out/prime.json
    certo number --n 600851475143 --question factor
"""
from certo import NumberSpec


def spec():
    return NumberSpec(n=2 ** 31 - 1, question="prime",
                      title="2^31 - 1 is prime")
