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

WHEN TO ADD AN EXPORTER, and it is a narrower rule than it looks:

    emit Lean only when the output is a SMALL SELF-CONTAINED ARTEFACT whose
    content IS the certificate's data

and not when it would be a SCAFFOLD for a proof somebody else will structure
their own way. The difference is visible in what already exists here. A Farkas
certificate becomes a ten-line `example` with its multipliers: small, runnable,
useful the moment it lands. An equitable quotient was first written as a
`structure` with fields, three theorems and typeclass binders -- a formalisation
project rather than an artefact -- and it did not compile. Every one of its
errors was in the scaffolding and none was in the data, which is the whole
lesson: the scaffolding carried all the risk and none of the value. Somebody
formalising that result writes the structure their own project wants and cannot
use this module's namespace layout anyway.

So that exporter now emits the numbers, the identities among them as `decide`
examples, and the obligation as prose. It imports nothing and elaborates in
seconds.

CERTO DOES NOT WRITE LEAN IT IS NOT CONFIDENT COMPILES. `NotExportable` is the
mechanism: a certificate whose data would need literals and a tactic call whose
behaviour cannot be predicted from here is refused, with the reason, rather
than rendered hopefully. A file that fails to elaborate costs its reader more
than no file at all and teaches them not to trust the next one -- and the
certificate already carries the numbers.

AND `--check` IS NOT A RELEASE GATE. Building a file against Mathlib costs
minutes, depends on a toolchain version, and fails in ways that say nothing
about whether certo's mathematics is right. It is a tool for the person adding
an exporter, run once, by hand. certo's job is the step BEFORE the proof
assistant; wiring its release cycle to one would be adopting the cost of a
different tool without taking on its work.
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

    imports = (["Mathlib.Tactic.Omega"]
               if _integer(variables, sorts) and _is_linear(rows)
               else None)
    lines = [_header("unsat_core", data.get("digest", "?"), source,
                     imports=imports), ""]
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

    # `omega` decides linear integer arithmetic outright, so the file closes
    # with no `sorry` and no multipliers. It does not do variable times
    # variable, and offering it a non-linear goal would emit a tactic call
    # that fails on a statement that is true.
    use_omega = _integer(variables, sorts) and _is_linear(rows)

    if goal is None:
        # No goal in the core means the hypotheses alone are unsatisfiable,
        # so what they entail is False -- and that IS the statement.
        lines.append("    : False := by")
        lines.extend(_core_tactic(p, hyps, omega=use_omega))
    else:
        poly, rel = goal
        lines.append("    : {} {} 0 := by".format(
            _poly_to_lean(poly), _positive(rel)))
        lines.extend(_core_tactic(p, hyps, omega=use_omega))

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
    elif use_omega:
        # There is no `sorry` in this file, and saying there is one would be
        # the same lie as a hollow theorem, in the other direction: a reader
        # who trusts the footer looks for a hole that is not there, and one
        # who checks stops trusting the footer.
        lines.append("There is NO `sorry` here. Linear integer arithmetic is "
                     "decidable and")
        lines.append("`omega` decides it, so Lean proves this statement "
                     "itself. What the")
        lines.append("certificate contributed is WHICH hypotheses it rests on "
                     "-- the ones")
        lines.append("listed above, with the rest dropped.")
        lines.append("")
        lines.append("What is still yours to check: that these hypotheses say "
                     "what you meant.")
    else:
        lines.append("The single `sorry` is the proof. certo established this "
                     "with a solver,")
        lines.append("which is a different thing from a Lean proof, and the "
                     "file does not")
        lines.append("pretend otherwise.")
    lines.append("-/")
    lines.append(FOOTER)
    return "\n".join(lines)


def _is_linear(rows) -> bool:
    """Every monomial of degree at most one: no variable times a variable."""
    return all(len(mono) <= 1 for _n, poly, _rel in rows for mono in poly)


def _integer(variables, sorts) -> bool:
    """Every variable an integer. A mixed problem is not `omega`'s."""
    return bool(variables) and all(sorts.get(v) == "Int" for v in variables)


def _core_tactic(payload, hyps, omega=False) -> list:
    """The tactic that closes the goal, or `sorry` when nothing licenses one.

    Three cases, and the first is the one that was missing.

    LINEAR INTEGER ARITHMETIC gets `omega`, and it needs no multipliers,
    because `omega` is not searching for a combination -- it DECIDES. Linear
    integer arithmetic is Presburger without quantifiers, and a core over the
    integers used to export as a `sorry` even when the statement was
    decidable, which is the common case in combinatorics.

    WITH FARKAS MULTIPLIERS the certificate says why, and `linarith`
    rediscovers them in milliseconds once handed the right hypotheses -- which
    is precisely what the core found out.

    WITHOUT EITHER, `sorry`. A bare core says WHICH hypotheses suffice and
    nothing licenses a tactic call, and emitting one that fails would be worse
    than an honest hole.
    """
    if omega:
        return ["  omega",
                "  -- certo: linear integer arithmetic is decidable, and",
                "  -- `omega` decides it. No multipliers are needed: this is",
                "  -- not a search for a combination, it is a decision",
                "  -- procedure, and the certificate's job was to say WHICH",
                "  -- hypotheses the statement rests on."]
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


# ---------------------------------------------------------------------------
# a symbolic quotient -> the identity `ring` closes, the window `decide` does
# ---------------------------------------------------------------------------


def _poly_over(poly: dict, ring) -> str:
    """A serialised `Poly` as Lean source, in the parameter names."""
    terms = {}
    for key, coef in poly.items():
        exps = [int(x) for x in key.split(" ")]
        mono = []
        for name, e in zip(ring, exps):
            mono.extend([name] * e)
        terms[tuple(mono)] = coef
    return _poly_to_lean(terms)


def parametric_symmetry_to_lean(data: dict, source="") -> str:
    """Three kinds of statement, and the file keeps them apart.

    The ARITHMETIC Lean can confirm outright: the multiplicities are
    polynomials, and that they sum to the object count is an identity `ring`
    closes. No `sorry`, no hand-waving, and it is the piece a formalisation
    actually wants -- the accounting behind "one variable per orbit".

    The WINDOW, as examples `decide` closes: at each parameter point the
    orbits have these sizes and the program has these rows. Finite facts about
    numbers, which is exactly what a proof assistant is cheap at.

    The BRIDGE, and it gets a `sorry` and a name that says so: that the
    declared group really has these orbits for EVERY parameter value. certo
    checked that on the window and nowhere else, so claiming it here would be
    the one move this whole design exists to refuse.
    """
    p = data["payload"]
    ring = tuple(p["parameters"])
    args = " ".join(ring)
    binder = "({} : ℕ)".format(" ".join(ring))

    lines = [_header("parametric_symmetry", data.get("digest", "?"), source),
             "",
             "-- Every multiplicity is a polynomial over the whole parameter",
             "-- ring, so a definition that does not mention one of them is",
             "-- normal rather than a mistake.",
             "set_option linter.unusedVariables false",
             ""]
    lines.append("/-! ## The orbit multiplicities, as polynomials -/")
    lines.append("")
    for name, poly in sorted(p["orbits"].items()):
        lines.append("/-- The size of the `{}` orbit. -/".format(name))
        lines.append("def mult_{} {} : ℚ := {}".format(
            _safe(name), binder, _poly_over(poly, ring)))
        lines.append("")

    lines.append("/-- Every object lies in exactly one orbit. -/")
    lines.append("def objects {} : ℚ := {}".format(
        binder, _poly_over(p["objects"], ring)))
    lines.append("")
    lines.append("/-- The accounting behind \"one variable per orbit\": the")
    lines.append("multiplicities partition the objects. This is arithmetic and")
    lines.append("Lean closes it outright. -/")
    total = " + ".join("mult_{} {}".format(_safe(n), args)
                       for n in sorted(p["orbits"]))
    lines.append("theorem multiplicities_partition {} :".format(binder))
    lines.append("    {} = objects {} := by".format(total, args))
    lines.append("  unfold {} objects".format(
        " ".join("mult_" + _safe(n) for n in sorted(p["orbits"]))))
    # `push_cast` was here and the linter reported it doing nothing: the
    # multiplicities are already rationals, so there is no cast to push. A
    # generated file that emits warnings teaches its reader to skim warnings.
    lines.append("  ring")
    lines.append("")

    lines.append("/-! ## The row conditions -/")
    lines.append("")
    for row in p["rows"]:
        conds = [_poly_over(g, ring) + " ≥ 0" for g in row["when"]]
        body = " ∧ ".join(conds) if conds else "True"
        lines.append("/-- `{}` contributes a row only here. -/".format(
            row["name"]))
        lines.append("def exists_{} {} : Prop := {}".format(
            _safe(row["name"]), "({} : ℤ)".format(" ".join(ring)), body))
        lines.append("")

    lines.append("/-! ## The window certo actually checked -/")
    lines.append("")
    shown = p["points"][:12]
    for row in shown:
        at = ", ".join("{} = {}".format(k, v)
                       for k, v in sorted(row["point"].items()))
        sizes = ", ".join("{}: {}".format(k, v)
                          for k, v in sorted(row["sizes"].items()))
        rows_here = ", ".join(row["rows"]) or "none"
        lines.append("-- {}  ->  orbit sizes {}; rows present: {}".format(
            at, sizes, rows_here))
        for name, size in sorted(row["sizes"].items()):
            lines.append("example : mult_{} {} = {} := by norm_num [mult_{}]"
                         .format(_safe(name),
                                 " ".join(str(row["point"][k]) for k in ring),
                                 size, _safe(name)))
        lines.append("")
    if len(p["points"]) > len(shown):
        lines.append("-- ... and {} further window points, in the certificate."
                     .format(len(p["points"]) - len(shown)))
        lines.append("")

    lines.append("/-! ## The bridge, which certo did NOT prove -/")
    lines.append("")
    lines.append("/-- That the declared group really has these orbits, with")
    lines.append("these sizes, for EVERY parameter value -- not only at the")
    lines.append("{} points certo examined. This is the step from the window"
                 .format(len(p["points"])))
    lines.append("to the region, and it is the whole reason this file marks")
    lines.append("it instead of stating it as established. -/")
    lines.extend(_placeholder("orbits_are_uniform_in_the_parameters",
                              "checked on a finite window only"))
    lines.append("")
    lines.append(FOOTER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# an equitable quotient -> the data, and the obligation stated in prose
# ---------------------------------------------------------------------------

#: The statement a formalisation has to prove, as prose. NOT emitted as a
#: `structure` with fields and a `theorem` with a `sorry`: the first version of
#: this exporter did that, and every one of its compile errors was in the
#: scaffolding while none was in the data. Somebody formalising this writes the
#: structure their own project wants, and cannot use certo's namespace layout
#: anyway -- so what is worth carrying across is the numbers and what they mean.
OBLIGATION = """\
/-!
# The obligation

`certo quotient` checked a partition of a linear program's rows and columns
and established that the physical program and its quotient have the SAME SET
of attainable values. Written out, with `E i` the resources of class `i` and
`C j` the objects of class `j`:

  Proj x j = sum over C in class j of x C          the class TOTAL MASS
  Lift z C = z (class C) / M (class C)             spread evenly

  physical:  max sum_C w C * x C   s.t.  sum_C A e C * x C <= b e,  x >= 0
  quotient:  max sum_j w j * z j   s.t.  sum_j B i j * z j <= N i * b i, z >= 0

  theorem: {v | exists x, physicalFeasible x and physicalValue x = v}
         = {v | exists z, quotientFeasible z and quotientValue z = v}

Projection sums the physical rows of a class, so a feasible `x` gives a
feasible `Proj x` of the same value. Lifting uses regularity the other way:
for `e` in class `i`, `sum_C A e C * Lift z C = (1 / N i) * sum_j B i j * z j`.
And `Proj (Lift z) = z`. Equality of OPTIMA is a corollary and needs no
duality.

## What certo checked, and it is the hypotheses rather than the theorem

  * the classes partition the rows and the columns, with no empty fibre
  * capacities and senses are constant on each row class
  * weights and bounds are constant on each column class
  * REGULARITY both ways, and they are different quantities:
      H i j   one resource of class i is used by this much of object class j
      B i j   one object of class j uses this many resources of class i
    Lifting needs H, the quotient's matrix needs B, and using one where the
    other belongs builds a quotient that is simply wrong.

The double count `N i * H i j = M j * B i j` ties the two. It is a CONSEQUENCE
of the two regularities rather than a third hypothesis, and it is below as
data because it is what catches one of them having been used as the other.

## What is NOT claimed

INTEGRALITY. The equivalence is between the FRACTIONAL programs. An integer
orbit mass need not lift to integer objects: on K4 with triangles only both
fractional programs give 4 while the integer packing gives 2.

THE PARTITION. That these classes are the ones the problem has is the spec's
claim. certo checked that the partition SUPPORTS the equivalence, against the
matrix -- not that it is the partition you meant.
-/"""


def _nat_list(values) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def equitable_quotient_to_lean(data: dict, source="") -> str:
    """The class data and the double count, and nothing that needs a tactic.

    Everything here is a literal or a decidable equation over `Nat`, so the
    file imports nothing and elaborates in seconds. That is the whole design:
    certo emits Lean when the output is a small self-contained artefact whose
    content IS the certificate's data, and does not emit Lean when it would be
    a scaffold for a proof somebody else will structure their own way.

    A quotient whose data are not integral is refused rather than rendered
    with rationals and a tactic call -- a file certo cannot be confident
    compiles is a file certo should not write.
    """
    p = data["payload"]
    N = {k: int(v) for k, v in p["N"].items()}
    M = {k: int(v) for k, v in p["M"].items()}
    rows, cols = sorted(N), sorted(M)
    B = {tuple(k.split("|", 1)): Fraction(v) for k, v in p["B"].items()}
    H = {tuple(k.split("|", 1)): Fraction(v) for k, v in p["H"].items()}

    fractional = [k for k, v in list(B.items()) + list(H.items())
                  if v.denominator != 1 or v < 0]
    if fractional:
        raise NotExportable(t("lean.quotient.not_integral",
                              n=len(fractional),
                              names="; ".join("{}|{}".format(*k)
                                              for k in fractional[:2])))

    lines = [_header("equitable_quotient", data.get("digest", "?"), source,
                     imports=[]), "", OBLIGATION, ""]

    lines.append("/-- Resource classes, in order, with their sizes. -/")
    lines.append("def rowSizes : List Nat := " + _nat_list(N[r] for r in rows))
    for r in rows:
        lines.append("--   {}".format(r))
    lines.append("")
    lines.append("/-- Object classes, in order, with their sizes. -/")
    lines.append("def colSizes : List Nat := " + _nat_list(M[c] for c in cols))
    lines.append("")

    lines.append("/-- Every class pair with a non-zero incidence, as")
    lines.append("`(N i, H i j, M j, B i j)`. -/")
    lines.append("def incidence : List (Nat \u00d7 Nat \u00d7 Nat \u00d7 Nat) := [")
    pairs = sorted(set(B) | set(H))
    for n, (i, j) in enumerate(pairs):
        lines.append("  ({}, {}, {}, {}){}    -- {} / {}".format(
            N[i], int(H.get((i, j), 0)), M[j], int(B.get((i, j), 0)),
            "," if n + 1 < len(pairs) else "", i, j))
    lines.append("]")
    lines.append("")

    lines.append("/-- The double count, on every pair at once. -/")
    lines.append("example :")
    lines.append("    incidence.all (fun e => e.1 * e.2.1 == e.2.2.1 *"
                 " e.2.2.2) = true := by")
    lines.append("  decide")
    lines.append("")
    lines.append("/-- The classes account for the physical program. -/")
    lines.append("example : rowSizes.sum = {} := by decide".format(
        p["physical_rows"]))
    lines.append("example : colSizes.sum = {} := by decide".format(
        p["physical_columns"]))
    lines.append("example : rowSizes.length = {} := by decide".format(len(rows)))
    lines.append("example : colSizes.length = {} := by decide".format(len(cols)))
    lines.append(FOOTER)
    return "\n".join(lines)


EXPORTERS = {
    "farkas": farkas_to_lean,
    "equitable_quotient": equitable_quotient_to_lean,
    "parametric_symmetry": parametric_symmetry_to_lean,
    "unsat_core": core_to_lean,
    "proof": proof_to_lean,
    "sweep": classification_to_lean,
    "domain_sweep": classification_to_lean,
    "graph_set": classification_to_lean,
}
