"""Shared exact, synthetic Task 5 test artifacts."""

from __future__ import annotations

from pathlib import Path

from d2t_rna.contracts.base import canonical_sha256
from d2t_rna.contracts.enums import (
    ProbabilityScope,
    SplitRelation,
    UnconditionalDerivation,
)
from d2t_rna.contracts.primitives import (
    ObjectCommitment,
    OverlapCount,
    ProofArtifactRef,
    Rational,
    RegistryRef,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.scenario import ScenarioProof
from d2t_rna.contracts.splits import SplitRelationSpec
from d2t_rna.exact import (
    EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
    ExactDecisionRuleSpec,
)
from d2t_rna.exact.confidence import (
    ExactParameterFamily,
    ExactParameterPoint,
    ExactSamplingLawEntry,
    ExactSamplingLawManifest,
    HypothesisThresholds,
    exact_parameter_registry_hash,
)
from d2t_rna.exact.enumerate import (
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
)
from d2t_rna.exact.support import ExactActionSpec, ExactSupportSpec
from d2t_rna.evaluation.risk_binding import (
    RiskCertificateReplayBundle,
    build_risk_certificate_replay_bundle,
)
from d2t_rna.evaluation.scenario import (
    BoundEventFlag,
    ExactScenarioOutcome,
    FiniteScenarioCoverageAggregate,
    aggregate_finite_scenarios,
    build_exact_enumeration_artifact,
    build_exact_synthetic_scenario_artifact,
    build_scenario_proof_manifest,
    evaluate_registered_exact_synthetic_coverage_report,
)
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    load_trusted_task2_registry,
)
from d2t_rna.probability.risk import (
    FailureAction,
    FailureBranch,
    FailurePolicyDefinition,
    RegisteredFailure,
    RegisteredFailurePolicy,
    RiskEvidenceBindings,
    UnconditionalRiskEvidence,
)
from d2t_rna.probability.scopes import SyntheticKnownChannelPrerequisites


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64


def _trusted_task2_registry() -> TrustedSemanticRegistry:
    manifest = (
        Path(__file__).parents[2]
        / "manifests"
        / "task2_semantic_registry.json"
    )
    return load_trusted_task2_registry(manifest.read_bytes())


def _exact_synthetic_microcase(
    *,
    conditioning_sigma_field_hash: str,
) -> tuple[
    ExactSupportSpec,
    ExactParameterFamily,
    ExactDecisionRuleSpec,
]:
    support = ExactSupportSpec(
        state_ids=("state.0", "state.1"),
        actions=(
            ExactActionSpec(
                action_id="action.0",
                sample_size=1,
                alphabet=("symbol.0", "symbol.1"),
            ),
        ),
    )

    def law(
        *,
        law_id: str,
        first_probability: Rational,
    ) -> IndependentMultinomialLaw:
        return IndependentMultinomialLaw(
            law_id=law_id,
            support_spec_hash=canonical_sha256(support),
            action_probabilities=(
                IndependentActionProbabilities(
                    action_id="action.0",
                    probabilities=(
                        first_probability,
                        Rational(
                            numerator=(
                                first_probability.denominator
                                - first_probability.numerator
                            ),
                            denominator=first_probability.denominator,
                        ),
                    ),
                ),
            ),
        )

    thresholds = HypothesisThresholds(
        tau0=Rational(numerator=1, denominator=1),
        epsilon=Rational(numerator=3, denominator=1),
    )
    points = (
        ExactParameterPoint(
            parameter_id="omega.h0",
            loss=Rational(numerator=1, denominator=1),
            law=law(
                law_id="law.h0",
                first_probability=Rational(numerator=1, denominator=1),
            ),
        ),
        ExactParameterPoint(
            parameter_id="omega.h1",
            loss=Rational(numerator=3, denominator=1),
            law=law(
                law_id="law.h1",
                first_probability=Rational(numerator=0, denominator=1),
            ),
        ),
        ExactParameterPoint(
            parameter_id="omega.indifference",
            loss=Rational(numerator=2, denominator=1),
            law=law(
                law_id="law.indifference",
                first_probability=Rational(numerator=1, denominator=20),
            ),
        ),
    )
    support_hash = canonical_sha256(support)
    sampling_law_manifest = ExactSamplingLawManifest(
        support_spec_hash=support_hash,
        entries=tuple(
            ExactSamplingLawEntry(
                parameter_id=point.parameter_id,
                law_hash=canonical_sha256(point.law),
            )
            for point in points
        ),
    )
    sampling_law_hash = canonical_sha256(sampling_law_manifest)
    registry = _trusted_task2_registry()
    probability_space = ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(
                object_id="channel.synthetic.known",
                object_hash=_SHA_A,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="synthetic.observation",
                object_hash=_SHA_B,
            ),
        ),
        sampling_law_hash=sampling_law_hash,
        parameter_space_hash=exact_parameter_registry_hash(
            thresholds,
            points,
        ),
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
        observation_model_hash=_SHA_A,
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
    prerequisites = SyntheticKnownChannelPrerequisites(
        known_channel_object_id="channel.synthetic.known",
        known_channel_object_hash=_SHA_A,
        sampling_law_hash=sampling_law_hash,
        support_definition_hash=support_hash,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.synthetic_channel_registration",
            artifact_hash=_SHA_D,
        ),
    )
    family = ExactParameterFamily(
        support_spec_hash=support_hash,
        semantic_registry=registry,
        probability_space=probability_space,
        synthetic_prerequisites=prerequisites,
        sampling_law_manifest=sampling_law_manifest,
        thresholds=thresholds,
        points=points,
    )
    decision_rule = ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
        parameter_universe_hash=family.parameter_universe_hash,
    )
    return support, family, decision_rule


def synthetic_task2_risk_replay_bundle(
    *,
    conditioning_sigma_field_hash: str = "1" * 64,
) -> RiskCertificateReplayBundle:
    """Build a real Task 2 raw-input replay bundle for synthetic tests."""

    _, family, _ = _exact_synthetic_microcase(
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
    )
    registry = family.semantic_registry
    dependency = registry.ref(
        "dependency.umi_family",
        SemanticRegistryRole.DEPENDENCY_UNIT,
    )
    probability_space = family.probability_space
    split_relation = SplitRelationSpec(
        split_relation=SplitRelation.INDEPENDENT_LIBRARIES,
        dependency_unit_level=dependency,
        planning_partition_hash=_SHA_A,
        certificate_partition_hash=_SHA_B,
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
        selection_inference_independence_proof=ProofArtifactRef(
            proof_id="proof.synthetic_independence",
            artifact_hash=_SHA_C,
        ),
        overlap_counts=(
            OverlapCount(
                left_partition_id="planning",
                right_partition_id="certificate",
                dependency_unit_level=dependency,
                count=0,
            ),
        ),
        split_seed=None,
    )
    prerequisites = family.synthetic_prerequisites
    failure_policy = RegisteredFailurePolicy(
        policy_ref=registry.ref(
            "failure.abstain_all_registered",
            SemanticRegistryRole.FAILURE_POLICY,
        ),
        definition=FailurePolicyDefinition(
            branches=tuple(
                FailureBranch(
                    failure=failure,
                    action=FailureAction.ABSTAIN,
                )
                for failure in RegisteredFailure
            ),
            unknown_failure_action=FailureAction.ABSTAIN,
        ),
    )
    risk_certificate = RiskCertificate(
        h0_wrong_reject_bound=Rational(numerator=1, denominator=20),
        h1_wrong_certify_bound=Rational(numerator=1, denominator=20),
        indifference_decisive_output_bound=Rational(
            numerator=1,
            denominator=20,
        ),
        confidence_set_uniform_coverage=Rational(
            numerator=19,
            denominator=20,
        ),
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
        success_event_hash=_SHA_E,
        failure_event_policy=failure_policy.policy_ref,
        conditional_bound=Rational(numerator=1, denominator=20),
        unconditional_bound=None,
        unconditional_derivation=UnconditionalDerivation.NOT_AVAILABLE,
        conditional_on_effective_molecule_count=False,
        prospective_unconditional_bound=None,
    )
    evidence = RiskEvidenceBindings(
        probability_space_hash=canonical_sha256(probability_space),
        split_relation_hash=canonical_sha256(split_relation),
        scope_prerequisites_hash=canonical_sha256(prerequisites),
        nuisance_handling_hash=None,
        uniform_confidence_set_proof=ProofArtifactRef(
            proof_id="proof.synthetic_uniform_confidence_set",
            artifact_hash=_SHA_A,
        ),
        indifference_decisive_implies_noncoverage_proof=ProofArtifactRef(
            proof_id="proof.synthetic_indifference_inclusion",
            artifact_hash=_SHA_B,
        ),
        split_independence_proof=(
            split_relation.selection_inference_independence_proof
        ),
        failure_policy_definition_hash=failure_policy.definition_hash,
        unconditional=UnconditionalRiskEvidence(
            validity_event_id="event.synthetic_registered_success",
            validity_event_hash=risk_certificate.success_event_hash,
            derivation=UnconditionalDerivation.NOT_AVAILABLE,
            validity_failure_probability=None,
            validity_event_failure_action=FailureAction.ABSTAIN,
            derivation_proof=None,
        ),
        effective_molecule_conditioning=None,
    )
    return build_risk_certificate_replay_bundle(
        risk_certificate=risk_certificate,
        probability_space=probability_space,
        split_relation=split_relation,
        scope_prerequisites=prerequisites,
        failure_policy=failure_policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=None,
        nuisance_handling=None,
    )


def exact_synthetic_scenario_aggregate(
    *,
    conditioning_sigma_field_hash: str,
    scenario_id: str = "registered-synthetic-scenario",
) -> FiniteScenarioCoverageAggregate:
    """Build a nonformal exact caller-atom fixture for ordinary unit tests."""

    risk = Rational(numerator=1, denominator=20)
    safe = Rational(numerator=19, denominator=20)
    artifact = build_exact_enumeration_artifact(
        scenario_id=scenario_id,
        hypothesis_region=RegistryRef(
            registry_id="registered-hypothesis-region",
            registry_hash="7" * 64,
        ),
        coverage_core_membership=RegistryRef(
            registry_id="registered-coverage-core",
            registry_hash="8" * 64,
        ),
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
        outcomes=(
            ExactScenarioOutcome(
                outcome_id="risk",
                outcome_payload_sha256="9" * 64,
                probability=risk,
                risk_events=(
                    BoundEventFlag(
                        bound_id="wrong-decision",
                        occurred=True,
                    ),
                ),
                coverage_events=(
                    BoundEventFlag(
                        bound_id="joint-coverage",
                        occurred=False,
                    ),
                ),
            ),
            ExactScenarioOutcome(
                outcome_id="safe",
                outcome_payload_sha256="a" * 64,
                probability=safe,
                risk_events=(
                    BoundEventFlag(
                        bound_id="wrong-decision",
                        occurred=False,
                    ),
                ),
                coverage_events=(
                    BoundEventFlag(
                        bound_id="joint-coverage",
                        occurred=True,
                    ),
                ),
            ),
        ),
    )
    proof = ScenarioProof(
        scenario_id=artifact.scenario_id,
        law_hash=artifact.law_hash,
        hypothesis_region=artifact.hypothesis_region,
        coverage_core_membership=artifact.coverage_core_membership,
        conditioning_sigma_field_hash=(
            artifact.conditioning_sigma_field_hash
        ),
        risk_upper_bounds=artifact.risk_upper_bounds,
        coverage_lower_bounds=artifact.coverage_lower_bounds,
        coverage_bound_method=artifact.coverage_bound_method,
        probability_mass_accounted=artifact.probability_mass_accounted,
        omitted_mass_bound=artifact.omitted_mass_bound,
        numerical_error_bound=artifact.numerical_error_bound,
        proof_artifact_hash=canonical_sha256(artifact),
        formal_guarantee=False,
    )
    manifest = build_scenario_proof_manifest(proof, artifact)
    return aggregate_finite_scenarios(
        (manifest,),
        scenario_probabilities={
            scenario_id: Rational(numerator=1, denominator=1),
        },
    )


def formal_task4_scenario_aggregate(
    *,
    conditioning_sigma_field_hash: str,
    scenario_id: str = "registered-task4-synthetic-scenario",
) -> FiniteScenarioCoverageAggregate:
    """Build the formal integration fixture from raw Task 4 replay inputs."""

    support, family, decision_rule = _exact_synthetic_microcase(
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
    )
    confidence_procedure, report = (
        evaluate_registered_exact_synthetic_coverage_report(
            support=support,
            family=family,
            decision_rule=decision_rule,
        )
    )
    artifact = build_exact_synthetic_scenario_artifact(
        scenario_id=scenario_id,
        support=support,
        family=family,
        confidence_procedure=confidence_procedure,
        decision_rule=decision_rule,
        confidence_rule_registry_id=(
            "confidence.task5.all-registered-parameters.v1"
        ),
        report=report,
    )
    proof = ScenarioProof(
        scenario_id=artifact.scenario_id,
        law_hash=artifact.law_hash,
        hypothesis_region=artifact.hypothesis_region,
        coverage_core_membership=artifact.coverage_core_membership,
        conditioning_sigma_field_hash=(
            artifact.conditioning_sigma_field_hash
        ),
        risk_upper_bounds=artifact.risk_upper_bounds,
        coverage_lower_bounds=artifact.coverage_lower_bounds,
        coverage_bound_method=artifact.coverage_bound_method,
        probability_mass_accounted=artifact.probability_mass_accounted,
        omitted_mass_bound=artifact.omitted_mass_bound,
        numerical_error_bound=artifact.numerical_error_bound,
        proof_artifact_hash=canonical_sha256(artifact),
        formal_guarantee=True,
    )
    manifest = build_scenario_proof_manifest(proof, artifact)
    return aggregate_finite_scenarios(
        (manifest,),
        scenario_probabilities={
            scenario_id: Rational(numerator=1, denominator=1),
        },
    )
