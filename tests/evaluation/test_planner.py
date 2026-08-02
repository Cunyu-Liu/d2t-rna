from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import canonical_sha256
from d2t_rna.contracts.enums import (
    PlannerFailureState,
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
from d2t_rna.contracts.splits import SplitRelationSpec
import d2t_rna.evaluation.milp_check as milp_module
import d2t_rna.evaluation.planner as planner_runtime
import d2t_rna.evaluation.risk_binding as risk_binding_runtime
import d2t_rna.probability.risk as task2_risk_runtime
from d2t_rna.evaluation.milp_check import (
    BoundedMilpModel,
    ConstraintSense,
    FeasibilityScope,
    IntegerVariable,
    IntegerWitnessValue,
    LinearConstraint,
    LinearTerm,
    MAX_EXACT_STATES,
    MAX_INTEGER_MAGNITUDE,
    MAX_RATIONAL_COMPONENT_BITS,
    MilpCheckReceipt,
    MilpCheckStatus,
    MilpTerminationReason,
    VariableKind,
    check_bounded_milp,
    replay_bounded_milp_check,
    verify_milp_witness,
)
from d2t_rna.evaluation.planner import (
    PlannerRunStatus,
    PlannerTerminationReason,
    RegisteredPlannerResult,
    build_coverage_feasibility_assessment,
    classify_planner_result,
    replay_coverage_feasibility_assessment,
)
from d2t_rna.evaluation.risk_binding import (
    RiskCertificateReplayBundle,
    build_risk_certificate_replay_bundle,
    replay_risk_certificate_replay_bundle,
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
    RiskAssessmentDisposition,
    RiskEvidenceBindings,
    UnconditionalRiskEvidence,
)
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
)
from tests.evaluation.factories import (
    exact_synthetic_scenario_aggregate,
    formal_task4_scenario_aggregate,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64
_SHA_F = "f" * 64


def _r(value: int) -> Rational:
    return Rational(numerator=value, denominator=1)


def _model(*, impossible: bool = False) -> BoundedMilpModel:
    return BoundedMilpModel(
        model_id="fixed-horizon-test",
        fixed_horizon=2,
        available_control_library=RegistryRef(
            registry_id="available-controls",
            registry_hash="a" * 64,
        ),
        registered_design_class=RegistryRef(
            registry_id="registered-designs",
            registry_hash="b" * 64,
        ),
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
                rhs=_r(3 if impossible else 2),
            ),
        ),
    )


def _not_found(model: BoundedMilpModel) -> RegisteredPlannerResult:
    return RegisteredPlannerResult(
        model_sha256=model.model_sha256,
        status=PlannerRunStatus.NO_CERTIFICATE_FOUND,
        witness=(),
        states_examined=1,
        termination_reason=PlannerTerminationReason.REGISTERED_SEARCH_EXHAUSTED,
        planner_configuration_sha256="c" * 64,
        planner_code_sha256="d" * 64,
    )


def _trusted_task2_registry() -> TrustedSemanticRegistry:
    manifest = (
        Path(__file__).parents[2]
        / "manifests"
        / "task2_semantic_registry.json"
    )
    return load_trusted_task2_registry(manifest.read_bytes())


def _valid_risk_bundle(
    *,
    conditioning_sigma_field_hash: str = "1" * 64,
) -> RiskCertificateReplayBundle:
    registry = _trusted_task2_registry()
    dependency = registry.ref(
        "dependency.umi_family",
        SemanticRegistryRole.DEPENDENCY_UNIT,
    )
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
        sampling_law_hash=_SHA_C,
        parameter_space_hash=_SHA_D,
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
    prerequisites = SyntheticKnownChannelPrerequisites(
        known_channel_object_id="channel.synthetic.known",
        known_channel_object_hash=_SHA_A,
        sampling_law_hash=_SHA_C,
        support_definition_hash=_SHA_F,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.synthetic_channel_registration",
            artifact_hash=_SHA_D,
        ),
    )
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


def test_independent_exact_checker_distinguishes_library_and_design() -> None:
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
    assert library.status is MilpCheckStatus.INFEASIBLE
    assert design.status is MilpCheckStatus.FEASIBLE


def test_planner_failure_is_not_promoted_without_independent_proof() -> None:
    model = _model()
    plain = classify_planner_result(model, _not_found(model))
    assert plain.failure_state is (
        PlannerFailureState.NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER
    )

    library = check_bounded_milp(
        model,
        scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        state_limit=16,
    )
    promoted = classify_planner_result(
        model,
        _not_found(model),
        available_control_library_check=library,
    )
    assert promoted.failure_state is (
        PlannerFailureState.NO_CERTIFICATE_WITHIN_AVAILABLE_CONTROL_LIBRARY
    )


def test_planner_classifier_rejects_live_witness_verifier_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model()
    invalid_found = RegisteredPlannerResult(
        model_sha256=model.model_sha256,
        status=PlannerRunStatus.CERTIFICATE_FOUND,
        witness=(
            IntegerWitnessValue(variable_id="x", value=0),
            IntegerWitnessValue(variable_id="y", value=0),
        ),
        states_examined=1,
        termination_reason=PlannerTerminationReason.CERTIFICATE_FOUND,
        planner_configuration_sha256="c" * 64,
        planner_code_sha256="d" * 64,
    )
    monkeypatch.setattr(
        planner_runtime,
        "verify_milp_witness",
        lambda *args, **kwargs: True,
    )
    with pytest.raises(RuntimeError, match="execution closure changed"):
        planner_runtime.classify_planner_result(model, invalid_found)


def test_full_design_infeasibility_requires_exhaustive_independent_check() -> None:
    model = _model(impossible=True)
    full = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=16,
    )
    assert full.status is MilpCheckStatus.INFEASIBLE
    assessment = classify_planner_result(
        model,
        _not_found(model),
        registered_design_class_check=full,
    )
    assert assessment.failure_state is (
        PlannerFailureState.NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS
    )


def test_checker_limit_and_planner_error_remain_unresolved() -> None:
    model = _model()
    check = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=1,
    )
    assert check.status is MilpCheckStatus.UNRESOLVED

    result = RegisteredPlannerResult(
        model_sha256=model.model_sha256,
        status=PlannerRunStatus.UNRESOLVED,
        witness=(),
        states_examined=0,
        termination_reason=PlannerTerminationReason.TIMEOUT,
        planner_configuration_sha256="c" * 64,
        planner_code_sha256="d" * 64,
    )
    assessment = classify_planner_result(model, result)
    assert assessment.failure_state is PlannerFailureState.PLANNER_UNRESOLVED


def test_fractional_constraints_and_witness_are_checked_exactly() -> None:
    model = BoundedMilpModel(
        model_id="fractional-equality",
        fixed_horizon=3,
        available_control_library=RegistryRef(
            registry_id="available-controls",
            registry_hash="a" * 64,
        ),
        registered_design_class=RegistryRef(
            registry_id="registered-designs",
            registry_hash="b" * 64,
        ),
        variables=(
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=3,
            ),
        ),
        available_control_variable_ids=("x",),
        constraints=(
            LinearConstraint(
                constraint_id="exact-rational-equality",
                terms=(
                    LinearTerm(
                        variable_id="x",
                        coefficient=Rational(numerator=1, denominator=3),
                    ),
                ),
                sense=ConstraintSense.EQUAL,
                rhs=Rational(numerator=2, denominator=3),
            ),
        ),
    )
    receipt = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=4,
    )
    assert receipt.status is MilpCheckStatus.FEASIBLE
    assert receipt.witness == (
        IntegerWitnessValue(variable_id="x", value=2),
    )
    assert verify_milp_witness(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        witness=receipt.witness,
    )


def test_model_requires_canonical_variable_order() -> None:
    model = _model()
    with pytest.raises(ValueError, match="canonically sorted"):
        BoundedMilpModel(
            model_id=model.model_id,
            fixed_horizon=model.fixed_horizon,
            available_control_library=model.available_control_library,
            registered_design_class=model.registered_design_class,
            variables=tuple(reversed(model.variables)),
            available_control_variable_ids=model.available_control_variable_ids,
            constraints=model.constraints,
        )


def test_state_cap_is_checked_before_partial_enumeration() -> None:
    receipt = check_bounded_milp(
        _model(),
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=3,
    )
    assert receipt.status is MilpCheckStatus.UNRESOLVED
    assert receipt.states_examined == 0
    assert receipt.state_space_size == 4


def test_receipt_must_replay_instead_of_trusting_serialized_fields() -> None:
    model = _model()
    receipt = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=16,
    )
    forged_payload = receipt.model_dump(
        mode="python",
        exclude={"verification_receipt_sha256"},
    )
    forged_payload.update(
        {
            "status": MilpCheckStatus.INFEASIBLE,
            "termination_reason": (
                MilpTerminationReason.EXHAUSTIVE_INFEASIBILITY
            ),
            "states_examined": receipt.state_space_size,
            "witness": (),
            "exhaustive": True,
            "witness_verified": False,
        }
    )
    forged = MilpCheckReceipt(
        **forged_payload,
        verification_receipt_sha256=canonical_sha256(forged_payload),
    )
    with pytest.raises(ValueError, match="fresh independent replay"):
        replay_bounded_milp_check(model, forged)


def test_unresolved_independent_check_cannot_promote_planner_no_find() -> None:
    model = _model()
    unresolved = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=1,
    )
    assessment = classify_planner_result(
        model,
        _not_found(model),
        registered_design_class_check=unresolved,
    )
    assert assessment.failure_state is PlannerFailureState.PLANNER_UNRESOLVED


def test_coverage_feasibility_assessment_binds_common_inputs_without_claim() -> None:
    model = _model()
    risk_bundle = _valid_risk_bundle()
    risk_certificate = risk_bundle.inputs.risk_certificate
    scenario_aggregate = exact_synthetic_scenario_aggregate(
        conditioning_sigma_field_hash=(
            risk_certificate.conditioning_sigma_field_hash
        )
    )
    assessment = build_coverage_feasibility_assessment(
        model,
        _not_found(model),
        risk_certificate=risk_certificate,
        risk_certificate_replay_bundle=risk_bundle,
        scenario_coverage_aggregate=scenario_aggregate,
        yield_scope=RegistryRef(
            registry_id="yield-scope",
            registry_hash="4" * 64,
        ),
        cost_table=RegistryRef(
            registry_id="cost-table",
            registry_hash="5" * 64,
        ),
        expansion_order=RegistryRef(
            registry_id="expansion-order",
            registry_hash="6" * 64,
        ),
    )
    assert assessment.risk_certificate_sha256 == canonical_sha256(
        risk_certificate
    )
    assert assessment.risk_certificate_replay_bundle == risk_bundle
    assert assessment.risk_certificate_semantic_replay_required is True
    assert assessment.risk_certificate_semantics_replayed is True
    assert assessment.scientific_claim_authorized is False
    assert assessment.formal_scientific_certificate_authorized is False
    assert assessment.scenario_replay_required is True
    assert assessment.scenario_proof_replayed is True
    assert assessment.scenario_coverage_aggregate == scenario_aggregate
    assert assessment.scenario_coverage_aggregate_sha256 == canonical_sha256(
        scenario_aggregate
    )
    assert assessment.scenario_proof_manifest_sha256 == canonical_sha256(
        scenario_aggregate.per_scenario_proof_manifest
    )

    forged_classification = assessment.planner_assessment.model_copy(
        update={
            "failure_state": (
                PlannerFailureState.NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS
            ),
            "independent_infeasibility_proof_scope": (
                FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS
            ),
            "registered_design_class_check_sha256": "f" * 64,
            "serialized_bearer_authorization": False,
        }
    )
    forged_payload = assessment.model_dump(
        mode="python",
        exclude={"common_binding_sha256"},
    )
    forged_payload.update(
        {
            "planner_assessment": forged_classification,
            "planner_assessment_sha256": canonical_sha256(
                forged_classification
            ),
        }
    )
    forged_payload["common_binding_sha256"] = canonical_sha256(
        forged_payload
    )
    with pytest.raises(ValidationError, match="receipt|replay|evidence"):
        type(assessment).model_validate(forged_payload, strict=True)

    forged_scenarios = scenario_aggregate.model_copy(
        update={
            "scenario_probability_mass_accounted": Rational(
                numerator=1,
                denominator=2,
            )
        }
    )
    with pytest.raises(ValueError, match="aggregate replay"):
        build_coverage_feasibility_assessment(
            model,
            _not_found(model),
            risk_certificate=risk_certificate,
            risk_certificate_replay_bundle=risk_bundle,
            scenario_coverage_aggregate=forged_scenarios,
            yield_scope=assessment.yield_scope,
            cost_table=assessment.cost_table,
            expansion_order=assessment.expansion_order,
        )


def test_coverage_assessment_rejects_scenario_conditioning_mismatch() -> None:
    model = _model()
    risk_bundle = _valid_risk_bundle()
    risk_certificate = risk_bundle.inputs.risk_certificate
    with pytest.raises(ValueError, match="different sigma fields"):
        build_coverage_feasibility_assessment(
            model,
            _not_found(model),
            risk_certificate=risk_certificate,
            risk_certificate_replay_bundle=risk_bundle,
            scenario_coverage_aggregate=(
                exact_synthetic_scenario_aggregate(
                    conditioning_sigma_field_hash="f" * 64,
                )
            ),
            yield_scope=RegistryRef(
                registry_id="yield-scope",
                registry_hash="4" * 64,
            ),
            cost_table=RegistryRef(
                registry_id="cost-table",
                registry_hash="5" * 64,
            ),
            expansion_order=RegistryRef(
                registry_id="expansion-order",
                registry_hash="6" * 64,
            ),
        )


def test_formal_coverage_assessment_rejects_different_probability_space() -> None:
    model = _model()
    risk_bundle = _valid_risk_bundle()
    conditioning = (
        risk_bundle.inputs.risk_certificate.conditioning_sigma_field_hash
    )
    scenarios = formal_task4_scenario_aggregate(
        conditioning_sigma_field_hash=conditioning,
    )
    with pytest.raises(ValueError, match="different probability spaces"):
        build_coverage_feasibility_assessment(
            model,
            _not_found(model),
            risk_certificate=risk_bundle.inputs.risk_certificate,
            risk_certificate_replay_bundle=risk_bundle,
            scenario_coverage_aggregate=scenarios,
            yield_scope=RegistryRef(
                registry_id="yield-scope",
                registry_hash="4" * 64,
            ),
            cost_table=RegistryRef(
                registry_id="cost-table",
                registry_hash="5" * 64,
            ),
            expansion_order=RegistryRef(
                registry_id="expansion-order",
                registry_hash="6" * 64,
            ),
        )


def test_coverage_assessment_rejects_cfa_dependency_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _model()
    risk_bundle = _valid_risk_bundle()
    scenarios = exact_synthetic_scenario_aggregate(
        conditioning_sigma_field_hash=(
            risk_bundle.inputs.risk_certificate.conditioning_sigma_field_hash
        ),
    )
    monkeypatch.setattr(
        planner_runtime,
        "parse_contract_json",
        lambda *args, **kwargs: None,
    )
    with pytest.raises(
        RuntimeError,
        match="CFA contract JSON parser runtime identity changed",
    ):
        build_coverage_feasibility_assessment(
            model,
            _not_found(model),
            risk_certificate=risk_bundle.inputs.risk_certificate,
            risk_certificate_replay_bundle=risk_bundle,
            scenario_coverage_aggregate=scenarios,
            yield_scope=RegistryRef(
                registry_id="yield-scope",
                registry_hash="4" * 64,
            ),
            cost_table=RegistryRef(
                registry_id="cost-table",
                registry_hash="5" * 64,
            ),
            expansion_order=RegistryRef(
                registry_id="expansion-order",
                registry_hash="6" * 64,
            ),
        )


def test_risk_replay_bundle_recomputes_task2_assessment_without_claim() -> None:
    bundle = _valid_risk_bundle()
    replayed = replay_risk_certificate_replay_bundle(bundle)
    serialized = bundle.model_dump_json()
    parsed = RiskCertificateReplayBundle.model_validate_json(
        serialized,
        strict=True,
    )

    assert replayed == bundle
    assert replay_risk_certificate_replay_bundle(parsed) == bundle
    assert bundle.risk_evaluation_inputs_sha256 == canonical_sha256(
        bundle.inputs
    )
    assert bundle.risk_certificate_assessment_sha256 == canonical_sha256(
        bundle.assessment
    )
    assert replayed.assessment.disposition is (
        RiskAssessmentDisposition.NOT_ISSUED_SYNTHETIC_PENDING_TASK_4
    )
    assert replayed.task2_semantic_evaluator_replayed is True
    assert replayed.task5_risk_binding_evaluator_replayed is True
    assert len(replayed.task2_semantic_evaluator_execution_sha256) == 64
    assert (
        len(replayed.task5_risk_binding_evaluator_execution_sha256)
        == 64
    )
    assert replayed.certificate_issued is False
    assert replayed.scientific_claim_authorized is False
    assert replayed.assessment.certificate_issued is False
    assert replayed.assessment.scientific_claim_authorized is False


def test_risk_replay_bundle_rejects_tampered_serialized_assessment() -> None:
    bundle = _valid_risk_bundle()
    forged_assessment = bundle.assessment.model_copy(
        update={"reason_codes": ("FORGED_CALLER_ASSESSMENT",)}
    )
    forged_payload = bundle.model_dump(mode="python")
    forged_payload.update(
        {
            "assessment": forged_assessment,
            "risk_certificate_assessment_sha256": canonical_sha256(
                forged_assessment
            ),
        }
    )

    with pytest.raises(
        ValidationError,
        match="fresh Task 2 semantic evaluation",
    ):
        RiskCertificateReplayBundle.model_validate(
            forged_payload,
            strict=True,
        )


def test_risk_replay_bundle_rejects_task2_evaluator_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _valid_risk_bundle()

    def forged_evaluator(**kwargs: object):
        return bundle.assessment

    monkeypatch.setattr(
        task2_risk_runtime,
        "evaluate_risk_certificate",
        forged_evaluator,
    )
    with pytest.raises(RuntimeError, match="runtime identity changed"):
        replay_risk_certificate_replay_bundle(bundle)


def test_risk_replay_bundle_rejects_task2_dependency_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _valid_risk_bundle()

    def skip_certificate_arithmetic(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        task2_risk_runtime,
        "_validate_certificate_arithmetic",
        skip_certificate_arithmetic,
    )
    with pytest.raises(RuntimeError, match="execution closure changed"):
        risk_binding_runtime.replay_risk_certificate_replay_bundle(bundle)


def test_risk_replay_bundle_rejects_task5_wrapper_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _valid_risk_bundle()

    def forged_wrapper(inputs: object):
        return bundle.assessment

    monkeypatch.setattr(
        risk_binding_runtime,
        "_evaluate_inputs",
        forged_wrapper,
    )
    with pytest.raises(
        RuntimeError,
        match="Task 5 risk binding evaluator runtime identity changed",
    ):
        risk_binding_runtime.replay_risk_certificate_replay_bundle(bundle)


def test_coverage_assessment_rejects_certificate_replaced_outside_bundle() -> None:
    model = _model()
    bundle = _valid_risk_bundle()
    replacement = bundle.inputs.risk_certificate.model_copy(
        update={"success_event_hash": _SHA_F}
    )
    scenarios = exact_synthetic_scenario_aggregate(
        conditioning_sigma_field_hash=(
            replacement.conditioning_sigma_field_hash
        )
    )

    with pytest.raises(ValueError, match="byte-identical"):
        build_coverage_feasibility_assessment(
            model,
            _not_found(model),
            risk_certificate=replacement,
            risk_certificate_replay_bundle=bundle,
            scenario_coverage_aggregate=scenarios,
            yield_scope=RegistryRef(
                registry_id="yield-scope",
                registry_hash="4" * 64,
            ),
            cost_table=RegistryRef(
                registry_id="cost-table",
                registry_hash="5" * 64,
            ),
            expansion_order=RegistryRef(
                registry_id="expansion-order",
                registry_hash="6" * 64,
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        (
            "h0_wrong_reject_bound",
            Rational(numerator=-9, denominator=1),
        ),
        (
            "h1_wrong_certify_bound",
            Rational(numerator=7, denominator=1),
        ),
        (
            "confidence_set_uniform_coverage",
            Rational(numerator=3, denominator=1),
        ),
        (
            "conditional_bound",
            Rational(numerator=-5, denominator=1),
        ),
    ],
)
def test_risk_replay_bundle_rejects_semantically_invalid_bounds(
    field_name: str,
    invalid_value: Rational,
) -> None:
    valid = _valid_risk_bundle()
    invalid_certificate = valid.inputs.risk_certificate.model_copy(
        update={field_name: invalid_value}
    )

    with pytest.raises(ValueError, match=r"interval \[0, 1\]"):
        build_risk_certificate_replay_bundle(
            risk_certificate=invalid_certificate,
            probability_space=valid.inputs.probability_space,
            split_relation=valid.inputs.split_relation,
            scope_prerequisites=valid.inputs.scope_prerequisites,
            failure_policy=valid.inputs.failure_policy,
            evidence=valid.inputs.evidence,
            registry=valid.inputs.registry,
            proof_verification_receipt=(
                valid.inputs.proof_verification_receipt
            ),
            nuisance_handling=valid.inputs.nuisance_handling,
        )


def test_coverage_assessment_replays_risk_bundle_with_other_bindings() -> None:
    model = _model()
    planner_result = _not_found(model)
    risk_bundle = _valid_risk_bundle()
    risk_certificate = risk_bundle.inputs.risk_certificate
    scenario_aggregate = exact_synthetic_scenario_aggregate(
        conditioning_sigma_field_hash=(
            risk_certificate.conditioning_sigma_field_hash
        )
    )
    yield_scope = RegistryRef(
        registry_id="yield-scope",
        registry_hash="4" * 64,
    )
    cost_table = RegistryRef(
        registry_id="cost-table",
        registry_hash="5" * 64,
    )
    expansion_order = RegistryRef(
        registry_id="expansion-order",
        registry_hash="6" * 64,
    )
    assessment = build_coverage_feasibility_assessment(
        model,
        planner_result,
        risk_certificate=risk_certificate,
        risk_certificate_replay_bundle=risk_bundle,
        scenario_coverage_aggregate=scenario_aggregate,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
    )

    replayed = replay_coverage_feasibility_assessment(
        assessment,
        model,
        planner_result,
        risk_certificate=risk_certificate,
        risk_certificate_replay_bundle=risk_bundle,
        scenario_coverage_aggregate=scenario_aggregate,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
    )
    assert replayed == assessment
    assert replayed.risk_certificate_semantics_replayed is True
    assert replayed.risk_scenario_probability_space_binding_required is False
    assert replayed.risk_scenario_probability_space_binding_verified is False
    assert replayed.formal_scenario_probability_space_sha256s == ()
    assert replayed.risk_probability_space_sha256 == canonical_sha256(
        risk_bundle.inputs.probability_space
    )
    assert replayed.scientific_claim_authorized is False


def test_planner_termination_reason_and_status_cannot_contradict() -> None:
    model = _model()
    with pytest.raises(ValidationError, match="termination"):
        RegisteredPlannerResult(
            model_sha256=model.model_sha256,
            status=PlannerRunStatus.NO_CERTIFICATE_FOUND,
            witness=(),
            states_examined=0,
            termination_reason=PlannerTerminationReason.TIMEOUT,
            planner_configuration_sha256="c" * 64,
            planner_code_sha256="d" * 64,
        )
    with pytest.raises(ValidationError, match="UNRESOLVED"):
        RegisteredPlannerResult(
            model_sha256=model.model_sha256,
            status=PlannerRunStatus.NO_CERTIFICATE_FOUND,
            witness=(),
            states_examined=1,
            termination_reason=PlannerTerminationReason.NUMERICAL_FAILURE,
            planner_configuration_sha256="c" * 64,
            planner_code_sha256="d" * 64,
        )


def test_hard_state_cap_cannot_be_overridden() -> None:
    model = BoundedMilpModel(
        model_id="over-cap",
        fixed_horizon=1,
        available_control_library=RegistryRef(
            registry_id="available-controls",
            registry_hash="a" * 64,
        ),
        registered_design_class=RegistryRef(
            registry_id="registered-designs",
            registry_hash="b" * 64,
        ),
        variables=(
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=MAX_EXACT_STATES,
            ),
        ),
        available_control_variable_ids=("x",),
        constraints=(),
    )
    unresolved = check_bounded_milp(
        model,
        scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        state_limit=MAX_EXACT_STATES,
    )
    assert unresolved.status is MilpCheckStatus.UNRESOLVED
    assert unresolved.states_examined == 0
    with pytest.raises(ValueError, match="MAX_EXACT_STATES"):
        check_bounded_milp(
            model,
            scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
            state_limit=MAX_EXACT_STATES + 1,
        )


def test_schema_caps_reject_huge_integers_and_rationals_before_hashing() -> None:
    with pytest.raises(ValidationError, match="less than or equal"):
        IntegerVariable(
            variable_id="huge",
            lower_bound=0,
            upper_bound=MAX_INTEGER_MAGNITUDE + 1,
        )
    with pytest.raises(ValidationError, match="bit length"):
        LinearTerm(
            variable_id="x",
            coefficient=Rational(
                numerator=1 << (MAX_RATIONAL_COMPONENT_BITS + 1),
                denominator=1,
            ),
        )


def test_empty_library_requires_explicit_registered_noop() -> None:
    kwargs = {
        "model_id": "empty-library",
        "fixed_horizon": 1,
        "available_control_library": RegistryRef(
            registry_id="available-controls",
            registry_hash="a" * 64,
        ),
        "registered_design_class": RegistryRef(
            registry_id="registered-designs",
            registry_hash="b" * 64,
        ),
        "variables": (
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=1,
            ),
        ),
        "available_control_variable_ids": (),
        "constraints": (),
    }
    with pytest.raises(ValidationError, match="registered_noop"):
        BoundedMilpModel(**kwargs)

    noop_model = BoundedMilpModel(**kwargs, registered_noop=True)
    receipt = check_bounded_milp(
        noop_model,
        scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        state_limit=1,
    )
    assert receipt.status is MilpCheckStatus.FEASIBLE
    assert receipt.witness == (
        IntegerWitnessValue(variable_id="x", value=0),
    )


def test_variable_kind_and_horizon_rules_are_explicit() -> None:
    with pytest.raises(ValidationError, match="nonnegative"):
        IntegerVariable(
            variable_id="count",
            kind=VariableKind.NONNEGATIVE,
            horizon_index=0,
            lower_bound=-1,
            upper_bound=1,
        )
    auxiliary = IntegerVariable(
        variable_id="slack",
        kind=VariableKind.AUXILIARY,
        horizon_index=None,
        lower_bound=-2,
        upper_bound=2,
    )
    with pytest.raises(ValidationError, match="horizon_index"):
        BoundedMilpModel(
            model_id="bad-horizon",
            fixed_horizon=1,
            available_control_library=RegistryRef(
                registry_id="available-controls",
                registry_hash="a" * 64,
            ),
            registered_design_class=RegistryRef(
                registry_id="registered-designs",
                registry_hash="b" * 64,
            ),
            variables=(
                auxiliary,
                IntegerVariable(
                    variable_id="x",
                    horizon_index=1,
                    lower_bound=0,
                    upper_bound=1,
                ),
            ),
            available_control_variable_ids=("x",),
            constraints=(),
        )


@pytest.mark.parametrize(
    "dependency_name",
    [
        "_assignment_satisfies_constraints",
        "product",
        "Fraction",
        "_state_space_size",
        "_scope_variable_ids",
    ],
)
def test_checker_execution_closure_detects_monkeypatch_before_receipt(
    monkeypatch: pytest.MonkeyPatch,
    dependency_name: str,
) -> None:
    monkeypatch.setattr(
        milp_module,
        dependency_name,
        lambda *args, **kwargs: True,
    )
    with pytest.raises(RuntimeError, match="execution closure"):
        check_bounded_milp(
            _model(),
            scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
            state_limit=16,
        )


def test_strong_classification_embeds_receipt_but_is_not_a_bearer() -> None:
    model = _model(impossible=True)
    receipt = check_bounded_milp(
        model,
        scope=FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        state_limit=16,
    )
    classification = classify_planner_result(
        model,
        _not_found(model),
        registered_design_class_check=receipt,
    )
    assert classification.serialized_bearer_authorization is False
    assert classification.fresh_replay_required is True
    assert classification.registered_design_class_check == receipt
    assert classification.registered_design_class_check_sha256 == (
        canonical_sha256(receipt)
    )
