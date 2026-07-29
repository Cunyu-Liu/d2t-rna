"""Immutable per-scenario proof schema; proof semantics are Task 5."""

from __future__ import annotations

from typing import Literal

from pydantic import StrictBool

from .base import FrozenContractModel
from .enums import CoverageBoundMethod
from .primitives import (
    NamedBound,
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)


class ScenarioProof(FrozenContractModel):
    schema_id: Literal["d2t_rna.scenario_proof"] = (
        "d2t_rna.scenario_proof"
    )
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: RegisteredId
    law_hash: Sha256Hex
    hypothesis_region: RegistryRef
    coverage_core_membership: RegistryRef
    conditioning_sigma_field_hash: Sha256Hex
    risk_upper_bounds: tuple[NamedBound, ...]
    coverage_lower_bounds: tuple[NamedBound, ...]
    coverage_bound_method: CoverageBoundMethod
    probability_mass_accounted: Rational
    omitted_mass_bound: Rational
    numerical_error_bound: Rational
    proof_artifact_hash: Sha256Hex
    formal_guarantee: StrictBool
