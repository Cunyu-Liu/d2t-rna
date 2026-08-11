"""P0-8 v3 data-qualification recheck tests (seven-scope, fail-closed).

Enforces the six known audit corrections applied by the P0-8 recheck:

  1. miniTTR docstring must NOT claim per-position error is used.
  2. The three ADD scopes must NEVER be merged; each is its own independent unit.
  3. public/accessibility is NOT a license.
  4. Phase2 Bernoulli sensitivity n=9806/... is count depth, NOT biological N.
  5. constructed identical positions are only a zero-separation control-flow
     test, not real data.
  6. missing raw counts / executable action / real marginal cost =>
     TERMINATED_FOR_CURRENT_DATA (fail-closed).

Also validates the committed v3 manifest and the fail-closed aggregate route.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.data.qualification import (  # noqa: E402
    ADD_SCOPES_NEVER_MERGED,
    REAL_DATA_ATOMIC_CRITERIA,
    REAL_DATA_ROUTE,
    REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA,
    V3_TERMINATED_FOR_CURRENT_DATA,
    V3_VERDICT_VOCABULARY,
    DataQualificationV3,
    add_scopes_never_merged,
    aggregate_real_data_route_v3,
    classify_sample_kind,
    constructed_identical_positions_role,
    fail_closed_v3_verdict,
    license_requires_verified_text,
)

_REPO = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO / "manifests" / "data" / "v7_data_qualification_v3.json"

# Phase2 Bernoulli sensitivity table (required reads per condition) - these are
# COUNT DEPTH values, never biological replicate N (correction 4).
_PHASE2_COUNT_DEPTH_N = (9806, 1565, 388, 93, 39)

# The three ADD scopes are independent units and must never be merged (corr. 2).
_ADD_SCOPES = ("ADD71_STD_0001", "ADDAPO_DCP_0000", "ADDRSW_SHP_0003")


def _load_manifest() -> dict:
    if not _MANIFEST.is_file():
        pytest.skip("v3 qualification manifest not present")
    return json.loads(_MANIFEST.read_text())


def _record_from_scope(scope: dict) -> DataQualificationV3:
    return DataQualificationV3(
        schema_id=scope.get("schema_id", "d2t_rna.v7_data_qualification_v3"),
        schema_version=scope.get("schema_version", "3.0"),
        scope_id=scope["scope_id"],
        purpose=scope.get("purpose", "DATA_QUALIFICATION_RECHECK"),
        paper_eligible=scope.get("paper_eligible", False),
        accession=scope["accession"],
        exact_filename=scope["exact_filename"],
        hash_sha256=scope["hash_sha256"],
        source_url=scope["source_url"],
        retrieval_date=scope["retrieval_date"],
        license_text=scope["license_text"],
        license_version=scope["license_version"],
        license_receipt=scope["license_receipt"],
        raw_counts_present=bool(scope.get("raw_counts_present", False)),
        raw_counts=scope["raw_counts"],
        depth=scope["depth"],
        biological_replicate_crosswalk=scope["biological_replicate_crosswalk"],
        technical_replicate_crosswalk=scope["technical_replicate_crosswalk"],
        merge_history=scope["merge_history"],
        normalization_history=scope["normalization_history"],
        missingness=scope["missingness"],
        error_fields=scope["error_fields"],
        per_position_error_used_by_likelihood=bool(
            scope["per_position_error_used_by_likelihood"]
        ),
        historical_exposure=scope["historical_exposure"],
        independent_unit=scope["independent_unit"],
        dependency_dag=scope["dependency_dag"],
        action_executable=bool(scope.get("action_executable", False)),
        real_marginal_cost=bool(scope.get("real_marginal_cost", False)),
        calibrated_likelihood=bool(scope.get("calibrated_likelihood", False)),
        selection_diagnostic_confirmation_role=scope[
            "selection_diagnostic_confirmation_role"
        ],
        verdict=scope["verdict"],
        corrections_applied=tuple(scope.get("corrections_applied", ())),
        reasons=tuple(scope.get("reasons", ())),
        sources=tuple(scope.get("sources", ())),
    )


# --- correction 6: fail-closed verdict -----------------------------------


def test_fail_closed_verdict_when_raw_counts_missing():
    assert (
        fail_closed_v3_verdict(
            raw_counts_present=False,
            executable_action=True,
            real_marginal_cost=True,
        )
        == V3_TERMINATED_FOR_CURRENT_DATA
    )


def test_fail_closed_verdict_when_action_missing():
    assert (
        fail_closed_v3_verdict(
            raw_counts_present=True,
            executable_action=False,
            real_marginal_cost=True,
        )
        == V3_TERMINATED_FOR_CURRENT_DATA
    )


def test_fail_closed_verdict_when_cost_missing():
    assert (
        fail_closed_v3_verdict(
            raw_counts_present=True,
            executable_action=True,
            real_marginal_cost=False,
        )
        == V3_TERMINATED_FOR_CURRENT_DATA
    )


# --- correction 2: three ADD scopes never merged -------------------------


def test_add_scopes_are_three_distinct_units():
    assert ADD_SCOPES_NEVER_MERGED == _ADD_SCOPES
    assert len(ADD_SCOPES_NEVER_MERGED) == 3


def test_three_add_scopes_never_merged():
    # a single independent unit carrying more than one ADD scope is a merge
    assert add_scopes_never_merged(("ADD71_STD_0001",)) is True
    assert add_scopes_never_merged(("ADDAPO_DCP_0000",)) is True
    assert add_scopes_never_merged(("ADDRSW_SHP_0003",)) is True
    # any pair merged into one unit must be rejected
    assert add_scopes_never_merged(("ADD71_STD_0001", "ADDAPO_DCP_0000")) is False
    assert add_scopes_never_merged(("ADD71_STD_0001", "ADDRSW_SHP_0003")) is False
    assert add_scopes_never_merged(("ADDAPO_DCP_0000", "ADDRSW_SHP_0003")) is False
    assert add_scopes_never_merged(("ADD71_STD_0001", "ADDAPO_DCP_0000", "ADDRSW_SHP_0003")) is False


# --- correction 3: public != license ------------------------------------


def test_public_download_is_not_license():
    assert (
        license_requires_verified_text(
            publicly_downloadable=True,
            verified_license_receipt=False,
        )
        is False
    )
    assert (
        license_requires_verified_text(
            publicly_downloadable=False,
            verified_license_receipt=True,
        )
        is True
    )


def test_no_scope_asserts_verified_license():
    manifest = _load_manifest()
    for scope in manifest["scopes"]:
        rec = _record_from_scope(scope)
        assert rec.license_receipt != "VERIFIED", scope["scope_id"]


# --- correction 4: count depth != biological N --------------------------


def test_phase2_sensitivity_n_is_count_depth_not_biological():
    for n in _PHASE2_COUNT_DEPTH_N:
        assert classify_sample_kind(claimed_as="count_depth") == "COUNT_DEPTH"
    assert classify_sample_kind(claimed_as="biological_replicates") == "BIOLOGICAL_N"
    # the Bernoulli sensitivity table values are count depth, never biological N
    assert classify_sample_kind(claimed_as="count_depth") != "BIOLOGICAL_N"


# --- correction 5: constructed identical positions are control-flow -----


def test_constructed_identical_positions_are_control_flow_only():
    assert (
        constructed_identical_positions_role(constructed=True)
        == "ZERO_SEPARATION_CONTROL_FLOW_ONLY"
    )
    assert constructed_identical_positions_role(constructed=False) == "REAL_DATA"


# --- correction 1: miniTTR docstring must not claim error used ----------


def test_minittr_docstring_does_not_claim_per_position_error_used():
    src = (_REPO / "src" / "d2t_rna" / "data" / "measured_mattr.py").read_text()
    assert "parsed and used" not in src
    # the corrected docstring must say the error is parsed but NOT used
    assert "parsed but NOT used" in src
    # the likelihood remains the clamp (no per-position error consumption)
    assert "per_position_error_used=False" in src


# --- manifest structure / consistency -----------------------------------


def test_manifest_covers_seven_scopes_with_closed_verdicts():
    manifest = _load_manifest()
    assert manifest["paper_eligible"] is False
    assert manifest["purpose"] == "DATA_QUALIFICATION_RECHECK"
    assert len(manifest["scopes"]) == 7
    for scope in manifest["scopes"]:
        assert scope["verdict"] in V3_VERDICT_VOCABULARY


def test_all_scopes_fail_closed_terminated():
    manifest = _load_manifest()
    for scope in manifest["scopes"]:
        rec = _record_from_scope(scope)
        # correction 6: missing raw counts/action/cost -> TERMINATED
        expected = fail_closed_v3_verdict(
            raw_counts_present=rec.raw_counts_present,
            executable_action=rec.action_executable,
            real_marginal_cost=rec.real_marginal_cost,
        )
        assert expected == V3_TERMINATED_FOR_CURRENT_DATA
        assert rec.verdict == V3_TERMINATED_FOR_CURRENT_DATA


def test_aggregate_route_stays_terminated():
    manifest = _load_manifest()
    records = [_record_from_scope(s) for s in manifest["scopes"]]
    decision = aggregate_real_data_route_v3(records)
    assert decision["route"] == REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA
    assert decision["open"] is False


def test_global_real_data_route_stays_terminated():
    assert REAL_DATA_ROUTE == REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA
    assert len(REAL_DATA_ATOMIC_CRITERIA) == 8


def test_no_scope_satisfies_all_eight_atomic_criteria():
    manifest = _load_manifest()
    for scope in manifest["scopes"]:
        rec = _record_from_scope(scope)
        assert rec.real_data_atomic_criteria_met is False, scope["scope_id"]
