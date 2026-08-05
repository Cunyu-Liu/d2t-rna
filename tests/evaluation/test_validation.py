"""Tests for the D2T-RNA v7 §10 validation module (contract section 10).

Covers the assumption-violation gate (§10.2), registered nuisance coupling
(§10.1), claim lint (§1.3 / CLAIM-BOUNDARY-GATE), and the §10.3 independent
checker aggregation receipt — all fail-closed.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.evaluation.validation import (
    ACTION_INDUCED_STATE_CHANGE,
    AUTHORIZED,
    DEPENDENT_OBSERVATIONS,
    NOT_ESTABLISHED,
    NO_COMPLETE_OBSERVATION_MODEL,
    OMITTED_THIRD_STATE,
    PROCEED,
    UNKNOWN_DEPENDENCY_UNIT,
    UNREGISTERED_SHARED_NUISANCE,
    VALID_PROFILE,
    AssumptionProfile,
    assumption_gate,
    claim_lint,
    product_law_authorized,
    section10_receipt,
    wrong_coupling_pairwise,
)

F = Fraction


def test_valid_profile_proceeds() -> None:
    assert assumption_gate(VALID_PROFILE) == PROCEED
    assert VALID_PROFILE.violations() == []


def test_each_assumption_violation_is_not_established() -> None:
    cases = {
        "action_changes_state": ACTION_INDUCED_STATE_CHANGE,
        "omitted_third_state": OMITTED_THIRD_STATE,
        "unregistered_nuisance": UNREGISTERED_SHARED_NUISANCE,
        "unknown_dependency_unit": UNKNOWN_DEPENDENCY_UNIT,
        "no_complete_obs_model": NO_COMPLETE_OBSERVATION_MODEL,
        "dependent_observations": DEPENDENT_OBSERVATIONS,
    }
    for name, prof in cases.items():
        assert assumption_gate(prof) == NOT_ESTABLISHED, name
        assert len(prof.violations()) == 1, name


def test_contraction_with_two_violations_lists_both() -> None:
    prof = AssumptionProfile(
        complete_observation_model=True,
        dependency_unit_known=False,
        shared_nuisance_registered=False,
        action_preserves_latent_state=True,
        no_unmodeled_third_state=True,
        observations_independent=True,
    )
    assert assumption_gate(prof) == NOT_ESTABLISHED
    assert len(prof.violations()) == 2


def test_registered_coupling_authorized_only() -> None:
    assert product_law_authorized("CARTESIAN")[0] == AUTHORIZED
    assert product_law_authorized("EQUAL_REALIZED_VALUE")[0] == AUTHORIZED
    assert product_law_authorized("WRONG_UNREGISTERED_COUPLING")[0] == NOT_ESTABLISHED


def test_wrong_coupling_pairwise_boundary() -> None:
    verdicts = wrong_coupling_pairwise()
    assert [v for _, v in verdicts] == [AUTHORIZED, AUTHORIZED, NOT_ESTABLISHED]


def test_claim_lint_clean_text_passes() -> None:
    res = claim_lint(
        "model-conditional certificate for a registered finite pair catalog"
    )
    assert res["gate"] == "PASS"
    assert res["violations"] == []


def test_claim_lint_forbidden_word_fails() -> None:
    res = claim_lint("This provides prospective new-library validation.")
    assert res["gate"] == "FAIL"
    assert any("prospective" in v for v in res["violations"])
    assert any("new-library" in v for v in res["violations"])


def test_claim_lint_native_t4_and_replicate_abuse_fail() -> None:
    res = claim_lint("native-T4 biological truth from reads used as replicates")
    assert res["gate"] == "FAIL"
    assert any("native-t4" in v for v in res["violations"])


def test_section10_receipt_all_pass() -> None:
    receipt = section10_receipt(
        profile=VALID_PROFILE,
        coupling="CARTESIAN",
        claim_text="model-conditional certificate for a registered finite catalog",
        collision={
            "verified": True,
            "failures": [],
            "marginal_collision": True,
            "action_residuals_zero": True,
        },
        separation={"verified": True, "failures": [], "reported_gamma": F(0), "infimum_over_catalog": F(0)},
        lp_results={
            "dual_feasible": True,
            "lower_bound": F(1),
            "budget": F(2),
            "expected_no_go": False,
            "cost": F(3),
            "integer_cost": F(3),
        },
        product_tv_pair=((F(1, 2), F(1, 2)), (F(0, 1), F(1, 1))),
    )
    assert receipt.all_pass is True
    assert receipt.assumption_gate == PROCEED
    assert receipt.claim_gate == "PASS"
    assert receipt.lp_dual_feasible is True
    assert receipt.budget_cost_consistent is True


def test_section10_receipt_fails_closed_on_broken_assumption() -> None:
    receipt = section10_receipt(
        profile=OMITTED_THIRD_STATE,
        coupling="CARTESIAN",
        claim_text="model-conditional certificate for a registered finite catalog",
        collision={"verified": True, "failures": []},
        separation={"verified": True, "failures": []},
        lp_results={
            "dual_feasible": True,
            "lower_bound": F(1),
            "budget": F(2),
            "expected_no_go": False,
            "cost": F(3),
            "integer_cost": F(3),
        },
    )
    assert receipt.all_pass is False
    assert receipt.assumption_gate == NOT_ESTABLISHED
    assert "unmodeled third latent state present" in receipt.assumptions_violated


def test_section10_receipt_fails_on_forbidden_claim() -> None:
    receipt = section10_receipt(
        profile=VALID_PROFILE,
        coupling="CARTESIAN",
        claim_text="this is independent validation of a new library",
        collision={"verified": True, "failures": []},
        separation={"verified": True, "failures": []},
        lp_results={"dual_feasible": True},
    )
    assert receipt.all_pass is False
    assert receipt.claim_gate == "FAIL"


def test_section10_receipt_no_go_sign_consistency() -> None:
    # lower_bound > budget with expected_no_go=True is consistent.
    receipt = section10_receipt(
        profile=VALID_PROFILE,
        coupling="CARTESIAN",
        claim_text="model-conditional certificate for a registered finite catalog",
        collision={"verified": True, "failures": []},
        separation={"verified": True, "failures": []},
        lp_results={
            "dual_feasible": True,
            "lower_bound": F(5),
            "budget": F(2),
            "expected_no_go": True,
            "cost": F(3),
            "integer_cost": F(3),
        },
    )
    assert receipt.no_go_sign_consistent is True
    assert receipt.all_pass is True