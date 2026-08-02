from __future__ import annotations

import hashlib

import pytest

from d2t_rna.contracts.base import canonical_sha256
from d2t_rna.contracts.enums import ExtendedValueTag
from d2t_rna.contracts.extended import (
    ExtendedValue,
    FiniteExtendedValue,
    NotAvailableExtendedValue,
    PositiveInfinityExtendedValue,
)
from d2t_rna.contracts.primitives import Rational, RegistryRef
from d2t_rna.evaluation.baselines import (
    BaselineCommonBinding,
    BaselineComparisonDisposition,
    BaselineEvaluationBatch,
    BaselineOutcome,
    BaselineSeedDeclaration,
    BaselineSeedResult,
    BaselineSpecification,
    MethodEvaluationResult,
    RandomBaselineSummary,
    build_baseline_common_binding,
    build_baseline_evaluation_batch,
    build_baseline_evaluation_batch_from_declarations,
    build_baseline_seed_declaration,
    build_baseline_seed_result,
    build_method_evaluation_result,
    compare_method_to_baselines,
    derive_random_seeds,
    replay_baseline_comparison,
    replay_random_baseline_summary,
    summarize_random_baseline,
)
from d2t_rna.evaluation.milp_check import (
    BoundedMilpModel,
    IntegerVariable,
)
from d2t_rna.evaluation.planner import (
    PlannerRunStatus,
    PlannerTerminationReason,
    RegisteredPlannerResult,
    build_coverage_feasibility_assessment,
)
from tests.evaluation.factories import (
    exact_synthetic_scenario_aggregate,
    formal_task4_scenario_aggregate,
    synthetic_task2_risk_replay_bundle,
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _finite(
    numerator: int,
    denominator: int = 1,
) -> FiniteExtendedValue:
    return FiniteExtendedValue(
        tag=ExtendedValueTag.FINITE,
        value=Rational(
            numerator=numerator,
            denominator=denominator,
        ),
    )


def _spec(baseline_id: str, *, root_tag: str) -> BaselineSpecification:
    return BaselineSpecification(
        baseline_id=baseline_id,
        implementation_sha256=_hash(f"implementation:{baseline_id}"),
        configuration_sha256=_hash(f"configuration:{baseline_id}"),
        seed_root_sha256=root_tag * 64,
    )


def _common_binding(
    specs: tuple[BaselineSpecification, ...] | None = None,
    *,
    tag: str = "1",
    formal_task4: bool = False,
) -> BaselineCommonBinding:
    registered = specs or (_spec("random", root_tag="1"),)
    model = BoundedMilpModel(
        model_id=f"baseline-model-{tag}",
        fixed_horizon=1,
        available_control_library=RegistryRef(
            registry_id=f"available-{tag}",
            registry_hash="a" * 64,
        ),
        registered_design_class=RegistryRef(
            registry_id=f"design-{tag}",
            registry_hash="b" * 64,
        ),
        variables=(
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=0,
            ),
        ),
        available_control_variable_ids=("x",),
        constraints=(),
    )
    risk_bundle = synthetic_task2_risk_replay_bundle(
        conditioning_sigma_field_hash=tag * 64,
    )
    risk = risk_bundle.inputs.risk_certificate
    planner_result = RegisteredPlannerResult(
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
    scenario_aggregate = (
        formal_task4_scenario_aggregate(
            conditioning_sigma_field_hash=(
                risk.conditioning_sigma_field_hash
            ),
            scenario_id=f"registered-formal-scenario-{tag}",
        )
        if formal_task4
        else exact_synthetic_scenario_aggregate(
            conditioning_sigma_field_hash=(
                risk.conditioning_sigma_field_hash
            ),
            scenario_id=f"registered-scenario-{tag}",
        )
    )
    assessment = build_coverage_feasibility_assessment(
        model,
        planner_result,
        risk_certificate=risk,
        risk_certificate_replay_bundle=risk_bundle,
        scenario_coverage_aggregate=scenario_aggregate,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
    )
    return build_baseline_common_binding(
        risk,
        assessment,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
        required_baseline_registry=registered,
    )


COMMON_BINDING = _common_binding()


def _results(
    binding: BaselineCommonBinding,
    baseline_id: str,
    *,
    infeasible: int = 0,
    unresolved: int = 0,
    zero_cost: bool = False,
) -> tuple[BaselineSeedResult, ...]:
    return _batch(
        binding,
        baseline_id,
        infeasible=infeasible,
        unresolved=unresolved,
        zero_cost=zero_cost,
    ).results


def _declarations(
    binding: BaselineCommonBinding,
    baseline_id: str,
    *,
    infeasible: int = 0,
    unresolved: int = 0,
    zero_cost: bool = False,
) -> tuple[BaselineSeedDeclaration, ...]:
    declarations: list[BaselineSeedDeclaration] = []
    for index in range(100):
        cost: ExtendedValue
        if index < unresolved:
            outcome = BaselineOutcome.UNRESOLVED
            cost = NotAvailableExtendedValue(tag=ExtendedValueTag.NA)
        elif index < unresolved + infeasible:
            outcome = BaselineOutcome.COMPLETED_INFEASIBLE
            cost = PositiveInfinityExtendedValue(
                tag=ExtendedValueTag.POS_INF
            )
        else:
            outcome = BaselineOutcome.FEASIBLE
            cost = _finite(0 if zero_cost else index + 1)
        declarations.append(
            build_baseline_seed_declaration(
                seed_index=index,
                outcome=outcome,
                cost=cost,
                execution_artifact_sha256=_hash(
                    f"{binding.common_binding_sha256}:"
                    f"{baseline_id}:{index}:{outcome.value}"
                ),
            )
        )
    return tuple(declarations)


def _batch(
    binding: BaselineCommonBinding,
    baseline_id: str,
    *,
    infeasible: int = 0,
    unresolved: int = 0,
    zero_cost: bool = False,
) -> BaselineEvaluationBatch:
    return build_baseline_evaluation_batch_from_declarations(
        binding,
        baseline_id=baseline_id,
        declarations=_declarations(
            binding,
            baseline_id,
            infeasible=infeasible,
            unresolved=unresolved,
            zero_cost=zero_cost,
        ),
    )


def _summary(
    binding: BaselineCommonBinding,
    baseline_id: str,
    *,
    infeasible: int = 0,
    unresolved: int = 0,
    zero_cost: bool = False,
) -> RandomBaselineSummary:
    batch = _batch(
        binding,
        baseline_id,
        infeasible=infeasible,
        unresolved=unresolved,
        zero_cost=zero_cost,
    )
    return summarize_random_baseline(batch)


def _method(
    binding: BaselineCommonBinding,
    *,
    outcome: BaselineOutcome = BaselineOutcome.FEASIBLE,
    cost: object | None = None,
) -> MethodEvaluationResult:
    if cost is None:
        if outcome is BaselineOutcome.FEASIBLE:
            cost = _finite(10)
        elif outcome is BaselineOutcome.COMPLETED_INFEASIBLE:
            cost = PositiveInfinityExtendedValue(
                tag=ExtendedValueTag.POS_INF
            )
        else:
            cost = NotAvailableExtendedValue(tag=ExtendedValueTag.NA)
    return build_method_evaluation_result(
        binding,
        method_id="registered-method",
        implementation_sha256="7" * 64,
        configuration_sha256="8" * 64,
        outcome=outcome,
        cost=cost,  # type: ignore[arg-type]
        execution_artifact_sha256="9" * 64,
    )


def test_common_binding_embeds_and_cross_checks_every_common_input() -> None:
    binding = COMMON_BINDING
    assert binding.schema_version == "2.0"
    assert binding.coverage_feasibility_assessment.schema_version == "5.0"
    assert binding.coverage_feasibility_assessment.risk_certificate_sha256 == (
        binding.risk_certificate_sha256
    )
    risk_bundle = (
        binding.coverage_feasibility_assessment.risk_certificate_replay_bundle
    )
    assert risk_bundle.schema_version == "3.0"
    assert risk_bundle.inputs.risk_certificate == binding.risk_certificate
    assert risk_bundle.task2_semantic_evaluator_replayed is True
    assert len(risk_bundle.task2_semantic_evaluator_execution_sha256) == 64
    assert risk_bundle.task5_risk_binding_evaluator_replayed is True
    assert len(
        risk_bundle.task5_risk_binding_evaluator_execution_sha256
    ) == 64
    assert risk_bundle.certificate_issued is False
    assert risk_bundle.scientific_claim_authorized is False
    scenario_manifest = (
        binding.coverage_feasibility_assessment
        .scenario_coverage_aggregate
        .per_scenario_proof_manifest[0]
    )
    assert scenario_manifest.formal_guarantee is False
    assert (
        binding.coverage_feasibility_assessment.scenario_formal_guarantee
        is False
    )
    assert (
        binding.coverage_feasibility_assessment
        .risk_probability_space_sha256
        == canonical_sha256(risk_bundle.inputs.probability_space)
    )
    assert (
        binding.coverage_feasibility_assessment
        .formal_scenario_probability_space_sha256s
        == ()
    )
    assert (
        binding.coverage_feasibility_assessment
        .risk_scenario_probability_space_binding_required
        is False
    )
    assert (
        binding.coverage_feasibility_assessment
        .risk_scenario_probability_space_binding_verified
        is False
    )
    assert (
        binding.coverage_feasibility_assessment
        .cfa_binding_execution_replayed
        is True
    )
    assert len(
        binding.coverage_feasibility_assessment
        .cfa_binding_execution_sha256
    ) == 64
    assert scenario_manifest.proof_artifact.schema_version == "1.0"
    assert (
        scenario_manifest.proof_artifact.schema_id
        == "d2t_rna.exact_enumeration_scenario_proof_artifact"
    )
    assert binding.yield_scope == (
        binding.coverage_feasibility_assessment.yield_scope
    )
    assert binding.cost_table == (
        binding.coverage_feasibility_assessment.cost_table
    )
    assert binding.expansion_order == (
        binding.coverage_feasibility_assessment.expansion_order
    )
    assert binding.required_baseline_registry_sha256 == canonical_sha256(
        binding.required_baseline_registry
    )
    assert binding.formal_scientific_certificate_authorized is False
    assert binding.scientific_claim_authorized is False
    assert binding.serialized_bearer_authorization is False

    forged = binding.model_copy(
        update={"risk_certificate_sha256": "f" * 64}
    )
    with pytest.raises(ValueError, match="fields do not replay"):
        build_baseline_seed_result(
            forged,
            baseline_id="random",
            seed_index=0,
            outcome=BaselineOutcome.FEASIBLE,
            cost=_finite(1),
            execution_artifact_sha256="a" * 64,
        )


def test_formal_task4_cfa_binds_the_same_risk_probability_space() -> None:
    binding = _common_binding(tag="e", formal_task4=True)
    assessment = binding.coverage_feasibility_assessment
    risk_space_sha256 = canonical_sha256(
        assessment.risk_certificate_replay_bundle.inputs.probability_space
    )
    manifest = assessment.scenario_coverage_aggregate
    proof_artifact = manifest.per_scenario_proof_manifest[0].proof_artifact

    assert assessment.schema_version == "5.0"
    assert assessment.scenario_formal_guarantee is True
    assert assessment.risk_probability_space_sha256 == risk_space_sha256
    assert assessment.formal_scenario_probability_space_sha256s == (
        risk_space_sha256,
    )
    assert assessment.risk_scenario_probability_space_binding_required is True
    assert assessment.risk_scenario_probability_space_binding_verified is True
    assert assessment.cfa_binding_execution_replayed is True
    assert len(assessment.cfa_binding_execution_sha256) == 64
    assert proof_artifact.schema_id == (
        "d2t_rna.exact_synthetic_scenario_proof_artifact"
    )
    assert proof_artifact.schema_version == "2.0"
    assert binding.formal_scientific_certificate_authorized is False
    assert binding.scientific_claim_authorized is False


def test_required_registry_is_canonical_and_seed_schedule_is_exact() -> None:
    binding = _common_binding(
        (
            _spec("z-rival", root_tag="2"),
            _spec("a-rival", root_tag="3"),
        )
    )
    assert tuple(
        item.baseline_id for item in binding.required_baseline_registry
    ) == ("a-rival", "z-rival")
    for spec in binding.required_baseline_registry:
        seeds = derive_random_seeds(spec.seed_root_sha256)
        assert len(seeds) == 100
        assert tuple(item.seed_index for item in seeds) == tuple(range(100))
        assert len({item.seed for item in seeds}) == 100


def test_seed_results_cannot_be_relabelled_or_moved_to_another_root() -> None:
    binding = _common_binding(
        (
            _spec("a-rival", root_tag="1"),
            _spec("b-rival", root_tag="2"),
        )
    )
    a_results = _results(binding, "a-rival")
    with pytest.raises(ValueError, match="binding differs"):
        build_baseline_evaluation_batch(
            binding,
            baseline_id="b-rival",
            results=a_results,
        )

    other_binding = _common_binding(
        (_spec("a-rival", root_tag="1"),),
        tag="2",
    )
    with pytest.raises(ValueError, match="binding differs"):
        build_baseline_evaluation_batch(
            other_binding,
            baseline_id="a-rival",
            results=a_results,
        )


def test_seed_and_method_execution_claims_are_fail_closed() -> None:
    results = _results(COMMON_BINDING, "random")
    seed = results[0]
    method = _method(COMMON_BINDING)

    assert seed.schema_version == "3.0"
    assert seed.execution_artifact_replayed is False
    assert seed.outcome_execution_verified is False
    assert seed.release_claim_authorized is False
    assert method.schema_version == "3.0"
    assert method.execution_artifact_replayed is False
    assert method.outcome_execution_verified is False
    assert method.release_claim_authorized is False

    forged_seed = seed.model_copy(
        update={
            "execution_artifact_replayed": True,
            "outcome_execution_verified": True,
            "release_claim_authorized": True,
        }
    )
    forged_results = (forged_seed, *results[1:])
    with pytest.raises(ValueError, match="False|replay"):
        build_baseline_evaluation_batch(
            COMMON_BINDING,
            baseline_id="random",
            results=forged_results,
        )

    forged_method = method.model_copy(
        update={
            "execution_artifact_replayed": True,
            "outcome_execution_verified": True,
            "release_claim_authorized": True,
        }
    )
    with pytest.raises(ValueError, match="False|replay"):
        compare_method_to_baselines(
            method_result=forged_method,
            baseline_summaries=(
                _summary(COMMON_BINDING, "random"),
            ),
        )


def test_batch_requires_complete_ordered_100_results() -> None:
    results = _results(COMMON_BINDING, "random")
    with pytest.raises(ValueError, match="exactly 100"):
        build_baseline_evaluation_batch(
            COMMON_BINDING,
            baseline_id="random",
            results=results[:-1],
        )
    reordered = list(results)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(ValueError, match="index and order"):
        build_baseline_evaluation_batch(
            COMMON_BINDING,
            baseline_id="random",
            results=reordered,
        )


def test_bulk_builder_replays_one_ordered_nonbearer_declaration_set() -> None:
    declarations = _declarations(COMMON_BINDING, "random")
    batch = build_baseline_evaluation_batch_from_declarations(
        COMMON_BINDING,
        baseline_id="random",
        declarations=declarations,
    )
    first = build_baseline_seed_result(
        COMMON_BINDING,
        baseline_id="random",
        seed_index=0,
        outcome=BaselineOutcome.FEASIBLE,
        cost=_finite(1),
        execution_artifact_sha256=declarations[0].execution_artifact_sha256,
    )

    assert declarations[0].schema_version == "1.0"
    assert declarations[0].execution_artifact_replayed is False
    assert declarations[0].outcome_execution_verified is False
    assert declarations[0].release_claim_authorized is False
    assert batch.schema_version == "3.0"
    assert batch.results[0] == first
    assert batch.all_seed_execution_artifacts_replayed is False
    assert batch.all_seed_outcomes_execution_verified is False
    assert batch.release_claim_authorized is False

    with pytest.raises(ValueError, match="exactly 100"):
        build_baseline_evaluation_batch_from_declarations(
            COMMON_BINDING,
            baseline_id="random",
            declarations=declarations[:-1],
        )

    reordered = list(declarations)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(ValueError, match="index and order"):
        build_baseline_evaluation_batch_from_declarations(
            COMMON_BINDING,
            baseline_id="random",
            declarations=reordered,
        )

    forged = declarations[0].model_copy(
        update={
            "execution_artifact_replayed": True,
            "outcome_execution_verified": True,
            "release_claim_authorized": True,
        }
    )
    with pytest.raises(ValueError, match="False"):
        build_baseline_evaluation_batch_from_declarations(
            COMMON_BINDING,
            baseline_id="random",
            declarations=(forged, *declarations[1:]),
        )


@pytest.mark.parametrize(
    ("outcome", "cost"),
    (
        (
            BaselineOutcome.FEASIBLE,
            PositiveInfinityExtendedValue(tag=ExtendedValueTag.POS_INF),
        ),
        (
            BaselineOutcome.COMPLETED_INFEASIBLE,
            NotAvailableExtendedValue(tag=ExtendedValueTag.NA),
        ),
        (
            BaselineOutcome.UNRESOLVED,
            _finite(1),
        ),
    ),
)
def test_outcome_to_extended_value_mapping_is_strict(
    outcome: BaselineOutcome,
    cost: object,
) -> None:
    with pytest.raises(ValueError, match="must map"):
        build_baseline_seed_result(
            COMMON_BINDING,
            baseline_id="random",
            seed_index=0,
            outcome=outcome,
            cost=cost,  # type: ignore[arg-type]
            execution_artifact_sha256="a" * 64,
        )


def test_any_unresolved_is_primary_na_but_resolved_only_remains() -> None:
    summary = _summary(COMMON_BINDING, "random", unresolved=1)
    assert summary.extended_cost_median.tag is ExtendedValueTag.NA
    assert summary.resolved_only_extended_median.tag is (
        ExtendedValueTag.FINITE
    )
    assert summary.unresolved_fraction == Rational(
        numerator=1,
        denominator=100,
    )


@pytest.mark.parametrize(
    ("infeasible", "expected_tag"),
    (
        (49, ExtendedValueTag.FINITE),
        (50, ExtendedValueTag.POS_INF),
        (51, ExtendedValueTag.POS_INF),
    ),
)
def test_extended_median_freezes_49_50_51_infinity_boundary(
    infeasible: int,
    expected_tag: ExtendedValueTag,
) -> None:
    summary = _summary(
        COMMON_BINDING,
        "random",
        infeasible=infeasible,
    )
    assert summary.extended_cost_median.tag is expected_tag


def test_all_na_has_no_resolved_or_feasible_ordering() -> None:
    summary = _summary(COMMON_BINDING, "random", unresolved=100)
    assert summary.extended_cost_median.tag is ExtendedValueTag.NA
    assert summary.resolved_only_extended_median.tag is ExtendedValueTag.NA
    assert summary.feasible_cost_median.tag is ExtendedValueTag.NA
    assert summary.feasible_cost_iqr.tag is ExtendedValueTag.NA


def test_even_feasible_median_and_iqr_are_exact_and_not_best_of() -> None:
    summary = _summary(COMMON_BINDING, "random")
    assert summary.feasible_cost_median == _finite(101, 2)
    assert summary.feasible_cost_q1 == _finite(51, 2)
    assert summary.feasible_cost_q3 == _finite(151, 2)
    assert summary.feasible_cost_iqr == _finite(50)
    assert summary.extended_cost_median != _finite(1)


@pytest.mark.parametrize(
    (
        "unresolved",
        "expected_median",
        "expected_q1",
        "expected_q3",
        "expected_iqr",
    ),
    (
        (99, _finite(100), _finite(100), _finite(100), _finite(0)),
        (98, _finite(199, 2), _finite(99), _finite(100), _finite(1)),
        (97, _finite(99), _finite(98), _finite(100), _finite(2)),
    ),
)
def test_one_two_three_feasible_iqr_edges_are_frozen(
    unresolved: int,
    expected_median: FiniteExtendedValue,
    expected_q1: FiniteExtendedValue,
    expected_q3: FiniteExtendedValue,
    expected_iqr: FiniteExtendedValue,
) -> None:
    summary = _summary(
        COMMON_BINDING,
        "random",
        unresolved=unresolved,
    )
    assert summary.feasible_cost_median == expected_median
    assert summary.feasible_cost_q1 == expected_q1
    assert summary.feasible_cost_q3 == expected_q3
    assert summary.feasible_cost_iqr == expected_iqr


def test_summary_direct_forgery_cannot_create_false_dominance() -> None:
    summary = _summary(COMMON_BINDING, "random")
    payload = summary.model_dump(mode="python")
    na = NotAvailableExtendedValue(tag=ExtendedValueTag.NA)
    inf = PositiveInfinityExtendedValue(tag=ExtendedValueTag.POS_INF)
    payload.update(
        {
            "feasible_count": 0,
            "completed_infeasible_count": 100,
            "feasibility_fraction": Rational(
                numerator=0,
                denominator=1,
            ),
            "extended_cost_median": inf,
            "resolved_only_extended_median": inf,
            "feasible_cost_median": na,
            "feasible_cost_q1": na,
            "feasible_cost_q3": na,
            "feasible_cost_iqr": na,
        }
    )
    payload_without_hash = dict(payload)
    payload_without_hash.pop("summary_sha256")
    payload["summary_sha256"] = canonical_sha256(payload_without_hash)
    with pytest.raises(ValueError, match="do not replay from batch"):
        RandomBaselineSummary.model_validate(payload, strict=True)

    forged = summary.model_copy(
        update={
            "feasible_count": 0,
            "completed_infeasible_count": 100,
        }
    )
    with pytest.raises(ValueError, match="do not replay from batch"):
        replay_random_baseline_summary(forged)


def test_comparison_rejects_missing_required_rival() -> None:
    binding = _common_binding(
        (
            _spec("a-infeasible", root_tag="1"),
            _spec("b-feasible", root_tag="2"),
        )
    )
    infeasible = _summary(
        binding,
        "a-infeasible",
        infeasible=100,
    )
    feasible = _summary(binding, "b-feasible")
    method = _method(binding)
    with pytest.raises(ValueError, match="exact required registry"):
        compare_method_to_baselines(
            method_result=method,
            baseline_summaries=(infeasible,),
        )
    comparison = compare_method_to_baselines(
        method_result=method,
        baseline_summaries=(infeasible, feasible),
    )
    assert comparison.disposition is (
        BaselineComparisonDisposition.FINITE_COST_RATIO
    )
    assert comparison.reference_baseline_id == "b-feasible"


def test_all_required_rivals_infeasible_is_dominance_without_ratio() -> None:
    binding = _common_binding(
        (
            _spec("a-rival", root_tag="1"),
            _spec("b-rival", root_tag="2"),
        )
    )
    summaries = tuple(
        _summary(binding, spec.baseline_id, infeasible=100)
        for spec in binding.required_baseline_registry
    )
    comparison = compare_method_to_baselines(
        method_result=_method(binding),
        baseline_summaries=summaries,
    )
    assert comparison.disposition is (
        BaselineComparisonDisposition.FEASIBILITY_DOMINANCE
    )
    assert comparison.cost_ratio is None
    assert comparison.reference_baseline_id is None
    assert comparison.schema_version == "3.0"
    assert (
        comparison.comparison_scope
        == "STRUCTURAL_HASH_BOUND_DECLARATIONS_ONLY"
    )
    assert comparison.all_execution_artifacts_replayed is False
    assert comparison.all_outcomes_execution_verified is False
    assert comparison.release_claim_authorized is False
    for summary in comparison.baseline_summaries:
        assert summary.schema_version == "3.0"
        assert summary.batch.schema_version == "3.0"
        assert summary.all_seed_execution_artifacts_replayed is False
        assert summary.all_seed_outcomes_execution_verified is False
        assert summary.release_claim_authorized is False


def test_method_result_binds_outcome_cost_and_common_binding() -> None:
    with pytest.raises(ValueError, match="must map"):
        _method(
            COMMON_BINDING,
            outcome=BaselineOutcome.UNRESOLVED,
            cost=_finite(1),
        )
    method = _method(COMMON_BINDING)
    other_binding = _common_binding(tag="2")
    forged = method.model_copy(
        update={
            "common_binding": other_binding,
            "common_binding_sha256": other_binding.common_binding_sha256,
        }
    )
    with pytest.raises(ValueError, match="does not replay"):
        compare_method_to_baselines(
            method_result=forged,
            baseline_summaries=(
                _summary(other_binding, "random"),
            ),
        )


@pytest.mark.parametrize(
    "invalid_method_id",
    (
        "has space",
        "-cannot-start-with-hyphen",
        "a" * 129,
    ),
)
def test_method_builder_rejects_invalid_registered_id(
    invalid_method_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="method_id must satisfy the RegisteredId contract",
    ):
        build_method_evaluation_result(
            COMMON_BINDING,
            method_id=invalid_method_id,
            implementation_sha256="7" * 64,
            configuration_sha256="8" * 64,
            outcome=BaselineOutcome.FEASIBLE,
            cost=_finite(10),
            execution_artifact_sha256="9" * 64,
        )


def test_comparison_edges_are_fail_closed() -> None:
    unresolved = _summary(
        COMMON_BINDING,
        "random",
        unresolved=1,
    )
    comparison = compare_method_to_baselines(
        method_result=_method(COMMON_BINDING),
        baseline_summaries=(unresolved,),
    )
    assert comparison.disposition is (
        BaselineComparisonDisposition.NOT_COMPARABLE
    )
    assert comparison.cost_ratio is None

    zero = _summary(COMMON_BINDING, "random", zero_cost=True)
    zero_comparison = compare_method_to_baselines(
        method_result=_method(COMMON_BINDING),
        baseline_summaries=(zero,),
    )
    assert zero_comparison.disposition is (
        BaselineComparisonDisposition.NOT_COMPARABLE
    )

    method_na = _method(
        COMMON_BINDING,
        outcome=BaselineOutcome.UNRESOLVED,
    )
    method_na_comparison = compare_method_to_baselines(
        method_result=method_na,
        baseline_summaries=(
            _summary(COMMON_BINDING, "random"),
        ),
    )
    assert method_na_comparison.disposition is (
        BaselineComparisonDisposition.NOT_COMPARABLE
    )


def test_comparison_records_sources_and_direct_forgery_fails_replay() -> None:
    summary = _summary(COMMON_BINDING, "random")
    comparison = compare_method_to_baselines(
        method_result=_method(COMMON_BINDING),
        baseline_summaries=(summary,),
    )
    assert comparison.method_evaluation_result_sha256 == (
        comparison.method_result.result_sha256
    )
    assert comparison.baseline_summary_commitments[0].summary_sha256 == (
        summary.summary_sha256
    )
    assert comparison.formal_scientific_certificate_authorized is False
    assert comparison.scientific_claim_authorized is False
    assert comparison.serialized_bearer_authorization is False
    assert comparison.release_claim_authorized is False
    assert comparison.all_execution_artifacts_replayed is False
    assert comparison.all_outcomes_execution_verified is False
    assert replay_baseline_comparison(comparison) == comparison

    forged_payload = comparison.model_dump(mode="python")
    forged_payload.update(
        {
            "disposition": (
                BaselineComparisonDisposition.FEASIBILITY_DOMINANCE
            ),
            "reference_baseline_id": None,
            "reference_baseline_summary_sha256": None,
            "cost_ratio": None,
        }
    )
    without_hash = dict(forged_payload)
    without_hash.pop("comparison_sha256")
    forged_payload["comparison_sha256"] = canonical_sha256(without_hash)
    with pytest.raises(ValueError, match="does not replay"):
        type(comparison).model_validate(forged_payload, strict=True)

    forged = comparison.model_copy(
        update={
            "disposition": (
                BaselineComparisonDisposition.FEASIBILITY_DOMINANCE
            ),
            "reference_baseline_id": None,
            "reference_baseline_summary_sha256": None,
            "cost_ratio": None,
        }
    )
    with pytest.raises(ValueError, match="does not replay"):
        replay_baseline_comparison(forged)

    self_signed_payload = comparison.model_dump(mode="python")
    self_signed_payload.update(
        {
            "all_execution_artifacts_replayed": True,
            "all_outcomes_execution_verified": True,
            "release_claim_authorized": True,
        }
    )
    without_hash = dict(self_signed_payload)
    without_hash.pop("comparison_sha256")
    self_signed_payload["comparison_sha256"] = canonical_sha256(without_hash)
    with pytest.raises(ValueError, match="False"):
        type(comparison).model_validate(self_signed_payload, strict=True)
