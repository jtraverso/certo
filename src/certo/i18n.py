"""Message catalogue.

English is the default and the source of truth: every key must exist in
``locales/en.json``. Other languages are overlays — a missing key falls back
to English rather than showing a raw key, so a partial translation degrades
gracefully instead of breaking the output.

Selection order: ``set_lang()`` > ``--lang`` > ``$CERTO_LANG`` > ``en``.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_LANG = "en"
_LOCALES = Path(__file__).parent / "locales"
_current = None


@lru_cache(maxsize=None)
def _catalogue(lang: str) -> dict:
    path = _LOCALES / "{}.json".format(lang)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def available() -> list:
    """Language codes shipped with this install."""
    return sorted(p.stem for p in _LOCALES.glob("*.json"))


def current() -> str:
    if _current is not None:
        return _current
    env = os.environ.get("CERTO_LANG", "").strip().lower()
    return env if env and _catalogue(env) else DEFAULT_LANG


def set_lang(lang) -> str:
    """Pin the language for this process. None restores env/default."""
    global _current
    if lang is None:
        _current = None
    else:
        lang = lang.strip().lower()
        if not _catalogue(lang):
            raise ValueError(
                "unknown language {!r}; available: {}".format(
                    lang, ", ".join(available())))
        _current = lang
    return current()


def t(key: str, **kw) -> str:
    """Translate a key, falling back to English and then to the key itself."""
    lang = current()
    msg = _catalogue(lang).get(key)
    if msg is None and lang != DEFAULT_LANG:
        msg = _catalogue(DEFAULT_LANG).get(key)
    if msg is None:
        return key if not kw else "{} {}".format(key, kw)
    try:
        return msg.format(**kw) if kw else msg
    except (KeyError, IndexError):
        # A translation with the wrong placeholders must not crash a run.
        return _catalogue(DEFAULT_LANG).get(key, key).format(**kw)
