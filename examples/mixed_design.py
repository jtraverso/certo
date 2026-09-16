"""mixed: a discrete skeleton found by search, certified by an exact LP.

The shape this exists for: a MILP chooses a discrete structure and a
compatible fractional packing at the same time. Here, four binary `y_i` each
reserving a slot, four continuous `q_i` packing inside what is left, a shared
capacity, and a cap on how many slots may be reserved.

What a proof of EXISTENCE needs is not that the choice was optimal -- it is
that the construction found REACHES A TARGET. So `mixed` does not certify the
MILP. It runs the search (CBC, heuristic, uncertified), freezes the discrete
part, and certifies the residual LP exactly:

    search -> freeze -> exact residual LP -> compare against the target

Three numbers come out and they are not the same number: what the design
ACHIEVES, the best the continuous part can do WITH THIS SKELETON, and the
relaxation bound over ALL skeletons. When the first meets the third, global
optimality falls out for free and is said; otherwise it is not claimed.

    certo mixed examples/mixed_design.py --cert out/mixed.json
    certo mixed examples/mixed_design.py --target 10
    certo verify out/mixed.json
"""
from fractions import Fraction

from certo import LPSpec


def spec():
    lp = LPSpec(sense="max", title="reserve slots, then pack what is left")
    for i in range(4):
        lp.variable("y{}".format(i), kind="binary")      # reserve slot i
        lp.variable("q{}".format(i))                     # pack fractionally
    lp.objective({**{"y{}".format(i): 2 for i in range(4)},
                  **{"q{}".format(i): 5 for i in range(4)}})
    for i in range(4):
        lp.constraint({"y{}".format(i): 1, "q{}".format(i): 1}, "<=", 1,
                      name="slot{}".format(i))
    lp.constraint({"q{}".format(i): 1 for i in range(4)}, "<=", Fraction(2, 3),
                  name="shared")
    lp.constraint({"y{}".format(i): 1 for i in range(4)}, "<=", 3,
                  name="reservations")
    return lp
