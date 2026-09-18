"""Lean 4 export: one exporter, and the shortness is the policy.

certo emits Lean for a LINEAR Farkas certificate and for nothing else. That is
not a gap waiting to be filled -- it is where the line landed after compiling
generated files against a real Mathlib, and it follows from one rule:

    emit Lean only when the output is a SMALL SELF-CONTAINED ARTEFACT whose
    content IS the certificate's data, closed by a tactic that DECIDES the
    fragment its goal lives in

A linear Farkas certificate is exactly that. certo has already verified the
multipliers exactly, `linarith` is complete for linear arithmetic over an
ordered field, and the file is thirty-eight lines: an `example`, its
hypotheses, and one tactic call. If Lean disagrees you find out here rather
than three weeks in.

WHAT WAS REMOVED AND WHY. Exporters for classifications, compose proofs, unsat
cores, symbolic quotients and equitable quotients. Each failed the rule in one
of two ways. Some emitted a HEURISTIC -- `nlinarith` adds products and squares
and tries -- so "it should compile" could not be said honestly. Others emitted
enough Lean syntax that the ENCODING became the risk: the equitable-quotient
exporter was first written as a structure with fields, three theorems and
typeclass binders, and compiled against a real Mathlib it produced a wall of
errors in four minutes -- every one of them in the scaffolding and none in the
data.

Rewriting that one as pure data got it compiling in 12.8 seconds. It was still
removed, because certo's job is the step BEFORE the proof assistant: what a
formalisation needs from a session of exploration is the numbers and the
statement, and the certificate already carries both. Somebody formalising a
result writes the structure their own project wants and cannot use this
module's namespace layout anyway.

CERTO DOES NOT WRITE LEAN IT IS NOT CONFIDENT COMPILES. `NotExportable` is the
mechanism rather than the intention: a nonlinear Farkas certificate is refused
here, with the reason and a pointer at the multipliers, instead of rendered
hopefully. A file that fails to elaborate costs its reader more than no file at
all, and teaches them not to trust the next one.

`--check` IS NOT A RELEASE GATE. Building against Mathlib costs minutes,
depends on a toolchain version, and fails in ways that say nothing about
whether certo's mathematics is right. It is a tool for the person touching an
exporter, run once, by hand -- `tests/run_lean.py`.

READING Lean stays, and it is a different capability: `hollow_count` and
`certo status` find hollow statements in files certo did not write, which is
how a `theorem X : True` that passes a build gate and a `sorry` audit gets
caught.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from . import __version__


class NotExportable(ValueError):
    """certo will not write Lean it is not confident compiles.

    The rule the exports follow: emit only when the output is a small
    self-contained artefact whose content IS the certificate's data. A
    certificate whose data would need a tactic call certo cannot predict the
    behaviour of is refused here rather than rendered hopefully -- a file that
    fails to elaborate costs its reader more than no file at all, and teaches
    them not to trust the next one.
    """
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


#: The marker a hollow statement carries, in its name and in the file. Grep
#: for it: that is the point.
HOLLOW = "HOLLOW"


def hollow_count(text: str) -> int:
    """How many placeholders a generated file carries."""
    return text.count(" : True := by")


def farkas_to_lean(data: dict, source="") -> str:
    """A Farkas certificate as a runnable `example` with its `linarith` call.

    The multipliers are not passed to Lean -- `linarith` rediscovers them, and
    quickly, once it is given the right hypotheses. Which hypotheses those are
    is precisely what the certificate found out, and precisely what is lost
    when someone retypes the lemma and hands linarith everything in scope.
    """
    from . import linarith

    p = data["payload"]

    # A degree-2 Positivstellensatz certificate would go out as `nlinarith`,
    # and `nlinarith` is a HEURISTIC: it adds products and squares and tries.
    # Every other tactic certo emits DECIDES the fragment its goal lives in,
    # so this is the one case where "it should compile" could not be said
    # honestly -- and it is refused rather than written hopefully. The
    # multipliers are in the certificate and can be transcribed.
    if p.get("nonlinear"):
        raise NotExportable(t("lean.farkas.nonlinear"))

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
        # No goal row: there is nothing to state, so this is a placeholder and
        # is marked as one rather than closed with `trivial`.
        lines.append("    : True := by")
        lines.append("      sorry    -- certo: {} no goal row in the "
                     "certificate".format(HOLLOW))
    else:
        # The stored row is the NEGATED goal. Emitting the goal positively
        # rather than as `¬ (row)` is what linarith expects, and it is what
        # the lemma actually says.
        poly, rel = goal
        lines.append("    : {} {} 0 := by".format(
            _poly_to_lean(poly), _positive(rel)))
        # `linarith` is handed exactly the hypotheses the certificate used --
        # not everything in scope. Narrowing the list is the difference
        # between a call that closes and one that times out when somebody
        # retypes the lemma later with more around it.
        hints = [_safe(n) for n, _, _ in hyps]
        lines.append("  linarith{}".format(
            " [{}]".format(", ".join(hints)) if hints else ""))

    lines.append("")
    lines.append(FOOTER)
    return _trim_header("\n".join(lines))


def _trim_header(text: str) -> str:
    """Drop the promise to list `sorry`s when the file carries none.

    A small thing, and the kind of small thing that makes a generated file
    feel unread by whoever generated it.
    """
    body = text.split("-/", 1)[1] if "-/" in text else text
    if "sorry" in body:
        return text
    return text.replace(
        "is right. Each\n"
        "  `sorry` below marks a place where something outside Lean was"
        " relied on, and\n"
        "  they are listed at the end.",
        "is right.\n"
        "  There is no `sorry` here: certo verified the multipliers exactly,"
        " and\n"
        "  `linarith` is complete for the fragment this goal lives in.")


def _op(rel) -> str:
    return {"<=": "≤", "<": "<", "=": "="}[rel]


def _positive(rel) -> str:
    """The negation of a stored row's relation: `p < 0` negated is `p ≥ 0`."""
    return {"<": "≥", "<=": ">", "=": "≠"}[rel]


def _safe(name) -> str:
    out = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    return ("h_" + out) if not out or out[0].isdigit() else out


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
        if p.suffix == ".lean":
            # How many of its theorems state nothing. A manifest that recorded
            # only a hash would tie the file to its source and still let a
            # hollow one travel as evidence.
            n = hollow_count(raw.decode("utf-8", errors="replace"))
            entry["hollow"] = n
            if n:
                entry["note"] = ("{} theorem(s) state `True` and are closed "
                                 "with `sorry`: transcribe them before "
                                 "citing this file".format(n))
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
        # ABSOLUTE: the file is named relative to wherever the user ran certo,
        # and lake runs with cwd inside the Lean project. Passing it through
        # as given made lake look for `.github/lean/.github/lean/...` and
        # report "no such file or directory" -- which read as a compile
        # failure, so `--check` had never actually compiled anything in CI.
        out = subprocess.run([lake, "env", "lean", str(p.resolve())],
                             cwd=str(root),
                             capture_output=True, text=True, timeout=timeout,
                             encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return {"ran": False, "reason": "{}: {}".format(type(e).__name__, e)}
    text = (out.stdout or "") + (out.stderr or "")
    sorries = text.count("declaration uses 'sorry'")
    # Compiling was never the question. A file whose theorems all state `True`
    # builds cleanly and says nothing, so the count travels beside `ok` and
    # the caller is expected to treat it as a failure.
    hollow = hollow_count(p.read_text(encoding="utf-8", errors="replace"))
    return {"ran": True, "ok": out.returncode == 0, "sorries": sorries,
            "hollow": hollow, "output": text.strip()[:4000]}


#: kind -> the function that writes it. ONE entry, and the shortness is the
#: policy rather than an accident -- see the module docstring.
EXPORTERS = {
    "farkas": farkas_to_lean,
}
