"""Run every example, and verify the certificate it produces.

The examples are the documentation. Documentation that no longer runs is worse
than none: a spec that stopped working still reads convincingly.

Each entry says which command the example is for, because that is the one
thing a spec file does not carry -- `spec()` returns an object, and the
command follows from its type, but the flags do not. Anything not listed here
is reported at the end rather than silently skipped, so a new example cannot
join the repository without joining this file.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
OUT = ROOT / "out"

# (example, command, extra flags). `None` means "produces no certificate".
CASES = [
    ("amgm.py", "prove", []),
    ("pigeonhole.py", "cases", []),
    ("core_matrix.py", "core", []),
    ("farkas_linear.py", "farkas", []),
    ("farkas_nonlinear.py", "farkas", ["--nonlinear"]),
    ("bounds_constant.py", "bounds", []),
    ("ideal_inconsistent.py", "ideal", []),
    ("sos_quartic.py", "sos", []),
    ("number_mersenne.py", "number", []),
    ("induct_sum.py", "induct", []),
    ("lp_mixed_packing.py", "opt", []),
    ("mixed_design.py", "mixed", []),
    ("walkthrough.py", "opt", ["--gap"]),
    ("walkthrough_ideal.py", "ideal", []),
    ("walkthrough_proof.py", "compose", []),
    ("packing_mixed.py", "opt", ["--by-type"]),
    ("synth_constant.py", "synth", []),
    ("synth_prove_identity.py", "synth", ["--prove-candidate"]),
    ("ramsey.py", "cases", []),
    ("ramsey_k5.py", "cases", []),
    ("mus_ramsey.py", "shrink", []),
    ("sweep_simplicial.py", "sweep", []),
    ("sweep_certified_lp.py", "sweep", []),
    ("sweep_orbits.py", "sweep", []),
    ("setfamily_sweep.py", "sweep", ["--witnesses"]),
    ("shrink_nonchordal.py", "shrink", []),
    ("bisect_constant.py", "bisect", []),
    ("bisect_ramsey.py", "bisect", []),
    ("compose_proof.py", "compose", []),
]

# compose_proof.py reads two certificates that are output, not source, so they
# have to exist before it runs. This is the `make examples` the backlog wants,
# in the one place that already knows the order.
PREREQS = {
    # The walkthrough's proof reads the two certificates the earlier steps
    # produce, which is the point of it -- so they have to exist first.
    "walkthrough_proof.py": [
        ("opt", "walkthrough.py", ["--gap", "--cert", "out/gap.json"]),
        ("mixed", "walkthrough.py",
         ["--prove-optimal", "--max-nodes", "30000",
          "--cert", "out/optimal.json"]),
    ],
    "compose_proof.py": [
        ("cases", "ramsey.py", ["--cert", "out/r33_k6.json"]),
        ("cases", "ramsey_k5.py", ["--cert", "out/r33_k5.json"]),
    ],
}


def run(args, label):
    p = subprocess.run([sys.executable, "-m", "certo.cli", *args],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    # Exit 2 is "inconclusive", which several examples are ON PURPOSE -- a
    # sweep that refutes, a bisect that brackets. Only 1 and 3 are failures.
    if p.returncode in (1, 3):
        print("[XX] {}\n{}".format(label, (p.stdout + p.stderr)[-800:]))
        return False
    return True


def _tracked_examples():
    """The example files git actually carries, or None outside a checkout."""
    try:
        p = subprocess.run(["git", "ls-files", "examples/*.py"], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode:
        return None
    return {line.split("/")[-1] for line in p.stdout.split() if line}


def main() -> int:
    OUT.mkdir(exist_ok=True)
    listed = {name for name, _, _ in CASES}
    # Files the repository does not carry (a contributor's local work) would
    # show up here as "not covered" every run, which is noise about something
    # this file cannot cover anyway.
    tracked = _tracked_examples()
    present = {p.name for p in EX.glob("*.py")
               if tracked is None or p.name in tracked}
    missing = sorted(present - listed)

    failures = 0
    for name, command, flags in CASES:
        if name not in present:
            print("[XX] {} is listed here but not in examples/".format(name))
            failures += 1
            continue
        for pre_cmd, pre_name, pre_flags in PREREQS.get(name, []):
            run([pre_cmd, "examples/" + pre_name, *pre_flags],
                "prereq {}".format(pre_name))

        cert = OUT / (name[:-3] + ".json")
        ok = run([command, "examples/" + name, *flags, "--cert", str(cert)],
                 "{} {}".format(command, name))
        if not ok:
            failures += 1
            continue
        if cert.exists() and not run(["verify", str(cert)],
                                     "verify {}".format(cert.name)):
            failures += 1
        else:
            print("[ok] {:<10} {}".format(command, name))

    if missing:
        # Not a failure, but it must not be silent: an example nobody runs is
        # an example nobody notices breaking.
        print("\nNOT COVERED by this file: " + ", ".join(missing))

    print("\n{}/{} examples ran and verified".format(
        len(CASES) - failures, len(CASES)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
