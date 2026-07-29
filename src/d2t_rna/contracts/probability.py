"""Immutable ProbabilitySpaceSpec schema; semantic checks are Task 2."""

from __future__ import annotations

from typing import Literal

from pydantic import StrictBool

from .base import FrozenContractModel
from .enums import ProbabilityScope
from .primitives import (
    ObjectCommitment,
    RegistryRef,
    Sha256Hex,
)


class ProbabilitySpaceSpec(FrozenContractModel):
    schema_id: Literal["d2t_rna.probability_space"] = (
        "d2t_rna.probability_space"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_scope: ProbabilityScope
    fixed_objects: tuple[ObjectCommitment, ...]
    random_objects: tuple[ObjectCommitment, ...]
    sampling_law_hash: Sha256Hex
    parameter_space_hash: Sha256Hex
    conditioning_sigma_field_hash: Sha256Hex
    observation_model_hash: Sha256Hex | None
    estimand: RegistryRef
    target: RegistryRef
    formal_scientific_risk_guarantee: StrictBool
