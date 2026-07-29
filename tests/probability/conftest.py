from __future__ import annotations

from pathlib import Path

import pytest

from d2t_rna.contracts.enums import ProbabilityScope, SplitRelation
from d2t_rna.contracts.primitives import (
    ObjectCommitment,
    OverlapCount,
    ProofArtifactRef,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.splits import SplitRelationSpec
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    load_trusted_task2_registry,
)
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
    WithinLibraryPrerequisites,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64


@pytest.fixture(scope="session")
def registry() -> TrustedSemanticRegistry:
    manifest = Path(__file__).parents[2] / "manifests" / "task2_semantic_registry.json"
    return load_trusted_task2_registry(manifest.read_bytes())


@pytest.fixture
def empirical_spec(registry: TrustedSemanticRegistry) -> ProbabilitySpaceSpec:
    return ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.FINITE_OBSERVED_DATASET_SUBSAMPLING,
        fixed_objects=(
            ObjectCommitment(object_id="dataset.D_obs", object_hash=SHA_A),
        ),
        random_objects=(
            ObjectCommitment(object_id="subsample.index.I", object_hash=SHA_B),
        ),
        sampling_law_hash=SHA_C,
        parameter_space_hash=SHA_D,
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=None,
        estimand=registry.ref(
            "estimand.empirical_feature_distribution",
            SemanticRegistryRole.OBSERVED_ESTIMAND,
        ),
        target=registry.ref(
            "target.full_observed_dataset_empirical_feature_distribution",
            SemanticRegistryRole.OBSERVED_TARGET,
        ),
        formal_scientific_risk_guarantee=False,
    )


@pytest.fixture
def within_spec(registry: TrustedSemanticRegistry) -> ProbabilitySpaceSpec:
    return ProbabilitySpaceSpec(
        probability_scope=(
            ProbabilityScope.WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL
        ),
        fixed_objects=(
            ObjectCommitment(
                object_id="library.realized.001",
                object_hash=SHA_A,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="observation.read_sampling",
                object_hash=SHA_B,
            ),
        ),
        sampling_law_hash=SHA_C,
        parameter_space_hash=SHA_D,
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=SHA_F,
        estimand=registry.ref(
            "estimand.within_realized_library_latent_ensemble",
            SemanticRegistryRole.WITHIN_LIBRARY_ESTIMAND,
        ),
        target=registry.ref(
            "target.within_realized_library_latent_ensemble",
            SemanticRegistryRole.WITHIN_LIBRARY_TARGET,
        ),
        formal_scientific_risk_guarantee=True,
    )


@pytest.fixture
def within_prerequisites(
    registry: TrustedSemanticRegistry,
) -> WithinLibraryPrerequisites:
    return WithinLibraryPrerequisites(
        realized_library_object_id="library.realized.001",
        realized_library_object_hash=SHA_A,
        sampling_law_hash=SHA_C,
        observation_model_hash=SHA_F,
        conditioning_sigma_field_hash=SHA_E,
        same_library_sampling_proof=ProofArtifactRef(
            proof_id="proof.same_library_sampling",
            artifact_hash=SHA_A,
        ),
        observation_model_proof=ProofArtifactRef(
            proof_id="proof.observation_model",
            artifact_hash=SHA_B,
        ),
        weighting_sequencing_law=registry.ref(
            "observation.weighting.registered",
            SemanticRegistryRole.OBSERVATION_WEIGHTING_LAW,
        ),
        nuisance_parameter_space_hash=SHA_D,
        nuisance_definition_proof=ProofArtifactRef(
            proof_id="proof.nuisance_definition",
            artifact_hash=SHA_C,
        ),
        duplicate_ess_policy=registry.ref(
            "duplicate_ess.registered",
            SemanticRegistryRole.DUPLICATE_ESS_POLICY,
        ),
        uniform_confidence_set_proof=ProofArtifactRef(
            proof_id="proof.uniform_confidence_set",
            artifact_hash=SHA_D,
        ),
        target_binding_proof=ProofArtifactRef(
            proof_id="proof.target_binding",
            artifact_hash=SHA_E,
        ),
    )


@pytest.fixture
def synthetic_spec(
    registry: TrustedSemanticRegistry,
) -> ProbabilitySpaceSpec:
    return ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(
                object_id="channel.synthetic.known",
                object_hash=SHA_A,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="synthetic.observation",
                object_hash=SHA_B,
            ),
        ),
        sampling_law_hash=SHA_C,
        parameter_space_hash=SHA_D,
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=SHA_A,
        estimand=registry.ref(
            "estimand.synthetic_known_channel_decision_risk",
            SemanticRegistryRole.SYNTHETIC_ESTIMAND,
        ),
        target=registry.ref(
            "target.synthetic_known_channel_risk_coverage",
            SemanticRegistryRole.SYNTHETIC_TARGET,
        ),
        formal_scientific_risk_guarantee=True,
    )


@pytest.fixture
def synthetic_prerequisites() -> SyntheticKnownChannelPrerequisites:
    return SyntheticKnownChannelPrerequisites(
        known_channel_object_id="channel.synthetic.known",
        known_channel_object_hash=SHA_A,
        sampling_law_hash=SHA_C,
        support_definition_hash=SHA_F,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.synthetic_channel_registration",
            artifact_hash=SHA_D,
        ),
    )


@pytest.fixture
def conditional_split(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
) -> SplitRelationSpec:
    dependency = registry.ref(
        "dependency.umi_family",
        SemanticRegistryRole.DEPENDENCY_UNIT,
    )
    return SplitRelationSpec(
        split_relation=(
            SplitRelation.CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE
        ),
        dependency_unit_level=dependency,
        planning_partition_hash=SHA_A,
        certificate_partition_hash=SHA_B,
        conditioning_sigma_field_hash=within_spec.conditioning_sigma_field_hash,
        selection_inference_independence_proof=ProofArtifactRef(
            proof_id="proof.conditional_independence",
            artifact_hash=SHA_C,
        ),
        overlap_counts=(
            OverlapCount(
                left_partition_id="planning",
                right_partition_id="certificate",
                dependency_unit_level=dependency,
                count=0,
            ),
        ),
        split_seed=11,
    )
