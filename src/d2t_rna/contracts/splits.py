"""Immutable SplitRelationSpec schema; semantic checks are Task 2."""

from __future__ import annotations

from typing import Literal

from pydantic import StrictInt

from .base import FrozenContractModel
from .enums import SplitRelation
from .primitives import (
    OverlapCount,
    ProofArtifactRef,
    RegistryRef,
    Sha256Hex,
)


class SplitRelationSpec(FrozenContractModel):
    schema_id: Literal["d2t_rna.split_relation"] = "d2t_rna.split_relation"
    schema_version: Literal["1.0"] = "1.0"
    split_relation: SplitRelation
    dependency_unit_level: RegistryRef
    planning_partition_hash: Sha256Hex
    certificate_partition_hash: Sha256Hex
    conditioning_sigma_field_hash: Sha256Hex
    selection_inference_independence_proof: ProofArtifactRef | None
    overlap_counts: tuple[OverlapCount, ...]
    split_seed: StrictInt | None
