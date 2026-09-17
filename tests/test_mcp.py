"""MCP server tests. `python tests/test_mcp.py`, or with pytest."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import anyio

_WS = tempfile.mkdtemp(prefix="certo_mcp_")
os.environ["CERTO_WORKSPACE"] = _WS

from certo.mcp_server import mcp  # noqa: E402

AMGM = """
import z3
from certo import Spec
def spec():
    a, b, c, t = z3.Reals("a b c t")
    s = Spec()
    s.assume("a_pos", a > 0); s.assume("b_pos", b > 0); s.assume("c_pos", c > 0)
    s.assume("ruido", t == 42)
    s.claim((a+b)*(b+c)*(a+c) >= 8*a*b*c)
    return s
"""

RAMSEY = """
from itertools import combinations
from certo import CNF, CNFSpec
N = %d
def spec():
    cnf = CNF(title="R33")
    def x(i, j): return cnf.var("e%%d_%%d" %% (min(i,j), max(i,j)))
    for i, j in combinations(range(N), 2): x(i, j)
    for t in combinations(range(N), 3):
        a, b, c = x(t[0],t[1]), x(t[0],t[2]), x(t[1],t[2])
        cnf.add(-a,-b,-c); cnf.add(a,b,c)
    return CNFSpec(cnf=cnf)
"""


async def call(name, args):
    r = await mcp.call_tool(name, args)
    sc = getattr(r, "structuredContent", None)
    if sc is not None:
        return sc.get("result", sc) if isinstance(sc, dict) else sc
    text = r.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def run(coro):
    return anyio.run(lambda: coro)


# ---------------------------------------------------------------------------


def test_every_command_is_exposed():
    tools = {t.name for t in run(mcp.list_tools())}
    expected = {"prove", "check", "core", "synth", "opt", "cases", "enum",
                "sweep", "shrink", "bisect", "verify", "export", "dsl_guide"}
    assert expected <= tools, expected - tools


def test_dsl_guide_covers_every_spec_type():
    guide = run(call("dsl_guide", {}))
    text = guide if isinstance(guide, str) else json.dumps(guide)
    for t in ("Spec", "SynthSpec", "LPSpec", "CNFSpec", "SweepSpec", "BisectSpec"):
        assert t in text


def test_inline_spec_then_verify_by_path():
    out = run(call("core", {"spec_source": AMGM}))
    assert out["verdict"] == "proved"
    assert out["meta"]["hypotheses_dropped"] == ["ruido"]

    path = out["certificate"]["path"]
    assert (Path(_WS) / path).exists()
    assert run(call("verify", {"certificate_path": path}))["ok"]


def test_certificates_go_to_disk_not_into_the_response():
    out = run(call("cases", {"spec_source": RAMSEY % 7}))
    assert out["verdict"] == "proved"

    blob = json.dumps(out)
    assert "p cnf" not in blob          # the DIMACS does not travel
    assert len(blob) < 4000             # the response stays small
    cert = json.loads((Path(_WS) / out["certificate"]["path"]).read_text("utf-8"))
    assert "dimacs" in cert["payload"] and cert["payload"]["proof"]


def test_refusal_outside_the_workspace():
    """Every path the running platform can use to leave the workspace.

    A backslash escapes a directory on Windows and is a legal character in a
    POSIX filename, so `..\\..\\secret.json` names a file INSIDE the
    workspace there and correctly draws no refusal. Asserting otherwise tested
    Windows semantics on a Linux runner, which is the failure that found this.
    """
    escapes = ["../../etc/passwd", "../" * 6 + "secret.json",
               str(Path(tempfile.gettempdir()).resolve() / "outside.json")]
    if os.name == "nt":
        escapes.append("..\\..\\secret.json")

    for bad in escapes:
        out = run(call("verify", {"certificate_path": bad}))
        assert out.get("ok") is False, bad
        assert "workspace" in out["error"].lower(), (bad, out)
        assert out["hint"]


def test_a_backslash_name_stays_inside_the_workspace_on_posix():
    """Not a refusal, and not a hole: it is a filename, and it is confined."""
    from certo.mcp_server import _resolve, _workspace

    if os.name == "nt":
        return                      # there it is a traversal, tested above
    inside = _resolve("..\\..\\secret.json")
    assert _workspace() in inside.parents


def test_wrong_spec_type_is_rejected_with_an_actionable_message():
    """The SDK turns any exception into "Error executing tool X" and swallows
    the reason; a model reading that cannot fix its spec. The server returns
    the error as DATA, hint included."""
    out = run(call("cases", {"spec_source": AMGM}))   # returns a Spec, not a CNFSpec
    assert out.get("ok") is False
    assert "CNFSpec" in out["error"] and "Spec" in out["error"]
    assert "dsl_guide" in out["hint"]


def test_a_broken_spec_reports_the_python_error():
    out = run(call("prove", {"spec_source": "def spec(): return no_existe"}))
    assert out.get("ok") is False
    assert out["error_type"] == "NameError"
    assert out["hint"]


def test_missing_spec_function_is_explained():
    out = run(call("prove", {"spec_source": "x = 1"}))
    assert out.get("ok") is False
    assert "spec()" in out["error"]
    assert "def spec()" in out["hint"]


def test_big_lists_are_capped():
    out = run(call("enum", {"n": 6, "filters": ["connected"]}))
    assert out["graphs_total"] == 112
    assert len(out["graphs_sample"]) <= 10


def test_bisect_over_mcp_computes_ramsey():
    src = RAMSEY % 0  # placeholder, replaced below
    src = """
from itertools import combinations
from certo import CNF, CNFSpec, BisectSpec
def build(n):
    cnf = CNF()
    def x(i, j): return cnf.var("e%d_%d" % (min(i,j), max(i,j)))
    for i, j in combinations(range(n), 2): x(i, j)
    for t in combinations(range(n), 3):
        a, b, c = x(t[0],t[1]), x(t[0],t[2]), x(t[1],t[2])
        cnf.add(-a,-b,-c); cnf.add(a,b,c)
    return CNFSpec(cnf=cnf)
def spec():
    return BisectSpec(build=build, lo=3, hi=8, integer=True)
"""
    out = run(call("bisect", {"spec_source": src}))
    assert out["meta"]["threshold"] == 6
    assert run(call("verify", {"certificate_path": out["certificate"]["path"]}))["ok"]


def test_farkas_returns_the_multipliers_and_the_lean_line():
    src = """
import z3
from certo import Spec
def spec():
    x, y, z = z3.Reals("x y z")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise", z <= 100)
    s.claim(x + y >= 2)
    return s
"""
    out = run(call("farkas", {"spec_source": src}))
    assert out["verdict"] == "proved"
    assert set(out["multipliers"]) == {"x_ge_1", "y_ge_1", "__goal__"}
    assert out["lean"] == "linarith [x_ge_1, y_ge_1]"
    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert rep["ok"] and rep["solver_free"]


def test_farkas_nonlinear_is_opt_in_and_says_so():
    src = """
import z3
from certo import Spec
def spec():
    a, b = z3.Reals("a b")
    s = Spec()
    s.claim(a * a + b * b >= 2 * a * b)
    return s
"""
    off = run(call("farkas", {"spec_source": src}))
    assert off["status"] == "out_of_theory"
    assert "nonlinear" in off["detail"]

    on = run(call("farkas", {"spec_source": src, "nonlinear": True}))
    assert on["verdict"] == "proved"
    assert "sq_a_b" in on["multipliers"]
    assert run(call("verify", {"certificate_path": on["certificate"]["path"]}))["ok"]

def test_compose_over_mcp_reports_bridges_and_unused_lemmas():
    import json as _json
    import os
    from pathlib import Path

    from certo import Limits, Spec
    from certo.engines import smt

    ws = Path(os.environ["CERTO_WORKSPACE"])
    (ws / "certs").mkdir(exist_ok=True)
    import z3

    x = z3.Real("x")
    src = Spec()
    src.assume("h", x >= 1)
    src.claim(x >= 1)
    sub = smt.prove(src, Limits(timeout_ms=10_000)).certificate
    (ws / "certs" / "bridge.json").write_text(
        _json.dumps(sub.to_dict()), encoding="utf-8")

    spec_src = """
import z3
from certo import ProofSpec, Spec
k = z3.Int("k")
def spec():
    p = ProofSpec(title="mcp compose")
    p.assume("k_ge_6", k >= 6)
    p.lemma("finite", certificate="certs/bridge.json", states=(k <= 10),
            bridge="checked exhaustively")
    sub = Spec(); sub.assume("h", k >= 6); sub.claim(k >= 0)
    p.lemma("spare", proves=sub)
    p.conclude(z3.And(k >= 6, k <= 10))
    return p
"""
    out = run(call("compose", {"spec_source": spec_src, "timeout_ms": 60_000}))
    assert out["verdict"] == "proved", out
    assert out["bridges"] == ["finite"]
    assert out["unused"] == ["spare"]
    assert run(call("verify", {"certificate_path": out["certificate"]["path"]}))["ok"]

def test_bounds_over_mcp_settles_a_transcendental_claim():
    src = """
from certo import BoundSpec
def spec():
    return BoundSpec(value=lambda m: m.e / m.pi, claim=("<", "0.866"),
                     describe="e / pi", prec=64)
"""
    out = run(call("bounds", {"spec_source": src}))
    assert out["verdict"] == "proved", out
    assert out["backend"]
    assert run(call("verify", {"certificate_path": out["certificate"]["path"]}))["ok"]


def test_bounds_over_mcp_reports_running_out_of_precision_as_such():
    src = """
from certo import BoundSpec
def spec():
    return BoundSpec(value=lambda m: m.exp(1) - m.e, claim=("!=", "0"),
                     prec=64, max_prec=256)
"""
    out = run(call("bounds", {"spec_source": src}))
    assert out["status"] == "resource_exhausted"
    assert out["certificate"] is None

def test_a_bare_bool_sweep_never_summarises_as_plain_proved_over_mcp():
    """The model reads the summary, so the summary carries the level."""
    src = """
from certo import DomainSpec
def spec():
    return DomainSpec(items=list(range(20)), predicate=lambda i: i >= 0,
                      key=lambda i: "i=" + str(i))
"""
    out = run(call("sweep", {"spec_source": src}))
    assert out["verdict"] == "proved"
    assert out["predicate_level"] == "reproducible"
    assert out["meta"]["predicate_uncertified"] == 20

    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert rep["ok"]
    # The warnings are the honesty layer; dropping them from the response is
    # the same overclaim in a different place.
    assert any("carry no certificate" in w for w in rep["warnings"])
    assert rep["method"] == "cli.verify.by_replay"


def test_mcp_certificates_carry_provenance_so_they_can_be_replayed():
    src = """
from certo import DomainSpec
def spec():
    return DomainSpec(items=list(range(8)), predicate=lambda i: True,
                      key=lambda i: "i=" + str(i))
"""
    out = run(call("sweep", {"spec_source": src}))
    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert any("re-running" in c["check"] and c["ok"] for c in rep["checks"])

def test_the_algebra_tools_reach_the_model_over_mcp():
    ideal_src = """
import z3
from certo import IdealSpec
def spec():
    x, y = z3.Reals("x y")
    return IdealSpec(variables=["x", "y"],
                     equations=[x - 2, x - 3], claim=None)
"""
    out = run(call("ideal", {"spec_source": ideal_src}))
    assert out["verdict"] == "proved"
    assert out["cofactors"]
    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert rep["ok"] and rep["solver_free"]
    assert any("COMPLEX" in w for w in rep["warnings"])

    sos_src = """
import z3
from certo import SOSSpec
def spec():
    x, y = z3.Reals("x y")
    return SOSSpec(variables=["x", "y"], poly=x*x - 2*x*y + y*y)
"""
    out = run(call("sos", {"spec_source": sos_src}))
    assert out["verdict"] == "proved" and out["squares"]
    assert run(call("verify", {"certificate_path": out["certificate"]["path"]}))["ok"]


def test_number_over_mcp_refuses_a_composite():
    ok = run(call("number", {"n": 1000003}))
    assert ok["verdict"] == "proved" and ok["witness"]
    bad = run(call("number", {"n": 561}))
    assert bad["verdict"] == "refuted"
    assert bad["certificate"] is None


def test_lint_reaches_the_model_before_the_compute_is_spent():
    """The one finding worth the round trip: a regime nobody is in."""
    src = """
import z3
from certo import Spec
def spec():
    x, y = z3.Reals("x y")
    s = Spec(title="a regime nobody is in")
    s.assume("x_big", x > 10)
    s.assume("y_ok", y > 0)
    s.assume("x_small", x < 1)
    s.claim(y * y >= 0)
    return s
"""
    rep = run(call("lint", {"spec_source": src}))
    assert rep["kind"] == "Spec" and rep["errors"] == 1
    clash = [f for f in rep["findings"] if f["key"] == "spec.vacuous"]
    assert len(clash) == 1
    assert "x_big" in clash[0]["text"] and "x_small" in clash[0]["text"]
    assert "y_ok" not in clash[0]["text"]


def test_status_over_mcp_reports_what_the_workspace_still_owes():
    """A model picking up a workspace has no memory of what was established."""
    src = """
import z3
from certo import Spec
def spec():
    a, b = z3.Reals("a b")
    s = Spec(title="squares are not negative")
    s.assume("a_pos", a > 0)
    s.claim((a - b) * (a - b) >= 0)
    return s
"""
    run(call("prove", {"spec_source": src}))
    rep = run(call("status", {}))
    assert rep["certificates"] >= 1
    assert isinstance(rep["owed"], list)
    assert isinstance(rep["hollow"], list)
    assert isinstance(rep["results"], list)
    # It reads rather than re-verifies unless asked, and says which it did.
    assert rep["verified"] is False


def test_status_over_mcp_carries_a_vacuous_proof_through_as_hollow():
    src = """
import z3
from certo import Spec
def spec():
    x = z3.Real("x")
    s = Spec(title="an empty regime")
    s.assume("too_big", x > 10)
    s.assume("too_small", x < 1)
    s.claim(x == 42)
    return s
"""
    out = run(call("prove", {"spec_source": src}))
    where = str(Path(out["certificate"]["path"]).parent)
    rep = run(call("status", {"directory": where}))
    hollow = " ".join(h["text"] for h in rep["hollow"])
    assert "too_big" in hollow and "too_small" in hollow



def test_check_over_mcp_can_ask_whether_the_regime_is_non_empty():
    """The flag has to reach the model: it is who writes claim(False)."""
    src = """
import z3
from certo import Spec
def spec():
    d, k = z3.Reals("dens kappa")
    s = Spec(title="a regime")
    s.assume("dens_ok", d > z3.RealVal(1)/4)
    s.assume("kappa_large", k >= 4)
    s.assume("sparse", d <= z3.RealVal(1)/2)
    s.claim(z3.BoolVal(False))
    return s
"""
    plain = run(call("check", {"spec_source": src}))
    assert plain["verdict"] == "unsatisfiable"
    assert "hypotheses-only" in plain["detail"]

    asked = run(call("check", {"spec_source": src, "hypotheses_only": True}))
    assert asked["verdict"] == "satisfiable"
    assert asked["certificate"]["kind"] == "model"



def test_eliminate_reaches_the_model_with_the_identity_attached():
    """A determinant nobody can check is a number somebody takes on faith."""
    src = """
import z3
from certo import EliminateSpec
def spec():
    s, t = z3.Reals("s t")
    return EliminateSpec(variables=["s", "t"],
                         equations=[t**3 + s*t + 1, t*t - s],
                         eliminate="t", title="condition on s")
"""
    out = run(call("eliminate", {"spec_source": src}))
    assert out["verdict"] == "satisfiable"
    assert out["meta"]["resultant"] == "-4*s^3 + 1"
    assert out["certificate"]["kind"] == "resultant"

    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert rep["ok"] and rep["solver_free"]
    # The caveat travels with it: necessary always, sufficient only over an
    # algebraically closed field.
    assert any("algebraically closed" in w for w in rep["warnings"])



def test_parametric_reaches_the_model_as_a_statement_about_a_family():
    src = """
from fractions import Fraction
from certo import ParametricSpec
from certo.polynomials import Poly
RING = ("p",)
P = Poly.var(RING, "p")
K = lambda c: Poly.const(RING, c)
def spec():
    return ParametricSpec(
        parameters={"p": 10}, sense="max",
        objective={"a": K(1), "b": K(1)},
        constraints=[("big", {"a": K(2), "b": K(1)}, "<=", P * P),
                     ("small", {"b": K(3)}, "<=", P - K(5))],
        dual={"big": Fraction(1, 2), "small": Fraction(1, 3)},
        title="t")
"""
    out = run(call("parametric", {"spec_source": src}))
    assert out["verdict"] == "proved"
    assert "p >= 10" in out["meta"]["floor"]
    assert out["certificate"]["kind"] == "parametric_bound"

    rep = run(call("verify", {"certificate_path": out["certificate"]["path"]}))
    assert rep["ok"] and rep["solver_free"]
    assert any("integer optimum" in w for w in rep["warnings"])


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
    print("\n{}/{} passed   (workspace: {})".format(len(fns) - fails, len(fns), _WS))
    raise SystemExit(1 if fails else 0)
