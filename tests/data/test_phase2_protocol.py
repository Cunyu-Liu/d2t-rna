"""Tests for the Conditional Phase 2 real-data protocol (plan §P2).

These verify the fail-closed terminal route decision, the completeness of the
pre-registered protocol elements, the deterministic analytic power / delta_min
computation, and the acquisition NO_GO decision.  They run entirely on
synthetic fixture qualification manifests (no real data, no fabricated data).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from d2t_rna.data.phase2_protocol import (
    ACQUISITION_NO_GO,
    TERMINAL_ROUTE,
    build_phase2_protocol,
    delta_min_at_n,
    required_n_per_condition,
)


def _write_qual_manifest(
    dir_: pathlib.Path,
    dataset_id: str,
    verdict: str,
    *,
    raw_counts: bool = False,
    crosswalk: bool = False,
    calibrated: bool = False,
    action: bool = False,
    cost: bool = False,
    exposure: str = "selection_exposed",
) -> pathlib.Path:
    p = dir_ / f"{dataset_id}_qualification_v2.json"
    p.write_text(
        json.dumps(
            {
                "schema_id": "d2t_rna.data_qualification_v2",
                "schema_version": "2.0",
                "dataset_id": dataset_id,
                "accessions": [f"ACC_{dataset_id}"],
                "verdict": verdict,
                "raw_per_replicate_counts_available": raw_counts,
                "independent_unit_crosswalk": crosswalk,
                "calibrated_likelihood": calibrated,
                "executable_action": action,
                "real_marginal_cost": cost,
                "per_position_error_used": False,
                "exposure_role": exposure,
                "reasons": ["fixture reason"],
                "forbidden_claims": ["held-out", "test"],
                "sources": ["fixture"],
            }
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def qual_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "qual"
    d.mkdir()
    # Two blocked/descriptive domains, none qualified.
    _write_qual_manifest(d, "glycine", "BLOCKED_PENDING_ARCHIVE_QUALIFICATION")
    _write_qual_manifest(d, "add", "DESCRIPTIVE_ONLY")
    return d


def test_route_terminated_for_current_data(qual_dir: pathlib.Path) -> None:
    m = build_phase2_protocol(qual_dir, head="abc123")
    assert m["real_data_route_for_current_data"] == TERMINAL_ROUTE
    assert m["aggregate_route_from_qualification_layer"] != TERMINAL_ROUTE
    assert m["qualified_domains"] == []
    assert m["pivot"] == "SYNTHETIC_SOFTWARE_PAPER"


def test_all_protocol_elements_present(qual_dir: pathlib.Path) -> None:
    m = build_phase2_protocol(qual_dir, head="h")
    expected = {
        "independent_unit_dag",
        "count_likelihood",
        "calibration_protocol",
        "action_registry",
        "cost_receipt",
        "delta_min",
        "power_precision_simulation",
        "multiplicity_control",
        "qc_exclusion",
        "sealed_confirmation_protocol",
    }
    assert expected.issubset(m["protocol"].keys())
    # fail-closed statuses
    assert (
        m["protocol"]["count_likelihood"]["status"]
        == "PRE_REGISTERED_SPEC_NOT_FITTABLE_ON_CURRENT_DATA"
    )
    assert m["protocol"]["action_registry"]["registered_real_actions"] == []
    assert m["protocol"]["cost_receipt"]["registered_real_marginal_cost"] is False


def test_acquisition_no_go(qual_dir: pathlib.Path) -> None:
    m = build_phase2_protocol(qual_dir, head="h")
    assert m["acquisition"]["decision"] == ACQUISITION_NO_GO
    assert m["acquisition"]["authorization_required"] is True
    assert "separate acquisition authorization" in m["acquisition"]["go_conditions"][-1]


def test_forbidden_practices_recorded(qual_dir: pathlib.Path) -> None:
    m = build_phase2_protocol(qual_dir, head="h")
    joined = " ".join(m["forbidden_practices"]).lower()
    assert "clamp" in joined
    assert "n=3/15/3" in m["forbidden_practices"][2].lower()


def test_deterministic_rebuild(qual_dir: pathlib.Path) -> None:
    a = build_phase2_protocol(qual_dir, head="same")
    b = build_phase2_protocol(qual_dir, head="same")
    assert a == b


def test_input_manifest_shas_bound(qual_dir: pathlib.Path) -> None:
    m = build_phase2_protocol(qual_dir, head="h")
    assert set(m["input_manifests_sha256"].keys()) == {
        "add_qualification_v2.json",
        "glycine_qualification_v2.json",
    }
    for v in m["input_manifests_sha256"].values():
        assert len(v) == 64


def test_required_n_monotone_in_delta() -> None:
    n_small = required_n_per_condition(0.10)
    n_large = required_n_per_condition(0.30)
    assert n_large < n_small
    assert n_small > 0


def test_historical_n_delta_min_is_large() -> None:
    # At the claimed historical n=3 the resolvable effect is very large,
    # consistent with the audit's rejection of the n=3 real-repeat claims.
    assert delta_min_at_n(3) > 0.3
    # More replicates resolve smaller effects.
    assert delta_min_at_n(15) < delta_min_at_n(3)


def test_delta_min_at_n_matches_required_n_inverse() -> None:
    d = delta_min_at_n(50)
    # n required for that delta should be near 50
    assert 40 <= required_n_per_condition(d) <= 60
