"""Fail-closed semantics for the four registered probability scopes."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import StrictBool, StrictStr

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.primitives import (
    ProofArtifactRef,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec

from .registry import (
    RegistryResolutionError,
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    ensure_trusted_task2_registry,
    require_registered_id,
    resolve_registry_ref,
)


class ScopeSemanticError(ValueError):
    """Raised for a contradictory or semantically spliced scope."""


class ProbabilityScopeDisposition(str, Enum):
    EMPIRICAL_QA_ONLY = "EMPIRICAL_QA_ONLY"
    WITHIN_LIBRARY_INPUTS_BOUND_PENDING_PROOF = (
        "WITHIN_LIBRARY_INPUTS_BOUND_PENDING_PROOF"
    )
    SYNTHETIC_PENDING_TASK_4 = "SYNTHETIC_PENDING_TASK_4"
    NEW_LIBRARY_HARD_NO_GO = "NEW_LIBRARY_HARD_NO_GO"
    ABSTAIN = "ABSTAIN"


class WithinLibraryPrerequisites(FrozenContractModel):
    """Registered within-library inputs; references are not proof verdicts."""

    schema_id: Literal["d2t_rna.within_library_prerequisites"] = (
        "d2t_rna.within_library_prerequisites"
    )
    schema_version: Literal["1.0"] = "1.0"
    realized_library_object_id: RegisteredId
    realized_library_object_hash: Sha256Hex
    sampling_law_hash: Sha256Hex
    observation_model_hash: Sha256Hex
    conditioning_sigma_field_hash: Sha256Hex
    same_library_sampling_proof: ProofArtifactRef
    observation_model_proof: ProofArtifactRef
    weighting_sequencing_law: RegistryRef
    nuisance_parameter_space_hash: Sha256Hex
    nuisance_definition_proof: ProofArtifactRef
    duplicate_ess_policy: RegistryRef
    uniform_confidence_set_proof: ProofArtifactRef
    target_binding_proof: ProofArtifactRef


class SyntheticKnownChannelPrerequisites(FrozenContractModel):
    """Pinned synthetic channel inputs awaiting Task 4 exact proof replay."""

    schema_id: Literal["d2t_rna.synthetic_known_channel_prerequisites"] = (
        "d2t_rna.synthetic_known_channel_prerequisites"
    )
    schema_version: Literal["1.0"] = "1.0"
    known_channel_object_id: RegisteredId
    known_channel_object_hash: Sha256Hex
    sampling_law_hash: Sha256Hex
    support_definition_hash: Sha256Hex
    channel_registration_proof: ProofArtifactRef


ScopePrerequisites = (
    WithinLibraryPrerequisites | SyntheticKnownChannelPrerequisites
)


class ProbabilityScopeAssessment(FrozenContractModel):
    schema_id: Literal["d2t_rna.probability_scope_assessment"] = (
        "d2t_rna.probability_scope_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_space_hash: Sha256Hex
    disposition: ProbabilityScopeDisposition
    risk_certificate_must_abstain: Literal[True] = True
    formal_scientific_risk_authorized: Literal[False] = False
    proof_replay_required: StrictBool
    target_description: StrictStr
    reason_codes: tuple[StrictStr, ...]


def _assessment(
    spec: ProbabilitySpaceSpec,
    disposition: ProbabilityScopeDisposition,
    *,
    target_description: str,
    reasons: tuple[str, ...],
    proof_replay_required: bool,
) -> ProbabilityScopeAssessment:
    return ProbabilityScopeAssessment(
        probability_space_hash=canonical_sha256(spec),
        disposition=disposition,
        risk_certificate_must_abstain=True,
        formal_scientific_risk_authorized=False,
        proof_replay_required=proof_replay_required,
        target_description=target_description,
        reason_codes=reasons,
    )


def _resolve_or_raise(
    reference: RegistryRef,
    registry: TrustedSemanticRegistry,
    role: SemanticRegistryRole,
    label: str,
) -> None:
    try:
        resolve_registry_ref(reference, registry, role)
    except RegistryResolutionError as exc:
        raise ScopeSemanticError(f"{label} registry resolution failed: {exc}") from exc


def _validate_empirical_scope(
    spec: ProbabilitySpaceSpec,
    registry: TrustedSemanticRegistry,
) -> ProbabilityScopeAssessment:
    if spec.formal_scientific_risk_guarantee:
        raise ScopeSemanticError(
            "empirical QA cannot authorize a formal scientific risk guarantee"
        )
    if len(spec.fixed_objects) != 1:
        raise ScopeSemanticError(
            "observed QA fixed objects must be exactly the complete dataset D_obs"
        )
    if len(spec.random_objects) != 1:
        raise ScopeSemanticError(
            "observed QA random objects must be exactly subsampling index I"
        )
    fixed = spec.fixed_objects[0]
    random = spec.random_objects[0]
    try:
        require_registered_id(
            fixed.object_id,
            registry,
            SemanticRegistryRole.OBSERVED_DATASET,
        )
        require_registered_id(
            random.object_id,
            registry,
            SemanticRegistryRole.SUBSAMPLING_INDEX,
        )
    except RegistryResolutionError as exc:
        raise ScopeSemanticError(
            f"observed dataset/random-object registration failed: {exc}"
        ) from exc
    _resolve_or_raise(
        spec.estimand,
        registry,
        SemanticRegistryRole.OBSERVED_ESTIMAND,
        "observed estimand",
    )
    _resolve_or_raise(
        spec.target,
        registry,
        SemanticRegistryRole.OBSERVED_TARGET,
        "observed target",
    )
    return _assessment(
        spec,
        ProbabilityScopeDisposition.EMPIRICAL_QA_ONLY,
        target_description=(
            "FULL_OBSERVED_DATASET_EMPIRICAL_FEATURE_DISTRIBUTION"
        ),
        reasons=(
            "D_OBS_COMMITMENT_PRESENT",
            "ONLY_SUBSAMPLING_INDEX_RANDOM",
            "NO_LATENT_OR_NEW_LIBRARY_TARGET",
            "OBSERVED_DATASET_CLOSURE_NOT_ESTABLISHED_IN_TASK_2",
        ),
        proof_replay_required=False,
    )


def _validate_within_library_scope(
    spec: ProbabilitySpaceSpec,
    registry: TrustedSemanticRegistry,
    prerequisites: ScopePrerequisites | None,
) -> ProbabilityScopeAssessment:
    _resolve_or_raise(
        spec.estimand,
        registry,
        SemanticRegistryRole.WITHIN_LIBRARY_ESTIMAND,
        "within-library estimand",
    )
    _resolve_or_raise(
        spec.target,
        registry,
        SemanticRegistryRole.WITHIN_LIBRARY_TARGET,
        "within-library target",
    )
    reasons: list[str] = []
    if not spec.formal_scientific_risk_guarantee:
        reasons.append("FORMAL_GUARANTEE_FLAG_FALSE")
    if spec.observation_model_hash is None:
        reasons.append("OBSERVATION_MODEL_MISSING")
    if prerequisites is None:
        reasons.append("WITHIN_LIBRARY_PREREQUISITES_MISSING")
    elif type(prerequisites) is not WithinLibraryPrerequisites:
        reasons.append("WITHIN_LIBRARY_PREREQUISITE_TYPE_MISMATCH")
    if reasons:
        return _assessment(
            spec,
            ProbabilityScopeDisposition.ABSTAIN,
            target_description="WITHIN_REALIZED_LIBRARY_LATENT_ENSEMBLE",
            reasons=tuple(reasons),
            proof_replay_required=True,
        )

    assert type(prerequisites) is WithinLibraryPrerequisites
    rebuilt = strict_revalidate_contract_model(prerequisites)
    fixed_matches = tuple(
        item
        for item in spec.fixed_objects
        if item.object_id == rebuilt.realized_library_object_id
    )
    binding_reasons: list[str] = []
    if len(fixed_matches) != 1:
        binding_reasons.append("REALIZED_LIBRARY_OBJECT_NOT_FIXED_EXACTLY_ONCE")
    elif fixed_matches[0].object_hash != rebuilt.realized_library_object_hash:
        binding_reasons.append("REALIZED_LIBRARY_OBJECT_HASH_MISMATCH")
    if rebuilt.sampling_law_hash != spec.sampling_law_hash:
        binding_reasons.append("SAMPLING_LAW_HASH_MISMATCH")
    if rebuilt.observation_model_hash != spec.observation_model_hash:
        binding_reasons.append("OBSERVATION_MODEL_HASH_MISMATCH")
    if (
        rebuilt.conditioning_sigma_field_hash
        != spec.conditioning_sigma_field_hash
    ):
        binding_reasons.append("CONDITIONING_SIGMA_FIELD_HASH_MISMATCH")
    if binding_reasons:
        return _assessment(
            spec,
            ProbabilityScopeDisposition.ABSTAIN,
            target_description="WITHIN_REALIZED_LIBRARY_LATENT_ENSEMBLE",
            reasons=tuple(binding_reasons),
            proof_replay_required=True,
        )
    try:
        resolve_registry_ref(
            rebuilt.weighting_sequencing_law,
            registry,
            SemanticRegistryRole.OBSERVATION_WEIGHTING_LAW,
        )
        resolve_registry_ref(
            rebuilt.duplicate_ess_policy,
            registry,
            SemanticRegistryRole.DUPLICATE_ESS_POLICY,
        )
    except RegistryResolutionError as exc:
        raise ScopeSemanticError(
            f"within-library prerequisite registration failed: {exc}"
        ) from exc
    return _assessment(
        spec,
        (
            ProbabilityScopeDisposition
            .WITHIN_LIBRARY_INPUTS_BOUND_PENDING_PROOF
        ),
        target_description="WITHIN_REALIZED_LIBRARY_LATENT_ENSEMBLE",
        reasons=(
            "SAME_LIBRARY_INPUTS_HASH_BOUND",
            "OBSERVATION_AND_WEIGHTING_INPUTS_HASH_BOUND",
            "NUISANCE_AND_DUPLICATE_POLICY_HASH_BOUND",
            "PROOF_REPLAY_NOT_YET_ESTABLISHED",
        ),
        proof_replay_required=True,
    )


def _validate_synthetic_scope(
    spec: ProbabilitySpaceSpec,
    registry: TrustedSemanticRegistry,
    prerequisites: ScopePrerequisites | None,
) -> ProbabilityScopeAssessment:
    _resolve_or_raise(
        spec.estimand,
        registry,
        SemanticRegistryRole.SYNTHETIC_ESTIMAND,
        "synthetic estimand",
    )
    _resolve_or_raise(
        spec.target,
        registry,
        SemanticRegistryRole.SYNTHETIC_TARGET,
        "synthetic target",
    )
    reasons: list[str] = []
    if not spec.formal_scientific_risk_guarantee:
        reasons.append("FORMAL_GUARANTEE_FLAG_FALSE")
    if prerequisites is None:
        reasons.append("SYNTHETIC_KNOWN_CHANNEL_PREREQUISITES_MISSING")
    elif type(prerequisites) is not SyntheticKnownChannelPrerequisites:
        reasons.append("SYNTHETIC_PREREQUISITE_TYPE_MISMATCH")
    if reasons:
        return _assessment(
            spec,
            ProbabilityScopeDisposition.ABSTAIN,
            target_description="SYNTHETIC_KNOWN_CHANNEL",
            reasons=tuple(reasons),
            proof_replay_required=True,
        )

    assert type(prerequisites) is SyntheticKnownChannelPrerequisites
    rebuilt = strict_revalidate_contract_model(prerequisites)
    try:
        require_registered_id(
            rebuilt.known_channel_object_id,
            registry,
            SemanticRegistryRole.SYNTHETIC_KNOWN_CHANNEL,
        )
    except RegistryResolutionError as exc:
        raise ScopeSemanticError(
            f"synthetic known-channel registration failed: {exc}"
        ) from exc
    fixed_matches = tuple(
        item
        for item in spec.fixed_objects
        if item.object_id == rebuilt.known_channel_object_id
    )
    binding_reasons: list[str] = []
    if len(fixed_matches) != 1:
        binding_reasons.append("KNOWN_CHANNEL_OBJECT_NOT_FIXED_EXACTLY_ONCE")
    elif fixed_matches[0].object_hash != rebuilt.known_channel_object_hash:
        binding_reasons.append("KNOWN_CHANNEL_OBJECT_HASH_MISMATCH")
    if spec.observation_model_hash != rebuilt.known_channel_object_hash:
        binding_reasons.append("KNOWN_CHANNEL_OBSERVATION_MODEL_HASH_MISMATCH")
    if spec.sampling_law_hash != rebuilt.sampling_law_hash:
        binding_reasons.append("SYNTHETIC_SAMPLING_LAW_HASH_MISMATCH")
    if binding_reasons:
        return _assessment(
            spec,
            ProbabilityScopeDisposition.ABSTAIN,
            target_description="SYNTHETIC_KNOWN_CHANNEL",
            reasons=tuple(binding_reasons),
            proof_replay_required=True,
        )
    return _assessment(
        spec,
        ProbabilityScopeDisposition.SYNTHETIC_PENDING_TASK_4,
        target_description="SYNTHETIC_KNOWN_CHANNEL",
        reasons=(
            "KNOWN_CHANNEL_INPUTS_HASH_BOUND",
            "EXACT_PROOF_ENGINE_PENDING_TASK_4",
        ),
        proof_replay_required=True,
    )


def assess_probability_scope(
    probability_space: ProbabilitySpaceSpec,
    registry: TrustedSemanticRegistry,
    prerequisites: ScopePrerequisites | None = None,
) -> ProbabilityScopeAssessment:
    """Assess one scope without upgrading references into scientific proof."""

    if type(probability_space) is not ProbabilitySpaceSpec:
        raise TypeError("probability_space must be exactly ProbabilitySpaceSpec")
    if prerequisites is not None and type(prerequisites) not in {
        WithinLibraryPrerequisites,
        SyntheticKnownChannelPrerequisites,
    }:
        raise TypeError("prerequisites must be an exact registered Task 2 type")
    spec = strict_revalidate_contract_model(probability_space)
    trusted = ensure_trusted_task2_registry(registry)
    if (
        spec.probability_scope
        is ProbabilityScope.FINITE_OBSERVED_DATASET_SUBSAMPLING
    ):
        if prerequisites is not None:
            raise ScopeSemanticError(
                "observed empirical QA cannot carry latent/synthetic prerequisites"
            )
        return _validate_empirical_scope(spec, trusted)
    if (
        spec.probability_scope
        is ProbabilityScope.WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL
    ):
        return _validate_within_library_scope(spec, trusted, prerequisites)
    if (
        spec.probability_scope
        is ProbabilityScope.NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL
    ):
        return _assessment(
            spec,
            ProbabilityScopeDisposition.NEW_LIBRARY_HARD_NO_GO,
            target_description="NEW_LIBRARY_ROBUST_TARGET_FORBIDDEN_IN_V1",
            reasons=("NO_GO_NEW_LIBRARY_RISK_CERTIFICATE",),
            proof_replay_required=True,
        )
    return _validate_synthetic_scope(spec, trusted, prerequisites)
