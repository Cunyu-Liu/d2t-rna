from __future__ import annotations

import pytest

from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
    TrustedSemanticRegistry,
)
from d2t_rna.probability.scopes import (
    ProbabilityScopeDisposition,
    ScopeSemanticError,
    SyntheticKnownChannelPrerequisites,
    WithinLibraryPrerequisites,
    assess_probability_scope,
)


def test_observed_dataset_qa_rejects_formal_scientific_guarantee(
    registry: TrustedSemanticRegistry,
    empirical_spec: ProbabilitySpaceSpec,
) -> None:
    invalid = empirical_spec.model_copy(
        update={"formal_scientific_risk_guarantee": True}
    )
    with pytest.raises(
        ScopeSemanticError,
        match="empirical QA cannot authorize a formal scientific risk guarantee",
    ):
        assess_probability_scope(invalid, registry)


def test_observed_dataset_qa_is_fixed_empirical_target_only(
    registry: TrustedSemanticRegistry,
    empirical_spec: ProbabilitySpaceSpec,
) -> None:
    result = assess_probability_scope(empirical_spec, registry)
    assert result.disposition is ProbabilityScopeDisposition.EMPIRICAL_QA_ONLY
    assert result.risk_certificate_must_abstain is True
    assert result.formal_scientific_risk_authorized is False
    assert result.target_description == (
        "FULL_OBSERVED_DATASET_EMPIRICAL_FEATURE_DISTRIBUTION"
    )


def test_observed_dataset_qa_rejects_latent_target_splicing(
    registry: TrustedSemanticRegistry,
    empirical_spec: ProbabilitySpaceSpec,
) -> None:
    invalid = empirical_spec.model_copy(
        update={
            "target": registry.ref(
                "target.within_realized_library_latent_ensemble",
                SemanticRegistryRole.WITHIN_LIBRARY_TARGET,
            )
        }
    )
    with pytest.raises(ScopeSemanticError, match="observed target"):
        assess_probability_scope(invalid, registry)


def test_within_library_missing_observation_model_forces_abstain(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
) -> None:
    missing = within_spec.model_copy(update={"observation_model_hash": None})
    result = assess_probability_scope(missing, registry, within_prerequisites)
    assert result.disposition is ProbabilityScopeDisposition.ABSTAIN
    assert "OBSERVATION_MODEL_MISSING" in result.reason_codes


def test_within_library_missing_registered_prerequisites_forces_abstain(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
) -> None:
    result = assess_probability_scope(within_spec, registry)
    assert result.disposition is ProbabilityScopeDisposition.ABSTAIN
    assert "WITHIN_LIBRARY_PREREQUISITES_MISSING" in result.reason_codes


def test_complete_within_library_inputs_remain_pending_proof_replay(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
) -> None:
    result = assess_probability_scope(
        within_spec,
        registry,
        within_prerequisites,
    )
    assert result.disposition is (
        ProbabilityScopeDisposition.WITHIN_LIBRARY_INPUTS_BOUND_PENDING_PROOF
    )
    assert result.risk_certificate_must_abstain is True
    assert result.formal_scientific_risk_authorized is False


def test_within_library_target_role_splicing_is_rejected(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
) -> None:
    invalid = within_spec.model_copy(
        update={
            "target": registry.ref(
                "target.full_observed_dataset_empirical_feature_distribution",
                SemanticRegistryRole.OBSERVED_TARGET,
            )
        }
    )
    with pytest.raises(ScopeSemanticError, match="within-library target"):
        assess_probability_scope(invalid, registry, within_prerequisites)


def test_new_library_scope_is_hard_no_go(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
) -> None:
    invalid = within_spec.model_copy(
        update={
            "probability_scope": (
                ProbabilityScope.NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL
            )
        }
    )
    result = assess_probability_scope(invalid, registry)
    assert result.disposition is ProbabilityScopeDisposition.NEW_LIBRARY_HARD_NO_GO
    assert result.risk_certificate_must_abstain is True
    assert result.formal_scientific_risk_authorized is False


def test_synthetic_scope_requires_a_registered_known_channel_bundle(
    registry: TrustedSemanticRegistry,
    synthetic_spec: ProbabilitySpaceSpec,
    synthetic_prerequisites: SyntheticKnownChannelPrerequisites,
) -> None:
    result = assess_probability_scope(
        synthetic_spec,
        registry,
        synthetic_prerequisites,
    )
    assert result.disposition is (
        ProbabilityScopeDisposition.SYNTHETIC_PENDING_TASK_4
    )
    assert result.risk_certificate_must_abstain is True
    assert result.formal_scientific_risk_authorized is False


def test_synthetic_target_splicing_is_rejected(
    registry: TrustedSemanticRegistry,
    synthetic_spec: ProbabilitySpaceSpec,
    synthetic_prerequisites: SyntheticKnownChannelPrerequisites,
) -> None:
    invalid = synthetic_spec.model_copy(
        update={
            "target": registry.ref(
                "target.within_realized_library_latent_ensemble",
                SemanticRegistryRole.WITHIN_LIBRARY_TARGET,
            )
        }
    )
    with pytest.raises(ScopeSemanticError, match="synthetic target"):
        assess_probability_scope(
            invalid,
            registry,
            synthetic_prerequisites,
        )
