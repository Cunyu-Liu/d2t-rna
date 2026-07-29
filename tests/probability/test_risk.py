from __future__ import annotations

from fractions import Fraction

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import (
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import (
    ProbabilityScope,
    SplitRelation,
    UnconditionalDerivation,
)
from d2t_rna.contracts.primitives import ProofArtifactRef, Rational
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.splits import SplitRelationSpec
from d2t_rna.probability.registry import (
    TRUSTED_TASK2_REGISTRY_SHA256,
    SemanticRegistryRole,
    TrustedSemanticRegistry,
)
from d2t_rna.probability.risk import (
    TASK2_FIXTURE_CLAIM_SET_SHA256,
    TASK2_FIXTURE_VERIFIER_CONFIGURATION_SHA256,
    EffectiveMoleculeConditioningSpec,
    FailureAction,
    FailureBranch,
    FailurePolicyDefinition,
    ProofEvidenceGrade,
    ProofVerificationOutcome,
    ProofVerificationReceipt,
    RegisteredFailure,
    RegisteredFailurePolicy,
    RiskAssessmentDisposition,
    RiskEvaluationInputBundle,
    RiskEvidenceBindings,
    RiskSemanticError,
    UnconditionalRiskEvidence,
    action_for_failure,
    derive_unconditional_bound,
    evaluate_risk_certificate,
    good_event_union_bound,
    validate_uniform_indifference_control,
)
from d2t_rna.probability.scopes import (
    ScopePrerequisites,
    SyntheticKnownChannelPrerequisites,
    WithinLibraryPrerequisites,
)
from d2t_rna.probability.splits import (
    NuisanceHandlingEvidence,
    NuisanceHandlingMode,
)

from .conftest import SHA_A, SHA_B, SHA_C, SHA_D, SHA_E, SHA_F


def _all_abstain_policy(
    registry: TrustedSemanticRegistry,
) -> RegisteredFailurePolicy:
    return RegisteredFailurePolicy(
        policy_ref=registry.ref(
            "failure.abstain_all_registered",
            SemanticRegistryRole.FAILURE_POLICY,
        ),
        definition=FailurePolicyDefinition(
            branches=tuple(
                FailureBranch(failure=failure, action=FailureAction.ABSTAIN)
                for failure in RegisteredFailure
            ),
            unknown_failure_action=FailureAction.ABSTAIN,
        ),
    )


def _tower_evidence(
    *,
    policy: RegisteredFailurePolicy,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    prerequisites: ScopePrerequisites | None,
    nuisance_handling: NuisanceHandlingEvidence | None = None,
    effective: EffectiveMoleculeConditioningSpec | None = None,
) -> RiskEvidenceBindings:
    uniform_proof = (
        prerequisites.uniform_confidence_set_proof
        if isinstance(prerequisites, WithinLibraryPrerequisites)
        else ProofArtifactRef(
            proof_id="proof.uniform_confidence_set",
            artifact_hash=SHA_D,
        )
    )
    return RiskEvidenceBindings(
        probability_space_hash=canonical_sha256(probability_space),
        split_relation_hash=canonical_sha256(split_relation),
        scope_prerequisites_hash=(
            canonical_sha256(prerequisites)
            if prerequisites is not None
            else None
        ),
        nuisance_handling_hash=(
            canonical_sha256(nuisance_handling)
            if nuisance_handling is not None
            else None
        ),
        uniform_confidence_set_proof=uniform_proof,
        indifference_decisive_implies_noncoverage_proof=ProofArtifactRef(
            proof_id="proof.indifference_inclusion",
            artifact_hash=SHA_B,
        ),
        split_independence_proof=(
            split_relation.selection_inference_independence_proof
        ),
        failure_policy_definition_hash=policy.definition_hash,
        unconditional=UnconditionalRiskEvidence(
            validity_event_id="event.registered_success",
            validity_event_hash=SHA_E,
            derivation=UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE,
            validity_failure_probability=None,
            validity_event_failure_action=FailureAction.ABSTAIN,
            derivation_proof=ProofArtifactRef(
                proof_id="proof.tower_uniform_as",
                artifact_hash=SHA_D,
            ),
        ),
        effective_molecule_conditioning=effective,
    )


def _within_certificate(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
) -> RiskCertificate:
    delta = Rational(numerator=1, denominator=20)
    return RiskCertificate(
        h0_wrong_reject_bound=delta,
        h1_wrong_certify_bound=delta,
        indifference_decisive_output_bound=delta,
        confidence_set_uniform_coverage=Rational(
            numerator=19,
            denominator=20,
        ),
        probability_scope=within_spec.probability_scope,
        conditioning_sigma_field_hash=(
            within_spec.conditioning_sigma_field_hash
        ),
        success_event_hash=SHA_E,
        failure_event_policy=registry.ref(
            "failure.abstain_all_registered",
            SemanticRegistryRole.FAILURE_POLICY,
        ),
        conditional_bound=delta,
        unconditional_bound=delta,
        unconditional_derivation=(
            UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE
        ),
        conditional_on_effective_molecule_count=False,
        prospective_unconditional_bound=None,
    )


def _input_bundle(
    *,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    prerequisites: ScopePrerequisites | None,
    nuisance_handling: NuisanceHandlingEvidence | None,
    certificate: RiskCertificate,
    evidence: RiskEvidenceBindings,
    policy: RegisteredFailurePolicy,
) -> RiskEvaluationInputBundle:
    return RiskEvaluationInputBundle(
        probability_space_hash=canonical_sha256(probability_space),
        split_relation_hash=canonical_sha256(split_relation),
        scope_prerequisites_hash=(
            canonical_sha256(prerequisites)
            if prerequisites is not None
            else None
        ),
        nuisance_handling_hash=(
            canonical_sha256(nuisance_handling)
            if nuisance_handling is not None
            else None
        ),
        risk_certificate_hash=canonical_sha256(certificate),
        risk_evidence_hash=canonical_sha256(evidence),
        failure_policy_definition_hash=policy.definition_hash,
        semantic_registry_root_hash=TRUSTED_TASK2_REGISTRY_SHA256,
    )


def _fixture_receipt(
    *,
    registry: TrustedSemanticRegistry,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    prerequisites: ScopePrerequisites | None,
    nuisance_handling: NuisanceHandlingEvidence | None = None,
    certificate: RiskCertificate,
    evidence: RiskEvidenceBindings,
    policy: RegisteredFailurePolicy,
) -> ProofVerificationReceipt:
    bundle = _input_bundle(
        probability_space=probability_space,
        split_relation=split_relation,
        prerequisites=prerequisites,
        nuisance_handling=nuisance_handling,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    )
    verifier = registry.ref(
        "verifier.task2.fixture",
        SemanticRegistryRole.TEST_FIXTURE_VERIFIER,
    )
    return ProofVerificationReceipt(
        receipt_id="receipt.task2.fixture.001",
        probability_space_hash=bundle.probability_space_hash,
        split_relation_hash=bundle.split_relation_hash,
        scope_prerequisites_hash=bundle.scope_prerequisites_hash,
        nuisance_handling_hash=bundle.nuisance_handling_hash,
        risk_certificate_hash=bundle.risk_certificate_hash,
        risk_evidence_hash=bundle.risk_evidence_hash,
        evaluation_input_bundle_hash=bundle.bundle_hash,
        semantic_registry_root_hash=TRUSTED_TASK2_REGISTRY_SHA256,
        verifier=verifier,
        verifier_code_hash=verifier.registry_hash,
        verifier_configuration_hash=(
            TASK2_FIXTURE_VERIFIER_CONFIGURATION_SHA256
        ),
        claim_set_hash=TASK2_FIXTURE_CLAIM_SET_SHA256,
        verification_log_hash=SHA_F,
        evidence_grade=ProofEvidenceGrade.TEST_FIXTURE_ONLY,
        outcome=ProofVerificationOutcome.PASS,
    )


def _effective_conditioning(
    *,
    prerequisites: WithinLibraryPrerequisites,
    split_relation: SplitRelationSpec,
) -> EffectiveMoleculeConditioningSpec:
    return EffectiveMoleculeConditioningSpec(
        conditioning_id="conditioning.effective_molecules.001",
        dependency_unit_level=split_relation.dependency_unit_level,
        realized_library_object_id=prerequisites.realized_library_object_id,
        realized_library_object_hash=prerequisites.realized_library_object_hash,
        observed_effective_molecule_count=37,
        count_definition_hash=SHA_A,
        parent_conditioning_sigma_field_hash=(
            prerequisites.conditioning_sigma_field_hash
        ),
        counting_proof=ProofArtifactRef(
            proof_id="proof.effective_molecule_count",
            artifact_hash=SHA_B,
        ),
    )


def test_tower_property_preserves_exact_conditional_bound() -> None:
    delta = Rational(numerator=1, denominator=20)
    result = derive_unconditional_bound(
        delta,
        UnconditionalRiskEvidence(
            validity_event_id="event.registered_success",
            validity_event_hash=SHA_E,
            derivation=UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE,
            validity_failure_probability=None,
            validity_event_failure_action=FailureAction.ABSTAIN,
            derivation_proof=ProofArtifactRef(
                proof_id="proof.tower",
                artifact_hash=SHA_A,
            ),
        ),
    )
    assert result == delta


def test_failure_abstain_keeps_delta_but_continue_uses_union_bound() -> None:
    delta = Rational(numerator=1, denominator=20)
    rho = Rational(numerator=1, denominator=10)
    abstain = derive_unconditional_bound(
        delta,
        UnconditionalRiskEvidence(
            validity_event_id="event.registered_success",
            validity_event_hash=SHA_E,
            derivation=UnconditionalDerivation.ABSTAIN_OUTSIDE_VALIDITY_EVENT,
            validity_failure_probability=None,
            validity_event_failure_action=FailureAction.ABSTAIN,
            derivation_proof=ProofArtifactRef(
                proof_id="proof.abstain_outside",
                artifact_hash=SHA_A,
            ),
        ),
    )
    assert abstain == delta
    assert good_event_union_bound(delta, rho) == Rational(
        numerator=29,
        denominator=200,
    )


def test_good_event_union_bound_requires_continue_decision() -> None:
    with pytest.raises(ValidationError, match="CONTINUE_DECISION"):
        UnconditionalRiskEvidence(
            validity_event_id="event.registered_success",
            validity_event_hash=SHA_E,
            derivation=UnconditionalDerivation.GOOD_EVENT_UNION_BOUND,
            validity_failure_probability=Rational(
                numerator=1,
                denominator=10,
            ),
            validity_event_failure_action=FailureAction.ABSTAIN,
            derivation_proof=ProofArtifactRef(
                proof_id="proof.union",
                artifact_hash=SHA_A,
            ),
        )


@pytest.mark.parametrize(
    ("delta", "rho", "expected"),
    [
        (
            Rational(numerator=1, denominator=3),
            Rational(numerator=1, denominator=7),
            Rational(numerator=3, denominator=7),
        ),
        (
            Rational(numerator=0, denominator=1),
            Rational(numerator=1, denominator=7),
            Rational(numerator=1, denominator=7),
        ),
        (
            Rational(numerator=1, denominator=1),
            Rational(numerator=1, denominator=7),
            Rational(numerator=1, denominator=1),
        ),
    ],
)
def test_good_event_union_bound_is_exact(
    delta: Rational,
    rho: Rational,
    expected: Rational,
) -> None:
    result = good_event_union_bound(delta, rho)
    assert result == expected
    assert Fraction(result.numerator, result.denominator) == (
        Fraction(delta.numerator, delta.denominator)
        + (
            1 - Fraction(delta.numerator, delta.denominator)
        )
        * Fraction(rho.numerator, rho.denominator)
    )


def test_qc_gof_solver_yield_and_unknown_failures_all_abstain(
    registry: TrustedSemanticRegistry,
) -> None:
    policy = _all_abstain_policy(registry)
    for failure in RegisteredFailure:
        assert action_for_failure(policy, failure) is FailureAction.ABSTAIN
    assert action_for_failure(policy, "UNREGISTERED") is FailureAction.ABSTAIN
    assert policy.definition_hash == policy.policy_ref.registry_hash

    with pytest.raises(ValidationError, match="must ABSTAIN"):
        FailurePolicyDefinition(
            branches=tuple(
                FailureBranch(
                    failure=failure,
                    action=(
                        FailureAction.CONTINUE_DECISION
                        if failure is RegisteredFailure.GOF
                        else FailureAction.ABSTAIN
                    ),
                )
                for failure in RegisteredFailure
            ),
            unknown_failure_action=FailureAction.ABSTAIN,
        )
    with pytest.raises(ValidationError, match="exactly once"):
        FailurePolicyDefinition(
            branches=policy.definition.branches[:-1],
            unknown_failure_action=FailureAction.ABSTAIN,
        )
    with pytest.raises(ValidationError, match="unknown failures"):
        FailurePolicyDefinition(
            branches=policy.definition.branches,
            unknown_failure_action=FailureAction.CONTINUE_DECISION,
        )


def test_uniform_95_percent_cs_controls_indifference_decisions() -> None:
    validate_uniform_indifference_control(
        coverage=Rational(numerator=19, denominator=20),
        decisive_bound=Rational(numerator=1, denominator=20),
    )
    with pytest.raises(RiskSemanticError, match="indifference decisive"):
        validate_uniform_indifference_control(
            coverage=Rational(numerator=19, denominator=20),
            decisive_bound=Rational(numerator=2, denominator=20),
        )


def test_noncoverage_inclusion_alone_cannot_claim_a_tighter_bound() -> None:
    with pytest.raises(RiskSemanticError, match="exact noncoverage complement"):
        validate_uniform_indifference_control(
            coverage=Rational(numerator=19, denominator=20),
            decisive_bound=Rational(numerator=0, denominator=1),
        )
    validate_uniform_indifference_control(
        coverage=Rational(numerator=99, denominator=100),
        decisive_bound=Rational(numerator=1, denominator=100),
    )


def test_within_library_certificate_stays_pending_without_replayed_proof(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    result = evaluate_risk_certificate(
        certificate=_within_certificate(registry, within_spec),
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_PENDING_PROOF_REPLAY
    )
    assert result.scientific_claim_authorized is False
    assert result.certificate_issued is False
    forged = result.model_copy(
        update={
            "certificate_issued": True,
            "scientific_claim_authorized": True,
        }
    )
    with pytest.raises(ValidationError, match="literal_error"):
        strict_revalidate_contract_model(forged)
    constructed = type(result).model_construct(
        **{
            **result.model_dump(mode="python"),
            "certificate_issued": True,
            "scientific_claim_authorized": True,
        }
    )
    with pytest.raises(ValidationError, match="literal_error"):
        strict_revalidate_contract_model(constructed)


def test_within_library_can_bind_uniform_worst_case_over_nuisance(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    worst_case_space = within_spec.model_copy(
        update={"conditioning_sigma_field_hash": SHA_F}
    )
    worst_case_prerequisites = within_prerequisites.model_copy(
        update={"conditioning_sigma_field_hash": SHA_F}
    )
    nuisance = NuisanceHandlingEvidence(
        mode=NuisanceHandlingMode.UNIFORM_WORST_CASE_OVER_REGISTERED_NUISANCE,
        split_conditioning_sigma_field_hash=SHA_E,
        certificate_conditioning_sigma_field_hash=SHA_F,
        nuisance_parameter_space_hash=(
            worst_case_prerequisites.nuisance_parameter_space_hash
        ),
        uniform_worst_case_proof=ProofArtifactRef(
            proof_id="proof.uniform_worst_case_over_nuisance",
            artifact_hash=SHA_A,
        ),
    )
    policy = _all_abstain_policy(registry)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=worst_case_space,
        split_relation=conditional_split,
        prerequisites=worst_case_prerequisites,
        nuisance_handling=nuisance,
    )
    result = evaluate_risk_certificate(
        certificate=_within_certificate(registry, worst_case_space),
        probability_space=worst_case_space,
        split_relation=conditional_split,
        scope_prerequisites=worst_case_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
        nuisance_handling=nuisance,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_PENDING_PROOF_REPLAY
    )
    assert result.nuisance_handling_hash == canonical_sha256(nuisance)
    assert result.scientific_claim_authorized is False


def test_fixture_receipt_only_validates_a_non_scientific_software_candidate(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    )
    result = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=receipt,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.TEST_FIXTURE_BINDINGS_MATCHED
    )
    assert result.proof_verification_receipt_hash == canonical_sha256(receipt)
    assert result.certificate_issued is False
    assert result.scientific_claim_authorized is False


def test_proof_receipt_cannot_be_spliced_across_certificate_candidates(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    ).model_copy(update={"risk_certificate_hash": SHA_A})
    with pytest.raises(RiskSemanticError, match="receipt binding mismatch"):
        evaluate_risk_certificate(
            certificate=certificate,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=receipt,
        )


def test_proof_receipt_cannot_be_replayed_after_prerequisite_splicing(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    )
    spliced = within_prerequisites.model_copy(
        update={
            "target_binding_proof": ProofArtifactRef(
                proof_id="proof.target_binding.spliced",
                artifact_hash=SHA_F,
            )
        }
    )
    with pytest.raises(RiskSemanticError, match="prerequisite"):
        evaluate_risk_certificate(
            certificate=certificate,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=spliced,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=receipt,
        )


def test_success_event_cannot_be_spliced_from_derivation_evidence(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec).model_copy(
        update={"success_event_hash": SHA_F}
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    with pytest.raises(RiskSemanticError, match="success event"):
        evaluate_risk_certificate(
            certificate=certificate,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_formal_receipt_cannot_use_the_fixture_verifier(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    ).model_copy(
        update={"evidence_grade": ProofEvidenceGrade.FORMAL_PROOF_REPLAY}
    )
    result = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=receipt,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_FORMAL_VERIFIER_UNAVAILABLE
    )
    assert result.scientific_claim_authorized is False


def test_fixture_verifier_release_hash_is_checked(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    ).model_copy(update={"verifier_code_hash": SHA_A})
    with pytest.raises(RiskSemanticError, match="verifier code hash"):
        evaluate_risk_certificate(
            certificate=certificate,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=receipt,
        )


def test_receipt_registry_root_and_fail_outcome_are_auditable(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    receipt = _fixture_receipt(
        registry=registry,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        certificate=certificate,
        evidence=evidence,
        policy=policy,
    )
    with pytest.raises(RiskSemanticError, match="receipt binding mismatch"):
        evaluate_risk_certificate(
            certificate=certificate,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=receipt.model_copy(
                update={"semantic_registry_root_hash": SHA_A}
            ),
        )

    failed = receipt.model_copy(
        update={"outcome": ProofVerificationOutcome.FAIL}
    )
    result = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=failed,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_PROOF_VERIFICATION_FAILED
    )
    assert result.proof_verification_receipt_hash == canonical_sha256(failed)

    altered_log = receipt.model_copy(
        update={"verification_log_hash": SHA_A}
    )
    structural_only = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=altered_log,
    )
    assert structural_only.disposition is (
        RiskAssessmentDisposition.TEST_FIXTURE_BINDINGS_MATCHED
    )
    assert "PROOF_AND_LOG_CONTENT_NOT_AUTHENTICATED" in (
        structural_only.reason_codes
    )
    assert structural_only.scientific_claim_authorized is False


def test_risk_bounds_outside_unit_interval_are_rejected(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    invalid = _within_certificate(registry, within_spec).model_copy(
        update={
            "h0_wrong_reject_bound": Rational(
                numerator=-1,
                denominator=20,
            )
        }
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    with pytest.raises(RiskSemanticError, match=r"\[0, 1\]"):
        evaluate_risk_certificate(
            certificate=invalid,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_component_bounds_and_unconditional_derivation_must_match(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    too_large = _within_certificate(registry, within_spec).model_copy(
        update={
            "h0_wrong_reject_bound": Rational(
                numerator=1,
                denominator=10,
            )
        }
    )
    with pytest.raises(RiskSemanticError, match="exceeds"):
        evaluate_risk_certificate(
            certificate=too_large,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )
    wrong_unconditional = _within_certificate(
        registry,
        within_spec,
    ).model_copy(
        update={
            "unconditional_bound": Rational(
                numerator=1,
                denominator=10,
            )
        }
    )
    with pytest.raises(RiskSemanticError, match="exact derivation"):
        evaluate_risk_certificate(
            certificate=wrong_unconditional,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_effective_molecule_conditioning_forbids_prospective_bound(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    invalid = _within_certificate(registry, within_spec).model_copy(
        update={
            "conditional_on_effective_molecule_count": True,
            "prospective_unconditional_bound": Rational(
                numerator=1,
                denominator=20,
            ),
        }
    )
    effective = _effective_conditioning(
        prerequisites=within_prerequisites,
        split_relation=conditional_split,
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        effective=effective,
    )
    with pytest.raises(RiskSemanticError, match="prospective"):
        evaluate_risk_certificate(
            certificate=invalid,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_effective_molecule_conditioning_requires_structured_bound_spec(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    conditional = _within_certificate(registry, within_spec).model_copy(
        update={"conditional_on_effective_molecule_count": True}
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    with pytest.raises(RiskSemanticError, match="structured spec"):
        evaluate_risk_certificate(
            certificate=conditional,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_effective_molecule_source_and_sigma_are_cross_bound(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    conditional = _within_certificate(registry, within_spec).model_copy(
        update={"conditional_on_effective_molecule_count": True}
    )
    spliced = _effective_conditioning(
        prerequisites=within_prerequisites,
        split_relation=conditional_split,
    ).model_copy(update={"realized_library_object_hash": SHA_F})
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        effective=spliced,
    )
    with pytest.raises(RiskSemanticError, match="source library"):
        evaluate_risk_certificate(
            certificate=conditional,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_valid_effective_molecule_conditioning_is_still_only_pending_proof(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    conditional = _within_certificate(registry, within_spec).model_copy(
        update={"conditional_on_effective_molecule_count": True}
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
        effective=_effective_conditioning(
            prerequisites=within_prerequisites,
            split_relation=conditional_split,
        ),
    )
    result = evaluate_risk_certificate(
        certificate=conditional,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_PENDING_PROOF_REPLAY
    )
    assert result.scientific_claim_authorized is False


def test_v1_rejects_prospective_bound_even_without_effective_n_conditioning(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    invalid = _within_certificate(registry, within_spec).model_copy(
        update={
            "prospective_unconditional_bound": Rational(
                numerator=1,
                denominator=20,
            )
        }
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    )
    with pytest.raises(RiskSemanticError, match="prospective"):
        evaluate_risk_certificate(
            certificate=invalid,
            probability_space=within_spec,
            split_relation=conditional_split,
            scope_prerequisites=within_prerequisites,
            failure_policy=policy,
            evidence=evidence,
            registry=registry,
            proof_verification_receipt=None,
        )


def test_not_available_derivation_requires_null_unconditional_bound(
    registry: TrustedSemanticRegistry,
    within_spec: ProbabilitySpaceSpec,
    within_prerequisites: WithinLibraryPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    certificate = _within_certificate(registry, within_spec).model_copy(
        update={
            "unconditional_bound": None,
            "unconditional_derivation": UnconditionalDerivation.NOT_AVAILABLE,
        }
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=within_spec,
        split_relation=conditional_split,
        prerequisites=within_prerequisites,
    ).model_copy(
        update={
            "unconditional": UnconditionalRiskEvidence(
                validity_event_id="event.registered_success",
                validity_event_hash=SHA_E,
                derivation=UnconditionalDerivation.NOT_AVAILABLE,
                validity_failure_probability=None,
                validity_event_failure_action=FailureAction.ABSTAIN,
                derivation_proof=None,
            )
        }
    )
    result = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=within_spec,
        split_relation=conditional_split,
        scope_prerequisites=within_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_PENDING_PROOF_REPLAY
    )


def test_empirical_scope_never_yields_latent_risk_certificate(
    registry: TrustedSemanticRegistry,
    empirical_spec: ProbabilitySpaceSpec,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    cert = _within_certificate(registry, empirical_spec).model_copy(
        update={
            "probability_scope": (
                ProbabilityScope.FINITE_OBSERVED_DATASET_SUBSAMPLING
            )
        }
    )
    evidence = _tower_evidence(
        policy=policy,
        probability_space=empirical_spec,
        split_relation=conditional_split,
        prerequisites=None,
    )
    result = evaluate_risk_certificate(
        certificate=cert,
        probability_space=empirical_spec,
        split_relation=conditional_split,
        scope_prerequisites=None,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_EMPIRICAL_QA_ONLY
    )
    assert result.scientific_claim_authorized is False


def test_synthetic_pending_status_does_not_mask_an_invalid_split(
    registry: TrustedSemanticRegistry,
    synthetic_spec: ProbabilitySpaceSpec,
    synthetic_prerequisites: SyntheticKnownChannelPrerequisites,
    conditional_split: SplitRelationSpec,
) -> None:
    policy = _all_abstain_policy(registry)
    invalid_split = conditional_split.model_copy(
        update={
            "split_relation": SplitRelation.UNKNOWN,
            "selection_inference_independence_proof": None,
        }
    )
    certificate = _within_certificate(registry, synthetic_spec)
    evidence = _tower_evidence(
        policy=policy,
        probability_space=synthetic_spec,
        split_relation=invalid_split,
        prerequisites=synthetic_prerequisites,
    )
    result = evaluate_risk_certificate(
        certificate=certificate,
        probability_space=synthetic_spec,
        split_relation=invalid_split,
        scope_prerequisites=synthetic_prerequisites,
        failure_policy=policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
    )
    assert result.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_SCOPE_OR_SPLIT_ABSTAIN
    )
    assert result.certificate_issued is False
