"""Deeper Lean 4 export: proofs, not only counterexamples.

`lean.py` emits a graph as data. That is the easy half. What a formalisation
actually needs from a session of exploration is the other half:

  * a Farkas certificate is already a `linarith` call with the hypothesis list
    narrowed -- emitting it as a runnable `example` means the multipliers do
    not have to be rediscovered, and if Lean disagrees you find out here
    rather than three weeks in;
  * a finite classification is a `List` plus a `decide`, which Lean can check
    itself;
  * a `compose` proof knows exactly which of its lemmas are DERIVED and which
    are BRIDGES, so the skeleton can put `sorry` precisely on the bridges and
    nowhere else. That boundary is the single most useful thing to carry
    across, and it is the thing a person transcribing by hand gets wrong;
  * a manifest with hashes, so the Lean side can say which run it came from.

Everything here is text generation. Nothing is proved by emitting it, and the
header of every file says so. `--check` runs the toolchain when there is one,
which turns "this should compile" into a fact or a failure.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from . import __version__
from .i18n import t

HEADER = """\
/-
  Emitted by certo {version} from a {kind} certificate.
  digest {digest}{source}

  What this file is: the STATEMENTS, the data, and the proof steps certo
  established, transcribed. What it is not: a proof that certo is right. Each
  `sorry` below marks a place where something outside Lean was relied on, and
  they are listed at the end.
-/
{imports}

namespace Certo
"""

FOOTER = """
end Certo
"""


# Importing all of Mathlib costs minutes per file and pulls in everything that
# could ever be broken in a local build. Each exporter asks for what it needs.
IMPORTS = {
    # Linarith alone does not bring the ordered-field instances for R or Q,
    # so the hypotheses would not even elaborate. Found by --check, which is
    # the whole reason it exists.
    "farkas": ["Mathlib.Data.Real.Basic", "Mathlib.Tactic.Linarith"],
    "classification": ["Mathlib.Data.List.Basic"],
    "proof": ["Mathlib"],
}


def _header(kind, digest, source="", imports=None):
    mods = imports if imports is not None else IMPORTS.get(kind, ["Mathlib"])
    return HEADER.format(
        version=__version__, kind=kind, digest=digest,
        imports="\n".join("import " + m for m in mods),
        source="\n  source " + source if source else "")


# ---------------------------------------------------------------------------
# farkas -> a linarith example
# ---------------------------------------------------------------------------


def _mono_to_lean(mono) -> str:
    if not mono:
        return "1"
    return " * ".join(mono)


def _poly_to_lean(poly: dict) -> str:
    """A polynomial as Lean source. Rationals stay rationals."""
    parts = []
    for mono, coef in sorted(poly.items()):
        c = Fraction(coef)
        if c == 0:
            continue
        term = _mono_to_lean(mono)
        if term == "1":
            piece = _rat(c)
        elif c == 1:
            piece = term
        elif c == -1:
            piece = "-" + term
        else:
            piece = "{} * {}".format(_rat(c), term)
        parts.append(piece)
    if not parts:
        return "0"
    out = parts[0]
    for p in parts[1:]:
        out += (" - " + p[1:]) if p.startswith("-") else (" + " + p)
    return out


def _rat(c: Fraction) -> str:
    return str(c.numerator) if c.denominator == 1 else \
        "({}/{} : ℚ)".format(c.numerator, c.denominator)


def farkas_to_lean(data: dict, source="") -> str:
    """A Farkas certificate as a runnable `example` with its `linarith` call.

    The multipliers are not passed to Lean -- `linarith` rediscovers them, and
    quickly, once it is given the right hypotheses. Which hypotheses those are
    is precisely what the certificate found out, and precisely what is lost
    when someone retypes the lemma and hands linarith everything in scope.
    """
    from . import linarith

    p = data["payload"]
    rows = linarith.parse_rows(p["rows"])
    lams = [Fraction(x) for x in p["multipliers"]]
    sorts = p.get("sorts") or {}

    used = [(n, poly, rel, lam) for (n, poly, rel), lam in zip(rows, lams) if lam]
    hyps = [(n, poly, rel) for n, poly, rel, _ in used if n != "__goal__"
            and not n.startswith("sq_") and "*" not in n and "^" not in n]

    # Only the variables that actually appear in the used rows: binding the
    # rest would leave Lean with unused binders that say nothing.
    variables = sorted({v for _, poly, _, _ in used for m in poly for v in m})
    binder = " ".join(variables) or "_x"
    types = "ℝ" if not any(sorts.get(v) == "Int" for v in variables) else "ℤ"

    lines = [_header("farkas", data.get("digest", "?"), source), ""]
    lines.append("/-- The hypotheses the certificate actually used, and the")
    lines.append("goal they close. `linarith` is given exactly those: the")
    lines.append("certificate's whole content is which ones matter. -/")
    lines.append("example ({} : {})".format(binder, types))
    for name, poly, rel in hyps:
        lines.append("    ({} : {} {} 0)".format(
            _safe(name), _poly_to_lean(poly), _op(rel)))

    goal = next(((poly, rel) for n, poly, rel, _ in used if n == "__goal__"),
                None)
    if goal is None:
        lines.append("    : True := trivial")
    else:
        # The stored row is the NEGATED goal. Emitting the goal positively
        # rather than as `¬ (row)` is what linarith expects, and it is what
        # the lemma actually says.
        poly, rel = goal
        lines.append("    : {} {} 0 := by".format(
            _poly_to_lean(poly), _positive(rel)))
        tactic = "nlinarith" if p.get("nonlinear") else "linarith"
        # The hints ARE the certificate. nlinarith will not rediscover
        # `sq_nonneg (a - b)` on its own for a - b squared, and that row is
        # exactly what the search found; handing it over is the difference
        # between a file that compiles and one that says "failed to find a
        # contradiction".
        hints = [_safe(n) for n, _, _ in hyps] + _square_hints(p, used)
        lines.append("  {}{}".format(
            tactic, " [{}]".format(", ".join(hints)) if hints else ""))

    lines.append("")
    if p.get("nonlinear"):
        lines.append("-- nlinarith adds products and squares of the hypotheses")
        lines.append("-- itself, which is how the certificate was found too.")
    lines.append(FOOTER)
    return "\n".join(lines)


def _square_hints(payload, used) -> list:
    """`sq_nonneg (...)` for every square the certificate actually used.

    Reconstructed from the polynomial the engine recorded, not from the row's
    name: a variable may contain an underscore, and `sq_a_b` would then be
    ambiguous between two variables and one called `a_b`.
    """
    from . import linarith

    derived = payload.get("derived") or {}
    out = []
    for name, _, _, _ in used:
        info = derived.get(name)
        if not info or info.get("kind") != "square":
            continue
        poly = {(() if k == "1" else tuple(k.split(" "))): Fraction(v)
                for k, v in info["of"].items()}
        out.append("sq_nonneg ({})".format(_poly_to_lean(poly)))
    return out


def _op(rel) -> str:
    return {"<=": "≤", "<": "<", "=": "="}[rel]


def _positive(rel) -> str:
    """The negation of a stored row's relation: `p < 0` negated is `p ≥ 0`."""
    return {"<": "≥", "<=": ">", "=": "≠"}[rel]


def _safe(name) -> str:
    out = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    return ("h_" + out) if not out or out[0].isdigit() else out


# ---------------------------------------------------------------------------
# a finite classification -> a List Lean can decide
# ---------------------------------------------------------------------------


def classification_to_lean(data: dict, source="") -> str:
    """A sweep's family as a `List`, plus what was established about it.

    Lean can check `decide` over a concrete list. What it cannot check is that
    the list is COMPLETE -- that is the enumerator's claim, and it is stated
    as an axiom-shaped comment rather than smuggled in as a lemma.
    """
    p = data["payload"]
    ids = p.get("family_graph6") or p.get("ids") or []
    kind = "graph6" if p.get("family_graph6") else "id"

    lines = [_header("classification", data.get("digest", "?"), source), ""]
    lines.append("/-- The {} objects the sweep examined, as {} strings.".format(
        len(ids), kind))
    lines.append("")
    lines.append("COMPLETENESS IS NOT PROVED HERE. That this list is the whole")
    lines.append("family is the enumerator's claim; Lean sees a list. -/")
    lines.append("def family : List String := [")
    for i in range(0, len(ids), 4):
        lines.append("  " + ", ".join('"{}"'.format(x) for x in ids[i:i + 4])
                     + ("," if i + 4 < len(ids) else ""))
    lines.append("]")
    lines.append("")
    lines.append("/-- The sweep's own arithmetic, which Lean can confirm. -/")
    lines.append("example : family.length = {} := by decide".format(len(ids)))
    lines.append("example : family.Nodup := by decide")
    lines.append("")

    ev = p.get("evaluations", 0)
    cert = p.get("certified", 0)
    lines.append("-- The sweep reported: {} evaluations, {} with a certificate."
                 .format(ev, cert))
    if cert < ev:
        lines.append("-- The remaining {} were NOT certified: the predicate's"
                     .format(ev - cert))
        lines.append("-- answers are reproducible, not established.")
    lines.append(FOOTER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# a compose proof -> a skeleton with sorry exactly on the bridges
# ---------------------------------------------------------------------------


def proof_to_lean(data: dict, source="") -> str:
    """The lemma structure, with `sorry` on the bridges and nowhere else.

    This is the piece worth carrying across. `compose` already computed which
    lemmas are derived -- their certificates entail their statements -- and
    which are bridges, where a finite computation was read as a formula. A
    person transcribing by hand has to remember that boundary; here it is
    mechanical, and the bridges are listed again at the bottom so the file
    cannot be skimmed past them.
    """
    p = data["payload"]
    lines = [_header("proof", data.get("digest", "?"), source), ""]
    if p.get("title"):
        lines.append("/-! ## {} -/".format(p["title"]))
        lines.append("")

    bridges = []
    for lem in p.get("lemmas", []):
        name = _safe(lem["name"])
        derived = lem.get("derived")
        lines.append("/-- {}".format(
            t("lean.lemma.derived", engine=lem.get("engine", "?"))
            if derived else t("lean.lemma.bridge",
                              why=lem.get("bridge") or lem.get("engine", "?"))))
        lines.append("")
        lines.append("    statement (SMT-LIB2, transcribe by hand):")
        for line in (lem.get("statement_smt2") or "").strip().splitlines()[:12]:
            lines.append("      " + line)
        lines.append("-/")
        lines.append("theorem {} : True := by".format(name))
        if derived:
            lines.append("  trivial  -- certo: derived and linked; restate and prove")
        else:
            bridges.append(lem["name"])
            lines.append("  sorry    -- certo: BRIDGE, nothing proved this in Lean")
        lines.append("")

    lines.append("/-- The theorem the lemmas were composed into. -/")
    lines.append("theorem main : True := by")
    lines.append("  trivial  -- certo: restate from theorem_smt2 and close")
    lines.append("")
    lines.append("/-!")
    lines.append("## What is NOT proved in this file")
    lines.append("")
    if bridges:
        for b in bridges:
            lines.append("* `{}` -- a bridge: a finite computation read as a "
                         "formula.".format(_safe(b)))
    else:
        lines.append("* Nothing is a bridge: every lemma was derived and linked.")
    lines.append("")
    lines.append("Every statement above is a placeholder `True`. certo does "
                 "not know your")
    lines.append("Mathlib encoding, so it transcribes the structure and the "
                 "boundary, not")
    lines.append("the statements.")
    lines.append("-/")
    lines.append(FOOTER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def manifest(paths) -> dict:
    """What produced this Lean file, hashed, so the two can be tied together."""
    out = {"certo_version": __version__, "files": []}
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        raw = p.read_bytes()
        entry = {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(),
                 "bytes": len(raw)}
        if p.suffix == ".json":
            try:
                d = json.loads(raw.decode("utf-8"))
                entry["kind"] = d.get("kind")
                entry["digest"] = d.get("payload") and _digest_of(d)
                entry["provenance"] = d.get("provenance")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        out["files"].append(entry)
    return out


def _digest_of(d):
    from .certificate import Certificate

    return Certificate.from_dict(d).digest()


# ---------------------------------------------------------------------------
# compiling it
# ---------------------------------------------------------------------------


def check(path, project=None, timeout=900) -> dict:
    """Run the Lean toolchain over the emitted file, if there is one.

    "It should compile" is not a claim anyone should have to take on trust
    from a text generator, and it is the claim most likely to be wrong: three
    rounds against a real compiler is what it took to get the graph export
    right. Without a toolchain this says so rather than staying quiet.
    """
    p = Path(path)
    lake = shutil.which("lake")
    if not lake:
        return {"ran": False, "reason": t("lean.check.no_lake")}
    root = Path(project) if project else p.parent
    if not (root / "lakefile.lean").exists() and \
       not (root / "lakefile.toml").exists():
        return {"ran": False, "reason": t("lean.check.no_project", path=str(root))}
    try:
        out = subprocess.run([lake, "env", "lean", str(p)], cwd=str(root),
                             capture_output=True, text=True, timeout=timeout,
                             encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return {"ran": False, "reason": "{}: {}".format(type(e).__name__, e)}
    text = (out.stdout or "") + (out.stderr or "")
    sorries = text.count("declaration uses 'sorry'")
    return {"ran": True, "ok": out.returncode == 0, "sorries": sorries,
            "output": text.strip()[:4000]}


EXPORTERS = {
    "farkas": farkas_to_lean,
    "proof": proof_to_lean,
    "sweep": classification_to_lean,
    "domain_sweep": classification_to_lean,
    "graph_set": classification_to_lean,
}
