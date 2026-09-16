"""Language layer. `python tests/test_i18n.py`, or with pytest."""
from __future__ import annotations

import json
import pathlib

import certo
import re
from pathlib import Path

from certo import i18n

LOCALES = Path(i18n.__file__).parent / "locales"
SRC = Path(i18n.__file__).parent


def _catalogue(code):
    return json.loads((LOCALES / "{}.json".format(code)).read_text(encoding="utf-8"))


def test_english_is_the_default():
    i18n.set_lang(None)
    assert i18n.current() == "en"
    assert i18n.t("verdict.proved") == "PROVED"


def test_spanish_is_available_and_switchable():
    assert "es" in i18n.available()
    try:
        i18n.set_lang("es")
        assert i18n.t("verdict.proved") == "DEMOSTRADO"
    finally:
        i18n.set_lang(None)
    assert i18n.t("verdict.proved") == "PROVED"


def test_unknown_language_is_refused():
    try:
        i18n.set_lang("xx")
        raise AssertionError("it accepted a language that does not exist")
    except AssertionError:
        raise
    except ValueError as e:
        assert "available" in str(e)


def test_a_missing_key_falls_back_to_english():
    """A partial translation must degrade, never break the output."""
    en, es = _catalogue("en"), _catalogue("es")
    missing = set(en) - set(es)
    try:
        i18n.set_lang("es")
        for key in list(missing)[:5]:
            assert i18n.t(key) == en[key]
        assert i18n.t("no.such.key.anywhere") == "no.such.key.anywhere"
    finally:
        i18n.set_lang(None)


def test_no_translation_has_keys_english_lacks():
    """English is the source of truth: an orphan key is a translation bug."""
    en = set(_catalogue("en"))
    for code in i18n.available():
        if code == "en":
            continue
        orphans = set(_catalogue(code)) - en
        assert not orphans, "{}: {}".format(code, sorted(orphans)[:5])


def test_translations_use_the_same_placeholders():
    """A translation with the wrong placeholders would crash at format time."""
    en = _catalogue("en")
    holes = lambda s: set(re.findall(r"\{(\w+)", s))  # noqa: E731
    for code in i18n.available():
        if code == "en":
            continue
        cat = _catalogue(code)
        for key, text in cat.items():
            if key in en:
                assert holes(text) == holes(en[key]), "{}:{}".format(code, key)


def test_every_literal_key_used_in_the_code_exists_in_english():
    en = set(_catalogue("en"))
    used = set()
    for py in SRC.rglob("*.py"):
        used |= set(re.findall(r'\bt\(\s*"([a-z][\w.]*)"', py.read_text("utf-8")))
    # Keys ending in "." are prefixes built at runtime ("verdict." + value);
    # the families they index are checked below instead.
    unknown = {k for k in used if not k.endswith(".") and k not in en}
    assert not unknown, sorted(unknown)


def test_the_runtime_built_key_families_are_complete():
    """`t("verdict." + verdict.value)` must resolve for every enum value."""
    from certo.status import Verdict

    en = set(_catalogue("en"))
    for v in Verdict:
        assert "verdict." + v.value in en, v

    # Scoped banners and notes: whatever cli.py declares must exist.
    from certo import cli

    for command, verdict in cli.SCOPED:
        assert "scope.{}.{}".format(command, verdict.value) in en
    for command, verdict in cli.SCOPE_NOTE:
        assert "note.{}.{}".format(command, verdict.value) in en

    # `check` names a constant claim by what the literal was.
    for which in ("false", "true"):
        assert "cli.check.constant." + which in en, which


def test_certificates_carry_the_note_key_not_the_rendered_text():
    """A certificate must read correctly whatever language produced it."""
    from certo.certificate import Certificate, model_certificate

    try:
        i18n.set_lang("es")
        cert = model_certificate("(assert true)", {})
        assert cert.note_key == "cert.note.model"
        assert "sustituyendo" in cert.note
        raw = json.loads(json.dumps(cert.to_dict()))
    finally:
        i18n.set_lang(None)

    back = Certificate.from_dict(raw)      # same certificate, English reader
    assert back.note_key == "cert.note.model"
    assert "substitution" in back.note



def test_every_lint_finding_has_a_message_in_both_languages():
    """`lint` builds "lint." + key, which the literal-key sweep cannot see.

    A finding whose message is missing renders as the key itself, which is
    the one output shape nobody can act on.
    """
    src = (SRC / "lint.py").read_text(encoding="utf-8")
    keys = {"lint." + m for m in re.findall(r'_f\(\w+, "([^"]+)"', src)}
    assert len(keys) > 30, keys

    for lang in ("en", "es"):
        cat = _catalogue(lang)
        missing = sorted(k for k in keys if k not in cat)
        assert not missing, (lang, missing)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn()
            print("[ok] " + fn.__name__)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print("[XX] {}: {}: {}".format(fn.__name__, type(e).__name__, e))
    print("\n{}/{} passed".format(len(fns) - fails, len(fns)))
    raise SystemExit(1 if fails else 0)
