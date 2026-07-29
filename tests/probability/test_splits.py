from __future__ import annotations

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.enums import SplitRelation
from d2t_rna.contracts.primitives import RegistryRef
from d2t_rna.contracts.splits import SplitRelationSpec
from d2t_rna.probability.registry import TrustedSemanticRegistry
from d2t_rna.probability.splits import (
    NuisanceHandlingEvidence,
    NuisanceHandlingMode,
    SplitDisposition,
    SplitSemanticError,
    assess_split_relation,
    require_independent_split,
)

from .conftest import SHA_A, SHA_E, SHA_F


def test_model_conditional_split_missing_independence_proof_abstains(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    missing = conditional_split.model_copy(
        update={"selection_inference_independence_proof": None}
    )
    result = assess_split_relation(missing, registry)
    assert result.disposition is SplitDisposition.ABSTAIN
    assert "INDEPENDENCE_PROOF_MISSING" in result.reason_codes


def test_zero_overlap_is_not_treated_as_independence(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    result = assess_split_relation(conditional_split, registry)
    assert result.disposition is (
        SplitDisposition.INDEPENDENCE_INPUTS_BOUND_PENDING_PROOF
    )
    assert result.observed_zero_dependency_overlap is True
    assert result.formal_independence_established is False
    assert result.risk_certificate_must_abstain is True


def test_random_finite_partition_never_serializes_as_independent(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    finite = conditional_split.model_copy(
        update={
            "split_relation": (
                SplitRelation.RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET
            ),
            "selection_inference_independence_proof": None,
            "split_seed": 19,
        }
    )
    result = assess_split_relation(finite, registry)
    assert result.disposition is SplitDisposition.FINITE_POPULATION_JOINT_LAW_ONLY
    assert result.finite_population_joint_law_required is True
    assert result.formal_independence_established is False
    with pytest.raises(SplitSemanticError, match="not an independent split"):
        require_independent_split(result)


def test_conditioning_sigma_field_mismatch_forces_abstain(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    result = assess_split_relation(
        conditional_split,
        registry,
        expected_conditioning_sigma_field_hash=SHA_A,
    )
    assert result.disposition is SplitDisposition.ABSTAIN
    assert "CONDITIONING_SIGMA_FIELD_MISMATCH" in result.reason_codes


def test_conditional_split_can_bind_uniform_worst_case_over_nuisance(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    evidence = NuisanceHandlingEvidence(
        mode=NuisanceHandlingMode.UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE,
        split_conditioning_sigma_field_hash=SHA_E,
        certificate_conditioning_sigma_field_hash=SHA_F,
        nuisance_parameter_space_hash=SHA_A,
        uniform_worst_case_proof=conditional_split.selection_inference_independence_proof,
    )
    result = assess_split_relation(
        conditional_split,
        registry,
        expected_conditioning_sigma_field_hash=SHA_F,
        nuisance_handling=evidence,
    )
    assert result.disposition is (
        SplitDisposition.INDEPENDENCE_INPUTS_BOUND_PENDING_PROOF
    )
    assert result.nuisance_handling_mode is (
        NuisanceHandlingMode.UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE
    )
    assert result.formal_independence_established is False


def test_dependency_unit_hash_splicing_is_rejected(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    invalid = conditional_split.model_copy(
        update={
            "dependency_unit_level": RegistryRef(
                registry_id="dependency.umi_family",
                registry_hash="0" * 64,
            )
        }
    )
    with pytest.raises(SplitSemanticError, match="registry resolution"):
        assess_split_relation(invalid, registry)


def test_caller_cannot_forge_a_verified_independent_assessment(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    pending = assess_split_relation(conditional_split, registry)
    forged = pending.model_copy(
        update={"formal_independence_established": True}
    )
    with pytest.raises(ValidationError, match="literal_error"):
        require_independent_split(forged)
    constructed = type(pending).model_construct(
        **{
            **pending.model_dump(mode="python"),
            "formal_independence_established": True,
        }
    )
    with pytest.raises(ValidationError, match="literal_error"):
        require_independent_split(constructed)


def test_duplicate_overlap_pair_is_rejected(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    duplicated = conditional_split.model_copy(
        update={
            "overlap_counts": (
                conditional_split.overlap_counts[0],
                conditional_split.overlap_counts[0],
            )
        }
    )
    with pytest.raises(SplitSemanticError, match="duplicate overlap"):
        assess_split_relation(duplicated, registry)


def test_negative_random_partition_seed_forces_abstain(
    registry: TrustedSemanticRegistry,
    conditional_split: SplitRelationSpec,
) -> None:
    finite = conditional_split.model_copy(
        update={
            "split_relation": (
                SplitRelation.RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET
            ),
            "selection_inference_independence_proof": None,
            "split_seed": -1,
        }
    )
    result = assess_split_relation(finite, registry)
    assert result.disposition is SplitDisposition.ABSTAIN
    assert "RANDOM_PARTITION_SEED_NEGATIVE" in result.reason_codes
