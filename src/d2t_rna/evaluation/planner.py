"""Fail-closed planner classification and common feasibility bindings."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import StrictBool, field_validator, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import PlannerFailureState, ProbabilityScope
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.exact.confidence import (
    ExactParameterFamily,
    python_function_execution_sha256,
)

from .milp_check import (
    BoundedMilpModel,
    FeasibilityScope,
    IntegerWitnessValue,
    MilpCheckReceipt,
    MilpCheckStatus,
    replay_bounded_milp_check,
    verify_milp_witness,
)
from .scenario import (
    ExactSyntheticScenarioProofArtifact,
    FiniteScenarioCoverageAggregate,
    ScenarioCoverageDisposition,
    replay_finite_scenario_aggregate,
)
from .risk_binding import (
    RiskCertificateReplayBundle,
    replay_risk_certificate_replay_bundle,
)


_PLANNER_WITNESS_VERIFIER = verify_milp_witness
_PLANNER_EXECUTION_HASHER = python_function_execution_sha256
_PLANNER_CLASSIFIER_PURPOSE = "TASK5_PLANNER_CLASSIFIER_REPLAY"
_CONTRACT_JSON_PARSER = parse_contract_json
_RISK_BUNDLE_REPLAYER = replay_risk_certificate_replay_bundle
_SCENARIO_AGGREGATE_REPLAYER = replay_finite_scenario_aggregate
_CFA_BINDER_PURPOSE = "TASK5_COVERAGE_FEASIBILITY_BINDING_REPLAY"


class PlannerRunStatus(str, Enum):
    CERTIFICATE_FOUND = "CERTIFICATE_FOUND"
    NO_CERTIFICATE_FOUND = "NO_CERTIFICATE_FOUND"
    UNRESOLVED = "UNRESOLVED"


class PlannerTerminationReason(str, Enum):
    CERTIFICATE_FOUND = "CERTIFICATE_FOUND"
    REGISTERED_SEARCH_EXHAUSTED = "REGISTERED_SEARCH_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    UNKNOWN = "UNKNOWN"


_UNRESOLVED_TERMINATION_REASONS = frozenset(
    {
        PlannerTerminationReason.TIMEOUT,
        PlannerTerminationReason.ERROR,
        PlannerTerminationReason.NUMERICAL_FAILURE,
        PlannerTerminationReason.UNKNOWN,
    }
)


class RegisteredPlannerResult(FrozenContractModel):
    """Receipt emitted by the registered planner, not an infeasibility proof."""

    schema_id: Literal["d2t_rna.registered_planner_result"] = (
        "d2t_rna.registered_planner_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    model_sha256: Sha256Hex
    status: PlannerRunStatus
    search_scope: FeasibilityScope = (
        FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS
    )
    witness: tuple[IntegerWitnessValue, ...]
    states_examined: NonNegativeInt
    termination_reason: PlannerTerminationReason
    planner_configuration_sha256: Sha256Hex
    planner_code_sha256: Sha256Hex

    @field_validator("termination_reason", mode="before")
    @classmethod
    def accept_only_registered_reason_strings(
        cls,
        value: object,
    ) -> object:
        if type(value) is str:
            try:
                return PlannerTerminationReason(value)
            except ValueError as exc:
                raise ValueError(
                    "termination_reason is not in the closed registered set"
                ) from exc
        return value

    @model_validator(mode="after")
    def result_fields_are_canonical(self) -> "RegisteredPlannerResult":
        witness_ids = tuple(item.variable_id for item in self.witness)
        if len(witness_ids) != len(set(witness_ids)):
            raise ValueError("planner witness contains duplicate variable IDs")
        if witness_ids != tuple(sorted(witness_ids)):
            raise ValueError(
                "planner witness values must be canonically sorted by "
                "variable_id"
            )
        if self.status is PlannerRunStatus.CERTIFICATE_FOUND:
            if (
                self.termination_reason
                is not PlannerTerminationReason.CERTIFICATE_FOUND
            ):
                raise ValueError(
                    "CERTIFICATE_FOUND status requires the matching "
                    "termination reason"
                )
            if not self.witness:
                raise ValueError(
                    "CERTIFICATE_FOUND must carry a nonempty planner witness"
                )
            if self.states_examined < 1:
                raise ValueError(
                    "CERTIFICATE_FOUND must examine at least one state"
                )
        elif self.status is PlannerRunStatus.NO_CERTIFICATE_FOUND:
            if (
                self.termination_reason
                is not PlannerTerminationReason.REGISTERED_SEARCH_EXHAUSTED
            ):
                if (
                    self.termination_reason
                    in _UNRESOLVED_TERMINATION_REASONS
                ):
                    raise ValueError(
                        "TIMEOUT, ERROR, NUMERICAL_FAILURE, and UNKNOWN "
                        "terminations may only map to UNRESOLVED"
                    )
                raise ValueError(
                    "NO_CERTIFICATE_FOUND termination must be "
                    "REGISTERED_SEARCH_EXHAUSTED"
                )
            if self.witness:
                raise ValueError(
                    "NO_CERTIFICATE_FOUND cannot carry a planner witness"
                )
            if self.states_examined < 1:
                raise ValueError(
                    "registered search exhaustion must examine at least one "
                    "state"
                )
        else:
            if (
                self.termination_reason
                not in _UNRESOLVED_TERMINATION_REASONS
            ):
                raise ValueError(
                    "UNRESOLVED requires TIMEOUT, ERROR, "
                    "NUMERICAL_FAILURE, or UNKNOWN termination"
                )
            if self.witness:
                raise ValueError(
                    "UNRESOLVED cannot carry a planner witness"
                )
        return self

    @property
    def result_sha256(self) -> str:
        return canonical_sha256(self)


def _is_exhaustive_infeasibility(
    receipt: MilpCheckReceipt | None,
) -> bool:
    return (
        receipt is not None
        and receipt.status is MilpCheckStatus.INFEASIBLE
        and receipt.exhaustive
        and receipt.states_examined == receipt.state_space_size
    )


def _expected_failure_and_scope(
    planner_status: PlannerRunStatus,
    available: MilpCheckReceipt | None,
    registered: MilpCheckReceipt | None,
) -> tuple[PlannerFailureState | None, FeasibilityScope | None]:
    if planner_status is PlannerRunStatus.CERTIFICATE_FOUND:
        return None, None
    if planner_status is PlannerRunStatus.UNRESOLVED:
        return PlannerFailureState.PLANNER_UNRESOLVED, None
    if _is_exhaustive_infeasibility(registered):
        return (
            PlannerFailureState.NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS,
            FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
        )
    if _is_exhaustive_infeasibility(available):
        return (
            PlannerFailureState.NO_CERTIFICATE_WITHIN_AVAILABLE_CONTROL_LIBRARY,
            FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        )
    if (
        registered is not None
        and registered.status is MilpCheckStatus.UNRESOLVED
    ) or (
        available is not None
        and available.status is MilpCheckStatus.UNRESOLVED
    ):
        return PlannerFailureState.PLANNER_UNRESOLVED, None
    return (
        PlannerFailureState.NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER,
        None,
    )


class PlannerClassification(FrozenContractModel):
    schema_id: Literal["d2t_rna.planner_classification"] = (
        "d2t_rna.planner_classification"
    )
    schema_version: Literal["2.0"] = "2.0"
    model_sha256: Sha256Hex
    planner_result_sha256: Sha256Hex
    planner_status: PlannerRunStatus
    planner_termination_reason: PlannerTerminationReason
    planner_search_scope: FeasibilityScope
    failure_state: PlannerFailureState | None
    certificate_found: StrictBool
    planner_witness_verified: StrictBool
    available_control_library_check: MilpCheckReceipt | None
    registered_design_class_check: MilpCheckReceipt | None
    available_control_library_check_sha256: Sha256Hex | None
    registered_design_class_check_sha256: Sha256Hex | None
    independent_infeasibility_proof_scope: FeasibilityScope | None
    planner_classifier_execution_sha256: Sha256Hex
    planner_classifier_execution_replayed: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    fresh_replay_required: Literal[True] = True
    scientific_claim_authorized: Literal[False] = False

    @model_validator(mode="after")
    def disposition_is_internally_consistent(self) -> "PlannerClassification":
        if (
            self.planner_classifier_execution_sha256
            != _assert_planner_classifier_execution_closure()
        ):
            raise ValueError(
                "planner classifier execution hash is stale"
            )
        if self.planner_status is PlannerRunStatus.CERTIFICATE_FOUND:
            if (
                self.planner_termination_reason
                is not PlannerTerminationReason.CERTIFICATE_FOUND
            ):
                raise ValueError(
                    "planner status and termination reason contradict"
                )
        elif self.planner_status is PlannerRunStatus.NO_CERTIFICATE_FOUND:
            if (
                self.planner_termination_reason
                is not PlannerTerminationReason.REGISTERED_SEARCH_EXHAUSTED
            ):
                raise ValueError(
                    "planner status and termination reason contradict"
                )
        elif (
            self.planner_termination_reason
            not in _UNRESOLVED_TERMINATION_REASONS
        ):
            raise ValueError(
                "UNRESOLVED classification has a resolved termination reason"
            )

        receipt_fields = (
            (
                "available control library",
                self.available_control_library_check,
                self.available_control_library_check_sha256,
                FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
            ),
            (
                "registered design class",
                self.registered_design_class_check,
                self.registered_design_class_check_sha256,
                FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS,
            ),
        )
        for label, receipt, receipt_sha256, expected_scope in receipt_fields:
            if receipt is None:
                if receipt_sha256 is not None:
                    raise ValueError(
                        f"{label} receipt hash has no raw receipt evidence"
                    )
                continue
            if receipt_sha256 is None:
                raise ValueError(f"{label} raw receipt has no receipt hash")
            if receipt.scope is not expected_scope:
                raise ValueError(f"{label} raw receipt has the wrong scope")
            if canonical_sha256(receipt) != receipt_sha256:
                raise ValueError(f"{label} raw receipt hash does not replay")

        if self.certificate_found:
            if self.planner_status is not PlannerRunStatus.CERTIFICATE_FOUND:
                raise ValueError(
                    "certificate_found contradicts the planner status"
                )
            if self.failure_state is not None:
                raise ValueError(
                    "successful planner classification cannot have a failure "
                    "state"
                )
            if not self.planner_witness_verified:
                raise ValueError(
                    "successful planner result needs an exact verified witness"
                )
            if self.independent_infeasibility_proof_scope is not None:
                raise ValueError(
                    "successful result cannot also claim infeasibility"
                )
            if _is_exhaustive_infeasibility(
                self.registered_design_class_check
            ):
                raise ValueError(
                    "successful result contradicts full-design "
                    "infeasibility evidence"
                )
            if (
                self.planner_search_scope
                is FeasibilityScope.AVAILABLE_CONTROL_LIBRARY
                and _is_exhaustive_infeasibility(
                    self.available_control_library_check
                )
            ):
                raise ValueError(
                    "successful library result contradicts library "
                    "infeasibility evidence"
                )
        else:
            if self.planner_status is PlannerRunStatus.CERTIFICATE_FOUND:
                raise ValueError(
                    "failed classification contradicts the planner status"
                )
            if self.failure_state is None:
                raise ValueError(
                    "unsuccessful planner classification needs a failure state"
                )
            if self.planner_witness_verified:
                raise ValueError(
                    "unsuccessful planner classification has no verified "
                    "witness"
                )

        expected_failure, expected_scope = _expected_failure_and_scope(
            self.planner_status,
            self.available_control_library_check,
            self.registered_design_class_check,
        )
        if self.failure_state is not expected_failure:
            raise ValueError(
                "classified failure state does not match planner status and "
                "raw checker receipts"
            )
        if self.independent_infeasibility_proof_scope is not expected_scope:
            raise ValueError(
                "independent infeasibility scope does not match the classified "
                "failure state"
            )
        return self

    @property
    def classification_sha256(self) -> str:
        return canonical_sha256(self)


def _strict_model(model: BoundedMilpModel) -> BoundedMilpModel:
    if type(model) is not BoundedMilpModel:
        raise TypeError("model must be exactly BoundedMilpModel")
    return strict_revalidate_contract_model(model)


def _strict_planner_result(
    result: RegisteredPlannerResult,
) -> RegisteredPlannerResult:
    if type(result) is not RegisteredPlannerResult:
        raise TypeError("planner_result must be exactly RegisteredPlannerResult")
    return strict_revalidate_contract_model(result)


def _replay_scoped_check(
    model: BoundedMilpModel,
    receipt: MilpCheckReceipt | None,
    *,
    expected_scope: FeasibilityScope,
    label: str,
) -> MilpCheckReceipt | None:
    if receipt is None:
        return None
    replayed = replay_bounded_milp_check(model, receipt)
    if replayed.scope is not expected_scope:
        raise ValueError(
            f"{label} has scope {replayed.scope.value}, expected "
            f"{expected_scope.value}"
        )
    return replayed


def _classify_planner_result_core(
    model: BoundedMilpModel,
    planner_result: RegisteredPlannerResult,
    *,
    planner_classifier_execution_sha256: str,
    available_control_library_check: MilpCheckReceipt | None = None,
    registered_design_class_check: MilpCheckReceipt | None = None,
) -> PlannerClassification:
    """Classify without treating planner failure as infeasibility evidence."""

    checked_model = _strict_model(model)
    result = _strict_planner_result(planner_result)
    model_sha256 = canonical_sha256(checked_model)
    if result.model_sha256 != model_sha256:
        raise ValueError("planner result is bound to a different MILP model")

    available = _replay_scoped_check(
        checked_model,
        available_control_library_check,
        expected_scope=FeasibilityScope.AVAILABLE_CONTROL_LIBRARY,
        label="available_control_library_check",
    )
    registered = _replay_scoped_check(
        checked_model,
        registered_design_class_check,
        expected_scope=(
            FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS
        ),
        label="registered_design_class_check",
    )
    available_sha256 = (
        canonical_sha256(available) if available is not None else None
    )
    registered_sha256 = (
        canonical_sha256(registered) if registered is not None else None
    )

    if result.status is PlannerRunStatus.CERTIFICATE_FOUND:
        if not _PLANNER_WITNESS_VERIFIER(
            checked_model,
            scope=result.search_scope,
            witness=result.witness,
        ):
            raise ValueError(
                "registered planner claimed a certificate with an invalid "
                "exact witness"
            )
        if (
            result.search_scope
            is FeasibilityScope.REGISTERED_FIXED_HORIZON_DESIGN_CLASS
            and registered is not None
            and registered.status is MilpCheckStatus.INFEASIBLE
        ):
            raise ValueError(
                "planner witness contradicts replayed full-design "
                "infeasibility"
            )
        if (
            result.search_scope is FeasibilityScope.AVAILABLE_CONTROL_LIBRARY
            and available is not None
            and available.status is MilpCheckStatus.INFEASIBLE
        ):
            raise ValueError(
                "planner witness contradicts replayed library infeasibility"
            )
        return PlannerClassification(
            model_sha256=model_sha256,
            planner_result_sha256=canonical_sha256(result),
            planner_status=result.status,
            planner_termination_reason=result.termination_reason,
            planner_search_scope=result.search_scope,
            failure_state=None,
            certificate_found=True,
            planner_witness_verified=True,
            available_control_library_check=available,
            registered_design_class_check=registered,
            available_control_library_check_sha256=available_sha256,
            registered_design_class_check_sha256=registered_sha256,
            independent_infeasibility_proof_scope=None,
            planner_classifier_execution_sha256=(
                planner_classifier_execution_sha256
            ),
            planner_classifier_execution_replayed=True,
            serialized_bearer_authorization=False,
            fresh_replay_required=True,
            scientific_claim_authorized=False,
        )

    failure_state, proof_scope = _expected_failure_and_scope(
        result.status,
        available,
        registered,
    )

    return PlannerClassification(
        model_sha256=model_sha256,
        planner_result_sha256=canonical_sha256(result),
        planner_status=result.status,
        planner_termination_reason=result.termination_reason,
        planner_search_scope=result.search_scope,
        failure_state=failure_state,
        certificate_found=False,
        planner_witness_verified=False,
        available_control_library_check=available,
        registered_design_class_check=registered,
        available_control_library_check_sha256=available_sha256,
        registered_design_class_check_sha256=registered_sha256,
        independent_infeasibility_proof_scope=proof_scope,
        planner_classifier_execution_sha256=(
            planner_classifier_execution_sha256
        ),
        planner_classifier_execution_replayed=True,
        serialized_bearer_authorization=False,
        fresh_replay_required=True,
        scientific_claim_authorized=False,
    )


_PLANNER_CLASSIFIER_CORE = _classify_planner_result_core


def _planner_classifier_execution_sha256() -> str:
    if verify_milp_witness is not _PLANNER_WITNESS_VERIFIER:
        raise RuntimeError(
            "planner classifier execution closure changed: "
            "witness verifier identity differs"
        )
    if (
        globals().get("_classify_planner_result_core")
        is not _PLANNER_CLASSIFIER_CORE
    ):
        raise RuntimeError(
            "planner classifier runtime identity changed"
        )
    if python_function_execution_sha256 is not _PLANNER_EXECUTION_HASHER:
        raise RuntimeError(
            "planner execution hasher runtime identity changed"
        )
    return python_function_execution_sha256(
        _PLANNER_CLASSIFIER_CORE,
        purpose=_PLANNER_CLASSIFIER_PURPOSE,
        strict_pure=False,
    )


_PLANNER_CLASSIFIER_EXECUTION_BASELINE_SHA256 = (
    _planner_classifier_execution_sha256()
)


def _assert_planner_classifier_execution_closure() -> str:
    observed = _planner_classifier_execution_sha256()
    if observed != _PLANNER_CLASSIFIER_EXECUTION_BASELINE_SHA256:
        raise RuntimeError(
            "planner classifier execution closure changed"
        )
    return observed


def classify_planner_result(
    model: BoundedMilpModel,
    planner_result: RegisteredPlannerResult,
    *,
    available_control_library_check: MilpCheckReceipt | None = None,
    registered_design_class_check: MilpCheckReceipt | None = None,
) -> PlannerClassification:
    """Classify only under an unchanged live planner execution closure."""

    execution_pre = _assert_planner_classifier_execution_closure()
    classification = _PLANNER_CLASSIFIER_CORE(
        model,
        planner_result,
        planner_classifier_execution_sha256=execution_pre,
        available_control_library_check=available_control_library_check,
        registered_design_class_check=registered_design_class_check,
    )
    execution_post = _assert_planner_classifier_execution_closure()
    if (
        execution_post != execution_pre
        or classification.planner_classifier_execution_sha256
        != execution_pre
    ):
        raise RuntimeError(
            "planner classifier execution closure changed during replay"
        )
    return classification


class CoverageFeasibilityAssessment(FrozenContractModel):
    """Replayable common binding shared by method and baseline evaluations."""

    schema_id: Literal["d2t_rna.coverage_feasibility_assessment"] = (
        "d2t_rna.coverage_feasibility_assessment"
    )
    schema_version: Literal["5.0"] = "5.0"
    model: BoundedMilpModel
    model_sha256: Sha256Hex
    planner_result: RegisteredPlannerResult
    available_control_library_check: MilpCheckReceipt | None
    registered_design_class_check: MilpCheckReceipt | None
    risk_certificate: RiskCertificate
    risk_certificate_sha256: Sha256Hex
    risk_certificate_probability_scope: ProbabilityScope
    risk_certificate_replay_bundle: RiskCertificateReplayBundle
    risk_certificate_replay_bundle_sha256: Sha256Hex
    scenario_coverage_aggregate: FiniteScenarioCoverageAggregate
    scenario_coverage_aggregate_sha256: Sha256Hex
    scenario_proof_manifest_sha256: Sha256Hex
    scenario_coverage_disposition: ScenarioCoverageDisposition
    scenario_formal_guarantee: StrictBool
    risk_probability_space_sha256: Sha256Hex
    formal_scenario_probability_space_sha256s: tuple[Sha256Hex, ...]
    risk_scenario_probability_space_binding_required: StrictBool
    risk_scenario_probability_space_binding_verified: StrictBool
    yield_scope: RegistryRef
    cost_table: RegistryRef
    expansion_order: RegistryRef
    planner_assessment: PlannerClassification
    planner_assessment_sha256: Sha256Hex
    common_binding_sha256: Sha256Hex
    cfa_binding_execution_sha256: Sha256Hex
    cfa_binding_execution_replayed: Literal[True] = True
    planner_evidence_fresh_replay_required: Literal[True] = True
    risk_certificate_semantic_replay_required: Literal[True] = True
    risk_certificate_semantics_replayed: Literal[True] = True
    scenario_replay_required: Literal[True] = True
    scenario_proof_replayed: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False

    @model_validator(mode="after")
    def hashes_replay_from_bound_inputs(self) -> "CoverageFeasibilityAssessment":
        cfa_execution_pre = _assert_cfa_binding_execution_closure()
        checked_model = _strict_model(self.model)
        checked_planner_result = _strict_planner_result(self.planner_result)
        if type(self.risk_certificate) is not RiskCertificate:
            raise TypeError("risk_certificate must be exactly RiskCertificate")
        checked_risk = strict_revalidate_contract_model(
            self.risk_certificate
        )
        checked_risk_bundle = _RISK_BUNDLE_REPLAYER(
            self.risk_certificate_replay_bundle
        )
        checked_scenarios = _strict_scenario_aggregate(
            self.scenario_coverage_aggregate
        )
        probability_space_binding = _risk_scenario_probability_space_binding(
            checked_scenarios,
            checked_risk_bundle.inputs.probability_space,
        )
        _strict_registry_ref(self.yield_scope, label="yield_scope")
        _strict_registry_ref(self.cost_table, label="cost_table")
        _strict_registry_ref(self.expansion_order, label="expansion_order")

        if canonical_sha256(checked_model) != self.model_sha256:
            raise ValueError("bound MILP model hash does not replay")
        if (
            canonical_sha256(checked_risk)
            != self.risk_certificate_sha256
        ):
            raise ValueError("bound risk certificate hash does not replay")
        if (
            canonical_sha256(checked_risk_bundle)
            != self.risk_certificate_replay_bundle_sha256
        ):
            raise ValueError(
                "bound risk certificate replay bundle hash does not replay"
            )
        if (
            canonical_json_bytes(checked_risk)
            != canonical_json_bytes(
                checked_risk_bundle.inputs.risk_certificate
            )
        ):
            raise ValueError(
                "bound risk certificate and Task 2 replay bundle certificate "
                "are not byte-identical"
            )
        if (
            self.risk_certificate_sha256
            != checked_risk_bundle.risk_certificate_sha256
        ):
            raise ValueError(
                "bound risk certificate hash differs from Task 2 replay bundle"
            )
        if (
            checked_risk.probability_scope
            is not self.risk_certificate_probability_scope
        ):
            raise ValueError(
                "risk certificate probability scope does not replay"
            )
        if (
            canonical_sha256(checked_scenarios)
            != self.scenario_coverage_aggregate_sha256
        ):
            raise ValueError(
                "bound scenario coverage aggregate hash does not replay"
            )
        expected_manifest_sha256 = canonical_sha256(
            checked_scenarios.per_scenario_proof_manifest
        )
        if expected_manifest_sha256 != self.scenario_proof_manifest_sha256:
            raise ValueError(
                "bound per-scenario proof manifest hash does not replay"
            )
        if (
            checked_scenarios.coverage_disposition
            is not self.scenario_coverage_disposition
            or checked_scenarios.formal_guarantee
            is not self.scenario_formal_guarantee
        ):
            raise ValueError(
                "scenario coverage disposition does not replay"
            )
        for field_name, expected_value in probability_space_binding.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(
                    "risk/scenario probability-space binding "
                    f"{field_name} does not replay"
                )
        scenario_conditioning = (
            checked_scenarios.per_scenario_proof_manifest[0]
            .scenario_proof.conditioning_sigma_field_hash
        )
        if checked_risk.conditioning_sigma_field_hash != scenario_conditioning:
            raise ValueError(
                "risk certificate and scenario aggregate condition on "
                "different sigma fields"
            )

        replayed_planner = _CFA_PLANNER_CLASSIFIER(
            checked_model,
            checked_planner_result,
            available_control_library_check=(
                self.available_control_library_check
            ),
            registered_design_class_check=(
                self.registered_design_class_check
            ),
        )
        rebuilt_planner = strict_revalidate_contract_model(
            self.planner_assessment
        )
        if (
            canonical_json_bytes(replayed_planner)
            != canonical_json_bytes(rebuilt_planner)
        ):
            raise ValueError(
                "planner assessment does not match fresh model-and-receipt "
                "replay"
            )
        if replayed_planner.model_sha256 != self.model_sha256:
            raise ValueError(
                "planner assessment and coverage assessment model hashes differ"
            )
        if canonical_sha256(rebuilt_planner) != self.planner_assessment_sha256:
            raise ValueError("planner assessment hash does not replay")
        payload = self.model_dump(
            mode="python",
            exclude={"common_binding_sha256"},
        )
        if canonical_sha256(payload) != self.common_binding_sha256:
            raise ValueError(
                "coverage feasibility common binding does not replay"
            )
        if self.cfa_binding_execution_sha256 != cfa_execution_pre:
            raise ValueError(
                "coverage feasibility binding execution hash is stale"
            )
        cfa_execution_post = _assert_cfa_binding_execution_closure()
        if cfa_execution_post != cfa_execution_pre:
            raise RuntimeError(
                "coverage feasibility binding execution closure changed "
                "during replay"
            )
        return self

    @property
    def assessment_sha256(self) -> str:
        return canonical_sha256(self)


def _strict_registry_ref(value: RegistryRef, *, label: str) -> RegistryRef:
    if type(value) is not RegistryRef:
        raise TypeError(f"{label} must be exactly RegistryRef")
    return strict_revalidate_contract_model(value)


def _strict_scenario_aggregate(
    value: FiniteScenarioCoverageAggregate,
) -> FiniteScenarioCoverageAggregate:
    if type(value) is not FiniteScenarioCoverageAggregate:
        raise TypeError(
            "scenario_coverage_aggregate must be exactly "
            "FiniteScenarioCoverageAggregate"
        )
    return _SCENARIO_AGGREGATE_REPLAYER(value)


def _risk_scenario_probability_space_binding(
    scenarios: FiniteScenarioCoverageAggregate,
    risk_probability_space: ProbabilitySpaceSpec,
) -> dict[str, object]:
    if type(risk_probability_space) is not ProbabilitySpaceSpec:
        raise TypeError(
            "risk_probability_space must be exactly ProbabilitySpaceSpec"
        )
    risk_space = strict_revalidate_contract_model(risk_probability_space)
    risk_hash = canonical_sha256(risk_space)
    if not scenarios.formal_guarantee:
        return {
            "risk_probability_space_sha256": risk_hash,
            "formal_scenario_probability_space_sha256s": (),
            "risk_scenario_probability_space_binding_required": False,
            "risk_scenario_probability_space_binding_verified": False,
        }

    hashes: list[str] = []
    for manifest in scenarios.per_scenario_proof_manifest:
        artifact = manifest.proof_artifact
        if type(artifact) is not ExactSyntheticScenarioProofArtifact:
            raise ValueError(
                "formal scenario aggregate contains no registered Task 4 "
                "exact-synthetic raw-input artifact"
            )
        family = _CONTRACT_JSON_PARSER(
            ExactParameterFamily,
            artifact.family_json,
        )
        scenario_space = family.probability_space
        scenario_hash = canonical_sha256(scenario_space)
        hashes.append(scenario_hash)
        if (
            canonical_json_bytes(scenario_space)
            != canonical_json_bytes(risk_space)
        ):
            raise ValueError(
                "formal scenario and RiskCertificate replay bundle use "
                "different probability spaces"
            )
    if not hashes:
        raise ValueError(
            "formal scenario probability-space binding has no manifests"
        )
    return {
        "risk_probability_space_sha256": risk_hash,
        "formal_scenario_probability_space_sha256s": tuple(hashes),
        "risk_scenario_probability_space_binding_required": True,
        "risk_scenario_probability_space_binding_verified": True,
    }


def _build_coverage_feasibility_assessment_core(
    model: BoundedMilpModel,
    planner_result: RegisteredPlannerResult,
    *,
    cfa_binding_execution_sha256: str,
    risk_certificate: RiskCertificate,
    risk_certificate_replay_bundle: RiskCertificateReplayBundle,
    scenario_coverage_aggregate: FiniteScenarioCoverageAggregate,
    yield_scope: RegistryRef,
    cost_table: RegistryRef,
    expansion_order: RegistryRef,
    available_control_library_check: MilpCheckReceipt | None = None,
    registered_design_class_check: MilpCheckReceipt | None = None,
) -> CoverageFeasibilityAssessment:
    """Bind common feasibility inputs without authorizing a scientific claim."""

    checked_model = _strict_model(model)
    checked_planner_result = _strict_planner_result(planner_result)
    if type(risk_certificate) is not RiskCertificate:
        raise TypeError("risk_certificate must be exactly RiskCertificate")
    checked_risk = strict_revalidate_contract_model(risk_certificate)
    checked_risk_bundle = _RISK_BUNDLE_REPLAYER(
        risk_certificate_replay_bundle
    )
    if (
        canonical_json_bytes(checked_risk)
        != canonical_json_bytes(checked_risk_bundle.inputs.risk_certificate)
    ):
        raise ValueError(
            "risk_certificate must be byte-identical to the certificate in "
            "risk_certificate_replay_bundle"
        )
    checked_scenarios = _strict_scenario_aggregate(
        scenario_coverage_aggregate
    )
    probability_space_binding = _risk_scenario_probability_space_binding(
        checked_scenarios,
        checked_risk_bundle.inputs.probability_space,
    )
    scenario_conditioning = (
        checked_scenarios.per_scenario_proof_manifest[0]
        .scenario_proof.conditioning_sigma_field_hash
    )
    if checked_risk.conditioning_sigma_field_hash != scenario_conditioning:
        raise ValueError(
            "risk certificate and scenario aggregate condition on "
            "different sigma fields"
        )
    checked_yield = _strict_registry_ref(yield_scope, label="yield_scope")
    checked_cost = _strict_registry_ref(cost_table, label="cost_table")
    checked_order = _strict_registry_ref(
        expansion_order,
        label="expansion_order",
    )
    classification = _CFA_PLANNER_CLASSIFIER(
        checked_model,
        checked_planner_result,
        available_control_library_check=available_control_library_check,
        registered_design_class_check=registered_design_class_check,
    )
    payload = {
        "schema_id": "d2t_rna.coverage_feasibility_assessment",
        "schema_version": "5.0",
        "model": checked_model,
        "model_sha256": canonical_sha256(checked_model),
        "planner_result": checked_planner_result,
        "available_control_library_check": (
            classification.available_control_library_check
        ),
        "registered_design_class_check": (
            classification.registered_design_class_check
        ),
        "risk_certificate": checked_risk,
        "risk_certificate_sha256": canonical_sha256(checked_risk),
        "risk_certificate_probability_scope": checked_risk.probability_scope,
        "risk_certificate_replay_bundle": checked_risk_bundle,
        "risk_certificate_replay_bundle_sha256": canonical_sha256(
            checked_risk_bundle
        ),
        "scenario_coverage_aggregate": checked_scenarios,
        "scenario_coverage_aggregate_sha256": canonical_sha256(
            checked_scenarios
        ),
        "scenario_proof_manifest_sha256": canonical_sha256(
            checked_scenarios.per_scenario_proof_manifest
        ),
        "scenario_coverage_disposition": (
            checked_scenarios.coverage_disposition
        ),
        "scenario_formal_guarantee": checked_scenarios.formal_guarantee,
        **probability_space_binding,
        "yield_scope": checked_yield,
        "cost_table": checked_cost,
        "expansion_order": checked_order,
        "planner_assessment": classification,
        "planner_assessment_sha256": canonical_sha256(classification),
        "cfa_binding_execution_sha256": cfa_binding_execution_sha256,
        "cfa_binding_execution_replayed": True,
        "planner_evidence_fresh_replay_required": True,
        "risk_certificate_semantic_replay_required": True,
        "risk_certificate_semantics_replayed": True,
        "scenario_replay_required": True,
        "scenario_proof_replayed": True,
        "serialized_bearer_authorization": False,
        "formal_scientific_certificate_authorized": False,
        "scientific_claim_authorized": False,
    }
    return CoverageFeasibilityAssessment(
        **payload,
        common_binding_sha256=canonical_sha256(payload),
    )


_CFA_PLANNER_CLASSIFIER = classify_planner_result
_CFA_PROBABILITY_SPACE_BINDER = _risk_scenario_probability_space_binding
_CFA_BUILDER_CORE = _build_coverage_feasibility_assessment_core
_CFA_MODEL_VALIDATOR = (
    CoverageFeasibilityAssessment.hashes_replay_from_bound_inputs
)


def _cfa_binding_execution_sha256() -> str:
    identity_checks = (
        (
            "Task 5 CFA builder",
            globals().get("_build_coverage_feasibility_assessment_core"),
            _CFA_BUILDER_CORE,
        ),
        (
            "Task 5 CFA probability-space binder",
            globals().get("_risk_scenario_probability_space_binding"),
            _CFA_PROBABILITY_SPACE_BINDER,
        ),
        (
            "Task 5 CFA contract JSON parser",
            globals().get("parse_contract_json"),
            _CONTRACT_JSON_PARSER,
        ),
        (
            "Task 5 CFA risk replay",
            globals().get("replay_risk_certificate_replay_bundle"),
            _RISK_BUNDLE_REPLAYER,
        ),
        (
            "Task 5 CFA scenario replay",
            globals().get("replay_finite_scenario_aggregate"),
            _SCENARIO_AGGREGATE_REPLAYER,
        ),
        (
            "Task 5 CFA planner classifier",
            globals().get("classify_planner_result"),
            _CFA_PLANNER_CLASSIFIER,
        ),
        (
            "Task 5 CFA model validator",
            getattr(
                CoverageFeasibilityAssessment,
                "hashes_replay_from_bound_inputs",
                None,
            ),
            _CFA_MODEL_VALIDATOR,
        ),
    )
    for label, observed, expected in identity_checks:
        if observed is not expected:
            raise RuntimeError(f"{label} runtime identity changed")
    if python_function_execution_sha256 is not _PLANNER_EXECUTION_HASHER:
        raise RuntimeError(
            "Task 5 CFA execution hasher runtime identity changed"
        )
    return python_function_execution_sha256(
        _CFA_BUILDER_CORE,
        purpose=_CFA_BINDER_PURPOSE,
        strict_pure=False,
    )


_CFA_BINDING_EXECUTION_BASELINE_SHA256 = (
    _cfa_binding_execution_sha256()
)


def _assert_cfa_binding_execution_closure() -> str:
    observed = _cfa_binding_execution_sha256()
    if observed != _CFA_BINDING_EXECUTION_BASELINE_SHA256:
        raise RuntimeError(
            "coverage feasibility binding execution closure changed"
        )
    return observed


def build_coverage_feasibility_assessment(
    model: BoundedMilpModel,
    planner_result: RegisteredPlannerResult,
    *,
    risk_certificate: RiskCertificate,
    risk_certificate_replay_bundle: RiskCertificateReplayBundle,
    scenario_coverage_aggregate: FiniteScenarioCoverageAggregate,
    yield_scope: RegistryRef,
    cost_table: RegistryRef,
    expansion_order: RegistryRef,
    available_control_library_check: MilpCheckReceipt | None = None,
    registered_design_class_check: MilpCheckReceipt | None = None,
) -> CoverageFeasibilityAssessment:
    """Bind common inputs only under an unchanged CFA execution closure."""

    execution_pre = _assert_cfa_binding_execution_closure()
    assessment = _CFA_BUILDER_CORE(
        model,
        planner_result,
        cfa_binding_execution_sha256=execution_pre,
        risk_certificate=risk_certificate,
        risk_certificate_replay_bundle=risk_certificate_replay_bundle,
        scenario_coverage_aggregate=scenario_coverage_aggregate,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
        available_control_library_check=available_control_library_check,
        registered_design_class_check=registered_design_class_check,
    )
    execution_post = _assert_cfa_binding_execution_closure()
    if (
        execution_post != execution_pre
        or assessment.cfa_binding_execution_sha256 != execution_pre
    ):
        raise RuntimeError(
            "coverage feasibility binding execution closure changed "
            "during build"
        )
    return assessment


def replay_coverage_feasibility_assessment(
    assessment: CoverageFeasibilityAssessment,
    model: BoundedMilpModel,
    planner_result: RegisteredPlannerResult,
    *,
    risk_certificate: RiskCertificate,
    risk_certificate_replay_bundle: RiskCertificateReplayBundle,
    scenario_coverage_aggregate: FiniteScenarioCoverageAggregate,
    yield_scope: RegistryRef,
    cost_table: RegistryRef,
    expansion_order: RegistryRef,
    available_control_library_check: MilpCheckReceipt | None = None,
    registered_design_class_check: MilpCheckReceipt | None = None,
) -> CoverageFeasibilityAssessment:
    """Rebuild every binding and reject a serialized assessment mismatch."""

    if type(assessment) is not CoverageFeasibilityAssessment:
        raise TypeError(
            "assessment must be exactly CoverageFeasibilityAssessment"
        )
    try:
        checked = strict_revalidate_contract_model(assessment)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"coverage feasibility assessment failed structural replay: {exc}"
        ) from exc
    replayed = build_coverage_feasibility_assessment(
        model,
        planner_result,
        risk_certificate=risk_certificate,
        risk_certificate_replay_bundle=risk_certificate_replay_bundle,
        scenario_coverage_aggregate=scenario_coverage_aggregate,
        yield_scope=yield_scope,
        cost_table=cost_table,
        expansion_order=expansion_order,
        available_control_library_check=available_control_library_check,
        registered_design_class_check=registered_design_class_check,
    )
    if canonical_json_bytes(checked) != canonical_json_bytes(replayed):
        raise ValueError(
            "coverage feasibility assessment does not match fresh replay"
        )
    return replayed
