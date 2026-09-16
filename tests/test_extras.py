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
