"""Hash-only truth commitments visible before Lock D."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import FrozenContractModel
from .enums import TruthVisibility
from .primitives import RegisteredId, RegistryRef, Sha256Hex


class TruthAssetCommitment(FrozenContractModel):
    schema_id: Literal["d2t_rna.truth_asset_commitment"] = (
        "d2t_rna.truth_asset_commitment"
    )
    schema_version: Literal["1.0"] = "1.0"
    truth_asset_id: RegisteredId
    asset_hash: Sha256Hex = Field(
        description=(
            "Raw-file SHA-256 of the exact sealed reveal package bytes, "
            "including numeric, semantic, and decision-binding components"
        )
    )
    sequence_identity_hash: Sha256Hex
    condition_spec_hash: Sha256Hex
    measurement_modality: RegistryRef
    eligibility_status_without_direction: RegistryRef
    numeric_payload_hash: Sha256Hex
    semantic_payload_hash: Sha256Hex
    visibility: Literal[TruthVisibility.HASH_ONLY]
