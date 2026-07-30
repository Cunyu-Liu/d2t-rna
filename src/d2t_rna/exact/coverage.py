"""Exact synthetic risk and confidence-coverage verification.

This module exhaustively evaluates a finite registered known-channel family.
It emits an exact-synthetic report only.  It cannot issue, authorize, or be
converted into a scientific :class:`RiskCertificate`.
"""

from __future__ import annotations

import hashlib
import sys
from fractions import Fraction
from pathlib import Path
from types import FunctionType
from typing import Literal, TypeAlias, TypeVar

from pydantic import StrictBool, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    Rational,
    RegisteredId,
    Sha256Hex,
)

from .confidence import (
    FROZEN_CONTRACT_SHA256,
    ConfidenceRule,
    ConfidenceRuleOutput,
    ConfidenceProcedureSpec,
    DecisionOutcome,
    ExactDecisionRuleSpec,
    ExactParameterFamily,
    HypothesisRegion,
    _assert_fraction_runtime_integrity,
    _confidence_output_record,
    _decision_from_validated_members,
    _runtime_identity_matches,
    _type_runtime_identity_token,
    _type_runtime_surface_descriptor,
    _validate_confidence_rule_output,
    classify_hypothesis_region,
    confidence_module_sha256,
    confidence_rule_implementation_sha256,
    python_function_execution_sha256,
)
from .enumerate import (
    JointOutcome,
    iter_joint_outcome_probabilities,
)
from .support import ExactSupportSpec, validate_and_size_support


EXACT_COVERAGE_VERIFIER_CONFIGURATION_SHA256 = canonical_sha256(
    {
        "verifier_id": "d2t_rna.exact_synthetic_coverage.v1",
        "contract_sha256": FROZEN_CONTRACT_SHA256,
        "arithmetic": "FRACTION",
        "support": "FULL_ENUMERATION",
        "coverage_aggregation": "MIN_PER_PARAMETER",
        "risk_aggregation": "MAX_PER_REGISTERED_REGION",
        "indifference_bound": {"numerator": 1, "denominator": 20},
        "uniform_coverage": {"numerator": 19, "denominator": 20},
    }
)
_COVERAGE_MODEL_RUNTIME_BASELINES: tuple[
    tuple[type, str, object],
    ...,
] = ()


def _assert_coverage_fraction_runtime_integrity() -> None:
    """Bind both local aliases that execute coverage arithmetic."""

    if type(iter_joint_outcome_probabilities) is not FunctionType:
        raise RuntimeError(
            "coverage probability enumerator was replaced after import"
        )
    _assert_fraction_runtime_integrity(
        module_aliases=(
            ("d2t_rna.exact.coverage", Fraction),
            (
                "d2t_rna.exact.enumerate",
                iter_joint_outcome_probabilities.__globals__.get(
                    "Fraction"
                ),
            ),
        )
    )


def coverage_module_sha256() -> str:
    """Hash the exact source/runtime closure executing coverage verification."""

    _assert_coverage_fraction_runtime_integrity()
    _assert_coverage_model_runtime_integrity()
    d2t_rna_root = Path(__file__).resolve().parents[1]
    files = {
        "exact.coverage": Path(__file__).resolve(),
        "contracts.enums": d2t_rna_root / "contracts" / "enums.py",
    }
    file_hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in files.items()
    }
    runtime_function_names = (
        "_fraction",
        "_rational",
        "_bounded_probability",
        "_validate_probability_partition",
        "_strict_exact",
        "_assert_fraction_runtime_integrity",
        "_assert_coverage_fraction_runtime_integrity",
        "_update_transcript",
        "_new_accumulator",
        "_execute_confidence_rule_twice",
        "_validate_coverage_outcome",
        "_iter_lockstep_law_rows",
        "_build_point_result",
        "evaluate_exact_synthetic_risk_coverage",
        "replay_exact_synthetic_coverage_report",
        "canonical_json_bytes",
        "canonical_sha256",
        "strict_revalidate_contract_model",
        "_validate_confidence_rule_output",
        "_confidence_output_record",
        "_decision_from_validated_members",
        "_type_runtime_surface_descriptor",
        "classify_hypothesis_region",
        "confidence_rule_implementation_sha256",
        "iter_joint_outcome_probabilities",
        "validate_and_size_support",
    )
    function_hashes: dict[str, str] = {}
    for name in runtime_function_names:
        function = globals().get(name)
        if type(function) is not FunctionType:
            raise RuntimeError(
                f"coverage runtime dependency was replaced: {name}"
            )
        function_hashes[name] = python_function_execution_sha256(
            function,
            purpose=f"COVERAGE_RUNTIME_DEPENDENCY:{name}",
            strict_pure=False,
        )
    return canonical_sha256(
        {
            "schema": "d2t_rna.coverage_execution_closure.v1",
            "files": file_hashes,
            "confidence_execution_closure_hash": (
                # This transitively binds enumerate, support, base, primitives,
                # Python, and Pydantic runtime versions.
                confidence_module_sha256()
            ),
            "runtime_function_code_hashes": function_hashes,
            "python_cache_tag": sys.implementation.cache_tag,
        }
    )


class CoverageSemanticError(ValueError):
    """Raised when an exact report would be incomplete or semantically invalid."""


def _assert_coverage_model_runtime_integrity() -> None:
    """Reject coverage-model class mutation after clean module import."""

    if not _COVERAGE_MODEL_RUNTIME_BASELINES:
        raise RuntimeError(
            "coverage model runtime baseline was not initialized"
        )
    for (
        model_type,
        expected_hash,
        expected_identity,
    ) in _COVERAGE_MODEL_RUNTIME_BASELINES:
        actual_hash = canonical_sha256(
            _type_runtime_surface_descriptor(model_type)
        )
        actual_identity = _type_runtime_identity_token(model_type)
        if (
            actual_hash != expected_hash
            or not _runtime_identity_matches(
                actual_identity,
                expected_identity,
            )
        ):
            raise RuntimeError(
                "coverage verifier runtime class was mutated after import: "
                f"{model_type.__module__}.{model_type.__qualname__}"
            )


def _fraction(value: Rational) -> Fraction:
    return Fraction(value.numerator, value.denominator)


def _rational(value: Fraction | int) -> Rational:
    exact = Fraction(value)
    return Rational(
        numerator=exact.numerator,
        denominator=exact.denominator,
    )


def _bounded_probability(value: Rational, *, label: str) -> Fraction:
    exact = _fraction(value)
    if exact < 0 or exact > 1:
        raise ValueError(f"{label} must lie in the exact interval [0, 1]")
    return exact


def _validate_probability_partition(
    *,
    total_probability: Rational,
    p_certify: Rational,
    p_reject: Rational,
    p_abstain: Rational,
    coverage: Rational,
) -> None:
    total = _bounded_probability(
        total_probability,
        label="total probability",
    )
    certify = _bounded_probability(p_certify, label="p_certify")
    reject = _bounded_probability(p_reject, label="p_reject")
    abstain = _bounded_probability(p_abstain, label="p_abstain")
    _bounded_probability(coverage, label="coverage")
    if total != 1:
        raise ValueError("each exact parameter law must account for mass one")
    if certify + reject + abstain != total:
        raise ValueError(
            "CERTIFY, REJECT, and ABSTAIN must partition exact probability mass"
        )


class H0PointRiskCoverage(FrozenContractModel):
    schema_id: Literal["d2t_rna.exact_h0_point_risk_coverage"] = (
        "d2t_rna.exact_h0_point_risk_coverage"
    )
    schema_version: Literal["1.0"] = "1.0"
    parameter_id: RegisteredId
    region: Literal[HypothesisRegion.H0] = HypothesisRegion.H0
    total_probability: Rational
    p_certify: Rational
    p_reject: Rational
    p_abstain: Rational
    coverage: Rational
    wrong_reject_probability: Rational

    @model_validator(mode="after")
    def h0_error_is_exactly_reject(self) -> "H0PointRiskCoverage":
        _validate_probability_partition(
            total_probability=self.total_probability,
            p_certify=self.p_certify,
            p_reject=self.p_reject,
            p_abstain=self.p_abstain,
            coverage=self.coverage,
        )
        if _fraction(self.wrong_reject_probability) != _fraction(
            self.p_reject
        ):
            raise ValueError("the H0 wrong event is exactly REJECT")
        if _fraction(self.wrong_reject_probability) > (
            1 - _fraction(self.coverage)
        ):
            raise ValueError("H0 wrong rejection must imply noncoverage")
        return self


class H1PointRiskCoverage(FrozenContractModel):
    schema_id: Literal["d2t_rna.exact_h1_point_risk_coverage"] = (
        "d2t_rna.exact_h1_point_risk_coverage"
    )
    schema_version: Literal["1.0"] = "1.0"
    parameter_id: RegisteredId
    region: Literal[HypothesisRegion.H1] = HypothesisRegion.H1
    total_probability: Rational
    p_certify: Rational
    p_reject: Rational
    p_abstain: Rational
    coverage: Rational
    wrong_certify_probability: Rational

    @model_validator(mode="after")
    def h1_error_is_exactly_certify(self) -> "H1PointRiskCoverage":
        _validate_probability_partition(
            total_probability=self.total_probability,
            p_certify=self.p_certify,
            p_reject=self.p_reject,
            p_abstain=self.p_abstain,
            coverage=self.coverage,
        )
        if _fraction(self.wrong_certify_probability) != _fraction(
            self.p_certify
        ):
            raise ValueError("the H1 wrong event is exactly CERTIFY")
        if _fraction(self.wrong_certify_probability) > (
            1 - _fraction(self.coverage)
        ):
            raise ValueError("H1 wrong certification must imply noncoverage")
        return self


class IndifferencePointRiskCoverage(FrozenContractModel):
    schema_id: Literal[
        "d2t_rna.exact_indifference_point_risk_coverage"
    ] = "d2t_rna.exact_indifference_point_risk_coverage"
    schema_version: Literal["1.0"] = "1.0"
    parameter_id: RegisteredId
    region: Literal[HypothesisRegion.INDIFFERENCE] = (
        HypothesisRegion.INDIFFERENCE
    )
    total_probability: Rational
    p_certify: Rational
    p_reject: Rational
    p_abstain: Rational
    coverage: Rational
    decisive_probability: Rational

    @model_validator(mode="after")
    def indifference_error_is_exactly_decisive(
        self,
    ) -> "IndifferencePointRiskCoverage":
        _validate_probability_partition(
            total_probability=self.total_probability,
            p_certify=self.p_certify,
            p_reject=self.p_reject,
            p_abstain=self.p_abstain,
            coverage=self.coverage,
        )
        decisive = _fraction(self.p_certify) + _fraction(self.p_reject)
        if _fraction(self.decisive_probability) != decisive:
            raise ValueError(
                "the indifference decisive event is CERTIFY union REJECT"
            )
        if decisive > 1 - _fraction(self.coverage):
            raise ValueError(
                "an indifference decisive output must imply noncoverage"
            )
        return self


PointRiskCoverage: TypeAlias = (
    H0PointRiskCoverage
    | H1PointRiskCoverage
    | IndifferencePointRiskCoverage
)


class ExactSyntheticCoverageReport(FrozenContractModel):
    """Hash-bound exhaustive result with a deliberately narrow claim domain."""

    schema_id: Literal["d2t_rna.exact_synthetic_coverage_report"] = (
        "d2t_rna.exact_synthetic_coverage_report"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_scope: Literal[ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL] = (
        ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL
    )
    claim_domain: Literal["EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY"] = (
        "EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY"
    )
    evidence_grade: Literal["EXACT_RATIONAL_ENUMERATION"] = (
        "EXACT_RATIONAL_ENUMERATION"
    )
    support_spec_hash: Sha256Hex
    support_plan_hash: Sha256Hex
    parameter_universe_hash: Sha256Hex
    probability_space_hash: Sha256Hex
    synthetic_prerequisites_hash: Sha256Hex
    sampling_law_manifest_hash: Sha256Hex
    hypothesis_partition_hash: Sha256Hex
    confidence_procedure_hash: Sha256Hex
    decision_rule_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    engine_code_hash: Sha256Hex
    verifier_configuration_hash: Sha256Hex
    evaluation_transcript_hash: Sha256Hex
    transcript_complete: Literal[True] = True
    outcome_count: NonNegativeInt
    point_results: tuple[
        H0PointRiskCoverage
        | H1PointRiskCoverage
        | IndifferencePointRiskCoverage,
        ...,
    ]
    h0_wrong_reject_bound: Rational
    h0_worst_parameter_id: RegisteredId
    h1_wrong_certify_bound: Rational
    h1_worst_parameter_id: RegisteredId
    indifference_decisive_output_bound: Rational
    indifference_worst_parameter_id: RegisteredId
    confidence_set_uniform_coverage: Rational
    coverage_worst_parameter_id: RegisteredId
    required_uniform_coverage: Rational
    required_indifference_decisive_bound: Rational
    probability_mass_accounted: Rational
    omitted_mass_bound: Rational
    numerical_error_bound: Rational
    mathematical_statement_verified: StrictBool
    risk_certificate_issued: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False
    prospective_claim_authorized: Literal[False] = False
    new_library_claim_authorized: Literal[False] = False

    @model_validator(mode="after")
    def exact_report_has_no_scientific_scope_escalation(
        self,
    ) -> "ExactSyntheticCoverageReport":
        if not self.point_results:
            raise ValueError("exact synthetic report cannot be empty")
        if self.outcome_count <= 0:
            raise ValueError("exact synthetic report must enumerate outcomes")
        if _fraction(self.probability_mass_accounted) != 1:
            raise ValueError("exact report must account for all probability mass")
        if _fraction(self.omitted_mass_bound) != 0:
            raise ValueError("exact enumeration cannot carry omitted mass")
        if _fraction(self.numerical_error_bound) != 0:
            raise ValueError("Fraction enumeration has zero numerical error")
        if self.engine_code_hash != coverage_module_sha256():
            raise ValueError("exact coverage engine code hash is stale")
        if (
            self.verifier_configuration_hash
            != EXACT_COVERAGE_VERIFIER_CONFIGURATION_SHA256
        ):
            raise ValueError(
                "exact coverage verifier configuration is unregistered"
            )
        parameter_ids = tuple(
            result.parameter_id for result in self.point_results
        )
        if len(set(parameter_ids)) != len(parameter_ids):
            raise ValueError("point results contain duplicate parameter IDs")
        if parameter_ids != tuple(sorted(parameter_ids)):
            raise ValueError("point results must be canonically ordered")
        h0_results = tuple(
            result
            for result in self.point_results
            if isinstance(result, H0PointRiskCoverage)
        )
        h1_results = tuple(
            result
            for result in self.point_results
            if isinstance(result, H1PointRiskCoverage)
        )
        indifference_results = tuple(
            result
            for result in self.point_results
            if isinstance(result, IndifferencePointRiskCoverage)
        )
        if not h0_results or not h1_results or not indifference_results:
            raise ValueError(
                "exact report requires H0, H1, and indifference results"
            )
        worst_h0 = max(
            h0_results,
            key=lambda result: _fraction(
                result.wrong_reject_probability
            ),
        )
        worst_h1 = max(
            h1_results,
            key=lambda result: _fraction(
                result.wrong_certify_probability
            ),
        )
        worst_indifference = max(
            indifference_results,
            key=lambda result: _fraction(result.decisive_probability),
        )
        worst_coverage = min(
            self.point_results,
            key=lambda result: _fraction(result.coverage),
        )
        aggregate_bindings = (
            (
                _fraction(self.h0_wrong_reject_bound),
                self.h0_worst_parameter_id,
                _fraction(worst_h0.wrong_reject_probability),
                worst_h0.parameter_id,
            ),
            (
                _fraction(self.h1_wrong_certify_bound),
                self.h1_worst_parameter_id,
                _fraction(worst_h1.wrong_certify_probability),
                worst_h1.parameter_id,
            ),
            (
                _fraction(self.indifference_decisive_output_bound),
                self.indifference_worst_parameter_id,
                _fraction(worst_indifference.decisive_probability),
                worst_indifference.parameter_id,
            ),
            (
                _fraction(self.confidence_set_uniform_coverage),
                self.coverage_worst_parameter_id,
                _fraction(worst_coverage.coverage),
                worst_coverage.parameter_id,
            ),
        )
        if any(
            observed_value != expected_value
            or observed_id != expected_id
            for (
                observed_value,
                observed_id,
                expected_value,
                expected_id,
            ) in aggregate_bindings
        ):
            raise ValueError(
                "exact report aggregates do not replay from point results"
            )
        required_coverage = _fraction(self.required_uniform_coverage)
        required_decisive = _fraction(
            self.required_indifference_decisive_bound
        )
        if required_coverage != Fraction(19, 20):
            raise ValueError("Task 4 uniform coverage target must be 19/20")
        if required_decisive != Fraction(1, 20):
            raise ValueError("Task 4 indifference bound must be 1/20")
        derived_verdict = (
            _fraction(self.confidence_set_uniform_coverage)
            >= required_coverage
            and _fraction(self.h0_wrong_reject_bound) <= required_decisive
            and _fraction(self.h1_wrong_certify_bound) <= required_decisive
            and _fraction(self.indifference_decisive_output_bound)
            <= required_decisive
        )
        if self.mathematical_statement_verified is not derived_verdict:
            raise ValueError(
                "mathematical verdict must equal the exact registered gates"
            )
        return self


class ExactSyntheticCoverageReplayCredential(FrozenContractModel):
    """Non-bearer record emitted after re-running every registered raw input.

    Reports and credentials are deliberately separate types.  A saved report
    has no replay status, while this record binds the freshly rebuilt report.
    It cannot authorize scientific or downstream claims by possession alone;
    a consumer must repeat the live replay and verify an external source
    manifest for the recorded engine hash.
    """

    schema_id: Literal["d2t_rna.exact_coverage_replay_credential"] = (
        "d2t_rna.exact_coverage_replay_credential"
    )
    schema_version: Literal["1.0"] = "1.0"
    report_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    evaluation_transcript_hash: Sha256Hex
    engine_code_hash: Sha256Hex
    verifier_configuration_hash: Sha256Hex
    live_replay_completed: Literal[True] = True
    external_source_anchor_required: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    risk_certificate_issued: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False
    prospective_claim_authorized: Literal[False] = False
    new_library_claim_authorized: Literal[False] = False

    @model_validator(mode="after")
    def credential_remains_non_bearer_and_runtime_bound(
        self,
    ) -> "ExactSyntheticCoverageReplayCredential":
        if self.engine_code_hash != coverage_module_sha256():
            raise ValueError("exact coverage replay engine hash is stale")
        if (
            self.verifier_configuration_hash
            != EXACT_COVERAGE_VERIFIER_CONFIGURATION_SHA256
        ):
            raise ValueError(
                "exact coverage replay configuration is unregistered"
            )
        return self


ModelT = TypeVar("ModelT", bound=FrozenContractModel)


def _strict_exact(
    value: object,
    expected_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    if type(value) is not expected_type:
        raise TypeError(f"{label} must be exactly {expected_type.__name__}")
    return strict_revalidate_contract_model(value)


def _update_transcript(
    digest: "hashlib._Hash",
    value: object,
) -> None:
    payload = canonical_json_bytes(value)
    digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
    digest.update(payload)


def _new_accumulator() -> dict[str, Fraction]:
    return {
        "total": Fraction(0, 1),
        "coverage": Fraction(0, 1),
        "certify": Fraction(0, 1),
        "reject": Fraction(0, 1),
        "abstain": Fraction(0, 1),
    }


def _execute_confidence_rule_twice(
    rule: ConfidenceRule,
    outcome: JointOutcome,
) -> ConfidenceRuleOutput:
    checked_first = _validate_confidence_rule_output(
        rule(outcome),
        label="coverage",
    )
    checked_second = _validate_confidence_rule_output(
        rule(outcome),
        label="coverage replay",
    )
    if checked_first != checked_second:
        raise CoverageSemanticError(
            "confidence procedure is not deterministic on replay"
        )
    return checked_first


def _validate_coverage_outcome(
    outcome: object,
    support: ExactSupportSpec,
) -> JointOutcome:
    if type(outcome) is not tuple:
        raise CoverageSemanticError("coverage stream outcome must be a tuple")
    if len(outcome) != len(support.actions):
        raise CoverageSemanticError(
            "coverage stream outcome has wrong action dimension"
        )
    for action, counts in zip(support.actions, outcome, strict=True):
        if type(counts) is not tuple:
            raise CoverageSemanticError(
                "coverage stream count vector must be a tuple"
            )
        if len(counts) != len(action.alphabet):
            raise CoverageSemanticError(
                "coverage stream alphabet dimension mismatch"
            )
        if any(type(count) is not int or count < 0 for count in counts):
            raise CoverageSemanticError(
                "coverage stream counts must be nonnegative exact integers"
            )
        if sum(counts) != action.sample_size:
            raise CoverageSemanticError(
                "coverage stream counts do not sum to the sample size"
            )
    return outcome


def _iter_lockstep_law_rows(
    streams: tuple[object, ...],
):
    """Translate unequal registered law streams into a semantic gate failure."""

    try:
        yield from zip(*streams, strict=True)
    except ValueError as exc:
        raise CoverageSemanticError(
            "registered point law streams have different lengths"
        ) from exc


def _build_point_result(
    *,
    parameter_id: str,
    region: HypothesisRegion,
    accumulator: dict[str, Fraction],
) -> PointRiskCoverage:
    common = {
        "parameter_id": parameter_id,
        "total_probability": _rational(accumulator["total"]),
        "p_certify": _rational(accumulator["certify"]),
        "p_reject": _rational(accumulator["reject"]),
        "p_abstain": _rational(accumulator["abstain"]),
        "coverage": _rational(accumulator["coverage"]),
    }
    if region is HypothesisRegion.H0:
        return H0PointRiskCoverage(
            **common,
            wrong_reject_probability=_rational(accumulator["reject"]),
        )
    if region is HypothesisRegion.H1:
        return H1PointRiskCoverage(
            **common,
            wrong_certify_probability=_rational(accumulator["certify"]),
        )
    return IndifferencePointRiskCoverage(
        **common,
        decisive_probability=_rational(
            accumulator["certify"] + accumulator["reject"]
        ),
    )


def evaluate_exact_synthetic_risk_coverage(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    confidence_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    confidence_rule: ConfidenceRule,
    engine_code_hash: Sha256Hex,
) -> ExactSyntheticCoverageReport:
    """Exhaustively evaluate exact coverage and the three registered risks.

    The callback is invoked twice per canonical count outcome to detect local
    nondeterminism.  All point-law streams are hash-bound and consumed in
    lockstep.  An exception,
    short stream, invalid result, or mass mismatch aborts before a report is
    constructed.
    """

    _assert_coverage_fraction_runtime_integrity()
    checked_support = _strict_exact(
        support,
        ExactSupportSpec,
        label="support",
    )
    checked_family = _strict_exact(
        family,
        ExactParameterFamily,
        label="parameter family",
    )
    checked_procedure = _strict_exact(
        confidence_procedure,
        ConfidenceProcedureSpec,
        label="confidence procedure",
    )
    checked_decision_rule = _strict_exact(
        decision_rule,
        ExactDecisionRuleSpec,
        label="decision rule",
    )
    if type(engine_code_hash) is not str:
        raise TypeError("engine_code_hash must be a SHA-256 string")
    if len(engine_code_hash) != 64 or any(
        character not in "0123456789abcdef"
        for character in engine_code_hash
    ):
        raise ValueError("engine_code_hash must be lowercase SHA-256 hex")
    actual_engine_code_hash = coverage_module_sha256()
    if engine_code_hash != actual_engine_code_hash:
        raise CoverageSemanticError(
            "engine_code_hash does not match the executing coverage module"
        )
    if not callable(confidence_rule):
        raise TypeError("confidence_rule must be callable")
    callable_hash = confidence_rule_implementation_sha256(
        confidence_rule
    )
    if checked_procedure.implementation_hash != callable_hash:
        raise CoverageSemanticError(
            "confidence procedure hash does not bind the supplied "
            "implementation"
        )

    support_hash = canonical_sha256(checked_support)
    if checked_family.support_spec_hash != support_hash:
        raise CoverageSemanticError(
            "parameter family belongs to a different exact support"
        )
    universe_hash = checked_family.parameter_universe_hash
    if (
        checked_procedure.parameter_universe_hash != universe_hash
        or checked_decision_rule.parameter_universe_hash != universe_hash
    ):
        raise CoverageSemanticError(
            "confidence procedure, decision rule, and family universe differ"
        )

    regions = tuple(
        classify_hypothesis_region(
            point.loss,
            checked_family.thresholds,
        )
        for point in checked_family.points
    )
    required_regions = {
        HypothesisRegion.H0,
        HypothesisRegion.H1,
        HypothesisRegion.INDIFFERENCE,
    }
    if set(regions) != required_regions:
        raise CoverageSemanticError(
            "exact report requires nonempty registered H0, H1, and "
            "indifference point sets"
        )

    support_plan = validate_and_size_support(checked_support)
    support_plan_hash = canonical_sha256(support_plan)
    confidence_procedure_hash = canonical_sha256(checked_procedure)
    decision_rule_hash = canonical_sha256(checked_decision_rule)
    hypothesis_partition_hash = canonical_sha256(
        tuple(
            {
                "parameter_id": point.parameter_id,
                "region": region,
            }
            for point, region in zip(
                checked_family.points,
                regions,
                strict=True,
            )
        )
    )
    evaluation_input_bundle_hash = canonical_sha256(
        {
            "schema": "d2t_rna.exact_coverage_input_bundle.v1",
            "contract_sha256": FROZEN_CONTRACT_SHA256,
            "support_spec_hash": support_hash,
            "support_plan_hash": support_plan_hash,
            "parameter_universe_hash": universe_hash,
            "probability_space_hash": (
                checked_family.probability_space_hash
            ),
            "synthetic_prerequisites_hash": (
                checked_family.synthetic_prerequisites_hash
            ),
            "sampling_law_manifest_hash": (
                checked_family.sampling_law_manifest_hash
            ),
            "hypothesis_partition_hash": hypothesis_partition_hash,
            "confidence_procedure_hash": confidence_procedure_hash,
            "decision_rule_hash": decision_rule_hash,
            "engine_code_hash": actual_engine_code_hash,
            "verifier_configuration_hash": (
                EXACT_COVERAGE_VERIFIER_CONFIGURATION_SHA256
            ),
        }
    )

    accumulators = {
        point.parameter_id: _new_accumulator()
        for point in checked_family.points
    }
    streams = tuple(
        iter_joint_outcome_probabilities(checked_support, point.law)
        for point in checked_family.points
    )
    transcript = hashlib.sha256()
    _update_transcript(
        transcript,
        {
            "transcript_schema": (
                "d2t_rna.exact_synthetic_risk_coverage_transcript.v1"
            ),
            "support_spec_hash": support_hash,
            "support_plan_hash": support_plan_hash,
            "parameter_universe_hash": universe_hash,
            "hypothesis_partition_hash": hypothesis_partition_hash,
            "confidence_procedure_hash": confidence_procedure_hash,
            "decision_rule_hash": decision_rule_hash,
            "evaluation_input_bundle_hash": evaluation_input_bundle_hash,
        },
    )

    outcome_count = 0
    previous_outcome: JointOutcome | None = None
    for point_rows in _iter_lockstep_law_rows(streams):
        if any(type(row) is not tuple or len(row) != 2 for row in point_rows):
            raise CoverageSemanticError(
                "coverage law stream row must be an outcome/probability tuple"
            )
        outcome = _validate_coverage_outcome(
            point_rows[0][0],
            checked_support,
        )
        if previous_outcome is not None and outcome <= previous_outcome:
            raise CoverageSemanticError(
                "coverage outcomes must be strictly increasing"
            )
        if any(
            _validate_coverage_outcome(row[0], checked_support) != outcome
            for row in point_rows[1:]
        ):
            raise CoverageSemanticError(
                "registered point laws enumerated different outcome orders"
            )
        if outcome_count >= support_plan.joint_support_size:
            raise CoverageSemanticError(
                "coverage stream exceeded the support preflight count"
            )
        previous_outcome = outcome
        result = _execute_confidence_rule_twice(
            confidence_rule,
            outcome,
        )
        decision = _decision_from_validated_members(
            result[0],
            family=checked_family,
            decision_rule=checked_decision_rule,
        )

        transcript_probabilities: list[dict[str, object]] = []
        for point, row in zip(
            checked_family.points,
            point_rows,
            strict=True,
        ):
            probability = row[1]
            if type(probability) is not Fraction:
                raise CoverageSemanticError(
                    "exact coverage law probability must be exactly Fraction"
                )
            if probability < 0 or probability > 1:
                raise CoverageSemanticError(
                    "exact point law emitted probability outside [0, 1]"
                )
            accumulator = accumulators[point.parameter_id]
            accumulator["total"] += probability
            if point.parameter_id in result[0]:
                accumulator["coverage"] += probability
            if decision is DecisionOutcome.CERTIFY:
                accumulator["certify"] += probability
            elif decision is DecisionOutcome.REJECT:
                accumulator["reject"] += probability
            else:
                accumulator["abstain"] += probability
            transcript_probabilities.append(
                {
                    "parameter_id": point.parameter_id,
                    "probability": _rational(probability),
                }
            )

        _update_transcript(
            transcript,
            {
                "outcome_index": outcome_count,
                "outcome": outcome,
                "confidence_result": _confidence_output_record(
                    result,
                    parameter_universe_hash=universe_hash,
                ),
                "decision": decision,
                "point_probabilities": tuple(transcript_probabilities),
            },
        )
        outcome_count += 1

    if outcome_count != support_plan.joint_support_size:
        raise CoverageSemanticError(
            "coverage outcome count does not match support preflight"
        )
    if confidence_rule_implementation_sha256(
        confidence_rule
    ) != callable_hash:
        raise CoverageSemanticError(
            "confidence implementation state changed during evaluation"
        )
    if coverage_module_sha256() != actual_engine_code_hash:
        raise CoverageSemanticError(
            "coverage engine runtime changed during evaluation"
        )
    _update_transcript(
        transcript,
        {
            "expected_outcome_count": support_plan.joint_support_size,
            "observed_outcome_count": outcome_count,
            "transcript_complete": True,
        },
    )

    point_results: list[PointRiskCoverage] = []
    for point, region in zip(
        checked_family.points,
        regions,
        strict=True,
    ):
        accumulator = accumulators[point.parameter_id]
        if accumulator["total"] != 1:
            raise CoverageSemanticError(
                f"point law {point.parameter_id!r} has incomplete mass"
            )
        if (
            accumulator["certify"]
            + accumulator["reject"]
            + accumulator["abstain"]
            != accumulator["total"]
        ):
            raise CoverageSemanticError(
                f"decision mass does not partition point {point.parameter_id!r}"
            )
        point_results.append(
            _build_point_result(
                parameter_id=point.parameter_id,
                region=region,
                accumulator=accumulator,
            )
        )

    h0_results = tuple(
        result
        for result in point_results
        if isinstance(result, H0PointRiskCoverage)
    )
    h1_results = tuple(
        result
        for result in point_results
        if isinstance(result, H1PointRiskCoverage)
    )
    indifference_results = tuple(
        result
        for result in point_results
        if isinstance(result, IndifferencePointRiskCoverage)
    )
    worst_h0 = max(
        h0_results,
        key=lambda result: _fraction(result.wrong_reject_probability),
    )
    worst_h1 = max(
        h1_results,
        key=lambda result: _fraction(result.wrong_certify_probability),
    )
    worst_indifference = max(
        indifference_results,
        key=lambda result: _fraction(result.decisive_probability),
    )
    worst_coverage = min(
        point_results,
        key=lambda result: _fraction(result.coverage),
    )

    h0_bound = _fraction(worst_h0.wrong_reject_probability)
    h1_bound = _fraction(worst_h1.wrong_certify_probability)
    indifference_bound = _fraction(
        worst_indifference.decisive_probability
    )
    uniform_coverage = _fraction(worst_coverage.coverage)
    target_coverage = Fraction(19, 20)
    target_risk = Fraction(1, 20)
    verified = (
        uniform_coverage >= target_coverage
        and h0_bound <= target_risk
        and h1_bound <= target_risk
        and indifference_bound <= target_risk
    )

    report = ExactSyntheticCoverageReport(
        support_spec_hash=support_hash,
        support_plan_hash=support_plan_hash,
        parameter_universe_hash=universe_hash,
        probability_space_hash=checked_family.probability_space_hash,
        synthetic_prerequisites_hash=(
            checked_family.synthetic_prerequisites_hash
        ),
        sampling_law_manifest_hash=(
            checked_family.sampling_law_manifest_hash
        ),
        hypothesis_partition_hash=hypothesis_partition_hash,
        confidence_procedure_hash=confidence_procedure_hash,
        decision_rule_hash=decision_rule_hash,
        evaluation_input_bundle_hash=evaluation_input_bundle_hash,
        engine_code_hash=actual_engine_code_hash,
        verifier_configuration_hash=(
            EXACT_COVERAGE_VERIFIER_CONFIGURATION_SHA256
        ),
        evaluation_transcript_hash=transcript.hexdigest(),
        transcript_complete=True,
        outcome_count=outcome_count,
        point_results=tuple(point_results),
        h0_wrong_reject_bound=_rational(h0_bound),
        h0_worst_parameter_id=worst_h0.parameter_id,
        h1_wrong_certify_bound=_rational(h1_bound),
        h1_worst_parameter_id=worst_h1.parameter_id,
        indifference_decisive_output_bound=_rational(
            indifference_bound
        ),
        indifference_worst_parameter_id=(
            worst_indifference.parameter_id
        ),
        confidence_set_uniform_coverage=_rational(uniform_coverage),
        coverage_worst_parameter_id=worst_coverage.parameter_id,
        required_uniform_coverage=_rational(target_coverage),
        required_indifference_decisive_bound=_rational(target_risk),
        probability_mass_accounted=_rational(1),
        omitted_mass_bound=_rational(0),
        numerical_error_bound=_rational(0),
        mathematical_statement_verified=verified,
        risk_certificate_issued=False,
        formal_scientific_certificate_authorized=False,
        prospective_claim_authorized=False,
        new_library_claim_authorized=False,
    )
    if coverage_module_sha256() != actual_engine_code_hash:
        raise CoverageSemanticError(
            "coverage engine runtime changed before report completion"
        )
    return report


def replay_exact_synthetic_coverage_report(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    confidence_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    confidence_rule: ConfidenceRule,
    engine_code_hash: Sha256Hex,
    report: ExactSyntheticCoverageReport,
) -> ExactSyntheticCoverageReplayCredential:
    """Re-run raw inputs and return a distinct, explicitly non-bearer record."""

    _assert_coverage_fraction_runtime_integrity()
    rebuilt = _strict_exact(
        report,
        ExactSyntheticCoverageReport,
        label="exact synthetic report",
    )
    expected = evaluate_exact_synthetic_risk_coverage(
        support=support,
        family=family,
        confidence_procedure=confidence_procedure,
        decision_rule=decision_rule,
        confidence_rule=confidence_rule,
        engine_code_hash=engine_code_hash,
    )
    if rebuilt != expected:
        raise CoverageSemanticError(
            "exact synthetic report does not replay from registered raw inputs"
        )
    credential = ExactSyntheticCoverageReplayCredential(
        report_hash=canonical_sha256(expected),
        evaluation_input_bundle_hash=(
            expected.evaluation_input_bundle_hash
        ),
        evaluation_transcript_hash=expected.evaluation_transcript_hash,
        engine_code_hash=expected.engine_code_hash,
        verifier_configuration_hash=(
            expected.verifier_configuration_hash
        ),
        live_replay_completed=True,
        external_source_anchor_required=True,
        serialized_bearer_authorization=False,
        risk_certificate_issued=False,
        formal_scientific_certificate_authorized=False,
        prospective_claim_authorized=False,
        new_library_claim_authorized=False,
    )
    _assert_coverage_fraction_runtime_integrity()
    return credential


_COVERAGE_RUNTIME_MODEL_TYPES = (
    H0PointRiskCoverage,
    H1PointRiskCoverage,
    IndifferencePointRiskCoverage,
    ExactSyntheticCoverageReport,
    ExactSyntheticCoverageReplayCredential,
)
_COVERAGE_MODEL_RUNTIME_BASELINES = tuple(
    (
        model_type,
        canonical_sha256(_type_runtime_surface_descriptor(model_type)),
        _type_runtime_identity_token(model_type),
    )
    for model_type in _COVERAGE_RUNTIME_MODEL_TYPES
)
