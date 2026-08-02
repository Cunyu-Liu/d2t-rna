"""Replayable Task 5 scenario proofs, finite aggregation, and RORC metrics.

Only exact enumeration has a registered formal verifier in this module.
Verified-interval and certified-truncation records remain nonformal until a
method-specific replay implementation exists. Monte Carlo records are always
predicted/nonformal. All aggregate claims are limited to the finite scenarios
embedded in the aggregate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum
from fractions import Fraction
from pathlib import Path
from types import CodeType, FunctionType
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
    validate_contract_json_syntax,
)
from d2t_rna.contracts.enums import (
    CoverageBoundMethod,
    RorcReason,
)
from d2t_rna.contracts.primitives import (
    NamedBound,
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.scenario import ScenarioProof
from d2t_rna.exact.confidence import (
    FROZEN_CONTRACT_SHA256,
    ConfidenceProcedureSpec,
    ExactDecisionRuleSpec,
    ExactParameterFamily,
    _runtime_identity_matches,
    _type_runtime_identity_token,
    _type_runtime_surface_descriptor,
    confidence_rule_implementation_sha256,
)
from d2t_rna.exact.coverage import (
    ExactSyntheticCoverageReport,
    ExactSyntheticCoverageReplayCredential,
    coverage_module_sha256,
    evaluate_exact_synthetic_risk_coverage,
    replay_exact_synthetic_coverage_report,
)
from d2t_rna.exact.support import ExactSupportSpec
from d2t_rna.probability.risk import validate_uniform_indifference_control


MAX_SCENARIO_OUTCOMES = 10_000
MAX_SCENARIO_BOUNDS_PER_KIND = 64
MAX_FINITE_SCENARIOS = 256
MAX_RORC_CASES = 10_000
MAX_BOUND_SEMANTICS_TEXT = 1_024
MAX_RATIONAL_COMPONENT_BITS = 256
MAX_EXACT_SUPPORT_JSON_CHARS = 100_000
MAX_EXACT_FAMILY_JSON_CHARS = 1_000_000
MAX_EXACT_PROCEDURE_JSON_CHARS = 20_000
MAX_EXACT_DECISION_RULE_JSON_CHARS = 20_000
MAX_EXACT_REPORT_JSON_CHARS = 2_000_000
MAX_EXACT_REPLAY_CREDENTIAL_JSON_CHARS = 100_000
MAX_EXACT_RAW_JSON_NODES = 100_000
MAX_EXACT_RAW_JSON_DEPTH = 64


class ScenarioCoverageDisposition(str, Enum):
    """Claim strength allowed by the replayed per-scenario method."""

    FORMAL_REGISTERED_SCENARIO_COVERAGE = (
        "FORMAL_REGISTERED_SCENARIO_COVERAGE"
    )
    RISK_CERTIFIED_COVERAGE_PREDICTED = (
        "RISK_CERTIFIED_COVERAGE_PREDICTED"
    )
    REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL = (
        "REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL"
    )


class RorcDecision(str, Enum):
    """The registered prospective RORC action remains abstention only."""

    ABSTAIN = "ABSTAIN"


class RorcObservedDecision(str, Enum):
    """Decision observed in a historically exposed retrospective RORC case."""

    ABSTAIN = "ABSTAIN"
    CERTIFY = "CERTIFY"
    REJECT = "REJECT"


class BoundKind(str, Enum):
    """Direction and event family of one registered probability statement."""

    RISK_UPPER_BOUND = "RISK_UPPER_BOUND"
    COVERAGE_LOWER_BOUND = "COVERAGE_LOWER_BOUND"


class BoundSemanticDefinition(FrozenContractModel):
    """Full, hash-bound meaning of one reported bound.

    A bare bound ID is never a semantic registry.  Each entry freezes the
    event, estimand, estimator, numerical method, direction, and contract root.
    """

    bound_id: RegisteredId
    bound_kind: BoundKind
    event_semantics: StrictStr = Field(
        min_length=1,
        max_length=MAX_BOUND_SEMANTICS_TEXT,
    )
    estimand_definition: StrictStr = Field(
        min_length=1,
        max_length=MAX_BOUND_SEMANTICS_TEXT,
    )
    estimator_definition: StrictStr = Field(
        min_length=1,
        max_length=MAX_BOUND_SEMANTICS_TEXT,
    )
    coverage_bound_method: CoverageBoundMethod
    frozen_contract_sha256: Literal[FROZEN_CONTRACT_SHA256] = (
        FROZEN_CONTRACT_SHA256
    )


def _fraction(value: Rational, *, label: str) -> Fraction:
    if type(value) is not Rational:
        raise TypeError(f"{label} must be exactly Rational")
    checked = strict_revalidate_contract_model(value)
    if (
        abs(checked.numerator).bit_length()
        > MAX_RATIONAL_COMPONENT_BITS
        or checked.denominator.bit_length()
        > MAX_RATIONAL_COMPONENT_BITS
    ):
        raise ValueError(
            f"{label} exceeds the registered "
            f"{MAX_RATIONAL_COMPONENT_BITS}-bit rational component cap"
        )
    return _bounded_fraction(
        Fraction(checked.numerator, checked.denominator),
        label=label,
    )


def _bounded_fraction(value: Fraction, *, label: str) -> Fraction:
    if type(value) is not Fraction:
        raise TypeError(f"{label} must be exactly Fraction")
    if (
        abs(value.numerator).bit_length() > MAX_RATIONAL_COMPONENT_BITS
        or value.denominator.bit_length() > MAX_RATIONAL_COMPONENT_BITS
    ):
        raise ValueError(
            f"{label} arithmetic exceeds the registered "
            f"{MAX_RATIONAL_COMPONENT_BITS}-bit rational component cap"
        )
    return value


def _bounded_add(
    left: Fraction,
    right: Fraction,
    *,
    label: str,
) -> Fraction:
    return _bounded_fraction(left + right, label=label)


def _bounded_fraction_sum(
    values: Iterable[Fraction],
    *,
    label: str,
) -> Fraction:
    total = Fraction(0)
    for value in values:
        total = _bounded_add(total, value, label=label)
    return total


def _probability(value: Rational, *, label: str) -> Fraction:
    exact = _fraction(value, label=label)
    if exact < 0 or exact > 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return exact


def _positive_probability(value: Rational, *, label: str) -> Fraction:
    exact = _probability(value, label=label)
    if exact == 0:
        raise ValueError(f"{label} must be positive")
    return exact


def _rational(value: Fraction | int) -> Rational:
    exact = _bounded_fraction(
        Fraction(value),
        label="derived rational",
    )
    return Rational(
        numerator=exact.numerator,
        denominator=exact.denominator,
    )


def _validate_bound_set(
    bounds: tuple[NamedBound, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if not bounds:
        raise ValueError(f"{label} must be nonempty")
    if len(bounds) > MAX_SCENARIO_BOUNDS_PER_KIND:
        raise ValueError(
            f"{label} exceeds the registered "
            f"{MAX_SCENARIO_BOUNDS_PER_KIND}-bound cap"
        )
    if any(type(bound) is not NamedBound for bound in bounds):
        raise TypeError(f"{label} members must be exactly NamedBound")
    checked = tuple(strict_revalidate_contract_model(bound) for bound in bounds)
    bound_ids = tuple(bound.bound_id for bound in checked)
    if len(set(bound_ids)) != len(bound_ids):
        raise ValueError(f"{label} contains a duplicate bound ID")
    if bound_ids != tuple(sorted(bound_ids)):
        raise ValueError(f"{label} must use canonical bound-ID order")
    for bound in checked:
        _probability(bound.value, label=f"{label} {bound.bound_id!r}")
    return bound_ids


def _validate_event_flags(
    flags: tuple[BoundEventFlag, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if not flags:
        raise ValueError(f"{label} must be nonempty")
    if len(flags) > MAX_SCENARIO_BOUNDS_PER_KIND:
        raise ValueError(
            f"{label} exceeds the registered "
            f"{MAX_SCENARIO_BOUNDS_PER_KIND}-event cap"
        )
    if any(type(flag) is not BoundEventFlag for flag in flags):
        raise TypeError(f"{label} members must be exactly BoundEventFlag")
    checked = tuple(strict_revalidate_contract_model(flag) for flag in flags)
    bound_ids = tuple(flag.bound_id for flag in checked)
    if len(set(bound_ids)) != len(bound_ids):
        raise ValueError(f"{label} contains a duplicate bound ID")
    if bound_ids != tuple(sorted(bound_ids)):
        raise ValueError(f"{label} must use canonical bound-ID order")
    return bound_ids


def _bound_registry_sha256(
    definitions: tuple[BoundSemanticDefinition, ...],
) -> str:
    checked = _validate_bound_semantics(definitions)
    return canonical_sha256(
        {
            "schema": "d2t_rna.bound_semantics_registry.v1",
            "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
            "definitions": checked,
        },
    )


def _validate_bound_semantics(
    definitions: tuple[BoundSemanticDefinition, ...],
    *,
    risk_bound_ids: tuple[str, ...] | None = None,
    coverage_bound_ids: tuple[str, ...] | None = None,
) -> tuple[BoundSemanticDefinition, ...]:
    if not definitions:
        raise ValueError("bound semantic definitions must be nonempty")
    if len(definitions) > 2 * MAX_SCENARIO_BOUNDS_PER_KIND:
        raise ValueError("bound semantic registry exceeds the registered cap")
    if any(type(item) is not BoundSemanticDefinition for item in definitions):
        raise TypeError(
            "bound semantic definitions must be exactly "
            "BoundSemanticDefinition"
        )
    checked = tuple(
        strict_revalidate_contract_model(item) for item in definitions
    )
    keys = tuple((item.bound_kind.value, item.bound_id) for item in checked)
    if len(set(keys)) != len(keys):
        raise ValueError("bound semantic registry contains duplicate entries")
    if keys != tuple(sorted(keys)):
        raise ValueError("bound semantic registry must use canonical order")
    if risk_bound_ids is not None:
        observed_risk = tuple(
            item.bound_id
            for item in checked
            if item.bound_kind is BoundKind.RISK_UPPER_BOUND
        )
        if observed_risk != risk_bound_ids:
            raise ValueError(
                "risk bounds do not match the bound semantic registry"
            )
    if coverage_bound_ids is not None:
        observed_coverage = tuple(
            item.bound_id
            for item in checked
            if item.bound_kind is BoundKind.COVERAGE_LOWER_BOUND
        )
        if observed_coverage != coverage_bound_ids:
            raise ValueError(
                "coverage bounds do not match the bound semantic registry"
            )
    return checked


def _nonformal_atom_bound_semantics(
    *,
    risk_bound_ids: tuple[str, ...],
    coverage_bound_ids: tuple[str, ...],
    method: CoverageBoundMethod,
) -> tuple[BoundSemanticDefinition, ...]:
    """Describe caller-supplied evidence without elevating it to a proof."""

    definitions = tuple(
        BoundSemanticDefinition(
            bound_id=bound_id,
            bound_kind=BoundKind.COVERAGE_LOWER_BOUND,
            event_semantics=(
                "Caller-supplied Boolean coverage event over caller-supplied "
                f"finite atoms; registry key {bound_id}."
            ),
            estimand_definition=(
                "Probability of the named caller-supplied coverage event "
                "under the caller-supplied finite law."
            ),
            estimator_definition=(
                "Exact rational sum over caller-supplied atoms; this generic "
                "record is observational/nonformal and cannot authorize a "
                "registered coverage guarantee."
            ),
            coverage_bound_method=method,
        )
        for bound_id in coverage_bound_ids
    ) + tuple(
        BoundSemanticDefinition(
            bound_id=bound_id,
            bound_kind=BoundKind.RISK_UPPER_BOUND,
            event_semantics=(
                "Caller-supplied Boolean risk event over caller-supplied "
                f"finite atoms; registry key {bound_id}."
            ),
            estimand_definition=(
                "Probability of the named caller-supplied risk event under "
                "the caller-supplied finite law."
            ),
            estimator_definition=(
                "Exact rational sum over caller-supplied atoms; this generic "
                "record is observational/nonformal and cannot authorize a "
                "registered risk guarantee."
            ),
            coverage_bound_method=method,
        )
        for bound_id in risk_bound_ids
    )
    return tuple(
        sorted(
            definitions,
            key=lambda item: (item.bound_kind.value, item.bound_id),
        )
    )


class BoundEventFlag(FrozenContractModel):
    """Truth value of one registered event for one exact outcome."""

    bound_id: RegisteredId
    occurred: StrictBool


class ExactScenarioOutcome(FrozenContractModel):
    """One canonical atom of an exactly enumerated scenario law."""

    outcome_id: RegisteredId
    outcome_payload_sha256: Sha256Hex
    probability: Rational
    risk_events: tuple[BoundEventFlag, ...]
    coverage_events: tuple[BoundEventFlag, ...]

    @model_validator(mode="after")
    def validate_exact_outcome(self) -> ExactScenarioOutcome:
        _positive_probability(
            self.probability,
            label=f"outcome {self.outcome_id!r} probability",
        )
        _validate_event_flags(
            self.risk_events,
            label=f"outcome {self.outcome_id!r} risk events",
        )
        _validate_event_flags(
            self.coverage_events,
            label=f"outcome {self.outcome_id!r} coverage events",
        )
        return self


def _derive_exact_enumeration(
    *,
    scenario_id: str,
    outcomes: tuple[ExactScenarioOutcome, ...],
) -> dict[str, object]:
    if not outcomes:
        raise ValueError("exact enumeration requires at least one outcome")
    if len(outcomes) > MAX_SCENARIO_OUTCOMES:
        raise ValueError(
            "exact enumeration exceeds the registered "
            f"{MAX_SCENARIO_OUTCOMES}-outcome cap"
        )
    if any(type(outcome) is not ExactScenarioOutcome for outcome in outcomes):
        raise TypeError(
            "exact enumeration outcomes must be exactly ExactScenarioOutcome"
        )
    checked = tuple(
        strict_revalidate_contract_model(outcome) for outcome in outcomes
    )
    outcome_ids = tuple(outcome.outcome_id for outcome in checked)
    if len(set(outcome_ids)) != len(outcome_ids):
        raise ValueError("exact outcome IDs must be unique")
    if outcome_ids != tuple(sorted(outcome_ids)):
        raise ValueError("exact outcomes must use canonical outcome-ID order")

    probabilities = tuple(
        _positive_probability(
            outcome.probability,
            label=f"outcome {outcome.outcome_id!r} probability",
        )
        for outcome in checked
    )
    if (
        _bounded_fraction_sum(
            probabilities,
            label="exact outcome probability sum",
        )
        != 1
    ):
        raise ValueError("exact outcome probabilities must sum to one")

    risk_ids = _validate_event_flags(
        checked[0].risk_events,
        label=f"outcome {checked[0].outcome_id!r} risk events",
    )
    coverage_ids = _validate_event_flags(
        checked[0].coverage_events,
        label=f"outcome {checked[0].outcome_id!r} coverage events",
    )
    for outcome in checked[1:]:
        if (
            _validate_event_flags(
                outcome.risk_events,
                label=f"outcome {outcome.outcome_id!r} risk events",
            )
            != risk_ids
        ):
            raise ValueError(
                "all exact outcomes must share one risk-bound registry"
            )
        if (
            _validate_event_flags(
                outcome.coverage_events,
                label=f"outcome {outcome.outcome_id!r} coverage events",
            )
            != coverage_ids
        ):
            raise ValueError(
                "all exact outcomes must share one coverage-bound registry"
            )

    risk_values = {bound_id: Fraction(0) for bound_id in risk_ids}
    coverage_values = {bound_id: Fraction(0) for bound_id in coverage_ids}
    for outcome, probability in zip(checked, probabilities, strict=True):
        for flag in outcome.risk_events:
            if flag.occurred:
                risk_values[flag.bound_id] = _bounded_add(
                    risk_values[flag.bound_id],
                    probability,
                    label=f"risk event {flag.bound_id!r} probability sum",
                )
        for flag in outcome.coverage_events:
            if flag.occurred:
                coverage_values[flag.bound_id] = _bounded_add(
                    coverage_values[flag.bound_id],
                    probability,
                    label=(
                        f"coverage event {flag.bound_id!r} probability sum"
                    ),
                )

    risk_bounds = tuple(
        NamedBound(bound_id=bound_id, value=_rational(risk_values[bound_id]))
        for bound_id in risk_ids
    )
    coverage_bounds = tuple(
        NamedBound(
            bound_id=bound_id,
            value=_rational(coverage_values[bound_id]),
        )
        for bound_id in coverage_ids
    )
    law_hash = canonical_sha256(
        {
            "scenario_id": scenario_id,
            "canonical_exact_outcomes": checked,
        }
    )
    bound_semantics = _nonformal_atom_bound_semantics(
        risk_bound_ids=risk_ids,
        coverage_bound_ids=coverage_ids,
        method=CoverageBoundMethod.EXACT_ENUMERATION,
    )
    return {
        "outcomes": checked,
        "law_hash": law_hash,
        "risk_upper_bounds": risk_bounds,
        "coverage_lower_bounds": coverage_bounds,
        "probability_mass_accounted": _rational(1),
        "omitted_mass_bound": _rational(0),
        "numerical_error_bound": _rational(0),
        "bound_semantics": bound_semantics,
        "bound_registry_sha256": _bound_registry_sha256(bound_semantics),
    }


class ExactEnumerationScenarioProofArtifact(FrozenContractModel):
    """Raw finite law from which the exact verifier recomputes every bound."""

    schema_id: Literal[
        "d2t_rna.exact_enumeration_scenario_proof_artifact"
    ] = "d2t_rna.exact_enumeration_scenario_proof_artifact"
    schema_version: Literal["1.0"] = "1.0"
    coverage_bound_method: Literal[
        CoverageBoundMethod.EXACT_ENUMERATION
    ] = CoverageBoundMethod.EXACT_ENUMERATION
    scenario_id: RegisteredId
    law_hash: Sha256Hex
    hypothesis_region: RegistryRef
    coverage_core_membership: RegistryRef
    conditioning_sigma_field_hash: Sha256Hex
    outcomes: tuple[ExactScenarioOutcome, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_OUTCOMES,
    )
    risk_upper_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    coverage_lower_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    probability_mass_accounted: Rational
    omitted_mass_bound: Rational
    numerical_error_bound: Rational
    bound_semantics: tuple[BoundSemanticDefinition, ...] = Field(
        min_length=2,
        max_length=2 * MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    bound_registry_sha256: Sha256Hex

    @model_validator(mode="after")
    def replay_exact_enumeration(
        self,
    ) -> ExactEnumerationScenarioProofArtifact:
        derived = _derive_exact_enumeration(
            scenario_id=self.scenario_id,
            outcomes=self.outcomes,
        )
        for field_name, expected in derived.items():
            if getattr(self, field_name) != expected:
                raise ValueError(
                    f"exact enumeration {field_name} does not replay"
                )
        return self


def _risk_bounds_from_certificate(
    certificate: RiskCertificate,
) -> tuple[NamedBound, ...]:
    return (
        NamedBound(
            bound_id="h0-wrong-reject",
            value=certificate.h0_wrong_reject_bound,
        ),
        NamedBound(
            bound_id="h1-wrong-certify",
            value=certificate.h1_wrong_certify_bound,
        ),
        NamedBound(
            bound_id="indifference-decisive-output",
            value=certificate.indifference_decisive_output_bound,
        ),
    )


def _strict_validated_risk_certificate(
    certificate: RiskCertificate,
) -> RiskCertificate:
    if type(certificate) is not RiskCertificate:
        raise TypeError(
            "Monte Carlo evidence requires exactly RiskCertificate"
        )
    checked = strict_revalidate_contract_model(certificate)
    for field_name in (
        "h0_wrong_reject_bound",
        "h1_wrong_certify_bound",
        "indifference_decisive_output_bound",
        "confidence_set_uniform_coverage",
        "conditional_bound",
    ):
        _probability(
            getattr(checked, field_name),
            label=f"risk certificate {field_name}",
        )
    if checked.unconditional_bound is not None:
        _probability(
            checked.unconditional_bound,
            label="risk certificate unconditional_bound",
        )
    if checked.prospective_unconditional_bound is not None:
        raise ValueError(
            "v1 risk certificate cannot carry a prospective unconditional "
            "bound"
        )
    validate_uniform_indifference_control(
        coverage=checked.confidence_set_uniform_coverage,
        decisive_bound=checked.indifference_decisive_output_bound,
    )
    conditional = _probability(
        checked.conditional_bound,
        label="risk certificate conditional_bound",
    )
    for field_name in (
        "h0_wrong_reject_bound",
        "h1_wrong_certify_bound",
        "indifference_decisive_output_bound",
    ):
        if (
            _probability(
                getattr(checked, field_name),
                label=f"risk certificate {field_name}",
            )
            > conditional
        ):
            raise ValueError(
                f"risk certificate {field_name} exceeds conditional bound"
            )
    return checked


class _MethodEvidenceScenarioProofArtifact(FrozenContractModel):
    """Typed nonformal record awaiting a method-specific replay verifier."""

    scenario_id: RegisteredId
    law_hash: Sha256Hex
    hypothesis_region: RegistryRef
    coverage_core_membership: RegistryRef
    conditioning_sigma_field_hash: Sha256Hex
    risk_upper_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    coverage_lower_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    probability_mass_accounted: Rational
    omitted_mass_bound: Rational
    numerical_error_bound: Rational
    method_evidence_sha256: Sha256Hex
    bound_semantics: tuple[BoundSemanticDefinition, ...] = Field(
        min_length=2,
        max_length=2 * MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    bound_registry_sha256: Sha256Hex

    @model_validator(mode="before")
    @classmethod
    def bind_full_bound_semantics(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if (
            "bound_semantics" in payload
            and "bound_registry_sha256" in payload
        ):
            return payload
        risk_bounds = payload.get("risk_upper_bounds")
        coverage_bounds = payload.get("coverage_lower_bounds")
        if (
            type(risk_bounds) is not tuple
            or type(coverage_bounds) is not tuple
            or any(type(item) is not NamedBound for item in risk_bounds)
            or any(type(item) is not NamedBound for item in coverage_bounds)
        ):
            return payload
        method = payload.get(
            "coverage_bound_method",
            cls.model_fields["coverage_bound_method"].default,
        )
        if type(method) is not CoverageBoundMethod:
            return payload
        semantics = _nonformal_atom_bound_semantics(
            risk_bound_ids=tuple(item.bound_id for item in risk_bounds),
            coverage_bound_ids=tuple(
                item.bound_id for item in coverage_bounds
            ),
            method=method,
        )
        payload.setdefault("bound_semantics", semantics)
        payload.setdefault(
            "bound_registry_sha256",
            _bound_registry_sha256(semantics),
        )
        return payload

    @model_validator(mode="after")
    def validate_nonformal_record(
        self,
    ) -> _MethodEvidenceScenarioProofArtifact:
        risk_ids = _validate_bound_set(
            self.risk_upper_bounds,
            label="risk bounds",
        )
        coverage_ids = _validate_bound_set(
            self.coverage_lower_bounds,
            label="coverage bounds",
        )
        semantics = _validate_bound_semantics(
            self.bound_semantics,
            risk_bound_ids=risk_ids,
            coverage_bound_ids=coverage_ids,
        )
        if any(
            item.coverage_bound_method is not self.coverage_bound_method
            for item in semantics
        ):
            raise ValueError(
                "bound semantic method does not match the proof method"
            )
        if self.bound_registry_sha256 != _bound_registry_sha256(semantics):
            raise ValueError("bound semantic registry hash does not replay")
        accounted = _probability(
            self.probability_mass_accounted,
            label="probability mass accounted",
        )
        omitted = _probability(
            self.omitted_mass_bound,
            label="omitted mass bound",
        )
        _probability(
            self.numerical_error_bound,
            label="numerical error bound",
        )
        if accounted + omitted < 1:
            raise ValueError(
                "probability mass accounted plus omitted mass must cover one"
            )
        return self


class VerifiedIntervalScenarioProofArtifact(
    _MethodEvidenceScenarioProofArtifact
):
    """Typed interval evidence; formal replay is intentionally unavailable."""

    schema_id: Literal[
        "d2t_rna.verified_interval_scenario_proof_artifact"
    ] = "d2t_rna.verified_interval_scenario_proof_artifact"
    schema_version: Literal["1.0"] = "1.0"
    coverage_bound_method: Literal[
        CoverageBoundMethod.VERIFIED_INTERVAL
    ] = CoverageBoundMethod.VERIFIED_INTERVAL


class CertifiedTruncationScenarioProofArtifact(
    _MethodEvidenceScenarioProofArtifact
):
    """Typed truncation evidence; formal replay is intentionally unavailable."""

    schema_id: Literal[
        "d2t_rna.certified_truncation_scenario_proof_artifact"
    ] = "d2t_rna.certified_truncation_scenario_proof_artifact"
    schema_version: Literal["1.0"] = "1.0"
    coverage_bound_method: Literal[
        CoverageBoundMethod.CERTIFIED_TRUNCATION
    ] = CoverageBoundMethod.CERTIFIED_TRUNCATION


class MonteCarloScenarioProofArtifact(_MethodEvidenceScenarioProofArtifact):
    """Typed Monte Carlo evidence that can never authorize a formal claim."""

    schema_id: Literal[
        "d2t_rna.monte_carlo_scenario_proof_artifact"
    ] = "d2t_rna.monte_carlo_scenario_proof_artifact"
    schema_version: Literal["1.0"] = "1.0"
    coverage_bound_method: Literal[
        CoverageBoundMethod.MONTE_CARLO_ONLY
    ] = CoverageBoundMethod.MONTE_CARLO_ONLY
    risk_certificate: RiskCertificate
    risk_certificate_sha256: Sha256Hex

    @model_validator(mode="before")
    @classmethod
    def bind_risk_certificate_hash(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        certificate = payload.get("risk_certificate")
        if (
            "risk_certificate_sha256" not in payload
            and type(certificate) is RiskCertificate
        ):
            payload["risk_certificate_sha256"] = canonical_sha256(certificate)
        return payload

    @model_validator(mode="after")
    def validate_embedded_risk_certificate(
        self,
    ) -> MonteCarloScenarioProofArtifact:
        certificate = _strict_validated_risk_certificate(
            self.risk_certificate
        )
        if self.risk_certificate_sha256 != canonical_sha256(certificate):
            raise ValueError("Monte Carlo risk-certificate hash does not replay")
        if (
            self.conditioning_sigma_field_hash
            != certificate.conditioning_sigma_field_hash
        ):
            raise ValueError(
                "Monte Carlo conditioning field differs from risk certificate"
            )
        expected_risk = _risk_bounds_from_certificate(certificate)
        if self.risk_upper_bounds != expected_risk:
            raise ValueError(
                "Monte Carlo risk bounds must replay from the embedded "
                "RiskCertificate"
            )
        return self


REGISTERED_EXACT_CONFIDENCE_RULE_ID: Literal[
    "confidence.task5.all-registered-parameters.v1"
] = "confidence.task5.all-registered-parameters.v1"


def _registered_all_parameter_confidence_rule(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[tuple[str, ...], None]:
    """Frozen production rule for the registered three-point micro-universe."""

    return ("omega.h0", "omega.h1", "omega.indifference"), None


REGISTERED_EXACT_CONFIDENCE_RULE_IMPLEMENTATION_SHA256: Sha256Hex = (
    confidence_rule_implementation_sha256(
        _registered_all_parameter_confidence_rule
    )
)


def build_registered_exact_confidence_procedure(
    family: ExactParameterFamily,
) -> ConfidenceProcedureSpec:
    """Bind the fixed production callback to one exact parameter universe."""

    if type(family) is not ExactParameterFamily:
        raise TypeError("family must be exactly ExactParameterFamily")
    checked_family = strict_revalidate_contract_model(family)
    expected_ids = ("omega.h0", "omega.h1", "omega.indifference")
    if tuple(point.parameter_id for point in checked_family.points) != expected_ids:
        raise ValueError(
            "registered Task 5 confidence procedure requires the frozen "
            "three-point parameter universe"
        )
    return ConfidenceProcedureSpec(
        procedure_id=REGISTERED_EXACT_CONFIDENCE_RULE_ID,
        implementation_hash=(
            REGISTERED_EXACT_CONFIDENCE_RULE_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=checked_family.parameter_universe_hash,
    )


def evaluate_registered_exact_synthetic_coverage_report(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    decision_rule: ExactDecisionRuleSpec,
) -> tuple[ConfidenceProcedureSpec, ExactSyntheticCoverageReport]:
    """Run Task 4 exact coverage using only the fixed production registry."""

    procedure = build_registered_exact_confidence_procedure(family)
    rule = _resolve_registered_confidence_rule(
        registry_id=REGISTERED_EXACT_CONFIDENCE_RULE_ID,
        procedure=procedure,
        family=family,
    )
    report = evaluate_exact_synthetic_risk_coverage(
        support=support,
        family=family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=rule,
        engine_code_hash=coverage_module_sha256(),
    )
    return procedure, report


def _registered_confidence_rule_registry_root_sha256() -> str:
    return canonical_sha256(
        {
            "schema": "d2t_rna.task5_confidence_rule_registry.v1",
            "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
            "entries": (
                {
                    "rule_id": REGISTERED_EXACT_CONFIDENCE_RULE_ID,
                    "event_semantics": (
                        "Return the full fixed three-point registered "
                        "parameter universe for every exact outcome."
                    ),
                    "implementation_sha256": (
                        REGISTERED_EXACT_CONFIDENCE_RULE_IMPLEMENTATION_SHA256
                    ),
                    "expected_parameter_ids": (
                        "omega.h0",
                        "omega.h1",
                        "omega.indifference",
                    ),
                },
            ),
        }
    )


def _resolve_registered_confidence_rule(
    *,
    registry_id: str,
    procedure: ConfidenceProcedureSpec,
    family: ExactParameterFamily,
) -> FunctionType:
    if type(registry_id) is not str:
        raise TypeError("confidence-rule registry ID must be exactly str")
    if registry_id != REGISTERED_EXACT_CONFIDENCE_RULE_ID:
        raise ValueError("confidence-rule registry ID is not registered")
    if type(procedure) is not ConfidenceProcedureSpec:
        raise TypeError(
            "confidence_procedure must be exactly ConfidenceProcedureSpec"
        )
    checked_procedure = strict_revalidate_contract_model(procedure)
    checked_family = strict_revalidate_contract_model(family)
    expected_ids = ("omega.h0", "omega.h1", "omega.indifference")
    observed_ids = tuple(point.parameter_id for point in checked_family.points)
    if observed_ids != expected_ids:
        raise ValueError(
            "registered Task 5 confidence rule requires the frozen "
            "three-point parameter universe"
        )
    expected_hash = REGISTERED_EXACT_CONFIDENCE_RULE_IMPLEMENTATION_SHA256
    if (
        checked_procedure.procedure_id
        != REGISTERED_EXACT_CONFIDENCE_RULE_ID
        or checked_procedure.implementation_hash != expected_hash
        or checked_procedure.parameter_universe_hash
        != checked_family.parameter_universe_hash
    ):
        raise ValueError(
            "confidence procedure does not bind the fixed production registry"
        )
    return _registered_all_parameter_confidence_rule


def _exact_synthetic_bound_semantics(
) -> tuple[BoundSemanticDefinition, ...]:
    definitions = (
        BoundSemanticDefinition(
            bound_id="confidence-set-uniform-coverage",
            bound_kind=BoundKind.COVERAGE_LOWER_BOUND,
            event_semantics=(
                "For each registered synthetic-known-channel parameter, the "
                "confidence set contains that true parameter."
            ),
            estimand_definition=(
                "The minimum, over the complete registered finite parameter "
                "universe, of exact confidence-set coverage probability."
            ),
            estimator_definition=(
                "Exact rational exhaustive enumeration by "
                "replay_exact_synthetic_coverage_report."
            ),
            coverage_bound_method=CoverageBoundMethod.EXACT_ENUMERATION,
        ),
        BoundSemanticDefinition(
            bound_id="h0-wrong-reject",
            bound_kind=BoundKind.RISK_UPPER_BOUND,
            event_semantics=(
                "Under a registered H0 parameter, the frozen "
                "confidence-subset decision rule outputs REJECT."
            ),
            estimand_definition=(
                "Maximum exact wrong-REJECT probability over every "
                "registered H0 parameter."
            ),
            estimator_definition=(
                "Exact rational exhaustive enumeration by "
                "replay_exact_synthetic_coverage_report."
            ),
            coverage_bound_method=CoverageBoundMethod.EXACT_ENUMERATION,
        ),
        BoundSemanticDefinition(
            bound_id="h1-wrong-certify",
            bound_kind=BoundKind.RISK_UPPER_BOUND,
            event_semantics=(
                "Under a registered H1 parameter, the frozen "
                "confidence-subset decision rule outputs CERTIFY."
            ),
            estimand_definition=(
                "Maximum exact wrong-CERTIFY probability over every "
                "registered H1 parameter."
            ),
            estimator_definition=(
                "Exact rational exhaustive enumeration by "
                "replay_exact_synthetic_coverage_report."
            ),
            coverage_bound_method=CoverageBoundMethod.EXACT_ENUMERATION,
        ),
        BoundSemanticDefinition(
            bound_id="indifference-decisive-output",
            bound_kind=BoundKind.RISK_UPPER_BOUND,
            event_semantics=(
                "Under a registered indifference parameter, the frozen "
                "confidence-subset decision rule emits CERTIFY or REJECT."
            ),
            estimand_definition=(
                "Maximum exact decisive-output probability over every "
                "registered indifference parameter."
            ),
            estimator_definition=(
                "Exact rational exhaustive enumeration by "
                "replay_exact_synthetic_coverage_report."
            ),
            coverage_bound_method=CoverageBoundMethod.EXACT_ENUMERATION,
        ),
    )
    return _validate_bound_semantics(definitions)


def _exact_synthetic_payload_from_validated_inputs(
    *,
    scenario_id: str,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    confidence_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    confidence_rule_registry_id: str,
    report: ExactSyntheticCoverageReport,
    replay_credential: ExactSyntheticCoverageReplayCredential,
) -> dict[str, object]:
    _resolve_registered_confidence_rule(
        registry_id=confidence_rule_registry_id,
        procedure=confidence_procedure,
        family=family,
    )
    report_hash = canonical_sha256(report)
    expected_bindings = {
        "support_spec_hash": canonical_sha256(support),
        "parameter_universe_hash": family.parameter_universe_hash,
        "confidence_procedure_hash": canonical_sha256(confidence_procedure),
        "decision_rule_hash": canonical_sha256(decision_rule),
    }
    for field_name, expected in expected_bindings.items():
        if getattr(report, field_name) != expected:
            raise ValueError(
                f"Task 4 report {field_name} does not bind the raw input"
            )
    if (
        replay_credential.report_hash != report_hash
        or replay_credential.evaluation_input_bundle_hash
        != report.evaluation_input_bundle_hash
        or replay_credential.evaluation_transcript_hash
        != report.evaluation_transcript_hash
        or replay_credential.engine_code_hash != report.engine_code_hash
        or replay_credential.verifier_configuration_hash
        != report.verifier_configuration_hash
    ):
        raise ValueError(
            "Task 4 replay credential does not bind the embedded report"
        )
    risk_bounds = (
        NamedBound(
            bound_id="h0-wrong-reject",
            value=report.h0_wrong_reject_bound,
        ),
        NamedBound(
            bound_id="h1-wrong-certify",
            value=report.h1_wrong_certify_bound,
        ),
        NamedBound(
            bound_id="indifference-decisive-output",
            value=report.indifference_decisive_output_bound,
        ),
    )
    coverage_bounds = (
        NamedBound(
            bound_id="confidence-set-uniform-coverage",
            value=report.confidence_set_uniform_coverage,
        ),
    )
    semantics = _exact_synthetic_bound_semantics()
    _validate_bound_semantics(
        semantics,
        risk_bound_ids=tuple(item.bound_id for item in risk_bounds),
        coverage_bound_ids=tuple(item.bound_id for item in coverage_bounds),
    )
    support_json = canonical_json_bytes(support).decode("utf-8")
    family_json = canonical_json_bytes(family).decode("utf-8")
    confidence_procedure_json = canonical_json_bytes(
        confidence_procedure
    ).decode("utf-8")
    decision_rule_json = canonical_json_bytes(decision_rule).decode("utf-8")
    report_json = canonical_json_bytes(report).decode("utf-8")
    replay_credential_json = canonical_json_bytes(replay_credential).decode(
        "utf-8"
    )
    return {
        "scenario_id": scenario_id,
        "support_json": support_json,
        "support_sha256": hashlib.sha256(
            support_json.encode("utf-8")
        ).hexdigest(),
        "family_json": family_json,
        "family_sha256": hashlib.sha256(
            family_json.encode("utf-8")
        ).hexdigest(),
        "confidence_procedure_json": confidence_procedure_json,
        "confidence_procedure_sha256": hashlib.sha256(
            confidence_procedure_json.encode("utf-8")
        ).hexdigest(),
        "decision_rule_json": decision_rule_json,
        "decision_rule_sha256": hashlib.sha256(
            decision_rule_json.encode("utf-8")
        ).hexdigest(),
        "confidence_rule_registry_id": confidence_rule_registry_id,
        "confidence_rule_registry_root_sha256": (
            _registered_confidence_rule_registry_root_sha256()
        ),
        "exact_synthetic_coverage_report_json": report_json,
        "exact_replay_credential_json": replay_credential_json,
        "exact_replay_credential_sha256": hashlib.sha256(
            replay_credential_json.encode("utf-8")
        ).hexdigest(),
        "law_hash": report.sampling_law_manifest_hash,
        "hypothesis_region": RegistryRef(
            registry_id="hypothesis.partition.task4.exact-synthetic.v1",
            registry_hash=report.hypothesis_partition_hash,
        ),
        "coverage_core_membership": RegistryRef(
            registry_id="coverage.core.task4.parameter-universe.v1",
            registry_hash=report.parameter_universe_hash,
        ),
        "conditioning_sigma_field_hash": (
            family.probability_space.conditioning_sigma_field_hash
        ),
        "risk_upper_bounds": risk_bounds,
        "coverage_lower_bounds": coverage_bounds,
        "probability_mass_accounted": report.probability_mass_accounted,
        "omitted_mass_bound": report.omitted_mass_bound,
        "numerical_error_bound": report.numerical_error_bound,
        "bound_semantics": semantics,
        "bound_registry_sha256": _bound_registry_sha256(semantics),
        "exact_synthetic_coverage_report_sha256": report_hash,
        "task4_mathematical_statement_verified": (
            report.mathematical_statement_verified
        ),
    }


def _derive_exact_synthetic_artifact(
    *,
    scenario_id: str,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    confidence_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    confidence_rule_registry_id: str,
    report: ExactSyntheticCoverageReport,
) -> dict[str, object]:
    if type(support) is not ExactSupportSpec:
        raise TypeError("support must be exactly ExactSupportSpec")
    if type(family) is not ExactParameterFamily:
        raise TypeError("family must be exactly ExactParameterFamily")
    if type(confidence_procedure) is not ConfidenceProcedureSpec:
        raise TypeError(
            "confidence_procedure must be exactly ConfidenceProcedureSpec"
        )
    if type(decision_rule) is not ExactDecisionRuleSpec:
        raise TypeError("decision_rule must be exactly ExactDecisionRuleSpec")
    if type(report) is not ExactSyntheticCoverageReport:
        raise TypeError(
            "report must be exactly ExactSyntheticCoverageReport"
        )
    checked_support = strict_revalidate_contract_model(support)
    checked_family = strict_revalidate_contract_model(family)
    checked_procedure = strict_revalidate_contract_model(
        confidence_procedure
    )
    checked_decision_rule = strict_revalidate_contract_model(decision_rule)
    checked_report = strict_revalidate_contract_model(report)
    rule = _resolve_registered_confidence_rule(
        registry_id=confidence_rule_registry_id,
        procedure=checked_procedure,
        family=checked_family,
    )
    replay_credential = replay_exact_synthetic_coverage_report(
        support=checked_support,
        family=checked_family,
        confidence_procedure=checked_procedure,
        decision_rule=checked_decision_rule,
        confidence_rule=rule,
        engine_code_hash=coverage_module_sha256(),
        report=checked_report,
    )
    return _exact_synthetic_payload_from_validated_inputs(
        scenario_id=scenario_id,
        support=checked_support,
        family=checked_family,
        confidence_procedure=checked_procedure,
        decision_rule=checked_decision_rule,
        confidence_rule_registry_id=confidence_rule_registry_id,
        report=checked_report,
        replay_credential=replay_credential,
    )


def _validate_canonical_exact_raw_json(
    raw: str,
    *,
    label: str,
) -> None:
    """Apply bounded syntax/canonical checks before any Task 4 model parse."""

    try:
        checked_text = validate_contract_json_syntax(raw)
        decoded = json.loads(checked_text)
    except RecursionError as exc:
        raise ValueError(
            f"{label} exceeds the registered raw JSON depth cap"
        ) from exc
    stack: list[tuple[object, int]] = [(decoded, 0)]
    node_count = 0
    while stack:
        value, depth = stack.pop()
        node_count += 1
        if node_count > MAX_EXACT_RAW_JSON_NODES:
            raise ValueError(
                f"{label} exceeds the registered raw JSON node cap"
            )
        if depth > MAX_EXACT_RAW_JSON_DEPTH:
            raise ValueError(
                f"{label} exceeds the registered raw JSON depth cap"
            )
        if type(value) is int:
            if abs(value).bit_length() > MAX_RATIONAL_COMPONENT_BITS:
                raise ValueError(
                    f"{label} contains an integer exceeding the registered "
                    f"{MAX_RATIONAL_COMPONENT_BITS}-bit cap"
                )
        elif type(value) is list:
            stack.extend((item, depth + 1) for item in value)
        elif type(value) is dict:
            stack.extend((item, depth + 1) for item in value.values())
    try:
        canonical = canonical_json_bytes(decoded).decode("utf-8")
    except RecursionError as exc:
        raise ValueError(
            f"{label} exceeds the registered raw JSON depth cap"
        ) from exc
    if canonical != checked_text:
        raise ValueError(f"{label} must be exact canonical JSON")


class ExactSyntheticScenarioProofArtifact(FrozenContractModel):
    """Task 4 report plus raw inputs, replayed by fixed production code."""

    schema_id: Literal[
        "d2t_rna.exact_synthetic_scenario_proof_artifact"
    ] = "d2t_rna.exact_synthetic_scenario_proof_artifact"
    schema_version: Literal["2.0"] = "2.0"
    coverage_bound_method: Literal[
        CoverageBoundMethod.EXACT_ENUMERATION
    ] = CoverageBoundMethod.EXACT_ENUMERATION
    scenario_id: RegisteredId
    support_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_SUPPORT_JSON_CHARS,
    )
    support_sha256: Sha256Hex
    family_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_FAMILY_JSON_CHARS,
    )
    family_sha256: Sha256Hex
    confidence_procedure_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_PROCEDURE_JSON_CHARS,
    )
    confidence_procedure_sha256: Sha256Hex
    decision_rule_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_DECISION_RULE_JSON_CHARS,
    )
    decision_rule_sha256: Sha256Hex
    confidence_rule_registry_id: Literal[
        "confidence.task5.all-registered-parameters.v1"
    ]
    confidence_rule_registry_root_sha256: Sha256Hex
    exact_synthetic_coverage_report_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_REPORT_JSON_CHARS,
    )
    exact_replay_credential_json: StrictStr = Field(
        min_length=2,
        max_length=MAX_EXACT_REPLAY_CREDENTIAL_JSON_CHARS,
    )
    exact_replay_credential_sha256: Sha256Hex
    exact_synthetic_coverage_report_sha256: Sha256Hex
    task4_mathematical_statement_verified: StrictBool
    law_hash: Sha256Hex
    hypothesis_region: RegistryRef
    coverage_core_membership: RegistryRef
    conditioning_sigma_field_hash: Sha256Hex
    risk_upper_bounds: tuple[NamedBound, ...] = Field(
        min_length=3,
        max_length=3,
    )
    coverage_lower_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=1,
    )
    probability_mass_accounted: Rational
    omitted_mass_bound: Rational
    numerical_error_bound: Rational
    bound_semantics: tuple[BoundSemanticDefinition, ...] = Field(
        min_length=4,
        max_length=4,
    )
    bound_registry_sha256: Sha256Hex
    formal_scientific_certificate_authorized: Literal[False] = False
    prospective_claim_authorized: Literal[False] = False
    new_library_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def bind_raw_json_hashes(
        self,
    ) -> ExactSyntheticScenarioProofArtifact:
        for field_name in (
            "support_json",
            "family_json",
            "confidence_procedure_json",
            "decision_rule_json",
            "exact_synthetic_coverage_report_json",
            "exact_replay_credential_json",
        ):
            raw = getattr(self, field_name)
            _validate_canonical_exact_raw_json(raw, label=field_name)
        raw_hashes = {
            "support_sha256": hashlib.sha256(
                self.support_json.encode("utf-8")
            ).hexdigest(),
            "family_sha256": hashlib.sha256(
                self.family_json.encode("utf-8")
            ).hexdigest(),
            "confidence_procedure_sha256": hashlib.sha256(
                self.confidence_procedure_json.encode("utf-8")
            ).hexdigest(),
            "decision_rule_sha256": hashlib.sha256(
                self.decision_rule_json.encode("utf-8")
            ).hexdigest(),
            "exact_synthetic_coverage_report_sha256": hashlib.sha256(
                self.exact_synthetic_coverage_report_json.encode("utf-8")
            ).hexdigest(),
            "exact_replay_credential_sha256": hashlib.sha256(
                self.exact_replay_credential_json.encode("utf-8")
            ).hexdigest(),
        }
        for field_name, expected in raw_hashes.items():
            if getattr(self, field_name) != expected:
                raise ValueError(
                    "exact synthetic raw JSON "
                    f"{field_name} does not match bytes"
                )
        return self


ScenarioProofArtifact: TypeAlias = Annotated[
    ExactSyntheticScenarioProofArtifact
    | ExactEnumerationScenarioProofArtifact
    | VerifiedIntervalScenarioProofArtifact
    | CertifiedTruncationScenarioProofArtifact
    | MonteCarloScenarioProofArtifact,
    Field(discriminator="schema_id"),
]

_SCENARIO_PROOF_ARTIFACT_TYPES = (
    ExactSyntheticScenarioProofArtifact,
    ExactEnumerationScenarioProofArtifact,
    VerifiedIntervalScenarioProofArtifact,
    CertifiedTruncationScenarioProofArtifact,
    MonteCarloScenarioProofArtifact,
)


def build_exact_enumeration_artifact(
    *,
    scenario_id: str,
    hypothesis_region: RegistryRef,
    coverage_core_membership: RegistryRef,
    conditioning_sigma_field_hash: str,
    outcomes: Sequence[ExactScenarioOutcome],
) -> ExactEnumerationScenarioProofArtifact:
    """Construct an exact artifact solely from its canonical outcome atoms."""

    if type(hypothesis_region) is not RegistryRef:
        raise TypeError("hypothesis_region must be exactly RegistryRef")
    if type(coverage_core_membership) is not RegistryRef:
        raise TypeError(
            "coverage_core_membership must be exactly RegistryRef"
        )
    outcome_tuple = tuple(outcomes)
    derived = _derive_exact_enumeration(
        scenario_id=scenario_id,
        outcomes=outcome_tuple,
    )
    return ExactEnumerationScenarioProofArtifact.model_validate(
        {
            "scenario_id": scenario_id,
            "hypothesis_region": strict_revalidate_contract_model(
                hypothesis_region
            ),
            "coverage_core_membership": strict_revalidate_contract_model(
                coverage_core_membership
            ),
            "conditioning_sigma_field_hash": conditioning_sigma_field_hash,
            **derived,
        },
        strict=True,
    )


def build_exact_synthetic_scenario_artifact(
    *,
    scenario_id: str,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    confidence_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    confidence_rule_registry_id: str,
    report: ExactSyntheticCoverageReport,
) -> ExactSyntheticScenarioProofArtifact:
    """Build the only exact artifact eligible for a formal Task 5 label."""

    return ExactSyntheticScenarioProofArtifact.model_validate(
        _derive_exact_synthetic_artifact(
            scenario_id=scenario_id,
            support=support,
            family=family,
            confidence_procedure=confidence_procedure,
            decision_rule=decision_rule,
            confidence_rule_registry_id=confidence_rule_registry_id,
            report=report,
        ),
        strict=True,
    )


def _fresh_replay_exact_synthetic_artifact(
    artifact: ExactSyntheticScenarioProofArtifact,
) -> ExactSyntheticCoverageReport:
    support = parse_contract_json(ExactSupportSpec, artifact.support_json)
    family = parse_contract_json(ExactParameterFamily, artifact.family_json)
    procedure = parse_contract_json(
        ConfidenceProcedureSpec,
        artifact.confidence_procedure_json,
    )
    decision_rule = parse_contract_json(
        ExactDecisionRuleSpec,
        artifact.decision_rule_json,
    )
    report = parse_contract_json(
        ExactSyntheticCoverageReport,
        artifact.exact_synthetic_coverage_report_json,
    )
    embedded_credential = parse_contract_json(
        ExactSyntheticCoverageReplayCredential,
        artifact.exact_replay_credential_json,
    )
    rule = _resolve_registered_confidence_rule(
        registry_id=artifact.confidence_rule_registry_id,
        procedure=procedure,
        family=family,
    )
    fresh_credential = replay_exact_synthetic_coverage_report(
        support=support,
        family=family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=rule,
        engine_code_hash=coverage_module_sha256(),
        report=report,
    )
    if fresh_credential != embedded_credential:
        raise ValueError(
            "exact synthetic replay credential does not match fresh "
            "Task 4 replay"
        )
    expected = _exact_synthetic_payload_from_validated_inputs(
        scenario_id=artifact.scenario_id,
        support=support,
        family=family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule_registry_id=artifact.confidence_rule_registry_id,
        report=report,
        replay_credential=fresh_credential,
    )
    for field_name, expected_value in expected.items():
        if getattr(artifact, field_name) != expected_value:
            raise ValueError(
                "exact synthetic scenario artifact "
                f"{field_name} does not replay from raw JSON"
            )
    return report


def _strict_artifact(
    artifact: ScenarioProofArtifact,
) -> ScenarioProofArtifact:
    if type(artifact) not in _SCENARIO_PROOF_ARTIFACT_TYPES:
        raise TypeError(
            "proof artifact must be exactly one registered "
            "ScenarioProofArtifact"
        )
    return strict_revalidate_contract_model(artifact)


def _validate_scenario_proof(proof: ScenarioProof) -> ScenarioProof:
    if type(proof) is not ScenarioProof:
        raise TypeError("scenario proof must be exactly ScenarioProof")
    checked = strict_revalidate_contract_model(proof)
    _validate_bound_set(checked.risk_upper_bounds, label="risk bounds")
    _validate_bound_set(
        checked.coverage_lower_bounds,
        label="coverage bounds",
    )
    accounted = _probability(
        checked.probability_mass_accounted,
        label="probability mass accounted",
    )
    omitted = _probability(
        checked.omitted_mass_bound,
        label="omitted mass bound",
    )
    _probability(
        checked.numerical_error_bound,
        label="numerical error bound",
    )
    if accounted + omitted < 1:
        raise ValueError(
            "probability mass accounted plus omitted mass must cover one"
        )
    return checked


def _replay_proof_against_artifact(
    proof: ScenarioProof,
    artifact: ScenarioProofArtifact,
    *,
    fresh_exact_replay: bool = True,
) -> tuple[
    ScenarioProof,
    ScenarioProofArtifact,
    ScenarioCoverageDisposition,
    bool,
]:
    checked_proof = _validate_scenario_proof(proof)
    checked_artifact = _strict_artifact(artifact)
    replayed_exact_report: ExactSyntheticCoverageReport | None = None
    if (
        type(checked_artifact) is ExactSyntheticScenarioProofArtifact
        and fresh_exact_replay
    ):
        replayed_exact_report = _fresh_replay_exact_synthetic_artifact(
            checked_artifact
        )

    common_fields = (
        "scenario_id",
        "law_hash",
        "hypothesis_region",
        "coverage_core_membership",
        "conditioning_sigma_field_hash",
        "coverage_bound_method",
        "probability_mass_accounted",
        "omitted_mass_bound",
        "numerical_error_bound",
    )
    for field_name in common_fields:
        if getattr(checked_proof, field_name) != getattr(
            checked_artifact,
            field_name,
        ):
            raise ValueError(
                f"scenario proof {field_name} does not replay from artifact"
            )
    if (
        checked_proof.risk_upper_bounds
        != checked_artifact.risk_upper_bounds
    ):
        raise ValueError("scenario proof risk bounds do not replay from artifact")
    if (
        checked_proof.coverage_lower_bounds
        != checked_artifact.coverage_lower_bounds
    ):
        raise ValueError(
            "scenario proof coverage bounds do not replay from artifact"
        )
    expected_artifact_hash = canonical_sha256(checked_artifact)
    if checked_proof.proof_artifact_hash != expected_artifact_hash:
        raise ValueError("scenario proof artifact hash does not replay")

    if type(checked_artifact) is ExactSyntheticScenarioProofArtifact:
        if fresh_exact_replay and replayed_exact_report is None:
            raise RuntimeError("exact synthetic report replay was not executed")
        formal = (
            replayed_exact_report.mathematical_statement_verified
            if replayed_exact_report is not None
            else checked_artifact.task4_mathematical_statement_verified
        )
        disposition = (
            ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
            if formal
            else ScenarioCoverageDisposition
            .REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
        )
    elif type(checked_artifact) is ExactEnumerationScenarioProofArtifact:
        disposition = (
            ScenarioCoverageDisposition
            .REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
        )
        formal = False
    elif type(checked_artifact) is MonteCarloScenarioProofArtifact:
        disposition = (
            ScenarioCoverageDisposition.RISK_CERTIFIED_COVERAGE_PREDICTED
        )
        formal = False
    else:
        if checked_proof.formal_guarantee:
            raise ValueError(
                f"formal replay unavailable for "
                f"{checked_artifact.coverage_bound_method.value}"
            )
        disposition = (
            ScenarioCoverageDisposition
            .REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
        )
        formal = False
    if checked_proof.formal_guarantee is not formal:
        checked_proof = strict_revalidate_contract_model(
            checked_proof.model_copy(
                update={"formal_guarantee": formal},
            )
        )
    return checked_proof, checked_artifact, disposition, formal


SCENARIO_PROOF_VERIFIER_CONFIGURATION_SHA256: Sha256Hex = canonical_sha256(
    {
        "verifier": "d2t_rna.evaluation.scenario",
        "version": "2.0",
        "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
        "formal_source": (
            "TASK4_EXACT_SYNTHETIC_RAW_INPUT_FRESH_REPLAY_ONLY"
        ),
        "nonformal_methods_without_production_replay": (
            "GENERIC_CALLER_ATOMS",
            CoverageBoundMethod.VERIFIED_INTERVAL,
            CoverageBoundMethod.CERTIFIED_TRUNCATION,
            CoverageBoundMethod.MONTE_CARLO_ONLY,
        ),
        "aggregation": (
            "FINITE_MAX_RISK_MIN_COVERAGE_CAPPED_SUM_UNION_BOUND"
        ),
    }
)


def scenario_proof_verifier_code_sha256() -> str:
    """Hash the source file for audit only; this is not the runtime gate."""

    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _code_constant_descriptor(value: object) -> object:
    if isinstance(value, CodeType):
        return _live_code_descriptor(value)
    if value is None or type(value) in (str, bytes, bool, int):
        return (
            {"bytes_sha256": hashlib.sha256(value).hexdigest()}
            if type(value) is bytes
            else value
        )
    if type(value) is tuple:
        return tuple(_code_constant_descriptor(item) for item in value)
    raise RuntimeError(
        "scenario verifier code contains an unregistered constant type: "
        f"{type(value).__name__}"
    )


def _live_code_descriptor(code: CodeType) -> dict[str, object]:
    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "bytecode_sha256": hashlib.sha256(code.co_code).hexdigest(),
        "constants": tuple(
            _code_constant_descriptor(item) for item in code.co_consts
        ),
        "names": code.co_names,
        "varnames": code.co_varnames,
        "freevars": code.co_freevars,
        "cellvars": code.co_cellvars,
    }


def _live_function_descriptor(
    name: str,
    function: FunctionType,
) -> dict[str, object]:
    if function.__closure__:
        raise RuntimeError(
            f"scenario verifier function {name} unexpectedly has a closure"
        )
    if function.__dict__:
        raise RuntimeError(
            f"scenario verifier function {name} has runtime attributes"
        )
    return {
        "module": function.__module__,
        "qualname": function.__qualname__,
        "code": _live_code_descriptor(function.__code__),
        "defaults": _code_constant_descriptor(
            function.__defaults__ or (),
        ),
        "keyword_defaults": tuple(
            (
                key,
                _code_constant_descriptor(value),
            )
            for key, value in sorted(
                (function.__kwdefaults__ or {}).items()
            )
        ),
    }


def scenario_proof_verifier_execution_closure_sha256() -> str:
    """Hash the live production call graph, independent of source-file bytes."""

    function_descriptors: dict[str, object] = {}
    for name in _SCENARIO_RUNTIME_FUNCTION_NAMES:
        function = globals().get(name)
        if type(function) is not FunctionType:
            raise RuntimeError(
                f"scenario verifier runtime dependency was replaced: {name}"
            )
        expected_identity = _SCENARIO_RUNTIME_FUNCTION_IDENTITIES.get(name)
        if expected_identity is not None and function is not expected_identity:
            raise RuntimeError(
                f"scenario verifier runtime dependency identity changed: {name}"
            )
        function_descriptors[name] = _live_function_descriptor(name, function)
    for name, expected in _SCENARIO_IMPORTED_FUNCTION_IDENTITIES.items():
        if globals().get(name) is not expected:
            raise RuntimeError(
                f"scenario imported runtime dependency changed: {name}"
            )
    model_surfaces: dict[str, str] = {}
    for (
        name,
        model_type,
        expected_surface,
        expected_identity,
    ) in _SCENARIO_RUNTIME_MODEL_BASELINES:
        if globals().get(name) is not model_type:
            raise RuntimeError(
                f"scenario runtime model global changed: {name}"
            )
        if not _runtime_identity_matches(
            _type_runtime_identity_token(model_type),
            expected_identity,
        ):
            raise RuntimeError(
                f"scenario runtime model identity changed: {name}"
            )
        observed_surface = canonical_sha256(
            _type_runtime_surface_descriptor(model_type)
        )
        if observed_surface != expected_surface:
            raise RuntimeError(
                f"scenario runtime model surface changed: {name}"
            )
        model_surfaces[name] = observed_surface
    model_methods: dict[str, object] = {}
    for (
        class_name,
        method_name,
        expected_method,
    ) in _SCENARIO_RUNTIME_MODEL_METHOD_BASELINES:
        model_type = globals().get(class_name)
        observed_method = getattr(model_type, method_name, None)
        if observed_method is not expected_method:
            raise RuntimeError(
                "scenario runtime model method changed: "
                f"{class_name}.{method_name}"
            )
        if type(observed_method) is not FunctionType:
            raise RuntimeError(
                "scenario runtime model method is not a plain function: "
                f"{class_name}.{method_name}"
            )
        model_methods[f"{class_name}.{method_name}"] = (
            _live_function_descriptor(
                f"{class_name}.{method_name}",
                observed_method,
            )
        )
    return canonical_sha256(
        {
            "schema": "d2t_rna.task5_scenario_execution_closure.v2",
            "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
            "scenario_configuration_sha256": (
                SCENARIO_PROOF_VERIFIER_CONFIGURATION_SHA256
            ),
            "scenario_function_descriptors": function_descriptors,
            "scenario_model_runtime_surfaces": model_surfaces,
            "scenario_model_runtime_methods": model_methods,
            "confidence_rule_registry_definition": {
                "rule_id": REGISTERED_EXACT_CONFIDENCE_RULE_ID,
                "expected_parameter_ids": (
                    "omega.h0",
                    "omega.h1",
                    "omega.indifference",
                ),
                "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
            },
            "rorc_reason_order": tuple(
                reason.value for reason in RorcReason
            ),
        }
    )


def _assert_scenario_execution_closure() -> str:
    observed = scenario_proof_verifier_execution_closure_sha256()
    if observed != _SCENARIO_EXECUTION_CLOSURE_BASELINE_SHA256:
        raise RuntimeError(
            "scenario verifier live execution closure differs from the "
            "import-time production baseline"
        )
    return observed


def _derive_manifest(
    proof: ScenarioProof,
    artifact: ScenarioProofArtifact,
    *,
    fresh_exact_replay: bool = True,
) -> dict[str, object]:
    (
        checked_proof,
        checked_artifact,
        disposition,
        formal,
    ) = _replay_proof_against_artifact(
        proof,
        artifact,
        fresh_exact_replay=fresh_exact_replay,
    )
    return {
        "scenario_proof": checked_proof,
        "proof_artifact": checked_artifact,
        "scenario_proof_hash": canonical_sha256(checked_proof),
        "proof_artifact_hash": canonical_sha256(checked_artifact),
        "verifier_configuration_sha256": (
            SCENARIO_PROOF_VERIFIER_CONFIGURATION_SHA256
        ),
        "verifier_code_sha256": scenario_proof_verifier_code_sha256(),
        "coverage_disposition": disposition,
        "formal_guarantee": formal,
    }


class ScenarioProofManifest(FrozenContractModel):
    """Self-contained proof record that replays its raw typed artifact."""

    schema_id: Literal["d2t_rna.scenario_proof_manifest"] = (
        "d2t_rna.scenario_proof_manifest"
    )
    schema_version: Literal["3.0"] = "3.0"
    scenario_proof: ScenarioProof
    proof_artifact: ScenarioProofArtifact
    scenario_proof_hash: Sha256Hex
    proof_artifact_hash: Sha256Hex
    verifier_configuration_sha256: Sha256Hex
    verifier_code_sha256: Sha256Hex
    verifier_execution_closure_sha256: Sha256Hex
    coverage_disposition: ScenarioCoverageDisposition
    proof_artifact_hash_verified: Literal[True] = True
    formal_guarantee: StrictBool
    formal_scientific_certificate_authorized: Literal[False] = False
    prospective_claim_authorized: Literal[False] = False
    new_library_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @property
    def scenario_id(self) -> str:
        return self.scenario_proof.scenario_id

    @model_validator(mode="after")
    def replay_manifest(self) -> ScenarioProofManifest:
        try:
            execution_pre = _assert_scenario_execution_closure()
            expected = _derive_manifest(
                self.scenario_proof,
                self.proof_artifact,
            )
            for field_name, expected_value in expected.items():
                if getattr(self, field_name) != expected_value:
                    raise ValueError(
                        f"{field_name} does not match replayed value"
                    )
            if self.verifier_execution_closure_sha256 != execution_pre:
                raise ValueError(
                    "verifier execution closure does not match live replay"
                )
            if (
                self.scenario_proof.proof_artifact_hash
                != self.proof_artifact_hash
            ):
                raise ValueError(
                    "proof artifact hash is inconsistent across manifest"
                )
            execution_post = _assert_scenario_execution_closure()
            if execution_post != execution_pre:
                raise RuntimeError(
                    "scenario verifier execution closure changed during replay"
                )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"manifest replay failed: {exc}") from exc
        return self


def build_scenario_proof_manifest(
    proof: ScenarioProof,
    proof_artifact: ScenarioProofArtifact,
) -> ScenarioProofManifest:
    """Replay a proof from a typed artifact and freeze the full evidence."""

    if type(proof_artifact) not in _SCENARIO_PROOF_ARTIFACT_TYPES:
        raise TypeError(
            "proof artifact must be exactly one registered "
            "ScenarioProofArtifact"
        )
    execution_pre = _assert_scenario_execution_closure()
    payload = _derive_manifest(
        proof,
        proof_artifact,
        fresh_exact_replay=False,
    )
    execution_post = _assert_scenario_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "scenario verifier execution closure changed during build"
        )
    payload["verifier_execution_closure_sha256"] = execution_pre
    return ScenarioProofManifest.model_validate(
        payload,
        strict=True,
    )


def replay_scenario_proof_manifest(
    manifest: ScenarioProofManifest,
) -> ScenarioProofManifest:
    """Strictly reconstruct a manifest, detecting unchecked model copies."""

    if type(manifest) is not ScenarioProofManifest:
        raise TypeError("manifest must be exactly ScenarioProofManifest")
    try:
        return strict_revalidate_contract_model(manifest)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"manifest replay failed: {exc}") from exc


class RegisteredScenarioProbability(FrozenContractModel):
    """Exact positive probability assigned to one finite scenario."""

    scenario_id: RegisteredId
    probability: Rational

    @model_validator(mode="after")
    def validate_probability(self) -> RegisteredScenarioProbability:
        _positive_probability(
            self.probability,
            label=f"scenario {self.scenario_id!r} probability",
        )
        return self


_UNION_BOUND_DERIVATION_ID: Literal[
    "FINITE_REGISTERED_SCENARIO_AND_BOUND_EVENT_UNION_BOUND_V2"
] = "FINITE_REGISTERED_SCENARIO_AND_BOUND_EVENT_UNION_BOUND_V2"


class RegisteredScenarioCoverageFailureUnionTerm(FrozenContractModel):
    """Conservative within-scenario sum over every coverage failure event."""

    scenario_id: RegisteredId
    failure_union_upper_bound: Rational
    derivation: Literal[
        "MIN_ONE_SUM_OVER_REGISTERED_COVERAGE_FAILURE_UPPER_BOUNDS"
    ] = "MIN_ONE_SUM_OVER_REGISTERED_COVERAGE_FAILURE_UPPER_BOUNDS"

    @model_validator(mode="after")
    def validate_union_term(
        self,
    ) -> RegisteredScenarioCoverageFailureUnionTerm:
        _probability(
            self.failure_union_upper_bound,
            label=f"scenario {self.scenario_id!r} failure union bound",
        )
        return self


def _artifact_bound_registry_hash(
    artifact: ScenarioProofArtifact,
) -> str:
    risk_ids = _validate_bound_set(
        artifact.risk_upper_bounds,
        label="risk bounds",
    )
    coverage_ids = _validate_bound_set(
        artifact.coverage_lower_bounds,
        label="coverage bounds",
    )
    semantics = _validate_bound_semantics(
        artifact.bound_semantics,
        risk_bound_ids=risk_ids,
        coverage_bound_ids=coverage_ids,
    )
    derived = _bound_registry_sha256(semantics)
    if artifact.bound_registry_sha256 != derived:
        raise ValueError("artifact bound semantic registry does not replay")
    return derived


def _derive_finite_aggregate(
    manifests: tuple[ScenarioProofManifest, ...],
    probabilities: tuple[RegisteredScenarioProbability, ...],
    *,
    replay_manifests: bool = True,
) -> dict[str, object]:
    if not manifests:
        raise ValueError("at least one scenario manifest is required")
    if len(manifests) > MAX_FINITE_SCENARIOS:
        raise ValueError(
            "finite scenario aggregate exceeds the registered "
            f"{MAX_FINITE_SCENARIOS}-scenario cap"
        )
    if any(type(item) is not ScenarioProofManifest for item in manifests):
        raise TypeError(
            "aggregate inputs must be exactly ScenarioProofManifest"
        )
    checked_manifests = (
        tuple(replay_scenario_proof_manifest(item) for item in manifests)
        if replay_manifests
        else manifests
    )
    scenario_ids = tuple(item.scenario_id for item in checked_manifests)
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("aggregate scenario IDs must be unique")
    if scenario_ids != tuple(sorted(scenario_ids)):
        raise ValueError("aggregate manifests must use canonical order")

    if any(
        type(item) is not RegisteredScenarioProbability
        for item in probabilities
    ):
        raise TypeError(
            "scenario weights must be exactly RegisteredScenarioProbability"
        )
    checked_probabilities = tuple(
        strict_revalidate_contract_model(item) for item in probabilities
    )
    probability_ids = tuple(
        item.scenario_id for item in checked_probabilities
    )
    if probability_ids != scenario_ids:
        raise ValueError(
            "scenario probabilities must match manifest canonical order"
        )
    exact_probabilities = tuple(
        _positive_probability(
            item.probability,
            label=f"scenario {item.scenario_id!r} probability",
        )
        for item in checked_probabilities
    )
    if (
        _bounded_fraction_sum(
            exact_probabilities,
            label="scenario probability sum",
        )
        != 1
    ):
        raise ValueError("scenario probabilities must sum to one")

    first_proof = checked_manifests[0].scenario_proof
    first_artifact = checked_manifests[0].proof_artifact
    risk_ids = _validate_bound_set(
        first_proof.risk_upper_bounds,
        label="risk bounds",
    )
    coverage_ids = _validate_bound_set(
        first_proof.coverage_lower_bounds,
        label="coverage bounds",
    )
    registry_hash = _artifact_bound_registry_hash(first_artifact)
    for manifest in checked_manifests[1:]:
        proof = manifest.scenario_proof
        if proof.hypothesis_region != first_proof.hypothesis_region:
            raise ValueError(
                "scenario hypothesis regions are not comparable"
            )
        if (
            proof.coverage_core_membership
            != first_proof.coverage_core_membership
        ):
            raise ValueError(
                "scenario coverage-core registries are not comparable"
            )
        if (
            proof.conditioning_sigma_field_hash
            != first_proof.conditioning_sigma_field_hash
        ):
            raise ValueError(
                "scenario conditioning sigma fields are not comparable"
            )
        if (
            _validate_bound_set(
                proof.risk_upper_bounds,
                label="risk bounds",
            )
            != risk_ids
            or _validate_bound_set(
                proof.coverage_lower_bounds,
                label="coverage bounds",
            )
            != coverage_ids
        ):
            raise ValueError("scenario bound registries are not comparable")
        if _artifact_bound_registry_hash(
            manifest.proof_artifact
        ) != registry_hash:
            raise ValueError("scenario bound registries are not comparable")

    risk_maxima = {bound_id: Fraction(0) for bound_id in risk_ids}
    coverage_minima = {bound_id: Fraction(1) for bound_id in coverage_ids}
    union_terms: list[RegisteredScenarioCoverageFailureUnionTerm] = []
    accounted_mass = Fraction(0)
    for manifest, scenario_probability in zip(
        checked_manifests,
        exact_probabilities,
        strict=True,
    ):
        proof = manifest.scenario_proof
        for bound in proof.risk_upper_bounds:
            value = _probability(
                bound.value,
                label=f"risk bound {bound.bound_id!r}",
            )
            risk_maxima[bound.bound_id] = max(
                risk_maxima[bound.bound_id],
                value,
            )
        per_scenario_coverage_failures: list[Fraction] = []
        for bound in proof.coverage_lower_bounds:
            value = _probability(
                bound.value,
                label=f"coverage bound {bound.bound_id!r}",
            )
            coverage_minima[bound.bound_id] = min(
                coverage_minima[bound.bound_id],
                value,
            )
            per_scenario_coverage_failures.append(
                _bounded_fraction(
                    1 - value,
                    label=(
                        f"coverage failure {bound.bound_id!r} complement"
                    ),
                )
            )
        within_scenario_union = min(
            Fraction(1),
            _bounded_fraction_sum(
                per_scenario_coverage_failures,
                label=(
                    f"scenario {manifest.scenario_id!r} coverage failure "
                    "union sum"
                ),
            ),
        )
        union_terms.append(
            RegisteredScenarioCoverageFailureUnionTerm(
                scenario_id=manifest.scenario_id,
                failure_union_upper_bound=_rational(within_scenario_union),
            )
        )
        weighted_mass = _bounded_fraction(
            scenario_probability
            * _probability(
                proof.probability_mass_accounted,
                label="probability mass accounted",
            ),
            label="weighted scenario probability mass",
        )
        accounted_mass = _bounded_add(
            accounted_mass,
            weighted_mass,
            label="finite scenario probability mass sum",
        )

    risk_bounds = tuple(
        NamedBound(
            bound_id=bound_id,
            value=_rational(risk_maxima[bound_id]),
        )
        for bound_id in risk_ids
    )
    coverage_bounds = tuple(
        NamedBound(
            bound_id=bound_id,
            value=_rational(coverage_minima[bound_id]),
        )
        for bound_id in coverage_ids
    )
    if all(manifest.formal_guarantee for manifest in checked_manifests):
        disposition = (
            ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
        )
        formal = True
    elif any(
        manifest.coverage_disposition
        is ScenarioCoverageDisposition.RISK_CERTIFIED_COVERAGE_PREDICTED
        for manifest in checked_manifests
    ):
        disposition = (
            ScenarioCoverageDisposition.RISK_CERTIFIED_COVERAGE_PREDICTED
        )
        formal = False
    else:
        disposition = (
            ScenarioCoverageDisposition
            .REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
        )
        formal = False

    return {
        "per_scenario_proof_manifest": checked_manifests,
        "scenario_probabilities": checked_probabilities,
        "risk_upper_bounds": risk_bounds,
        "coverage_lower_bounds": coverage_bounds,
        "per_scenario_coverage_failure_union_bounds": tuple(union_terms),
        "scenario_coverage_union_bound": _rational(
            min(
                Fraction(1),
                _bounded_fraction_sum(
                    (
                        _fraction(
                            term.failure_union_upper_bound,
                            label="per-scenario failure union bound",
                        )
                        for term in union_terms
                    ),
                    label="cross-scenario coverage failure union sum",
                ),
            )
        ),
        "scenario_probability_mass_accounted": _rational(accounted_mass),
        "bound_registry_sha256": registry_hash,
        "union_bound_derivation_id": _UNION_BOUND_DERIVATION_ID,
        "coverage_disposition": disposition,
        "formal_guarantee": formal,
    }


class FiniteScenarioCoverageAggregate(FrozenContractModel):
    """Replayable max-risk/min-coverage finite-registry aggregate."""

    schema_id: Literal["d2t_rna.finite_scenario_coverage_aggregate"] = (
        "d2t_rna.finite_scenario_coverage_aggregate"
    )
    schema_version: Literal["3.0"] = "3.0"
    per_scenario_proof_manifest: tuple[ScenarioProofManifest, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_SCENARIOS,
    )
    scenario_probabilities: tuple[RegisteredScenarioProbability, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_SCENARIOS,
    )
    risk_upper_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    coverage_lower_bounds: tuple[NamedBound, ...] = Field(
        min_length=1,
        max_length=MAX_SCENARIO_BOUNDS_PER_KIND,
    )
    per_scenario_coverage_failure_union_bounds: tuple[
        RegisteredScenarioCoverageFailureUnionTerm,
        ...,
    ] = Field(min_length=1, max_length=MAX_FINITE_SCENARIOS)
    scenario_coverage_union_bound: Rational
    scenario_probability_mass_accounted: Rational
    bound_registry_sha256: Sha256Hex
    union_bound_derivation_id: Literal[
        "FINITE_REGISTERED_SCENARIO_AND_BOUND_EVENT_UNION_BOUND_V2"
    ] = _UNION_BOUND_DERIVATION_ID
    union_bound_scope: Literal[
        "CAPPED_SUM_ACROSS_ALL_REGISTERED_SCENARIOS_AND_COVERAGE_FAILURE_EVENTS"
    ] = (
        "CAPPED_SUM_ACROSS_ALL_REGISTERED_SCENARIOS_AND_COVERAGE_FAILURE_EVENTS"
    )
    scenario_probability_weights_used_for_union: Literal[False] = False
    coverage_disposition: ScenarioCoverageDisposition
    formal_guarantee: StrictBool
    verifier_execution_closure_sha256: Sha256Hex
    aggregation_rule: Literal["MAX_RISK_MIN_COVERAGE_ONLY"] = (
        "MAX_RISK_MIN_COVERAGE_ONLY"
    )
    claim_scope: Literal["FINITE_REGISTERED_SCENARIOS_ONLY"] = (
        "FINITE_REGISTERED_SCENARIOS_ONLY"
    )
    continuous_uncertainty_set_claim: Literal[False] = False
    interpolation_authorized: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False
    prospective_claim_authorized: Literal[False] = False
    new_library_claim_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def replay_aggregate(self) -> FiniteScenarioCoverageAggregate:
        try:
            execution_pre = _assert_scenario_execution_closure()
            expected = _derive_finite_aggregate(
                self.per_scenario_proof_manifest,
                self.scenario_probabilities,
                replay_manifests=False,
            )
            for field_name, expected_value in expected.items():
                if getattr(self, field_name) != expected_value:
                    raise ValueError(
                        f"{field_name} does not match replayed value"
                    )
            if self.verifier_execution_closure_sha256 != execution_pre:
                raise ValueError(
                    "aggregate verifier execution closure does not match "
                    "live replay"
                )
            execution_post = _assert_scenario_execution_closure()
            if execution_post != execution_pre:
                raise RuntimeError(
                    "scenario verifier execution closure changed during "
                    "aggregate replay"
                )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"aggregate replay failed: {exc}") from exc
        return self


def _normalize_scenario_probabilities(
    manifests: tuple[ScenarioProofManifest, ...],
    scenario_probabilities: Mapping[str, Rational],
) -> tuple[RegisteredScenarioProbability, ...]:
    if not isinstance(scenario_probabilities, Mapping):
        raise TypeError("scenario_probabilities must be a mapping")
    if len(manifests) > MAX_FINITE_SCENARIOS:
        raise ValueError("finite scenario input exceeds the registered cap")
    if len(scenario_probabilities) > MAX_FINITE_SCENARIOS:
        raise ValueError(
            "scenario probability mapping exceeds the registered cap"
        )
    scenario_ids = tuple(manifest.scenario_id for manifest in manifests)
    if set(scenario_probabilities) != set(scenario_ids):
        raise ValueError(
            "scenario probabilities must have exactly the manifest IDs"
        )
    normalized: list[RegisteredScenarioProbability] = []
    for scenario_id in scenario_ids:
        probability = scenario_probabilities[scenario_id]
        if type(probability) is not Rational:
            raise TypeError(
                "scenario probability values must be exactly Rational"
            )
        normalized.append(
            RegisteredScenarioProbability(
                scenario_id=scenario_id,
                probability=probability,
            )
        )
    return tuple(normalized)


def aggregate_finite_scenarios(
    manifests: Sequence[ScenarioProofManifest],
    *,
    scenario_probabilities: Mapping[str, Rational],
) -> FiniteScenarioCoverageAggregate:
    """Aggregate only mutually comparable, embedded finite scenario proofs."""

    manifest_tuple = tuple(manifests)
    probabilities = _normalize_scenario_probabilities(
        manifest_tuple,
        scenario_probabilities,
    )
    execution_pre = _assert_scenario_execution_closure()
    payload = _derive_finite_aggregate(
        manifest_tuple,
        probabilities,
        replay_manifests=False,
    )
    execution_post = _assert_scenario_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "scenario verifier execution closure changed during aggregation"
        )
    payload["verifier_execution_closure_sha256"] = execution_pre
    return FiniteScenarioCoverageAggregate.model_validate(
        payload,
        strict=True,
    )


def replay_finite_scenario_aggregate(
    aggregate: FiniteScenarioCoverageAggregate,
) -> FiniteScenarioCoverageAggregate:
    """Strictly replay an aggregate, including all embedded proof manifests."""

    if type(aggregate) is not FiniteScenarioCoverageAggregate:
        raise TypeError(
            "aggregate must be exactly FiniteScenarioCoverageAggregate"
        )
    try:
        return strict_revalidate_contract_model(aggregate)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"aggregate replay failed: {exc}") from exc


_RORC_REASON_ORDER = {
    reason.value: index for index, reason in enumerate(RorcReason)
}


def _normalize_rorc_reasons(
    reasons: Iterable[RorcReason],
) -> tuple[RorcReason, ...]:
    if isinstance(reasons, (str, bytes)):
        raise TypeError("RORC reasons must contain exact RorcReason members")
    received = tuple(reasons)
    if any(type(reason) is not RorcReason for reason in received):
        raise TypeError("RORC reasons must contain exact RorcReason members")
    unique = set(received)
    if not unique:
        return (RorcReason.ABSTAIN_INDETERMINATE,)
    return tuple(
        sorted(unique, key=lambda reason: _RORC_REASON_ORDER[reason.value])
    )


class RorcAssessment(FrozenContractModel):
    """Registered RORC assessment; no prospective decisive path exists."""

    schema_id: Literal["d2t_rna.rorc_assessment"] = (
        "d2t_rna.rorc_assessment"
    )
    schema_version: Literal["2.0"] = "2.0"
    decision: Literal[RorcDecision.ABSTAIN] = RorcDecision.ABSTAIN
    reasons: tuple[RorcReason, ...]
    evidence_role: Literal[
        "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    ] = "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    held_out_claim_authorized: Literal[False] = False
    scientific_conclusion_authorized: Literal[False] = False
    diagnostic_tuning_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def validate_reasons(self) -> RorcAssessment:
        if self.reasons != _normalize_rorc_reasons(self.reasons):
            raise ValueError("RORC reasons are not canonical")
        return self


def assess_rorc(reasons: Iterable[RorcReason]) -> RorcAssessment:
    """Return the only registered RORC action with canonical reason codes."""

    return RorcAssessment(reasons=_normalize_rorc_reasons(reasons))


class RegisteredRorcPathReplay(FrozenContractModel):
    """One actually executed path in the frozen RORC reason powerset."""

    path_id: RegisteredId
    supplied_reasons: tuple[RorcReason, ...] = Field(
        max_length=len(RorcReason),
    )
    assessment: RorcAssessment
    assessment_sha256: Sha256Hex


def _registered_rorc_reason_paths() -> tuple[tuple[RorcReason, ...], ...]:
    reasons = tuple(RorcReason)
    return tuple(
        tuple(
            reason
            for reason_index, reason in enumerate(reasons)
            if mask & (1 << reason_index)
        )
        for subset_size in range(len(reasons) + 1)
        for mask in range(1 << len(reasons))
        if sum(
            1
            for reason_index in range(len(reasons))
            if mask & (1 << reason_index)
        )
        == subset_size
    )


def _rorc_path_registry_root_sha256() -> str:
    return canonical_sha256(
        {
            "schema": "d2t_rna.registered_rorc_reason_path_registry.v1",
            "frozen_contract_sha256": FROZEN_CONTRACT_SHA256,
            "reason_order": tuple(reason.value for reason in RorcReason),
            "paths": _registered_rorc_reason_paths(),
            "path_semantics": (
                "Complete powerset of every closed RorcReason member; each "
                "path is executed through assess_rorc."
            ),
        }
    )


def _derive_registered_rorc_path_audit() -> dict[str, object]:
    paths = _registered_rorc_reason_paths()
    expected_count = 2 ** len(tuple(RorcReason))
    if len(paths) != expected_count:
        raise RuntimeError("registered RORC reason powerset is incomplete")
    if len(set(paths)) != expected_count:
        raise RuntimeError(
            "registered RORC reason powerset contains duplicate paths"
        )
    if {
        reason
        for path in paths
        for reason in path
    } != set(RorcReason):
        raise RuntimeError(
            "registered RORC reason powerset omits a registered reason"
        )
    records: list[RegisteredRorcPathReplay] = []
    for index, reasons in enumerate(paths):
        assessment = assess_rorc(reasons)
        records.append(
            RegisteredRorcPathReplay(
                path_id=f"rorc-path-{index:03d}",
                supplied_reasons=reasons,
                assessment=assessment,
                assessment_sha256=canonical_sha256(assessment),
            )
        )
    all_abstain = all(
        record.assessment.decision is RorcDecision.ABSTAIN
        for record in records
    )
    if not all_abstain:
        raise RuntimeError("a registered RORC path produced a decisive output")
    return {
        "registered_path_registry_root_sha256": (
            _rorc_path_registry_root_sha256()
        ),
        "expected_path_count": expected_count,
        "path_replays": tuple(records),
        "all_registered_paths_abstain": True,
    }


class RegisteredRorcPathAudit(FrozenContractModel):
    """Fresh exhaustive execution audit; the sole all-paths claim bearer."""

    schema_id: Literal["d2t_rna.registered_rorc_path_audit"] = (
        "d2t_rna.registered_rorc_path_audit"
    )
    schema_version: Literal["1.0"] = "1.0"
    registered_path_registry_root_sha256: Sha256Hex
    expected_path_count: Literal[16] = 16
    path_replays: tuple[RegisteredRorcPathReplay, ...] = Field(
        min_length=16,
        max_length=16,
    )
    all_registered_paths_abstain: Literal[True] = True
    registered_path_set_complete: Literal[True] = True
    paths_executed_via_assess_rorc: Literal[True] = True
    verifier_execution_closure_sha256: Sha256Hex
    evidence_role: Literal[
        "REGISTERED_PATH_EXECUTION_AUDIT_ONLY"
    ] = "REGISTERED_PATH_EXECUTION_AUDIT_ONLY"
    held_out_claim_authorized: Literal[False] = False
    scientific_conclusion_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def replay_registered_paths(self) -> RegisteredRorcPathAudit:
        execution_pre = _assert_scenario_execution_closure()
        expected = _derive_registered_rorc_path_audit()
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(
                    f"registered RORC path audit {field_name} does not replay"
                )
        if self.verifier_execution_closure_sha256 != execution_pre:
            raise ValueError(
                "registered RORC path audit execution closure is stale"
            )
        execution_post = _assert_scenario_execution_closure()
        if execution_post != execution_pre:
            raise RuntimeError(
                "scenario execution closure changed during RORC path audit"
            )
        return self


def audit_registered_rorc_paths() -> RegisteredRorcPathAudit:
    """Execute every path in the complete frozen reason powerset."""

    execution_pre = _assert_scenario_execution_closure()
    payload = _derive_registered_rorc_path_audit()
    execution_post = _assert_scenario_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "scenario execution closure changed during RORC path audit"
        )
    payload["verifier_execution_closure_sha256"] = execution_pre
    return RegisteredRorcPathAudit.model_validate(payload, strict=True)


class RorcCaseRecord(FrozenContractModel):
    """One replayable historically exposed RORC stress-test case."""

    case_id: RegisteredId
    case_input_sha256: Sha256Hex
    decision_artifact_sha256: Sha256Hex
    observed_decision: RorcObservedDecision
    reasons: tuple[RorcReason, ...]
    decision_correct: StrictBool
    covered_with_registered_state_dictionary: StrictBool
    covered_after_omitting_third_state: StrictBool

    @field_validator("reasons", mode="before")
    @classmethod
    def canonicalize_reasons(
        cls,
        value: object,
    ) -> tuple[RorcReason, ...]:
        if not isinstance(value, Iterable):
            raise TypeError("RORC reasons must be iterable")
        return _normalize_rorc_reasons(value)

    @model_validator(mode="after")
    def validate_reason_order(self) -> RorcCaseRecord:
        if self.reasons != _normalize_rorc_reasons(self.reasons):
            raise ValueError("RORC case reasons are not canonical")
        return self


def _derive_rorc_case_manifest(
    cases: tuple[RorcCaseRecord, ...],
) -> dict[str, object]:
    if not cases:
        raise ValueError("RORC case manifest requires at least one case")
    if len(cases) > MAX_RORC_CASES:
        raise ValueError(
            "RORC case manifest exceeds the registered "
            f"{MAX_RORC_CASES}-case cap"
        )
    if any(type(case) is not RorcCaseRecord for case in cases):
        raise TypeError("RORC cases must be exactly RorcCaseRecord")
    checked = tuple(strict_revalidate_contract_model(case) for case in cases)
    case_ids = tuple(case.case_id for case in checked)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("RORC case IDs must be unique")
    if case_ids != tuple(sorted(case_ids)):
        raise ValueError("RORC cases must use canonical case-ID order")
    return {
        "cases": checked,
        "case_records_sha256": canonical_sha256(
            {"canonical_rorc_cases": checked}
        ),
    }


class RorcCaseManifest(FrozenContractModel):
    """Canonical full-case bearer for retrospective RORC metric replay."""

    schema_id: Literal["d2t_rna.rorc_case_manifest"] = (
        "d2t_rna.rorc_case_manifest"
    )
    schema_version: Literal["1.0"] = "1.0"
    cases: tuple[RorcCaseRecord, ...] = Field(
        min_length=1,
        max_length=MAX_RORC_CASES,
    )
    case_records_sha256: Sha256Hex
    evidence_role: Literal[
        "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    ] = "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    held_out_claim_authorized: Literal[False] = False
    scientific_conclusion_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def replay_case_manifest(self) -> RorcCaseManifest:
        expected = _derive_rorc_case_manifest(self.cases)
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(
                    f"RORC case manifest {field_name} does not replay"
                )
        return self


def build_rorc_case_manifest(
    cases: Sequence[RorcCaseRecord],
) -> RorcCaseManifest:
    """Freeze canonical RORC cases before computing any summary metric."""

    return RorcCaseManifest.model_validate(
        _derive_rorc_case_manifest(tuple(cases)),
        strict=True,
    )


def _derive_rorc_metrics(
    case_manifest: RorcCaseManifest,
) -> dict[str, object]:
    if type(case_manifest) is not RorcCaseManifest:
        raise TypeError("case_manifest must be exactly RorcCaseManifest")
    checked_manifest = strict_revalidate_contract_model(case_manifest)
    total = len(checked_manifest.cases)
    decisive = sum(
        case.observed_decision is not RorcObservedDecision.ABSTAIN
        for case in checked_manifest.cases
    )
    incorrect_decisive = sum(
        (
            case.observed_decision is not RorcObservedDecision.ABSTAIN
            and not case.decision_correct
        )
        for case in checked_manifest.cases
    )
    covered = sum(
        case.covered_with_registered_state_dictionary
        for case in checked_manifest.cases
    )
    covered_without_third = sum(
        case.covered_after_omitting_third_state
        for case in checked_manifest.cases
    )
    coverage_change = Fraction(covered_without_third - covered, total)
    return {
        "case_manifest": checked_manifest,
        "case_manifest_sha256": canonical_sha256(checked_manifest),
        "total_cases": total,
        "decisive_output_count": decisive,
        "incorrect_decisive_output_count": incorrect_decisive,
        "covered_with_registered_state_dictionary": covered,
        "covered_after_omitting_third_state": covered_without_third,
        "decisive_output_probability": _rational(Fraction(decisive, total)),
        "incorrect_decisive_output_probability": _rational(
            Fraction(incorrect_decisive, total)
        ),
        "coverage_change_after_omitting_third_state": _rational(
            coverage_change
        ),
        "coverage_decline_after_omitting_third_state": _rational(
            -coverage_change
        ),
        "coverage_increase_observed": coverage_change > 0,
        "observed_case_set_all_abstain": decisive == 0,
        "observational_case_set_complete": False,
        "observational_decision_execution_verified": False,
    }


class RorcStressMetrics(FrozenContractModel):
    """Metrics derived exclusively by replaying every embedded RORC case."""

    schema_id: Literal["d2t_rna.rorc_stress_metrics"] = (
        "d2t_rna.rorc_stress_metrics"
    )
    schema_version: Literal["3.0"] = "3.0"
    case_manifest: RorcCaseManifest
    case_manifest_sha256: Sha256Hex
    total_cases: StrictInt
    decisive_output_count: StrictInt
    incorrect_decisive_output_count: StrictInt
    covered_with_registered_state_dictionary: StrictInt
    covered_after_omitting_third_state: StrictInt
    decisive_output_probability: Rational
    incorrect_decisive_output_probability: Rational
    coverage_change_after_omitting_third_state: Rational
    coverage_decline_after_omitting_third_state: Rational
    coverage_increase_observed: StrictBool
    observed_case_set_all_abstain: StrictBool
    observational_case_set_complete: Literal[False] = False
    observational_decision_execution_verified: Literal[False] = False
    metric_replay_execution_closure_sha256: Sha256Hex
    evidence_role: Literal[
        "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    ] = "HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE"
    held_out_claim_authorized: Literal[False] = False
    scientific_conclusion_authorized: Literal[False] = False
    diagnostic_tuning_authorized: Literal[False] = False
    serialized_bearer_authorization: Literal[False] = False

    @model_validator(mode="after")
    def replay_metrics(self) -> RorcStressMetrics:
        try:
            execution_pre = _assert_scenario_execution_closure()
            expected = _derive_rorc_metrics(self.case_manifest)
            for field_name, expected_value in expected.items():
                if getattr(self, field_name) != expected_value:
                    raise ValueError(
                        f"{field_name} does not match replayed value"
                    )
            if (
                self.metric_replay_execution_closure_sha256
                != execution_pre
            ):
                raise ValueError(
                    "RORC metric replay execution closure is stale"
                )
            execution_post = _assert_scenario_execution_closure()
            if execution_post != execution_pre:
                raise RuntimeError(
                    "scenario execution closure changed during RORC metric "
                    "replay"
                )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"metrics replay failed: {exc}") from exc
        return self


def compute_rorc_stress_metrics(
    case_manifest: RorcCaseManifest,
) -> RorcStressMetrics:
    """Compute exact retrospective metrics from the full case manifest."""

    execution_pre = _assert_scenario_execution_closure()
    payload = _derive_rorc_metrics(case_manifest)
    execution_post = _assert_scenario_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "scenario execution closure changed during RORC metric replay"
        )
    payload["metric_replay_execution_closure_sha256"] = execution_pre
    return RorcStressMetrics.model_validate(
        payload,
        strict=True,
    )


def replay_rorc_stress_metrics(
    metrics: RorcStressMetrics,
) -> RorcStressMetrics:
    """Strictly replay metrics, detecting unchecked constructor upgrades."""

    if type(metrics) is not RorcStressMetrics:
        raise TypeError("metrics must be exactly RorcStressMetrics")
    try:
        return strict_revalidate_contract_model(metrics)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"metrics replay failed: {exc}") from exc


_SCENARIO_RUNTIME_FUNCTION_NAMES = (
    "_fraction",
    "_bounded_fraction",
    "_bounded_add",
    "_bounded_fraction_sum",
    "_probability",
    "_positive_probability",
    "_rational",
    "_validate_bound_set",
    "_validate_event_flags",
    "_validate_bound_semantics",
    "_bound_registry_sha256",
    "_nonformal_atom_bound_semantics",
    "_derive_exact_enumeration",
    "_risk_bounds_from_certificate",
    "_strict_validated_risk_certificate",
    "_registered_all_parameter_confidence_rule",
    "build_registered_exact_confidence_procedure",
    "evaluate_registered_exact_synthetic_coverage_report",
    "_registered_confidence_rule_registry_root_sha256",
    "_resolve_registered_confidence_rule",
    "_exact_synthetic_bound_semantics",
    "_exact_synthetic_payload_from_validated_inputs",
    "_derive_exact_synthetic_artifact",
    "_validate_canonical_exact_raw_json",
    "_fresh_replay_exact_synthetic_artifact",
    "_strict_artifact",
    "_validate_scenario_proof",
    "_replay_proof_against_artifact",
    "_derive_manifest",
    "_artifact_bound_registry_hash",
    "_derive_finite_aggregate",
    "_normalize_scenario_probabilities",
    "_normalize_rorc_reasons",
    "assess_rorc",
    "_registered_rorc_reason_paths",
    "_rorc_path_registry_root_sha256",
    "_derive_registered_rorc_path_audit",
    "_derive_rorc_case_manifest",
    "_derive_rorc_metrics",
    "_code_constant_descriptor",
    "_live_code_descriptor",
    "_live_function_descriptor",
    "scenario_proof_verifier_execution_closure_sha256",
    "_assert_scenario_execution_closure",
)
_SCENARIO_RUNTIME_FUNCTION_IDENTITIES = {
    name: globals()[name] for name in _SCENARIO_RUNTIME_FUNCTION_NAMES
}
_SCENARIO_IMPORTED_FUNCTION_IDENTITIES = {
    "Fraction": Fraction,
    "hashlib": hashlib,
    "json": json,
    "canonical_json_bytes": canonical_json_bytes,
    "canonical_sha256": canonical_sha256,
    "parse_contract_json": parse_contract_json,
    "validate_contract_json_syntax": validate_contract_json_syntax,
    "strict_revalidate_contract_model": strict_revalidate_contract_model,
    "confidence_rule_implementation_sha256": (
        confidence_rule_implementation_sha256
    ),
    "coverage_module_sha256": coverage_module_sha256,
    "evaluate_exact_synthetic_risk_coverage": (
        evaluate_exact_synthetic_risk_coverage
    ),
    "replay_exact_synthetic_coverage_report": (
        replay_exact_synthetic_coverage_report
    ),
    "validate_uniform_indifference_control": (
        validate_uniform_indifference_control
    ),
}
_SCENARIO_RUNTIME_MODEL_NAMES = (
    "ExactSyntheticScenarioProofArtifact",
    "ExactEnumerationScenarioProofArtifact",
    "MonteCarloScenarioProofArtifact",
    "ScenarioProofManifest",
    "FiniteScenarioCoverageAggregate",
    "RorcAssessment",
    "RegisteredRorcPathAudit",
    "RorcCaseManifest",
    "RorcStressMetrics",
)
_SCENARIO_RUNTIME_MODEL_BASELINES = tuple(
    (
        name,
        globals()[name],
        canonical_sha256(
            _type_runtime_surface_descriptor(globals()[name])
        ),
        _type_runtime_identity_token(globals()[name]),
    )
    for name in _SCENARIO_RUNTIME_MODEL_NAMES
)
_SCENARIO_RUNTIME_MODEL_METHOD_NAMES = (
    (
        "ExactSyntheticScenarioProofArtifact",
        "bind_raw_json_hashes",
    ),
    (
        "ExactEnumerationScenarioProofArtifact",
        "replay_exact_enumeration",
    ),
    (
        "MonteCarloScenarioProofArtifact",
        "validate_embedded_risk_certificate",
    ),
    ("ScenarioProofManifest", "replay_manifest"),
    ("FiniteScenarioCoverageAggregate", "replay_aggregate"),
    ("RorcAssessment", "validate_reasons"),
    ("RegisteredRorcPathAudit", "replay_registered_paths"),
    ("RorcCaseManifest", "replay_case_manifest"),
    ("RorcStressMetrics", "replay_metrics"),
)
_SCENARIO_RUNTIME_MODEL_METHOD_BASELINES = tuple(
    (
        class_name,
        method_name,
        getattr(globals()[class_name], method_name),
    )
    for class_name, method_name in _SCENARIO_RUNTIME_MODEL_METHOD_NAMES
)
_SCENARIO_EXECUTION_CLOSURE_BASELINE_SHA256 = (
    scenario_proof_verifier_execution_closure_sha256()
)
