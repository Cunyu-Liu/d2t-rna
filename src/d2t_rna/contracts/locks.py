"""Payload-bound A-C locks and topology-only A-D verification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypeAlias

from pydantic import model_validator

from .base import (
    FrozenContractModel,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
)
from .enums import LockStage
from .primitives import RegisteredId, SchemaVersion, Sha256Hex
from .truth import TruthAssetCommitment


LOCK_LINK_SCHEMA_ID = "d2t_rna.lock_link"
LOCK_LINK_SCHEMA_VERSION = "1.0"
SEALED_PAYLOAD_SCHEMA_ID = "d2t_rna.sealed_truth_lock_payload"
SEALED_PAYLOAD_SCHEMA_VERSION = "1.0"
REVEAL_PAYLOAD_SCHEMA_ID = "d2t_rna.decision_truth_binding_reveal"
REVEAL_PAYLOAD_SCHEMA_VERSION = "1.0"

RawJson: TypeAlias = str | bytes | bytearray


class SealedTruthLockPayload(FrozenContractModel):
    schema_id: Literal["d2t_rna.sealed_truth_lock_payload"] = (
        "d2t_rna.sealed_truth_lock_payload"
    )
    schema_version: Literal["1.0"] = "1.0"
    stage: LockStage
    public_payload_hash: Sha256Hex
    truth_assets: tuple[TruthAssetCommitment, ...]

    @model_validator(mode="after")
    def stage_is_pre_reveal(self) -> "SealedTruthLockPayload":
        if self.stage is LockStage.D:
            raise ValueError("Lock D requires the reveal schema from Task 3")
        return self


def _expected_payload_schema(stage: LockStage) -> tuple[str, str]:
    if stage is LockStage.D:
        return REVEAL_PAYLOAD_SCHEMA_ID, REVEAL_PAYLOAD_SCHEMA_VERSION
    return SEALED_PAYLOAD_SCHEMA_ID, SEALED_PAYLOAD_SCHEMA_VERSION


def _lock_core(
    *,
    schema_id: str,
    schema_version: str,
    chain_id: str,
    stage: LockStage,
    payload_schema_id: str,
    payload_schema_version: str,
    payload_hash: str,
    previous_lock_hash: str | None,
) -> dict[str, object]:
    return {
        "chain_id": chain_id,
        "payload_hash": payload_hash,
        "payload_schema_id": payload_schema_id,
        "payload_schema_version": payload_schema_version,
        "previous_lock_hash": previous_lock_hash,
        "schema_id": schema_id,
        "schema_version": schema_version,
        "stage": stage.value,
    }


class LockLink(FrozenContractModel):
    schema_id: Literal["d2t_rna.lock_link"] = "d2t_rna.lock_link"
    schema_version: Literal["1.0"] = "1.0"
    chain_id: RegisteredId
    stage: LockStage
    payload_schema_id: RegisteredId
    payload_schema_version: SchemaVersion
    payload_hash: Sha256Hex
    previous_lock_hash: Sha256Hex | None
    lock_hash: Sha256Hex

    @model_validator(mode="after")
    def registered_schema_and_digest_match(self) -> "LockLink":
        expected_schema = _expected_payload_schema(self.stage)
        observed_schema = (
            self.payload_schema_id,
            self.payload_schema_version,
        )
        if observed_schema != expected_schema:
            raise ValueError(
                "payload schema is not registered for this lock stage"
            )
        expected_hash = canonical_sha256(
            _lock_core(
                schema_id=self.schema_id,
                schema_version=self.schema_version,
                chain_id=self.chain_id,
                stage=self.stage,
                payload_schema_id=self.payload_schema_id,
                payload_schema_version=self.payload_schema_version,
                payload_hash=self.payload_hash,
                previous_lock_hash=self.previous_lock_hash,
            )
        )
        if self.lock_hash != expected_hash:
            raise ValueError("lock_hash does not match the canonical link core")
        return self


def _strict_lock_link(value: object) -> LockLink:
    if type(value) is not LockLink:
        raise TypeError("lock verifier requires exactly LockLink")
    return strict_revalidate_contract_model(value)


def _strict_sealed_payload(value: object) -> SealedTruthLockPayload:
    if type(value) is not SealedTruthLockPayload:
        raise TypeError("A-C payload must be exactly SealedTruthLockPayload")
    return strict_revalidate_contract_model(value)


def make_topology_link(
    *,
    chain_id: str,
    stage: LockStage,
    payload_schema_id: str,
    payload_schema_version: str,
    payload_hash: str,
    previous_lock_hash: str | None,
) -> LockLink:
    """Build one registered topology link from an already computed digest."""

    core = _lock_core(
        schema_id=LOCK_LINK_SCHEMA_ID,
        schema_version=LOCK_LINK_SCHEMA_VERSION,
        chain_id=chain_id,
        stage=stage,
        payload_schema_id=payload_schema_id,
        payload_schema_version=payload_schema_version,
        payload_hash=payload_hash,
        previous_lock_hash=previous_lock_hash,
    )
    return LockLink(
        chain_id=chain_id,
        stage=stage,
        payload_schema_id=payload_schema_id,
        payload_schema_version=payload_schema_version,
        payload_hash=payload_hash,
        previous_lock_hash=previous_lock_hash,
        lock_hash=canonical_sha256(core),
    )


def make_pre_reveal_lock_link(
    *,
    chain_id: str,
    payload: SealedTruthLockPayload,
    previous_link: LockLink | None,
) -> LockLink:
    """Build an A-C link while deriving every payload commitment field."""

    payload = _strict_sealed_payload(payload)
    expected_stages = tuple(LockStage)
    stage_index = expected_stages.index(payload.stage)
    if stage_index > 2:
        raise ValueError("Lock D payload verification is deferred to Task 3")
    if stage_index == 0:
        if previous_link is not None:
            raise ValueError("Lock A cannot have a predecessor")
        previous_hash = None
    else:
        if previous_link is None:
            raise ValueError("Lock B or C requires the previous link")
        previous_link = _strict_lock_link(previous_link)
        if previous_link.chain_id != chain_id:
            raise ValueError("predecessor belongs to a different chain")
        if previous_link.stage is not expected_stages[stage_index - 1]:
            raise ValueError("predecessor is not the immediately prior stage")
        previous_hash = previous_link.lock_hash
    return make_topology_link(
        chain_id=chain_id,
        stage=payload.stage,
        payload_schema_id=payload.schema_id,
        payload_schema_version=payload.schema_version,
        payload_hash=canonical_sha256(payload),
        previous_lock_hash=previous_hash,
    )


def validate_lock_payload_binding(
    link: LockLink,
    payload: SealedTruthLockPayload,
) -> None:
    """Strictly rebuild and bind one A-C link to its actual payload."""

    link = _strict_lock_link(link)
    payload = _strict_sealed_payload(payload)
    if link.stage is LockStage.D:
        raise ValueError("Lock D payload verification is deferred to Task 3")
    if link.stage is not payload.stage:
        raise ValueError("link stage does not match payload stage")
    if link.payload_schema_id != payload.schema_id:
        raise ValueError("link payload_schema_id does not match actual payload")
    if link.payload_schema_version != payload.schema_version:
        raise ValueError(
            "link payload_schema_version does not match actual payload"
        )
    if link.payload_hash != canonical_sha256(payload):
        raise ValueError("link payload_hash does not match actual payload")


def validate_lock_topology(
    links: Sequence[LockLink],
    *,
    require_complete: bool,
) -> None:
    """Strictly rebuild links and enforce one exact A-B-C-D prefix."""

    if not links:
        raise ValueError("lock chain is empty")
    validated_links = tuple(_strict_lock_link(link) for link in links)
    expected_stages = tuple(LockStage)
    if len(validated_links) > len(expected_stages):
        raise ValueError("lock chain contains more than A-B-C-D")
    if require_complete and len(validated_links) != len(expected_stages):
        raise ValueError("complete lock topology must contain A-B-C-D")

    chain_id = validated_links[0].chain_id
    previous: str | None = None
    for index, link in enumerate(validated_links):
        if link.stage is not expected_stages[index]:
            raise ValueError("lock stages are not an exact A-B-C-D prefix")
        if link.chain_id != chain_id:
            raise ValueError("cross-chain splice detected")
        if link.previous_lock_hash != previous:
            raise ValueError("lock predecessor digest mismatch")
        previous = link.lock_hash


def validate_pre_reveal_chain(
    records: Sequence[tuple[RawJson, RawJson]],
    *,
    expected_terminal_stage: Literal[LockStage.A, LockStage.B, LockStage.C],
) -> tuple[LockLink, ...]:
    """Validate duplicate-safe raw link/payload records through Lock A-C."""

    if expected_terminal_stage not in (LockStage.A, LockStage.B, LockStage.C):
        raise ValueError("pre-reveal validation stops at Lock A, B, or C")
    expected_length = tuple(LockStage).index(expected_terminal_stage) + 1
    if len(records) != expected_length:
        raise ValueError("pre-reveal record count does not match terminal stage")

    links: list[LockLink] = []
    for raw_link, raw_payload in records:
        link = parse_contract_json(LockLink, raw_link)
        payload = parse_contract_json(SealedTruthLockPayload, raw_payload)
        validate_lock_payload_binding(link, payload)
        links.append(link)
    validate_lock_topology(links, require_complete=False)
    if links[-1].stage is not expected_terminal_stage:
        raise ValueError("pre-reveal chain ended at the wrong stage")
    return tuple(links)


def validate_complete_payload_bound_chain(
    records: Sequence[tuple[RawJson, RawJson]],
) -> None:
    """Fail closed until Task 3 binds raw A-D link and payload records."""

    del records
    raise NotImplementedError(
        "complete payload-bound A-D validation requires the Task 3 reveal schema"
    )
