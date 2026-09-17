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
    "unsat_core": ["Mathlib.Data.Real.Basic", "Mathlib.Tactic.Linarith"],
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


#: The marker a hollow statement carries, in its name and in the file. Grep
#: for it: that is the point.
HOLLOW = "HOLLOW"


def _placeholder(name, why, indent="") -> list:
    """A statement certo could not render, emitted so that NOTHING mistakes it.

    `True := by trivial` compiles, carries no `sorry`, and passes an axiom
    audit -- so a placeholder written that way is invisible to every check a
    formalisation project runs, and a user found that out the hard way. It
    closes with `sorry` now, and the name says what it is.

    The goal stays `True` rather than becoming a guess at the real statement:
    guessing a Mathlib encoding is how a DIFFERENT wrong theorem gets proved,
    which is worse than an obvious hole.
    """
    return [
        indent + "theorem {}_{} : True := by".format(_safe(name), HOLLOW),
        indent + "  sorry    -- certo: {}".format(why),
    ]


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
        if derived:
            lines.extend(_placeholder(
                name, "derived and linked, but the STATEMENT is not "
                      "transcribed; restate it and prove"))
        else:
            bridges.append(lem["name"])
            lines.extend(_placeholder(
                name, "BRIDGE: a finite computation read as a formula, and "
                      "nothing proved it in Lean"))
        lines.append("")

    lines.append("/-- The theorem the lemmas were composed into. -/")
    lines.extend(_placeholder("main",
                              "restate from theorem_smt2 above and close"))
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
    lines.append("EVERY statement above is HOLLOW: the goal is `True` and "
                 "the proof is")
    lines.append("`sorry`. certo does not know your Mathlib encoding and will "
                 "not guess at")
    lines.append("one, so it transcribes the structure and the boundary, not "
                 "the statements.")
    lines.append("")
    lines.append("A hollow theorem compiles. That was never the question: it "
                 "states nothing,")
    lines.append("and it is closed with `sorry` precisely so that every audit "
                 "you already")
    lines.append("run -- `sorry` counts, axiom queries, a build gate -- sees "
                 "it too.")
    lines.append("-/")
    lines.append(FOOTER)
    return "\n".join(lines)


def _core_rows(payload):
    """The core's formulas as linarith rows, or None if they are not linear.

    The certificate stores SMT-LIB2, which is the portable form and not a
    structure anything can render. Parsing it back with z3 and running it
    through the same `as_row` the Farkas exporter uses means the two exporters
    agree by construction rather than by inspection.
    """
    import z3

    from . import linarith, z3util

    smt2 = payload.get("core_smt2") or ""
    if not smt2.strip():
        return None
    try:
        formulas = list(z3.parse_smt2_string(smt2))
    except z3.Z3Exception:
        return None

    names = list(payload.get("names") or [])
    if len(names) != len(formulas):
        # The names and the formulas are written from the same list in the
        # same order; if that ever stops being true, say nothing rather than
        # attaching a hypothesis to the wrong name.
        return None
    rows, sorts = [], {}
    for name, f in zip(names, formulas):
        try:
            poly, rel = linarith.as_row(f)
        except Exception:
            return None
        rows.append((name, poly, rel))
        # The sort comes from the formulas themselves rather than a stored
        # field: an integer regime emitted over the reals would elaborate and
        # mean something weaker than what was certified.
        for c in z3util.free_consts(f):
            sorts[str(c)] = c.sort().name()
    return rows, sorts


def core_to_lean(data: dict, source="") -> str:
    """An unsat core as a theorem skeleton: the hypotheses, and no proof."""
    p = data["payload"]
    parsed = _core_rows(p)
    if parsed is None:
        return _core_structure_only(data, source)
    rows, sorts = parsed

    hyps = [(n, poly, rel) for n, poly, rel in rows if n != "__goal__"]
    goal = next(((poly, rel) for n, poly, rel in rows if n == "__goal__"), None)
    variables = sorted({v for _, poly, _ in rows for m in poly for v in m})
    binder = " ".join(variables) or "_x"
    types = "ℤ" if any(sorts.get(v) == "Int" for v in variables) else "ℝ"

    lines = [_header("unsat_core", data.get("digest", "?"), source), ""]
    if p.get("vacuous"):
        lines.append("/-- These hypotheses cannot hold together: the regime is")
        lines.append("EMPTY. Anything proved under them is vacuously true, "
                     "which is")
        lines.append("what no `#print axioms` will tell you. -/")
    else:
        lines.append("/-- The hypotheses the core actually needed, and the "
                     "goal they")
        lines.append("close. The ones certo DROPPED are listed at the bottom: "
                     "that")
        lines.append("list is the content of the certificate. -/")
    lines.append("theorem {} ({} : {})".format(
        "regime_empty" if p.get("vacuous") else "from_core", binder, types))
    for name, poly, rel in hyps:
        lines.append("    ({} : {} {} 0)".format(
            _safe(name), _poly_to_lean(poly), _op(rel)))

    if goal is None:
        # No goal in the core means the hypotheses alone are unsatisfiable,
        # so what they entail is False -- and that IS the statement.
        lines.append("    : False := by")
        lines.extend(_core_tactic(p, hyps))
    else:
        poly, rel = goal
        lines.append("    : {} {} 0 := by".format(
            _poly_to_lean(poly), _positive(rel)))
        lines.extend(_core_tactic(p, hyps))

    lines.append("")
    lines.append("/-!")
    lines.append("## What this file does and does not say")
    lines.append("")
    dropped = [d for d in (p.get("dropped") or []) if d != "__goal__"]
    if dropped:
        lines.append("certo dropped these hypotheses as unnecessary: "
                     + ", ".join("`{}`".format(_safe(d)) for d in dropped))
    else:
        lines.append("Every hypothesis was needed: certo could drop none.")
    lines.append("")
    if p.get("vacuous"):
        lines.append("The core is VACUOUS. The statement above is that the "
                     "regime is empty,")
        lines.append("and it is the useful one: a theorem proved under these "
                     "hypotheses is")
        lines.append("true, `sorry`-free, clean on `#print axioms`, and about "
                     "nothing.")
    else:
        lines.append("The single `sorry` is the proof. certo established this "
                     "with a solver,")
        lines.append("which is a different thing from a Lean proof, and the "
                     "file does not")
        lines.append("pretend otherwise.")
    lines.append("-/")
    lines.append(FOOTER)
    return "\n".join(lines)


def _core_tactic(payload, hyps) -> list:
    """`linarith` when the certificate knows why, `sorry` when it does not.

    A bare core says WHICH hypotheses suffice and nothing licenses a tactic
    call. With Farkas multipliers attached it says why, and `linarith`
    rediscovers them in milliseconds once handed the right hypotheses --
    which is precisely what the core found out.
    """
    if not payload.get("multipliers"):
        return ["  sorry    -- certo: a core says WHICH hypotheses suffice, "
                "not why.",
                "           -- Run `certo prove` with an LP backend installed "
                "and the",
                "           -- Farkas multipliers travel in the certificate, "
                "and this",
                "           -- becomes a `linarith` call that compiles."]
    names = [_safe(n) for n, _, _ in hyps]
    return ["  linarith{}".format(
        " [{}]".format(", ".join(names)) if names else ""),
        "  -- certo: the multipliers are in the certificate; linarith",
        "  -- rediscovers them, and which hypotheses to hand it is",
        "  -- exactly what the core found out."]


def _core_structure_only(data: dict, source="") -> str:
    """Not linear arithmetic: carry the structure, not a guessed encoding."""
    p = data["payload"]
    lines = [_header("unsat_core", data.get("digest", "?"), source,
                     imports=["Mathlib"]), ""]
    lines.append("/-- The core, as SMT-LIB2. certo does not know your Mathlib")
    lines.append("encoding for this theory and will not guess at one, so the")
    lines.append("statement is carried verbatim for you to transcribe.")
    lines.append("")
    lines.append("    needed: {}".format(
        ", ".join(n for n in (p.get("names") or []) if n != "__goal__")
        or "(none)"))
    lines.append("    dropped: {}".format(
        ", ".join(d for d in (p.get("dropped") or []) if d != "__goal__")
        or "(none)"))
    lines.append("")
    for line in (p.get("core_smt2") or "").strip().splitlines()[:40]:
        lines.append("      " + line)
    lines.append("-/")
    lines.extend(_placeholder("from_core",
                              "restate from the SMT-LIB2 above and prove"))
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


EXPORTERS = {
    "farkas": farkas_to_lean,
    "unsat_core": core_to_lean,
    "proof": proof_to_lean,
    "sweep": classification_to_lean,
    "domain_sweep": classification_to_lean,
    "graph_set": classification_to_lean,
}
