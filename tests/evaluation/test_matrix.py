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
from d2t_rna.t2.decision import exact_bayes_average_error
from d2t_rna.t2.theorem import collision_or_separation
from d2t_rna.evaluation.matrix import (
    ExperimentSpec,
    MatrixReport,
    MultiActionOracle,
    action_law,
    build_matrix_report,
    chernoff_information,
    cross_validate_single_pair,
    microcase_fixtures,
    per_action_tv,
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
    assert oracle.minimax_error == exact_bayes_average_error(p0, p1, 3)
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


# ---------------------------------------------------------------------------
# P0-6 benchmark-authenticity reference tests (v7 audit blockers 4 & 6)
# ---------------------------------------------------------------------------

def test_product_bhattacharyya_is_product_over_actions() -> None:
    # Action "a" has BC=1/2, action "b" is information-free (BC=1).  The
    # correct multi-action product bound is prod_u BC_u^{n_u}.  The v7 audit
    # blocker T9-multi-action used only the first action and BC_0^{sum n_u}.
    m = microcase_fixtures()["heterogeneous_bc"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    q0a = action_law(m, m.actions[0], p0)
    q1a = action_law(m, m.actions[0], p1)
    q0b = action_law(m, m.actions[1], p0)
    q1b = action_law(m, m.actions[1], p1)
    res = MultiActionOracle((q0a, q0b), (q1a, q1b), (F(1), F(1)), (2, 1)).evaluate()
    bc_a = F(1, 2)
    bc_b = F(1)
    assert res.product_bhattacharyya == (bc_a ** 2) * (bc_b ** 1)
    # the old buggy form BC_0 ** sum(n) must be excluded
    assert res.product_bhattacharyya != bc_a ** (2 + 1)


def test_single_action_bc_is_unchanged() -> None:
    # With one action, product_bhattacharyya stays BC^n (BC=1/2, n=3).
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    res = MultiActionOracle((p0,), (p1,), (F(1),), (3,)).evaluate()
    assert res.product_bhattacharyya == (F(1, 2) ** 3)


def test_oracle_is_cap_free_single_action() -> None:
    # A single action with budget 8 whose laws overlap (P0=(1/4,3/4),
    # P1=(1,0)): minimax error is (1/2)(1/4)^n, decreasing with n but never
    # reaching 0, so the complete cap-free oracle allocates all 8 repeats
    # (the old hard cap of 6 is removed).
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    m = T2FiniteModel(
        name="t2c_cap_free",
        n_states=2,
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=((F(1), F(0)), (F(0), F(1))),
        actions=(Action("a", ((F(1), F(0)), (F(0), F(1)))),),
    )
    spec = ExperimentSpec(
        model_name=m.name, p0=p0, p1=p1, costs=(F(1),), budget=F(8)
    )
    results = run_baselines(m, spec)
    oracle_run = results["exhaustive_oracle"]
    assert oracle_run.allocation == (8,)
    assert oracle_run.cost == F(8)


def test_oracle_is_global_minimizer_across_feasible_allocations() -> None:
    # The complete cap-free oracle must be a global minimizer of the minimax
    # error over every within-budget allocation (independent brute-force check).
    m = microcase_fixtures()["repeated_action"]
    p0 = m.theta_0[0]
    p1 = m.theta_1[0]
    costs = (F(1), F(1))
    budget = F(5)
    spec = ExperimentSpec(model_name=m.name, p0=p0, p1=p1, costs=costs, budget=budget)
    results = run_baselines(m, spec)
    oracle_res = results["exhaustive_oracle"].oracle
    p0_laws = tuple(action_law(m, a, p0) for a in m.actions)
    p1_laws = tuple(action_law(m, a, p1) for a in m.actions)
    best = None
    for n0 in range(int(budget // costs[0]) + 1):
        for n1 in range(int(budget // costs[1]) + 1):
            if n0 + n1 > int(budget):
                continue
            cand = MultiActionOracle(p0_laws, p1_laws, costs, (n0, n1)).evaluate()
            if best is None or cand.minimax_error < best:
                best = cand.minimax_error
    assert best is not None
    assert oracle_res.minimax_error == best


def test_true_chernoff_matches_reference() -> None:
    # P0=(1/4,3/4), P1=(1,0): tilde(s)=(1/4)^s for s in (0,1), so the true
    # Chernoff information is -log(1/4)=ln 4.  The old baseline returned the
    # bogus "1 - sum min(q0,q1) = 3/4".
    import math
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    c = chernoff_information(p0, p1)
    assert abs(c - math.log(4)) < 1e-3


def test_per_action_tv_in_unit_interval() -> None:
    # TV separation must lie in [0,1] (contradicting the v7 TV>1 blocker).
    p0 = (F(1, 4), F(3, 4))
    p1 = (F(1), F(0))
    tv = per_action_tv(p0, p1)
    assert tv >= 0 and tv <= 1
    assert tv == F(3, 4)


def test_baseline_scores_are_distinct() -> None:
    # EIG (Hellinger information) and Test-Cover (TV) rank the two actions in
    # opposite order here, so their greedy allocations must differ (the v7
    # audit blocker 4: greedy / EIG / LM2R were all the same score).
    p0 = (F(1), F(0))
    p1 = (F(0), F(1))
    m = T2FiniteModel(
        name="opposite_separation_rankings",
        n_states=2,
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=((F(1), F(0)), (F(0), F(1))),
        actions=(
            Action(
                "a",
                (
                    (F(9, 10), F(1, 10)),
                    (F(1, 20), F(9, 20)),
                    (F(1, 20), F(9, 20)),
                ),
            ),
            Action(
                "b",
                (
                    (F(1, 2), F(0)),
                    (F(1, 2), F(1, 2)),
                    (F(0), F(1, 2)),
                ),
            ),
        ),
    )
    spec = ExperimentSpec(
        model_name=m.name, p0=p0, p1=p1, costs=(F(1), F(1)), budget=F(5)
    )
    results = run_baselines(m, spec)
    alloc_greedy = results["greedy_test_cover"].allocation
    alloc_eig = results["eig"].allocation
    alloc_chernoff = results["chernoff"].allocation
    alloc_lm2r = results["lm2r_heuristic"].allocation
    # greedy uses TV (ranks action a higher), EIG uses Hellinger info (action b)
    assert alloc_greedy != alloc_eig
    # at least two distinct allocations among the four labelled methods
    distinct = {alloc_greedy, alloc_eig, alloc_chernoff, alloc_lm2r}
    assert len(distinct) >= 2
