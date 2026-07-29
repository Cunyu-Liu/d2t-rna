"""Fail-closed split-relation semantics."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import StrictBool, StrictStr, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import SplitRelation
from d2t_rna.contracts.primitives import ProofArtifactRef, Sha256Hex
from d2t_rna.contracts.splits import SplitRelationSpec

from .registry import (
    RegistryResolutionError,
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    ensure_trusted_task2_registry,
    resolve_registry_ref,
)


class SplitSemanticError(ValueError):
    """Raised for contradictory split semantics."""


class SplitDisposition(str, Enum):
    INDEPENDENCE_INPUTS_BOUND_PENDING_PROOF = (
        "INDEPENDENCE_INPUTS_BOUND_PENDING_PROOF"
    )
    FINITE_POPULATION_JOINT_LAW_ONLY = "FINITE_POPULATION_JOINT_LAW_ONLY"
    SHARED_OR_UNKNOWN_DEPENDENCE = "SHARED_OR_UNKNOWN_DEPENDENCE"
    ABSTAIN = "ABSTAIN"


class NuisanceHandlingMode(str, Enum):
    CONDITION_ON_REGISTERED_NUISANCE = (
        "CONDITION_ON_REGISTERED_NUISANCE"
    )
    UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE = (
        "UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE"
    )


class NuisanceHandlingEvidence(FrozenContractModel):
    """Bindings for either conditional or uniform-worst-case nuisance handling."""

    schema_id: Literal["d2t_rna.nuisance_handling_evidence"] = (
        "d2t_rna.nuisance_handling_evidence"
    )
    schema_version: Literal["1.0"] = "1.0"
    mode: NuisanceHandlingMode
    split_conditioning_sigma_field_hash: Sha256Hex
    certificate_conditioning_sigma_field_hash: Sha256Hex
    nuisance_parameter_space_hash: Sha256Hex
    uniform_worst_case_proof: ProofArtifactRef | None

    @model_validator(mode="after")
    def mode_shape_is_exact(self) -> "NuisanceHandlingEvidence":
        if (
            self.mode
            is NuisanceHandlingMode.CONDITION_ON_REGISTERED_NUISANCE
        ):
            if (
                self.split_conditioning_sigma_field_hash
                != self.certificate_conditioning_sigma_field_hash
            ):
                raise ValueError(
                    "conditional nuisance handling requires matching sigma-fields"
                )
            if self.uniform_worst_case_proof is not None:
                raise ValueError(
                    "conditional nuisance handling cannot carry worst-case proof"
                )
        elif self.uniform_worst_case_proof is None:
            raise ValueError(
                "uniform worst-case nuisance handling requires a proof artifact"
            )
        return self


class SplitRelationAssessment(FrozenContractModel):
    schema_id: Literal["d2t_rna.split_relation_assessment"] = (
        "d2t_rna.split_relation_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    split_relation_hash: Sha256Hex
    disposition: SplitDisposition
    observed_zero_dependency_overlap: StrictBool
    formal_independence_established: Literal[False] = False
    finite_population_joint_law_required: StrictBool
    nuisance_handling_mode: NuisanceHandlingMode | None
    nuisance_handling_evidence_hash: Sha256Hex | None
    risk_certificate_must_abstain: Literal[True] = True
    proof_replay_required: StrictBool
    reason_codes: tuple[StrictStr, ...]


def _assessment(
    spec: SplitRelationSpec,
    disposition: SplitDisposition,
    *,
    zero_overlap: bool,
    finite_population: bool,
    proof_replay: bool,
    reasons: tuple[str, ...],
    nuisance_handling: NuisanceHandlingEvidence | None = None,
) -> SplitRelationAssessment:
    return SplitRelationAssessment(
        split_relation_hash=canonical_sha256(spec),
        disposition=disposition,
        observed_zero_dependency_overlap=zero_overlap,
        formal_independence_established=False,
        finite_population_joint_law_required=finite_population,
        nuisance_handling_mode=(
            nuisance_handling.mode if nuisance_handling is not None else None
        ),
        nuisance_handling_evidence_hash=(
            canonical_sha256(nuisance_handling)
            if nuisance_handling is not None
            else None
        ),
        risk_certificate_must_abstain=True,
        proof_replay_required=proof_replay,
        reason_codes=reasons,
    )


def assess_split_relation(
    split_relation: SplitRelationSpec,
    registry: TrustedSemanticRegistry,
    *,
    expected_conditioning_sigma_field_hash: str | None = None,
    nuisance_handling: NuisanceHandlingEvidence | None = None,
) -> SplitRelationAssessment:
    """Classify a split while refusing to infer independence from overlap."""

    if type(split_relation) is not SplitRelationSpec:
        raise TypeError("split_relation must be exactly SplitRelationSpec")
    if nuisance_handling is not None and type(
        nuisance_handling
    ) is not NuisanceHandlingEvidence:
        raise TypeError(
            "nuisance_handling must be exactly NuisanceHandlingEvidence"
        )
    spec = strict_revalidate_contract_model(split_relation)
    trusted = ensure_trusted_task2_registry(registry)
    handling = (
        strict_revalidate_contract_model(nuisance_handling)
        if nuisance_handling is not None
        else None
    )
    if (
        handling is not None
        and spec.split_relation
        is not SplitRelation.CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE
    ):
        raise SplitSemanticError(
            "nuisance handling evidence is only valid for conditional splits"
        )
    try:
        resolve_registry_ref(
            spec.dependency_unit_level,
            trusted,
            SemanticRegistryRole.DEPENDENCY_UNIT,
        )
        for overlap in spec.overlap_counts:
            if overlap.dependency_unit_level != spec.dependency_unit_level:
                raise SplitSemanticError(
                    "overlap dependency-unit level does not match split level"
                )
            resolve_registry_ref(
                overlap.dependency_unit_level,
                trusted,
                SemanticRegistryRole.DEPENDENCY_UNIT,
            )
    except RegistryResolutionError as exc:
        raise SplitSemanticError(
            f"dependency-unit registry resolution failed: {exc}"
        ) from exc

    overlap_pairs = tuple(
        (item.left_partition_id, item.right_partition_id)
        for item in spec.overlap_counts
    )
    if len(set(overlap_pairs)) != len(overlap_pairs):
        raise SplitSemanticError("duplicate overlap partition pair")
    if spec.overlap_counts and not any(
        pair in {
            ("planning", "certificate"),
            ("certificate", "planning"),
        }
        for pair in overlap_pairs
    ):
        raise SplitSemanticError(
            "overlap evidence does not include planning/certificate pair"
        )
    zero_overlap = bool(spec.overlap_counts) and all(
        overlap.count == 0 for overlap in spec.overlap_counts
    )
    nuisance_binding_reasons: list[str] = []
    if handling is not None:
        if (
            handling.split_conditioning_sigma_field_hash
            != spec.conditioning_sigma_field_hash
        ):
            nuisance_binding_reasons.append(
                "NUISANCE_SPLIT_SIGMA_FIELD_MISMATCH"
            )
        if (
            expected_conditioning_sigma_field_hash is None
            or handling.certificate_conditioning_sigma_field_hash
            != expected_conditioning_sigma_field_hash
        ):
            nuisance_binding_reasons.append(
                "NUISANCE_CERTIFICATE_SIGMA_FIELD_MISMATCH"
            )
    elif (
        expected_conditioning_sigma_field_hash is not None
        and spec.conditioning_sigma_field_hash
        != expected_conditioning_sigma_field_hash
    ):
        nuisance_binding_reasons.append("CONDITIONING_SIGMA_FIELD_MISMATCH")
    if nuisance_binding_reasons:
        return _assessment(
            spec,
            SplitDisposition.ABSTAIN,
            zero_overlap=zero_overlap,
            finite_population=False,
            proof_replay=True,
            reasons=tuple(nuisance_binding_reasons),
            nuisance_handling=handling,
        )

    if spec.split_relation in {
        SplitRelation.INDEPENDENT_LIBRARIES,
        SplitRelation.CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE,
    }:
        reasons: list[str] = []
        if spec.selection_inference_independence_proof is None:
            reasons.append("INDEPENDENCE_PROOF_MISSING")
        if (
            spec.planning_partition_hash
            == spec.certificate_partition_hash
        ):
            reasons.append("PLANNING_AND_CERTIFICATE_PARTITIONS_IDENTICAL")
        if not zero_overlap:
            reasons.append("ZERO_DEPENDENCY_UNIT_OVERLAP_NOT_ESTABLISHED")
        if reasons:
            return _assessment(
                spec,
                SplitDisposition.ABSTAIN,
                zero_overlap=zero_overlap,
                finite_population=False,
                proof_replay=True,
                reasons=tuple(reasons),
                nuisance_handling=handling,
            )
        return _assessment(
            spec,
            SplitDisposition.INDEPENDENCE_INPUTS_BOUND_PENDING_PROOF,
            zero_overlap=True,
            finite_population=False,
            proof_replay=True,
            reasons=(
                "ZERO_OVERLAP_IS_NOT_AN_INDEPENDENCE_PROOF",
                "SELECTION_INFERENCE_PROOF_REPLAY_PENDING",
            )
            + (
                (
                    "UNIFORM_WORST_CASE_INPUTS_BOUND_PENDING_PROOF",
                )
                if (
                    handling is not None
                    and handling.mode
                    is NuisanceHandlingMode.UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE
                )
                else (
                    "CERTIFICATE_CONDITIONS_ON_REGISTERED_NUISANCE",
                )
            ),
            nuisance_handling=handling,
        )

    if (
        spec.split_relation
        is SplitRelation.RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET
    ):
        if spec.selection_inference_independence_proof is not None:
            raise SplitSemanticError(
                "random finite partition cannot carry an independent-split proof"
            )
        if spec.split_seed is None:
            return _assessment(
                spec,
                SplitDisposition.ABSTAIN,
                zero_overlap=zero_overlap,
                finite_population=True,
                proof_replay=False,
                reasons=("RANDOM_PARTITION_SEED_MISSING",),
            )
        if spec.split_seed < 0:
            return _assessment(
                spec,
                SplitDisposition.ABSTAIN,
                zero_overlap=zero_overlap,
                finite_population=True,
                proof_replay=False,
                reasons=("RANDOM_PARTITION_SEED_NEGATIVE",),
            )
        if (
            spec.planning_partition_hash
            == spec.certificate_partition_hash
        ):
            return _assessment(
                spec,
                SplitDisposition.ABSTAIN,
                zero_overlap=zero_overlap,
                finite_population=True,
                proof_replay=False,
                reasons=("PLANNING_AND_CERTIFICATE_PARTITIONS_IDENTICAL",),
            )
        return _assessment(
            spec,
            SplitDisposition.FINITE_POPULATION_JOINT_LAW_ONLY,
            zero_overlap=zero_overlap,
            finite_population=True,
            proof_replay=False,
            reasons=(
                "FINITE_POPULATION_JOINT_LAW_ARTIFACT_REQUIRED",
                "IID_OR_INDEPENDENT_SERIALIZATION_FORBIDDEN",
            ),
        )

    return _assessment(
        spec,
        SplitDisposition.SHARED_OR_UNKNOWN_DEPENDENCE,
        zero_overlap=zero_overlap,
        finite_population=False,
        proof_replay=True,
        reasons=("SHARED_OR_UNKNOWN_DEPENDENCE_FORCES_ABSTAIN",),
    )


def require_independent_split(
    assessment: SplitRelationAssessment,
) -> None:
    """Fail unless a later trusted proof engine has established independence."""

    if type(assessment) is not SplitRelationAssessment:
        raise TypeError("assessment must be exactly SplitRelationAssessment")
    rebuilt = strict_revalidate_contract_model(assessment)
    raise SplitSemanticError(
        f"{rebuilt.disposition.value} is not an independent split; "
        "Task 2 has no verified-independent credential type"
    )
