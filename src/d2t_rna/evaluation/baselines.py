"""Replayable, fail-closed baseline evaluation artifacts.

These models replay declarations, hashes, seed schedules, and derived
statistics.  They do not execute a method or baseline runner and therefore
cannot verify the outcomes behind caller-supplied execution-artifact hashes.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from fractions import Fraction
from typing import Annotated, Literal, Sequence, cast

from pydantic import Field, StrictInt, TypeAdapter, ValidationError, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import ExtendedValueTag
from d2t_rna.contracts.extended import (
    ExtendedValue,
    FiniteExtendedValue,
    NotAvailableExtendedValue,
    PositiveInfinityExtendedValue,
    parse_extended_value,
)
from d2t_rna.contracts.primitives import (
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.risk import RiskCertificate

from .planner import CoverageFeasibilityAssessment


RANDOM_BASELINE_SEED_COUNT = 100
RANDOM_SEED_DERIVATION_ALGORITHM = (
    "SHA256_DOMAIN_ROOT_BYTES_UINT32BE_INDEX_TO_UINT63BE_V1"
)
EXTENDED_MEDIAN_ALGORITHM = (
    "SORT_FINITE_BEFORE_POS_INF_EXACT_MIDDLE_MEAN_V1"
)
FEASIBLE_IQR_ALGORITHM = (
    "SORT_EXACT_EXCLUDE_ODD_CENTER_MEDIAN_OF_HALVES_Q3_MINUS_Q1_V1"
)
BASELINE_COMPARISON_ALGORITHM = (
    "METHOD_OVER_LOWEST_FINITE_REQUIRED_RIVAL_MEDIAN_V2"
)
BASELINE_COMPARISON_SCOPE = "STRUCTURAL_HASH_BOUND_DECLARATIONS_ONLY"

_SEED_DOMAIN = b"D2T-RNA/random-baseline-seed/v1\x00"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_UINT63_MASK = (1 << 63) - 1
_REGISTERED_ID_ADAPTER = TypeAdapter(RegisteredId)

SeedIndex = Annotated[
    StrictInt,
    Field(ge=0, lt=RANDOM_BASELINE_SEED_COUNT),
]
SeedInteger = Annotated[StrictInt, Field(ge=0, le=_UINT63_MASK)]
SeedCount = Annotated[
    StrictInt,
    Field(ge=0, le=RANDOM_BASELINE_SEED_COUNT),
]


class BaselineOutcome(str, Enum):
    FEASIBLE = "FEASIBLE"
    COMPLETED_INFEASIBLE = "COMPLETED_INFEASIBLE"
    UNRESOLVED = "UNRESOLVED"


class BaselineComparisonDisposition(str, Enum):
    FINITE_COST_RATIO = "FINITE_COST_RATIO"
    FEASIBILITY_DOMINANCE = "FEASIBILITY_DOMINANCE"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class BaselineSpecification(FrozenContractModel):
    """One required rival and its frozen implementation, config, and seeds."""

    baseline_id: RegisteredId
    implementation_sha256: Sha256Hex
    configuration_sha256: Sha256Hex
    seed_root_sha256: Sha256Hex


class BaselineSeed(FrozenContractModel):
    seed_index: SeedIndex
    seed: SeedInteger
    seed_sha256: Sha256Hex


def _require_sha256(value: object, *, field_name: str) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")
    return value


def _require_registered_id(value: object, *, field_name: str) -> str:
    try:
        return _REGISTERED_ID_ADAPTER.validate_python(value, strict=True)
    except ValidationError as exc:
        raise ValueError(
            f"{field_name} must satisfy the RegisteredId contract"
        ) from exc


def _seed_at(seed_root_sha256: str, seed_index: int) -> BaselineSeed:
    root = _require_sha256(
        seed_root_sha256,
        field_name="seed_root_sha256",
    )
    if (
        type(seed_index) is not int
        or seed_index < 0
        or seed_index >= RANDOM_BASELINE_SEED_COUNT
    ):
        raise ValueError("seed_index must be an integer in [0, 100)")
    digest = hashlib.sha256(
        _SEED_DOMAIN
        + bytes.fromhex(root)
        + seed_index.to_bytes(4, byteorder="big", signed=False)
    ).digest()
    return BaselineSeed(
        seed_index=seed_index,
        seed=int.from_bytes(digest[:8], byteorder="big") & _UINT63_MASK,
        seed_sha256=digest.hex(),
    )


def derive_random_seeds(
    seed_root_sha256: str,
) -> tuple[BaselineSeed, ...]:
    seeds = tuple(
        _seed_at(seed_root_sha256, index)
        for index in range(RANDOM_BASELINE_SEED_COUNT)
    )
    if (
        len({item.seed for item in seeds}) != RANDOM_BASELINE_SEED_COUNT
        or len({item.seed_sha256 for item in seeds})
        != RANDOM_BASELINE_SEED_COUNT
    ):
        raise RuntimeError(
            "SHA-derived random-baseline seed schedule is not unique"
        )
    return seeds


def _strict_registry_ref(value: RegistryRef, *, label: str) -> RegistryRef:
    if type(value) is not RegistryRef:
        raise TypeError(f"{label} must be exactly RegistryRef")
    return strict_revalidate_contract_model(value)


def _strict_spec(value: BaselineSpecification) -> BaselineSpecification:
    if type(value) is not BaselineSpecification:
        raise TypeError(
            "required registry members must be BaselineSpecification"
        )
    return strict_revalidate_contract_model(value)


def _canonical_specs(
    values: Sequence[BaselineSpecification],
) -> tuple[BaselineSpecification, ...]:
    specs = tuple(_strict_spec(value) for value in values)
    if not specs:
        raise ValueError("required baseline registry cannot be empty")
    ordered = tuple(sorted(specs, key=lambda item: item.baseline_id))
    ids = tuple(item.baseline_id for item in ordered)
    if len(set(ids)) != len(ids):
        raise ValueError("required baseline identifiers must be unique")
    return ordered


def _common_binding_payload(
    risk_certificate: RiskCertificate,
    assessment: CoverageFeasibilityAssessment,
    yield_scope: RegistryRef,
    cost_table: RegistryRef,
    expansion_order: RegistryRef,
    registry: tuple[BaselineSpecification, ...],
) -> dict[str, object]:
    return {
        "schema_id": "d2t_rna.baseline_common_binding",
        "schema_version": "2.0",
        "risk_certificate": risk_certificate,
        "risk_certificate_sha256": canonical_sha256(risk_certificate),
        "coverage_feasibility_assessment": assessment,
        "coverage_feasibility_assessment_sha256": canonical_sha256(
            assessment
        ),
        "coverage_feasibility_common_binding_sha256": (
            assessment.common_binding_sha256
        ),
        "yield_scope": yield_scope,
        "cost_table": cost_table,
        "expansion_order": expansion_order,
        "required_baseline_registry": registry,
        "required_baseline_registry_sha256": canonical_sha256(registry),
        "formal_scientific_certificate_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class BaselineCommonBinding(FrozenContractModel):
    """Non-bearer closure over every common baseline input and rival spec."""

    schema_id: Literal["d2t_rna.baseline_common_binding"] = (
        "d2t_rna.baseline_common_binding"
    )
    schema_version: Literal["2.0"] = "2.0"
    risk_certificate: RiskCertificate
    risk_certificate_sha256: Sha256Hex
    coverage_feasibility_assessment: CoverageFeasibilityAssessment
    coverage_feasibility_assessment_sha256: Sha256Hex
    coverage_feasibility_common_binding_sha256: Sha256Hex
    yield_scope: RegistryRef
    cost_table: RegistryRef
    expansion_order: RegistryRef
    required_baseline_registry: tuple[BaselineSpecification, ...]
    required_baseline_registry_sha256: Sha256Hex
    common_binding_sha256: Sha256Hex
    formal_scientific_certificate_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def embedded_objects_and_hashes_replay(self) -> "BaselineCommonBinding":
        risk = strict_revalidate_contract_model(self.risk_certificate)
        assessment = strict_revalidate_contract_model(
            self.coverage_feasibility_assessment
        )
        yield_scope = _strict_registry_ref(
            self.yield_scope,
            label="yield_scope",
        )
        cost_table = _strict_registry_ref(
            self.cost_table,
            label="cost_table",
        )
        expansion_order = _strict_registry_ref(
            self.expansion_order,
            label="expansion_order",
        )
        registry = _canonical_specs(self.required_baseline_registry)
        if registry != self.required_baseline_registry:
            raise ValueError(
                "required baseline registry must be in canonical ID order"
            )
        if assessment.risk_certificate_sha256 != canonical_sha256(risk):
            raise ValueError(
                "embedded RiskCertificate differs from embedded assessment"
            )
        if assessment.risk_certificate_probability_scope is not (
            risk.probability_scope
        ):
            raise ValueError(
                "RiskCertificate probability scope differs from assessment"
            )
        for label, left, right in (
            ("yield scope", yield_scope, assessment.yield_scope),
            ("cost table", cost_table, assessment.cost_table),
            (
                "expansion order",
                expansion_order,
                assessment.expansion_order,
            ),
        ):
            if left != right:
                raise ValueError(
                    f"baseline {label} differs from embedded assessment"
                )
        expected = _common_binding_payload(
            risk,
            assessment,
            yield_scope,
            cost_table,
            expansion_order,
            registry,
        )
        actual = self.model_dump(
            mode="python",
            exclude={"common_binding_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError("baseline common binding fields do not replay")
        if canonical_sha256(expected) != self.common_binding_sha256:
            raise ValueError("baseline common binding hash does not replay")
        return self


def build_baseline_common_binding(
    risk_certificate: RiskCertificate,
    coverage_feasibility_assessment: CoverageFeasibilityAssessment,
    *,
    yield_scope: RegistryRef,
    cost_table: RegistryRef,
    expansion_order: RegistryRef,
    required_baseline_registry: Sequence[BaselineSpecification],
) -> BaselineCommonBinding:
    if type(risk_certificate) is not RiskCertificate:
        raise TypeError("risk_certificate must be exactly RiskCertificate")
    if (
        type(coverage_feasibility_assessment)
        is not CoverageFeasibilityAssessment
    ):
        raise TypeError(
            "coverage_feasibility_assessment must be exactly "
            "CoverageFeasibilityAssessment"
        )
    risk = strict_revalidate_contract_model(risk_certificate)
    assessment = strict_revalidate_contract_model(
        coverage_feasibility_assessment
    )
    checked_yield = _strict_registry_ref(yield_scope, label="yield_scope")
    checked_cost = _strict_registry_ref(cost_table, label="cost_table")
    checked_order = _strict_registry_ref(
        expansion_order,
        label="expansion_order",
    )
    registry = _canonical_specs(required_baseline_registry)
    payload = _common_binding_payload(
        risk,
        assessment,
        checked_yield,
        checked_cost,
        checked_order,
        registry,
    )
    return BaselineCommonBinding.model_validate(
        {
            **payload,
            "common_binding_sha256": canonical_sha256(payload),
        },
        strict=True,
    )


def _strict_common_binding(
    value: BaselineCommonBinding,
) -> BaselineCommonBinding:
    if type(value) is not BaselineCommonBinding:
        raise TypeError("common_binding must be exactly BaselineCommonBinding")
    return strict_revalidate_contract_model(value)


def _spec_for(
    binding: BaselineCommonBinding,
    baseline_id: str,
) -> BaselineSpecification:
    matches = tuple(
        spec
        for spec in binding.required_baseline_registry
        if spec.baseline_id == baseline_id
    )
    if len(matches) != 1:
        raise ValueError(
            f"baseline {baseline_id!r} is not exactly once in required registry"
        )
    return matches[0]


def _validate_outcome_cost(
    outcome: BaselineOutcome,
    cost: ExtendedValue,
) -> ExtendedValue:
    checked = parse_extended_value(cost)
    expected: type[
        FiniteExtendedValue
        | PositiveInfinityExtendedValue
        | NotAvailableExtendedValue
    ]
    if outcome is BaselineOutcome.FEASIBLE:
        expected = FiniteExtendedValue
    elif outcome is BaselineOutcome.COMPLETED_INFEASIBLE:
        expected = PositiveInfinityExtendedValue
    else:
        expected = NotAvailableExtendedValue
    if type(checked) is not expected:
        raise ValueError(
            f"{outcome.value} must map to {expected.__name__}"
        )
    if (
        type(checked) is FiniteExtendedValue
        and checked.value.numerator < 0
    ):
        raise ValueError("feasible cost must be non-negative")
    return checked


class BaselineSeedDeclaration(FrozenContractModel):
    """One non-bearer caller declaration consumed by the bulk builder."""

    schema_id: Literal["d2t_rna.baseline_seed_declaration"] = (
        "d2t_rna.baseline_seed_declaration"
    )
    schema_version: Literal["1.0"] = "1.0"
    seed_index: SeedIndex
    outcome: BaselineOutcome
    cost: ExtendedValue
    execution_artifact_sha256: Sha256Hex
    execution_artifact_replayed: Literal[False] = False
    outcome_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def declaration_is_structural_only(
        self,
    ) -> "BaselineSeedDeclaration":
        _validate_outcome_cost(self.outcome, self.cost)
        _require_sha256(
            self.execution_artifact_sha256,
            field_name="execution_artifact_sha256",
        )
        return self


def build_baseline_seed_declaration(
    *,
    seed_index: int,
    outcome: BaselineOutcome,
    cost: ExtendedValue,
    execution_artifact_sha256: str,
) -> BaselineSeedDeclaration:
    """Validate one caller declaration without claiming runner execution."""

    if type(outcome) is not BaselineOutcome:
        raise TypeError("outcome must be exactly BaselineOutcome")
    checked_cost = _validate_outcome_cost(outcome, cost)
    artifact_hash = _require_sha256(
        execution_artifact_sha256,
        field_name="execution_artifact_sha256",
    )
    return BaselineSeedDeclaration(
        seed_index=seed_index,
        outcome=outcome,
        cost=checked_cost,
        execution_artifact_sha256=artifact_hash,
        execution_artifact_replayed=False,
        outcome_execution_verified=False,
        release_claim_authorized=False,
        scientific_claim_authorized=False,
        serialized_bearer_authorization=False,
    )


def _seed_result_payload(
    *,
    baseline_id: str,
    common_binding_sha256: str,
    seed_root_sha256: str,
    implementation_sha256: str,
    configuration_sha256: str,
    seed: BaselineSeed,
    outcome: BaselineOutcome,
    cost: ExtendedValue,
    execution_artifact_sha256: str,
) -> dict[str, object]:
    return {
        "schema_id": "d2t_rna.baseline_seed_result",
        "schema_version": "3.0",
        "baseline_id": baseline_id,
        "common_binding_sha256": common_binding_sha256,
        "seed_root_sha256": seed_root_sha256,
        "baseline_implementation_sha256": implementation_sha256,
        "baseline_configuration_sha256": configuration_sha256,
        "seed_index": seed.seed_index,
        "seed": seed.seed,
        "seed_sha256": seed.seed_sha256,
        "outcome": outcome,
        "cost": cost,
        "execution_artifact_sha256": execution_artifact_sha256,
        "execution_artifact_replayed": False,
        "outcome_execution_verified": False,
        "release_claim_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class BaselineSeedResult(FrozenContractModel):
    """One hash-bound caller declaration, not a replayed execution result."""

    schema_id: Literal["d2t_rna.baseline_seed_result"] = (
        "d2t_rna.baseline_seed_result"
    )
    schema_version: Literal["3.0"] = "3.0"
    baseline_id: RegisteredId
    common_binding_sha256: Sha256Hex
    seed_root_sha256: Sha256Hex
    baseline_implementation_sha256: Sha256Hex
    baseline_configuration_sha256: Sha256Hex
    seed_index: SeedIndex
    seed: SeedInteger
    seed_sha256: Sha256Hex
    outcome: BaselineOutcome
    cost: ExtendedValue
    execution_artifact_sha256: Sha256Hex
    result_sha256: Sha256Hex
    execution_artifact_replayed: Literal[False] = False
    outcome_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def bindings_and_outcome_replay(self) -> "BaselineSeedResult":
        checked_cost = _validate_outcome_cost(self.outcome, self.cost)
        expected_seed = _seed_at(self.seed_root_sha256, self.seed_index)
        if (
            self.seed != expected_seed.seed
            or self.seed_sha256 != expected_seed.seed_sha256
        ):
            raise ValueError("seed does not replay from root and index")
        expected = _seed_result_payload(
            baseline_id=self.baseline_id,
            common_binding_sha256=self.common_binding_sha256,
            seed_root_sha256=self.seed_root_sha256,
            implementation_sha256=self.baseline_implementation_sha256,
            configuration_sha256=self.baseline_configuration_sha256,
            seed=expected_seed,
            outcome=self.outcome,
            cost=checked_cost,
            execution_artifact_sha256=self.execution_artifact_sha256,
        )
        actual = self.model_dump(
            mode="python",
            exclude={"result_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError("baseline seed result fields do not replay")
        if canonical_sha256(expected) != self.result_sha256:
            raise ValueError("baseline seed result hash does not replay")
        return self


def _seed_result_from_binding_and_declaration(
    binding: BaselineCommonBinding,
    spec: BaselineSpecification,
    declaration: BaselineSeedDeclaration,
) -> BaselineSeedResult:
    seed = _seed_at(spec.seed_root_sha256, declaration.seed_index)
    payload = _seed_result_payload(
        baseline_id=spec.baseline_id,
        common_binding_sha256=binding.common_binding_sha256,
        seed_root_sha256=spec.seed_root_sha256,
        implementation_sha256=spec.implementation_sha256,
        configuration_sha256=spec.configuration_sha256,
        seed=seed,
        outcome=declaration.outcome,
        cost=declaration.cost,
        execution_artifact_sha256=(
            declaration.execution_artifact_sha256
        ),
    )
    return BaselineSeedResult.model_validate(
        {
            **payload,
            "result_sha256": canonical_sha256(payload),
        },
        strict=True,
    )


def build_baseline_seed_result(
    common_binding: BaselineCommonBinding,
    *,
    baseline_id: str,
    seed_index: int,
    outcome: BaselineOutcome,
    cost: ExtendedValue,
    execution_artifact_sha256: str,
) -> BaselineSeedResult:
    binding = _strict_common_binding(common_binding)
    spec = _spec_for(binding, baseline_id)
    declaration = build_baseline_seed_declaration(
        seed_index=seed_index,
        outcome=outcome,
        cost=cost,
        execution_artifact_sha256=execution_artifact_sha256,
    )
    return _seed_result_from_binding_and_declaration(
        binding,
        spec,
        declaration,
    )


def _batch_payload(
    common_binding: BaselineCommonBinding,
    spec: BaselineSpecification,
    results: tuple[BaselineSeedResult, ...],
) -> dict[str, object]:
    return {
        "schema_id": "d2t_rna.baseline_evaluation_batch",
        "schema_version": "3.0",
        "common_binding": common_binding,
        "common_binding_sha256": common_binding.common_binding_sha256,
        "baseline_specification": spec,
        "baseline_specification_sha256": canonical_sha256(spec),
        "baseline_id": spec.baseline_id,
        "seed_root_sha256": spec.seed_root_sha256,
        "baseline_implementation_sha256": spec.implementation_sha256,
        "baseline_configuration_sha256": spec.configuration_sha256,
        "results": results,
        "seed_results_sha256": canonical_sha256(results),
        "all_seed_execution_artifacts_replayed": False,
        "all_seed_outcomes_execution_verified": False,
        "release_claim_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class BaselineEvaluationBatch(FrozenContractModel):
    """Complete ordered 100-declaration artifact for one required rival."""

    schema_id: Literal["d2t_rna.baseline_evaluation_batch"] = (
        "d2t_rna.baseline_evaluation_batch"
    )
    schema_version: Literal["3.0"] = "3.0"
    common_binding: BaselineCommonBinding
    common_binding_sha256: Sha256Hex
    baseline_specification: BaselineSpecification
    baseline_specification_sha256: Sha256Hex
    baseline_id: RegisteredId
    seed_root_sha256: Sha256Hex
    baseline_implementation_sha256: Sha256Hex
    baseline_configuration_sha256: Sha256Hex
    results: tuple[BaselineSeedResult, ...]
    seed_results_sha256: Sha256Hex
    batch_sha256: Sha256Hex
    all_seed_execution_artifacts_replayed: Literal[False] = False
    all_seed_outcomes_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def complete_batch_replays(self) -> "BaselineEvaluationBatch":
        binding = _strict_common_binding(self.common_binding)
        spec = _strict_spec(self.baseline_specification)
        if spec != _spec_for(binding, self.baseline_id):
            raise ValueError("batch specification is not its registry member")
        if len(self.results) != RANDOM_BASELINE_SEED_COUNT:
            raise ValueError("batch must contain exactly 100 seed results")
        checked_results: list[BaselineSeedResult] = []
        for position, result in enumerate(self.results):
            if type(result) is not BaselineSeedResult:
                raise TypeError(
                    f"results[{position}] must be BaselineSeedResult"
                )
            checked = strict_revalidate_contract_model(result)
            if checked.seed_index != position:
                raise ValueError(
                    "batch must preserve complete seed index and order"
                )
            if (
                checked.baseline_id != spec.baseline_id
                or checked.common_binding_sha256
                != binding.common_binding_sha256
                or checked.seed_root_sha256 != spec.seed_root_sha256
                or checked.baseline_implementation_sha256
                != spec.implementation_sha256
                or checked.baseline_configuration_sha256
                != spec.configuration_sha256
            ):
                raise ValueError(
                    "seed result binding differs from batch registry spec"
                )
            checked_results.append(checked)
        if len({item.result_sha256 for item in checked_results}) != 100:
            raise ValueError("batch seed result hashes must be unique")
        expected = _batch_payload(
            binding,
            spec,
            tuple(checked_results),
        )
        actual = self.model_dump(
            mode="python",
            exclude={"batch_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError("baseline batch fields do not replay")
        if canonical_sha256(expected) != self.batch_sha256:
            raise ValueError("baseline batch hash does not replay")
        return self


def build_baseline_evaluation_batch(
    common_binding: BaselineCommonBinding,
    *,
    baseline_id: str,
    results: Sequence[BaselineSeedResult],
) -> BaselineEvaluationBatch:
    if type(common_binding) is not BaselineCommonBinding:
        raise TypeError("common_binding must be exactly BaselineCommonBinding")
    binding = common_binding
    spec = _spec_for(binding, baseline_id)
    supplied = tuple(results)
    if any(type(item) is not BaselineSeedResult for item in supplied):
        raise TypeError("results must contain only BaselineSeedResult")
    payload = _batch_payload(binding, spec, supplied)
    return BaselineEvaluationBatch.model_validate(
        {
            **payload,
            "batch_sha256": canonical_sha256(payload),
        },
        strict=True,
    )


def build_baseline_evaluation_batch_from_declarations(
    common_binding: BaselineCommonBinding,
    *,
    baseline_id: str,
    declarations: Sequence[BaselineSeedDeclaration],
) -> BaselineEvaluationBatch:
    """Build 100 results with one final fresh common-binding replay."""

    if type(common_binding) is not BaselineCommonBinding:
        raise TypeError("common_binding must be exactly BaselineCommonBinding")
    binding = common_binding
    spec = _spec_for(binding, baseline_id)
    supplied = tuple(declarations)
    if len(supplied) != RANDOM_BASELINE_SEED_COUNT:
        raise ValueError("bulk builder requires exactly 100 declarations")
    checked: list[BaselineSeedDeclaration] = []
    for position, declaration in enumerate(supplied):
        if type(declaration) is not BaselineSeedDeclaration:
            raise TypeError(
                f"declarations[{position}] must be "
                "BaselineSeedDeclaration"
            )
        replayed = strict_revalidate_contract_model(declaration)
        if replayed.seed_index != position:
            raise ValueError(
                "bulk declarations must preserve complete seed index and order"
            )
        checked.append(replayed)
    results = tuple(
        _seed_result_from_binding_and_declaration(
            binding,
            spec,
            declaration,
        )
        for declaration in checked
    )
    return build_baseline_evaluation_batch(
        binding,
        baseline_id=baseline_id,
        results=results,
    )


def _fraction(value: Rational) -> Fraction:
    return Fraction(value.numerator, value.denominator)


def _finite(value: Fraction | Rational) -> FiniteExtendedValue:
    fraction = (
        _fraction(value)
        if isinstance(value, Rational)
        else value
    )
    return FiniteExtendedValue(
        tag=ExtendedValueTag.FINITE,
        value=Rational(
            numerator=fraction.numerator,
            denominator=fraction.denominator,
        ),
    )


def _positive_infinity() -> PositiveInfinityExtendedValue:
    return PositiveInfinityExtendedValue(tag=ExtendedValueTag.POS_INF)


def _not_available() -> NotAvailableExtendedValue:
    return NotAvailableExtendedValue(tag=ExtendedValueTag.NA)


def _median_sorted(values: Sequence[Fraction]) -> Fraction:
    if not values:
        raise ValueError("cannot compute median of empty values")
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _median_finite(values: Sequence[Rational]) -> ExtendedValue:
    if not values:
        return _not_available()
    return _finite(_median_sorted(sorted(_fraction(item) for item in values)))


def _median_resolved(values: Sequence[ExtendedValue]) -> ExtendedValue:
    if not values:
        return _not_available()
    if any(type(item) is NotAvailableExtendedValue for item in values):
        raise ValueError("NA is forbidden from extended-value ordering")
    ordered: list[Fraction | None] = sorted(
        [
            _fraction(item.value)
            if type(item) is FiniteExtendedValue
            else None
            for item in values
        ],
        key=lambda item: (item is None, item or Fraction(0)),
    )
    middle = len(ordered) // 2
    selected = (
        (ordered[middle],)
        if len(ordered) % 2
        else (ordered[middle - 1], ordered[middle])
    )
    if any(item is None for item in selected):
        return _positive_infinity()
    finite = tuple(item for item in selected if item is not None)
    return _finite(sum(finite, start=Fraction(0)) / len(selected))


def _quartiles(
    values: Sequence[Rational],
) -> tuple[ExtendedValue, ExtendedValue, ExtendedValue]:
    if not values:
        na = _not_available()
        return na, na, na
    ordered = sorted(_fraction(item) for item in values)
    if len(ordered) == 1:
        q1 = q3 = ordered[0]
    else:
        middle = len(ordered) // 2
        lower = ordered[:middle]
        upper = (
            ordered[middle + 1 :]
            if len(ordered) % 2
            else ordered[middle:]
        )
        q1 = _median_sorted(lower)
        q3 = _median_sorted(upper)
    return _finite(q1), _finite(q3), _finite(q3 - q1)


def _summary_payload(batch: BaselineEvaluationBatch) -> dict[str, object]:
    feasible = tuple(
        item.cost.value
        for item in batch.results
        if type(item.cost) is FiniteExtendedValue
    )
    resolved = tuple(
        item.cost
        for item in batch.results
        if type(item.cost) is not NotAvailableExtendedValue
    )
    infeasible_count = sum(
        item.outcome is BaselineOutcome.COMPLETED_INFEASIBLE
        for item in batch.results
    )
    unresolved_count = sum(
        item.outcome is BaselineOutcome.UNRESOLVED
        for item in batch.results
    )
    resolved_median = _median_resolved(resolved)
    primary: ExtendedValue = (
        _not_available() if unresolved_count else resolved_median
    )
    q1, q3, iqr = _quartiles(feasible)
    feasible_count = len(feasible)
    return {
        "schema_id": "d2t_rna.random_baseline_summary",
        "schema_version": "3.0",
        "batch": batch,
        "batch_sha256": batch.batch_sha256,
        "baseline_id": batch.baseline_id,
        "common_binding_sha256": batch.common_binding_sha256,
        "baseline_specification_sha256": (
            batch.baseline_specification_sha256
        ),
        "seed_root_sha256": batch.seed_root_sha256,
        "seed_results_sha256": batch.seed_results_sha256,
        "seed_count": 100,
        "feasible_count": feasible_count,
        "completed_infeasible_count": infeasible_count,
        "unresolved_count": unresolved_count,
        "feasibility_fraction": Rational(
            numerator=feasible_count,
            denominator=100,
        ),
        "unresolved_fraction": Rational(
            numerator=unresolved_count,
            denominator=100,
        ),
        "extended_cost_median": primary,
        "resolved_only_extended_median": resolved_median,
        "feasible_cost_median": _median_finite(feasible),
        "feasible_cost_q1": q1,
        "feasible_cost_q3": q3,
        "feasible_cost_iqr": iqr,
        "seed_derivation_algorithm": RANDOM_SEED_DERIVATION_ALGORITHM,
        "extended_median_algorithm": EXTENDED_MEDIAN_ALGORITHM,
        "feasible_iqr_algorithm": FEASIBLE_IQR_ALGORITHM,
        "all_seed_execution_artifacts_replayed": False,
        "all_seed_outcomes_execution_verified": False,
        "release_claim_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class RandomBaselineSummary(FrozenContractModel):
    """Exact statistics over declarations, without execution verification."""

    schema_id: Literal["d2t_rna.random_baseline_summary"] = (
        "d2t_rna.random_baseline_summary"
    )
    schema_version: Literal["3.0"] = "3.0"
    batch: BaselineEvaluationBatch
    batch_sha256: Sha256Hex
    baseline_id: RegisteredId
    common_binding_sha256: Sha256Hex
    baseline_specification_sha256: Sha256Hex
    seed_root_sha256: Sha256Hex
    seed_results_sha256: Sha256Hex
    seed_count: Literal[100] = 100
    feasible_count: SeedCount
    completed_infeasible_count: SeedCount
    unresolved_count: SeedCount
    feasibility_fraction: Rational
    unresolved_fraction: Rational
    extended_cost_median: ExtendedValue
    resolved_only_extended_median: ExtendedValue
    feasible_cost_median: ExtendedValue
    feasible_cost_q1: ExtendedValue
    feasible_cost_q3: ExtendedValue
    feasible_cost_iqr: ExtendedValue
    seed_derivation_algorithm: Literal[
        "SHA256_DOMAIN_ROOT_BYTES_UINT32BE_INDEX_TO_UINT63BE_V1"
    ] = "SHA256_DOMAIN_ROOT_BYTES_UINT32BE_INDEX_TO_UINT63BE_V1"
    extended_median_algorithm: Literal[
        "SORT_FINITE_BEFORE_POS_INF_EXACT_MIDDLE_MEAN_V1"
    ] = "SORT_FINITE_BEFORE_POS_INF_EXACT_MIDDLE_MEAN_V1"
    feasible_iqr_algorithm: Literal[
        "SORT_EXACT_EXCLUDE_ODD_CENTER_MEDIAN_OF_HALVES_Q3_MINUS_Q1_V1"
    ] = "SORT_EXACT_EXCLUDE_ODD_CENTER_MEDIAN_OF_HALVES_Q3_MINUS_Q1_V1"
    summary_sha256: Sha256Hex
    all_seed_execution_artifacts_replayed: Literal[False] = False
    all_seed_outcomes_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def statistics_replay_from_batch(self) -> "RandomBaselineSummary":
        if type(self.batch) is not BaselineEvaluationBatch:
            raise TypeError("batch must be exactly BaselineEvaluationBatch")
        batch = strict_revalidate_contract_model(self.batch)
        expected = _summary_payload(batch)
        actual = self.model_dump(
            mode="python",
            exclude={"summary_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError(
                "baseline summary statistics do not replay from batch"
            )
        if canonical_sha256(expected) != self.summary_sha256:
            raise ValueError("baseline summary hash does not replay")
        return self


def summarize_random_baseline(
    batch: BaselineEvaluationBatch,
) -> RandomBaselineSummary:
    if type(batch) is not BaselineEvaluationBatch:
        raise TypeError("batch must be exactly BaselineEvaluationBatch")
    checked = strict_revalidate_contract_model(batch)
    payload = _summary_payload(checked)
    # Inputs were freshly replayed above; construct once to avoid recursively
    # replaying the same embedded common binding a second time in this call.
    return RandomBaselineSummary.model_construct(
        **payload,
        summary_sha256=canonical_sha256(payload),
    )


def replay_random_baseline_summary(
    summary: RandomBaselineSummary,
) -> RandomBaselineSummary:
    if type(summary) is not RandomBaselineSummary:
        raise TypeError("summary must be exactly RandomBaselineSummary")
    return strict_revalidate_contract_model(summary)


def _method_payload(
    *,
    common_binding: BaselineCommonBinding,
    method_id: str,
    implementation_sha256: str,
    configuration_sha256: str,
    outcome: BaselineOutcome,
    cost: ExtendedValue,
    execution_artifact_sha256: str,
) -> dict[str, object]:
    return {
        "schema_id": "d2t_rna.method_evaluation_result",
        "schema_version": "3.0",
        "common_binding": common_binding,
        "common_binding_sha256": common_binding.common_binding_sha256,
        "method_id": method_id,
        "method_implementation_sha256": implementation_sha256,
        "method_configuration_sha256": configuration_sha256,
        "outcome": outcome,
        "cost": cost,
        "execution_artifact_sha256": execution_artifact_sha256,
        "execution_artifact_replayed": False,
        "outcome_execution_verified": False,
        "release_claim_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class MethodEvaluationResult(FrozenContractModel):
    """One hash-bound method declaration, not a replayed runner receipt."""

    schema_id: Literal["d2t_rna.method_evaluation_result"] = (
        "d2t_rna.method_evaluation_result"
    )
    schema_version: Literal["3.0"] = "3.0"
    common_binding: BaselineCommonBinding
    common_binding_sha256: Sha256Hex
    method_id: RegisteredId
    method_implementation_sha256: Sha256Hex
    method_configuration_sha256: Sha256Hex
    outcome: BaselineOutcome
    cost: ExtendedValue
    execution_artifact_sha256: Sha256Hex
    result_sha256: Sha256Hex
    execution_artifact_replayed: Literal[False] = False
    outcome_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def result_replays(self) -> "MethodEvaluationResult":
        binding = _strict_common_binding(self.common_binding)
        checked_cost = _validate_outcome_cost(self.outcome, self.cost)
        expected = _method_payload(
            common_binding=binding,
            method_id=self.method_id,
            implementation_sha256=self.method_implementation_sha256,
            configuration_sha256=self.method_configuration_sha256,
            outcome=self.outcome,
            cost=checked_cost,
            execution_artifact_sha256=self.execution_artifact_sha256,
        )
        actual = self.model_dump(
            mode="python",
            exclude={"result_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError("method evaluation result fields do not replay")
        if canonical_sha256(expected) != self.result_sha256:
            raise ValueError("method evaluation result hash does not replay")
        return self


def build_method_evaluation_result(
    common_binding: BaselineCommonBinding,
    *,
    method_id: str,
    implementation_sha256: str,
    configuration_sha256: str,
    outcome: BaselineOutcome,
    cost: ExtendedValue,
    execution_artifact_sha256: str,
) -> MethodEvaluationResult:
    checked_method_id = _require_registered_id(
        method_id,
        field_name="method_id",
    )
    binding = _strict_common_binding(common_binding)
    if type(outcome) is not BaselineOutcome:
        raise TypeError("outcome must be exactly BaselineOutcome")
    checked_cost = _validate_outcome_cost(outcome, cost)
    implementation = _require_sha256(
        implementation_sha256,
        field_name="implementation_sha256",
    )
    configuration = _require_sha256(
        configuration_sha256,
        field_name="configuration_sha256",
    )
    artifact = _require_sha256(
        execution_artifact_sha256,
        field_name="execution_artifact_sha256",
    )
    payload = _method_payload(
        common_binding=binding,
        method_id=checked_method_id,
        implementation_sha256=implementation,
        configuration_sha256=configuration,
        outcome=outcome,
        cost=checked_cost,
        execution_artifact_sha256=artifact,
    )
    # Every input was freshly replayed or strictly checked above.
    return MethodEvaluationResult.model_construct(
        **payload,
        result_sha256=canonical_sha256(payload),
    )


class BaselineSummaryCommitment(FrozenContractModel):
    baseline_id: RegisteredId
    batch_sha256: Sha256Hex
    summary_sha256: Sha256Hex


def _checked_comparison_sources(
    method_result: MethodEvaluationResult,
    summaries: Sequence[RandomBaselineSummary],
) -> tuple[
    MethodEvaluationResult,
    tuple[RandomBaselineSummary, ...],
]:
    if type(method_result) is not MethodEvaluationResult:
        raise TypeError("method_result must be exactly MethodEvaluationResult")
    method = strict_revalidate_contract_model(method_result)
    supplied = tuple(summaries)
    expected_ids = tuple(
        spec.baseline_id
        for spec in method.common_binding.required_baseline_registry
    )
    if len(supplied) != len(expected_ids):
        raise ValueError(
            "baseline summaries must cover the exact required registry"
        )
    checked: list[RandomBaselineSummary] = []
    for position, summary in enumerate(supplied):
        if type(summary) is not RandomBaselineSummary:
            raise TypeError(
                f"baseline_summaries[{position}] must be "
                "RandomBaselineSummary"
            )
        replayed = replay_random_baseline_summary(summary)
        checked.append(replayed)
    actual_ids = tuple(item.baseline_id for item in checked)
    if actual_ids != expected_ids:
        raise ValueError(
            "baseline summaries must be in canonical required registry order"
        )
    for summary in checked:
        if (
            summary.common_binding_sha256
            != method.common_binding_sha256
            or summary.batch.common_binding != method.common_binding
        ):
            raise ValueError(
                "all method and baseline common bindings must match"
            )
    return method, tuple(checked)


def _comparison_derived(
    method: MethodEvaluationResult,
    summaries: tuple[RandomBaselineSummary, ...],
) -> dict[str, object]:
    commitments = tuple(
        BaselineSummaryCommitment(
            baseline_id=item.baseline_id,
            batch_sha256=item.batch_sha256,
            summary_sha256=item.summary_sha256,
        )
        for item in summaries
    )
    baseline_ids = tuple(item.baseline_id for item in summaries)
    disposition = BaselineComparisonDisposition.NOT_COMPARABLE
    reference_id: str | None = None
    reference_hash: str | None = None
    ratio: Rational | None = None
    all_infeasible = all(
        item.feasible_count == 0
        and item.completed_infeasible_count == 100
        and item.unresolved_count == 0
        for item in summaries
    )
    if (
        method.outcome is BaselineOutcome.FEASIBLE
        and all_infeasible
    ):
        disposition = BaselineComparisonDisposition.FEASIBILITY_DOMINANCE
    elif (
        method.outcome is BaselineOutcome.FEASIBLE
        and not any(
            type(item.extended_cost_median)
            is NotAvailableExtendedValue
            for item in summaries
        )
    ):
        finite = tuple(
            item
            for item in summaries
            if type(item.extended_cost_median)
            is FiniteExtendedValue
        )
        if finite:
            reference = min(
                finite,
                key=lambda item: (
                    _fraction(
                        cast(
                            FiniteExtendedValue,
                            item.extended_cost_median,
                        ).value
                    ),
                    item.baseline_id,
                ),
            )
            reference_cost = cast(
                FiniteExtendedValue,
                reference.extended_cost_median,
            ).value
            method_cost = cast(FiniteExtendedValue, method.cost).value
            if reference_cost.numerator != 0:
                disposition = (
                    BaselineComparisonDisposition.FINITE_COST_RATIO
                )
                reference_id = reference.baseline_id
                reference_hash = reference.summary_sha256
                ratio = Rational(
                    numerator=(
                        method_cost.numerator
                        * reference_cost.denominator
                    ),
                    denominator=(
                        method_cost.denominator
                        * reference_cost.numerator
                    ),
                )
    return {
        "method_evaluation_result_sha256": method.result_sha256,
        "method_common_binding_sha256": method.common_binding_sha256,
        "baseline_ids": baseline_ids,
        "baseline_summary_commitments": commitments,
        "disposition": disposition,
        "reference_baseline_id": reference_id,
        "reference_baseline_summary_sha256": reference_hash,
        "cost_ratio": ratio,
    }


def _comparison_payload(
    method: MethodEvaluationResult,
    summaries: tuple[RandomBaselineSummary, ...],
) -> dict[str, object]:
    return {
        "schema_id": "d2t_rna.baseline_comparison",
        "schema_version": "3.0",
        "method_result": method,
        "baseline_summaries": summaries,
        **_comparison_derived(method, summaries),
        "comparison_algorithm": BASELINE_COMPARISON_ALGORITHM,
        "comparison_scope": BASELINE_COMPARISON_SCOPE,
        "all_execution_artifacts_replayed": False,
        "all_outcomes_execution_verified": False,
        "release_claim_authorized": False,
        "formal_scientific_certificate_authorized": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }


class BaselineComparison(FrozenContractModel):
    """Structural comparison only; never a release or scientific bearer."""

    schema_id: Literal["d2t_rna.baseline_comparison"] = (
        "d2t_rna.baseline_comparison"
    )
    schema_version: Literal["3.0"] = "3.0"
    method_result: MethodEvaluationResult
    baseline_summaries: tuple[RandomBaselineSummary, ...]
    method_evaluation_result_sha256: Sha256Hex
    method_common_binding_sha256: Sha256Hex
    baseline_ids: tuple[RegisteredId, ...]
    baseline_summary_commitments: tuple[
        BaselineSummaryCommitment,
        ...,
    ]
    disposition: BaselineComparisonDisposition
    reference_baseline_id: RegisteredId | None
    reference_baseline_summary_sha256: Sha256Hex | None
    cost_ratio: Rational | None
    comparison_algorithm: Literal[
        "METHOD_OVER_LOWEST_FINITE_REQUIRED_RIVAL_MEDIAN_V2"
    ] = "METHOD_OVER_LOWEST_FINITE_REQUIRED_RIVAL_MEDIAN_V2"
    comparison_scope: Literal[
        "STRUCTURAL_HASH_BOUND_DECLARATIONS_ONLY"
    ] = "STRUCTURAL_HASH_BOUND_DECLARATIONS_ONLY"
    comparison_sha256: Sha256Hex
    all_execution_artifacts_replayed: Literal[False] = False
    all_outcomes_execution_verified: Literal[False] = False
    release_claim_authorized: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def comparison_replays_from_sources(self) -> "BaselineComparison":
        method, summaries = _checked_comparison_sources(
            self.method_result,
            self.baseline_summaries,
        )
        expected = _comparison_payload(method, summaries)
        actual = self.model_dump(
            mode="python",
            exclude={"comparison_sha256"},
        )
        if canonical_json_bytes(actual) != canonical_json_bytes(expected):
            raise ValueError(
                "baseline comparison does not replay from source artifacts"
            )
        if canonical_sha256(expected) != self.comparison_sha256:
            raise ValueError("baseline comparison hash does not replay")
        return self


def compare_method_to_baselines(
    *,
    method_result: MethodEvaluationResult,
    baseline_summaries: Sequence[RandomBaselineSummary],
) -> BaselineComparison:
    method, summaries = _checked_comparison_sources(
        method_result,
        baseline_summaries,
    )
    payload = _comparison_payload(method, summaries)
    # Source artifacts were freshly replayed above. Serialized model_validate
    # remains the fail-closed untrusted-input path.
    return BaselineComparison.model_construct(
        **payload,
        comparison_sha256=canonical_sha256(payload),
    )


def replay_baseline_comparison(
    comparison: BaselineComparison,
) -> BaselineComparison:
    if type(comparison) is not BaselineComparison:
        raise TypeError("comparison must be exactly BaselineComparison")
    return strict_revalidate_contract_model(comparison)
