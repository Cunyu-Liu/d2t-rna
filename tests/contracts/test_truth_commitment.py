from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from d2t_rna.contracts.enums import TruthVisibility
from d2t_rna.contracts.primitives import RegistryRef
from d2t_rna.contracts.truth import TruthAssetCommitment

from .conftest import SHA_A, SHA_B, SHA_C, SHA_D, SHA_E, SHA_F


def valid_commitment_payload() -> dict[str, Any]:
    return {
        "truth_asset_id": "truth.synthetic.001",
        "asset_hash": SHA_A,
        "sequence_identity_hash": SHA_B,
        "condition_spec_hash": SHA_C,
        "measurement_modality": RegistryRef(
            registry_id="modality.synthetic_counts",
            registry_hash=SHA_D,
        ),
        "eligibility_status_without_direction": RegistryRef(
            registry_id="eligibility.registered_without_direction",
            registry_hash=SHA_E,
        ),
        "numeric_payload_hash": SHA_F,
        "semantic_payload_hash": SHA_A,
        "visibility": TruthVisibility.HASH_ONLY,
    }


def test_truth_commitment_is_hash_only() -> None:
    commitment = TruthAssetCommitment(**valid_commitment_payload())
    assert set(commitment.model_dump(mode="json")) == {
        "schema_id",
        "schema_version",
        "truth_asset_id",
        "asset_hash",
        "sequence_identity_hash",
        "condition_spec_hash",
        "measurement_modality",
        "eligibility_status_without_direction",
        "numeric_payload_hash",
        "semantic_payload_hash",
        "visibility",
    }
    assert commitment.visibility is TruthVisibility.HASH_ONLY


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "population_estimate",
        "confidence_region",
        "directional_evidence",
        "state_preservation_result",
        "projected_state_proportions",
        "h0_h1_core_binding",
        "action_effect_labels",
        "native_t4_eligible",
    ],
)
def test_truth_numeric_or_directional_payload_is_rejected_before_lock_d(
    forbidden_field: str,
) -> None:
    payload = valid_commitment_payload()
    payload[forbidden_field] = {"sealed": False}
    with pytest.raises(ValidationError):
        TruthAssetCommitment(**payload)


@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll",),
            whitelist_characters="_",
        ),
        min_size=1,
        max_size=24,
    ).filter(
        lambda value: value
        not in {
            "schema_id",
            "schema_version",
            "truth_asset_id",
            "asset_hash",
            "sequence_identity_hash",
            "condition_spec_hash",
            "measurement_modality",
            "eligibility_status_without_direction",
            "numeric_payload_hash",
            "semantic_payload_hash",
            "visibility",
        }
    )
)
def test_any_unregistered_truth_field_is_rejected(field: str) -> None:
    payload = valid_commitment_payload()
    payload[field] = "unexpected"
    with pytest.raises(ValidationError):
        TruthAssetCommitment(**payload)
