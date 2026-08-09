"""Batch 3 audit tests: real-data qualification, statistical-unit contract.

Validates the fail-closed qualification verdicts for ADD / glycine / miniTTR /
SAM-III / RORC, the machine-derived ``per_position_error_used`` rule, the
aggregate real-data route, and the statistical-unit contract (independent N is
never positions/reads/seeds/budget cells; exposed profiles cannot be renamed
held-out).
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
    DATA_BLOCKED_ARCHIVE,
    DATA_DESCRIPTIVE_ONLY,
    DATA_INELIGIBLE,
    DATA_QUALIFIED,
    DataQualification,
    aggregate_real_data_route,
    machine_derived_per_position_error_used,
)

# Per-domain verdicts from the read-only inventory + audit.
_DOMAINS = {
    "add": {
        "accessions": ("ADD71_STD_0001", "ADDAPO_DCP_0000", "ADDRSW_SHP_0003"),
        "raw": False,
        "crosswalk": False,
        "calibrated": False,
        "action": False,
        "cost": False,
        "verdict": DATA_DESCRIPTIVE_ONLY,
        "role": "selection_exposed",
    },
    "glycine": {
        "accessions": ("BSUGLY_DMS_0013", "BSUGLY_DMS_0014"),
        "raw": False,
        "crosswalk": False,
        "calibrated": False,
        "action": False,
        "cost": False,
        "verdict": DATA_BLOCKED_ARCHIVE,
        "role": "selection_exposed",
    },
    "minittr": {
        "accessions": ("MTTR1_MGTI_0001",),
        "raw": False,
        "crosswalk": False,
        "calibrated": False,
        "action": False,
        "cost": False,
        "verdict": DATA_DESCRIPTIVE_ONLY,
        "role": "selection_exposed",
    },
    "samiii": {
        "accessions": ("GSE278422",),
        "raw": False,
        "crosswalk": False,
        "calibrated": False,
        "action": False,
        "cost": False,
        "verdict": DATA_BLOCKED_ARCHIVE,
        "role": "selection_exposed",
    },
    "rorc": {
        "accessions": (),
        "raw": False,
        "crosswalk": False,
        "calibrated": False,
        "action": False,
        "cost": False,
        "verdict": DATA_INELIGIBLE,
        "role": "selection_exposed",
    },
}


def _qualify(dataset_id: str, **overrides) -> DataQualification:
    spec = dict(_DOMAINS[dataset_id])
    spec.update(overrides)
    return DataQualification(
        dataset_id=dataset_id,
        accessions=spec["accessions"],
        verdict=spec["verdict"],
        raw_per_replicate_counts_available=spec["raw"],
        independent_unit_crosswalk=spec["crosswalk"],
        calibrated_likelihood=spec["calibrated"],
        executable_action=spec["action"],
        real_marginal_cost=spec["cost"],
        per_position_error_used=False,  # clamp likelihood never uses error
        exposure_role=spec["role"],
        reasons=("audit fail-closed qualification",),
    )


def test_each_domain_has_a_closed_verdict():
    for dataset_id in _DOMAINS:
        q = _qualify(dataset_id)
        assert q.verdict in {
            DATA_QUALIFIED,
            DATA_BLOCKED_ARCHIVE,
            DATA_DESCRIPTIVE_ONLY,
            DATA_INELIGIBLE,
        }


def test_clamp_likelihood_never_reports_per_position_error_used():
    """The clamp model consumes no per-position error, so per_position_error_used
    must be machine-derived to False (the audit's exact finding)."""
    assert machine_derived_per_position_error_used(model_consumes_error=False) is False
    assert machine_derived_per_position_error_used(model_consumes_error=True) is True


def test_no_domain_meets_real_route_requirements():
    for dataset_id in _DOMAINS:
        q = _qualify(dataset_id)
        assert q.real_route_requirements_met is False


def test_aggregate_route_is_blocked_pending_archive():
    quals = [_qualify(d) for d in _DOMAINS]
    decision = aggregate_real_data_route(quals)
    assert decision.route == "BLOCKED_PENDING_ARCHIVE_QUALIFICATION"
    assert decision.any_qualified is False
    assert "rorc" not in decision.blocked_domains  # ineligible excluded


def test_qualified_domain_opens_route_for_it():
    q = _qualify(
        "add",
        raw=True,
        crosswalk=True,
        calibrated=True,
        action=True,
        cost=True,
        verdict=DATA_QUALIFIED,
    )
    decision = aggregate_real_data_route([q])
    assert decision.route == "OPEN_FOR_QUALIFIED_DOMAINS"
    assert decision.qualified_domains == ("add",)


def test_all_ineligible_routes_terminated():
    decision = aggregate_real_data_route([_qualify("rorc")])
    assert decision.route == "TERMINATED_FOR_CURRENT_DATA"


def test_exposed_profile_cannot_be_renamed_held_out():
    from d2t_rna.data.qualification import forbidden_claim_renames

    forbidden = forbidden_claim_renames("selection_exposed")
    for name in ("held-out", "test", "independent validation", "prospective", "blinded"):
        assert name in forbidden


@pytest.mark.parametrize(
    "unit",
    ["position", "read", "seed", "budget_cell", "cost_cell", "technical_repeat", "action_draw"],
)
def test_non_independent_units_are_never_independent_n(unit):
    from d2t_rna.data.qualification import _NON_INDEPENDENT_UNITS

    assert unit in _NON_INDEPENDENT_UNITS


def test_manifests_directory_qualification_records_validate():
    """The committed manifests/data/*_qualification_v2.json must parse as the
    expected per-domain verdicts and must be consistent with the module."""
    repo = Path(__file__).resolve().parents[2]
    data_manifests = repo / "manifests" / "data"
    if not data_manifests.is_dir():
        pytest.skip("manifests/data not present in this tree")
    expected = {
        "add": DATA_DESCRIPTIVE_ONLY,
        "glycine": DATA_BLOCKED_ARCHIVE,
        "minittr": DATA_DESCRIPTIVE_ONLY,
        "samiii": DATA_BLOCKED_ARCHIVE,
        "rorc": DATA_INELIGIBLE,
    }
    for name, verdict in expected.items():
        path = data_manifests / f"{name}_qualification_v2.json"
        if not path.is_file():
            continue
        rec = json.loads(path.read_text())
        assert rec["verdict"] == verdict, name
        assert rec["dataset_id"] == name
