"""Tests for the D2T-RNA v7 §12.3 submission-readiness gate (amended condition 6)."""

from __future__ import annotations

import pytest

from d2t_rna.contracts.submission_gate import (
    COMPLETE_FAIL_CLOSED_ONLY_AUDIT,
    NOT_APPLICABLE,
    NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE,
    NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL,
    NOT_ESTABLISHED,
    QUALIFIED_RETROSPECTIVE_CASE,
    SUBMISSION_READY,
    evaluate_submission_gate,
)


def _base(**overrides) -> dict:
    d = {
        "task5_closure_complete": True,
        "t2b_exact_collision_separation": True,
        "t2c_finite_sample": True,
        "executable_certificate": True,
        "oracle_baselines_misspecification_pass": True,
        "r2_outcomes": [NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL],
        "r2_audited": True,
        "data_role_dependency_claim_audit_pass": True,
        "reproducible": True,
    }
    d.update(overrides)
    return d


def test_all_conditions_pass_gives_submission_ready() -> None:
    r = evaluate_submission_gate(**_base())
    assert r.submission_ready is True
    assert r.gate_state == SUBMISSION_READY
    assert r.certificate_guard == "ESTABLISHED"
    assert r.condition_6_mode == COMPLETE_FAIL_CLOSED_ONLY_AUDIT
    assert r.scientific_claim_authorized is False


def test_qualified_retrospective_case_mode() -> None:
    r = evaluate_submission_gate(
        **{
            **_base(),
            "r2_outcomes": [
                NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL,
                "ESTABLISHED",
                NOT_APPLICABLE,
            ],
        }
    )
    assert r.condition_6_mode == QUALIFIED_RETROSPECTIVE_CASE
    assert r.submission_ready is True


def test_complete_fail_closed_only_audit_mode() -> None:
    r = evaluate_submission_gate(
        **{
            **_base(),
            "r2_outcomes": [
                NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL,
                NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE,
                NOT_APPLICABLE,
            ],
        }
    )
    assert r.condition_6_mode == COMPLETE_FAIL_CLOSED_ONLY_AUDIT
    assert r.submission_ready is True


def test_un_audited_r2_fails_condition_6() -> None:
    r = evaluate_submission_gate(**{**_base(), "r2_audited": False})
    assert r.condition_6_mode is None
    assert r.submission_ready is False
    assert r.gate_state == "NOT_SUBMISSION_READY"
    assert r.conditions["retrospective_qualified_or_complete_fail_closed"] is False


def test_unknown_outcome_breaks_complete_fail_closed() -> None:
    r = evaluate_submission_gate(**{**_base(), "r2_outcomes": ["UNKNOWN"]})
    assert r.condition_6_mode is None
    assert r.submission_ready is False


def test_any_other_condition_fails_blocks_submission_ready() -> None:
    r = evaluate_submission_gate(**{**_base(), "t2c_finite_sample": False})
    assert r.submission_ready is False
    assert r.conditions["t2c_finite_sample"] is False


def test_as_dict_roundtrip() -> None:
    r = evaluate_submission_gate(**_base())
    d = r.as_dict()
    assert d["gate_state"] == SUBMISSION_READY
    assert d["certificate_guard"] == "ESTABLISHED"
    assert d["scientific_claim_authorized"] is False
    assert d["condition_6_mode"] == COMPLETE_FAIL_CLOSED_ONLY_AUDIT