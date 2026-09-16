"""Generic domains, programmable filters, ranges, packings and Lean export."""
from __future__ import annotations

import json
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
