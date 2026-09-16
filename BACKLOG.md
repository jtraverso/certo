# certo — backlog

One file, so nothing is tracked in three places. Priorities are **P0** (blocks
a release), **P1** (the next thing worth doing), **P2** (real value, more
work), **P3** (worth keeping, nobody is waiting), **Blocked**, **Won't do**.

Items marked *(user feedback)* come from an external user's report after real
use; those carry more weight than anything on this list that was invented in
the abstract.

Last updated: 2026-09-16.

---

## Done

| | What landed | Notes |
|---|---|---|
| ✅ | `certo compose` | Lemmas + their certificates into one proof, with the **link** between each lemma and what its certificate closes checked. Bridges are declared and reported every verification. |
| ✅ | `certo bounds` | Rigorous enclosures via Arb / `mpmath.iv`; exact-rational intervals; precision as the work budget; Python floats refused. |
| ✅ | Vacuity detection | `prove`, `core`, `farkas`, `compose`. The verdict stays PROVED; the flag travels in the certificate so `verify` repeats it later. |
| ✅ | **Sweep levels: certified / reproducible / recorded** *(user feedback P0)* | Banner, counters and warnings say what a sweep established about its **predicate**, on PASS and REFUTED alike. |
| ✅ | **Verdict vector + replay verification** *(user feedback P0)* | One code per evaluation plus a digest; `verify` re-runs the predicate and names the first item that disagrees. |
| ✅ | **Honest counters** *(user feedback P0)* | `predicate_uncertified` used to read 0 on every passing sweep however many evaluations went unchecked. |
| ✅ | **Symmetries for `DomainSpec`** *(user feedback P1)* | `canonicalize=` reports labelled count, orbit count and a representative per orbit — for the **counterexamples**, which is the question. `verify` checks the decomposition adds up. |
| ✅ | **Standard reducers** *(user feedback P1)* | `reduce="auto" / "sets" / "sequences" / "decrement" / "graphs" / "masks"`. `auto` refuses on a type it does not know rather than inventing a reduction. |
| ✅ | **`certo doctor`** *(user feedback P1)* | Capabilities present and missing, each with **what happens without it**, plus `--register-mcp` (merges, never replaces) and a real start check. |
| ✅ | **`g6` → `id` in the payload** *(user feedback P1)* | A `DomainSpec` used to label triples of sets "graph6". Readers still accept `g6`, so earlier certificates verify. |
| ✅ | `load_spec` runs the bytes it hashed | Was reading stale `__pycache__` bytecode for a spec edited within the same second to the same length — which would have silently defeated replay verification. |
| ✅ | A spec can import a sibling file *(user feedback)* | `load_spec` puts the spec's directory on `sys.path`, the way Python does for a script. |
| ✅ | MCP `verify` returns its warnings | It was dropping them entirely — and the warnings are the whole honesty layer. |
| ✅ | MCP stamps provenance | Certificates produced over MCP carried no spec path, so they could not be replayed or found by `ledger verify`. |
| ✅ | `Path("")` is `.` | `shrink_graph` and `shrink_domain` verification died with a permission error instead of saying the certificate recorded no spec path. |

---

## P1 — next

### 1. `--by-orbit`: sweep one item per orbit

Split out of the symmetry work deliberately. Reporting orbits is sound with no
assumptions; **evaluating only representatives is not** — it needs the
predicate to be invariant under the declared symmetry, and nothing can prove
that, since `canonicalize` and the predicate are both arbitrary Python.

The design that makes it honest: evaluate representatives, then **spot-check**
a sample of real non-representatives against their representative's verdict.
That cannot make the sweep sound, but it turns a silent assumption into a
tested one and makes a wrong symmetry surface immediately. The certificate
records the assumption by name, like a bridge in `compose`, and the count of
spot checks that agreed.

Worth doing because it is what makes 31,494 configurations cheap rather than
merely legible.

### 2. Structural comparison, end to end *(user feedback)*

*1,400 labelled → 3–4 orbits → minimal representative of each.* The first two
thirds now exist; what is missing is `shrink` running automatically on each
orbit representative and reporting the three minimal witnesses together.

### 3. Deeper Lean export *(user feedback)*

- Farkas multipliers as the `linarith` combination they correspond to;
- finite classifications as verifiable lists;
- a manifest with hashes, ready to import;
- a skeleton with **the exact boundary between theorem and bridge** — which
  `compose` already computes, so this part is nearly free;
- and actually **compiling** the output (Mathlib is installed locally).

---

## P2 — high value, more work

### 4. Native combinatorial types *(user feedback)*

Set families, hypergraphs, designs, mask systems. They recur constantly and
are re-encoded by hand in every spec. Pairs naturally with the reducers and
with `canonicalize`, which such types could supply themselves.

### 5. `certo induct`

Exhaustive base cases + inductive step, composed into one certificate. Cheap
now that `compose` exists — essentially a `ProofSpec` factory — but no user is
waiting for it.

### 6. Symmetries for graph sweeps

`canonicalize` is on `DomainSpec` only. Graph sweeps already enumerate up to
isomorphism via nauty, so the need is weaker, but a sweep with a *finer*
symmetry than isomorphism (coloured or rooted graphs) has the same problem.

---

## P3 — keep, nobody waiting

| | What | Why it is down here |
|---|---|---|
| | `certo qe` | Quantifier elimination to **derive** the optimal constant instead of bracketing it with `bisect`. Genuinely distinctive; no demand yet. |
| | Cutting-plane certificates | Gomory–Chvátal for **integer** infeasibility, not just the LP relaxation. Relevant to packing bounds. |
| | Exact first moment | `E[X] < 1` in `Fraction` ⇒ existence. Small, and common in the probabilistic method. |
| | `certo repro` | Bundle spec + certificates + versions + hashes for a paper appendix. Partly absorbed by the Lean manifest in P1 #3. |
| | A full worked example | The published examples cover each command; none walks one problem from exploration to Lean. `examples/compose_proof.py` also needs two certificates that are deliberately not committed (they are output) — a `make examples` would remove that friction. |
| | Repository topics | `theorem-proving`, `smt`, `z3`, `lean`, `mcp`. **Needs authorisation.** |

---

## Blocked

**`cadical` / `kissat`.** No Windows wheel; cadical's releases ship no
binaries; kissat publishes macOS and Linux only; there is no C++ compiler on
the machine; and WSL needs administrator rights the user does not have. The
built-in CDCL covers the gap — correct, and slow. `certo doctor` now says this
in one line instead of leaving it to be discovered.

---

## Won't do

**Flag algebras / SDP.** An SDP is solved in floating point, so what comes back
is not exact, and an inexact certificate is not citable — the same reason
`farkas` does not go through an SOS relaxation and `opt` reconstructs
rationals. Revisit only with 2–3 real packing instances on the table and a
rounding-plus-exact-reverification plan.

---

## Release process

Releases are authorised by the project owner, one at a time. Work lands in
local commits; **pushing to the public repository is not automatic** and is
asked for each time. Each release bumps the version, writes its section of
[CHANGELOG.md](CHANGELOG.md), and is tagged.

Current: **0.2.0**.
