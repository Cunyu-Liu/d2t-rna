"""P0-7 Track R/C frozen decision registry tests.

Covers the fail-closed method-role consumer guard and the frozen primary /
endpoint / strongest-comparator / success registry:

  (a) an oracle row fed into a ranking/CI/superiority/Pareto consumer fails;
  (b) a missing cost-cap field returns TRACK_C_COST_CAP_NOT_REGISTERED;
  (c) an unidentifiable endpoint returns TRACK_C_ENDPOINT_NOT_IDENTIFIABLE;
  (d) no eligible comparator returns MATCHED_COMPARATOR_NOT_IDENTIFIED;
  (e) a WITHHELD method is not aliased to a solution;
  (f) cost_cap_hash is deterministic; primary switch requires a signed record;
  (g) Track C success criterion (descriptive-only below the CI floor, GO when
      median >= 10% and one-sided 95% lower CI > 0).
"""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from d2t_rna.evaluation import method_role as MR
from d2t_rna.evaluation import track_registry as TR
from d2t_rna.evaluation.track_registry import (
    MATCHED_COMPARATOR_NOT_IDENTIFIED,
    TRACK_C_COST_CAP_NOT_REGISTERED,
    TRACK_C_ENDPOINT_NOT_IDENTIFIABLE,
    TrackCCostCapNotRegistered,
    TrackCEndpointNotIdentifiable,
    TrackCPrimaryNotSwitchable,
    MatchedComparatorNotIdentified,
    WithheldAliasError,
)
from d2t_rna.evaluation.method_role import OracleRankingError


# ---------------------------------------------------------------------------
# (a) oracle ranking consumer must fail closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("claim", ["win", "tie", "worse", "ci", "confidence",
                                   "superiority", "pareto", "strict_improvement",
                                   "dominated"])
def test_oracle_ranking_consumer_fails(claim):
    with pytest.raises(OracleRankingError):
        MR.evaluate_method_role("INDEPENDENT_ORACLE_EXACT", claim)


@pytest.mark.parametrize("claim", ["regret", "gap", "ground_truth", "containment"])
def test_oracle_regret_gap_allowed(claim):
    # regret/gap/ground-truth reporting on an oracle row is permitted
    role = MR.evaluate_method_role("exhaustive_oracle", claim)
    assert role is MR.MethodRole.ORACLE


def test_non_oracle_consumer_is_noop():
    # a comparator row is rankable; the guard must not fire
    role = MR.evaluate_method_role("chernoff", "win")
    assert role is MR.MethodRole.COMPARATOR
    MR.assert_no_oracle_ranking(MR.MethodRole.DEPLOYABLE, "superiority")


# ---------------------------------------------------------------------------
# (b) missing cost-cap field -> TRACK_C_COST_CAP_NOT_REGISTERED
# ---------------------------------------------------------------------------


def test_missing_cost_cap_field_returns_not_registered():
    bad = dict(TR.FROZEN_PRIMARY_DECISION)
    del bad["cost_unit"]
    with pytest.raises(TrackCCostCapNotRegistered) as ei:
        TR.primary_decision(bad)
    assert ei.value.status == TRACK_C_COST_CAP_NOT_REGISTERED


def test_missing_any_canonical_field_fails():
    for field in ("max_registered_cost", "cost_scale", "cost_cap_source",
                  "track_primary"):
        bad = dict(TR.FROZEN_PRIMARY_DECISION)
        bad[field] = None
        with pytest.raises(TrackCCostCapNotRegistered):
            TR.canonical_primary_payload(bad)


# ---------------------------------------------------------------------------
# (c) endpoint not identifiable -> TRACK_C_ENDPOINT_NOT_IDENTIFIABLE
# ---------------------------------------------------------------------------


def test_endpoint_not_identifiable_returns_sentinel():
    # all families stuck far above every grid threshold
    families = [
        {"family_id": f"f{i}", "minimax_at_max_cost": F(1, 2)} for i in range(10)
    ]
    with pytest.raises(TrackCEndpointNotIdentifiable) as ei:
        TR.determine_track_c_endpoint(families)
    assert ei.value.status == TRACK_C_ENDPOINT_NOT_IDENTIFIABLE


def test_endpoint_identifies_smallest_threshold():
    # 16/20 families <= 0.10 -> endpoint must be the smallest threshold at 80%
    fams = []
    for i in range(16):
        fams.append({"family_id": f"reach_{i}", "minimax_at_max_cost": F(1, 10)})
    for i in range(4):
        fams.append({"family_id": f"miss_{i}", "minimax_at_max_cost": F(1, 5)})
    res = TR.determine_track_c_endpoint(fams)
    assert res["status"] == "IDENTIFIED"
    assert F(res["endpoint"]) == F(1, 10)
    # 0.05 must have been below the 80% requirement
    t005 = res["per_threshold"][0]
    assert t005["n_families_reach"] < 16


def test_empty_development_is_not_identifiable():
    with pytest.raises(TrackCEndpointNotIdentifiable):
        TR.determine_track_c_endpoint([])


# ---------------------------------------------------------------------------
# (d) no comparator -> MATCHED_COMPARATOR_NOT_IDENTIFIED
# ---------------------------------------------------------------------------


def test_no_comparator_returns_matched_not_identified():
    cands = [
        {"method_id": "chernoff", "task_reduction": True, "toy_parity": True,
         "coverage": 0.5, "reaches_endpoint": True,
         "family_cluster_mean_cost": 8.0},
        {"method_id": "eig", "task_reduction": True, "toy_parity": False,
         "coverage": 0.95, "reaches_endpoint": True,
         "family_cluster_mean_cost": 8.0},
    ]
    with pytest.raises(MatchedComparatorNotIdentified) as ei:
        TR.determine_strongest_comparator(cands, F(1, 10))
    assert ei.value.status == MATCHED_COMPARATOR_NOT_IDENTIFIED


def test_strongest_comparator_picks_lowest_cost_and_tie_set():
    cands = [
        {"method_id": "A", "task_reduction": True, "toy_parity": True,
         "coverage": 0.95, "reaches_endpoint": True,
         "family_cluster_mean_cost": 6.0},
        {"method_id": "B", "task_reduction": True, "toy_parity": True,
         "coverage": 0.93, "reaches_endpoint": True,
         "family_cluster_mean_cost": 6.0},
        {"method_id": "C", "task_reduction": True, "toy_parity": True,
         "coverage": 0.95, "reaches_endpoint": True,
         "family_cluster_mean_cost": 8.0},
    ]
    res = TR.determine_strongest_comparator(cands, F(1, 10))
    assert res["strongest_comparator"] == "A"
    assert set(res["co_strongest_set"]) == {"A", "B"}  # tie within 1e-12


# ---------------------------------------------------------------------------
# (e) WITHHELD must not be aliased to a solution
# ---------------------------------------------------------------------------


def test_withheld_not_aliased_to_solution():
    with pytest.raises(WithheldAliasError):
        TR.assert_withheld_not_aliased(
            method_id="some_method",
            status=TR.WITHHELD_STATUS,
            reported_allocation=[0, 1],
            claimed_solution_label="T2",
        )


def test_computed_method_can_be_claimed():
    # a COMPUTED (non-withheld) deployable may carry the solution label
    TR.assert_withheld_not_aliased(
        method_id="d2t", status="COMPUTED",
        reported_allocation=[1, 1], claimed_solution_label="D2T",
    )


def test_withheld_trace_without_solution_label_ok():
    # a WITHHELD record reporting a diagnostic allocation (no solution label) is
    # not an alias
    TR.assert_withheld_not_aliased(
        method_id="m", status=TR.WITHHELD_STATUS,
        reported_allocation=[0, 1],
    )


# ---------------------------------------------------------------------------
# (f) cost_cap_hash deterministic + signed switch guard
# ---------------------------------------------------------------------------


def test_cost_cap_hash_deterministic():
    a = TR.cost_cap_hash()
    b = TR.cost_cap_hash()
    assert a == b
    assert len(a) == 64
    pd = TR.primary_decision()
    assert pd["cost_cap_hash"] == a


def test_track_c_is_frozen_primary():
    pd = TR.primary_decision()
    assert pd["track_primary"] == TR.TRACK_C
    assert pd["primary_decision"]["max_registered_cost"] == 8


def test_primary_switch_to_track_r_requires_signed_record():
    with pytest.raises(TrackCPrimaryNotSwitchable):
        TR.require_track_r_switch_decision(None)
    with pytest.raises(TrackCPrimaryNotSwitchable):
        TR.require_track_r_switch_decision({"signer": "", "primary": TR.TRACK_R})
    with pytest.raises(TrackCPrimaryNotSwitchable):
        TR.require_track_r_switch_decision({"signer": "ext", "primary": TR.TRACK_C})
    # a properly signed Track R decision is accepted
    TR.require_track_r_switch_decision(
        {"signer": "external-independent", "primary": TR.TRACK_R,
         "tree": "abc123"}
    )


# ---------------------------------------------------------------------------
# (g) Track C success criterion
# ---------------------------------------------------------------------------


def test_success_descriptive_only_too_few_families():
    # 3 families < the CI floor of 5 -> descriptive only, no GO
    res = TR.track_c_success(
        [F(1), F(1), F(1)],
        [F(2), F(2), F(2)],
    )
    assert res["status"] == "DESCRIPTIVE_ONLY"
    assert res["go"] is False
    assert res["ci_defined"] is False


def test_success_go_when_median_and_ci_satisfied():
    # 20 families each with 50% cost reduction -> median 50% >= 10%, CI > 0
    d2t = [F(1) for _ in range(20)]
    comp = [F(2) for _ in range(20)]
    res = TR.track_c_success(d2t, comp, n_boot=2000)
    assert res["status"] == "GO"
    assert res["go"] is True
    assert res["median_ok_ge_0.10"] is True
    assert res["ci_ok_gt_0"] is True


def test_success_not_go_when_median_below_10pct():
    # tiny reductions -> median below 10%
    d2t = [F(99, 100) for _ in range(20)]
    comp = [F(100, 100) for _ in range(20)]
    res = TR.track_c_success(d2t, comp, n_boot=2000)
    assert res["go"] is False
    assert res["median_ok_ge_0.10"] is False
