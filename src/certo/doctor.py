"""What this install can and cannot do, and what each gap costs.

Installing every extra pulls in a fair chain of dependencies, and most people
need none of it. So the answer to "what do I actually have?" should not be
read off an import error in the middle of a run.

Every row says the same three things: whether the capability is there, what it
is for, and **what happens without it**. A missing optional tool is almost
never fatal here -- there is a slower or narrower fallback -- and a checklist
of red crosses that does not say so reads as a broken install.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .i18n import t


def _module(name):
    try:
        importlib.import_module(name)
        return True, ""
    except ImportError:
        return False, ""


def _binary(name, args=("--version",), must_run=False):
    """On PATH, and -- when `must_run` -- actually able to answer.

    `lake` on a machine with no toolchain is on PATH and reports an error, so
    "the binary exists" is the wrong question for anything we intend to run.
    """
    path = shutil.which(name)
    if not path:
        return False, ""
    try:
        out = subprocess.run([path, *args], capture_output=True, text=True,
                             timeout=20, encoding="utf-8",
                             errors="replace")
    except (OSError, subprocess.SubprocessError):
        return not must_run, path
    first = (out.stdout or out.stderr or "").strip().splitlines()
    detail = first[0][:70] if first else path
    if must_run and out.returncode != 0:
        return False, detail
    return True, detail


def _z3_version():
    try:
        import z3
        return True, z3.get_version_string()
    except ImportError:
        return False, ""


def _flint():
    ok, _ = _module("flint")
    if not ok:
        return False, ""
    import flint
    return True, "Arb via python-flint " + getattr(flint, "__version__", "?")


def _geng():
    # nauty's geng exits non-zero on --version, so ask it for nothing instead.
    return _binary("geng", ("-h",))


def _lean():
    return _binary("lake", ("--version",), must_run=True)


CHECKS = [
    # (key, required, probe)
    ("python", True, lambda: (sys.version_info >= (3, 11),
                              sys.version.split()[0])),
    ("z3", True, _z3_version),
    ("pulp", True, lambda: _module("pulp")),
    ("mcp", False, lambda: _module("mcp")),
    ("flint", False, _flint),
    ("mpmath", False, lambda: _module("mpmath")),
    ("nauty", False, _geng),
    ("cadical", False, lambda: _binary("cadical")),
    ("kissat", False, lambda: _binary("kissat")),
    ("drat_trim", False, lambda: _binary("drat-trim", ())),
    ("lean", False, _lean),
]


def report() -> dict:
    """Run every probe. Returns rows plus a count of what is missing."""
    rows, missing_required = [], 0
    for key, required, probe in CHECKS:
        try:
            ok, detail = probe()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, "{}: {}".format(type(e).__name__, e)
        if required and not ok:
            missing_required += 1
        rows.append({
            "key": key,
            "ok": bool(ok),
            "required": required,
            "detail": detail,
            "what": t("doctor.what." + key),
            "without": "" if ok else t("doctor.without." + key),
        })

    caps = {r["key"]: r["ok"] for r in rows}
    return {
        "rows": rows,
        "missing_required": missing_required,
        "numerics": caps["flint"] or caps["mpmath"],
        "sat_external": caps["cadical"] or caps["kissat"],
        "ok": missing_required == 0,
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


def mcp_status(workspace=None) -> dict:
    """Is the server registered, and does it actually start?

    Registered and working are different questions, and the second is the one
    people mean. Importing the server module in a subprocess answers it
    without needing a client.
    """
    ws = Path(workspace or os.environ.get("CERTO_WORKSPACE", Path.cwd()))
    cfg = Path.cwd() / ".mcp.json"
    out = {
        "workspace": str(ws.resolve()),
        "config_present": cfg.exists(),
        "config_path": str(cfg),
        "command_on_path": bool(shutil.which("certo-mcp")),
    }
    sdk, _ = _module("mcp")
    out["sdk"] = sdk
    if not sdk:
        out["starts"] = False
        out["detail"] = t("doctor.mcp.no_sdk")
        return out

    probe = subprocess.run(
        [sys.executable, "-c", "import certo.mcp_server as m; print(m.__name__)"],
        capture_output=True, text=True, timeout=60,
        encoding="utf-8", errors="replace")
    out["starts"] = probe.returncode == 0
    out["detail"] = ((probe.stderr or "").strip().splitlines() or [""])[-1][:200] \
        if probe.returncode else ""
    return out


MCP_ENTRY = {
    "mcpServers": {
        "certo": {"command": "certo-mcp", "env": {"CERTO_WORKSPACE": "."}}
    }
}


def register_mcp(path=None) -> dict:
    """Write `.mcp.json`, merging rather than replacing.

    Replacing would drop every other server the project has registered, which
    is a rude thing for a diagnostic command to do.
    """
    import json

    p = Path(path or (Path.cwd() / ".mcp.json"))
    existing = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"written": False, "path": str(p),
                    "detail": t("doctor.mcp.bad_json", path=str(p))}

    servers = dict(existing.get("mcpServers") or {})
    already = servers.get("certo") == MCP_ENTRY["mcpServers"]["certo"]
    servers["certo"] = MCP_ENTRY["mcpServers"]["certo"]
    existing["mcpServers"] = servers
    p.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "path": str(p), "already": already,
            "servers": sorted(servers)}
