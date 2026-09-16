# Changelog

Notable changes per release. Dates are ISO. This project uses semantic
versioning; while the major is 0, a minor bump may change a certificate
payload — each such change says so and what still reads the old shape.

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
