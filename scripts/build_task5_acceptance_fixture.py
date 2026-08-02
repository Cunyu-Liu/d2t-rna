#!/usr/bin/env python3
"""Build a small, fully replayable synthetic Task 5 fixture."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from d2t_rna.contracts.enums import (
    ExtendedValueTag,
    ProbabilityScope,
    RorcReason,
    SplitRelation,
    UnconditionalDerivation,
)
from d2t_rna.contracts.extended import FiniteExtendedValue
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
from d2t_rna.evaluation.baselines import (
    BaselineOutcome,
    BaselineSpecification,
    build_baseline_common_binding,
    build_baseline_evaluation_batch_from_declarations,
    build_baseline_seed_declaration,
    build_method_evaluation_result,
    compare_method_to_baselines,
    summarize_random_baseline,
)
from d2t_rna.evaluation.milp_check import (
    BoundedMilpModel,
    ConstraintSense,
    FeasibilityScope,
    IntegerVariable,
    LinearConstraint,
    LinearTerm,
    check_bounded_milp,
)
from d2t_rna.evaluation.planner import (
    PlannerRunStatus,
    PlannerTerminationReason,
    RegisteredPlannerResult,
    build_coverage_feasibility_assessment,
)
from d2t_rna.evaluation.risk_binding import (
    build_risk_certificate_replay_bundle,
)
from d2t_rna.evaluation.scenario import (
    RorcCaseRecord,
    RorcObservedDecision,
    aggregate_finite_scenarios,
    audit_registered_rorc_paths,
    build_exact_synthetic_scenario_artifact,
    build_rorc_case_manifest,
    build_scenario_proof_manifest,
    compute_rorc_stress_metrics,
    evaluate_registered_exact_synthetic_coverage_report,
)
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
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
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
)
from scripts.verify_task5_acceptance_manifest import (
    ARTIFACT_ROOT,
    CLAIM_BOUNDARY,
    CONTRACT_SHA256,
    FIXTURE_SCHEMA,
    verify_fixture,
)


def _r(numerator: int, denominator: int = 1) -> Rational:
    return Rational(numerator=numerator, denominator=denominator)


def _ref(identifier: str, character: str) -> RegistryRef:
    return RegistryRef(
        registry_id=identifier,
        registry_hash=character * 64,
    )


def _finite(numerator: int, denominator: int = 1) -> FiniteExtendedValue:
    return FiniteExtendedValue(
        tag=ExtendedValueTag.FINITE,
        value=_r(numerator, denominator),
    )


def _write_canonical(path: Path, value: object) -> dict[str, str]:
    payload = canonical_json_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(payload)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _exact_synthetic_microcase(
    project_root: Path,
    *,
    conditioning_hash: str,
) -> tuple[
    ExactSupportSpec,
    ExactParameterFamily,
    ExactDecisionRuleSpec,
]:
    """Construct the raw Task 4 inputs shared by scenario and risk replay."""

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
                        _r(
                            first_probability.denominator
                            - first_probability.numerator,
                            first_probability.denominator,
                        ),
                    ),
                ),
            ),
        )

    thresholds = HypothesisThresholds(tau0=_r(1), epsilon=_r(3))
    points = (
        ExactParameterPoint(
            parameter_id="omega.h0",
            loss=_r(1),
            law=law(law_id="law.h0", first_probability=_r(1)),
        ),
        ExactParameterPoint(
            parameter_id="omega.h1",
            loss=_r(3),
            law=law(law_id="law.h1", first_probability=_r(0)),
        ),
        ExactParameterPoint(
            parameter_id="omega.indifference",
            loss=_r(2),
            law=law(
                law_id="law.indifference",
                first_probability=_r(1, 20),
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
    registry_path = project_root / "manifests" / "task2_semantic_registry.json"
    registry = load_trusted_task2_registry(registry_path.read_bytes())
    probability_space = ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(
                object_id="channel.synthetic.known",
                object_hash="a" * 64,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="synthetic.observation",
                object_hash="b" * 64,
            ),
        ),
        sampling_law_hash=canonical_sha256(sampling_law_manifest),
        parameter_space_hash=exact_parameter_registry_hash(
            thresholds,
            points,
        ),
        conditioning_sigma_field_hash=conditioning_hash,
        observation_model_hash="a" * 64,
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
        known_channel_object_hash="a" * 64,
        sampling_law_hash=probability_space.sampling_law_hash,
        support_definition_hash=support_hash,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.synthetic_channel_registration",
            artifact_hash="d" * 64,
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


def _scenario_aggregate(
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    decision_rule: ExactDecisionRuleSpec,
):
    """Build the formal scenario solely through production Task 4 replay."""

    confidence_procedure, report = (
        evaluate_registered_exact_synthetic_coverage_report(
            support=support,
            family=family,
            decision_rule=decision_rule,
        )
    )
    artifact = build_exact_synthetic_scenario_artifact(
        scenario_id="task5.synthetic.registered-scenario",
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
        conditioning_sigma_field_hash=artifact.conditioning_sigma_field_hash,
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
            artifact.scenario_id: _r(1),
        },
    )


def _risk_bundle(family: ExactParameterFamily):
    """Bind Task 2 risk replay to the exact same full probability space."""

    registry = family.semantic_registry
    dependency = registry.ref(
        "dependency.umi_family",
        SemanticRegistryRole.DEPENDENCY_UNIT,
    )
    probability_space = family.probability_space
    conditioning_hash = probability_space.conditioning_sigma_field_hash
    split_relation = SplitRelationSpec(
        split_relation=SplitRelation.INDEPENDENT_LIBRARIES,
        dependency_unit_level=dependency,
        planning_partition_hash="a" * 64,
        certificate_partition_hash="b" * 64,
        conditioning_sigma_field_hash=conditioning_hash,
        selection_inference_independence_proof=ProofArtifactRef(
            proof_id="proof.synthetic_independence",
            artifact_hash="c" * 64,
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
        h0_wrong_reject_bound=_r(1, 20),
        h1_wrong_certify_bound=_r(1, 20),
        indifference_decisive_output_bound=_r(1, 20),
        confidence_set_uniform_coverage=_r(19, 20),
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        conditioning_sigma_field_hash=conditioning_hash,
        success_event_hash="e" * 64,
        failure_event_policy=failure_policy.policy_ref,
        conditional_bound=_r(1, 20),
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
            artifact_hash="a" * 64,
        ),
        indifference_decisive_implies_noncoverage_proof=ProofArtifactRef(
            proof_id="proof.synthetic_indifference_inclusion",
            artifact_hash="b" * 64,
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


def _model() -> BoundedMilpModel:
    return BoundedMilpModel(
        model_id="task5.synthetic.fixed-horizon",
        fixed_horizon=2,
        available_control_library=_ref("task5.available-controls", "a"),
        registered_design_class=_ref("task5.registered-designs", "b"),
        variables=(
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=1,
            ),
            IntegerVariable(
                variable_id="y",
                lower_bound=0,
                upper_bound=1,
            ),
        ),
        available_control_variable_ids=("x",),
        constraints=(
            LinearConstraint(
                constraint_id="coverage",
                terms=(
                    LinearTerm(variable_id="x", coefficient=_r(1)),
                    LinearTerm(variable_id="y", coefficient=_r(1)),
                ),
                sense=ConstraintSense.GREATER_THAN_OR_EQUAL,
                rhs=_r(2),
            ),
        ),
    )


def _build_artifacts(project_root: Path) -> dict[str, object]:
    conditioning_hash = "1" * 64
    support, family, decision_rule = _exact_synthetic_microcase(
        project_root,
        conditioning_hash=conditioning_hash,
    )
    scenario = _scenario_aggregate(support, family, decision_rule)
    risk_bundle = _risk_bundle(family)
    risk = risk_bundle.inputs.risk_certificate
    model = _model()
    library = check_bounded_milp(
        model,
        scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        state_limit=16,
    )
    design = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=16,
    )
    planner = RegisteredPlannerResult(
        model_sha256=model.model_sha256,
        status=PlannerRunStatus.NO_CERTIFICATE_FOUND,
        witness=(),
        states_examined=1,
        termination_reason=(
            PlannerTerminationReason.REGISTERED_SEARCH_EXHAUSTED
        ),
        planner_configuration_sha256="c" * 64,
        planner_code_sha256="d" * 64,
    )
    yield_scope = _ref("task5.yield-scope", "4")
    cost_table = _ref("task5.cost-table", "5")
    expansion_order = _ref("task5.expansion-order", "6")
    assessment = build_coverage_feasibility_assessment(
        model,
        planner,
        risk_certificate=risk,
        risk_certificate_replay_bundle=risk_bundle,
        scenario_coverage_aggregate=scenario,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
        available_control_library_check=library,
        registered_design_class_check=design,
    )
    baseline_spec = BaselineSpecification(
        baseline_id="task5.random-baseline",
        implementation_sha256=hashlib.sha256(
            b"task5.random-baseline.implementation.v1"
        ).hexdigest(),
        configuration_sha256=hashlib.sha256(
            b"task5.random-baseline.configuration.v1"
        ).hexdigest(),
        seed_root_sha256=hashlib.sha256(
            b"task5.random-baseline.seed-root.v1"
        ).hexdigest(),
    )
    binding = build_baseline_common_binding(
        risk,
        assessment,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
        required_baseline_registry=(baseline_spec,),
    )
    declarations = tuple(
        build_baseline_seed_declaration(
            seed_index=index,
            outcome=BaselineOutcome.FEASIBLE,
            cost=_finite(index + 1),
            execution_artifact_sha256=hashlib.sha256(
                (
                    "task5.synthetic.baseline:"
                    f"{binding.common_binding_sha256}:{index}"
                ).encode("utf-8")
            ).hexdigest(),
        )
        for index in range(100)
    )
    batch = build_baseline_evaluation_batch_from_declarations(
        binding,
        baseline_id=baseline_spec.baseline_id,
        declarations=declarations,
    )
    summary = summarize_random_baseline(batch)
    method = build_method_evaluation_result(
        binding,
        method_id="task5.registered-method",
        implementation_sha256="e" * 64,
        configuration_sha256="f" * 64,
        outcome=BaselineOutcome.FEASIBLE,
        cost=_finite(10),
        execution_artifact_sha256=hashlib.sha256(
            b"task5.synthetic.method.execution.v1"
        ).hexdigest(),
    )
    comparison = compare_method_to_baselines(
        method_result=method,
        baseline_summaries=(summary,),
    )
    rorc_case_manifest = build_rorc_case_manifest(
        (
            RorcCaseRecord(
                case_id="case-a",
                case_input_sha256="1" * 64,
                decision_artifact_sha256="2" * 64,
                observed_decision=RorcObservedDecision.ABSTAIN,
                reasons=(RorcReason.REGISTERED_MODEL_CLASS_REJECTED,),
                decision_correct=True,
                covered_with_registered_state_dictionary=True,
                covered_after_omitting_third_state=False,
            ),
            RorcCaseRecord(
                case_id="case-b",
                case_input_sha256="3" * 64,
                decision_artifact_sha256="4" * 64,
                observed_decision=RorcObservedDecision.ABSTAIN,
                reasons=(RorcReason.ABSTAIN_INDETERMINATE,),
                decision_correct=True,
                covered_with_registered_state_dictionary=True,
                covered_after_omitting_third_state=True,
            ),
        )
    )
    rorc = compute_rorc_stress_metrics(rorc_case_manifest)
    rorc_path_audit = audit_registered_rorc_paths()
    return {
        "available_control_library_check": library,
        "registered_design_class_check": design,
        "scenario_aggregate": scenario,
        "risk_certificate_replay_bundle": risk_bundle,
        "coverage_feasibility_assessment": assessment,
        "baseline_comparison": comparison,
        "rorc_metrics": rorc,
        "registered_rorc_path_audit": rorc_path_audit,
    }


def build_fixture(
    *,
    project_root: Path,
    output_dir: Path,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    resolved_root = artifact_root.resolve()
    resolved_output = output_dir.resolve()
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "Task 5 fixture output must remain under the artifact root"
        ) from exc
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Task 5 fixture output exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    artifacts = _build_artifacts(project_root)
    records = {
        name: _write_canonical(output_dir / f"{name}.json", value)
        for name, value in sorted(artifacts.items())
    }
    comparison = artifacts["baseline_comparison"]
    rorc = artifacts["rorc_metrics"]
    rorc_path_audit = artifacts["registered_rorc_path_audit"]
    scenario = artifacts["scenario_aggregate"]
    manifest = {
        "schema": FIXTURE_SCHEMA,
        "fixture_id": "task5.registered.synthetic-microcase.v1",
        "contract_sha256": CONTRACT_SHA256,
        "artifacts": records,
        "replay": {
            "all_registered_replays_passed": True,
            "scenario_count": len(
                scenario.per_scenario_proof_manifest  # type: ignore[union-attr]
            ),
            "baseline_seed_count": sum(
                len(summary.batch.results)
                for summary in comparison.baseline_summaries  # type: ignore[union-attr]
            ),
            "rorc_observational_case_count": (
                rorc.total_cases  # type: ignore[union-attr]
            ),
            "rorc_registered_path_count": (
                rorc_path_audit.expected_path_count  # type: ignore[union-attr]
            ),
            "all_registered_rorc_paths_abstain": (
                rorc_path_audit.all_registered_paths_abstain  # type: ignore[union-attr]
            ),
            "observed_case_set_all_abstain": (
                rorc.observed_case_set_all_abstain  # type: ignore[union-attr]
            ),
            "risk_certificate_issued": False,
            "scientific_claim_authorized": False,
            "serialized_bearer_authorization": False,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    manifest_path = output_dir / "fixture_manifest.json"
    _write_canonical(manifest_path, manifest)
    verify_fixture(
        project_root,
        manifest_path,
        artifact_root=artifact_root,
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    build_fixture(
        project_root=project_root,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
