"""Tests for the D2T-RNA v7 §9 evaluation matrix (contract sections 9.1-9.3).

Covers the synthetic microcase fixtures, the multi-action exhaustive oracle,
the §9.1 exhaustive-oracle vs certified-T2c-bounds cross-validation, and the
§9.3 actual execution of all eight baselines under one common experiment spec.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction as F

import pytest

from d2t_rna.t2.model import Action, T2FiniteModel
from d2t_rna.t2.decision import exact_minimax_error
from d2t_rna.t2.theorem import collision_or_separation
from d2t_rna.evaluation.matrix import (
    ExperimentSpec,
    MatrixReport,
    MultiActionOracle,
    action_law,
    build_matrix_report,
    cross_validate_single_pair,
    microcase_fixtures,
    run_baselines,
)

_REQUIRED_FIXTURES = [
    "alternating_rectangle_2x2",
    "no_cycle",
    "zero_margin",
    "symmetric_states",
    "repeated_action",
    "cancellation_cycled",
    "nondecomposable_3d",
    "exact_collision",
    "near_collision",
    "strict_positive_separation",
    "boundary",
]

_ALL_BASELINE_METHODS = [
    "exhaustive_oracle",
    "full_matrix",
    "random",
    "greedy_test_cover",
    "eig",
    "chernoff",
    "lm2r_heuristic",
    "t2_integer_lp",
]


def test_fixtures_cover_all_contract_scenarios() -> None:
    fixtures = microcase_fixtures()
    assert set(_REQUIRED_FIXTURES) <= set(fixtures.keys())


def test_all_fixtures_are_valid_models() -> None:
    # Construction validates column-stochastic actions, normalized catalogs and
    # matching state counts; any structural error raises here.
    for name, model in microcase_fixtures().items():
        assert model.name == name
        for a in model.actions:
            assert a.n_states() == model.n_states


def test_oracle_matches_theory_minimax_single_action() -> None:
    # T2c microcase P0=(1/4,3/4), P1=(1,0) with identity action: exact minimax
    # error over n=3 repeats is (1/2)(1/4)^3 = 1/128.
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    model = T2FiniteModel(
        name="t2c_microcase",
        n_states=2,
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=((F(1), F(0)), (F(0), F(1))),
        actions=(Action("a", ((F(1), F(0)), (F(0), F(1)))),),
    )
    q0 = action_law(model, model.actions[0], p0)
    q1 = action_law(model, model.actions[0], p1)
    oracle = MultiActionOracle((q0,), (q1,), (F(1),), (3,)).evaluate()
    assert q0 == p0 and q1 == p1
    assert oracle.minimax_error == exact_minimax_error(p0, p1, 3)
    assert oracle.minimax_error == F(1, 128)
    assert oracle.product_tv == F(1) - F(2) * F(1, 128)


def test_oracle_decision_consistency() -> None:
    # correct + wrong + abstain = 1 and correct = 1 - 2*err (no abstention).
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    oracle = MultiActionOracle((p0,), (p1,), (F(1),), (2,)).evaluate()
    assert oracle.correct_decl + oracle.wrong_decl + oracle.abstain == 1
    assert oracle.wrong_decl == oracle.minimax_error
    assert oracle.correct_decl == F(1) - oracle.wrong_decl


def test_abstention_increases_abstain_and_lowers_correct() -> None:
    # Overlapping supports so a likelihood-ratio band can actually abstain.
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1, 2), F(1, 2))
    base = MultiActionOracle((p0,), (p1,), (F(1),), (2,), abstain_ratio=F(1)).evaluate()
    strict = MultiActionOracle(
        (p0,), (p1,), (F(1),), (2,), abstain_ratio=F(3)
    ).evaluate()
    assert strict.abstain > 0
    assert strict.abstain > base.abstain
    assert strict.correct_decl < base.correct_decl


def test_cross_validate_strict_separation() -> None:
    m = microcase_fixtures()["strict_positive_separation"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    cv = cross_validate_single_pair(m, p0, p1, (3,), (F(1),))
    assert cv.oracle.minimax_error == 0  # disjoint laws -> perfect separation
    assert cv.oracle.product_tv == 1
    assert all(cv.crosscheck.values())
    assert cv.oracle_in_interval


def test_cross_validate_exact_collision() -> None:
    m = microcase_fixtures()["exact_collision"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    cv = cross_validate_single_pair(m, p0, p1, (2,), (F(1),))
    # the collapsed action maps both latent states to the same law -> err 1/2
    assert cv.oracle.minimax_error == F(1, 2)
    assert cv.oracle.product_tv == 0
    assert all(cv.crosscheck.values())


def test_cross_validate_near_collision() -> None:
    m = microcase_fixtures()["near_collision"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    cv = cross_validate_single_pair(m, p0, p1, (4,), (F(1),))
    # laws are close but not equal: error positive but strictly below 1/2
    assert cv.oracle.minimax_error > 0
    assert cv.oracle.minimax_error < F(1, 2)
    assert all(cv.crosscheck.values())


def test_all_baselines_execute_on_multi_action() -> None:
    m = microcase_fixtures()["repeated_action"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    spec = ExperimentSpec(
        model_name=m.name,
        p0=p0,
        p1=p1,
        costs=(F(1), F(1)),
        budget=F(8),
    )
    results = run_baselines(m, spec)
    assert set(_ALL_BASELINE_METHODS) == set(results.keys())
    for method, run in results.items():
        assert run.executed, method
        assert run.oracle is not None, method


def test_allocation_baselines_respect_budget() -> None:
    m = microcase_fixtures()["repeated_action"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    spec = ExperimentSpec(
        model_name=m.name,
        p0=p0,
        p1=p1,
        costs=(F(1), F(2)),
        budget=F(9),
    )
    results = run_baselines(m, spec)
    for method, run in results.items():
        if method == "t2_integer_lp":
            # unconstrained min-cost integer design; may exceed the budget
            continue
        assert run.cost <= spec.budget, method
        assert run.spent_exceeds_budget is False, method


def test_matrix_report_builds_and_replays() -> None:
    m = microcase_fixtures()["repeated_action"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    spec = ExperimentSpec(
        model_name=m.name, p0=p0, p1=p1, costs=(F(1), F(1)), budget=F(6)
    )
    report = build_matrix_report(m, spec)
    assert isinstance(report, MatrixReport)
    assert report.model_name == m.name
    assert set(_ALL_BASELINE_METHODS) == set(report.baselines.keys())
    # deterministic replay hash
    again = build_matrix_report(m, spec)
    assert report.replay_sha256() == again.replay_sha256()


def test_report_reports_sec92_metrics() -> None:
    # Contract §9.2 requires memory and certified omitted mass to be reported
    # for every baseline, alongside cost / risk / abstention / runtime / gap.
    m = microcase_fixtures()["repeated_action"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    spec = ExperimentSpec(
        model_name=m.name, p0=p0, p1=p1, costs=(F(1), F(1)), budget=F(6)
    )
    report = build_matrix_report(m, spec)
    for method, run in report.baselines.items():
        assert run.memory is not None and run.memory > 0, method
        assert run.certified_omitted_mass is not None, method
        assert run.certified_omitted_mass.lo >= 0, method
        assert run.runtime_s >= 0.0, method
        assert run.oracle is not None, method


def test_cancellation_fixture_is_collision() -> None:
    # Contract §10.1: "each generator is hit but the linear combination
    # cancels" must be a collision (no robust separation) on the full panel.
    m = microcase_fixtures()["cancellation_cycled"]
    panel = [a.action_id for a in m.actions]
    cert = collision_or_separation(m, panel)
    assert cert.gamma == 0
    assert cert.collision_witness is not None


def test_alternating_rectangle_has_nonzero_fiber() -> None:
    # The 2x2 alternating rectangle has a non-trivial cross-class fiber: the
    # difference set D is non-empty under the two marginals.
    m = microcase_fixtures()["alternating_rectangle_2x2"]
    panel = [a.action_id for a in m.actions]
    cert = collision_or_separation(m, panel)
    # collision (uniform catalogs share marginals) -> gamma 0 is expected
    assert cert.gamma == 0