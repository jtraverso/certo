# One problem, end to end

Every other example shows one command. This shows one *problem*, from not
knowing the answer to holding an artefact a referee can check — which is the
only thing that explains what the tool is for.

The problem is small enough to follow and real enough to be worth asking. It
is the shape that dominates one research corpus this tool was built against:
**a family of lists, and pairs taken from them.**

---

## The problem

A **list** is a set. Given a family of lists, take pairs `{a,b}` out of them,
subject to two rules:

* a pair may be used **once in total**, across the whole family;
* within a list, each element may be used **once**.

How many pairs can be taken? Call the integral answer **ν** and the fractional
relaxation **μ\***. The question behind the question is whether they differ,
because a gap is where the combinatorics lives.

```python
from certo import PackingSpec, SetFamily

family = SetFamily(5, [(0, 1), (0, 1, 2), (0, 1, 2, 3),
                       (0, 1, 3), (0, 2, 3, 4), (0, 4)])
packing = PackingSpec.lists(family)
```

Three lines. Rebuilding that packing by hand is fifteen, and the constraint
that goes missing is always the second one.

---

## 0. Ask whether the question is well posed

Before any of it, for the price of reading the file:

```bash
certo lint examples/walkthrough.py
```

```
PackingSpec -- for `certo opt --gap / opt --by-type`
  [--] 20 items over 27 resources
  [--] item kinds: pair -- `opt --by-type` splits the optimum by these
  [--] `integer=False`: `opt` solves the RELAXATION, so the answer is mu*,
       not the packing number
  nothing that will bite.
  errors 0   warnings 0   notes 3
```

Notes, no errors, no warnings: nothing here will bite. The last note is the
one worth reading before section 1 rather than after — `opt` on this spec
answers μ*, and the packing number is a different question, which is what
section 2 is for.

It is worth running on a spec you just wrote for the same reason a compiler is
worth running before a test suite: the failures it catches are the ones that
would otherwise cost you the whole run. A contradictory hypothesis set, an
inductive step that starts after the base cases end, a predicate returning
`bool` when you expected a certificate.

---

## 1. Measure it — and get both numbers at once

```bash
certo opt examples/walkthrough.py --gap --cert out/gap.json
```

```
SATISFIABLE  [sat]
  integrality gap 1/2: mu* = 15/2, nu = 7
  13 resources carry positive load in the dual
  CONDITIONAL OPTIMUM: continuous optimum conditional on the selected skeleton;
  global MILP optimality not claimed
```

**μ\* = 15/2, not 7.5.** The difference is the whole point: `15/2` is a
number a paper can carry, `7.5` is a number that came out of a solver.

Read the last line. `ν = 7` is a design that **exists** — certo found it and
checked it — but at this stage it is not a *proved* integral optimum. The tool
says which of the two it has.

### What the certificate actually holds

```bash
certo verify out/gap.json
```

```
VALID  gap certificate (verified with a solver)
  [ok] the fractional optimum holds
  [ok] the integral design holds
  [ok] both halves are about the same packing
  [ok] the gap is the difference        (15/2 - 7 = 1/2)
  [ok] the relaxation is at least the integral optimum
  WARNING: nu here is a design that EXISTS, not a proven integral optimum --
  so the true gap may be smaller than the one reported.
```

The third check is the one worth pausing on. Two numbers from two runs are two
numbers; the certificate records that they are about **the same packing**,
which a folder of files cannot say.

---

## 2. Close it — prove the integral optimum

```bash
certo mixed examples/walkthrough.py --prove-optimal --cert out/optimal.json
```

```
PROVED  [unsat]
  OPTIMUM 7, PROVED: 73 nodes, 37 of them closed by a certificate
  73 nodes: 19 closed by bound, 18 infeasible, 0 fully fixed
```

Now `ν = 7` is proved, and the gap is exactly `1/2`. What makes it a proof
rather than a search log is that **every leaf carries a certificate** and the
tree is checked to cover the integer domain:

```
  [ok] the incumbent design exists and attains the optimum
  [ok] every branch has all its children
  [ok] every leaf is closed by a certificate
```

A leaf is closed for one of three reasons, each checkable by arithmetic: its
LP bound cannot beat the incumbent (exact dual), it is infeasible (a Farkas
ray — three dot products), or every variable is fixed so the LP *is* the
answer. **A tree with a missing child reads exactly like a complete one**,
which is why the covering check is not optional.

---

## 3. Understand it — where does the obstruction live?

```bash
certo sweep examples/setfamily_sweep.py --witnesses --cert out/orbits.json
```

Sweeping nearby families finds many that fail — and most of them are the same
failure relabelled:

```
  90 counterexamples, 2 up to symmetry
  orbits (of the counterexamples):
    5:01|02|13   x60   5:01|02|13, 5:01|02|14, 5:01|02|23
    5:01|02|34   x30   5:01|02|34, 5:01|03|24, 5:01|04|23
  minimal witness per orbit:
    5:01|02|13  x60  ->  2:0|1  (4 reductions)
    5:01|02|34  x30  ->  2:0|1  (4 reductions)
```

Ninety failures are **two objects**. That is the answer; the ninety were the
same answer told ninety times.

`SetFamily` supplies its own `key`, `canonical` and `reductions`, so the spec
declares `canonicalize="auto"` and `reduce="auto"` and nothing else.

---

## 4. Certify the algebra

The bound above suggests an identity about the weights. `ideal` settles
whether it follows from the constraints:

```bash
certo ideal examples/walkthrough_ideal.py --cert out/identity.json
```

```
PROVED  [unsat]
  the claim vanishes on every common root of the system, certified by 3 cofactors
```

Verification expands a product and compares coefficients. **No solver, no
algebra system** — a library that says "yes, it is in the ideal" leaves you
with its word; this leaves you with the polynomials.

---

## 5. Assemble it, and see what is still owed

```bash
certo compose examples/walkthrough_proof.py --cert out/proof.json
```

```
PROVED  [unsat]
  theorem assembled from 3 lemmas (1 derived and linked, 2 asserted)
  lemmas:
    gap_is_half      BRIDGE     *
    optimum_is_7     BRIDGE     *
    arithmetic       linked
  NOT needed: arithmetic
```

The last line is worth reading twice. Once the two bridges are in, the
arithmetic lemma is redundant — Z3 rederives it. `compose` reports that from
the final step's unsat core rather than from a guess, and it is the kind of
thing nobody notices by hand.

Two of the three are **bridges**: the packing computation is not a first-order
formula, and reading "this LP has optimum 15/2" as a statement about the
mathematics is a modelling step no checker can make. `compose` does not refuse
them — it names them, and repeats them every time the proof is verified.

That is the honest end state: **one artefact, with the boundary between what
was proved and what was assumed drawn explicitly**, rather than a folder of
certificates and a memory of how they fit.

---

## 6. Hand it on

```bash
certo export out/proof.json --lean --out Walkthrough.lean --manifest out/manifest.json
```

The Lean file carries `sorry` on **exactly the bridges** and nowhere else —
`compose` already computed that boundary. The manifest hashes every
certificate, so the Lean side can say which run it came from.

## 7. Ask where that leaves you

Six commands produced five certificates, and until now the only way to see
what the pile amounted to was to open them one at a time.

```bash
certo status out/
```

```
5 certificates under out
  branch_bound 1   gap 1   ideal 1   orbit_witnesses 1   proof 1

  RESULTS -- 3 certificates nothing else here builds on
  ideal            identity.json    tight loads force the gain
  orbit_witnesses  orbits.json      intersecting families of three pairs on five points
  proof            proof.json       the canonical core has integrality gap exactly 1/2

  STILL OWED -- 3 assumptions these results rest on
  gap.json: optimality
      "the integral side is conditional_optimum, so nu is a value reached,
       not a proved maximum"
  proof.json: gap_is_half
      "the exact LP dual gives the fractional optimum 15/2; reading that as a
       statement about this packing is what the encoding means"
  proof.json: optimum_is_7
      "branch and bound closed every leaf with a certificate and the tree
       covers the integer domain, so 7 is the integral optimum -- of the
       encoded packing"

  HOLLOW -- 1 claims that are valid and say less than they look like
  orbits.json: no evaluation of the 120 carries a certificate: replayable,
               not certified

  read, not verified. `certo status --verify` re-checks every one.
```

Three of the five are results; `gap.json` and `optimal.json` do not appear
there because the proof is standing on them.

Read the STILL OWED list against the walkthrough. The two `proof.json` entries
are the two modelling steps taken in section 5 — each legitimate, each written
down, neither findable six months later by opening files one at a time. The
third is why section 2 exists at all: `opt --gap` alone gives ν as a value
*reached*, and it took branch and bound to make it a maximum *proved*. Note
what is **not** listed: `optimal.json` is a branch-and-bound certificate, so
the optimality its own incumbent could not claim is the thing that certificate
proves, and status does not ask for it twice.

HOLLOW is the orbit sweep. The predicate returns `bool`, so the run is
replayable rather than certified — which `certo lint` would have said before
it ran, and which `verify` says every time afterwards.

---

## What this cost, and what it bought

Seven commands, about fifteen seconds of compute, most of it the branch and
bound. What you end up holding:

| | Established | How it checks |
|---|---|---|
| `μ* = 15/2` | exactly | exact LP dual, no solver needed |
| `ν = 7` | **proved optimal** | 73 certified nodes covering the integer domain |
| gap `= 1/2` | exactly | the subtraction, on two halves shown to match |
| 90 failures → 2 objects | up to relabelling | the orbit decomposition adds up |
| the identity | symbolically | expand a product, compare coefficients |
| the assembly | with bridges named | each lemma linked to what its certificate closes |

And the thing that is *not* established is written down in the same artefact,
in the same voice, rather than left to be remembered.

---

## Running it

```bash
python tests/run_examples.py
```

runs every example in this directory, including these, and verifies what each
one produces.
