# Changelog

Notable changes per release. Dates are ISO. This project uses semantic
versioning; while the major is 0, a minor bump may change a certificate
payload — each such change says so and what still reads the old shape.

## [Unreleased]


## [0.9.1] — 2026-09-18

Four problems a user reported against 0.9.0, and one of them contradicted a
claim in 0.9.0's own release notes.

### `status` never opened a Lean file

0.9.0 said, of removing the Lean exporters: *"detection of hollow statements
survives — `certo status` and `hollow_count` still find a `theorem X : True`
in a file certo did not write"*. **That was false.** `status` read
certificates and never opened a `.lean`; `hollow_count` existed and nothing
called it on a user's files. A `theorem from_core : True` sat in a project
untouched while the report said everything was fine — and it compiles, carries
no `sorry`, and passes an axiom audit, so nothing else was going to catch it
either.

```
$ certo status .
no certificates under . (0 files were not certificates)
1 Lean statement(s) here state True and nothing else. Each one compiles,
carries no `sorry`, and passes an axiom audit, so every gate a formalisation
runs calls it green:
  Old.lean:3  from_core
```

It exits **1**: a directory with no certificates and a hollow theorem is the
worst case, not the empty one. `.lake` build trees are skipped, because
walking Mathlib turns a status call into a minute.

### `pip show certo` reported a version three releases old

Two causes, and the second is the one that matters.

The version was declared twice — in `pyproject.toml` and in `__init__.py` —
so a release had to edit both and they drifted. It is now declared once, in
`__init__.py`, with `pyproject.toml` reading it.

But the *mechanism* is worse: on Windows pip cannot replace a file another
process holds open, and `certo-mcp.exe` is held for as long as the MCP server
runs. `pip install -e .` from an editor with the server attached aborts
part-way, renames the old distribution to `~`-something, and leaves nothing
installed under the real name. Reproduced accidentally while fixing this —
the same reinstall failed the same way and left the package unimportable.

`certo doctor` now reports both: a leftover `~` directory with what to do
about it, and a disagreement between the installed metadata and the running
code. `certo --version` says so too, since that is where somebody looks.
`__version__` is deliberately *not* read from the metadata: a stale install
would then make the CLI report the old number confidently, which is worse than
reporting a disagreement.

### `certo --help` stayed alive indefinitely

Not certo. Measured here:

| | |
|---|---|
| bare interpreter | **1.30 s** |
| `python -S` | **0.24 s** |
| importing `certo.cli` | 0.08 s |

The rest is `site` running every `.pth` in site-packages before a single line
of certo executes, and one of them loads a certificate-store shim that reaches
for the system trust store — which on a corporate network can block.

certo cannot fix it, so `doctor` names it instead, and the check is the
symptom bounded: if a bare interpreter does not return inside the timeout,
*that* is the report. Only `.pth` files that begin with `import` are counted;
one that merely adds a path costs nothing.

### Still open

The manual transcription point between Lean data and the Python matrix. Not
touched.


## [0.9.0] — 2026-09-18

Four new commands, three defects fixed, and one deliberate removal that is
listed first because it is what a user notices first.

### REMOVED: `export --lean` now emits one thing

certo emits Lean for a **linear Farkas certificate** and for nothing else.
The exporters for unsat cores, compose proofs, classifications, symbolic
quotients and equitable quotients are gone.

**Why.** Compiling generated files against a real Mathlib for the first time
showed that the risk was never in the mathematics. The equitable-quotient
exporter — a structure with fields, three theorems and typeclass binders —
produced a wall of errors in four minutes, and *every one of them was in the
scaffolding while none was in the data*. Rewriting it as pure data got it
compiling in 12.8 seconds, and it was still removed: certo's job is the step
*before* the proof assistant, and what a formalisation needs from a session of
exploration is the numbers and the statement, which the certificate already
carries. Somebody formalising a result writes the structure their own project
wants and cannot use certo's namespace layout anyway.

**The rule, now written into `leanexport` itself:**

> emit Lean only when the output is a **small self-contained artefact whose
> content IS the certificate's data**, closed by a tactic that **decides** the
> fragment its goal lives in

A linear Farkas certificate is exactly that: the multipliers are already
verified exactly, `linarith` is complete for linear arithmetic over an ordered
field, and the file is twenty-seven lines with no `sorry`. The sizes made the
point on their own — the exporters that worked emitted 27, 39, 110 and 232
lines; the one that did not had 595.

**`NotExportable`** makes it a mechanism rather than an intention. A
*nonlinear* Farkas certificate would close with `nlinarith`, which is a
heuristic, so it is refused with the reason and a pointer at the multipliers
instead of written hopefully. The CLI declines cleanly rather than crashing.

**What this costs, stated plainly.** Two things shipped in 0.8 in response to
a user's reported defects go with it: the integer export closing with `omega`,
and the `HOLLOW` marking of statements certo could not render. The *detection*
of hollow statements survives — `certo status` and `hollow_count` still find a
`theorem X : True` in a file certo did not write, which is the case that
matters, since such a theorem compiles, carries no `sorry`, and passes an
axiom audit. Eighteen tests went with the removed code.

**`--check` is not a release gate**, and `tests/run_lean.py` is explicitly
outside the suite. Building against Mathlib costs minutes, depends on a
toolchain version, and fails in ways that say nothing about whether certo's
mathematics is right.

### `quotient`: the reduction as an equivalence

Asked for after `reduce --parametric`: *"demostrar algo más preciso que los
óptimos coinciden: una equivalencia constructiva entre los valores factibles
del LP físico y los de su cociente"*. The criticism was right. Comparing two
computed optima does not show a reduction is correct — it shows two numbers
agreed, which is also what a wrong reduction with a compensating error does.

So the claim is now the equivalence itself: the physical program and the
quotient have the **same set of attainable values**, by an explicit projection
`z_j = Σ_{C∈j} x_C` and lifting `x_C = z_j / M_j`, both preserving the
objective, with `Proj(Lift(z)) = z`. Equality of optima is a corollary and no
duality is needed to get it.

**The partition is an input, and the group is gone.** A group action produces
a partition; so does a colour refinement; so does somebody who knows what the
classes are. Separating the finite-sum core from the group theory is what a
proof assistant wants anyway, and it means a partition nobody can name a group
for is still certifiable. `reduce` becomes one route to the input rather than
the thing certified.

**Two regularities, and they are different quantities.** `H_ij` is how much of
object class `j` uses one resource of class `i`; `B_ij` is how many resources
of class `i` one object of class `j` uses. Lifting needs `H`, the quotient's
own matrix needs `B`, and the double count `N_i H_ij = M_j B_ij` ties them —
so it is a consequence of the two rather than a third hypothesis, and it is
checked anyway. Getting this wrong is not hypothetical: the first
implementation used one where the other belonged and reported 6 on a K₄ whose
value is 4. Nothing inside the reduced world catches that; the physical
program did.

**Per-row regularity, not block totals.** A block can have the right total
while individual rows inside a class see different amounts, and then projection
still works while lifting does not. That is checked row by row.

The acceptance control passes: K₄ with triangles only gives 4 physically and 4
in the quotient; drop one edge to capacity zero and the physical value is 2,
while aggregating over a class that now mixes capacities would report 10/3 —
so the partition is **refused**, naming `e01` and `e02`.

It says **nothing about integrality**. The equivalence is between the
fractional programs: on that same K₄ both give 4 while the integer packing
gives 2.

### The Lean export that was written and then removed

**This was built and then removed in the same release** — see *REMOVED*
above. It is recorded because what it cost to find out is the point: the
file below compiled in 12.8 seconds and was still the wrong thing for certo
to be writing.


`certo export --lean` on one of these certificates writes three things and
keeps them apart.

**The contract** is a structure whose fields *are* the checks — the
partitions, the non-empty fibres, the constancy of capacities and weights, and
regularity in both directions. There is deliberately no field reading "the
quotient is correct": a structure with a field asserting its own conclusion is
a definition that proves itself.

**The lemma** is `attainable_values_eq`, stated in full and left to Lean, over
a general `LinearOrderedField` rather than pinned to ℚ or ℝ — certo's data are
rationals and the equivalence holds over whatever they are read into. Three
`sorry`s, and each is a theorem about *all* equitable quotients rather than
about the instance: the lemma itself, the double count, and `proj_lift`.

**The instance** is what certo did do: class sizes, both tables, capacities
and weights, with the double-count identities among them as examples `decide`
closes — and two more confirming the classes account for the physical program,
226 rows and 3147 columns at `t = 2`. That section carries no `sorry` at all.

### Checked against a reconstructed family

The reference family was rebuilt from its description alone — six vertex
classes, three forming a clique and three hosts each complete to the core
classes it serves — with the orbit structure derived from an adjacency table
rather than transcribed. It reproduces every number it was given: 13 edge
orbits and 55 clique orbits (22 triangle types, 33 K₄ types); the boundary
strata 12/31, 13/49, 13/54, 13/55 at t = 1, 2, 3, ≥4; the optimum
`133/4·t² − 6t` for t ≥ 2 and **27** rather than `109/4` at t = 1; and 71,474
physical cliques across t = 1..4.

### `solve`: `A x = b` exactly, with a witness either way

Asked for after a user pointed out that a neighbouring tool was doing this and
certo was not. It half was: `solve_exact` had been sitting in `exact.py` since
early on, reachable from exactly one internal caller and from no command.

The certificate is the solution and the system it solves, so re-checking is one
matrix-vector product — and because `A` and `b` travel with `x`, the check is
against the system that was stated rather than the one somebody remembers
stating.

**Unsolvable is certified too**: `y` with `y·A = 0` and `y·b ≠ 0`, a row
operation the elimination already performed and which turns a negative result
into two more products. **Underdetermined returns the solution set** — a
particular solution plus a basis of the kernel — because reporting one point of
an affine subspace as the answer is how a free parameter disappears.

**Over ℤ the Smith normal form decides it**, which finishes something `matrix`
had listed in its own documentation and never exposed. The kernel there is a
basis of the *lattice*, not merely of the space it spans, which is the reason
to go through Smith rather than reduce over ℚ and clear denominators.

It establishes **neither non-negativity nor, over ℚ, integrality**, and
`verify` says so every time. The example makes that concrete rather than
sloganeering: on `K₄`, the edge vector `(2,2,2,0,0,0)` is non-negative
everywhere, its representation by triangles is unique, and it uses a weight of
−1 — with full column rank, so there is no other answer to choose instead.

One defect found while writing the tests: verification picked which argument
to require from **which evidence was in the payload** rather than from the
declared domain, so deleting the rational obstruction from a certificate let it
verify by an integer argument instead. Those are different claims and the
integer one is strictly weaker. It now branches on the domain.

### `reduce --parametric`: the same question about a family

The same question about a family rather than an instance. Asked for by the
user who put `reduce` through a real argument, and built around a case they
pointed at.

### The gap it closes

`reduce` checks the averaging argument on one program. A write-up does not
symmetrise one program — it symmetrises `S(p,q)` and writes the answer as a
formula. Everything between "I checked the instances I ran" and "the symbolic
identity the proof uses" was a step nobody was checking.

A family is now declared as orbits whose multiplicities are **polynomials** in
the parameters, and rows that exist only under stated conditions. The
**objective is not declared**: substituting one variable per orbit into `Σ z_e`
sums each orbit, so the objective *is* the multiplicities, and deriving it is
what stops the two from disagreeing.

### What measuring the real family changed

The design question going in was whether the orbit *count* varies with the
parameter. Across three write-ups it does not — it is fixed at 2, 3 and 4.
What varies is the **row set**: a triangle type that does not exist contributes
no constraint, and the program's shape changes at the boundary.

So the feature is built around row existence conditions rather than around
varying orbit structure, and the **regimes** — the distinct row sets the
conditions cut parameter space into — are derived rather than listed. A
piecewise closed form has one branch per regime, which makes the two directly
comparable: three branches over four regimes is a formula missing a case.

One thing measuring *did* change: an orbit is present exactly where its
multiplicity is **positive**, not wherever it is declared. The split family has
two edge orbits for `q ≥ 1` and one for `q = 0`, because there are no cross
edges to be an orbit of.

### Two levels, kept apart

**Symbolic**, wherever the declaration holds: which orbits, which rows, what
coefficients, which regimes, and that the multiplicities account for every
object. **Per instance**, on a finite window: that the declared group really
*has* these orbits at these sizes, and that the quotient averaging produces is
the symbolic one evaluated there.

The second does not become the first by adding points, and `verify` says so
every time. What the window buys is falsifiability — and it delivers:

| A declaration that is wrong | Window points where it fails |
|---|---|
| `3x ≥ 1` carried into `p = 2` | 7 of 35 |
| a coefficient of 3 where the row wants 2 | 30 |
| multiplicity `pq/2` instead of `pq` | 30 |
| multiplicity `p²/2` instead of `C(p,2)` | 35 |
| an orbit declared that does not exist | 35 |

The object count is checked against the instance's own variable count rather
than against the polynomial sum — comparing that sum with itself would have
been a check with no content.

### The Lean file that was written and then removed

**This was built and then removed in the same release** — see *REMOVED*
above. The `ring` proof really did close; the export went anyway.


`certo export --lean` on one of these certificates writes the multiplicity
identity as a theorem `ring` closes outright, the window points as examples
`norm_num` closes, and exactly **one** `sorry` — on the claim that the orbit
structure is uniform in the parameters. That is the step from the window to the
region, and marking it rather than stating it is the whole design.

### Also

`certo ask` routed a parametric spec to the single-instance engine, which would
have answered a weaker question than the one asked. The routing now picks the
engine from the spec type, the same way it already did for `sweep` over a
finite domain.

### Compatibility

One new spec type, `ParametricSymmetrySpec`, and one new certificate kind,
`parametric_symmetry`. `reduce` without the flag is unchanged and existing
`symmetry_reduction` certificates verify untouched. Schema stays at 4.



### `audit`: a denominator is not a free variable

One defect, reported against 0.8 within a day of it shipping, and it was two
defects in the same place.

Division is **total** in SMT. `n/0` is not an error in Z3; it is some fixed
value supplied by an internal function the solver may interpret however it
likes. So dropping a hypothesis that guards a denominator produced an instant
"counterexample" — `d = 0`, with the invented value chosen to break the goal —
and the hypothesis came back `needed` for a reason that was about the solver
rather than about the theorem.

The second half was worse than reported: those witnesses also carried Z3's
internal `div0` and `mod0`, which are not variables of the problem and which
re-checking could not parse. So on **any** spec containing a division, `audit`
emitted a certificate that did not verify at all — every row failed, including
the ones whose witnesses were mathematically fine.

Now every divisor that could vanish is collected up front, every search is
guarded by it, and the witnesses carry only arity-zero declarations of a sort
that can be written back down.

### A fourth verdict: `domain`

A hypothesis whose drop leaves a counterexample only outside the domain is not
`needed` — the claim does not become false without it — and emphatically not
`redundant`, because removing it does not give a more general theorem, it
gives a statement about a value nobody defined. It gets its own answer, naming
the obligation it was carrying:

```
[DOMAIN]     d_nonzero   holds up: d != 0
[needed]     n_zero      without it: d=-1, n=1
every search was guarded by 1 domain obligation(s): d != 0
```

**The distinction is asked, not read off the shape of the formula.** Put
`d >= 1` beside `d != 0` and the same `d != 0` comes back `redundant`, because
what remains still forces the obligation. The question is whether the dropped
hypothesis was carrying a well-definedness condition *nothing else carries*.

Verification derives the obligation list from the formulas that travelled
rather than reading it from the payload, for the same reason a branch-and-bound
node rebuilds its own linear program: a certificate declaring fewer divisors
than its formulas contain is one whose searches ran unguarded.

### Compatibility

`counts` gains a `domain` key and the payload gains an optional `obligations`
list. Certificates written by 0.8 declare three counts and no obligations, and
they keep verifying — the tally is compared on the keys the payload declares,
and a separate check refuses any row whose verdict the tally does not declare,
so deleting a key to hide a row does not work. Schema stays at 4.

## [0.8.0] — 2026-09-17

Three commands, and all three close a step that was being taken on trust. Two
of them were named by every report this project has received; the third is the
arithmetic both of the remaining requests are built on.

### `certo reduce`: "by symmetry", as a check rather than a sentence

Five shipped examples begin with a symmetrised program, and the step that gets
them there is always some version of *"averaging over the automorphism group,
an optimal solution may be assumed constant on each orbit"*. Everything
downstream of that sentence was certified — the reduced program's optimum, its
dual, its branches. The sentence itself was not, and if the group is wrong the
reduced program is a **different program** and every number after it is about
something else.

The argument has exactly three hypotheses and, given a generating set, all
three are finite checks: the action permutes the variables, the constraint set
is invariant, the objective is invariant. A generator that fails one is
**refused by name** — a wrong group does not give a weaker reduction, it gives
a wrong one. Where the group comes from is not this command's problem; nauty
computes it, a paper states it, certo checks it.

K7 triangle cover under S7: 35 variables to one orbit, 21 rows to one, optimum
7 both ways. A smaller group is still sound and just less useful — the cyclic
shift alone gives 5 orbits and 3 rows, same optimum.

The quotient is **rebuilt** during verification rather than believed, for the
same reason a branch-and-bound node derives its own linear program.

### `certo audit`: does each hypothesis earn its place?

`core` says which hypotheses an unsat core needed, which catches a theorem
stated with slack. It cannot catch the opposite mistake, and the opposite
mistake is the expensive one: a theorem stated **too strongly**, formalised,
and only then found to be about a smaller class than the paper claims. A month
goes into that.

One satisfiability query per hypothesis: drop it, and go looking for a
counterexample to what remains. Three verdicts — `needed`, `redundant`,
`unknown` — and the third is **never folded into the other two**, because a
report that quietly counted an exhausted budget as `needed` would say the
theorem is tight when nobody checked.

Every `needed` carries the assignment that breaks it, so re-checking is
evaluation and not search. On `examples/amgm.py` two hypotheses came back
redundant and only one of them was the planted red herring.

It does **not** claim the hypothesis set is minimal, and `verify` says so every
time. Hypotheses are dropped one at a time, and a pair can be jointly redundant
with neither redundant alone. Claiming otherwise would be the exact
overstatement this command exists to catch.

### `certo matrix`: exact integer linear algebra, checked by multiplying

rank, determinant, Hermite and Smith normal form over ℤ. A determinant from
floating point is a number to be trusted and a determinant from exact
elimination is a number to be **rerun**; neither is a certificate. So the
elimination's own transforms travel, together with their inverses:

    U · A = H          U · U_inv = I          U · A · V = S

and every claim becomes integer matrix multiplication. `U · U_inv = I` proves U
unimodular, so A and H span the same row lattice; H's pivots give the rank,
its diagonal gives the determinant, and Smith's checked divisibility chain
gives the invariant factors — so the torsion of ℤⁿ / A ℤᵐ is a finite checkable
fact rather than a line nobody verifies.

**The sign is the one interesting part.** `U · U_inv = I` pins |det(U)| and
says nothing about which sign, and that sign *is* the sign of det(A).
Recomputing it over ℤ would cost what the elimination costs — but det(U) was
already known to be +1 or −1, and those two are distinct modulo any odd prime.
One determinant mod a word-sized prime settles it. Not probably: exactly,
because there were only ever two candidates.

`rows` and `cols` select a submatrix first, so a **minor** is the same question
with no separate machinery. Entries must be integers: `2.5` is refused rather
than rounded, because a matrix quietly rounded is a different matrix.

### Three defects the work found

**`verify.matrix.detail` never existed.** `t()` returns the key when a message
is missing, so `core_matrix` certificates have been printing the literal string
`verify.matrix.detail` as their detail line since the command shipped. It only
became visible when `certo matrix` wanted the same name. Three tests now pin
the general case: every key the code asks for exists, the languages carry the
same keys with the same placeholders, and no message is called with arguments
it does not declare.

**`enum` was missing from `certo commands`.** The catalogue is how somebody who
does not know the names finds one; a command absent from it ships invisible.

**The README command table said twenty-eight, listed twenty-nine, and the CLI
had thirty-nine.** A reader looking for `audit` would have concluded it did not
exist. Both are now checked by tests, because a number nobody recomputes is a
number that is wrong.

### Compatibility

Three new certificate kinds — `symmetry_reduction`, `hypothesis_audit`,
`integer_matrix` — and one new spec type, `MatrixSpec`. Schema stays at 4 and
no existing payload changed shape; certificates written by 0.7 verify
unchanged. The `verify.matrix.*` message keys that belong to `certo matrix`
are named `verify.lattice.*`; `core_matrix` keeps the ones it already used.


## [0.7.0] — 2026-09-17

Read against three separate write-ups of one argument rather than against a
tool. Each symmetrises a fractional cover over edge orbits, states the value as
a minimum of named closed forms, and closes with *"duality completes the
proof"*. What duality completes it **with** is a finite object none of them
writes down, and certo could not express any of them.

Four things came out of chasing that, and three of them are holes that were
already shipped.

### `parametric`: the cover shape, and a dual that may be a polynomial

The command was built from the instance that arrived first — a packing, `max`,
`<=` rows — and refused a `min` problem or a `>=` row by design. **Every cover
in the corpus is the other shape.** So `sense="min"` with `>=` rows is the
second shape, certifying a bound from **below** out of a feasible packing, one
sign apart from the first.

A cover's dual is itself a packing, and a packing of a growing object grows
with it — `C(d,2)` triangles, not `1/3`. So a dual entry may be a polynomial,
and `y >= 0` becomes the same shift test as every other row. `dual_poly` carries
it exactly; `dual` keeps the readable form and is **checked against it**,
because a field nobody checks can say anything. Both are optional and written
only when they say something, so a packing certificate is byte-for-byte what it
was.

The branch conditions of a piecewise closed form turn out to **be** the dual's
feasibility conditions. Not a coincidence worth documenting — it is what a
piecewise-linear value function looks like from underneath, and it is why each
branch is its own certificate rather than a wider ray.

### `parametric`: a branch that is not a coordinate box

The shift test proves non-negativity on a ray, so what a certificate covers is
a **box**. A branch cut out by `q d + d r = d(d-1) + r(r-1)` is not one, and the
limitation was invisible: a spec that cannot be written as a box does not fail,
it never gets written.

Side conditions are **declared** now. `region=[("name", g)]` means `g(p) >= 0`
on the instances meant — exactly the standing the parameter floors already have
— and nothing here proves it. `verify` carries a warning of its own for them,
separate from the scope line, because a polynomial side condition reads like
something proved.

What certo finds is the **multipliers**, because that search is a linear
program. They are polynomials rather than numbers, and pairwise products of the
declared conditions are derived rather than assumed.

A four-orbit trichotomy that two boxes covered 68% of now takes five
certificates — three boxes, two scoped by a curve — and covers **1170 of 1170**
measured parameter points, every bound exact against an exact rational simplex.

### `certo peak`: the best integer choice, for a whole family at once

A value function optimised over something that has to be a whole number. A
write-up completes the square, observes the objective is an integer at integer
argument, concludes the maximum is the **floor** of the continuous peak, and
attains it at the nearest integer. Every step right, none of them a finite
object: the floor of a parametric expression is not a polynomial.

Moving the origin to the claimed maximiser makes it polynomial. An integer step
`t` changes the objective by `A t^2 + q'(x*) t`, which for `A < 0` is
non-positive for every non-zero integer `t` **exactly when**

    A <= q'(x*) <= -A

Two polynomial inequalities, checked by the same shift. No floor and no residue
appears in the certificate. The bound is **attained** because `x*` is an integer
— which is why a maximiser with non-integer coefficients is refused rather than
assumed integral, that being the step the written version takes on trust.
Residue classes are separate specs, the way branches are.

### Branch and bound: each node tied to its own subproblem

**The hole that mattered most.** A node closed by storing a whole nested
certificate, which `verify` checked *on its own terms*. But a dual for a node's
relaxation is a valid dual for **some** linear program, and nothing in it says
which node. So a tree with two node certificates **exchanged** verified — an
expensive subtree closed by a cheap one's certificate, reading exactly like a
complete proof. That breaks the strongest thing certo says.

Each node's problem is **derived** now, from a root system carried once and the
node's own fixings, by the same function the search calls — so producer and
verifier cannot hold two readings of what the node's LP is.

The two halves the backlog asked for came out of it for free: node data fell
from ~33,654 bytes to 880 on a 98-row instance and runs ~150-176 bytes per node
on branching trees, and `solver_free` is **computed** rather than hardcoded
false and comes back true.

Certificates written before the root system existed still verify, by the nested
path, with a warning naming exactly what they do not establish.

### A dedup you can check: `labelling=`

`canonicalize` hands over a **form** and asks to be believed, so *"these forty
are the same object"* was the spec's claim. `labelling` hands over the
**permutation**: certo applies it, the result is the canonical form, and the
permutation travels so anyone can re-apply it.

No cap, because nothing is searched. The instance that motivated it — a
vertex-transitive object certo's own canonical form refuses outright, where
`15!` is 1,307,674,368,000 and quotienting by the whole automorphism group still
leaves 10,897,286,400 cosets — deduplicates 40 labelled copies to 1 orbit with
40 witnesses, all re-applied on verification.

What it still does **not** show, that two different representatives are
different objects, is a warning rather than an implication. Declaring both
`canonicalize` and `labelling` is refused.

### Two more holes, found by the work above

* **A `SetFamily` id was ambiguous past ten points.** `key` juxtaposed point
  numbers, which is unambiguous only while a point is one digit: on fifteen
  points `{1,2,13}` and `{12,13}` both read as `1213`, so two **different**
  families shared an id and `from_key` returned a third. The id is the dedup key
  and what lands in a certificate. Ids separate their points above ten now and
  are byte-identical at or below it.
* **The exact simplex could return a `y` violating its own constraints.** Rows
  one-per-monomial are dependent by construction, so phase 1 ends with an
  artificial basic at level zero; the transition renamed it to variable index 0,
  which is a real variable, stating a false tableau. The result was a wrong
  answer or a spurious "unbounded", silently. No soundness hole where it was
  used — every caller re-checks what comes back — but it was losing answers.

### Adversarial coverage

`branch_bound` was **missing from the suite entirely**, which is how its hole
survived; it is in it now, with `integer_peak` and both new `parametric` shapes.
The suite also mutated a nested certificate's schema number rather than its
payload, so a field holding a whole sub-certificate looked unchecked when it was
checked thoroughly.

Three payload fields were written during this work and then **removed** rather
than excused, because the suite said mutating them flipped no check:
`dual_rows`, and `integer_peak`'s leading coefficient, slope and two step
inequalities. All are one expansion from what remains.

### Discharged against real obligations

Five examples, every output copied from a real run: `parametric_cover.py`,
`parametric_orbits.py`, `farkas_named_square.py`, `peak_residues.py`,
`orbits_witnessed.py`. The third needed **no new code** — `farkas --nonlinear`
searches a fixed square set and a margin estimate completing the square as
`(2s-q)^2` is outside it; a square is a tautology, so handing one over adds a
row and not an assumption.

Schema still **frozen at 4**. Every new field is optional.


### Adversarial verification, and the three holes it found

Two certificates shipped in 0.6.0 that `verify` rejects, and 339 tests could
not have caught either: every test feeds verification something the producer
built, so a contract misread in BOTH places passes.

`tests/test_adversarial.py` does the opposite. It takes a valid certificate of
every kind, mutates one payload field at a time, and asserts the mutation is
caught. The interesting failure is not a crash — it is a mutation that flips
**no check**, because a field nothing looks at is a field the certificate does
not really carry.

It found three:

* **A Pratt primality tree was never tied to the number it claimed.** A valid
  certificate for 2³¹ − 1, relabelled as 2³¹, verified — and 2³¹ is even. The
  tree was never wrong; nothing checked it was about the stated `n`.
* **`lp_dual` accepted a primal one entry short.** `zip` truncates in silence,
  so every check ran over the prefix and none noticed the missing variable.
  Shapes are checked first now.
* **An `unsat_core` with Farkas multipliers never read its own `core_smt2`.**
  From 0.6.1's own work: with multipliers present the SMT-LIB2 core was
  carried and unchecked, so a certificate could pair a bogus core with a valid
  multiplier set — and `compose` reads that core for its entailment check.
  The rows are now re-parsed from the SMT2 and matched.

Fields that legitimately carry no claim are excused **by name with a reason**,
not by a rule, so excusing one is a decision somebody made. Two categories:
descriptive (titles, counts, data the checked content is derived from) and
weakening — an exact cover really is an at-least cover, and a mutation that
makes a *smaller* true claim is not a forgery.

Two of those exclusions are worth reading on their own: `sos` records a
denominator its verifier never looks at, and a sweep whose predicate cannot be
re-run says so loudly and then checks none of its outcomes. The first is inert
and should probably not be in a checkable payload; the second is the honesty
layer working.

### `certo repro`: the bundle

Spec, certificates, versions, hashes and the ledger in one directory a referee
can check with nothing installed but certo. Two rules make it worth having:

**Nothing invalid goes in.** Every certificate is verified on the way and one
that fails is left out and named. A bundle containing a certificate that does
not check is worse than no bundle — it looks like evidence.

**Nothing untied goes in quietly.** A certificate names its spec by hash; when
the file still matches it is copied in, and when it has moved on the manifest
says so rather than shipping a different file in silence.

On a real directory: 132 certificates, 101 of them re-checking without a
solver, 57 specs copied, 6 named as untied and 5 left out with their reasons.
The bundle re-verified end to end.

### `verify --spec` and `certo --version`

    certo verify cert.json --spec spec.py

refuses unless that file is the one the certificate was made from, by hash —
the failure being verifying an old certificate correctly while believing it
describes the file on your screen. And `certo --version` reported a missing
subcommand; it now prints version, commit where available, and the newest
certificate schema this build writes.


### `cover --optimize`: a cover, and how far it is from the minimum

A cover certificate is an upper bound, and a user read one as an optimum —
reporting a construction of 780 parts where the obvious one uses about 41, and
calling the difference a property of the graph rather than a fact about their
construction. Nothing in the certificate was wrong; the missing half lived in
an LP they had to rebuild by hand.

```
  and how close that is to the minimum:
    your cover      21 parts   (an UPPER bound, certified above)
    relaxation      7   (a LOWER bound, exact rational dual -- fractional)
    integer optimum 7   (PROVED by branch and bound)
  your cover uses 21; the minimum is 7.
```

`CoverSpec.to_lp(integral=...)` is the canonical conversion, with **equality**
rows for an exact cover — the thing a hand-written relaxation gets wrong.
`candidates` is required and refused rather than guessed: minimal relative to
what is a modelling fact, and the set of all cliques is almost never what
anyone meant.

### An exact simplex, for when rounding a float dual cannot work

Building the above surfaced the limit of the 0.6.0 fix. On a degenerate
optimum, deriving the dual from complementary slackness means choosing which
tight rows carry weight — and on a realistic exact cover that is 49 tight rows
against 7 active variables, about **10⁸ candidate bases**. Right for a handful,
hopeless past it.

Past that, certo now solves the dual outright with a two-phase simplex in
exact rationals: no floats, Bland's rule throughout, which cannot cycle.
Termination matters more than speed in a fallback that only runs when the
cheap route has already failed.

The instance that motivated this came back `exact: False` before and is
certified now, with all six exact checks passing and no tolerances. Nothing
the simplex produces is trusted for being produced there — it goes through the
same `check_lp` as a rounded guess.


### `certo commands`, and aliases for the words people actually type

`certo order` shipped in 0.5.0 with its own README section, its own example,
and two table rows. A user spent a session writing it by hand in Python three
times, then asked for it as *the one function I would want in 0.7*. They had
searched for "asymptotic" and "decays"; the command is called `order`.

That is a discovery failure, and a worse problem than a missing feature: the
work was done and did not reach anyone. Four things, none of them another
table:

* **`certo asymptotics` and `certo decays`** run `order`. An alias costs one
  tuple entry and removes the whole failure mode.
* **The help line leads with the question**: "does this term DECAY in n, or is
  it Theta(1)?" rather than "the exponent of n in a term".
* **`certo commands`** (also `certo what`) prints the question-to-command
  table in the terminal, in your language. It existed only in the README, and
  the README is not where somebody is when they are stuck.
* **`lint` names the command** when a claim divides by a PRODUCT of symbols —
  the shape of a magnitude question, which `prove` cannot answer because a
  Theta(1) term is satisfiable forever and never improves.

The lint trigger is deliberately narrow: two or more distinct symbols at
negative exponent, because one is far too common to mean anything. It fires on
the exact expression that cost that user the session, and zero times across
the 39 shipped examples.


## [0.6.1] — 2026-09-17

**Schema unchanged: `SCHEMA_VERSION` stays 4.** Two optional payload fields on
`branch_bound`, and fixes.

Everything here comes from one field report, written after using 0.6.0 on a
real formalisation. Two defects it found, the fix for the class they belong
to, and three things it asked for.


### Fixed: two defects, found by running `verify` on our own output

**A `mixed_design` certificate was rejected by its own verifier whenever the
model had a `>=` or `==` constraint.** Reported as "all variables discrete, so
the residual LP is empty", and the empty residual turned out to be incidental:
the trigger is the constraint SENSE, and it bit mixed models with continuous
variables just as hard.

`LPSpec.as_leq_system` renames a `>=` row to `name_geq` and negates it, and
splits an `==` into `name_le` and `name_ge`. The equivalence check looked up
the ORIGINAL name in a table keyed by the normalised ones, missed, and called
a perfectly good certificate invalid. That mapping now lives in one place,
`certificate.normalised_rows`, and both consumers use it by name.

**A `>=` load reported a shadow price of zero.** Same root cause, different
consumer: the load reporter looked up `quota_A` while the row was
`quota_A_geq`. It now sums the normalised rows with their signs, so the number
is `d(optimum)/d(bound)` — for a binding `>=` quota that is negative, because
raising the floor costs you, and the message says which direction it means.
The rows it came from travel in the payload.

### Added: `--self-check`, which would have caught both

After producing a certificate, run the real verifier on it. **Solver-free
certificates are checked by default** — the check is arithmetic and costs
nothing — and anything needing a solver is opt-in via `--self-check`.

A failure is not a warning: the exit code says invalid, and the message says
plainly that this is a bug in certo rather than in the user's spec. Both
defects above reproduce as an immediate, loud failure under it.

This is the class of bug a test suite does not catch on its own, and it is
worth naming: every test fed verification a certificate the producer had
built, so producer and verifier agreed because both were wrong in the same
place.

### Also: a solver's stop reason, said in words

z3 says `canceled` when a timeout or an rlimit fires, and the report is right
that this reads as if the user had cancelled something. Known reasons are now
named as what they are, with the lever to raise:

```
inconclusive (timeout): the work or time limit was reached -- raise --rlimit
or --timeout-ms, or simplify the statement. A common one: divide out a power
that appears on both sides.
```

That last hint is from the same report: a `prove` on an inequality with a
symbolic `n^6` timed out at 10 s, and dividing out the common power settled it
in 12 ms.

### Also: the `ParametricSpec` docstring showed terms it does not accept

It wrote `objective={"x": one, "y": p - 5}`, which reads as z3 — and a
`z3.RealVal(3)` raises a `TypeError` naming no argument. Coefficients are
`Poly` over the parameter ring, or z3 terms in the parameter symbols, and the
docstring now builds them that way and says why a bare rational cannot work:
it has no ring to live in, and guessing one would be guessing which parameters
the problem has.

### Added: branch and bound accepts a minimisation

It refused with "negate the objective yourself". The transformation is exact
and mechanical, and making the user do it leaves their certificate describing
a formulation nobody posed — which is the one thing a certificate must not do.

The tree still searches `max -c.x`, because that is what was actually done,
and the payload records **both**: `sense` is what was searched,
`original_sense` and `original_optimum` are what was asked. The screen shows
the minimum in the user's own sign.

### Added: `--wall-timeout-ms`, and a stopped search that says what it knows

`--timeout-ms` bounds each solver call, not the search, and a nine-minute run
under a four-minute flag is a fair thing to be annoyed about. `--wall-timeout-ms`
is a budget for the whole branch and bound.

On expiry — by clock or by nodes — the result now carries the **best design,
the best bound, the gap and the node count**, and no certificate of
optimality. A search that runs out always knew all four; returning
INCONCLUSIVE with none of them made an instance a hole rather than a partial
result.


## [0.6.0] — 2026-09-17

**Schema unchanged: `SCHEMA_VERSION` stays 4.** Three new certificate kinds
and one optional payload field, which are the two shapes the freeze permits.
A 0.5 certificate verifies here and one from here verifies there, minus the
kinds and the field it will not know to look at.

Three new commands, all of them built against a real instance rather than in
the abstract, and one negative result kept because it corrects the backlog.

### `certo parametric`: the finite-to-infinite jump

The thing this project kept saying it could not do, and the sentence that
carries the most unearned weight in mathematical writing: *"and similarly for
larger n"*.

For a linear program whose data are POLYNOMIALS in a parameter, weak duality
is available symbolically: any `y >= 0` with `A(p)ᵀy >= c(p)` gives
`opt(p) <= b(p)·y` for every `p` at once. So the certificate is `y`, the
polynomial data, and per column the residual `A^T y - c` after substituting
`p = p0 + u` — whose coefficients are all non-negative, which is the whole
proof, because `u` and its powers are.

```
$ certo parametric examples/parametric_bound.py
PROVED  [unsat]
  for all p >= 10, the optimum is at most 1/6*p^2 + 1/6*p - 2/3
  and that is every value with p >= 10 -- not a sample of them
```

Not a loose bound either: solving that LP outright gives 53/3, 64/3, 118/3 and
463/3 at p = 10, 11, 15 and 30, and the polynomial gives exactly those. **One
dual, read off one solved instance, gives the exact optimum for every p above
the floor.**

certo does not search for `y`. `opt` on a single instance hands you one and so
would any other solver; what this checks is that it works for the whole
family, and that check is arithmetic. Same split as `farkas`, one level up.

The shift test is **sufficient and not necessary** — `p^2 - 3p + 3` is
positive everywhere and fails it at `p0 = 0`. A failure therefore means "not
established by this route", never "false", and **no certificate is emitted**,
because a route that did not work is not a bound.

Built against a real instance rather than in the abstract. A symmetrised LP
solved exactly for `p = 5..12` with a hand-written rational simplex turned out
to have duals that are piecewise constant with thresholds — one vertex at
p = 6, another across 7..9, a third from 10 — which is exactly the shape this
certifies. Reproducing that slice symbolically and certifying it was how the
command got its interface.

### `certo eliminate`: remove a variable, keep the condition

`ideal` says what follows from a system. This is the other question people ask
while setting one up — *get rid of `t` and tell me what has to be true of `s`*
— and the answer is the **resultant**, a polynomial in the remaining variables
that vanishes exactly when the two share a root in the eliminated one.

```
$ certo eliminate examples/eliminate_parameter.py
SATISFIABLE  [sat]
  eliminated t. A common root exists only where this vanishes: -4*s^3 + 1
```

What travels is not the number but the **Bezout identity** `Res = A*f + B*g`.
Computing a resultant is a determinant over a polynomial ring; checking one is
expanding two products and subtracting. That gap is the whole reason it is a
certificate rather than "the algebra system agreed", and `verify` does the
expansion in exact rationals with no solver.

The determinant is Bareiss — fraction-free, where every division is a
polynomial division whose **remainder is asserted to be zero** rather than
assumed. No rational functions ever appear, so nothing has to be cleared at
the end.

Three things it is careful about:

* A resultant that is a **non-zero constant** refutes a common root outright,
  for any values of anything, over any field. Conclusive, for one determinant.
* `Res = 0` is **necessary** always and **sufficient** only over an
  algebraically closed field with a non-vanishing leading coefficient.
  `verify` repeats that every time, and says so specifically when both leading
  coefficients can vanish — that locus is exactly where sufficiency is lost.
* **Exactly two polynomials.** Iterating pairwise over a larger system
  introduces extraneous factors nothing here could certify away; that is what
  `ideal` is for.

`certo lint` knows the spec: the wrong number of equations, a variable that is
not there, and a degree of zero in the eliminated variable are all caught by
comparing integers, before any determinant is computed.

### `certo cover`: is this really a clique partition, and how large?

Somebody hands you a clique partition and says it has 47 parts. Two things
have to be true and neither is visible by looking: every part really is a
clique, and every edge is covered EXACTLY once — not zero times, which makes
it not a cover, and not twice, which makes the count a lie. Checking both is
counting: no solver, no search, no trust in whatever produced it.

```
$ certo verify out/clique_partition.json
VALID  exact_cover certificate (checked by counting, no solver)
  [ok] every element of the universe is covered  (0 missed: -)
  [ok] and covered exactly once  (0 covered more than once: -)
  [ok] every part really is a clique of the graph  (0 parts are not)
```

The general object is an exact cover — a universe and parts, each element in
exactly one — and a clique partition is that with the edge set as the universe.
So the machinery is written once and the graph case adds the check a cover
cannot make: that a part's edges really are ALL the edges among its vertices.

Three failures, reported as three different things. A part that is not a
clique is a statement about the graph, so the run stops **inconclusive** with
the offending pairs named and writes no certificate. An edge covered twice or
zero times is **REFUTED**, named, and in the first case told that `exact=False`
would make the same data valid — an at-least cover is a weaker and reasonable
claim, recorded as a different one rather than left for a reader to assume.

**It is an upper bound.** That the size is minimum is a different statement,
and the exact rational dual from `opt` on the same universe is a lower bound
for it; where the two meet the number is proved, which is the pairing
`opt --gap` already makes for packings. Finding a minimum cover is NP-hard and
deliberately not what this does.

Built from a real audit that sends a graph plus a partition, and a graph plus
dual weights, to an external service for checking. The difference in model is
the point: a certificate carries its own check, so the same audit does not
need the service to still be running in six months.

### One thing that was tried and does not work

The backlog said the fix for `SetFamily.canonical()` refusing on symmetric
families was "individualisation-refinement, the way nauty does it". It was
implemented and verified correct — 400 random families agreed exactly with the
exhaustive reference, 120 families relabelled twelve ways each gave one form —
and then measured:

| | individualisation-refinement | exhaustive |
|---|---|---|
| K7 as a family | 157 ms | 89 ms |
| K8 as a family | 1809 ms | 2041 ms |
| 1-factorisation of K6 | still refuses | still refuses |

Refinement splits a cell only when its points differ by an isomorphism
invariant, and a vertex-transitive object has none — so on exactly the
families that hit the cap, it degenerates to the brute force it was meant to
replace. The real content of nauty is automorphism pruning; refinement is the
cheap part around it.

Reverted rather than shipped. The backlog now says that instead, along with
the measurement that the cap bites far earlier than it claimed: a
1-factorisation of K6 is fifteen points and five blocks and hits it.

### Local loads: named regions a packing has to respect

A packing certificate proved an optimum and could not say the thing an
argument usually needs next: *and the design holds the bounds I put on each
region, by this much, and that one cost me this.*

`PackingSpec(loads=[("within_A", {...}, "<=", 2)])` declares them, and they
become rows like any other — so the dual prices them for free:

```
2 declared loads, and what the design does to them:
  within_A         2 <= 2   BINDING
                   costs 1 per unit of bound -- relaxing it buys that much
  within_B         3 <= 5   slack 2
```

That second column is the point: a binding region with a shadow price is doing
work, one with slack is along for the ride, and knowing which is which is what
tells you where to spend effort tightening an argument.

A capacity is part of the ENCODING; a load is part of the ARGUMENT. They are
declared separately for that reason, and reported apart.

The certificate carries each load's coefficients, bound, achieved value and
slack, as an **optional payload field** — which the frozen schema allows.
`verify` recomputes the achieved value from the primal rather than believing
the declared one, so a certificate that understates what a region used fails.

Senses `<=`, `>=` and `==`; the last is exact preservation. A weight on an
item that is not in the packing, or a load name colliding with a resource, is
refused rather than accepted quietly — the first makes a row silently weaker
than intended and the second makes two prices indistinguishable in the dual.

Taken from a real model whose constraints read `within-A load <= N_A`
alongside a parity condition and a divisibility one.

## [0.5.2] — 2026-09-17

**Schema unchanged: `SCHEMA_VERSION` stays 4.** The two features here add
optional payload fields; nothing moves.

Both remaining P1 items from a user's report, and the thing writing the front
page exposed.

### An unsat core over linear arithmetic no longer needs a solver

A user's objection, quoted exactly: *`unsat_core` certificates depend on
trusting Z3 again; useful, but not solver-free like a rational Farkas
certificate.* Correct, and the machinery was already here.

After a core is found — in `prove`, in `check`, and in
`check --hypotheses-only` — the Farkas search runs on exactly those rows. When
it finds multipliers they travel in the payload as **optional fields**, which
the frozen schema allows, and `solver_free` becomes true: verification expands
`Σ λᵢ · rowᵢ` and reads off the contradiction in `Fraction`, with nothing to
trust.

Floating point in the search does not compromise that. The LP **finds** the
multipliers; `is_contradiction` accepts or rejects them in exact arithmetic,
independently. A bad guess is rejected rather than believed — the same
round-and-verify-exactly discipline as `opt` and `sos`. The core stays in the
payload, because `compose` reads it for the entailment check.

**And the Lean export stops saying `sorry`.** These were reported as two
separate gaps and they have one fix: a core exported with `sorry` precisely
because it says which hypotheses suffice and not why, and with the multipliers
it knows why. A vacuous regime now becomes a compiling Lean proof that it is
empty. CI compiles both paths against Mathlib v4.28.0 on every push.

Outside linear arithmetic nothing changes: no multipliers, `sorry`, and the
file says why.

### Exact LP certification stopped depending on CBC's dual

A user certified 56 LPs exactly and **3 needed the rational primal and dual
injected by hand**, all on symmetric solutions. On a degenerate vertex several
duals are optimal, CBC returns an arbitrary one, and rounding that particular
one need not be dual-feasible at all.

Given an exact primal, complementary slackness determines the dual: `yᵢ = 0`
on every slack row, `Σᵢ Aᵢⱼ yᵢ = cⱼ` for every active `xⱼ`. Solved in
`Fraction` by Gaussian elimination, with no floats anywhere. Where it
underdetermines the dual — more tight rows than active variables, which is
what symmetry produces — the leftover freedom IS the set of optimal duals, and
each choice is offered in turn.

A derived dual is not trusted for being derived: it is a candidate, like a
rounded one, and earns the certificate by passing the identical exact
`check_lp`. Reconstruction still runs first, so every LP that certified before
certifies the same way, with the same denominator and digest.

**One thing the backlog claimed and measurement refuted.** It said the coupled
denominator ladder was a second cause — that a primal wanting thirds and a
dual wanting halves had no rung that worked. `limit_denominator` is monotone
in accuracy, so a rung high enough for the harder of the two is high enough
for both, and pass 1 already climbs to it. Checked on three such pairs before
writing the fix; all were exact at one shared rung. The independent-ladder
pass was dropped rather than shipped, and a test pins the reason so nobody
adds it back.

### A refutation now shows what refuted it

The values were in the certificate and nowhere on screen, so refuting a claim
meant opening a JSON file to find out *what* refuted it. The counterexample is
the answer; the word "REFUTED" is not.

```
$ certo prove examples/refute_density.py
REFUTED  [sat]
  the counterexample:
    dens = 7/8
    kappa = 4
```

`check` and `check --hypotheses-only` do the same — the latter now literally
exhibits the parameter set that inhabits a regime, which is what it was for.

### The README leads with what happens, not with what it is

It opened on "a laboratory for supporting mathematical proofs". True, and it
tells you nothing about what running the thing does, which is what someone
deciding whether to try it needs and what a model being asked to use it needs
more.

It now opens on three real sessions, each runnable from `examples/`, and every
block of output is copied from an actual run. Two were wrong when checked
against one — including a claim that a `branch_bound` certificate verifies
*without* a solver. It does not, and the front page of a project about not
overclaiming is a bad place to overclaim.

Then **Start here**, a router by who the reader is, and **Which command
answers which question** — keyed on the question in the reader's own words
rather than on the command name.

## [0.5.1] — 2026-09-16

**Schema unchanged: `SCHEMA_VERSION` stays 4.** A new flag, a new Lean
exporter, and fixes. Nothing here moves a payload field.


### The last two items of a user report

**`check --hypotheses-only`.** The natural way to ask "are my hypotheses
satisfiable at all?" is `s.claim(z3.BoolVal(False))`, and it is the one
phrasing that cannot answer: `check` decides `hypotheses AND claim`, so a
claim of `False` reports UNSATISFIABLE whatever the hypotheses are. A user
asked exactly that, on a system with models, and was told "no model exists".
They found out only by going to `core`.

The flag asks it head on. Satisfiable returns a **model** — solver-free, the
whole parameter set exhibited rather than argued. Unsatisfiable returns the
**minimal clash** rather than the hypothesis set. And a constant claim is now
named wherever it appears, in `check` and in `lint`, because a flag only helps
someone who already knows it exists.

**`export --lean` for `unsat_core`.** It used to refuse the kind the most-used
command produces. For a core over linear arithmetic it now emits real Lean:
binders, hypotheses, the goal stated positively, and `sorry` — not a tactic
call, because a core says which hypotheses suffice and not why. A vacuous core
becomes `h₁ → … → False`, which is the emptiness of the regime stated in Lean.
Outside linear arithmetic it carries the SMT-LIB2 verbatim and says so.

The sort is read off the formulas rather than assumed: an integer regime
emitted over the reals elaborates fine and says something weaker.

### Fixed

- **`export --lean --check` had never compiled anything.** It passed the file
  path as given while running `lake` with its cwd inside the Lean project, so
  lake looked for `.github/lean/.github/lean/…` and reported "no such file or
  directory" — which surfaced as `compiled: FAILED`. Now absolute.
- **The lean CI job had never once passed**, for a different reason:
  `lean-action` refuses without a `lake-manifest.json` and there is no input
  that generates one. The manifest is now committed, pinning Mathlib and its
  eight transitive dependencies to exact revisions.
- **A confinement test asserted Windows path semantics on every platform.**
  `..\..\secret.json` escapes a directory on Windows and is a legal filename
  on POSIX; the tool was right on both and the test was not.
- **The "no Lean exporter for this kind" message listed a hand-kept set** that
  went stale the moment a new exporter landed. It is generated from the
  registry now.


## [0.5.0] — 2026-09-16

**The certificate schema is unchanged: `SCHEMA_VERSION` stays 4.** Everything
in this release is of the two shapes the freeze permits — an optional field a
reader may ignore, and commands that emit no certificate at all. A certificate
produced by 0.4.0 verifies here, and one produced here verifies there, minus
the optional field it will not know to look at.

### The one that matters: a fractional "integral point" verified as valid

A user reading output rather than code found it. `_verify_lp_dual` checked the
declared integral point for non-negativity, for `Ax <= b`, and for matching
its declared objective — and never that the values were **integers**. On
`max x + y` subject to `x + y <= 3`, a certificate claiming `x = 3/2,
y = 3/2` as the integral point passed all eight checks, because 3/2 is
feasible and does hit the declared value of 3.

`mixed_design` has checked this correctly since it shipped. `lp_dual` did not,
and `lp_dual` is what `opt` produces.

Now checked per **declared kind**, using the `kinds` the payload already
carried: every variable declared integer holds an integer, every binary holds
0 or 1, and a mixed problem's continuous weights stay fractional on purpose.
Both cases are pinned by a test.

No honest certificate is affected — the producer has always rounded, so the
points it wrote were integral. What changes is that the verification no longer
takes that on trust, which is the only thing that makes a certificate worth
anything.

Worth saying how it surfaced: 213 tests did not catch it, because every one of
them fed verification a certificate the producer had built correctly. **The
checker has to stand on its own**, and the only way to find out whether it
does is to hand it something wrong.


### Two commands that make no claim of their own

**`certo lint`** checks a spec before the compute is spent on it. Every other
command answers a question; this one asks whether the question is well posed.

The finding that pays for the whole thing is **contradictory hypotheses, found
first**. `prove` already reports vacuity — after reporting `PROVED`, which is
the moment somebody decides the run went well. Asking beforehand costs one
solver call on a strictly easier problem than the proof, and the clash it
names is minimal, so the next question is already answered.

Three more in the same spirit:

* an **inductive step that starts after the base cases end**. `induct` refuses
  this too, after discharging every base case, which is where the hours go.
  Here it is a comparison of two integers.
* a **predicate returning `bool`**, which means the sweep will be
  `reproducible` and not `certified` — a difference people who wrote the
  predicate themselves have read wrong.
* **`integer=True` makes every variable integer.** A user read it as "there
  are integers in here" and got a design worth nothing, every weight rounded
  to zero.

It counts a domain without building it (`items=lambda: iter(range(10**7))` is
peeked at, never materialised) and reads a graph family's size from a table,
so linting an 11-vertex sweep answers in the time it takes to read the file.
Loading a spec executes it; beyond that, lint calls the predicate at most once
and never runs the solver on the goal.

**`certo status`** reads a directory of certificates and says where the work
stands, in four sections ordered by how much they matter:

* **RESULTS** — the certificates nothing else there builds on. A lemma's
  certificate is not a result; the proof standing on it is.
* **STILL OWED** — every bridge and every unclaimed optimality, including ones
  reached three levels down. Bridges are legitimate and often unavoidable;
  losing count of them is not, and they are easy to lose precisely because
  everything around them verifies.
* **HOLLOW** — valid, and saying less than it looks like: a vacuous proof with
  its clash named, a sweep whose predicate nothing certified, a value reached
  rather than a maximum proved.
* **STALE** — the spec moved under the certificate. Not wrong; it verifies on
  its own. It just no longer describes the file next to it.

Neither emits a certificate, deliberately. They make no claims; they read the
claims other commands made. A report that certified itself would be the one
artefact here that nobody had checked.

### The question a solver cannot ask

A user found four bugs in one step they were doing by hand: take a symbolic
constraint, substitute asymptotic magnitudes (`d ≍ n²`, `C ≍ n`, `|W| ≍ n²`),
and ask whether a term decays in `n`. One of them,

```
5|κ| W C² / (u³ d² p¹⁰)
```

was **Θ(1)**, and it was invisible to Lean *and* to `certo prove`, for the same
reason: **it is not an infeasibility.** It is a feasibility that does not
improve with `n`, so a solver asked "is this satisfiable" says yes forever,
correctly, while the bound it sits in never gets better.

**`certo order`** asks that question. Substitute, collect into powers of the
parameter with exact rational coefficients, read off the leading exponent:
negative decays, positive grows, zero is the case that hurt.

What makes it worth a certificate rather than a calculation is that the
substitution is **written down** instead of done in someone's head, and that
the collection is exact — two terms landing on the same exponent whose
coefficients cancel really do cancel, and with `Fraction` that is decided
rather than estimated. Verification needs neither a solver nor the spec: the
Laurent polynomial travels.

Two limits it states rather than hides: it certifies the **exponent**, never
the constant in front of it (`≍` hides a factor, and `verify` repeats that
every time); and it refuses to divide by a **sum**, whose order depends on
which term dominates.

### Changed

- **Vacuity now names the minimal clash.** It used to say "run `check` on the
  hypotheses alone to find which pair clashes" — but the MUS machinery was
  already there, so it reports the clashing subset directly instead of making
  the user do the work twice. The set travels in the certificate as an
  optional field, which the frozen schema allows.
- **`verify` reads either shape.** `--cert FILE` writes the certificate;
  `--json` writes the RUN, which contains one. Both are right and a reader who
  guesses wrong loses an afternoon, so anything expecting a certificate now
  accepts either. They are told apart by the root key: `kind` versus
  `command`.
- **An INVALID report no longer ends on a line that reads like an
  endorsement.** The trailing detail describes what the certificate *claims*,
  and after a failure that has to be marked as such.
- **Vacuity detection is now a headline in the README**, third section in,
  rather than something to trip over. It is the check a proof assistant cannot
  do for you: `#print axioms` certifies "I did not cheat" and says nothing
  about "this is not hollow".

### Notes

- 285 tests, 32 examples. The example runner now exercises `status` over everything the other examples just produced, which is the only place it can be tried against a directory nobody built to suit it.

## [0.4.0] — 2026-09-16

**The certificate schema is frozen from here.** An existing payload's fields
do not move: no renames, no removals, no changes of meaning. Adding a new
certificate kind stays allowed and always will — that is additive and breaks
nothing — and so does adding an optional field a reader may ignore. Anything
else needs a schema bump and a migration note.

What that buys: a certificate produced for a paper today still verifies
against a later certo, which is the only way "re-verifiable" survives contact
with time. `SCHEMA_VERSION` is 4.

The release also closes the last of P1, which means the two sweep payloads are
finally symmetric — `--by-orbit` for graph sweeps needed three fields in
`sweep` that `domain_sweep` already had, and adding them after the freeze
would have cost a bump for a feature that was already designed.

### The headline: an optimum, proved

`mixed --prove-optimal` proves the MILP optimum by branch and bound, with
**every leaf carrying a certificate** and the tree checked to cover the
integer domain. A leaf closes for one of three reasons, each checkable by
arithmetic:

* its LP bound cannot beat the incumbent — an exact dual;
* it is infeasible — a **Farkas ray**, `y ≥ 0` with `A^T y ≥ 0` and `b·y < 0`,
  which checks in three dot products;
* every variable is fixed, so the residual LP *is* that design's answer.

And then the part that is easy to omit and fatal to: **the tree must cover the
integer domain**, checked node by node rather than assumed. A tree with a
missing child reads exactly like a complete one.

On the research instance this was built against, `ν = 7` went from "a design
that exists" to the proved integral optimum in 73 nodes — 19 closed by bound,
18 by Farkas rays — which pins the integrality gap at exactly `1/2` with both
sides certified.

### Added

- **`certo mixed --prove-optimal`** and the `branch_bound` certificate.
- **`farkas_ray`** — LP infeasibility with a certificate. `opt` used to report
  an infeasible LP and leave nothing behind; now there is a ray, and checking
  it needs no solver and no trust in the one that said "infeasible".
- **`PackingSpec.lists(family)`** — the `(list, pair)` packing, which is the
  shape 51 of 131 scripts in one research corpus share. Three lines instead of
  fifteen, and the constraint that goes missing by hand does not.
- **`opt --gap`** and the `gap` certificate — `μ* − ν` as **one exact
  rational**, with both sides certified and verification checking they are
  about the same packing. Two numbers from two runs are two numbers.
- **`sweep --by-orbit` for graph sweeps.** On a family quotiented by
  isomorphism it infers nothing, because the enumerator already did that — and
  it says so rather than silently doing the same work. It is for a symmetry
  *finer* than isomorphism.
- **`examples/WALKTHROUGH.md`** — one problem from not knowing the answer to
  holding an artefact a referee can check. Every other example shows one
  command; this shows one problem, and it is the only thing that explains what
  the tool is for.

### Changed

- A discrete packing item is bounded above by its tightest resource. With
  capacities of 1 that makes it binary, which it always was — and it is what
  gives branch and bound a finite tree to exhibit.
- `certo mixed` accepts a `PackingSpec` directly.
- `SCHEMA_VERSION` 3 → 4.

### Fixed

- `--by-orbit` that infers nothing is no longer reported as a failed check.
  Every orbit a singleton means the run *was* a full sweep and the invariance
  assumption was never used, which is a different thing from something being
  wrong.


### Added

- **`certo mixed`** — a discrete skeleton found by search, with the continuous
  part certified exactly. From a user's report on a MILP that chooses a
  structure and a compatible fractional packing at the same time, which
  `LPSpec(integer=True)` could not express: that flag makes **every** variable
  integer, a different problem rather than a restriction of this one.

  Variables now carry a kind — `lp.variable("y", kind="binary")` next to
  `lp.variable("q")` — and `mixed` runs the flow the user had been running by
  hand: search with CBC (heuristic, uncertified), freeze the discrete part,
  solve the residual LP with an exact rational dual, and compare against a
  `--target`.

  Three numbers come back and they are deliberately not merged: what the
  design **achieves** (exact, a genuine lower bound, because the construction
  exists), the **conditional** optimum given that skeleton, and the
  **relaxation bound** over all skeletons. That third one is not in the
  obvious design and costs one extra LP — and when the first meets it, global
  MILP optimality is certified for free.

  What is checked: the assignment is integral and in range, the full point
  satisfies every original constraint exactly, and **the residual LP really is
  the original problem with that assignment substituted** — the same gap
  `compose` closes between a lemma and the statement it is used for. CBC's
  answer is a guess until checked: it returns `0.9999997` for a binary as
  often as not, so the rounding is verified in exact arithmetic and a design
  that does not survive is refused rather than reported.

  What is not claimed, and says so: that the skeleton is the best one.

- `LPSpec.variable(kind=...)`, `spec.discrete`, `spec.continuous`,
  `spec.frozen(assignment)` and `spec.relaxed()`.

- **The three MILP levels, named.** A second round of the same user's feedback
  asked for exactly this taxonomy, in these words: `feasible` (a mixed point
  satisfies everything), `conditional_optimum` (and the residual LP is optimal
  given that skeleton), `global_optimum` (and it meets the relaxation bound).
  The information was already there; naming it is what a reader needs, and
  "declare exactly what was proved" is the whole discipline.
- **`mixed --freeze`** — take the discrete assignment from **your** solver
  rather than CBC. A real MILP may be solved by HiGHS, Gurobi, something
  bespoke or a person, and requiring certo's own solver to reproduce it would
  put certo's limits in front of a construction that already exists. The
  frozen assignment is rounded and checked exactly like any other, so where it
  came from changes nothing about what is certified — but the certificate
  records that certo never saw the search, and `verify` says so.
- **`opt --target`** — certify `objective >= T` rather than only reporting the
  optimum. For an existence proof the question is usually whether a bound is
  reached. Falling short is a warning on a valid certificate, not invalidity.
- **`PackingSpec(integer={"K3"})`** — integrality per item kind, so structural
  items can be whole while the rest stays fractional.
- Certificates record **each variable's kind** by name, so a reader of the
  certificate alone can tell a design from a relaxation.

### Fixed

- **`ideal` and `farkas` rejected `S**4`.** With a REAL base, z3 coerces the
  exponent to a rational literal, so `is_int_value` said no and an ordinary
  quartic was refused as a "non-constant exponent". The exponent's sort was
  never the question — whether it is a literal natural number is. Reported by
  a user who worked around it as `S*S*S*S`.
- **`opt` rounded every variable on a mixed problem**, turning fractional
  weights of 1/6 into zero and reporting a "design" worth nothing. On a mixed
  problem it now certifies the relaxation bound and points at `mixed`, which
  is where the achievable value comes from.
- **`opt` treated "has a discrete part" as "is entirely integer".** The
  relaxation was built from the spec's kinds, so for a mixed problem it
  rebuilt the integer problem and the dual meant nothing. A relaxation is
  continuous by definition and is now built that way.
- **`opt` on an ILP reported the relaxation as the objective.** `meta["objective"]`
  carried the LP relaxation's value, so an integer optimum of 7 came back as
  `15/2`. The detail text was half-honest about it; every programmatic reader —
  `--json`, the CLI display, the MCP response — was not. Found by rebuilding a
  real research instance as a `PackingSpec`.

  The fix goes further than the original intent: an ILP now certifies **both
  sides**. CBC's integer answer is rounded and **checked exactly** against the
  constraints, giving a feasible integral point as the achievable value, while
  the exact dual bounds the optimum. When they coincide the integer optimum is
  certified exactly; when they do not, the gap is reported rather than hidden,
  and `verify` warns that the number is a bound.

### Added

- **CI.** Tests on Linux and Windows across Python 3.11 and 3.12; every
  example run and its certificate verified; and the Lean exports compiled
  against Mathlib. Everything had only ever run on one Windows machine, and
  the three most useful bugs of the previous round were all specific to it.
- `tests/run_examples.py` — runs each example as the README shows it and
  verifies what comes out, including the two certificates `compose_proof.py`
  needs as input. An example listed nowhere is reported rather than silently
  skipped.

### Decided

- **PyPI:** not yet; revisit at a stable version.
- **Certificate schema:** frozen from 0.4, once that version closes.
- **Lean:** deeper Lean export is not the focus. certo establishes the
  mathematics; generating and compiling Lean is another tool's job.
- **`cadical`/`kissat`:** closed rather than blocked — no administrator rights
  on the target machine, and the built-in CDCL is the answer.

## [0.3.0] — 2026-09-16

The release where certo stopped being Z3 with a nicer interface.

Three engines that are not a solver, each answering a question an SMT solver
either grinds on or cannot phrase, and each producing a certificate that is
checked by arithmetic alone.

### `ideal` — polynomial systems, decided

Gröbner cofactors: `1 = Σ hᵢgᵢ` refutes a polynomial system outright,
`f = Σ hᵢgᵢ` certifies that `f` follows from it. Finding them is a Gröbner
basis computation with the transformation tracked through Buchberger; checking
them is expanding a product and comparing coefficients in exact rationals —
no solver, no algebra system. A library that says "yes, it's in the ideal"
leaves you with its word; this leaves you with the polynomials.

Two things worth knowing. **It decides**: membership is decidable, so a
negative answer is `REFUTED`, not `unknown_solver` — rare in this tool. And
**the field is ℂ**: `1 ∈ I` refutes over the complex numbers and hence over
everything smaller, while a proper ideal implies nothing about a real
solution. `verify` says so every time.

### `sos` — a numeric search, an exact certificate

This project's own notes argued twice that sums of squares were not worth
having, because an SDP is solved in floating point and an inexact certificate
is not citable. The objection was aimed at the wrong half: it would rule out
`opt` too, and `opt` answers it. Solve numerically, reconstruct rationals,
re-verify exactly.

`p = zᵀGz` is a linear condition on `G`; a numeric `G` is found by alternating
projections onto that affine subspace and the PSD cone (no SDP solver needed,
which matters, because there is not one here), then rounded, **projected back
onto the subspace exactly in `Fraction`**, and decomposed by an exact LDLᵀ.
Every pivot non-negative means the decomposition *is* the sum of squares. The
floats were the search and never reach the certificate.

Incomplete on purpose: from degree 4 in 3 variables there are non-negative
polynomials that are not sums of squares, so nothing found is
`unknown_solver`, never "it goes negative". Motzkin's polynomial is in the
tests for exactly that reason.

### `number` — primality you can cite

`n.is_prime()` is true, fast and uncitable. A Pratt certificate is the same
fact with the evidence: a witness generating `(ℤ/n)*`, plus a certificate for
each prime factor of `n−1`, recursively down to 2. Checking the tree is a
handful of `pow(a, e, n)` calls — 53 of them for 2³¹−1.

Three details that separate a certificate from a test: the factor list of
`n−1` must be complete (missing one would let a composite through, so that is
checked before the witness is looked at); Carmichael numbers like 561 pass the
Fermat condition and are caught by the order condition; and the witness is
found by trying small bases in order rather than randomly, so the same `n`
gives the same certificate and the same digest on every machine.

### Added

- **`certo induct`** — finite base cases plus an inductive step, with the join
  checked: the base cases are exactly `k0..base_upto` with no gap, and the
  step starts no later than the base ends. A base covering 3..8 with a step
  valid only from k ≥ 10 proves nothing about 9 and reads identically in
  prose. Z3 has no induction schema: the principle is applied by the tool, the
  certificate's structure is the application, and `verify` says so every time.
- **Native combinatorial types** (`SetFamily`) — hypergraphs, block designs,
  codes and mask systems are one shape. The type supplies `key()`,
  `canonical()` and `reductions()`, so a `DomainSpec` over one can leave
  `key`, `canonicalize` and `reduce` all at `"auto"`. The canonical form is
  exact under relabelling the ground set, and **raises** above a cap rather
  than falling back to a cheaper invariant that could merge two orbits.
- `SweepSpec(canonicalize=...)` — symmetries on graph sweeps, for a symmetry
  finer than isomorphism.
- `canonicalize="auto"` asks the item for its own canonical form, so any class
  with a `canonical()` method joins.

- **`sweep --by-orbit`** — evaluate one item per orbit instead of every item.
  Sound only if the predicate is invariant under the declared symmetry, which
  nothing can prove: the assumption is named in the certificate and
  **spot-checked** against real non-representatives, and a predicate that is
  not invariant stops the run naming the item and its representative.
  Inferred verdicts are marked in lower case in the verdict vector, and
  replay reproduces the inference rather than re-evaluating.
- **`sweep --witnesses`** — the structural story in one artefact: N labelled
  counterexamples → K orbits → a minimal witness for each. Verification
  checks the witnesses minimise the sweep's own representatives, which a
  directory of separate certificates cannot say.
- **Deep Lean export.** `certo export --lean` now reads the certificate's
  kind: a Farkas certificate becomes a runnable `linarith` example with the
  hypothesis list already narrowed and the `sq_nonneg` hints it actually
  used; a `compose` proof becomes a skeleton with `sorry` on exactly the
  bridges and nowhere else; a sweep becomes a `List` Lean can `decide` over,
  with completeness stated as the enumerator's claim rather than smuggled in.
  Plus `--manifest` (hashes tying the file to the run) and `--check`, which
  runs the toolchain and says so when there is not one.

### Fixed

- `subprocess` output was decoded with the Windows default codepage, so any
  Lean or tool output containing UTF-8 crashed the run.

### Notes

- 210 tests.
- New certificate kinds: `ideal`, `sos`, `number`, `induction`,
  `orbit_witnesses`. All five verify without a solver except `induction`.
- The three Lean exporters were checked by compiling them against Mathlib
  v4.28.0. `nlinarith` alone could not close the nonlinear example — the
  `sq_nonneg` hint from the certificate is what makes it compile, which is
  the clearest demonstration of what the certificate is worth.

## [0.2.0] — 2026-09-16

The release where a passing sweep stopped looking stronger than it was.

Almost everything here comes from one external user's report after using
`certo` on a real problem. It found a false lemma for them on first use, and
then it found something in `certo` worth more than the feature list: a result
that read as a certification and was not one.

### Never let a passing sweep look certified

A sweep over 11,480 elements that ended PASS printed `FINITE CASE VERIFIED`
and verified with no warning, while its certificate established **nothing** about
the boolean predicate. The refuted case did warn; the passing case did not —
and that is where it does most damage, because there is no counterexample to
go and look at. The counter meant to cover this, `predicate_uncertified`,
counted *stored counterexamples*, so it read `0` on every passing sweep.

A sweep now reports which of three levels it reached:

| Level | What holds |
|---|---|
| `certified` | every evaluation carries its own certificate |
| `reproducible` | a verdict vector is stored; re-running the predicate gives the same answers, which is **not** the same as establishing them |
| `recorded` | only the domain and its hash |

The banner, the counters and the warnings all say it, on PASS and REFUTED
alike. The level is **recomputed at verification time** rather than stored,
because `reproducible` depends on the spec still being there and a stored
label would quietly become a lie.

The two caveats are now separate, because they are different claims: *not the
theorem* is about generality, *not certified* is about trust.

### Replay verification

The certificate carries one character per evaluation plus a digest. `verify`
re-runs the predicate and compares, naming the first item that disagrees:

```
[XX] re-running the predicate gives the same verdicts
     (item a=1,b=1 (index 0) now answers differently)
```

This is the only check that catches a predicate edited under a stable name:
the domain hash cannot — the domain did not move — and there are no per-item
certificates to fall back on. Verification now costs a full re-run, which is
the honest price of the claim, and the header says **"by re-running the spec"**
rather than "without a solver", since replaying runs the spec's own Python.

### Symmetries

`DomainSpec(canonicalize=...)` declares when two items are the same object
relabelled. A refuted sweep then reports labelled count, orbit count and a
representative per orbit — of the **counterexamples**, which is the question:

```
REFUTED: 10 counterexamples out of 64 examined -- 10 labelled, 3 up to symmetry
  (1,2,3)   x6      (1,1,4)   x3      (2,2,2)   x1
```

That two items sharing a canonical form really are in one orbit is the spec's
claim. What `verify` checks is that the decomposition adds up: each
counterexample in exactly one orbit, no shared representatives, sizes
consistent.

### Added

- **`certo compose`** — assemble lemmas and their certificates into one proof,
  checking the **link**: what a lemma's certificate actually closes must
  entail the statement used downstream. If it does not, nothing is emitted.
  Lemmas supplied as a stored certificate are **bridges** — verified on their
  own, declared in prose, and reported by name on every verification.
- **`certo bounds`** — rigorous numerics via Arb (`python-flint`) or
  `mpmath.iv`. Enclosures come out as exact rationals, so the claim half of
  verification is fraction arithmetic. Precision is the work budget and runs
  out as `resource_exhausted`, never as a refutation. Python floats are
  refused: `0.1` is not one tenth.
- **`certo farkas`** — the `linarith` equivalent, with the certificate
  attached: non-negative rational multipliers that close the system, verified
  by adding fractions. `--nonlinear` is `nlinarith`. Emits the Lean tactic
  line with the hypothesis list already narrowed.
- **`certo doctor`** — what this install can and cannot do, each gap with
  **what happens without it**. `--register-mcp` merges into `.mcp.json`
  instead of replacing it, refuses invalid JSON, and checks the server
  actually starts.
- **Vacuity detection** in `prove`, `core`, `farkas` and `compose`. The
  verdict stays PROVED — it really is a proof — but it is said, and the flag
  travels in the certificate so `verify` repeats it months later.
- **Standard reducers** for `shrink`: `reduce="auto" | sets | sequences |
  decrement | graphs | masks`. `auto` refuses on a type it does not recognise
  rather than inventing a reduction.
- `BACKLOG.md`, one place for what is planned, blocked and refused.

### Fixed

- **`load_spec` read stale `__pycache__` bytecode** for a spec edited within
  the same second to the same byte length, so a replay could silently compare
  against the old code. It now compiles the bytes it hashed — which is also
  the right guarantee for a tool whose certificates carry a spec hash.
- **A spec could not import a file next to it.** `load_spec` now puts the
  spec's directory on `sys.path`, the way Python does for a script.
- **The MCP `verify` tool dropped `warnings` entirely** — the bridge, vacuity
  and predicate-level warnings never reached the model. An `ok: true` with
  those removed is the overclaim the tool exists to prevent.
- **Certificates produced over MCP carried no provenance**, so they could not
  be replayed or located by `ledger verify`.
- Verifying a `shrink` certificate with no recorded spec path died with
  `permission denied: '.'` — `Path("")` is the current directory.
- The whole `DSL_GUIDE` and the `synth` tool description were still in
  Spanish, though English is the default and the source of truth.

### Changed

- **Certificate payload:** the item id field is `id`, not `g6`. A `DomainSpec`
  used to label triples of sets "graph6". Readers still accept `g6`, so
  certificates issued by 0.1.0 still verify.
- `sweep` and `domain_sweep` payloads gain `evaluations`, `certified`,
  `outcomes`, `outcomes_sha256`, and (with a symmetry) `orbits` and
  `labelled`.
- `VerifyReport` gains `method`, because "not solver-free" and "a solver was
  used" are different statements.
- The redundant `verify.sweep.missing` warning is gone: the level warning that
  replaced it says strictly more, and two messages about one gap make readers
  skim both.

### Notes

- 149 tests, no test framework required.
- New optional extra: `pip install 'certo[numerics]'` for `bounds`.
- The default branch is now `main`.

## [0.1.0] — 2026-09-15

First public release. Twelve commands over CLI and MCP, every result carrying
a certificate that verifies without trusting the solver that produced it.
Engines: Z3, exact-rational LP over CBC, a self-contained CDCL with a
DRUP/DRAT checker, graph enumeration via nauty or a built-in engine, and
CEGIS. English by default with Spanish as an overlay.
