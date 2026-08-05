"""Tests for the D2T-RNA v7 §8.4 R2 retrospective fail-closed framework."""

from __future__ import annotations

import pytest

from d2t_rna.data.r2_evaluation import (
    ESTABLISHED,
    EVALUATION_LABEL,
    NOT_ESTABLISHED,
    certificate_guard,
    r2_dataset_status,
    r2_evaluate_all,
)


def _full_gates(**overrides):
    g = {
        "within_registered_fixed_dataset": True,
        "observed_data_materialized": True,
        "observation_model_available": True,
        "dependency_graph_available": True,
        "independence_proof_available": True,
        "no_held_out_blinded_prospective": True,
    }
    g.update(overrides)
    return g


def test_all_gates_present_establishes() -> None:
    s = r2_dataset_status("add", **_full_gates())
    assert s.status == ESTABLISHED
    assert s.missing_gates == ()
    assert s.reason_codes == ()
    assert s.label == EVALUATION_LABEL
    assert s.role == "COUNTERFACTUAL_RETROSPECTIVE_FULL_MATRIX_COMPRESSION"


def test_each_missing_gate_is_not_established_and_fail_closed() -> None:
    cases = {
        "within_registered_fixed_dataset": "escapes the registered fixed dataset",
        "observed_data_materialized": "not materialized within fixed dataset",
        "observation_model_available": "observation model unavailable",
        "dependency_graph_available": "dependency graph unavailable",
        "independence_proof_available": "independence proof unavailable",
        "no_held_out_blinded_prospective": "claim boundary breached",
    }
    for gate, needle in cases.items():
        s = r2_dataset_status("add", **_full_gates(**{gate: False}))
        assert s.status == NOT_ESTABLISHED, gate
        assert gate in s.missing_gates, gate
        assert any(needle in rc for rc in s.reason_codes), gate


def test_unknown_dataset_rejected() -> None:
    with pytest.raises(ValueError):
        r2_dataset_status("not-a-dataset", **_full_gates())


def test_rorc_role_registered() -> None:
    s = r2_dataset_status("rorc", **_full_gates())
    assert s.role == "HISTORICALLY_EXPOSED_THIRD_STATE_MISSPECIFICATION_STRESS"


def test_sam_iii_role_registered() -> None:
    s = r2_dataset_status("sam-iii", **_full_gates(observed_data_materialized=False))
    assert s.role == "RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC"
    assert s.status == NOT_ESTABLISHED


def test_r2_evaluate_all_aggregates_and_closes_when_any_missing() -> None:
    report = r2_evaluate_all(
        {
            "add": _full_gates(),
            "sam-iii": _full_gates(),
            "rorc": _full_gates(observed_data_materialized=False),
        }
    )
    assert report.all_established is False
    assert certificate_guard(report) == NOT_ESTABLISHED
    status_by_id = {s.dataset_id: s for s in report.datasets}
    assert status_by_id["add"].status == ESTABLISHED
    assert status_by_id["rorc"].status == NOT_ESTABLISHED


def test_r2_evaluate_all_established_only_when_all_pass() -> None:
    report = r2_evaluate_all(
        {
            "add": _full_gates(),
            "sam-iii": _full_gates(),
            "rorc": _full_gates(),
        }
    )
    assert report.all_established is True
    assert certificate_guard(report) == ESTABLISHED


def test_missing_dataset_profile_rejected() -> None:
    with pytest.raises(ValueError):
        r2_evaluate_all({"add": _full_gates(), "sam-iii": _full_gates()})


def test_as_dict_roundtrip() -> None:
    s = r2_dataset_status("add", **_full_gates(observed_data_materialized=False))
    d = s.as_dict()
    assert d["status"] == NOT_ESTABLISHED
    assert d["label"] == EVALUATION_LABEL
    assert "not materialized" in d["reason_codes"][0]