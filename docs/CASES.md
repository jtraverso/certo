# Worked cases

Real problems, end to end. Each section is a place where the obvious version
of a command was wrong and the correction is worth knowing.

[Orbits you can check](#orbits-you-can-check) ·
[What a sweep establishes](#what-a-sweep-establishes) ·
[Parametric symmetry](#parametric-symmetry) ·
[Where parametric came from](#where-parametric-came-from) ·
[Mixed designs](#mixed-designs) ·
[Local loads](#local-loads) ·
[Packings](#packings) ·
[Exact duals on a degenerate vertex](#exact-duals-on-a-degenerate-vertex)

---

## Orbits you can check

A combinatorial search produces relabelled copies of one object by the
hundred. A sweep reporting 1,400 counterexamples where there are four
structural ones has not told you four things and buried them — it has told you
one thing 1,400 times and left the reading to you.

`canonicalize` collapses them. Hand over a function from item to a hashable
form, and a sweep reporting forty counterexamples reports one, forty times
over.

That asks to be believed. `canonicalize` is arbitrary Python, so *"these forty
share a canonical form"* is the spec's claim, and all a certificate could check
was that the decomposition's arithmetic held together:

```
  [ok] the orbits partition the domain  (3 orbits covering 10 of 10 items)
  [ok] each orbit has its own representative  (0 representatives appear twice)
  [ok] each representative belongs to its orbit
```

Those are worth having — a decomposition whose parts do not add up is wrong
whatever the group was — and none of them is the question.

### The other bargain

```python
labelling=lambda item: {source_point: label, ...}
```

Hand over the **permutation** instead of the form. certo applies it, the result
*is* the canonical form, and the permutation travels in the certificate:

```
[ok] every member of every orbit carries its permutation  (40 witnesses)
[ok] each member IS the representative relabelled, by re-applying the stored
     permutation  (40 re-applied, 0 carried but not decodable, failing: -)
WARNING: what the witnesses show is that members of an orbit are the SAME
object relabelled. They do not show that two different representatives are
different objects [...]
```

Declaring both is refused: one asks to be believed and the other asks to be
checked.

### Why hand it over at all

certo's own canonical form is exact and **refuses** rather than guessing. On a
vertex-transitive object it refuses immediately: a 1-factorisation of K6 has
fifteen points that all look alike, `15!` is 1,307,674,368,000, and knowing the
automorphism group does not rescue it — `|Aut|` is 120, so quotienting by all
of it still leaves 10,897,286,400 cosets.

Computing a canonical labelling well is a hard search that a tool built for it
does far better. So nauty finds the labelling, certo checks it, and the artefact
carries both — the same split `parametric` makes with its dual and `farkas`
with its multipliers. **There is no cap on this route, because nothing is
searched.**

Only the **counterexamples** are decomposed. The orbit structure of everything
that passed is rarely the question, and computing it on a large domain is not
free.

---

## What a sweep establishes

A sweep that passes and a sweep that passes *with certificates* are not the
same result, and the gap is wide.

| Level | What holds | When |
|---|---|---|
| **certified** | every evaluation carries its own certificate; the predicate is not trusted at all | the predicate returns `Outcome(ok, cert=...)` **and** `--cert-all` stores them |
| **reproducible** | the domain, its hash, and a verdict vector: re-running the predicate gives the same answers | a bare `bool` predicate — the common case |
| **recorded** | only the domain and its hash | the spec is gone, moved, or was never stamped |

```
$ certo sweep spec.py
FINITE SWEEP REPRODUCIBLE -- the predicate is NOT certified  [unsat]
  the predicate holds on all 3481 items (FINITE DOMAIN, not the theorem)
  !! 3481 of 3481 evaluations carry no certificate. The sweep is REPRODUCIBLE
  -- re-running the predicate gives the same answers -- but nothing here
  establishes that those answers are right.
```

The two caveats are independent. "Not the theorem" is about **generality**: a
finite domain was checked, not every `n`. "Not certified" is about **trust**:
nothing here says the predicate answered correctly. A passing sweep used to
state only the first, and a green banner over eleven thousand unchecked
booleans is where that does the most damage — there is no counterexample to go
and look at.

### Replay: the middle level, named

The certificate stores a **verdict vector** — one character per item, in
domain order — and its digest. `verify` re-runs the predicate and compares:

```
$ certo verify out/sweep.json
VALID  domain_sweep certificate (by re-running the spec, not by trusting its answers)
  [ok] the family hash matches
  [ok] re-running the predicate gives the same verdicts  (3481 evaluations, all identical)
  WARNING: 3481 of 3481 evaluations carry no certificate. Replaying them
  agrees, which makes the sweep reproducible; it does NOT make the
  predicate's answers verified.
```

This is the only check that catches **a predicate edited under a stable name**.
The domain hash cannot — the domain did not move — and the stored certificates
cannot, because there are none. When it disagrees it names the item:

```
  [XX] re-running the predicate gives the same verdicts
       (item a=1,b=1 (index 0) now answers differently)
```

Two consequences worth stating. Verification now costs a full re-run of the
predicate, which is the honest price of the claim. And the header says **"by
re-running the spec"** rather than "without a solver": replaying runs the
spec's own Python, which may well call a solver, so the old phrasing was the
same overclaim one level down.

---

## Parametric symmetry

A write-up does not symmetrise one program. It symmetrises `S(p,q)` and writes
the answer as a formula in `p` and `q` — and between the instances somebody ran
and the symbolic identity the proof uses there is a step. That step is
`reduce --parametric`.

A family is declared as orbits whose multiplicities are **polynomials**, and
rows that exist only under stated conditions:

```python
orbits = {"clique": C(p,2), "cross": p*q}
rows   = [("KKK", {"clique": 3},             ">=", 1, [p - 3]),
          ("KKI", {"clique": 1, "cross": 2}, ">=", 1, [p - 2, q - 1])]
```

**The objective is not declared.** Substituting one variable per orbit into
`Σ z_e` sums each orbit, so the objective *is* the multiplicities. Declaring it
separately would let the two disagree, and an objective that disagrees with the
orbit sizes is an accounting error no amount of solving catches.

**An orbit is present exactly where its multiplicity is positive** — a
measurement, not a convention. The split family has two edge orbits for `q ≥ 1`
and **one** for `q = 0`, because there are no cross edges to be an orbit of.

**The regimes are derived, not listed.** The row conditions cut parameter space
into the distinct programs that actually occur:

```
$ certo reduce --parametric examples/parametric_symmetry.py
PROVED  [unsat]
  the symbolic quotient agrees with the family at all 35 window points:
  2 orbits over parameters (p, q), in 4 regime(s) of the row conditions
  objects: 1/2*p^2 + p*q - 1/2*p
  regimes: ['(none)', 'KKI', 'KKK', 'KKK,KKI']
```

A piecewise closed form has one branch per regime, so a formula with three
branches over a program with four regimes is a formula missing a case. The
boundary is where the errors are.

### Two levels, kept apart

| Level | What it covers | Needs an instance? |
|---|---|---|
| symbolic | which orbits, which rows, what coefficients, which regimes; that the multiplicities account for every object | no |
| per instance | that the declared group really *has* these orbits at these sizes, and that the quotient averaging produces is the symbolic one evaluated there | yes, on a finite window |

The second does not become the first by adding points, and `verify` repeats
that every time. What the window buys is **falsifiability**: drop one condition
— carry `3x ≥ 1` into `p = 2`, where there are no triangles on three clique
vertices — and it is refuted at 7 of the 35 points, the first being `p=2, q=0`.
A multiplicity of `pq/2` instead of `pq` fails at 30; `p²/2` instead of
`C(p,2)` at all 35.

It says nothing about the **value**. Solve the quotient with `opt` at a point,
or bound it for every parameter with `parametric`, which is the command built
for that hand-off.

---

## Where parametric came from

A real instance, and the structure is worth seeing. A symmetrised LP solved
exactly for `p = 5..12` with a hand-written rational simplex gave duals that
are **piecewise constant with thresholds** — one vertex at `p = 6`, another
across `p = 7, 8, 9`, a third from `p = 10`. On each piece the bound is a
polynomial in `p` and the dual is fixed, which is exactly the shape
`certo parametric` certifies. The thresholds are part of the answer, not
something to smooth over.

### The cover shape came from the other direction

Three separate write-ups of the same argument, each reducing to a symmetrised
cover program over two, three or four edge orbits, each stating the value as a
minimum of named closed forms, and each finishing with *"duality completes the
proof"*.

What duality completes it **with** is one dual per branch and a check that each
stays feasible along its branch — a finite object nobody had written down, and
exactly a certificate.

```
$ certo parametric examples/parametric_cover.py
PROVED  [unsat]
  for all p >= 3, s >= 0, the optimum is at least 1/2*p^2 - 1/2*p
  sense: min
```

Two things change with a cover, and both are forced rather than chosen.

**The dual is not a constant.** In a packing the multipliers are rates, one
rational each. A cover's dual is itself a packing, and a packing of a growing
object grows with it — `C(p,2)` triangles, not `1/3`. So a dual entry may be a
polynomial, and `y ≥ 0` becomes the same shift test as every other row.

**A threshold in the value function is the dual's feasibility.** The example
certifies the branch `q ≥ p − 1` of a closed form that changes shape at
`q = p − 1`. Its one non-trivial row is

```
p q - 2 C(p,2)  =  p (q - p + 1)  =  p s   >=  0
```

which is non-negative exactly on that branch. The dual stops being feasible
precisely where the closed form changes branch — which is what a threshold in a
piecewise-linear value function *is*, seen from underneath. Each branch is its
own spec and its own certificate, because each is its own claim.

`examples/parametric_orbits.py` is the same thing one size up: four edge
orbits, five triangle types, three candidate covers, and the branch conditions
falling out of the dual as one residual row and one non-negativity.

---

## Mixed designs

A MILP that chooses a discrete structure *and* a compatible fractional packing
at the same time is a shape `opt` could not express at all: `LPSpec(integer=
True)` makes **every** variable integer, which is a different problem, not a
restriction of this one. Variables carry a kind instead:

```python
lp.variable("y17", kind="binary")     # reserve this triangle
lp.variable("q42")                    # pack fractionally inside what is left
```

For an **existence proof**, whether the discrete choice was optimal does not
matter — exhibiting a construction that reaches the target is the whole job. So
the flow is deliberately not "certify the MILP":

```
search (CBC, heuristic)  →  freeze the discrete part
                         →  residual LP over the continuous part
                         →  exact dual, exact everything
                         →  compare against the target
```

```
$ certo mixed examples/mixed_design.py --target 10
SATISFIABLE  [sat]
  certified design reaching 28/3, target 10
  achieved 28/3 = 6 discrete + 10/3 continuous | relaxation bound 28/3
  the achieved value meets the relaxation bound, so this IS the global optimum
```

### The check that makes it more than three files in a folder

```
$ certo verify out/mixed.json
  [ok] the full point satisfies every original constraint
  [ok] the residual LP's own certificate holds
  [ok] and that residual IS the original problem with this assignment substituted
```

Without that last one the sub-certificate could be about a *different* problem
— the same gap `compose` closes between a lemma and the statement it is used
for.

CBC's answer is a **guess until something checks it**: it returns `0.9999997`
for a binary as often as not, so the assignment is rounded and then verified
against the original constraints in exact arithmetic. A design that does not
survive that check is refused rather than reported.

### A shortfall is not an invalid certificate

A design that misses its target verifies as **VALID** with a warning. The
certificate is correct; the design is insufficient, and those are different
statements. Reading `INVALID` there would say something is broken when nothing
is.

Full MILP optimality — a branch-and-bound certificate with an exact dual or an
infeasibility proof at every leaf — is `certo mixed --prove-optimal`, and it is
a different and much larger thing than what an existence proof needs.

---

## Local loads

A packing certificate proves an optimum. The thing an argument usually needs
next is different: **and the design holds the bounds I put on each region, by
this much, and that one cost me this.**

```python
PackingSpec(
    items=..., capacities=1,
    loads=[("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2),
           ("within_B", {"p3": 1, "p4": 1, "p5": 1}, "<=", 5)],
)
```

```
$ certo opt examples/packing_with_loads.py
  EXACT optimum certified: 5 (denominator <= 1)
  2 declared loads, and what the design does to them:
    within_A         2 <= 2   BINDING
                     costs 1 per unit of bound -- relaxing it buys that much
    within_B         3 <= 5   slack 2
```

Read the second column. `within_A` is **binding** and its shadow price is 1:
relax that bound by one and the optimum goes up by exactly one. `within_B` has
slack 2, so it is not what is holding you back and tightening the argument
there buys nothing. That is the difference between a bound doing work and a
bound along for the ride — and it is free, because a load is a row and the dual
already priced it.

A capacity is part of the **encoding**; a load is part of the **argument**.
They are declared separately for that reason, and reported apart.

`verify` recomputes each achieved value from the primal rather than believing
the declared one, so a certificate that understates what a region used fails:

```
[XX] load `within_A` holds, and at the declared value   2 <= 2, slack 0
```

Loads take `<=`, `>=` or `==`. The last is exact preservation — *this region
carries exactly this much* — which is what "preserve these local loads" means
when the argument depends on the value rather than a ceiling.

Refused rather than accepted quietly: a weight on an item that is not in the
packing, and a load name that collides with a resource.

---

## Packings

Cliques competing for edges, blocks competing for points — the shape recurs,
and rebuilding the LP by hand each time is where mistakes hide.

```python
from certo import PackingSpec
from certo.graphs import Graph

def spec():
    g = Graph.from_edges(6, [...])
    return PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
```

`to_lp()` hands back an `LPSpec`, so exact rationals and the verifiable dual
come for free. **The dual is the load certificate**: constraint names are
resource names, so `y_r` reads as "the load on resource r" — usually the object
you actually wanted.

```
$ certo opt examples/packing_mixed.py --by-type
  mixed      25/2       EXACT optimum certified: 25/2
  K3         10         EXACT optimum certified: 10
  K4         25/2       EXACT optimum certified: 25/2
```

Whether mixing buys anything is the gap between the mixed optimum and the best
single kind. Here, on K6, it buys nothing over pure K4.

`PackingSpec(integer={"K3"})` puts the structural items in whole while the rest
stays a fractional relaxation, which is the common shape. On such a problem
`opt` reports **only the relaxation bound** and says so: rounding every variable
would turn a K4 weight of 1/6 into zero and report a design worth nothing. The
achievable value comes from freezing the discrete part and re-solving the rest,
which is [`certo mixed`](#mixed-designs).

---

## Exact duals on a degenerate vertex

`opt` reconstructs a rational primal and dual from a float solver and checks
them exactly. There is a regime where that cannot work: a **degenerate**
optimum, where many dual solutions are optimal and the one CBC returns need not
round onto any of them.

A user certified 56 LPs exactly and **3 needed the rational primal and dual
injected by hand** — all of them on symmetric solutions. That is not bad luck.
Symmetry produces degeneracy, CBC returns an arbitrary optimal dual, and
rounding *that particular one* need not be dual-feasible at all.

The fix is not a longer denominator ladder. Given an exact primal,
complementary slackness determines the dual: `yᵢ = 0` on every row with slack,
and `Σᵢ Aᵢⱼ yᵢ = cⱼ` for every `j` with `xⱼ > 0`. That is a linear system over
the tight rows, solved in `Fraction` with no floats anywhere. Where it
underdetermines the dual — more tight rows than active variables, which is
exactly what symmetry produces — the leftover freedom **is** the set of optimal
duals, so each choice is offered in turn.

```
max 2x + 3y   s.t.  x + y ≤ 1,  x + 2y ≤ 1,  x, y ≥ 0
```

Both rows are tight at the optimum and only one variable is active. Certifying
it works with **no usable dual from the solver at all**:

| what CBC returned | certified | dual used |
|---|---|---|
| nothing (`0, 0`) | yes | `(0, 2)` |
| nonsense (`7.3, -2.1`) | yes | `(0, 2)` |
| another vertex's dual | yes | `(0, 1.5)` → `(0, 2)` |

A derived dual is **not** trusted for being derived. It is a candidate, like a
rounded one, and it earns the certificate by passing the identical exact
`check_lp`. What changed is where candidates come from: the structure of the
problem rather than whatever a float solver landed on.

Past a handful of tight rows, enumerating bases is hopeless — on a realistic
exact cover with 98 rows, 49 of them tight and 7 active variables, that is
C(49, 7) candidates, about 10⁸. So past that, certo solves the dual outright
with a **two-phase simplex in exact rationals**: Bland's rule throughout, which
is slower than steepest-edge and cannot cycle. Termination matters more than
speed in a fallback that only runs when the cheap route has already failed.

Nothing it produces is trusted for being produced there. The result goes
through the same `check_lp` as a rounded guess, so a bug in it shows up as a
certificate that does not verify — never as a wrong one that does.
