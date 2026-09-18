"""Does the exported theorem say what the certificate established?

Nothing compared them. The exporter reads a certificate and writes Lean; a bug
anywhere in that path -- a dropped hypothesis, a sign, a coefficient, a goal
rendered from the wrong row -- produces a theorem that compiles, that looks
right, and that is not the one the certificate supports. And it is the exact
failure this project has already had twice, in the other direction: producer
and verifier wrong in the same place, agreeing with each other.

So this does not ask the exporter what it meant. It PARSES THE EMITTED TEXT
BACK and compares the result against the certificate, by a different route:

    certificate -> SMT-LIB2 -> z3 -> linarith rows        (what it established)
    emitted Lean text -> this parser -> linarith rows     (what it says)

Two paths, one comparison. A rendering bug shows up as a mismatch rather than
as a second opinion that happens to agree.

COMPARISON IS SEMANTIC, NOT TEXTUAL, and it has to be. `-a < 0` and `a > 0`
are the same row; the exporter deliberately states a goal positively rather
than as a negation, because that is what the lemma says and what `linarith`
expects. Both sides are normalised to `p REL 0` with a positive leading
coefficient before anything is compared.

WHAT IT DOES NOT CHECK, and says so: that the Lean statement means what you
intended in Mathlib. It checks that the statement corresponds to the
certificate. Whether the certificate encodes your problem is the question no
tool here answers, and the one `verify` has always pushed back to the reader.

The grammar parsed is only the one certo emits -- polynomials over `+ - *`,
rationals as `(p/q : ℚ)`, relations `≤ < = ≥ > ≠`, all against zero. That is
deliberate: a general Lean parser would be a different project, and a
restricted one that REFUSES what it does not recognise cannot quietly approve
something it misread.
"""
from __future__ import annotations

import re
from fractions import Fraction

from .i18n import t as _t

#: `p REL 0` as the exporter writes it, and the row relation it means.
#: The exporter states hypotheses with `_op` and the goal with `_positive`,
#: so both directions appear and both are normalised here.
RELATIONS = {"≤": "<=", "<": "<", "=": "=", "≥": ">=", ">": ">", "≠": "!="}

_HEAD = re.compile(r"^\s*(?:theorem|example|lemma)\b[^(]*\(([^:]+):")
_HYP = re.compile(r"^\s*\(([^:()]+):\s*(.+?)\s*\)\s*$")
_GOAL = re.compile(r"^\s*:\s*(.+?)\s*:=\s*by\s*$")


#: The positive form of a stored row's relation. `_positive` in the exporter,
#: kept here separately so the two can disagree and be caught rather than
#: sharing a bug.
NEGATED = {"<": ">=", "<=": ">", "=": "!=", ">=": "<", ">": "<=", "!=": "="}


class NotParseable(ValueError):
    """The text is outside the grammar certo emits. Refused, not guessed at."""


def _term(piece: str):
    """One term of a polynomial: `3 * x * y`, `-x`, `(1/2 : ℚ) * x`, `7`."""
    piece = piece.strip()
    if not piece:
        raise NotParseable(_t("leancheck.empty_term"))
    sign = Fraction(1)
    while piece.startswith(("-", "+")):
        if piece[0] == "-":
            sign = -sign
        piece = piece[1:].strip()

    factors = [f.strip() for f in piece.split("*")]
    coef, mono = sign, []
    for f in factors:
        rat = re.fullmatch(r"\(\s*(-?\d+)\s*/\s*(\d+)\s*:\s*[ℚℝ]\s*\)", f)
        if rat:
            coef *= Fraction(int(rat.group(1)), int(rat.group(2)))
            continue
        if re.fullmatch(r"-?\d+", f):
            coef *= Fraction(int(f))
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9']*", f):
            mono.append(f)
            continue
        raise NotParseable(_t("leancheck.bad_factor", got=f))
    return tuple(sorted(mono)), coef


def parse_poly(text: str) -> dict:
    """A polynomial as `{monomial: coefficient}`, the shape `linarith` uses."""
    # Split on top-level + and - only; the grammar has no brackets around
    # sums, and a rational's own `/` never appears outside `( : ℚ)`.
    pieces, depth, current = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch in "+-" and current.strip():
            pieces.append(current)
            current = ch
            continue
        current += ch
    if current.strip():
        pieces.append(current)

    out: dict = {}
    for piece in pieces:
        mono, coef = _term(piece)
        out[mono] = out.get(mono, Fraction(0)) + coef
    return {m: c for m, c in out.items() if c}


def parse_relation(text: str):
    """`<poly> REL 0` -> (polynomial, relation). Only against zero."""
    for symbol, rel in RELATIONS.items():
        if symbol in text:
            left, _, right = text.partition(symbol)
            if right.strip() != "0":
                raise NotParseable(_t("leancheck.not_zero", got=right.strip()))
            return parse_poly(left), rel
    raise NotParseable(_t("leancheck.no_relation", got=text[:60]))


def parse_statement(text: str) -> dict:
    """The binders, hypotheses and goal of the one statement in the file.

    Returns `{"variables", "hypotheses", "goal"}` with each formula as
    `(polynomial, relation)`. Raises when the text is outside the grammar --
    which for a HOLLOW file it always is, and that is the right answer there.
    """
    variables, hypotheses, goal = [], [], None
    for line in text.splitlines():
        if goal is not None:
            break
        head = _HEAD.match(line)
        if head:
            variables = head.group(1).split()
            continue
        g = _GOAL.match(line)
        if g:
            goal = parse_relation(g.group(1))
            continue
        h = _HYP.match(line)
        if h and variables:
            hypotheses.append((h.group(1).strip(),
                               parse_relation(h.group(2))))
    if goal is None:
        raise NotParseable(_t("leancheck.no_goal"))
    return {"variables": variables, "hypotheses": hypotheses, "goal": goal}


def normalise(poly: dict, rel: str):
    """`p REL 0` in one canonical form, so two spellings compare equal.

    `-a < 0` and `a > 0` are one row. The exporter states hypotheses one way
    and the goal the other, on purpose, so normalising is not tidiness -- it
    is the difference between comparing meanings and comparing strings.
    """
    flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "!=": "!="}
    if not poly:
        return (), rel
    lead = min(poly)
    if poly[lead] < 0:
        poly = {m: -c for m, c in poly.items()}
        rel = flip[rel]
    return tuple(sorted((m, str(c)) for m, c in poly.items())), rel


def rows_of(cert: dict):
    """What the certificate established, as rows. The other path."""
    from . import leanexport

    kind = cert.get("kind")
    payload = cert.get("payload") or {}
    if kind == "unsat_core":
        parsed = leanexport._core_rows(payload)
        if parsed is None:
            return None
        rows, _sorts = parsed
        return [(n, poly, rel) for n, poly, rel in rows]
    if kind == "farkas":
        from fractions import Fraction

        from . import linarith

        # Only the rows the proof USES. A hypothesis whose multiplier is zero
        # is not part of the combination -- that is the documented feature of
        # this certificate, `core` for free, and it is why the exporter leaves
        # it out of the statement. Expecting every row here made the check
        # report `missing: noise` on the one export that works, which turned a
        # correspondence check into a job that is always red. A check nobody
        # can act on is a check nobody reads.
        rows = linarith.parse_rows(payload.get("rows") or [])
        lams = [Fraction(x) for x in (payload.get("multipliers") or [])]
        if len(lams) != len(rows):
            return None          # cannot tell which were used: say so
        return [(n, poly, rel) for (n, poly, rel), lam in zip(rows, lams)
                if lam]
    return None


def correspondence(cert: dict, text: str) -> dict:
    """Does the emitted statement correspond to what the certificate says?

    Returns a report rather than a boolean, because "could not check" and
    "checked and wrong" are different answers and collapsing them is how a
    gap becomes a green tick.
    """
    if " : True := by" in text:
        return {"checked": False, "reason": _t("leancheck.hollow")}

    established = rows_of(cert)
    if established is None:
        return {"checked": False, "reason": _t("leancheck.no_rows",
                                               kind=cert.get("kind"))}
    try:
        said = parse_statement(text)
    except NotParseable as e:
        return {"checked": False, "reason": str(e)}

    want_hyp, want_goal = {}, None
    for name, poly, rel in established:
        if name == "__goal__":
            # The row stores the NEGATED goal. The exporter states it
            # positively by flipping the RELATION and keeping the polynomial
            # -- `not (p < 0)` is `p >= 0` -- so the comparison does the same.
            # Negating the polynomial instead would be a different statement
            # that happens to be equivalent, and would compare unequal.
            want_goal = normalise(poly, NEGATED[rel])
        else:
            want_hyp[name] = normalise(poly, rel)

    got_hyp = {n: normalise(p, r) for n, (p, r) in said["hypotheses"]}
    got_goal = normalise(*said["goal"])

    missing = sorted(n for n in want_hyp if n not in got_hyp)
    extra = sorted(n for n in got_hyp if n not in want_hyp)
    changed = sorted(n for n in want_hyp
                     if n in got_hyp and want_hyp[n] != got_hyp[n])
    goal_ok = want_goal is not None and want_goal == got_goal

    return {
        "checked": True,
        "ok": not missing and not extra and not changed and goal_ok,
        "goal_matches": goal_ok,
        "missing": missing, "extra": extra, "changed": changed,
        "hypotheses": len(want_hyp),
    }
