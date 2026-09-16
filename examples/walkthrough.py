"""The walkthrough's packing: a family of lists, and pairs taken from them.

See examples/WALKTHROUGH.md for the whole story. A "list" is a set; taking the
pair {a,b} from list j is an item; each pair may be used once in total and
each (list, element) incidence once.

    certo opt examples/walkthrough.py --gap --cert out/gap.json
    certo mixed examples/walkthrough.py --prove-optimal
"""
from certo import PackingSpec, SetFamily

FAMILY = SetFamily(5, [(0, 1), (0, 1, 2), (0, 1, 2, 3),
                       (0, 1, 3), (0, 2, 3, 4), (0, 4)])


def spec():
    return PackingSpec.lists(FAMILY, title="the walkthrough's canonical core")
