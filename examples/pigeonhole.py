"""cases: the pigeonhole principle PHP(n+1, n).

n+1 pigeons in n holes, each pigeon in exactly one hole and no hole with two
pigeons. Unsatisfiable for every n.

The classic instance with exponential resolution proofs (Haken 1985), so it
is a good way to watch the proof grow with n and find where your budget runs
out.

    certo cases examples/pigeonhole.py --cert out/php.json
"""
from certo import CNF, CNFSpec

N = 5  # holes; there are N+1 pigeons


def spec():
    cnf = CNF(title="PHP({}, {})".format(N + 1, N))

    def p(bird, hole):
        return cnf.var("p{}_{}".format(bird, hole))

    for bird in range(N + 1):
        cnf.at_least_one([p(bird, h) for h in range(N)])
    for hole in range(N):
        cnf.at_most_one([p(b, hole) for b in range(N + 1)])

    return CNFSpec(cnf=cnf, title="pigeonhole principle", expect="unsat",
                   meta={"pigeons": N + 1, "holes": N})
