"""Hash-only pre-D commitments and the sealed Lock-D reveal package."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictStr, model_validator

from .base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
)
from .enums import TruthVisibility
from .primitives import (
    NamedBound,
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)


NonceHex = Annotated[
    StrictStr,
    Field(pattern=r"^[0-9a-f]{64}$"),
]

NUMERIC_COMMITMENT_DOMAIN = "d2t-rna:v1:numeric"
SEMANTIC_COMMITMENT_DOMAIN = "d2t-rna:v1:semantic"
BINDING_COMMITMENT_DOMAIN = "d2t-rna:v1:decision-binding"
FROZEN_CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)


class TruthAssetCommitment(FrozenContractModel):
    schema_id: Literal["d2t_rna.truth_asset_commitment"] = (
        "d2t_rna.truth_asset_commitment"
    )
    schema_version: Literal["1.0"] = "1.0"
    truth_asset_id: RegisteredId
    asset_hash: Sha256Hex = Field(
        description=(
            "Raw-file SHA-256 of the exact sealed reveal package bytes, "
            "including numeric, semantic, and decision-binding components"
        )
    )
    sequence_identity_hash: Sha256Hex
    condition_spec_hash: Sha256Hex
    measurement_modality: RegistryRef
    eligibility_status_without_direction: RegistryRef
    numeric_payload_hash: Sha256Hex
    semantic_payload_hash: Sha256Hex
    visibility: Literal[TruthVisibility.HASH_ONLY]


class RationalInterval(FrozenContractModel):
    """Closed exact interval; binary floating point is intentionally absent."""

    schema_id: Literal["d2t_rna.rational_interval"] = (
        "d2t_rna.rational_interval"
    )
    schema_version: Literal["1.0"] = "1.0"
    lower: Rational
    upper: Rational

    @model_validator(mode="after")
    def lower_does_not_exceed_upper(self) -> "RationalInterval":
        if (
            self.lower.numerator * self.upper.denominator
            > self.upper.numerator * self.lower.denominator
        ):
            raise ValueError("interval lower bound exceeds upper bound")
        return self


class NumericTruthPayload(FrozenContractModel):
    """Typed numeric truth sealed until Lock D."""

    schema_id: Literal["d2t_rna.numeric_truth_payload"] = (
        "d2t_rna.numeric_truth_payload"
    )
    schema_version: Literal["1.0"] = "1.0"
    population_estimate: Rational
    confidence_region: RationalInterval
    projected_state_proportions: tuple[NamedBound, ...]

    @model_validator(mode="after")
    def state_bounds_are_unique_and_canonically_sorted(
        self,
    ) -> "NumericTruthPayload":
        bound_ids = tuple(
            bound.bound_id for bound in self.projected_state_proportions
        )
        if not bound_ids:
            raise ValueError("projected state proportions cannot be empty")
        if len(set(bound_ids)) != len(bound_ids):
            raise ValueError("projected state proportion IDs must be unique")
        if bound_ids != tuple(sorted(bound_ids)):
            raise ValueError(
                "projected state proportions must be sorted by bound_id"
            )
        return self


class SemanticTruthPayload(FrozenContractModel):
    """Typed directional and action semantics sealed until Lock D."""

    schema_id: Literal["d2t_rna.semantic_truth_payload"] = (
        "d2t_rna.semantic_truth_payload"
    )
    schema_version: Literal["1.0"] = "1.0"
    directional_evidence: tuple[RegistryRef, ...]
    state_preservation_result: RegistryRef
    action_effect_labels: tuple[RegistryRef, ...]

    @model_validator(mode="after")
    def registered_lists_are_unique_and_sorted(
        self,
    ) -> "SemanticTruthPayload":
        for field_name in ("directional_evidence", "action_effect_labels"):
            values = getattr(self, field_name)
            identifiers = tuple(value.registry_id for value in values)
            if not identifiers:
                raise ValueError(f"{field_name} cannot be empty")
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"{field_name} registry IDs must be unique")
            if identifiers != tuple(sorted(identifiers)):
                raise ValueError(
                    f"{field_name} must be sorted by registry_id"
                )
        return self


class DecisionBindingPayload(FrozenContractModel):
    """Frozen decision, certificate, plan, and scoring inputs."""

    schema_id: Literal["d2t_rna.decision_binding_payload"] = (
        "d2t_rna.decision_binding_payload"
    )
    schema_version: Literal["1.0"] = "1.0"
    h0_binding: RegistryRef
    h1_binding: RegistryRef
    coverage_core_binding: RegistryRef
    certificate_hash: Sha256Hex
    frozen_decision_output_hash: Sha256Hex
    evaluation_plan_hash: Sha256Hex
    scoring_spec_hash: Sha256Hex


def _truth_context(
    *,
    contract_hash: str,
    evaluation_id: str,
    chain_id: str,
    truth_asset_id: str,
    sequence_identity_hash: str,
    condition_spec_hash: str,
    measurement_modality: RegistryRef,
    eligibility_status_without_direction: RegistryRef,
) -> dict[str, object]:
    return {
        "chain_id": chain_id,
        "condition_spec_hash": condition_spec_hash,
        "contract_hash": contract_hash,
        "eligibility_status_without_direction": (
            eligibility_status_without_direction
        ),
        "measurement_modality": measurement_modality,
        "evaluation_id": evaluation_id,
        "sequence_identity_hash": sequence_identity_hash,
        "truth_asset_id": truth_asset_id,
    }


def compute_numeric_payload_hash(
    *,
    contract_hash: str,
    evaluation_id: str,
    chain_id: str,
    truth_asset_id: str,
    sequence_identity_hash: str,
    condition_spec_hash: str,
    measurement_modality: RegistryRef,
    eligibility_status_without_direction: RegistryRef,
    nonce: str,
    payload: NumericTruthPayload,
) -> str:
    """Commit to numeric truth with a sealed nonce and explicit domain."""

    return canonical_sha256(
        {
            "context": _truth_context(
                contract_hash=contract_hash,
                evaluation_id=evaluation_id,
                chain_id=chain_id,
                truth_asset_id=truth_asset_id,
                sequence_identity_hash=sequence_identity_hash,
                condition_spec_hash=condition_spec_hash,
                measurement_modality=measurement_modality,
                eligibility_status_without_direction=(
                    eligibility_status_without_direction
                ),
            ),
            "domain": NUMERIC_COMMITMENT_DOMAIN,
            "nonce": nonce,
            "payload": payload,
            "payload_schema_id": payload.schema_id,
            "payload_schema_version": payload.schema_version,
        }
    )


def compute_semantic_payload_hash(
    *,
    contract_hash: str,
    evaluation_id: str,
    chain_id: str,
    truth_asset_id: str,
    sequence_identity_hash: str,
    condition_spec_hash: str,
    measurement_modality: RegistryRef,
    eligibility_status_without_direction: RegistryRef,
    nonce: str,
    payload: SemanticTruthPayload,
) -> str:
    """Commit to semantic truth with a distinct sealed nonce and domain."""

    return canonical_sha256(
        {
            "context": _truth_context(
                contract_hash=contract_hash,
                evaluation_id=evaluation_id,
                chain_id=chain_id,
                truth_asset_id=truth_asset_id,
                sequence_identity_hash=sequence_identity_hash,
                condition_spec_hash=condition_spec_hash,
                measurement_modality=measurement_modality,
                eligibility_status_without_direction=(
                    eligibility_status_without_direction
                ),
            ),
            "domain": SEMANTIC_COMMITMENT_DOMAIN,
            "nonce": nonce,
            "payload": payload,
            "payload_schema_id": payload.schema_id,
            "payload_schema_version": payload.schema_version,
        }
    )


def compute_binding_payload_hash(
    *,
    contract_hash: str,
    evaluation_id: str,
    chain_id: str,
    truth_asset_id: str,
    sequence_identity_hash: str,
    condition_spec_hash: str,
    measurement_modality: RegistryRef,
    eligibility_status_without_direction: RegistryRef,
    numeric_payload_hash: str,
    semantic_payload_hash: str,
    nonce: str,
    payload: DecisionBindingPayload,
    native_t4_eligible: bool,
) -> str:
    """Bind truth components to the exact frozen scoring inputs."""

    return canonical_sha256(
        {
            "context": _truth_context(
                contract_hash=contract_hash,
                evaluation_id=evaluation_id,
                chain_id=chain_id,
                truth_asset_id=truth_asset_id,
                sequence_identity_hash=sequence_identity_hash,
                condition_spec_hash=condition_spec_hash,
                measurement_modality=measurement_modality,
                eligibility_status_without_direction=(
                    eligibility_status_without_direction
                ),
            ),
            "domain": BINDING_COMMITMENT_DOMAIN,
            "native_t4_eligible": native_t4_eligible,
            "nonce": nonce,
            "numeric_payload_hash": numeric_payload_hash,
            "payload": payload,
            "payload_schema_id": payload.schema_id,
            "payload_schema_version": payload.schema_version,
            "semantic_payload_hash": semantic_payload_hash,
        }
    )


class DecisionTruthBindingReveal(FrozenContractModel):
    """One exact per-asset reveal package, visible only at Lock D."""

    schema_id: Literal["d2t_rna.decision_truth_binding_reveal_asset"] = (
        "d2t_rna.decision_truth_binding_reveal_asset"
    )
    schema_version: Literal["1.0"] = "1.0"
    contract_hash: Literal[
        "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
    ] = FROZEN_CONTRACT_SHA256
    evaluation_id: RegisteredId
    chain_id: RegisteredId
    truth_asset_id: RegisteredId
    sequence_identity_hash: Sha256Hex
    condition_spec_hash: Sha256Hex
    measurement_modality: RegistryRef
    eligibility_status_without_direction: RegistryRef
    numeric_nonce: NonceHex
    numeric_payload: NumericTruthPayload
    numeric_payload_hash: Sha256Hex
    semantic_nonce: NonceHex
    semantic_payload: SemanticTruthPayload
    semantic_payload_hash: Sha256Hex
    binding_nonce: NonceHex
    decision_binding: DecisionBindingPayload
    binding_payload_hash: Sha256Hex
    native_t4_eligible: StrictBool

    @model_validator(mode="after")
    def component_hashes_match_exact_reveal(
        self,
    ) -> "DecisionTruthBindingReveal":
        nonces = (
            self.numeric_nonce,
            self.semantic_nonce,
            self.binding_nonce,
        )
        if len(set(nonces)) != len(nonces):
            raise ValueError("numeric, semantic, and binding nonces must differ")
        if any(nonce == "0" * 64 for nonce in nonces):
            raise ValueError("all-zero commitment nonces are forbidden")

        numeric_hash = compute_numeric_payload_hash(
            contract_hash=self.contract_hash,
            evaluation_id=self.evaluation_id,
            chain_id=self.chain_id,
            truth_asset_id=self.truth_asset_id,
            sequence_identity_hash=self.sequence_identity_hash,
            condition_spec_hash=self.condition_spec_hash,
            measurement_modality=self.measurement_modality,
            eligibility_status_without_direction=(
                self.eligibility_status_without_direction
            ),
            nonce=self.numeric_nonce,
            payload=self.numeric_payload,
        )
        semantic_hash = compute_semantic_payload_hash(
            contract_hash=self.contract_hash,
            evaluation_id=self.evaluation_id,
            chain_id=self.chain_id,
            truth_asset_id=self.truth_asset_id,
            sequence_identity_hash=self.sequence_identity_hash,
            condition_spec_hash=self.condition_spec_hash,
            measurement_modality=self.measurement_modality,
            eligibility_status_without_direction=(
                self.eligibility_status_without_direction
            ),
            nonce=self.semantic_nonce,
            payload=self.semantic_payload,
        )
        binding_hash = compute_binding_payload_hash(
            contract_hash=self.contract_hash,
            evaluation_id=self.evaluation_id,
            chain_id=self.chain_id,
            truth_asset_id=self.truth_asset_id,
            sequence_identity_hash=self.sequence_identity_hash,
            condition_spec_hash=self.condition_spec_hash,
            measurement_modality=self.measurement_modality,
            eligibility_status_without_direction=(
                self.eligibility_status_without_direction
            ),
            numeric_payload_hash=numeric_hash,
            semantic_payload_hash=semantic_hash,
            nonce=self.binding_nonce,
            payload=self.decision_binding,
            native_t4_eligible=self.native_t4_eligible,
        )
        if self.numeric_payload_hash != numeric_hash:
            raise ValueError("numeric payload commitment mismatch")
        if self.semantic_payload_hash != semantic_hash:
            raise ValueError("semantic payload commitment mismatch")
        if self.binding_payload_hash != binding_hash:
            raise ValueError("decision-binding payload commitment mismatch")
        return self


def build_decision_truth_binding_reveal(
    *,
    evaluation_id: str,
    chain_id: str,
    truth_asset_id: str,
    sequence_identity_hash: str,
    condition_spec_hash: str,
    measurement_modality: RegistryRef,
    eligibility_status_without_direction: RegistryRef,
    numeric_nonce: str,
    numeric_payload: NumericTruthPayload,
    semantic_nonce: str,
    semantic_payload: SemanticTruthPayload,
    binding_nonce: str,
    decision_binding: DecisionBindingPayload,
    native_t4_eligible: bool,
) -> DecisionTruthBindingReveal:
    """Build a reveal while deriving all three registered commitments."""

    numeric_hash = compute_numeric_payload_hash(
        contract_hash=FROZEN_CONTRACT_SHA256,
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        truth_asset_id=truth_asset_id,
        sequence_identity_hash=sequence_identity_hash,
        condition_spec_hash=condition_spec_hash,
        measurement_modality=measurement_modality,
        eligibility_status_without_direction=(
            eligibility_status_without_direction
        ),
        nonce=numeric_nonce,
        payload=numeric_payload,
    )
    semantic_hash = compute_semantic_payload_hash(
        contract_hash=FROZEN_CONTRACT_SHA256,
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        truth_asset_id=truth_asset_id,
        sequence_identity_hash=sequence_identity_hash,
        condition_spec_hash=condition_spec_hash,
        measurement_modality=measurement_modality,
        eligibility_status_without_direction=(
            eligibility_status_without_direction
        ),
        nonce=semantic_nonce,
        payload=semantic_payload,
    )
    binding_hash = compute_binding_payload_hash(
        contract_hash=FROZEN_CONTRACT_SHA256,
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        truth_asset_id=truth_asset_id,
        sequence_identity_hash=sequence_identity_hash,
        condition_spec_hash=condition_spec_hash,
        measurement_modality=measurement_modality,
        eligibility_status_without_direction=(
            eligibility_status_without_direction
        ),
        numeric_payload_hash=numeric_hash,
        semantic_payload_hash=semantic_hash,
        nonce=binding_nonce,
        payload=decision_binding,
        native_t4_eligible=native_t4_eligible,
    )
    return DecisionTruthBindingReveal(
        contract_hash=FROZEN_CONTRACT_SHA256,
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        truth_asset_id=truth_asset_id,
        sequence_identity_hash=sequence_identity_hash,
        condition_spec_hash=condition_spec_hash,
        measurement_modality=measurement_modality,
        eligibility_status_without_direction=(
            eligibility_status_without_direction
        ),
        numeric_nonce=numeric_nonce,
        numeric_payload=numeric_payload,
        numeric_payload_hash=numeric_hash,
        semantic_nonce=semantic_nonce,
        semantic_payload=semantic_payload,
        semantic_payload_hash=semantic_hash,
        binding_nonce=binding_nonce,
        decision_binding=decision_binding,
        binding_payload_hash=binding_hash,
        native_t4_eligible=native_t4_eligible,
    )


def serialize_truth_reveal_package(
    reveal: DecisionTruthBindingReveal,
) -> str:
    """Return the one registered canonical UTF-8 package representation."""

    if type(reveal) is not DecisionTruthBindingReveal:
        raise TypeError(
            "truth reveal serializer requires exactly DecisionTruthBindingReveal"
        )
    reveal = strict_revalidate_contract_model(reveal)
    return canonical_json_bytes(reveal).decode("utf-8")


def parse_truth_reveal_package(
    raw: str | bytes | bytearray,
) -> DecisionTruthBindingReveal:
    """Duplicate-safe parse that also rejects non-canonical raw bytes."""

    reveal = parse_contract_json(DecisionTruthBindingReveal, raw)
    exact = (
        raw.encode("utf-8")
        if isinstance(raw, str)
        else bytes(raw)
    )
    if exact != canonical_json_bytes(reveal):
        raise ValueError(
            "truth reveal package is not the registered canonical UTF-8 bytes"
        )
    return reveal


def truth_reveal_asset_hash(raw: str | bytes | bytearray) -> str:
    """SHA-256 over exact sealed reveal-package bytes."""

    exact = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
    exact.decode("utf-8", errors="strict")
    return hashlib.sha256(exact).hexdigest()
