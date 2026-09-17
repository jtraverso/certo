"""Generic domains, programmable filters, ranges, packings and Lean export."""
from __future__ import annotations

import json
import pathlib
from fractions import Fraction

from certo import (DomainSpec, Graph, Limits, Outcome, PackingSpec, SweepSpec,
                   loads_from_dual, verify)
from certo.certificate import Certificate
from certo.engines import domain, graphsearch, lp, shrink
from certo.graphs import is_chordal
from certo.status import Status, Verdict

LIM = Limits(timeout_ms=20_000)


def _roundtrip(cert):
    return Certificate.from_dict(json.loads(json.dumps(cert.to_dict())))


# --- sweeps over an arbitrary finite domain --------------------------------


def _pairs(lo=2, hi=6):
    return [(s, r) for s in range(lo, hi) for r in range(lo, hi)]


def test_domain_sweep_refutes_and_certifies():
    spec = DomainSpec(
        items=_pairs(),
        predicate=lambda p: p[0] * p[1] >= p[0] + p[1] + 3,
        key=lambda p: "s={},r={}".format(*p),
    )
    r = domain.sweep_domain(spec, LIM)
    assert r.verdict is Verdict.REFUTED
    assert "s=2,r=2" in r.meta["counterexamples"]
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_domain_sweep_calibrates_exactly_without_a_predicate():
    spec = DomainSpec(items=_pairs(),
                      collect=lambda p: Fraction(p[0], p[1]),
                      key=lambda p: "{}/{}".format(*p))
    r = domain.sweep_domain(spec, LIM)
    assert r.verdict is Verdict.SATISFIABLE          # measures, does not refute
    cal = r.meta["calibration"]
    assert cal["min"] == "2/5" and cal["max"] == "5/2"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_domain_sweep_catches_duplicate_ids():
    """Two items sharing an id would silently collapse the domain."""
    spec = DomainSpec(items=[(1, 2), (2, 1)], collect=lambda p: p[0],
                      key=lambda p: "same")
    cert = _roundtrip(domain.sweep_domain(spec, LIM).certificate)
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("unique" in c[0] and not c[1] for c in rep.checks)


# --- programmable filters --------------------------------------------------


def test_a_callable_works_as_a_filter():
    dense = lambda g: g.m >= 8  # noqa: E731
    r = graphsearch.sweep(
        SweepSpec(n=5, filters=["connected", dense], predicate=is_chordal),
        LIM, use_geng=False)
    assert r.meta["enumerated"] == 34            # before filtering
    assert r.meta["in_family"] < 34              # after


def test_a_programmable_filter_is_flagged_as_unverifiable():
    """It lives in the spec, not the catalogue: verify must not pretend."""
    r = graphsearch.sweep(
        SweepSpec(n=5, filters=[lambda g: g.m >= 8], predicate=is_chordal),
        LIM, use_geng=False)
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("cannot be re-checked" in c[2] for c in rep.checks)


# --- shrink: starting point and objective ----------------------------------


def _density_spec(n=6):
    def density(g):
        return Fraction(g.m, g.n * (g.n - 1) // 2) if g.n > 1 else Fraction(0)

    return SweepSpec(
        n=n, filters=["connected"],
        predicate=lambda g: Outcome(ok=is_chordal(g), value=density(g)),
        collect=density, worst="min")


def test_shrink_understands_an_outcome_returning_predicate():
    """An Outcome object is always truthy: it has to be unwrapped."""
    spec = _density_spec()
    c4 = Graph.from_edges(4, [(0, 1), (1, 2), (2, 3), (3, 0)])
    r = shrink.shrink_graph(spec, c4, LIM)
    assert r.verdict is Verdict.REFUTED       # not ERROR "satisfies predicate"


def test_objective_mode_keeps_the_worst_ratio_instead_of_the_fewest_edges():
    """C4 with a pendant vertex: density 1/2, and C4 alone is 2/3.

    Plain shrink drops the pendant because smaller wins. With --objective the
    reduction is refused, because 2/3 is a WORSE ratio than 1/2 and the point
    was the worst ratio, not the fewest edges.
    """
    spec = _density_spec()
    pendant = Graph.from_edges(5, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4)])

    plain = shrink.shrink_graph(spec, pendant, LIM)
    assert (plain.meta["n"], plain.meta["m"]) == (4, 4)      # fewest edges

    guided = shrink.shrink_graph(spec, pendant, LIM, use_objective=True)
    assert guided.meta["objective"] == "1/2"                 # worst ratio kept
    assert guided.meta["n"] == 5 and guided.meta["steps"] == 0


def test_worst_counterexample_is_picked_from_a_certificate():
    from certo.cli import _worst_from_cert
    from pathlib import Path
    import tempfile

    r = graphsearch.sweep(_density_spec(), LIM, use_geng=False)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "c.json"
        f.write_text(json.dumps(r.certificate.to_dict()), encoding="utf-8")
        pick = _worst_from_cert(f, "min")
    values = {v["id"]: Fraction(v["value"])
              for v in r.certificate.payload["values"]}
    failures = {e["id"] for e in r.certificate.payload["entries"]}
    assert pick in failures
    assert values[pick] == min(values[g] for g in failures)


# --- packings --------------------------------------------------------------


def _k(n):
    return Graph.from_edges(n, [(i, j) for i in range(n) for j in range(i + 1, n)])


def test_packing_builds_the_same_lp_and_certifies_exactly():
    pk = PackingSpec.cliques_in_graph(_k(6), gains={3: 2, 4: 5})
    r = lp.opt(pk.to_lp(), LIM)
    assert r.meta["exact"] and r.meta["objective"] == "25/2"   # 5n(n-1)/12
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_the_dual_reads_as_a_load_per_resource():
    pk = PackingSpec.cliques_in_graph(_k(6), gains={3: 2, 4: 5})
    r = lp.opt(pk.to_lp(), LIM)
    loads = loads_from_dual(r.certificate)
    assert set(loads) <= set(pk.resources)          # keys are edge names
    assert all(Fraction(v) == Fraction(5, 6) for v in loads.values())


def test_restricting_to_one_kind_gives_the_optimum_of_that_type_alone():
    pk = PackingSpec.cliques_in_graph(_k(6), gains={3: 2, 4: 5})
    assert pk.kinds == ["K3", "K4"]
    only3 = lp.opt(pk.restricted({"K3"}).to_lp(), LIM)
    only4 = lp.opt(pk.restricted({"K4"}).to_lp(), LIM)
    assert only3.meta["objective"] == "10"          # triangles alone
    assert only4.meta["objective"] == "25/2"        # mixing buys nothing here


def test_packing_rejects_duplicate_item_names():
    try:
        PackingSpec(items=[("a", ["r"], 1), ("a", ["s"], 1)])
        raise AssertionError("it accepted two items with the same name")
    except AssertionError:
        raise
    except ValueError as e:
        assert "duplicate" in str(e)


# --- Lean export -----------------------------------------------------------


def test_lean_export_carries_the_edges_and_admits_it_is_unchecked():
    from certo import lean

    c4 = Graph.from_edges(4, [(0, 1), (1, 2), (2, 3), (3, 0)])
    text = lean.graph_to_lean(c4, source="test")
    assert "Checked against Lean" in text          # states its provenance
    assert "(0, 1), (1, 2), (2, 3), (0, 3)" in text.replace("  ", " ") or \
           text.count("(") >= 4
    assert "SimpleGraph (Fin 4)" in text


def test_lean_export_reads_a_shrink_certificate():
    from certo import lean

    spec = _density_spec()
    pendant = Graph.from_edges(5, [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4)])
    cert = shrink.shrink_graph(spec, pendant, LIM).certificate
    graphs = lean.graphs_from_certificate(cert.to_dict())
    assert len(graphs) == 1 and graphs[0].n == 4        # reduced to C4




# --- core over several goals ------------------------------------------------


def _multi():
    import z3

    from certo import MultiSpec

    r, d = z3.Reals("r d")
    s = MultiSpec()
    s.assume("r_ge_3", r >= 3)
    s.assume("d_ge_1", d >= 1)
    s.assume("d_le_r", d <= r)
    s.claim("identity", (d - 1) * (d - 2) + r * (r + 1) - d * (d + 1)
            - 4 * (r - d) == (r - 1) * (r - 2))
    s.claim("positivity", (r - 1) * (r - 2) >= 0)
    s.claim("ordering", r - d >= 0)
    return s


def test_core_matrix_separates_what_each_goal_needs():
    from certo.engines import smt

    r = smt.core_matrix(_multi(), LIM)
    table = r.meta["table"]
    assert table["r_ge_3"] == {"identity": False, "positivity": True,
                               "ordering": False}
    assert table["d_le_r"]["ordering"] is True
    assert r.meta["never_used"] == ["d_ge_1"]       # no goal needs it
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_core_matrix_table_must_agree_with_its_cores():
    from certo.engines import smt

    cert = _roundtrip(smt.core_matrix(_multi(), LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["table"]["d_ge_1"]["identity"] = True      # tamper
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("agrees" in c[0] and not c[1] for c in rep.checks)


# --- shrink over an arbitrary domain ---------------------------------------


DOMAIN_SRC = '''
from fractions import Fraction
from certo import DomainSpec

def spec():
    return DomainSpec(
        items=[(s, r) for s in range(2, 7) for r in range(2, 7)],
        predicate=lambda p: p[0] * p[1] >= 12,
        collect=lambda p: Fraction(p[0], p[1]),
        reduce=lambda p: ([(p[0] - 1, p[1]), (p[0], p[1] - 1)]
                          if p[0] > 1 and p[1] > 1 else []),
        key=lambda p: "s={},r={}".format(*p),
    )
'''


def test_shrink_over_a_domain_replays_on_verification():
    import tempfile
    from pathlib import Path

    from certo.engines import shrink
    from certo.spec import load_spec

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "dom.py"
        f.write_text(DOMAIN_SRC, encoding="utf-8")
        spec = load_spec(f)
        start = next(i for i in spec.enumerate() if spec.id_of(i) == "s=2,r=2")
        r = shrink.shrink_domain(spec, start, LIM, spec_path=str(f))
        assert r.verdict is Verdict.REFUTED
        # the trace records the index taken, so the descent can be replayed
        assert all("index" in s for s in r.meta["trace"])
        rep = verify(_roundtrip(r.certificate), LIM)
        assert rep.ok and rep.solver_free
        assert any("replays" in c[0] for c in rep.checks)


def test_shrink_over_a_domain_needs_a_reduce():
    from certo import DomainSpec
    from certo.engines import shrink

    spec = DomainSpec(items=[(1, 1)], predicate=lambda p: False)
    try:
        shrink.shrink_domain(spec, (1, 1), LIM)
        raise AssertionError("it should have asked for `reduce`")
    except AssertionError:
        raise
    except ValueError as e:
        assert "reduce" in str(e)


# --- sweep over a range of sizes -------------------------------------------


def test_sweep_range_finds_the_first_failing_size():
    r = graphsearch.sweep_range(
        SweepSpec(n=3, filters=["connected"], predicate=is_chordal),
        3, 5, LIM, use_geng=False)
    assert r.meta["first_failure"] == 4          # C4
    assert r.meta["verdicts"][3] == "proved"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_sweep_range_records_that_it_stopped_early():
    r = graphsearch.sweep_range(
        SweepSpec(n=3, filters=["connected"], predicate=is_chordal),
        3, 6, LIM, stop_on_first=True, use_geng=False)
    assert r.meta["stopped_early"] and r.meta["sizes"] == [3, 4]
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and any("stopped" in w for w in rep.warnings)


def test_sweep_range_restores_the_spec_size():
    """The loop mutates spec.n; it must not leak out."""
    spec = SweepSpec(n=3, filters=["connected"], predicate=is_chordal)
    graphsearch.sweep_range(spec, 3, 5, LIM, use_geng=False)
    assert spec.n == 3


# --- ledger ----------------------------------------------------------------


def test_ledger_records_and_reverifies():
    import tempfile
    from pathlib import Path

    from certo import ledger
    from certo.engines import smt

    with tempfile.TemporaryDirectory() as d:
        log, cert_p = Path(d) / "l.jsonl", Path(d) / "c.json"
        import z3

        from certo import Spec

        a = z3.Real("a")
        s = Spec()
        s.assume("pos", a > 0)
        s.claim(a * a >= 0)
        res = smt.prove(s, LIM)
        cert_p.write_text(json.dumps(res.certificate.to_dict()), encoding="utf-8")

        ledger.append(log, res, cert_path=cert_p, note="baseline", tags=["t"])
        rows = ledger.read(log)
        assert len(rows) == 1 and rows[0]["note"] == "baseline"

        rep = ledger.verify_all(log, LIM)
        assert rep["counts"]["ok"] == 1 and rep["counts"]["failed"] == 0


def test_ledger_flags_a_certificate_that_changed_after_logging():
    import tempfile
    from pathlib import Path

    import z3

    from certo import Spec, ledger
    from certo.engines import smt

    with tempfile.TemporaryDirectory() as d:
        log, cert_p = Path(d) / "l.jsonl", Path(d) / "c.json"
        a = z3.Real("a")
        s = Spec()
        s.assume("pos", a > 0)
        s.claim(a * a >= 0)
        res = smt.prove(s, LIM)
        cert_p.write_text(json.dumps(res.certificate.to_dict()), encoding="utf-8")
        ledger.append(log, res, cert_path=cert_p)

        data = json.loads(cert_p.read_text(encoding="utf-8"))
        data["payload"]["names"] = ["invented"]
        cert_p.write_text(json.dumps(data), encoding="utf-8")

        rep = ledger.verify_all(log, LIM)
        assert rep["counts"]["tampered"] == 1        # digest no longer matches
        assert rep["rows"][0]["state"] == "changed"


def test_ledger_survives_a_corrupt_line():
    import tempfile
    from pathlib import Path

    from certo import ledger

    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "l.jsonl"
        log.write_text('{"ts":"x"}\nnot json at all\n', encoding="utf-8")
        rep = ledger.verify_all(log, LIM)
        assert rep["counts"]["corrupt"] == 1
        assert rep["total"] == 2



# --- farkas / linarith / nlinarith -----------------------------------------


def _lin_spec():
    import z3

    from certo import Spec

    x, y, z = z3.Reals("x y z")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise", z <= 100)
    s.claim(x + y >= 2)
    return s


def test_farkas_finds_the_linarith_certificate():
    from fractions import Fraction as F

    from certo.engines import farkas as fk

    r = fk.farkas(_lin_spec(), LIM)
    assert r.verdict is Verdict.PROVED
    mult = r.meta["multipliers"]
    assert F(mult["x_ge_1"]) > 0 and F(mult["y_ge_1"]) > 0
    assert "noise" not in mult                    # irrelevant: multiplier 0
    assert r.meta["hint"] == "linarith [x_ge_1, y_ge_1]"


def test_the_farkas_certificate_needs_no_solver():
    from certo.engines import farkas as fk

    rep = verify(_roundtrip(fk.farkas(_lin_spec(), LIM).certificate), LIM)
    assert rep.ok and rep.solver_free
    assert all(c[1] for c in rep.checks)


def test_a_tampered_multiplier_stops_cancelling():
    from certo.engines import farkas as fk

    cert = _roundtrip(fk.farkas(_lin_spec(), LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["multipliers"][0] = "7"          # breaks the cancellation
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("cancels" in c[0] and not c[1] for c in rep.checks)


def test_a_negative_multiplier_is_rejected():
    from certo.engines import farkas as fk

    cert = _roundtrip(fk.farkas(_lin_spec(), LIM).certificate)
    cert.payload["multipliers"][0] = "-1"
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("non-negative" in c[0] and not c[1] for c in rep.checks)


def test_nonlinear_mode_rediscovers_the_square():
    """a^2 + b^2 >= 2ab is (a - b)^2 >= 0, which is what nlinarith adds."""
    import z3

    from certo import Spec
    from certo.engines import farkas as fk

    a, b = z3.Reals("a b")
    s = Spec()
    s.claim(a * a + b * b >= 2 * a * b)

    assert fk.farkas(s, LIM).status is Status.OUT_OF_THEORY   # linear mode
    r = fk.farkas(s, LIM, nonlinear=True)
    assert r.verdict is Verdict.PROVED
    assert "sq_a_b" in r.meta["multipliers"]                  # the (a-b)^2 row
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_nonlinear_system_says_to_use_the_right_mode():
    import z3

    from certo import Spec
    from certo.engines import farkas as fk

    a = z3.Real("a")
    s = Spec()
    s.claim(a * a >= 0)
    r = fk.farkas(s, LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "--nonlinear" in r.detail and "prove" in r.detail


def test_non_polynomial_input_is_refused_with_the_offending_term():
    import z3

    from certo import Spec
    from certo.engines import farkas as fk

    x = z3.Real("x")
    s = Spec()
    s.claim(x / x >= 0)                     # division by a non-constant
    r = fk.farkas(s, LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "division" in r.detail


def test_a_false_statement_yields_no_certificate():
    import z3

    from certo import Spec
    from certo.engines import farkas as fk

    x = z3.Real("x")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.claim(x >= 2)                         # false at x = 1
    r = fk.farkas(s, LIM)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None


def test_equalities_are_split_so_multipliers_stay_non_negative():
    import z3

    from certo import Spec
    from certo.engines import farkas as fk

    x, y = z3.Reals("x y")
    s = Spec()
    s.assume("eq", x == y)
    s.assume("y_ge_3", y >= 3)
    s.claim(x >= 3)
    r = fk.farkas(s, LIM)
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok

# --- compose: lemmas, their certificates, and the join between them --------


def _x():
    import z3

    return z3.Real("x")


def _lemma_spec(hyp, goal):
    from certo import Spec

    s = Spec()
    s.assume("h", hyp)
    s.claim(goal)
    return s


def test_compose_assembles_a_proof_and_reports_what_it_needed():
    import z3

    from certo import ProofSpec
    from certo.engines import compose

    x = _x()
    p = ProofSpec(title="compose smoke")
    p.assume("x_ge_1", x >= 1)
    p.lemma("doubles", proves=_lemma_spec(x >= 1, 2 * x >= 2))
    p.lemma("spare", proves=_lemma_spec(x >= 1, x + 1 >= 2))
    p.conclude(2 * x >= 2)

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok
    # Both lemmas come back as NOT needed, and that is correct: over linear
    # real arithmetic z3 rederives them from `x_ge_1` in the final step. The
    # report comes from the step's MUS, not from a guess. A lemma is needed
    # only when it carries something the theory cannot reach on its own --
    # which is what a bridge does.
    assert set(r.meta["unused"]) == {"doubles", "spare"}
    assert r.meta["used"] == ["x_ge_1"]


def test_a_lemma_may_not_claim_more_than_its_certificate_closes():
    """The whole reason compose exists: proved for x>=1, used as x>=2."""
    import z3

    from certo import ProofSpec
    from certo.engines import compose

    x = _x()
    p = ProofSpec()
    p.lemma("overreach", proves=_lemma_spec(x >= 1, x >= 1),
            states=z3.Implies(x >= 1, x >= 2))
    p.conclude(z3.Implies(x >= 1, x >= 2))

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None                  # nothing unlinkable is emitted
    assert r.meta["failed_lemma"] == "overreach"


def test_lemmas_that_do_not_close_the_theorem_say_so():
    from certo import ProofSpec
    from certo.engines import compose

    x = _x()
    p = ProofSpec()
    p.lemma("weak", proves=_lemma_spec(x >= 1, x >= 1))
    p.conclude(x >= 2)

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None


def test_swapping_a_lemma_statement_breaks_the_link_on_verification():
    import z3

    from certo import ProofSpec, z3util
    from certo.engines import compose

    x = _x()
    p = ProofSpec()
    p.lemma("ok", proves=_lemma_spec(x >= 1, x >= 1))
    p.conclude(z3.Implies(x >= 1, x >= 1))

    cert = _roundtrip(compose.compose(p, LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["lemmas"][0]["statement_smt2"] = \
        z3util.smt2(z3.Implies(x >= 1, x >= 99))
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("entails" in c[0] and not c[1] for c in rep.checks)


def test_a_farkas_lemma_links_through_its_rows():
    """The link check is uniform: an exact certificate answers it too."""
    import z3

    from certo import ProofSpec, Spec
    from certo.engines import compose

    a, b = z3.Reals("a b")
    sq = Spec()
    sq.claim(a * a + b * b >= 2 * a * b)

    p = ProofSpec()
    p.lemma("square", proves=sq, via="nlinarith")
    p.conclude(a * a + b * b >= 2 * a * b)

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.PROVED
    assert r.certificate.payload["lemmas"][0]["engine"] == "nlinarith"
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("entails" in c[0] and c[1] for c in rep.checks)


def test_a_stored_certificate_is_a_bridge_and_is_reported_as_one(tmp=None):
    import json
    import tempfile
    from pathlib import Path

    import z3

    from certo import ProofSpec, Spec
    from certo.engines import compose, smt

    x = _x()
    # Any certificate will do; what matters is that it is not linkable to the
    # statement on its own.
    src = Spec()
    src.assume("h", x >= 1)
    src.claim(x >= 1)
    sub = smt.prove(src, LIM).certificate

    d = Path(tempfile.mkdtemp(prefix="certo_bridge_"))
    (d / "c.json").write_text(json.dumps(sub.to_dict()), encoding="utf-8")

    k = z3.Int("k")
    p = ProofSpec()
    p.assume("k_ge_6", k >= 6)
    p.lemma("finite", certificate=str(d / "c.json"), states=(k <= 10),
            bridge="checked by hand for every case")
    p.conclude(z3.And(k >= 6, k <= 10))

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.PROVED
    assert r.meta["bridges"] == ["finite"]
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any(w.startswith("BRIDGE") or "PUENTE" in w for w in rep.warnings)


def test_a_bridge_needs_a_statement_because_nothing_can_guess_it():
    from certo import ProofSpec

    p = ProofSpec()
    try:
        p.lemma("finite", certificate="somewhere.json")
    except ValueError as e:
        assert "states" in str(e)
    else:
        raise AssertionError("a bridge without states must be refused")


def test_a_missing_certificate_names_the_lemma_and_the_path():
    import z3

    from certo import ProofSpec
    from certo.engines import compose

    x = _x()
    p = ProofSpec()
    p.lemma("gone", certificate="no/such/file.json", states=(x >= 0))
    p.conclude(x >= 0)
    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert "gone" in r.detail and "file.json" in r.detail

# --- bounds: rigorous numerics ---------------------------------------------


def _bound(**kw):
    from certo import BoundSpec

    kw.setdefault("prec", 64)
    return BoundSpec(**kw)


def test_a_transcendental_bound_is_established_and_rechecked():
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.e / m.pi, claim=("<", "0.866")),
                      LIM)
    assert r.verdict is Verdict.PROVED
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free


def test_the_enclosure_travels_as_exact_rationals():
    from fractions import Fraction

    from certo.engines import bounds

    cert = bounds.bounds(_bound(value=lambda m: m.pi), LIM).certificate
    lo, hi = Fraction(cert.payload["lo"]), Fraction(cert.payload["hi"])
    assert lo < Fraction(355, 113) < hi or lo < hi   # an interval, exactly
    assert hi - lo > 0 and float(hi - lo) < 1e-15


def test_precision_is_a_budget_and_it_escalates():
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.e / m.pi, prec=32,
                             claim=("<", "0.8652559794322652")), LIM)
    assert r.verdict is Verdict.PROVED
    assert r.meta["ladder"][0] == 32


def test_running_out_of_precision_is_not_a_refutation():
    """exp(1) - e is zero, so no enclosure can ever separate it from zero."""
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.exp(1) - m.e, claim=("!=", "0"),
                             max_prec=512), LIM)
    assert r.status is Status.RESOURCE_EXHAUSTED
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None
    assert "not a refutation" in r.detail or "no es una refutaci" in r.detail


def test_a_false_bound_is_refuted_with_the_interval_that_shows_it():
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.pi, claim=("<", "3")), LIM)
    assert r.verdict is Verdict.REFUTED
    assert r.certificate is None
    assert float(r.meta["lo_float"]) > 3


def test_a_python_float_in_the_expression_is_refused():
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.pi * 0.5, claim=("<", "2")), LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "float" in r.detail


def test_a_string_is_read_as_an_exact_rational_not_as_a_float():
    from fractions import Fraction

    from certo.numerics import Rig

    lo, hi = Rig(256)("0.1").enclosure()
    assert lo <= Fraction(1, 10) <= hi          # one tenth, not the double


def test_measuring_without_a_claim_records_the_enclosure():
    from certo.engines import bounds

    r = bounds.bounds(_bound(value=lambda m: m.zeta(3)), LIM)
    assert r.verdict is Verdict.PROVED
    assert r.certificate.payload["claim"][0] == "in"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_widened_interval_no_longer_settles_the_claim():
    from certo.engines import bounds

    cert = _roundtrip(bounds.bounds(
        _bound(value=lambda m: m.e / m.pi, claim=("<", "0.866")), LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["hi"] = "1"                    # still contains the value
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("settles" in c[0] and not c[1] for c in rep.checks)


def test_a_shifted_interval_fails_the_re_evaluation(tmp_path=None):
    """The rational half can pass while the interval is the wrong interval."""
    import tempfile
    from pathlib import Path

    from certo.engines import bounds

    src = Path(tempfile.mkdtemp(prefix="certo_ball_")) / "s.py"
    src.write_text(
        "from certo import BoundSpec\n"
        "def spec():\n"
        "    return BoundSpec(value=lambda m: m.e / m.pi,\n"
        "                     claim=('<', '0.866'), prec=64)\n",
        encoding="utf-8")

    from certo import load_spec

    cert = _roundtrip(bounds.bounds(load_spec(src), LIM, spec_path=str(src))
                      .certificate)
    assert verify(cert, LIM).ok
    cert.payload["lo"] = "1/100"                # settles "< 0.866" just fine
    cert.payload["hi"] = "2/100"
    rep = verify(cert, LIM)
    assert not rep.ok
    failed = [c for c, ok, _ in rep.checks if not ok]
    assert failed and all("re-evaluating" in c or "reevaluar" in c
                          for c in failed)


def test_both_backends_agree_on_an_elementary_quantity():
    from certo.numerics import Rig

    a = Rig(160, "python-flint (Arb)")
    b = Rig(160, "mpmath.iv")
    alo, ahi = (a.exp(1) / a.pi).enclosure()
    blo, bhi = (b.exp(1) / b.pi).enclosure()
    assert alo <= bhi and blo <= ahi            # the enclosures overlap
    assert max(alo, blo) <= min(ahi, bhi)


def test_a_function_the_backend_lacks_says_which_backend():
    from certo.numerics import NotRigorous, Rig

    try:
        Rig(64, "mpmath.iv").zeta(3)
    except NotRigorous as e:
        assert "mpmath" in str(e)
    else:
        raise AssertionError("mpmath.iv has no rigorous zeta; it must say so")

# --- vacuity: a proof from contradictory hypotheses is not a proof ---------


def _contradictory(goal):
    import z3

    from certo import Spec

    x = z3.Real("x")
    s = Spec()
    s.assume("big", x > 1)
    s.assume("small", x < 0)
    s.claim(goal(x))
    return s


def test_prove_says_when_the_hypotheses_contradict_each_other():
    from certo.engines import smt

    r = smt.prove(_contradictory(lambda x: x == 42), LIM)
    assert r.verdict is Verdict.PROVED        # it IS a proof; ex falso
    assert r.meta["vacuous"] is True
    assert "VACUOUS" in r.detail or "VACUA" in r.detail


def test_the_vacuity_survives_in_the_certificate():
    from certo.engines import smt

    cert = _roundtrip(smt.prove(_contradictory(lambda x: x == 42), LIM).certificate)
    rep = verify(cert, LIM)
    assert rep.ok                              # still a valid certificate
    assert any("VACUOUS" in w or "VACUA" in w for w in rep.warnings)


def test_an_honest_proof_is_not_flagged():
    import z3

    from certo import Spec
    from certo.engines import smt

    x = z3.Real("x")
    s = Spec()
    s.assume("pos", x > 1)
    s.claim(x > 0)
    r = smt.prove(s, LIM)
    assert r.meta["vacuous"] is False
    assert not verify(_roundtrip(r.certificate), LIM).warnings


def test_farkas_detects_vacuity_by_dropping_the_goal():
    """Reading it off the multipliers does not work; this asks directly."""
    import z3

    from certo import Spec
    from certo.engines import farkas

    x = z3.Real("x")
    s = Spec()
    s.assume("a", x >= 1)
    s.assume("b", x <= 0)
    s.claim(x >= 5)
    r = farkas.farkas(s, LIM)
    assert r.verdict is Verdict.PROVED
    assert r.meta["vacuous"] is True
    assert any("VACUOUS" in w or "VACUA" in w
               for w in verify(_roundtrip(r.certificate), LIM).warnings)


def test_nonlinear_vacuity_does_not_count_the_goal_products():
    """The products are named h*__goal__; keeping one would smuggle it back."""
    import z3

    from certo import Spec
    from certo.engines import farkas

    a, b = z3.Reals("a b")
    s = Spec()
    s.assume("h", a >= 0)
    s.claim(a * a + b * b >= 2 * a * b)
    assert farkas.farkas(s, LIM, nonlinear=True).meta["vacuous"] is False


def test_compose_reports_bridges_that_contradict_each_other():
    """Only bridges can contradict: two DERIVED lemmas are both true, so they
    cannot. Which is precisely why the check belongs where bridges enter."""
    import json
    import tempfile
    from pathlib import Path

    import z3

    from certo import ProofSpec, Spec
    from certo.engines import compose, smt

    x = z3.Real("x")
    src = Spec()
    src.assume("h", x >= 1)
    src.claim(x >= 1)
    sub = smt.prove(src, LIM).certificate
    d = Path(tempfile.mkdtemp(prefix="certo_vac_"))
    (d / "c.json").write_text(json.dumps(sub.to_dict()), encoding="utf-8")

    k = z3.Int("k")
    p = ProofSpec(title="contradictory bridges")
    p.lemma("small", certificate=str(d / "c.json"), states=(k <= 3),
            bridge="asserted")
    p.lemma("large", certificate=str(d / "c.json"), states=(k >= 9),
            bridge="also asserted, and incompatible with the first")
    p.conclude(k == 99)                       # follows from anything

    r = compose.compose(p, LIM)
    assert r.verdict is Verdict.PROVED        # ex falso: it really does follow
    assert r.meta["vacuous"] is True
    rep = verify(_roundtrip(r.certificate), LIM)
    assert any("VACUOUS" in w or "VACUA" in w for w in rep.warnings)



# --- P0: what a sweep establishes about the predicate ----------------------


def _bool_domain(pred, n=12):
    from certo import DomainSpec

    return DomainSpec(items=list(range(n)), predicate=pred,
                      key=lambda i: "i={}".format(i))


def _spec_file(dirname, threshold):
    """A DomainSpec on disk whose predicate depends on `threshold`."""
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp(prefix=dirname))
    src = d / "s.py"
    src.write_text(SPEC_TEMPLATE.format(t=threshold), encoding="utf-8")
    return src


SPEC_TEMPLATE = """
from certo import DomainSpec

def spec():
    return DomainSpec(items=list(range(12)),
                      predicate=lambda i: i >= {t},
                      key=lambda i: "i=" + str(i))
"""


def _pretend_unchanged(cert, src):
    """Make the provenance hash match the EDITED spec.

    Without this the provenance warning would fire and the replay would be
    skipped; the point of the test is that the replay is what catches an edit
    nothing else can see.
    """
    import hashlib

    cert.provenance["spec_sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
    return cert


def test_replay_catches_a_predicate_that_changed_under_a_stable_name():
    """The only check that can catch this. The domain hash cannot -- the
    domain did not move. The stored certificates cannot -- there are none."""
    from certo import load_spec
    from certo.engines import domain

    src = _spec_file("certo_replay_", 0)
    cert = _roundtrip(domain.sweep_domain(load_spec(src), LIM)
                      .certificate.stamp(src))
    assert verify(cert, LIM).ok

    src.write_text(SPEC_TEMPLATE.format(t=3), encoding="utf-8")   # three flip
    rep = verify(_pretend_unchanged(cert, src), LIM)
    assert not rep.ok
    failed = [(c, d) for c, ok, d in rep.checks if not ok]
    assert failed and "re-running" in failed[0][0]
    assert "i=0" in failed[0][1]


def test_a_sweep_with_no_spec_path_drops_to_recorded():
    from certo.engines import domain

    cert = _roundtrip(domain.sweep_domain(_bool_domain(lambda i: True),
                                          LIM).certificate)
    rep = verify(cert, LIM)                     # never stamped: nothing to replay
    assert rep.ok
    assert "recorded only" in rep.detail
    assert any("NOT re-run" in w for w in rep.warnings)
    assert any("could not be replayed" in w for w in rep.warnings)


def test_the_verdict_vector_is_what_makes_replay_possible():
    from certo.certificate import outcomes_digest
    from certo.engines import domain

    r = domain.sweep_domain(_bool_domain(lambda i: i % 2 == 0), LIM)
    p = r.certificate.payload
    assert p["outcomes"] == "TFTFTFTFTFTF"
    assert p["outcomes_sha256"] == outcomes_digest(p["outcomes"])
    assert p["evaluations"] == 12 and p["certified"] == 0


def test_an_inconclusive_evaluation_is_its_own_code():
    from certo import Outcome
    from certo.engines import domain

    def pred(i):
        if i == 5:
            return Outcome(ok=None, detail="gave up")
        if i == 7:
            raise RuntimeError("boom")
        return True

    p = domain.sweep_domain(_bool_domain(pred), LIM).certificate.payload
    assert p["outcomes"] == "TTTTT?TETTTT"


def test_calibration_has_no_predicate_to_certify_and_says_nothing_about_one():
    from fractions import Fraction

    from certo import DomainSpec
    from certo.engines import domain

    spec = DomainSpec(items=list(range(6)), collect=lambda i: Fraction(i, 7),
                      key=lambda i: "i={}".format(i))
    r = domain.sweep_domain(spec, LIM)
    assert "level" not in r.meta                # there is no predicate to rate
    assert "banner_key" not in r.meta           # the banner stays CALIBRATION
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert "no predicate" in rep.detail
    assert not any("carry no certificate" in w for w in rep.warnings)


def test_a_disagreeing_replay_does_not_also_claim_only_the_domain_was_checked():
    """Two messages for one problem make readers skim both."""
    from certo import load_spec
    from certo.engines import domain

    src = _spec_file("certo_one_msg_", 0)
    cert = _roundtrip(domain.sweep_domain(load_spec(src), LIM)
                      .certificate.stamp(src))
    src.write_text(SPEC_TEMPLATE.format(t=2), encoding="utf-8")

    rep = verify(_pretend_unchanged(cert, src), LIM)
    assert not rep.ok
    assert not any("could not be replayed" in w for w in rep.warnings)


def test_certificates_issued_before_the_rename_still_read():
    """`g6` was the field name when the only domain was graphs."""
    from certo.certificate import _entry_id

    assert _entry_id({"id": "a=1"}) == "a=1"
    assert _entry_id({"g6": "E??w"}) == "E??w"      # pre-rename certificate
    assert _entry_id({}) == "?"


def test_a_domain_sweep_no_longer_calls_its_items_graph6():
    from certo.engines import domain

    r = domain.sweep_domain(_bool_domain(lambda i: i < 8), LIM)
    p = r.certificate.payload
    assert p["entries"] and all("id" in e and "g6" not in e for e in p["entries"])

# --- P1: standard reducers -------------------------------------------------


def test_the_catalogue_reducers_are_deterministic_and_shrinking():
    from certo import reducers

    assert reducers.sets({3, 1, 2}) == [{2, 3}, {1, 3}, {1, 2}]
    assert reducers.sequences((1, 2, 3)) == [(2, 3), (1, 3), (1, 2)]
    assert reducers.decrement((4, 2)) == [(3, 2), (4, 1)]
    assert reducers.masks(0b1011) == [0b1010, 0b1001, 0b0011]
    assert reducers.decrement((0, 0)) == []          # already at the floor


def test_auto_treats_a_tuple_of_ints_as_a_point_not_a_collection():
    """Dropping a coordinate from a parameter point changes its arity."""
    from certo import reducers

    assert reducers.auto((3, 1)) == [(2, 1), (3, 0)]
    assert reducers.auto(("a", "b")) == [("b",), ("a",)]


def test_auto_refuses_rather_than_inventing_a_reduction():
    from certo import reducers

    try:
        reducers.auto(3.5)
    except TypeError as e:
        assert "float" in str(e)
    else:
        raise AssertionError("it made up a reduction for a float")


def test_a_named_reducer_replays_exactly_like_a_hand_written_one():
    from certo import load_spec
    from certo.engines import shrink

    src = _spec_file("certo_reducer_", 0)            # reduce="auto" inside
    src.write_text(
        SPEC_TEMPLATE.replace("predicate=lambda i: i >= {t},",
                              "predicate=lambda i: i < 4,")
        .replace("key=", "reduce='auto', key=").format(t=0),
        encoding="utf-8")
    spec = load_spec(src)
    r = shrink.shrink_domain(spec, 11, LIM, spec_path=src)
    assert r.verdict is Verdict.REFUTED
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_an_unknown_reducer_name_lists_the_known_ones():
    from certo import DomainSpec

    try:
        DomainSpec(items=[], reduce="nope").reducer()
    except ValueError as e:
        assert "auto" in str(e) and "graphs" in str(e)
    else:
        raise AssertionError("it accepted a name that does not exist")


def test_a_shrink_certificate_with_no_spec_path_says_so_instead_of_crashing():
    """Path("") is ".", which exists and is a directory."""
    from certo.certificate import shrink_domain_certificate

    rep = verify(shrink_domain_certificate("", "", "x", "x", [], [], 0), LIM)
    assert not rep.ok
    assert "spec" in rep.detail


# --- P1: orbits ------------------------------------------------------------


def _mirror_spec(n=7):
    from certo import DomainSpec

    return DomainSpec(
        items=[(a, b) for a in range(1, n) for b in range(1, n)],
        predicate=lambda p: p[0] + p[1] != n,
        key=lambda p: "({},{})".format(*p),
        canonicalize=lambda p: tuple(sorted(p)),
    )


def test_orbits_collapse_relabelled_counterexamples():
    from certo.engines import domain

    r = domain.sweep_domain(_mirror_spec(), LIM)
    assert r.verdict is Verdict.REFUTED
    assert r.meta["labelled"] == 6 and r.meta["orbit_count"] == 3
    reps = [row["representative"] for row in r.meta["orbits"]]
    assert reps == ["(1,6)", "(2,5)", "(3,4)"]       # smallest id, deterministic
    assert all(row["size"] == 2 for row in r.meta["orbits"])


def test_the_orbit_decomposition_is_checked_for_consistency():
    from certo.engines import domain

    cert = _roundtrip(domain.sweep_domain(_mirror_spec(), LIM).certificate)
    rep = verify(cert, LIM)
    assert rep.ok
    assert sum(1 for c, _, _ in rep.checks if "orbit" in c) == 3


def test_a_decomposition_that_does_not_add_up_is_caught():
    from certo.engines import domain

    cert = _roundtrip(domain.sweep_domain(_mirror_spec(), LIM).certificate)
    cert.payload["orbits"][0]["size"] = 99          # more members than items
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("partition" in c and not ok for c, ok, _ in rep.checks)


def test_two_orbits_may_not_share_a_representative():
    from certo.engines import domain

    cert = _roundtrip(domain.sweep_domain(_mirror_spec(), LIM).certificate)
    cert.payload["orbits"][1]["representative"] = \
        cert.payload["orbits"][0]["representative"]
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("representative" in c and not ok for c, ok, _ in rep.checks)


def test_only_the_counterexamples_are_decomposed():
    """The orbit structure of everything that passed is rarely the question."""
    from certo.engines import domain

    r = domain.sweep_domain(_mirror_spec(), LIM)
    assert r.meta["domain_orbits"] == 21            # the whole 6x6 domain
    assert r.meta["orbit_count"] == 3               # only the failures


def test_a_sweep_with_no_symmetry_declared_reports_no_orbits():
    from certo.engines import domain

    r = domain.sweep_domain(_bool_domain(lambda i: i < 5), LIM)
    assert "orbits" not in r.meta and "domain_orbits" not in r.meta
    assert r.certificate.payload["orbits"] is None


def test_canonicalize_must_return_something_hashable():
    from certo import DomainSpec
    from certo.engines import domain

    spec = DomainSpec(items=[(1, 2)], predicate=lambda p: False,
                      key=str, canonicalize=lambda p: list(p))
    try:
        domain.sweep_domain(spec, LIM)
    except TypeError as e:
        assert "hashable" in str(e)
    else:
        raise AssertionError("an unhashable canonical form was accepted")


# --- P1: doctor ------------------------------------------------------------


def test_doctor_reports_every_capability_with_its_fallback():
    from certo import doctor

    rep = doctor.report()
    assert rep["ok"]                                 # z3 and pulp are required
    keys = {r["key"] for r in rep["rows"]}
    assert {"python", "z3", "pulp", "flint", "nauty", "lean"} <= keys
    for r in rep["rows"]:
        assert r["what"] and not r["what"].startswith("doctor.")
        if not r["ok"]:
            assert r["without"], r["key"] + " has no stated fallback"


def test_registering_mcp_merges_instead_of_replacing():
    import json
    import tempfile
    from pathlib import Path

    from certo import doctor

    p = Path(tempfile.mkdtemp(prefix="certo_mcpreg_")) / ".mcp.json"
    p.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}),
                 encoding="utf-8")

    out = doctor.register_mcp(p)
    assert out["written"] and out["servers"] == ["certo", "other"]
    assert json.loads(p.read_text(encoding="utf-8"))["mcpServers"]["other"]

    again = doctor.register_mcp(p)
    assert again["already"]                          # idempotent


def test_a_broken_mcp_config_is_not_overwritten():
    import tempfile
    from pathlib import Path

    from certo import doctor

    p = Path(tempfile.mkdtemp(prefix="certo_mcpbad_")) / ".mcp.json"
    p.write_text("not json at all", encoding="utf-8")
    out = doctor.register_mcp(p)
    assert not out["written"]
    assert p.read_text(encoding="utf-8") == "not json at all"

# --- P2: native combinatorial types ----------------------------------------


def _fam(n, blocks):
    from certo import SetFamily

    return SetFamily(n, blocks)


def test_a_family_normalises_so_two_spellings_are_one_object():
    a = _fam(4, [(1, 0), (2, 1), (2, 1)])
    b = _fam(4, [(0, 1), (1, 2)])
    assert a == b and hash(a) == hash(b) and a.key() == b.key()


def test_the_key_round_trips():
    from certo import SetFamily

    f = _fam(5, [(0, 1, 2), (2, 3), (4,)])
    assert SetFamily.from_key(f.key()) == f


def test_the_canonical_form_is_invariant_under_relabelling():
    """Two paths on four points are the same object written differently."""
    path = _fam(4, [(0, 1), (1, 2), (2, 3)])
    same = _fam(4, [(1, 2), (2, 3), (3, 0)])
    star = _fam(4, [(0, 1), (0, 2), (0, 3)])
    assert path.canonical() == same.canonical()
    assert path.canonical() != star.canonical()


def test_the_canonical_form_survives_every_relabelling():
    from itertools import permutations

    f = _fam(5, [(0, 1), (1, 2), (2, 3), (3, 4)])
    forms = {f.relabelled({i: p[i] for i in range(5)}).canonical()
             for p in permutations(range(5))}
    assert len(forms) == 1


def test_a_family_too_symmetric_to_canonicalise_refuses():
    """A cheaper invariant could merge two orbits and nobody would notice."""
    from certo import SetFamily
    from certo import structures

    big = SetFamily.complete(14, 1)          # 14! candidate relabellings
    try:
        big.canonical()
    except ValueError as e:
        assert str(structures.PERM_CAP) in str(e) or "symmetric" in str(e)
    else:
        raise AssertionError("it canonicalised something it cannot")


def test_design_and_regularity_predicates():
    fano = _fam(7, [(0, 1, 2), (0, 3, 4), (0, 5, 6),
                    (1, 3, 5), (1, 4, 6), (2, 3, 6), (2, 4, 5)])
    assert fano.is_design(2, 1) and fano.is_regular(3) and fano.is_uniform(3)
    assert not fano.is_design(2, 2)


def test_masks_become_a_family_with_an_id():
    from certo import family_from_masks, mask_to_set, set_to_mask

    assert mask_to_set(0b1011, 4) == (0, 1, 3)
    assert set_to_mask((0, 1, 3)) == 0b1011
    assert family_from_masks(4, [0b0011, 0b1100]).key() == "4:01|23"


def test_reductions_drop_a_block_before_a_point():
    f = _fam(4, [(0, 1), (1, 2)])
    red = f.reductions()
    assert red[0] == _fam(4, [(1, 2)])        # blocks first
    assert red[f.size].n == 3                 # then points, ground set shrinks


def test_a_native_type_supplies_key_canonicalize_and_reduce_itself():
    from certo import DomainSpec, SetFamily
    from certo.engines import domain

    spec = DomainSpec(
        items=lambda: list(SetFamily.all_families(5, 2, 3)),
        predicate=lambda f: f.intersecting(),
        canonicalize="auto", reduce="auto",   # and no key= at all
    )
    r = domain.sweep_domain(spec, LIM)
    assert r.verdict is Verdict.REFUTED
    assert r.meta["labelled"] == 90 and r.meta["orbit_count"] == 2
    assert r.meta["counterexamples"][0].startswith("5:")   # the family's own id
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_auto_reduce_asks_the_item_before_guessing_from_its_type():
    from certo import reducers

    f = _fam(4, [(0, 1), (1, 2)])
    assert reducers.auto(f) == f.reductions()


# --- P2: symmetries on graph sweeps ----------------------------------------


def test_a_graph_sweep_can_declare_a_finer_symmetry_than_isomorphism():
    """The enumerator already quotients by isomorphism; this is finer."""
    r = graphsearch.sweep(
        SweepSpec(n=6, filters=["connected"], predicate=is_chordal,
                  canonicalize=lambda g: tuple(sorted(g.degree(v)
                                                      for v in range(g.n)))),
        LIM, use_geng=False)
    assert r.verdict is Verdict.REFUTED
    assert r.meta["orbit_count"] < r.meta["labelled"]
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_auto_on_a_graph_sweep_means_isomorphism():
    r = graphsearch.sweep(
        SweepSpec(n=5, filters=["connected"], predicate=is_chordal,
                  canonicalize="auto"),
        LIM, use_geng=False)
    # The family is already one graph per isomorphism class, so every orbit
    # is a singleton -- which is the right answer, and worth being able to see.
    assert all(row["size"] == 1 for row in r.meta["orbits"])


def test_a_graph_sweep_without_a_symmetry_reports_none():
    r = graphsearch.sweep(SweepSpec(n=5, filters=["connected"],
                                    predicate=is_chordal),
                          LIM, use_geng=False)
    assert "orbits" not in r.meta
    assert r.certificate.payload["orbits"] is None


# --- P2: induct ------------------------------------------------------------


def _induct_spec(step_from=3, base_upto=8):
    import z3

    from certo import InductSpec, Spec

    k = z3.Int("k")

    def edges(n):
        return n * (n - 1) / 2

    def base(j):
        s = Spec()
        s.claim(edges(z3.IntVal(j)) >= 3 * j - 6)
        return s

    step = Spec()
    step.assume("k_ge_3", k >= 3)
    step.assume("P_k", edges(k) >= 3 * k - 6)
    step.claim(edges(k + 1) >= 3 * (k + 1) - 6)

    return InductSpec(k0=3, base_upto=base_upto, base=base, step=step,
                      step_from=step_from)


def test_induct_chains_base_cases_to_a_step():
    from certo.engines import induct

    r = induct.induct(_induct_spec(), LIM)
    assert r.verdict is Verdict.PROVED
    assert r.meta["base_cases"] == [3, 4, 5, 6, 7, 8]
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_step_that_starts_after_the_base_ends_is_refused_up_front():
    """Base 3..8, step from 10: nothing proves n = 9."""
    from certo.engines import induct

    r = induct.induct(_induct_spec(step_from=10), LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert r.certificate is None
    assert "does not join" in r.detail


def test_the_gap_is_caught_again_at_verification():
    from certo.engines import induct

    cert = _roundtrip(induct.induct(_induct_spec(), LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["step_from"] = 10
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("no later" in c and not ok for c, ok, _ in rep.checks)


def test_a_missing_base_case_is_caught():
    from certo.engines import induct

    cert = _roundtrip(induct.induct(_induct_spec(), LIM).certificate)
    del cert.payload["base"][3]                   # k=6 quietly removed
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("exactly" in c and not ok for c, ok, _ in rep.checks)


def test_the_induction_schema_is_declared_every_time():
    """It is applied here, not verified by a solver, and that is said."""
    from certo.engines import induct

    rep = verify(_roundtrip(induct.induct(_induct_spec(), LIM).certificate), LIM)
    assert rep.ok
    assert any("APPLIED" in w or "APLICA" in w for w in rep.warnings)


def test_a_false_step_stops_the_whole_thing():
    import z3

    from certo import InductSpec, Spec
    from certo.engines import induct

    k = z3.Int("k")
    step = Spec()
    step.assume("k_ge_3", k >= 3)
    step.claim(k > k + 1)                          # plainly false

    spec = InductSpec(k0=3, base_upto=4, base=lambda j: Spec().claim(z3.BoolVal(True)),
                      step=step)
    r = induct.induct(spec, LIM)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None

# --- P1: --by-orbit --------------------------------------------------------


def _mirror(n=7, pred=None):
    from certo import DomainSpec

    return DomainSpec(
        items=[(a, b) for a in range(1, n) for b in range(1, n)],
        predicate=pred or (lambda p: p[0] + p[1] != n),
        key=lambda p: "({},{})".format(*p),
        canonicalize=lambda p: tuple(sorted(p)),
    )


def test_by_orbit_evaluates_one_item_per_orbit():
    from certo.engines import domain

    full = domain.sweep_domain(_mirror(), LIM)
    quick = domain.sweep_domain(_mirror(), LIM, by_orbit=True)
    assert quick.verdict is full.verdict
    assert quick.meta["counterexamples"] == full.meta["counterexamples"]
    # 36 ordered pairs quotiented by sorting is 21 orbits, so most of the
    # saving here is modest -- what matters is that fewer than 36 were run.
    assert quick.meta["evaluated"] == quick.meta["domain_orbits"]
    assert quick.meta["evaluated"] + quick.meta["inferred"] == 36
    assert quick.meta["evaluated"] < 36


def test_an_inferred_verdict_is_marked_in_the_vector():
    """Lower case says "not computed", so a reader can see how much was run."""
    from certo.engines import domain

    p = domain.sweep_domain(_mirror(), LIM, by_orbit=True).certificate.payload
    codes = p["outcomes"]
    assert set(codes) <= set("TFtf")
    assert sum(1 for c in codes if c.isupper()) == p["evaluated"]


def test_by_orbit_replays_the_inference_not_a_full_evaluation():
    from certo import load_spec
    from certo.engines import domain

    src = _spec_file("certo_byorbit_", 0)
    src.write_text(ORBIT_SPEC, encoding="utf-8")
    cert = _roundtrip(domain.sweep_domain(load_spec(src), LIM, by_orbit=True)
                      .certificate.stamp(src))
    rep = verify(cert, LIM)
    assert rep.ok
    assert any("re-running" in c and ok for c, ok, _ in rep.checks)


ORBIT_SPEC = """
from certo import DomainSpec

def spec():
    return DomainSpec(
        items=[(a, b) for a in range(1, 7) for b in range(1, 7)],
        predicate=lambda p: p[0] + p[1] != 7,
        key=lambda p: "(%d,%d)" % p,
        canonicalize=lambda p: tuple(sorted(p)),
    )
"""


def test_a_predicate_that_is_not_invariant_stops_the_run():
    """The spot checks exist for exactly this, and it is not a warning."""
    from certo.engines import domain

    r = domain.sweep_domain(_mirror(pred=lambda p: p[0] <= p[1]), LIM,
                            by_orbit=True)
    assert r.status is Status.OUT_OF_THEORY
    assert r.certificate is None
    assert "NOT invariant" in r.detail


def test_by_orbit_needs_a_symmetry_to_sweep_by():
    from certo.engines import domain

    r = domain.sweep_domain(_bool_domain(lambda i: i < 5), LIM, by_orbit=True)
    assert r.status is Status.OUT_OF_THEORY
    assert "canonicalize" in r.detail


def test_the_invariance_assumption_is_reported_on_every_verification():
    from certo.engines import domain

    rep = verify(_roundtrip(domain.sweep_domain(_mirror(), LIM, by_orbit=True)
                            .certificate), LIM)
    assert any("ASSUMED" in w or "SUPUESTO" in w for w in rep.warnings)
    assert any("spot checks" in c or "puntuales" in c for c, _, _ in rep.checks)


# --- P1: orbit witnesses ---------------------------------------------------


def test_witnesses_must_come_from_the_sweep_they_claim_to():
    from certo.certificate import orbit_witnesses_certificate
    from certo.engines import domain

    sweep = domain.sweep_domain(_mirror(), LIM)
    cert = _roundtrip(orbit_witnesses_certificate(
        sweep_cert=sweep.certificate.to_dict(),
        witnesses=[{"representative": "(9,9)", "size": 1, "minimal": "(9,9)",
                    "steps": 0, "cert": None}],
        labelled=6))
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("own representatives" in c and not ok
               for c, ok, _ in rep.checks)


# --- P1: the deep Lean export ----------------------------------------------


def _farkas_cert(nonlinear=False):
    import z3

    from certo import Spec
    from certo.engines import farkas

    if nonlinear:
        a, b = z3.Reals("a b")
        s = Spec()
        s.claim(a * a + b * b >= 2 * a * b)
    else:
        x, y = z3.Reals("x y")
        s = Spec()
        s.assume("x_ge_1", x >= 1)
        s.assume("y_ge_1", y >= 1)
        s.claim(x + y >= 2)
    r = farkas.farkas(s, LIM, nonlinear=nonlinear)
    d = r.certificate.to_dict()
    d["digest"] = r.certificate.digest()
    return d


def test_a_farkas_certificate_becomes_a_runnable_linarith_example():
    from certo import leanexport

    text = leanexport.farkas_to_lean(_farkas_cert())
    assert "example (x y : \u211d)" in text
    assert "linarith [x_ge_1, y_ge_1]" in text
    assert "import Mathlib.Data.Real.Basic" in text   # linarith alone is not enough
    assert "\u00ac" not in text                      # the goal is positive, not a negation


def test_the_nonlinear_export_hands_nlinarith_the_square_it_used():
    """Without the hint nlinarith fails; the certificate knows which square."""
    from certo import leanexport

    text = leanexport.farkas_to_lean(_farkas_cert(nonlinear=True))
    assert "nlinarith [sq_nonneg (a - b)]" in text


def test_the_square_hint_comes_from_the_polynomial_not_the_name():
    """`sq_a_b` is ambiguous when a variable contains an underscore."""
    import z3

    from certo import Spec, leanexport
    from certo.engines import farkas

    a_b, c = z3.Reals("a_b c")
    s = Spec()
    s.claim(a_b * a_b + c * c >= 2 * a_b * c)
    r = farkas.farkas(s, LIM, nonlinear=True)
    d = r.certificate.to_dict()
    d["digest"] = r.certificate.digest()
    text = leanexport.farkas_to_lean(d)
    assert "sq_nonneg (a_b - c)" in text


def test_a_proof_export_puts_sorry_on_the_bridges_and_nowhere_else():
    import json
    import tempfile
    from pathlib import Path

    import z3

    from certo import ProofSpec, Spec, leanexport
    from certo.engines import compose, smt

    x = z3.Real("x")
    src = Spec()
    src.assume("h", x >= 1)
    src.claim(x >= 1)
    sub = smt.prove(src, LIM).certificate
    d = Path(tempfile.mkdtemp(prefix="certo_leanproof_"))
    (d / "c.json").write_text(json.dumps(sub.to_dict()), encoding="utf-8")

    k = z3.Int("k")
    p = ProofSpec(title="two kinds of lemma")
    p.assume("k_ge_6", k >= 6)
    p.lemma("finite", certificate=str(d / "c.json"), states=(k <= 10),
            bridge="checked exhaustively")
    lem = Spec()
    lem.assume("h", k >= 6)
    lem.claim(k >= 0)
    p.lemma("derived", proves=lem)
    p.conclude(z3.And(k >= 6, k <= 10))

    cert = compose.compose(p, LIM).certificate
    data = cert.to_dict()
    data["digest"] = cert.digest()
    text = leanexport.proof_to_lean(data)

    assert text.count("sorry") == 2          # the bridge, and its listing
    assert "theorem finite" in text and "theorem derived" in text
    # The sorry belongs to the bridge, not to the derived lemma.
    bridge_block = text.split("theorem finite")[1].split("theorem")[0]
    derived_block = text.split("theorem derived")[1].split("/--")[0]
    assert "sorry" in bridge_block and "sorry" not in derived_block


def test_the_classification_export_states_what_lean_cannot_check():
    from certo import leanexport
    from certo.engines import domain

    cert = domain.sweep_domain(_bool_domain(lambda i: i < 20), LIM).certificate
    data = cert.to_dict()
    data["digest"] = cert.digest()
    text = leanexport.classification_to_lean(data)
    assert "COMPLETENESS IS NOT PROVED HERE" in text
    assert "family.length = 12" in text


def test_the_manifest_ties_the_lean_file_to_the_certificate():
    import json
    import tempfile
    from pathlib import Path

    from certo import leanexport

    d = Path(tempfile.mkdtemp(prefix="certo_manifest_"))
    cert = d / "c.json"
    cert.write_text(json.dumps(_farkas_cert()), encoding="utf-8")
    man = leanexport.manifest([cert])
    assert man["files"][0]["kind"] == "farkas"
    assert len(man["files"][0]["sha256"]) == 64


def test_check_says_it_did_not_run_rather_than_staying_quiet():
    import tempfile
    from pathlib import Path

    from certo import leanexport

    d = Path(tempfile.mkdtemp(prefix="certo_nocheck_"))
    f = d / "X.lean"
    f.write_text("example : True := trivial\n", encoding="utf-8")
    rep = leanexport.check(f)
    assert rep["ran"] is False
    assert rep["reason"]

# --- v0.3: exact multivariate polynomials ----------------------------------


def _ring(*names):
    from certo import Poly

    return tuple(names), [Poly.var(names, n) for n in names]


def test_polynomial_arithmetic_is_exact():
    from fractions import Fraction

    from certo import Poly

    V, (x, y) = _ring("x", "y")
    p = (x + y) * (x - y)
    assert p == x * x - y * y
    assert (x.scaled(Fraction(1, 3)) * x.scaled(3)) == x * x
    assert not (x - x)


def test_the_leading_term_follows_grevlex():
    V, (x, y, z) = _ring("x", "y", "z")
    p = x * x + y * y * y + z
    assert p.lead()[0] == (0, 3, 0)          # degree wins over position


def test_a_polynomial_round_trips_through_its_serialisation():
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    p = (x * x).scaled(3) - y + Poly.const(V, 7)
    assert Poly.parse(V, p.serialize()) == p


def test_division_reconstructs_the_dividend():
    from certo.polynomials import combination, divide

    V, (x, y) = _ring("x", "y")
    f = x * x * y + x * y * y
    gs = [x + y, y]
    quots, rem, _ = divide(f, gs)
    assert combination(quots, gs) + rem == f


# --- v0.3: ideal membership ------------------------------------------------


def _ideal(equations, claim=None, variables=("x", "y")):
    from certo import IdealSpec
    from certo.engines import algebra

    return algebra.ideal(IdealSpec(variables=list(variables),
                                   equations=equations, claim=claim), LIM)


def test_an_inconsistent_system_is_refuted_with_cofactors():
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    r = _ideal([x * x + y * y - Poly.const(V, 1), x - y,
                x + y - Poly.const(V, 3)])
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_the_cofactors_expand_back_to_one():
    from fractions import Fraction

    from certo import Poly
    from certo.polynomials import combination

    V, (x, y) = _ring("x", "y")
    gs = [x - Poly.const(V, 2), x - Poly.const(V, 3)]
    r = _ideal(gs)
    hs = [Poly.parse(V, h) for h in r.certificate.payload["cofactors"]]
    assert combination(hs, gs) == Poly.const(V, 1)


def test_a_consistent_system_is_reported_as_such_not_as_a_timeout():
    """Groebner DECIDES membership; a negative answer is an answer."""
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    # x^2+y^2=1 and x=2 has complex solutions, so the ideal is proper.
    r = _ideal([x * x + y * y - Poly.const(V, 1), x - Poly.const(V, 2)])
    assert r.verdict is Verdict.REFUTED
    assert r.status is Status.SAT
    assert r.certificate is None


def test_a_claim_that_follows_is_certified_the_same_way():
    V, (x, y) = _ring("x", "y")
    r = _ideal([x - y], claim=x * x - y * y)
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_claim_that_does_not_follow_says_so():
    V, (x, y) = _ring("x", "y")
    r = _ideal([x], claim=y)
    assert r.verdict is Verdict.REFUTED


def test_tampering_with_a_cofactor_breaks_the_expansion():
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    cert = _roundtrip(_ideal([x - Poly.const(V, 2),
                              x - Poly.const(V, 3)]).certificate)
    assert verify(cert, LIM).ok
    cert.payload["cofactors"][0] = {"0 0": "5"}
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("expands" in c and not ok for c, ok, _ in rep.checks)


def test_the_field_caveat_is_reported_every_time():
    """1 in the ideal refutes over C; a proper ideal implies nothing real."""
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    rep = verify(_roundtrip(_ideal([x - Poly.const(V, 2),
                                    x - Poly.const(V, 3)]).certificate), LIM)
    assert any("COMPLEX" in w or "COMPLEJOS" in w for w in rep.warnings)


def test_buchberger_gives_up_with_a_budget_rather_than_grinding():
    from certo import IdealSpec, Poly
    from certo.engines import algebra

    V, (x, y, z) = _ring("x", "y", "z")
    hard = [x * x * y - z * z * z, y * y * z - x * x * x,
            z * z * x - y * y * y, x * y * z - Poly.const(V, 1)]
    spec = IdealSpec(variables=list(V), equations=hard, max_pairs=3)
    r = algebra.ideal(spec, LIM)
    assert r.status in (Status.RESOURCE_EXHAUSTED, Status.UNSAT, Status.SAT)


# --- v0.3: sums of squares -------------------------------------------------


def _sos(poly, variables=("x", "y")):
    from certo import SOSSpec
    from certo.engines import algebra

    return algebra.sos(SOSSpec(variables=list(variables), poly=poly), LIM)


def test_a_quartic_is_certified_as_an_exact_sum_of_squares():
    V, (x, y) = _ring("x", "y")
    r = _sos(x * x * x * x + y * y * y * y - x * x * y * y)
    assert r.verdict is Verdict.PROVED
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free


def test_the_certificate_carries_rationals_not_floats():
    from fractions import Fraction

    V, (x, y) = _ring("x", "y")
    p = r = _sos(x * x - (x * y).scaled(2) + y * y)
    for term in r.certificate.payload["terms"]:
        Fraction(term["coef"])                      # parses exactly
        for c in term["form"].values():
            Fraction(c)


def test_motzkin_is_not_a_sum_of_squares_and_is_not_refuted_either():
    """Non-negative everywhere, provably not SOS: the honest third answer."""
    from certo import Poly

    V, (x, y) = _ring("x", "y")
    motzkin = (x * x * x * x * y * y + x * x * y * y * y * y
               - (x * x * y * y).scaled(3) + Poly.const(V, 1))
    r = _sos(motzkin)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.status is Status.UNKNOWN_SOLVER      # never REFUTED
    assert "not refutation" in r.detail.lower() or "NOT a" in r.detail


def test_an_odd_degree_polynomial_is_rejected_immediately():
    V, (x, y) = _ring("x", "y")
    r = _sos(x * x * x)
    assert r.verdict is Verdict.INCONCLUSIVE


def test_a_tampered_square_no_longer_adds_up():
    V, (x, y) = _ring("x", "y")
    cert = _roundtrip(_sos(x * x + y * y).certificate)
    assert verify(cert, LIM).ok
    cert.payload["terms"][0]["coef"] = "3"
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("add up" in c and not ok for c, ok, _ in rep.checks)


def test_a_negative_coefficient_is_caught_even_if_it_expands():
    V, (x, y) = _ring("x", "y")
    cert = _roundtrip(_sos(x * x - y * y + (y * y).scaled(2)).certificate)
    cert.payload["terms"][0]["coef"] = "-1"
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("non-negative" in c and not ok for c, ok, _ in rep.checks)


def test_the_exact_ldl_refuses_an_indefinite_matrix():
    from fractions import Fraction as F

    from certo.sos import ldl

    assert ldl([[F(1), F(0)], [F(0), F(1)]]) is not None
    assert ldl([[F(1), F(2)], [F(2), F(1)]]) is None     # eigenvalues 3, -1


# --- v0.3: primality and factorisation -------------------------------------


def _number(n, question="prime"):
    from certo import NumberSpec
    from certo.engines import algebra

    return algebra.number(NumberSpec(n=n, question=question), LIM)


def test_a_pratt_certificate_is_checked_by_modular_exponentiation():
    r = _number(2 ** 31 - 1)
    assert r.verdict is Verdict.PROVED
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free
    assert len(rep.checks) > 20


def test_a_carmichael_number_does_not_get_a_certificate():
    """561 passes Fermat for most bases; the order condition catches it."""
    r = _number(561)
    assert r.verdict is Verdict.REFUTED
    assert r.certificate is None


def test_the_witness_is_reproducible_across_runs():
    """Small bases in order, not random ones, so two runs agree on the digest."""
    a = _number(1000003).certificate
    b = _number(1000003).certificate
    assert a.digest() == b.digest()


def test_a_missing_factor_of_n_minus_one_is_caught():
    """Dropping one lets a composite through, so the check is not optional."""
    r = _number(2 ** 31 - 1)
    cert = _roundtrip(r.certificate)
    cert.payload["tree"]["factors"].pop()
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("all of" in c and not ok for c, ok, _ in rep.checks)


def test_a_forged_witness_fails_fermat():
    r = _number(1000003)
    cert = _roundtrip(r.certificate)
    cert.payload["tree"]["witness"] = 4
    rep = verify(cert, LIM)
    assert not rep.ok


def test_a_factorisation_multiplies_back_and_its_factors_are_prime():
    r = _number(600851475143, question="factor")
    assert r.verdict is Verdict.PROVED
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert "71" in r.meta["factors"]


def test_a_factorisation_that_does_not_multiply_back_is_caught():
    cert = _roundtrip(_number(360, question="factor").certificate)
    assert verify(cert, LIM).ok
    cert.payload["tree"]["factors"][0]["e"] = 9
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("multiply back" in c and not ok for c, ok, _ in rep.checks)

# --- an ILP has two numbers, and they are not the same number --------------


def _knapsack(cap, integer):
    from fractions import Fraction

    from certo import LPSpec

    s = LPSpec(sense="max", integer=integer)
    s.variable("x")
    s.variable("y")
    s.objective({"x": 1, "y": 1})
    s.constraint({"x": 1, "y": 1}, "<=", Fraction(cap), name="cap")
    return s


def test_an_ilp_reports_the_integer_optimum_not_its_relaxation():
    """It reported the relaxation as `objective`, which is an overclaim."""
    from fractions import Fraction

    from certo.engines import lp

    r = lp.opt(_knapsack(Fraction(3, 2), True), LIM)
    assert r.meta["objective"] == "1"          # achievable
    assert r.meta["bound"] == "3/2"            # certified by the dual
    assert r.meta["objective"] != r.meta["bound"]


def test_an_lp_is_untouched_by_that():
    from fractions import Fraction

    from certo.engines import lp

    r = lp.opt(_knapsack(Fraction(3, 2), False), LIM)
    assert r.meta["objective"] == "3/2"
    assert r.meta["bound"] is None


def test_both_sides_of_an_ilp_are_certified():
    from fractions import Fraction

    from certo.engines import lp

    cert = _roundtrip(lp.opt(_knapsack(Fraction(3, 2), True), LIM).certificate)
    rep = verify(cert, LIM)
    assert rep.ok and rep.solver_free
    assert any("integral point is feasible" in c and ok
               for c, ok, _ in rep.checks)
    assert any("differ" in w for w in rep.warnings)


def test_a_tight_ilp_says_the_optimum_is_certified():
    """When the integral point meets the bound, nu is pinned exactly."""
    from certo.engines import lp

    r = lp.opt(_knapsack(2, True), LIM)
    assert r.meta["objective"] == "2" == r.meta["bound"]
    assert "CERTIFIED" in r.detail or "CERTIFICADO" in r.detail
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert not any("differ" in w for w in rep.warnings)


def test_a_forged_integral_point_is_caught():
    from fractions import Fraction

    from certo.engines import lp

    cert = _roundtrip(lp.opt(_knapsack(Fraction(3, 2), True), LIM).certificate)
    cert.payload["integral_point"] = ["5", "5"]        # violates the capacity
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("feasible" in c and not ok for c, ok, _ in rep.checks)


def test_the_real_packing_that_found_this():
    """Their canonical core: nu = 7, mu* = 15/2, and the gap is the point."""
    from itertools import combinations

    from certo import PackingSpec
    from certo.engines import lp

    lists = [(0, 1), (0, 1, 2), (0, 1, 2, 3), (0, 1, 3), (0, 2, 3, 4), (0, 4)]
    items = []
    for j, block in enumerate(lists):
        for a, b in combinations(block, 2):
            items.append(("t{}_{}_{}".format(j, a, b),
                          ["e{}_{}".format(a, b), "d{}_{}".format(j, a),
                           "d{}_{}".format(j, b)], 1))

    frac = lp.opt(PackingSpec(items=items, capacities=1).to_lp(), LIM)
    integral = lp.opt(PackingSpec(items=items, capacities=1,
                                  integer=True).to_lp(), LIM)
    assert frac.meta["objective"] == "15/2" and frac.meta["exact"]
    assert integral.meta["objective"] == "7"
    assert verify(_roundtrip(frac.certificate), LIM).ok

# --- mixed designs: a searched skeleton, an exact residual -----------------


def _mixed_spec(slots=4, shared="2/3", cap=3):
    from fractions import Fraction

    from certo import LPSpec

    lp = LPSpec(sense="max")
    for i in range(slots):
        lp.variable("y{}".format(i), kind="binary")
        lp.variable("q{}".format(i))
    lp.objective({**{"y{}".format(i): 2 for i in range(slots)},
                  **{"q{}".format(i): 5 for i in range(slots)}})
    for i in range(slots):
        lp.constraint({"y{}".format(i): 1, "q{}".format(i): 1}, "<=", 1,
                      name="slot{}".format(i))
    lp.constraint({"q{}".format(i): 1 for i in range(slots)}, "<=",
                  Fraction(shared), name="shared")
    lp.constraint({"y{}".format(i): 1 for i in range(slots)}, "<=", cap,
                  name="count")
    return lp


def test_kinds_are_per_variable_not_per_spec():
    """`integer=True` makes EVERY variable integer, which is a different
    problem, not a restriction of this one."""
    spec = _mixed_spec()
    assert spec.is_mixed
    assert spec.discrete == ["y0", "y1", "y2", "y3"]
    assert spec.continuous == ["q0", "q1", "q2", "q3"]
    assert spec.kind_of("y0") == "binary" and spec.kind_of("q0") == "continuous"


def test_an_unknown_kind_is_refused():
    from certo import LPSpec

    try:
        LPSpec().variable("x", kind="fuzzy")
    except ValueError as e:
        assert "binary" in str(e)
    else:
        raise AssertionError("it accepted a kind that does not exist")


def test_freezing_moves_the_discrete_contribution_to_the_right_hand_side():
    from fractions import Fraction

    spec = _mixed_spec(slots=2)
    residual, const = spec.frozen({"y0": 1, "y1": 0})
    assert const == 2                              # one slot reserved, gain 2
    assert residual.var_names == ["q0", "q1"]
    rhs = {n: r for n, _, _, r in residual.cons}
    assert rhs["slot0"] == 0 and rhs["slot1"] == 1


def test_a_mixed_design_is_certified_and_verifies_without_a_solver():
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM)
    assert r.verdict is Verdict.SATISFIABLE
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free


def test_the_three_numbers_are_kept_apart():
    from fractions import Fraction

    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM)
    achieved = Fraction(r.meta["achieved"])
    assert achieved == (Fraction(r.meta["discrete_gain"])
                        + Fraction(r.meta["conditional"]))
    assert achieved <= Fraction(r.meta["bound"])    # the relaxation bounds it


def test_meeting_the_relaxation_bound_certifies_global_optimality_for_free():
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM)
    assert r.meta["globally_optimal"] is True
    assert "global optimum" in r.detail or "óptimo global" in r.detail
    rep = verify(_roundtrip(r.certificate), LIM)
    assert not any("NOT CLAIMED" in w or "NO SE AFIRMA" in w
                   for w in rep.warnings)


def test_otherwise_global_optimality_is_explicitly_not_claimed():
    from certo.certificate import Certificate
    from certo.engines import mixed

    cert = _roundtrip(mixed.mixed(_mixed_spec(), LIM).certificate)
    cert.payload["globally_optimal"] = False       # as it would be with a gap
    rep = verify(cert, LIM)
    assert rep.ok
    assert any("NOT CLAIMED" in w or "NO SE AFIRMA" in w for w in rep.warnings)


def test_a_design_short_of_its_target_is_valid_but_insufficient():
    """A shortfall is not an invalid certificate -- it is a valid certificate
    for a design that falls short, and the difference matters to a reader."""
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM, target="1000")
    assert r.verdict is Verdict.REFUTED            # the design misses
    assert r.meta["deficit"]
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok                                  # the CERTIFICATE is fine
    assert any("SHORT OF TARGET" in w or "POR DEBAJO" in w
               for w in rep.warnings)


def test_a_forged_assignment_fails_the_original_constraints():
    from certo.engines import mixed

    cert = _roundtrip(mixed.mixed(_mixed_spec(), LIM).certificate)
    assert verify(cert, LIM).ok
    for k in cert.payload["assignment"]:
        cert.payload["assignment"][k] = "1"        # every slot reserved
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("original constraint" in c and not ok
               for c, ok, _ in rep.checks)


def test_a_fractional_binary_is_caught():
    from certo.engines import mixed

    cert = _roundtrip(mixed.mixed(_mixed_spec(), LIM).certificate)
    cert.payload["assignment"]["y0"] = "1/2"
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("really is discrete" in c and not ok
               for c, ok, _ in rep.checks)


def test_the_residual_must_be_the_original_problem_frozen():
    """Otherwise the sub-certificate could be about a different problem --
    the same gap `compose` closes between a lemma and its use."""
    from certo.engines import mixed

    cert = _roundtrip(mixed.mixed(_mixed_spec(), LIM).certificate)
    cert.payload["system"][0]["rhs"] = "99"        # the original moved
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("substituted" in c and not ok for c, ok, _ in rep.checks)


def test_a_spec_with_no_discrete_variables_says_to_use_opt():
    from certo import LPSpec
    from certo.engines import mixed

    lp = LPSpec(sense="max")
    lp.variable("x")
    lp.objective({"x": 1})
    lp.constraint({"x": 1}, "<=", 1, name="c")
    r = mixed.mixed(lp, LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "opt" in r.detail

# --- the second round of feedback ------------------------------------------


def test_a_literal_exponent_on_a_real_is_not_a_non_constant_exponent():
    """`S**4` on a REAL S gives z3 a RATIONAL literal 4, not an integer one,
    so is_int_value said no and an ordinary quartic was rejected."""
    import z3

    from certo.linarith import polynomial

    S = z3.Real("S")
    n = z3.Int("n")
    assert polynomial(S ** 4) == polynomial(S * S * S * S)
    assert polynomial(n ** 3) == polynomial(n * n * n)
    assert polynomial(S ** 0) == {(): 1}


def test_fractional_and_symbolic_exponents_are_still_refused():
    import z3

    from certo.linarith import NotPolynomial, polynomial

    S, n = z3.Real("S"), z3.Int("n")
    for bad in (S ** z3.RealVal("1/2"), S ** -2, S ** n):
        try:
            polynomial(bad)
        except NotPolynomial:
            pass
        else:
            raise AssertionError("accepted {}".format(bad))


def test_a_quartic_identity_certifies_through_ideal():
    """The shape that was rejected: powers written with `**`."""
    import z3

    from certo import IdealSpec
    from certo.engines import algebra

    S = z3.Real("S")
    r = algebra.ideal(IdealSpec(variables=["S"], equations=[S ** 2 - 4],
                                claim=S ** 4 - 16), LIM)
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_the_three_milp_levels_are_named():
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM)
    assert r.meta["level"] == "global_optimum"
    rep = verify(_roundtrip(r.certificate), LIM)
    assert "GLOBAL OPTIMUM" in rep.detail or "ÓPTIMO GLOBAL" in rep.detail


def test_a_skeleton_can_come_from_someone_elses_solver():
    """A real MILP may be HiGHS, Gurobi or a person; requiring CBC to
    reproduce it would put certo's limits in front of a real construction."""
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM,
                    freeze={"y0": 1, "y1": 1, "y2": 0, "y3": 1})
    assert r.verdict is Verdict.SATISFIABLE
    assert r.meta["skeleton_from"] == "external"
    assert sorted(r.meta["selected"]) == ["y0", "y1", "y3"]
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("ANOTHER solver" in w or "OTRO solver" in w
               for w in rep.warnings)


def test_a_frozen_assignment_is_checked_like_any_other():
    """Where it came from changes nothing about what is certified."""
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM,
                    freeze={"y0": 1, "y1": 1, "y2": 1, "y3": 1})   # 4 > cap 3
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None


def test_an_incomplete_frozen_assignment_names_what_is_missing():
    from certo.engines import mixed

    r = mixed.mixed(_mixed_spec(), LIM, freeze={"y0": 1})
    assert r.status is Status.OUT_OF_THEORY
    assert "y1" in r.detail


def test_opt_takes_a_target_and_certifies_reaching_it():
    """For an existence proof the question is whether a bound is reached."""
    from certo.engines import lp

    r = lp.opt(_knapsack(3, False), LIM, target="2")
    assert r.meta["meets_target"] is True
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("reaches the target" in c and ok for c, ok, _ in rep.checks)


def test_falling_short_of_an_opt_target_is_a_warning_not_invalidity():
    from certo.engines import lp

    r = lp.opt(_knapsack(3, False), LIM, target="99")
    assert r.meta["meets_target"] is False
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("SHORT OF TARGET" in w or "POR DEBAJO" in w
               for w in rep.warnings)


def test_a_packing_can_be_whole_in_one_item_kind_only():
    from certo import Graph, PackingSpec

    g = Graph.from_edges(6, [(i, j) for i in range(6) for j in range(i + 1, 6)])
    base = PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
    pk = PackingSpec(items=base.items, capacities=base.capacities,
                     sense="max", integer={"K3"})
    assert pk.discrete_kinds() == {"K3"}
    lp_spec = pk.to_lp()
    assert lp_spec.is_mixed
    assert all(lp_spec.kind_of(n) == "integer"
               for n, _, _, k in pk.items if k == "K3")
    assert all(lp_spec.kind_of(n) == "continuous"
               for n, _, _, k in pk.items if k == "K4")


def test_opt_refuses_to_report_a_design_on_a_mixed_problem():
    """Rounding every variable would round the fractional weights to zero and
    report a design worth nothing. That number is `mixed`'s to compute."""
    from certo import Graph, PackingSpec
    from certo.engines import lp, mixed

    g = Graph.from_edges(6, [(i, j) for i in range(6) for j in range(i + 1, 6)])
    base = PackingSpec.cliques_in_graph(g, gains={3: 2, 4: 5})
    pk = PackingSpec(items=base.items, capacities=base.capacities,
                     sense="max", integer={"K3"}).to_lp()

    r = lp.opt(pk, LIM)
    assert r.meta["objective"] is None          # no design claimed
    assert r.meta["bound"] == "25/2"
    assert "mixed" in r.detail

    assert mixed.mixed(pk, LIM).meta["achieved"] == "25/2"


def test_the_certificate_records_which_variables_are_discrete():
    from certo.engines import lp

    p = lp.opt(_mixed_spec(), LIM).certificate.payload
    assert p["kinds"]["y0"] == "binary"
    assert p["kinds"]["q0"] == "continuous"

# --- P1: lists packings, the gap, and proved optimality --------------------


def _core():
    from certo import PackingSpec, SetFamily

    fam = SetFamily(5, [(0, 1), (0, 1, 2), (0, 1, 2, 3),
                        (0, 1, 3), (0, 2, 3, 4), (0, 4)])
    return PackingSpec.lists(fam)


def test_the_lists_constructor_builds_the_packing_the_corpus_uses():
    """A pair once globally, and once per (list, element)."""
    spec = _core()
    assert len(spec.items) == 20
    name, res, gain, kind = spec.items[0]
    assert kind == "pair" and gain == 1
    assert len(res) == 3                       # the pair, and two incidences


def test_the_gap_carries_both_sides_and_they_match():
    from certo import packing as pk

    cert, meta = pk.gap(_core(), LIM)
    assert (meta["mu"], meta["nu"], meta["gap"]) == ("15/2", "7", "1/2")
    rep = verify(_roundtrip(cert), LIM)
    assert rep.ok
    assert any("same packing" in c and ok for c, ok, _ in rep.checks)


def test_a_gap_whose_halves_disagree_is_caught():
    from certo import packing as pk

    cert = _roundtrip(pk.gap(_core(), LIM)[0])
    assert verify(cert, LIM).ok
    cert.payload["gap"] = "1/3"                # no longer the difference
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("difference" in c and not ok for c, ok, _ in rep.checks)


def test_a_gap_from_a_design_says_nu_is_not_proved_optimal():
    from certo import packing as pk

    rep = verify(_roundtrip(pk.gap(_core(), LIM)[0]), LIM)
    assert any("not a proven integral optimum" in w or "no un óptimo" in w
               for w in rep.warnings)


def test_branch_and_bound_proves_the_integral_optimum():
    """The whole point: nu = 7 stops being a design and becomes the optimum."""
    from certo import PackingSpec
    from certo.engines import bb

    core = _core()
    whole = PackingSpec(items=core.items, capacities=core.capacities,
                        sense="max", integer=True)
    r = bb.prove_optimal(whole.to_lp(), LIM, max_nodes=30_000)
    assert r.verdict is Verdict.PROVED
    assert r.meta["optimum"] == "7"
    assert r.meta["infeasible"] > 0            # Farkas rays closed real leaves
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_missing_child_makes_the_tree_a_non_proof():
    """A tree with a hole reads exactly like a complete one."""
    from certo.engines import bb

    cert = _roundtrip(bb.prove_optimal(_c5(), LIM).certificate)
    assert verify(cert, LIM).ok
    branch = next(n for n in cert.payload["nodes"] if n["why"] == "branch")
    child = branch["fixed"] + [[branch["on"], branch["values"][0]]]
    key = ",".join("{}={}".format(v, x) for v, x in child)
    cert.payload["nodes"] = [n for n in cert.payload["nodes"]
                             if ",".join("{}={}".format(v, x)
                                         for v, x in n["fixed"]) != key]
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("children" in c and not ok for c, ok, _ in rep.checks)


def _c5():
    from certo import LPSpec

    lp = LPSpec(sense="max")
    for i in range(5):
        lp.variable("y{}".format(i), kind="binary")
    lp.objective({"y{}".format(i): 1 for i in range(5)})
    for i in range(5):
        lp.constraint({"y{}".format(i): 1, "y{}".format((i + 1) % 5): 1},
                      "<=", 1, name="e{}".format(i))
    return lp


def test_a_leaf_pruned_above_the_incumbent_is_caught():
    from certo.engines import bb

    cert = _roundtrip(bb.prove_optimal(_c5(), LIM).certificate)
    node = next(n for n in cert.payload["nodes"] if n["why"] == "bound")
    node["bound"] = "99"                       # it could have held something
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("closed by a certificate" in c and not ok
               for c, ok, _ in rep.checks)


def test_an_unbounded_discrete_variable_has_no_tree_to_exhibit():
    from certo import LPSpec
    from certo.engines import bb

    lp = LPSpec(sense="max")
    lp.variable("n", kind="integer")            # no upper bound
    lp.objective({"n": 1})
    lp.constraint({"n": 1}, "<=", 10, name="c")
    r = bb.prove_optimal(lp, LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "upper bound" in r.detail


def test_a_farkas_ray_certifies_infeasibility_by_three_dot_products():
    from certo import LPSpec
    from certo.engines import lp

    s = LPSpec(sense="max")
    s.variable("x")
    s.objective({"x": 1})
    s.constraint({"x": 1}, "<=", 1, name="hi")
    s.constraint({"x": -1}, "<=", -2, name="lo")     # x >= 2 and x <= 1
    cert = lp.infeasible_certificate(s, LIM)
    assert cert is not None
    rep = verify(_roundtrip(cert), LIM)
    assert rep.ok and rep.solver_free
    assert len(rep.checks) == 3


def test_a_tampered_ray_stops_being_a_ray():
    from certo import LPSpec
    from certo.engines import lp

    s = LPSpec(sense="max")
    s.variable("x")
    s.objective({"x": 1})
    s.constraint({"x": 1}, "<=", 1, name="hi")
    s.constraint({"x": -1}, "<=", -2, name="lo")
    cert = _roundtrip(lp.infeasible_certificate(s, LIM))
    cert.payload["y"] = ["1", "0"]              # b.y is now positive
    rep = verify(cert, LIM)
    assert not rep.ok


def test_a_packing_item_is_bounded_by_its_tightest_resource():
    """Without it branch and bound has infinitely many children per node."""
    spec = _core()
    lp_spec = spec.to_lp()
    assert all(hi is None for _, hi in lp_spec.bounds.values())   # fractional

    from certo import PackingSpec

    whole = PackingSpec(items=spec.items, capacities=spec.capacities,
                        sense="max", integer=True).to_lp()
    assert all(hi == 1 for _, hi in whole.bounds.values())


def test_by_orbit_works_on_graph_sweeps_too():
    from certo.graphs import is_chordal

    r = graphsearch.sweep(
        SweepSpec(n=6, filters=["connected"], predicate=is_chordal,
                  canonicalize="auto"),
        LIM, use_geng=False, by_orbit=True)
    assert r.meta["by_orbit"] is True
    p = r.certificate.payload
    assert all(k in p for k in ("by_orbit", "evaluated", "spot_checks"))
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_inferring_nothing_is_not_a_failure():
    """Every orbit a singleton means it was a full sweep, not a broken one."""
    from certo.graphs import is_chordal

    r = graphsearch.sweep(
        SweepSpec(n=5, filters=["connected"], predicate=is_chordal,
                  canonicalize="auto"),
        LIM, use_geng=False, by_orbit=True)
    assert r.meta["inferred"] == 0
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("inferred NOTHING" in w or "no infirió NADA" in w
               for w in rep.warnings)

# --- order: a feasibility that does not improve with n ---------------------


def _sym(*names):
    import z3

    return z3.Reals(" ".join(names))


def test_the_term_that_was_invisible_to_both_lean_and_prove():
    """Not an infeasibility -- a feasibility that does not improve with n."""
    from certo import OrderSpec
    from certo.engines import order

    k, W, C, u, d, p = _sym("k", "W", "C", "u", "d", "p")
    spec = OrderSpec(
        expression=5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10),
        orders={"k": 0, "W": 2, "C": 1, "u": 0, "d": 2, "p": 0})
    r = order.order(spec, LIM)
    assert r.meta["degree"] == "0"
    assert r.meta["behaviour"] == "constant"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_claiming_it_decays_is_refuted():
    from certo import OrderSpec
    from certo.engines import order

    k, W, C, u, d, p = _sym("k", "W", "C", "u", "d", "p")
    spec = OrderSpec(
        expression=5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10),
        orders={"k": 0, "W": 2, "C": 1, "u": 0, "d": 2, "p": 0},
        expect="decays")
    r = order.order(spec, LIM)
    assert r.verdict is Verdict.REFUTED
    assert "Theta(1)" in r.detail


def test_decaying_and_growing_terms_are_told_apart():
    from certo import OrderSpec
    from certo.engines import order

    C, d = _sym("C", "d")
    o = {"C": 1, "d": 2}
    assert order.order(OrderSpec(expression=C / (d * d), orders=o),
                       LIM).meta["behaviour"] == "decays"
    assert order.order(OrderSpec(expression=C * d, orders=o),
                       LIM).meta["behaviour"] == "grows"


def test_cancellation_is_decided_not_estimated():
    """DIFFERENT monomials landing on the same exponent, cancelling exactly.

    `C^2` and `d` are different terms, but with C ~ n and d ~ n^2 both are
    n^2 -- and their coefficients sum to zero, so the top exponent is not
    there. With `Fraction` that is decided rather than estimated.
    """
    from certo import OrderSpec
    from certo.engines import order

    C, d, W = _sym("C", "d", "W")
    r = order.order(OrderSpec(expression=C * C - d + W,
                              orders={"C": 1, "d": 2, "W": 1}), LIM)
    assert r.meta["degree"] == "1"          # the two n^2 terms cancelled
    assert r.meta["cancelled"] == 1


def test_a_symbol_with_no_order_is_an_error_not_an_assumption():
    from certo import OrderSpec
    from certo.engines import order

    a, b = _sym("a", "b")
    r = order.order(OrderSpec(expression=a * b, orders={"a": 1}), LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "b" in r.detail


def test_dividing_by_a_sum_is_refused_rather_than_guessed():
    """1/(x+y) has an order that depends on which dominates."""
    from certo import OrderSpec
    from certo.engines import order

    x, y = _sym("x", "y")
    r = order.order(OrderSpec(expression=1 / (x + y), orders={"x": 1, "y": 2}),
                    LIM)
    assert r.status is Status.OUT_OF_THEORY
    assert "sum" in r.detail or "suma" in r.detail


def test_the_order_certificate_needs_neither_solver_nor_spec():
    from certo import OrderSpec
    from certo.engines import order

    C, d = _sym("C", "d")
    cert = _roundtrip(order.order(
        OrderSpec(expression=C / d, orders={"C": 1, "d": 2}), LIM).certificate)
    rep = verify(cert, LIM)
    assert rep.ok and rep.solver_free
    assert any("EXPONENT" in w or "EXPONENTE" in w for w in rep.warnings)


def test_a_forged_degree_is_recomputed_and_caught():
    from certo import OrderSpec
    from certo.engines import order

    C, d = _sym("C", "d")
    cert = _roundtrip(order.order(
        OrderSpec(expression=C / d, orders={"C": 1, "d": 2}), LIM).certificate)
    assert verify(cert, LIM).ok
    cert.payload["degree"] = "5"
    rep = verify(cert, LIM)
    assert not rep.ok
    assert any("leading exponent" in c and not ok for c, ok, _ in rep.checks)


# --- papercuts from the same report ----------------------------------------


def test_a_certificate_is_read_whether_it_arrived_alone_or_inside_a_run():
    """`--cert FILE` writes one shape and `--json` another; both are right."""
    import json as _json

    from certo import Spec
    from certo.engines import smt

    x = _sym("x")[0]
    s = Spec()
    s.assume("h", x >= 1)
    s.claim(x >= 1)
    res = smt.prove(s, LIM)

    alone = Certificate.from_dict(_json.loads(_json.dumps(
        res.certificate.to_dict())))
    inside = Certificate.from_dict(_json.loads(_json.dumps(res.to_dict())))
    assert alone.kind == inside.kind == "unsat_core"
    assert alone.digest() == inside.digest()


def test_vacuity_names_the_minimal_clash_instead_of_sending_you_elsewhere():
    import z3

    from certo import Spec
    from certo.engines import smt

    x, y = _sym("x", "y")
    s = Spec()
    s.assume("x_big", x > 10)
    s.assume("y_ok", y >= 0)            # innocent, and must not be blamed
    s.assume("x_small", x < 1)
    s.claim(x + y == 42)

    r = smt.prove(s, LIM)
    assert r.meta["vacuous"] is True
    assert set(r.meta["clash"]) == {"x_big", "x_small"}
    assert "x_big" in r.detail

    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    assert any("x_big, x_small" in w for w in rep.warnings)


def test_the_clash_is_an_optional_field_the_frozen_schema_allows():
    """An older reader ignores it; a newer one uses it."""
    from certo.certificate import unsat_core_certificate

    cert = unsat_core_certificate("(check-sat)", ["a"], [], vacuous=True)
    assert cert.payload["clash"] == []
    assert verify(_roundtrip(cert), LIM) is not None


# --- lint: the questions asked before the compute is spent -----------------


def _lint_file(tmp, body: str):
    """A spec on disk, because `lint` reads files the way a user does."""
    import hashlib

    name = "lint_" + hashlib.sha256(body.encode()).hexdigest()[:10] + ".py"
    f = tmp / name
    f.write_text(body, encoding="utf-8")
    return str(f)


def _tmp():
    import tempfile

    return pathlib.Path(tempfile.mkdtemp(prefix="certo_lint_"))


def test_lint_catches_contradictory_hypotheses_before_the_proof_is_run():
    """The headline check: vacuity found first, not after a valid-and-empty win."""
    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "import z3\n"
        "from certo.spec import Spec\n"
        "def spec():\n"
        "    x, y = z3.Real('x'), z3.Real('y')\n"
        "    s = Spec(title='a regime nobody is in')\n"
        "    s.assume('x_big', x > 10)\n"
        "    s.assume('y_ok', y > 0)\n"
        "    s.assume('x_small', x < 1)\n"
        "    s.claim(y * y >= 0)\n"
        "    return s\n"))
    rep = linter.lint(f, LIM)
    assert rep["kind"] == "Spec"
    clash = [x for x in rep["findings"] if x["key"] == "spec.vacuous"]
    assert len(clash) == 1
    assert "x_big" in clash[0]["text"] and "x_small" in clash[0]["text"]
    # The innocent hypothesis is not blamed: a minimal clash, not the core.
    assert "y_ok" not in clash[0]["text"]
    assert rep["errors"] == 1 and not rep["ok"]


def test_lint_catches_the_induction_gap_without_discharging_a_base_case():
    """The engine refuses this too -- after proving every base case first."""
    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "import z3\n"
        "from certo.spec import InductSpec, Spec\n"
        "def spec():\n"
        "    k = z3.Int('k')\n"
        "    step = Spec()\n"
        "    step.assume('k_big', k >= 10)\n"
        "    step.claim(k + 1 >= 11)\n"
        "    return InductSpec(k0=3, base_upto=8, base=lambda j: None,\n"
        "                      step=step, step_from=10, bridge='...',\n"
        "                      title='a chain that does not join')\n"))
    rep = linter.lint(f, LIM)
    gaps = [x for x in rep["findings"] if x["key"] == "induct.gap"]
    assert len(gaps) == 1
    assert "10" in gaps[0]["text"] and "8" in gaps[0]["text"]


def test_lint_says_a_bool_predicate_means_reproducible_not_certified():
    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "from certo.spec import DomainSpec\n"
        "def spec():\n"
        "    return DomainSpec(items=[(a, b) for a in range(4)"
        " for b in range(4)],\n"
        "                      predicate=lambda p: p[0] + p[1] >= 0,\n"
        "                      key=lambda p: '%d,%d' % p, title='t')\n"))
    rep = linter.lint(f, LIM)
    keys = {x["key"] for x in rep["findings"]}
    assert "sweep.bool" in keys
    assert "domain.no_reduce" in keys          # `shrink` would refuse
    # Notes alone are not a failure: this spec is fine, it just says less.
    assert rep["ok"] and rep["errors"] == 0 and rep["warnings"] == 0


def test_lint_reads_the_domain_size_without_materialising_it():
    """A generator of ten million items must not be turned into a list."""
    from certo import lint as linter
    from certo.lint import PEEK

    f = _lint_file(_tmp(), (
        "from certo.spec import DomainSpec\n"
        "def spec():\n"
        "    return DomainSpec(items=lambda: iter(range(10 ** 7)),\n"
        "                      predicate=lambda i: i >= 0, title='big')\n"))
    rep = linter.lint(f, LIM)
    huge = [x for x in rep["findings"] if x["key"] == "domain.huge"]
    assert len(huge) == 1
    assert str(PEEK) in huge[0]["text"] or "100000" in huge[0]["text"]


def test_lint_reports_an_unassigned_magnitude_as_an_error():
    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "import z3\n"
        "from certo.spec import OrderSpec\n"
        "def spec():\n"
        "    d, C, W = z3.Real('d'), z3.Real('C'), z3.Real('W')\n"
        "    return OrderSpec(expression=W * C / (d * d),\n"
        "                     orders={'W': 2, 'C': 1}, title='t')\n"))
    rep = linter.lint(f, LIM)
    bad = [x for x in rep["findings"] if x["key"] == "order.unassigned"]
    assert len(bad) == 1 and "d" in bad[0]["text"]
    assert rep["errors"] == 1


def test_lint_warns_that_integer_true_makes_every_variable_integer():
    """A user read it as "there are integers in here" and got everything rounded."""
    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "from certo.spec import LPSpec\n"
        "def spec():\n"
        "    lp = LPSpec(sense='max', integer=True, title='t')\n"
        "    lp.variable('x'); lp.variable('y')\n"
        "    lp.objective({'x': 1, 'y': 1})\n"
        "    lp.constraint({'x': 1, 'y': 1}, '<=', 3, name='cap')\n"
        "    return lp\n"))
    rep = linter.lint(f, LIM)
    warn = [x for x in rep["findings"] if x["key"] == "lp.integer_all"]
    assert len(warn) == 1 and "2" in warn[0]["text"]
    assert rep["warnings"] == 1 and not rep["ok"]


def test_lint_tells_a_script_from_a_broken_spec():
    from certo import lint as linter

    f = _lint_file(_tmp(), "print('I am a script')\n")
    rep = linter.lint(f, LIM)
    assert [x["key"] for x in rep["findings"]] == ["no_spec_fn"]


def test_lint_does_not_enumerate_a_family_it_cannot_afford():
    """Knowing a sweep's size must not cost what the sweep costs."""
    import time

    from certo import lint as linter

    f = _lint_file(_tmp(), (
        "from certo.spec import SweepSpec\n"
        "def spec():\n"
        "    return SweepSpec(n=11, predicate=lambda g: True, title='t')\n"))
    t0 = time.perf_counter()
    rep = linter.lint(f, LIM)
    assert time.perf_counter() - t0 < 5.0
    texts = " ".join(x["text"] for x in rep["findings"])
    assert "1018997864" in texts.replace(",", "")
    assert any(x["key"] == "sweep.not_probed" for x in rep["findings"])


# --- status: where the proof stands ---------------------------------------


def test_status_finds_the_bridges_a_proof_rests_on():
    """A bridge is legitimate. Losing count of them is not."""
    from certo import status_report
    from certo.certificate import proof_certificate

    tmp = _tmp()
    cert = proof_certificate(
        title="the theorem", theorem_smt2="(assert true)",
        assumptions=[], assumptions_smt2="",
        lemmas=[{"name": "counted", "derived": True, "cert": None},
                {"name": "k6", "derived": False, "cert": None,
                 "bridge": "the DRAT proof says the encoding is unsat"}],
        step=None, used=["counted", "k6"], unused=[],
    )
    (tmp / "p.json").write_text(json.dumps(cert.to_dict()), encoding="utf-8")

    rep = status_report.scan(str(tmp))
    assert rep["certificates"] == 1
    assert len(rep["owed"]) == 1
    assert rep["owed"][0]["name"] == "k6"
    assert "DRAT" in rep["owed"][0]["why"]
    assert not rep["hollow"] and not rep["stale"]


def test_status_separates_results_from_the_certificates_they_embed():
    """A lemma's certificate is not a result; the proof on top of it is."""
    import z3

    from certo import Spec, status_report
    from certo.certificate import proof_certificate
    from certo.engines import smt

    x = z3.Real("x")
    s = Spec()
    s.assume("pos", x > 0)
    s.claim(x >= 0)
    sub = smt.prove(s, LIM).certificate.to_dict()

    tmp = _tmp()
    (tmp / "lemma.json").write_text(json.dumps(sub), encoding="utf-8")
    top = proof_certificate(
        title="on top", theorem_smt2="(assert true)", assumptions=[],
        assumptions_smt2="",
        lemmas=[{"name": "pos", "derived": True, "cert": sub}],
        step=None, used=["pos"], unused=[],
    )
    (tmp / "top.json").write_text(json.dumps(top.to_dict()), encoding="utf-8")

    rep = status_report.scan(str(tmp))
    assert rep["certificates"] == 2
    # Both files hold a certificate; only one of them is a result.
    assert [n["kind"] for n in rep["results"]] == ["proof"]


def test_status_names_a_vacuous_proof_as_hollow_with_its_clash():
    import z3

    from certo import Spec, status_report
    from certo.engines import smt

    x, y = z3.Real("x"), z3.Real("y")
    s = Spec()
    s.assume("x_big", x > 10)
    s.assume("y_ok", y >= 0)
    s.assume("x_small", x < 1)
    s.claim(x + y == 42)

    tmp = _tmp()
    (tmp / "v.json").write_text(
        json.dumps(smt.prove(s, LIM).certificate.to_dict()), encoding="utf-8")

    rep = status_report.scan(str(tmp))
    assert len(rep["hollow"]) == 1
    text = rep["hollow"][0]["text"]
    assert "x_big" in text and "x_small" in text and "y_ok" not in text


def test_status_notices_the_spec_moved_under_a_certificate():
    import z3

    from certo import Spec, status_report
    from certo.engines import smt

    tmp = _tmp()
    spec_file = tmp / "s.py"
    spec_file.write_text("# version one\n", encoding="utf-8")

    x = z3.Real("x")
    s = Spec()
    s.assume("pos", x > 0)
    s.claim(x >= 0)
    cert = smt.prove(s, LIM).certificate.stamp(str(spec_file))
    (tmp / "c.json").write_text(json.dumps(cert.to_dict()), encoding="utf-8")

    assert not status_report.scan(str(tmp))["stale"]
    spec_file.write_text("# version TWO, materially different\n",
                         encoding="utf-8")
    stale = status_report.scan(str(tmp))["stale"]
    assert len(stale) == 1 and stale[0]["why"] == "changed"

    spec_file.unlink()
    assert status_report.scan(str(tmp))["stale"][0]["why"] == "gone"


def test_status_skips_files_that_are_not_certificates_without_complaining():
    """A ledger, a config and somebody's notes all live in the same directory."""
    from certo import status_report

    tmp = _tmp()
    (tmp / "notes.json").write_text('{"hello": "world"}', encoding="utf-8")
    (tmp / "broken.json").write_text("{not json", encoding="utf-8")
    rep = status_report.scan(str(tmp))
    assert rep["certificates"] == 0 and rep["skipped"] == 2


def test_status_reads_a_run_as_readily_as_a_bare_certificate():
    """`--cert` writes one shape and `--json` writes the other. Both are right."""
    import z3

    from certo import Spec, status_report
    from certo.engines import smt

    x = z3.Real("x")
    s = Spec()
    s.assume("pos", x > 0)
    s.claim(x >= 0)
    res = smt.prove(s, LIM)

    tmp = _tmp()
    (tmp / "run.json").write_text(json.dumps(res.to_dict()), encoding="utf-8")
    rep = status_report.scan(str(tmp))
    assert rep["certificates"] == 1
    assert rep["results"][0]["kind"] == "unsat_core"



def test_status_inherits_bridges_upward_but_not_unclaimed_optimality():
    """Two debts, two behaviours, and the difference is the point.

    A bridge is an ASSUMPTION: whatever stands on it stands on it too, however
    many levels down. An unclaimed optimality is a STATEMENT ABOUT ONE
    CERTIFICATE -- a proof citing a `gap` for the value 15/2 is not thereby
    claiming the optimum, and a `branch_bound` certificate is precisely the
    proof its own incumbent lacked.
    """
    from certo import status_report
    from certo.certificate import gap_certificate, proof_certificate

    inner = gap_certificate(
        fractional={"kind": "lp_dual", "payload": {}},
        integral={"kind": "mixed_design",
                  "payload": {"level": "conditional_optimum"}},
        mu="15/2", nu="7", gap="1/2", tight=[],
        level="conditional_optimum", title="the gap",
    ).to_dict()
    top = proof_certificate(
        title="on top", theorem_smt2="(assert true)", assumptions=[],
        assumptions_smt2="",
        lemmas=[{"name": "gap_is_half", "derived": False, "cert": inner,
                 "bridge": "reading the dual as a statement about the packing"}],
        step=None, used=["gap_is_half"], unused=[],
    )

    tmp = _tmp()
    (tmp / "top.json").write_text(json.dumps(top.to_dict()), encoding="utf-8")
    rep = status_report.scan(str(tmp))

    sorts = {o["sort"] for o in rep["owed"]}
    assert sorts == {"bridge"}, rep["owed"]
    assert rep["owed"][0]["name"] == "gap_is_half"

    # Alone, that same gap certificate DOES report its unclaimed optimality:
    # the rule is about inheritance, not about hiding it.
    alone = _tmp()
    (alone / "gap.json").write_text(json.dumps(inner), encoding="utf-8")
    assert [o["sort"] for o in status_report.scan(str(alone))["owed"]] \
        == ["not_claimed"]



def test_a_fractional_integral_point_does_not_verify():
    """Found by a user reading output, not code.

    `_verify_lp_dual` checked the declared integral point for non-negativity,
    for `Ax <= b`, and for matching its declared objective -- and never that
    the values were integers. `x = 3/2` satisfies `x + y <= 3` and hits the
    declared value of 3 perfectly well, and used to pass every check.
    """
    from certo.engines import lp
    from certo.spec import LPSpec

    s = LPSpec(sense="max", integer=True, title="maximise x + y, x + y <= 3")
    s.variable("x")
    s.variable("y")
    s.objective({"x": 1, "y": 1})
    s.constraint({"x": 1, "y": 1}, "<=", 3, name="cap")

    cert = lp.opt(s, LIM).certificate
    assert verify(_roundtrip(cert), LIM).ok

    forged = json.loads(json.dumps(cert.to_dict()))
    forged["payload"]["integral_point"] = ["3/2", "3/2"]
    rep = verify(Certificate.from_dict(forged), LIM)
    assert not rep.ok
    failed = [name for name, ok, _ in rep.checks if not ok]
    assert len(failed) == 1, rep.checks
    named = [d for name, ok, d in rep.checks if not ok][0]
    assert "x" in named and "y" in named


def test_a_mixed_problems_continuous_weights_may_be_fractional():
    """The integrality check is per DECLARED KIND, not blanket.

    A mixed design whose continuous weights are 1/6 is not an offender; the
    first version of this check would have called every one of them one.
    """
    from certo.engines import mixed
    from certo.spec import LPSpec

    s = LPSpec(sense="max", title="one switch, one continuous weight")
    s.variable("pick", 0, 1, kind="binary")
    s.variable("w", 0, None)
    s.objective({"pick": 1, "w": 1})
    s.constraint({"w": 6}, "<=", 1, name="cap")
    s.constraint({"pick": 1}, "<=", 1, name="one")

    r = mixed.mixed(s, LIM)
    assert r.certificate is not None
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok, [c for c in rep.checks if not c[1]]
    # The continuous weight really is fractional, which is the point.
    assert r.certificate.payload["continuous"]["w"] == "1/6"



# --- the question people actually ask -------------------------------------


def _regime():
    """Satisfiable hypotheses. dens = 1/2, kappa = 4 is a point in it."""
    import z3

    from certo import Spec

    d, k = z3.Reals("dens kappa")
    s = Spec(title="a regime that is NOT empty")
    s.assume("dens_ok", d > z3.RealVal(1) / 4)
    s.assume("kappa_large", k >= 4)
    s.assume("sparse", d <= z3.RealVal(1) / 2)
    return s, d, k


def test_claim_false_answers_the_opposite_of_the_question_and_says_so():
    """The footgun, pinned: `check` is right and the reading is inverted.

    A user wrote `claim(False)` to ask "are my hypotheses satisfiable?" and
    got UNSATISFIABLE on a system with models. The verdict does not change --
    `hypotheses AND False` really is unsat -- but it can no longer be read as
    a statement about the hypotheses without being told otherwise.
    """
    import z3

    from certo.engines import smt

    spec, _, _ = _regime()
    spec.claim(z3.BoolVal(False))

    r = smt.check(spec, LIM)
    assert r.verdict is Verdict.UNSATISFIABLE      # correct, and useless
    assert r.meta["constant_goal"] == "false"
    assert "hypotheses-only" in r.detail


def test_hypotheses_only_exhibits_a_point_in_a_non_empty_regime():
    """Not an argument that one exists: the parameters, on the table."""
    from certo.engines import smt

    spec, _, _ = _regime()
    r = smt.check(spec, LIM, hypotheses_only=True)
    assert r.verdict is Verdict.SATISFIABLE
    assert r.meta["hypotheses_only"] is True
    # A model certificate needs no solver to re-check: the non-emptiness of
    # the regime is the one answer here that verifies by evaluation.
    assert r.certificate.kind == "model"
    assert r.certificate.solver_free
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_hypotheses_only_names_the_minimal_clash_when_the_regime_is_empty():
    import z3

    from certo.engines import smt

    from certo import Spec

    d, k = z3.Reals("dens kappa")
    s = Spec(title="an empty one")
    s.assume("innocent", k >= 4)
    s.assume("dens_floor", d >= z3.RealVal(3) / 4)
    s.assume("sparse", d <= z3.RealVal(1) / 2)
    s.claim(z3.BoolVal(True))

    r = smt.check(s, LIM, hypotheses_only=True)
    assert r.verdict is Verdict.UNSATISFIABLE
    assert set(r.meta["clash"]) == {"dens_floor", "sparse"}
    assert "innocent" not in r.detail
    assert r.certificate.payload["vacuous"] is True


def test_hypotheses_only_ignores_the_claim_entirely():
    """Whatever the claim says, the question is about the hypotheses."""
    import z3

    from certo.engines import smt

    spec, d, _ = _regime()
    spec.claim(d > 10 ** 6)                # false in the regime, and irrelevant
    r = smt.check(spec, LIM, hypotheses_only=True)
    assert r.verdict is Verdict.SATISFIABLE


# --- an unsat core, stated in Lean ----------------------------------------


def test_a_linear_core_exports_real_lean_hypotheses():
    from certo import leanexport
    from certo.engines import smt

    from certo import Spec
    import z3

    a, b = z3.Ints("a b")
    s = Spec(title="an integer core")
    s.assume("a_big", a >= 10)
    s.assume("b_small", b <= 3)
    s.assume("unused", a + b >= 0)
    s.claim(a - b >= 7)

    cert = smt.core(s, LIM).certificate
    text = leanexport.core_to_lean(cert.to_dict())

    # The sort is read off the formulas, not assumed: an integer regime
    # emitted over the reals would elaborate and say something weaker.
    assert "(a b : \u2124)" in text
    assert "a_big" in text and "b_small" in text
    assert "unused" not in text.split("## What this file does")[0]
    # It used to be `sorry` here: a core said WHICH hypotheses suffice and
    # never why. With the Farkas multipliers in the certificate it says why,
    # so the file carries a real tactic and no `sorry` at all.
    body = text.split(":= by")[1].split("/-!")[0]
    assert "sorry" not in body
    assert "linarith [a_big, b_small]" in body


def test_a_vacuous_core_states_the_regime_is_empty():
    """`h1 -> ... -> False` IS the theorem, and it is the useful one."""
    import z3

    from certo import Spec, leanexport
    from certo.engines import smt

    d = z3.Real("dens")
    s = Spec(title="empty")
    s.assume("dens_floor", d >= z3.RealVal(3) / 4)
    s.assume("sparse", d <= z3.RealVal(1) / 2)
    s.claim(z3.BoolVal(True))

    cert = smt.check(s, LIM, hypotheses_only=True).certificate
    text = leanexport.core_to_lean(cert.to_dict())
    assert "theorem regime_empty" in text
    assert ": False := by" in text
    assert "(dens : \u211d)" in text


def test_a_nonlinear_core_carries_the_smt2_rather_than_guessing():
    """Division by a variable is not linear arithmetic, and it is not faked."""
    import z3

    from certo import Spec, leanexport
    from certo.engines import smt

    d, k = z3.Reals("dens kappa")
    s = Spec(title="nonlinear")
    s.assume("dens_high", d > 1 - 1 / k)
    s.assume("kappa_large", k >= 4)
    s.assume("sparse", d <= z3.RealVal(1) / 2)
    s.claim(z3.BoolVal(True))

    cert = smt.check(s, LIM, hypotheses_only=True).certificate
    text = leanexport.core_to_lean(cert.to_dict())
    assert "declare-fun" in text            # the SMT-LIB2, verbatim
    assert "theorem from_core : True" in text
    assert "will not guess" in text


def test_export_lean_now_accepts_an_unsat_core():
    """It used to refuse, with an otherwise excellent message."""
    from certo.leanexport import EXPORTERS

    assert "unsat_core" in EXPORTERS



def test_a_core_without_multipliers_still_says_sorry_and_why():
    """Nonlinear arithmetic has no Farkas certificate to attach."""
    import z3

    from certo import Spec, leanexport
    from certo.engines import smt

    x, y = z3.Reals("x y")
    s = Spec(title="nonlinear")
    s.assume("x_pos", x > 0)
    s.assume("y_pos", y > 0)
    s.claim(x * y + 1 > 0)

    cert = smt.prove(s, LIM).certificate
    assert "multipliers" not in cert.payload
    assert cert.solver_free is False

    text = leanexport.core_to_lean(cert.to_dict())
    body = text.split(":= by")[1].split("/-!")[0]
    assert "sorry" in body
    assert not body.strip().startswith("linarith")


def test_a_linear_core_is_solver_free_and_verifies_by_arithmetic():
    """The most-used command stops producing the least-checkable certificate."""
    import z3

    from certo import Spec
    from certo.engines import smt

    x, y = z3.Reals("x y")
    s = Spec(title="linear")
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.assume("noise", x + y <= 10 ** 6)
    s.claim(x + y >= 2)

    r = smt.prove(s, LIM)
    cert = r.certificate
    assert cert.solver_free is True
    assert cert.payload["multipliers"]
    # The core is still there: `compose` reads it for the entailment check.
    assert cert.payload["core_smt2"]

    rep = verify(_roundtrip(cert), LIM)
    assert rep.ok and rep.solver_free
    assert rep.method_key == "verify.core.by_farkas"


def test_forged_multipliers_are_rejected_by_the_arithmetic():
    """The check does not trust the search that produced them."""
    import z3

    from certo import Spec
    from certo.engines import smt

    x, y = z3.Reals("x y")
    s = Spec()
    s.assume("x_ge_1", x >= 1)
    s.assume("y_ge_1", y >= 1)
    s.claim(x + y >= 2)

    d = json.loads(json.dumps(smt.prove(s, LIM).certificate.to_dict()))
    lams = d["payload"]["multipliers"]

    # Scaling every multiplier is NOT a forgery: the system is scale-free and
    # the halved vector closes just as well. Worth pinning, because a check
    # that rejected it would be wrong.
    d["payload"]["multipliers"] = [str(Fraction(x) / 2) for x in lams]
    assert verify(Certificate.from_dict(d), LIM).ok

    # Changing ONE of them is: the monomials stop cancelling.
    d["payload"]["multipliers"] = [str(Fraction(lams[0]) + 1)] + lams[1:]
    assert not verify(Certificate.from_dict(d), LIM).ok

    d["payload"]["multipliers"] = ["-1"] + lams[1:]
    rep = verify(Certificate.from_dict(d), LIM)
    assert not rep.ok
    assert any(not ok for name, ok, _ in rep.checks)



# --- deriving the dual instead of reconstructing CBC's --------------------


def test_exact_certification_no_longer_needs_a_usable_dual():
    """The headline of P1 #1: CBC's dual stops being on the critical path.

    3 of 56 exact LPs needed the rational pair injected by hand, all on
    symmetric solutions -- where several duals are optimal and CBC returns an
    arbitrary one, which need not round onto anything dual-feasible.
    """
    from certo import exact

    #   max 2x + 3y   s.t.  x + y <= 1,  x + 2y <= 1,  x, y >= 0
    # The optimum is 2 at (1, 0), where BOTH rows are tight and only one
    # variable is active: degenerate, so the dual is underdetermined.
    A, b, c = [[1, 1], [1, 2]], [1, 1], [2, 3]

    for useless in ([0.0, 0.0], [7.3, -2.1], [0.0, 1.5]):
        x, y, rep, _ = exact.certify(A, b, c, [1.0, 0.0], useless)
        assert x is not None, useless
        assert rep["ok"] and rep["objective"] == 2
        # Derived, not rounded from what was handed in.
        assert y == [Fraction(0), Fraction(2)]


def test_a_derived_dual_is_a_candidate_and_not_a_promise():
    """Nothing is trusted for where it came from: check_lp still decides."""
    from certo import exact

    A, b, c = [[1, 1], [1, 2]], [1, 1], [2, 3]
    # The first candidate complementary slackness allows here is infeasible --
    # it satisfies the active column and fails the inactive one. The search
    # has to go on rather than return it.
    first = exact.dual_from_primal(A, b, c, [Fraction(1), Fraction(0)])
    assert not exact.check_lp(A, b, c, [Fraction(1), Fraction(0)], first)["ok"]

    good = [y for y in exact.dual_candidates(A, b, c, [Fraction(1), Fraction(0)])
            if exact.check_lp(A, b, c, [Fraction(1), Fraction(0)], y)["ok"]]
    assert good == [[Fraction(0), Fraction(2)]]


def test_the_simplest_denominator_still_wins_when_reconstruction_works():
    """Pass 1 runs first, so nothing that already certified changes."""
    from certo import exact

    A, b, c = [[1, 1]], [1], [1, 1]
    x, y, _rep, denom = exact.certify(A, b, c, [0.5, 0.5], [1.0])
    # 2, not 1: rung 1 cannot express 1/2, and the FIRST rung that works is
    # the one returned -- which is the denominator worth citing.
    assert denom == 2
    assert x == [Fraction(1, 2)] * 2 and y == [Fraction(1)]


def test_solve_exact_is_rational_throughout():
    from certo import exact

    # 2x + y = 1, x - y = 1  ->  x = 2/3, y = -1/3
    sol = exact.solve_exact([[2, 1], [1, -1]], [1, 1])
    assert sol == [Fraction(2, 3), Fraction(-1, 3)]
    assert all(isinstance(v, Fraction) for v in sol)

    # inconsistent: 0 = 1 after elimination
    assert exact.solve_exact([[1, 1], [1, 1]], [1, 2]) is None

    # underdetermined: the free position is pinned to zero, which is what
    # complementary slackness wants for a row nothing forces.
    assert exact.solve_exact([[1, 1]], [2]) == [Fraction(2), Fraction(0)]


def test_a_coupled_denominator_ladder_was_never_the_problem():
    """Pinned because the backlog claimed it was, and measurement said no.

    `limit_denominator` is monotone in accuracy, so a rung high enough for the
    harder of the two values is high enough for both. Reconstructing `x` and
    `y` at independent rungs looks like a free win and buys nothing.
    """
    from certo.exact import DENOM_LADDER, reconstruct

    for xf, yf in ((1 / 3, 0.5), (1 / 7, 0.5), (2 / 7, 3 / 11)):
        want_x = Fraction(xf).limit_denominator(10 ** 6)
        want_y = Fraction(yf).limit_denominator(10 ** 6)
        shared = next((d for d in DENOM_LADDER
                       if reconstruct([xf], d) == [want_x]
                       and reconstruct([yf], d) == [want_y]), None)
        assert shared is not None, (xf, yf)



# --- eliminating a variable, with the identity that proves it -------------


def _elim(equations, eliminate, variables):
    from certo import EliminateSpec
    from certo.engines import algebra

    return algebra.eliminate(
        EliminateSpec(variables=list(variables), equations=equations,
                      eliminate=eliminate, title="t"), LIM)


def test_the_resultant_is_the_discriminant_when_it_should_be():
    """Res(f, f') = -(b^2 - 4c) for f = t^2 + bt + c. Checkable by hand."""
    import z3

    b, c, t = z3.Reals("b c t")
    r = _elim([t * t + b * t + c, 2 * t + b], "t", ["b", "c", "t"])
    assert r.verdict is Verdict.SATISFIABLE
    assert r.meta["resultant"] == "-b^2 + 4*c"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_elimination_turns_a_system_into_a_condition_on_what_is_left():
    """t^2 = s in t^3 + st + 1 gives 2st + 1, so a common root needs 4s^3 = 1."""
    import z3

    s, t = z3.Reals("s t")
    r = _elim([t ** 3 + s * t + 1, t * t - s], "t", ["s", "t"])
    assert r.meta["resultant"] == "-4*s^3 + 1"
    assert "4*s^3" in r.detail


def test_a_constant_resultant_refutes_a_common_root_over_any_field():
    import z3

    t = z3.Real("t")
    r = _elim([t * t, t * t - 1], "t", ["t"])
    assert r.verdict is Verdict.REFUTED and r.status is Status.UNSAT
    assert r.meta["case"] == "no_common_root"
    assert r.meta["resultant"] == "1"


def test_a_vanishing_resultant_means_a_shared_factor():
    import z3

    s, t = z3.Reals("s t")
    f = (t - s) * (t + 1)
    r = _elim([f, f], "t", ["s", "t"])
    assert r.meta["case"] == "common_factor"
    assert r.meta["resultant"] == "0"


def test_the_certificate_verifies_by_expanding_and_needs_no_solver():
    import z3

    s, t = z3.Reals("s t")
    r = _elim([t ** 3 + s * t + 1, t * t - s], "t", ["s", "t"])
    cert = r.certificate
    assert cert.solver_free

    rep = verify(_roundtrip(cert), LIM)
    assert rep.ok and rep.solver_free
    names = [n for n, _, _ in rep.checks]
    assert any("A*f + B*g" in n for n in names)
    # The eliminated variable is gone from the answer, which is the point.
    assert "t" not in cert.payload["resultant"]


def test_forged_cofactors_are_caught_by_the_arithmetic():
    """The identity is the whole claim, so breaking it must fail."""
    import z3

    s, t = z3.Reals("s t")
    d = json.loads(json.dumps(
        _elim([t ** 3 + s * t + 1, t * t - s], "t", ["s", "t"])
        .certificate.to_dict()))
    key = next(iter(d["payload"]["A"]))
    d["payload"]["A"][key] = str(Fraction(d["payload"]["A"][key]) + 1)
    assert not verify(Certificate.from_dict(d), LIM).ok


def test_sufficiency_is_qualified_when_both_leading_coefficients_can_vanish():
    """Res = 0 stops being enough where the leading coefficients die."""
    import z3

    s, t = z3.Reals("s t")
    # Leading coefficient in t is `s` for both: at s = 0 the degrees drop.
    r = _elim([s * t * t + 1, s * t * t + t], "t", ["s", "t"])
    cert = r.certificate
    assert cert.payload["lead_f_constant"] is False
    assert cert.payload["lead_g_constant"] is False
    rep = verify(_roundtrip(cert), LIM)
    assert rep.ok
    assert any("sufficiency is lost" in w for w in rep.warnings)


def test_three_equations_are_refused_rather_than_iterated():
    """Pairwise resultants introduce factors nothing here could certify away."""
    import z3

    s, t = z3.Reals("s t")
    r = _elim([t * t - s, t - s, t + s], "t", ["s", "t"])
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None
    assert "ideal" in r.detail


def test_a_variable_that_is_not_there_says_which_ones_are():
    import z3

    s, t = z3.Reals("s t")
    r = _elim([t * t - s, t - s], "u", ["s", "t"])
    assert r.verdict is Verdict.INCONCLUSIVE
    assert "s, t" in r.detail



# --- a bound for every parameter value, not the ones you tried ------------


def _param(dual, low=10, sense="max", rows=None):
    from certo import ParametricSpec
    from certo.polynomials import Poly

    ring = ("p",)
    P = Poly.var(ring, "p")
    K = lambda c: Poly.const(ring, c)                      # noqa: E731
    return ParametricSpec(
        parameters={"p": low}, sense=sense,
        objective={"x_big": K(1), "x_mid": K(1), "x_small": K(1)},
        constraints=rows if rows is not None else [
            ("cap_big", {"x_big": K(3), "x_mid": K(1)}, "<=",
             P * (P - K(1)) * K(Fraction(1, 2))),
            ("cap_mid", {"x_mid": K(2), "x_small": K(1)}, "<=", P - K(5)),
            ("cap_small", {"x_small": K(2)}, "<=", K(3)),
        ],
        dual=dual, title="t")


def _run(spec):
    from certo.engines import algebra

    return algebra.parametric(spec, LIM)


def test_one_dual_certifies_the_optimum_for_every_parameter_above_the_floor():
    """The whole point: a finite computation becomes a statement about a family."""
    from certo.parametric import evaluate
    from certo.polynomials import Poly

    r = _run(_param({"cap_big": Fraction(1, 3), "cap_mid": Fraction(1, 3),
                     "cap_small": Fraction(1, 3)}))
    assert r.verdict is Verdict.PROVED
    assert r.meta["bound"] == "1/6*p^2 + 1/6*p - 2/3"

    # Tight at the floor and far beyond it, against the LP solved outright.
    bound = Poly.parse(("p",), r.certificate.payload["bound"])
    for p, want in ((10, Fraction(53, 3)), (11, Fraction(64, 3)),
                    (30, Fraction(463, 3))):
        assert evaluate(bound, {"p": p}) == want, p

    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free
    assert any("says nothing below it" in w for w in rep.warnings)


def test_a_dual_that_is_infeasible_on_the_ray_yields_no_certificate():
    """The shift is sufficient, not necessary, so a failure is not a refutation."""
    r = _run(_param({"cap_big": Fraction(1, 100), "cap_mid": Fraction(0),
                     "cap_small": Fraction(0)}))
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None          # no bound, so no certificate
    assert "NOT ESTABLISHED" in r.detail
    assert r.meta["failed_columns"]


def test_a_negative_dual_entry_is_refused_outright():
    r = _run(_param({"cap_big": Fraction(1, 3), "cap_mid": Fraction(-1),
                     "cap_small": Fraction(1, 3)}))
    assert r.verdict is Verdict.INCONCLUSIVE
    assert "cap_mid" in r.detail


def test_min_problems_and_ge_rows_are_refused_rather_than_reinterpreted():
    d = {"cap_big": Fraction(1, 3), "cap_mid": Fraction(1, 3),
         "cap_small": Fraction(1, 3)}
    assert "sense=min" in _run(_param(d, sense="min")).detail

    from certo.polynomials import Poly
    ring = ("p",)
    K = lambda c: Poly.const(ring, c)                      # noqa: E731
    r = _run(_param({"only": Fraction(1)}, rows=[
        ("only", {"x_big": K(1)}, ">=", K(1))]))
    assert "only" in r.detail


def test_the_shift_is_exact_and_sufficient_not_necessary():
    """Pinned, because the gap is the honest limit of the whole command."""
    from certo.parametric import nonneg_on_ray, shift
    from certo.polynomials import Poly

    ring = ("p",)
    P = Poly.var(ring, "p")
    K = lambda c: Poly.const(ring, c)                      # noqa: E731

    # (p - 10) is non-negative on p >= 10, and the shift sees it immediately.
    ok, shifted = nonneg_on_ray(P - K(10), {"p": 10})
    assert ok and str(shifted) == "p"

    # p^2 - 3p + 3 is positive EVERYWHERE and the shift at 0 does not see it.
    ok, shifted = nonneg_on_ray(P * P - K(3) * P + K(3), {"p": 0})
    assert not ok
    # ... and shifting far enough up does.
    ok, _ = nonneg_on_ray(P * P - K(3) * P + K(3), {"p": 2})
    assert ok

    # the substitution itself is exact
    assert str(shift(P * P, {"p": 1})) == "p^2 + 2*p + 1"


def test_forging_the_bound_is_caught_by_re_expanding_it():
    r = _run(_param({"cap_big": Fraction(1, 3), "cap_mid": Fraction(1, 3),
                     "cap_small": Fraction(1, 3)}))
    d = json.loads(json.dumps(r.certificate.to_dict()))
    key = next(iter(d["payload"]["bound"]))
    d["payload"]["bound"][key] = str(Fraction(d["payload"]["bound"][key]) - 1)
    assert not verify(Certificate.from_dict(d), LIM).ok



# --- local loads: named regions the design has to respect -----------------


def _loaded(loads, caps=1):
    from certo import PackingSpec

    items = [("p{}".format(i), res, 1) for i, res in enumerate(
        [("dA0", "e01"), ("dA1", "e02"), ("dA2", "e12"),
         ("dB0", "e34"), ("dB1", "e35"), ("dB2", "e45")])]
    return PackingSpec(items=items, capacities=caps, loads=loads,
                       title="a packing with region bounds")


def _opt(spec):
    from certo.engines import lp

    return lp.opt(spec.to_lp(), LIM)


def test_a_load_is_a_row_the_dual_prices():
    """Not a post-hoc check: it constrains the optimum and shows its price."""
    free = _opt(_loaded([]))
    bound = _opt(_loaded([("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 1)]))
    assert Fraction(free.meta["objective"]) > Fraction(bound.meta["objective"])

    loads = bound.certificate.payload["loads"]
    assert [ld["name"] for ld in loads] == ["within_A"]
    assert loads[0]["binding"] is True
    # A binding region has a shadow price: relaxing it buys exactly that.
    assert Fraction(loads[0]["dual"]) > 0


def test_the_certificate_records_what_the_design_does_to_each_load():
    r = _opt(_loaded([("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2),
                      ("within_B", {"p3": 1, "p4": 1, "p5": 1}, "<=", 3)]))
    loads = {ld["name"]: ld for ld in r.certificate.payload["loads"]}
    assert loads["within_A"]["achieved"] == "2"
    assert loads["within_A"]["slack"] == "0"
    assert loads["within_B"]["achieved"] == "3"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_load_with_slack_is_reported_as_such():
    r = _opt(_loaded([("roomy", {"p0": 1}, "<=", 5)]))
    ld = r.certificate.payload["loads"][0]
    assert ld["binding"] is False
    assert Fraction(ld["slack"]) > 0
    assert Fraction(ld["dual"]) == 0          # slack means it costs nothing


def test_a_forged_load_value_is_caught_by_recomputing_it():
    """The coefficients travel, so the artefact answers on its own."""
    r = _opt(_loaded([("within_A", {"p0": 1, "p1": 1, "p2": 1}, "<=", 2)]))
    d = json.loads(json.dumps(r.certificate.to_dict()))
    d["payload"]["loads"][0]["achieved"] = "1"
    rep = verify(Certificate.from_dict(d), LIM)
    assert not rep.ok
    assert any("within_A" in name for name, ok, _ in rep.checks if not ok)


def test_loads_accept_every_sense_including_exact_preservation():
    from certo import PackingSpec

    for sense, bound, want in (("<=", 2, True), (">=", 1, True),
                               ("==", 2, True)):
        r = _opt(_loaded([("region", {"p0": 1, "p1": 1, "p2": 1},
                           sense, bound)]))
        ld = r.certificate.payload["loads"][0]
        assert ld["sense"] == sense
        assert verify(_roundtrip(r.certificate), LIM).ok is want, sense
    _ = PackingSpec


def test_a_load_on_an_item_that_is_not_there_is_refused():
    """Otherwise the row is silently weaker than intended."""
    try:
        _loaded([("oops", {"p0": 1, "ghost": 1}, "<=", 1)])
    except ValueError as e:
        assert "ghost" in str(e)
    else:
        raise AssertionError("a weight on a missing item was accepted")


def test_a_load_may_not_take_a_resource_name():
    try:
        _loaded([("e01", {"p0": 1}, "<=", 1)]).to_lp()
    except ValueError as e:
        assert "e01" in str(e)
    else:
        raise AssertionError("a load shadowed a resource row")


def test_a_packing_with_no_loads_carries_an_empty_list():
    """The field is optional, and its absence must not change anything."""
    r = _opt(_loaded([]))
    assert r.certificate.payload["loads"] == []
    assert verify(_roundtrip(r.certificate), LIM).ok



# --- exact covers, and clique partitions as one case ----------------------


FANO = [(0, 1, 3), (1, 2, 4), (2, 3, 5), (3, 4, 6),
        (4, 5, 0), (5, 6, 1), (6, 0, 2)]


def _cover(universe, parts, **kw):
    from certo import CoverSpec
    from certo.engines import algebra

    return algebra.cover(CoverSpec(universe=universe, parts=parts,
                                   title="t", **kw), LIM)


def _complete_pairs(n):
    import itertools

    return list(itertools.combinations(range(n), 2))


def test_the_fano_plane_partitions_k7_into_seven_triangles():
    """Tight and checkable by hand: 21 edges, 7 parts, 3 edges each."""
    r = _cover(_complete_pairs(7), FANO, cliques=True, max_size=3)
    assert r.verdict is Verdict.PROVED
    assert r.meta == {"parts": 7, "universe": 21, "missed": 0, "doubled": 0}

    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok and rep.solver_free
    assert any("really is a clique" in name for name, _, _ in rep.checks)
    # It is an upper bound and says so.
    assert any("does not say it is the smallest" in w for w in rep.warnings)


def test_an_edge_covered_twice_is_refuted_not_accepted():
    r = _cover(_complete_pairs(7), FANO + [(0, 1, 3)], cliques=True)
    assert r.verdict is Verdict.REFUTED
    assert r.meta["doubled"] == 3            # the three edges of that triangle
    assert r.certificate is None
    assert "exact=False" in r.detail          # and what would make it valid


def test_an_uncovered_edge_is_named():
    r = _cover(_complete_pairs(7), FANO[:-1], cliques=True)
    assert r.verdict is Verdict.REFUTED
    assert r.meta["missed"] == 3


def test_a_part_that_is_not_a_clique_stops_before_any_certificate():
    """A statement about the graph, not about the cover."""
    edges = [e for e in _complete_pairs(7) if e != (0, 1)]
    r = _cover(edges, FANO, cliques=True)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.certificate is None
    assert "not a clique" in r.detail and "(0, 1)" in r.detail


def test_at_least_covers_are_a_different_claim_and_recorded_as_one():
    r = _cover(_complete_pairs(7), FANO + [(0, 1, 3)], cliques=True, exact=False)
    assert r.verdict is Verdict.PROVED
    assert r.certificate.payload["exact"] is False
    rep = verify(_roundtrip(r.certificate), LIM)
    assert rep.ok
    # The stronger claim is simply not made, and the wording says which.
    assert "at least once" in rep.detail


def test_a_generic_exact_cover_needs_no_graph_at_all():
    r = _cover(["a", "b", "c", "d"], [["a", "c"], ["b", "d"]])
    assert r.verdict is Verdict.PROVED
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_parts_covering_something_outside_the_universe_are_caught():
    """Otherwise the cover is of a different object than the one declared."""
    r = _cover(["a", "b"], [["a", "b"], ["z"]])
    assert r.verdict is Verdict.REFUTED
    assert "not in the universe" in r.detail


def test_a_repeated_universe_element_is_refused_outright():
    """'Exactly once' would not mean anything."""
    r = _cover(["a", "a", "b"], [["a", "b"]])
    assert r.verdict is Verdict.INCONCLUSIVE
    assert "repeats" in r.detail


def test_forging_the_part_count_is_caught_by_recounting():
    r = _cover(_complete_pairs(7), FANO, cliques=True)
    d = json.loads(json.dumps(r.certificate.to_dict()))
    d["payload"]["size"] = 5
    rep = verify(Certificate.from_dict(d), LIM)
    assert not rep.ok


def test_a_forged_part_is_caught_by_re_deriving_its_edges():
    """The clique check is redone from the graph, not read off the payload."""
    r = _cover(_complete_pairs(7), FANO, cliques=True)
    d = json.loads(json.dumps(r.certificate.to_dict()))
    d["payload"]["part_report"][0]["vertices"] = ["0", "1", "3", "5"]
    assert not verify(Certificate.from_dict(d), LIM).ok



# --- 0.6 defects, each pinned by the case that found it -------------------


def _mixed_with(sense_row, all_discrete=True):
    from certo import LPSpec
    from certo.engines import mixed

    lp = LPSpec(sense="max", title="t")
    lp.variable("a", 0, 1, kind="binary")
    lp.variable("b", 0, 1, kind="binary")
    if not all_discrete:
        lp.variable("w", 0, None)
    lp.objective({"a": 3, "b": 2, **({} if all_discrete else {"w": 1})})
    lp.constraint({"a": 1, "b": 1}, "<=", 1, name="cap")
    lp.constraint({"a": 1, "b": 1}, sense_row, 1, name="quota")
    if not all_discrete:
        lp.constraint({"w": 6}, "<=", 1, name="w_cap")
    return mixed.mixed(lp, LIM)


def test_a_mixed_certificate_survives_a_ge_or_eq_row():
    """The 0.6 P0. Reported as "all variables discrete"; the trigger was the
    row SENSE, and it bit mixed models too.

    `as_leq_system` renames a `>=` row to `name_geq` and negates it, and
    splits an `==` into `name_le` and `name_ge`. The equivalence check looked
    up the ORIGINAL name in a table keyed by the normalised ones, missed, and
    called a perfectly good certificate invalid.
    """
    for sense in ("<=", ">=", "=="):
        for all_discrete in (True, False):
            r = _mixed_with(sense, all_discrete)
            assert r.certificate is not None, (sense, all_discrete)
            rep = verify(_roundtrip(r.certificate), LIM)
            assert rep.ok, (sense, all_discrete,
                            [c for c in rep.checks if not c[1]])


def test_normalised_rows_is_the_one_place_that_mapping_lives():
    from certo.certificate import normalised_rows

    assert normalised_rows("q", "<=") == [("q", 1)]
    assert normalised_rows("q", ">=") == [("q_geq", -1)]
    assert normalised_rows("q", "==") == [("q_le", 1), ("q_ge", -1)]


def test_a_ge_load_reports_the_shadow_price_it_actually_has():
    """The 0.6 P1: the row is renamed, the reporter looked up the old name,
    and a quota that was costing you showed a price of zero."""
    from certo import PackingSpec
    from certo.engines import lp

    # cheap A-items and valuable B-items compete for the same resources, so a
    # quota forcing A costs you B -- and the price says how much.
    spec = PackingSpec(
        items=[("a0", ("s0",), 1), ("a1", ("s1",), 1),
               ("b0", ("s0",), 5), ("b1", ("s1",), 5)],
        capacities=1,
        loads=[("quota_A", {"a0": 1, "a1": 1}, ">=", 2)])
    r = lp.opt(spec.to_lp(), LIM)
    ld = r.certificate.payload["loads"][0]

    assert ld["binding"] is True
    assert ld["rows"] == ["quota_A_geq"]
    # Forcing one more A means dropping one B: 1 gained, 5 lost.
    assert Fraction(ld["dual"]) == -4
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_branch_and_bound_accepts_a_minimisation_and_keeps_the_sign():
    """Refusing it left the user negating by hand, and their certificate then
    described a formulation nobody posed."""
    from certo import LPSpec
    from certo.engines import bb

    lp_spec = LPSpec(sense="min", title="set cover")
    for v in ("a", "b", "c"):
        lp_spec.variable(v, 0, 1, kind="binary")
    lp_spec.objective({"a": 2, "b": 3, "c": 4})
    lp_spec.constraint({"a": 1, "b": 1}, ">=", 1, name="cover1")
    lp_spec.constraint({"b": 1, "c": 1}, ">=", 1, name="cover2")

    r = bb.prove_optimal(lp_spec, LIM)
    assert r.verdict is Verdict.PROVED
    assert r.meta["optimum"] == "3"          # b alone covers both
    assert r.meta["minimising"] is True

    p = r.certificate.payload
    # Both formulations, because the tree really did search the negated one.
    assert p["sense"] == "max" and p["original_sense"] == "min"
    assert p["incumbent"] == "-3" and p["original_optimum"] == "3"
    assert verify(_roundtrip(r.certificate), LIM).ok


def test_a_stopped_search_says_what_it_knows_instead_of_nothing():
    """INCONCLUSIVE with no incumbent, bound or gap made an instance a hole."""
    from certo import PackingSpec
    from certo.engines import bb

    # A 5-cycle: the matching relaxation is half-integral (5/2) and the
    # integer answer is 2, so the search really does have to branch.
    items = [("e{}".format(i), ("v{}".format(i), "v{}".format((i + 1) % 5)), 1)
             for i in range(5)]
    spec = PackingSpec(items=items, capacities=1, integer=True).to_lp()

    r = bb.prove_optimal(spec, LIM, max_nodes=1)
    assert r.verdict is Verdict.INCONCLUSIVE
    assert r.status is Status.RESOURCE_EXHAUSTED
    assert r.certificate is None              # optimality is NOT established
    assert r.meta["stopped"] is True
    # All four things a stopped search knows, and the gap is real.
    assert r.meta["incumbent"] == "2"
    assert r.meta["best_bound"] == "5/2"
    assert r.meta["gap"] == "1/2"
    assert r.meta["nodes_opened"] == 1
    assert "NOT established" in r.detail

    # And with room, the same instance proves it.
    full = bb.prove_optimal(spec, LIM, max_nodes=500)
    assert full.verdict is Verdict.PROVED and full.meta["optimum"] == "2"


def test_self_check_refuses_to_report_a_certificate_verify_rejects():
    """The fix that would have caught both P0s before anyone ran verify."""
    import argparse

    from certo import cli

    r = _mixed_with(">=")
    args = argparse.Namespace(
        json=False, cert=None, log=None, note="", tag=None, spec=None,
        self_check=True, timeout_ms=20_000, rlimit=20_000_000,
        max_memory_mb=2048, seed=0)
    assert cli._self_check(r, args) is True
    assert r.meta["self_check"] == "ok"

    # A certificate that has been tampered with must not pass.
    r.certificate.payload["achieved"] = "999"
    r.meta.pop("self_check", None)
    assert cli._self_check(r, args) is False
    assert r.meta["self_check"] == "FAILED"



# --- discovery: a command that shipped and nobody found -------------------


def test_order_answers_to_the_words_people_actually_type():
    """`order` shipped in 0.5.0 and its user searched for "asymptotic"."""
    from certo.cli import build_parser

    choices = None
    for action in build_parser()._actions:
        if getattr(action, "dest", "") == "cmd" and action.choices:
            choices = action.choices
    assert "order" in choices
    for word in ("asymptotics", "decays"):
        assert word in choices, word
        # An alias is the same parser, not a copy that can drift.
        assert choices[word] is choices["order"]


def test_the_help_line_leads_with_the_question_not_the_machinery():
    from certo.cli import build_parser

    for action in build_parser()._actions:
        if getattr(action, "dest", "") == "cmd" and action.choices:
            helptext = action._choices_actions
    line = next(a.help for a in helptext if a.dest == "order")
    assert "DECAY" in line and "asymptotic" in line


def test_the_question_table_is_available_in_the_terminal():
    """It lived only in the README, which is not where somebody is stuck."""
    from certo.cli import BY_QUESTION
    from certo.i18n import t

    commands = {c for _, rows in BY_QUESTION for _, c in rows}
    assert "order" in commands
    # Every label resolves in both languages, or the table prints raw keys.
    for group, rows in BY_QUESTION:
        assert not t(group).startswith("commands."), group
        for question, _ in rows:
            assert not t(question).startswith("commands."), question


def test_lint_names_order_when_the_claim_divides_by_a_product():
    """The precise trigger, on the expression that cost a user three sessions."""
    import z3

    from certo.lint import _magnitude_shaped

    k, W, C, u, d, p = z3.Reals("k W C u d p")
    hit = _magnitude_shaped(5 * k * W * C * C / (u ** 3 * d ** 2 * p ** 10))
    assert hit == ["d", "p", "u"]

    # And it stays quiet where it would be noise. One symbol downstairs is
    # far too common to mean anything.
    x, y, z = z3.Reals("x y z")
    assert _magnitude_shaped(x + y) is None
    assert _magnitude_shaped(x / y) is None
    assert _magnitude_shaped(x * y * z) is None
    assert _magnitude_shaped((x + y) / z) is None
    assert _magnitude_shaped(x / (y * z)) == ["y", "z"]


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
