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
| ✅ | **Sweep levels: certified / reproducible / recorded** *(user feedback P0)* | Banner, counters and warnings now say what a sweep established about its **predicate**, on PASS and REFUTED alike. |
| ✅ | **Verdict vector + replay verification** *(user feedback P0)* | The certificate stores one code per evaluation and its digest; `verify` re-runs the predicate and names the first item that disagrees. |
| ✅ | **Honest counters** *(user feedback P0)* | `predicate_uncertified` used to be 0 on every passing sweep however many evaluations went unchecked. |
| ✅ | `load_spec` runs the bytes it hashed | Was reading stale `__pycache__` bytecode for a spec edited within the same second to the same length — which would have silently defeated replay verification. |
| ✅ | A spec can import a sibling file *(user feedback)* | `load_spec` puts the spec's directory on `sys.path`, the way Python does for a script. |
| ✅ | MCP `verify` returns its warnings *(follows from the P0)* | It was dropping them entirely — and the warnings are the whole honesty layer. |
| ✅ | MCP stamps provenance | Certificates produced over MCP carried no spec path, so they could not be replayed or found by `ledger verify`. |

---

## P1 — next

### 1. Symmetries for `DomainSpec` *(user feedback)*

Declare a group action or a `canonicalize` function; report **labelled count,
orbit count, and a minimal representative per orbit**.

> The user's run produced 1,400 counterexamples that were 3–4 structural
> orbits. That is the difference between a dump and a result.

Certificate: the orbit decomposition, with the canonical form of each
representative, so it can be re-derived.

### 2. Standard reducers for `shrink` *(user feedback)*

`shrink` requires a hand-written `reduce`. Honest, but it blocks the automatic
minimisation asked for separately. Ship reducers for: sets, tuples, graphs
(vertex/edge deletion), mask families, and hypothesis lists.

Keep the current behaviour when `reduce` is given — this adds defaults, it
does not guess.

### 3. Rename the `g6` payload key to `id` *(user feedback)*

`DomainSpec` output calls counterexamples "graph6" when they are triples of
sets. It is a presentation bug with a schema change behind it, so it should
land while we are at 0.1.0. `_entry_id()` already reads both, so the migration
is safe.

### 4. `certo doctor` *(user feedback)*

Report available and missing capabilities (nauty, cadical/kissat, drat-trim,
python-flint, mpmath, Lean/Mathlib), plus **one-step MCP registration and a
connection check**. Merges two separate pieces of the same feedback.

---

## P2 — high value, more work

### 5. Deeper Lean export *(user feedback)*

Today `export --lean` emits a counterexample as data. Wanted:

- Farkas multipliers as the `linarith` combination they correspond to;
- finite classifications as verifiable lists;
- a manifest with hashes, ready to import;
- a skeleton with **the exact boundary between theorem and bridge** — which
  `compose` already computes, so this part is nearly free;
- and actually **compiling** the output (Mathlib is installed locally).

### 6. Native combinatorial types *(user feedback)*

Set families, hypergraphs, designs, mask systems. They recur constantly and
are currently re-encoded by hand in every spec.

### 7. Structural comparison of counterexamples *(user feedback)*

The deliverable the user actually wanted: *1,400 labelled → 3–4 orbits →
minimal representative of each*. It is P1 #1 and P1 #2 composed, so it lands
once both do.

### 8. `certo induct`

Exhaustive base cases + inductive step, composed into one certificate. Cheap
now that `compose` exists — essentially a `ProofSpec` factory — but no user is
waiting for it.

---

## P3 — keep, nobody waiting

| | What | Why it is down here |
|---|---|---|
| | `certo qe` | Quantifier elimination to **derive** the optimal constant instead of bracketing it with `bisect`. Genuinely distinctive; no demand yet. |
| | Cutting-plane certificates | Gomory–Chvátal for **integer** infeasibility, not just the LP relaxation. Relevant to packing bounds. |
| | Exact first moment | `E[X] < 1` in `Fraction` ⇒ existence. Small, and common in the probabilistic method. |
| | `certo repro` | Bundle spec + certificates + versions + hashes for a paper appendix. Partly absorbed by the Lean manifest in P2 #5. |
| | More example specs in the repo | The published examples cover each command, but not a full worked problem end to end. `examples/compose_proof.py` also needs two certificates that are deliberately not committed (they are output); a `make examples` or a script that produces them would remove the friction. |
| | Default branch is `master` | Rename to `main` if wanted. One command. |
| | Repository topics | `theorem-proving`, `smt`, `z3`, `lean`, `mcp` — helps discovery. |

---

## Blocked

**`cadical` / `kissat`.** No Windows wheel; cadical's releases ship no
binaries; kissat publishes macOS and Linux only; there is no C++ compiler on
the machine; and WSL needs administrator rights the user does not have. The
built-in CDCL covers the gap — correct, and slow.

---

## Won't do

**Flag algebras / SDP.** An SDP is solved in floating point, so what comes back
is not exact, and an inexact certificate is not citable — the same reason
`farkas` does not go through an SOS relaxation and `opt` reconstructs
rationals. Revisit only with 2–3 real packing instances on the table and a
rounding-plus-exact-reverification plan.
