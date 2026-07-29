"""Payload-bound A-C locks and complete raw Lock-D reveal verification."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
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
from .truth import (
    DecisionTruthBindingReveal,
    FROZEN_CONTRACT_SHA256,
    TruthAssetCommitment,
    parse_truth_reveal_package,
    truth_reveal_asset_hash,
)


LOCK_LINK_SCHEMA_ID = "d2t_rna.lock_link"
LOCK_LINK_SCHEMA_VERSION = "1.0"
SEALED_PAYLOAD_SCHEMA_ID = "d2t_rna.sealed_truth_lock_payload"
SEALED_PAYLOAD_SCHEMA_VERSION = "1.0"
REVEAL_PAYLOAD_SCHEMA_ID = "d2t_rna.decision_truth_binding_reveal"
REVEAL_PAYLOAD_SCHEMA_VERSION = "1.0"

RawJson: TypeAlias = str | bytes | bytearray


def current_lock_verifier_code_hash() -> str:
    """Hash the exact executing verifier source rather than trusting D input."""

    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


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
        asset_ids = tuple(asset.truth_asset_id for asset in self.truth_assets)
        if not asset_ids:
            raise ValueError("pre-reveal truth commitment set cannot be empty")
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("pre-reveal truth asset IDs must be unique")
        if asset_ids != tuple(sorted(asset_ids)):
            raise ValueError(
                "pre-reveal truth commitments must be sorted by truth_asset_id"
            )
        from d2t_rna.data.sanitize import pre_d_public_text_rule

        public_identifiers = (
            identifier
            for asset in self.truth_assets
            for identifier in (
                asset.truth_asset_id,
                asset.measurement_modality.registry_id,
                asset.eligibility_status_without_direction.registry_id,
            )
        )
        if any(
            pre_d_public_text_rule(identifier) is not None
            for identifier in public_identifiers
        ):
            raise ValueError(
                "pre-reveal public truth identifiers carry registered semantics"
            )
        return self


class SanitizerReceiptBinding(FrozenContractModel):
    """Bind one public planning-package root to its redacted sanitizer report."""

    schema_id: Literal["d2t_rna.sanitizer_receipt_binding"] = (
        "d2t_rna.sanitizer_receipt_binding"
    )
    schema_version: Literal["1.0"] = "1.0"
    stage: LockStage
    planning_package_root_hash: Sha256Hex
    sanitizer_report_hash: Sha256Hex
    disposition: Literal[
        "NO_REGISTERED_LEAKAGE_DETECTED",
        "EVALUATION_INVALIDATED_PRE_LOCK_D",
        "AUDIT_INCOMPLETE_FAIL_CLOSED",
    ]

    @model_validator(mode="after")
    def stage_is_pre_reveal(self) -> "SanitizerReceiptBinding":
        if self.stage is LockStage.D:
            raise ValueError("Lock D cannot be a pre-reveal sanitizer receipt")
        return self


class RawTruthAssetPackage(FrozenContractModel):
    """Exact canonical reveal JSON carried as a string inside the D bundle."""

    schema_id: Literal["d2t_rna.raw_truth_asset_package"] = (
        "d2t_rna.raw_truth_asset_package"
    )
    schema_version: Literal["1.0"] = "1.0"
    truth_asset_id: RegisteredId
    raw_package_json: str

    @model_validator(mode="after")
    def raw_package_is_nonempty_utf8(self) -> "RawTruthAssetPackage":
        if not self.raw_package_json:
            raise ValueError("raw truth reveal package cannot be empty")
        self.raw_package_json.encode("utf-8", errors="strict")
        return self


class LockDRevealPayload(FrozenContractModel):
    """Top-level D bundle; its link commits to exact embedded raw packages."""

    schema_id: Literal["d2t_rna.decision_truth_binding_reveal"] = (
        "d2t_rna.decision_truth_binding_reveal"
    )
    schema_version: Literal["1.0"] = "1.0"
    stage: Literal[LockStage.D] = LockStage.D
    evaluation_id: RegisteredId
    chain_id: RegisteredId
    claimed_pre_reveal_audit_status: Literal[
        "NO_EARLY_REVEAL_OBSERVED",
        "EVALUATION_INVALID_EARLY_REVEAL",
        "AUDIT_INCOMPLETE_FAIL_CLOSED",
    ]
    pre_reveal_audit_hash: Sha256Hex
    sanitizer_receipts: tuple[SanitizerReceiptBinding, ...]
    truth_asset_packages: tuple[RawTruthAssetPackage, ...]

    @model_validator(mode="after")
    def collections_are_complete_unique_and_sorted(
        self,
    ) -> "LockDRevealPayload":
        from d2t_rna.data.sanitize import pre_d_public_text_rule

        if (
            pre_d_public_text_rule(self.evaluation_id) is not None
            or pre_d_public_text_rule(self.chain_id) is not None
        ):
            raise ValueError(
                "D evaluation or chain identifier carries registered semantics"
            )
        receipt_stages = tuple(
            receipt.stage for receipt in self.sanitizer_receipts
        )
        if receipt_stages != (LockStage.A, LockStage.B, LockStage.C):
            raise ValueError(
                "D reveal requires exactly ordered sanitizer receipts A, B, C"
            )
        asset_ids = tuple(
            package.truth_asset_id for package in self.truth_asset_packages
        )
        if not asset_ids:
            raise ValueError("D reveal truth asset package set cannot be empty")
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("D reveal truth asset IDs must be unique")
        if asset_ids != tuple(sorted(asset_ids)):
            raise ValueError(
                "D reveal packages must be sorted by truth_asset_id"
            )
        return self


class LockDVerificationCredential(FrozenContractModel):
    """Structural receipt; no chronology/access authority exists in Task 3."""

    schema_id: Literal["d2t_rna.lock_d_verification_credential"] = (
        "d2t_rna.lock_d_verification_credential"
    )
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED"]
    scoring_allowed: Literal[False]
    authorization_blocker: Literal[
        "AUTHENTICATED_CHRONOLOGY_AND_BOUND_ARTIFACT_REPLAY_UNAVAILABLE"
    ]
    contract_hash: Literal[
        "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
    ]
    evaluation_id: RegisteredId
    chain_id: RegisteredId
    a_to_d_lock_hashes: tuple[
        Sha256Hex,
        Sha256Hex,
        Sha256Hex,
        Sha256Hex,
    ]
    terminal_lock_hash: Sha256Hex
    commitment_set_hash: Sha256Hex
    reveal_payload_hash: Sha256Hex
    raw_asset_package_manifest_hash: Sha256Hex
    validated_truth_asset_ids: tuple[RegisteredId, ...]
    certificate_hash: Sha256Hex
    frozen_decision_output_hash: Sha256Hex
    evaluation_plan_hash: Sha256Hex
    scoring_spec_hash: Sha256Hex
    decision_binding_hash: Sha256Hex
    claimed_pre_reveal_audit_hash: Sha256Hex
    sanitizer_report_hashes: tuple[Sha256Hex, Sha256Hex, Sha256Hex]
    verifier_code_hash: Sha256Hex
    historical_exposure_registry_hash: Sha256Hex


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
        from d2t_rna.data.sanitize import pre_d_public_text_rule

        if pre_d_public_text_rule(self.chain_id) is not None:
            raise ValueError("lock chain ID carries registered truth semantics")
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


def _strict_d_payload(value: object) -> LockDRevealPayload:
    if type(value) is not LockDRevealPayload:
        raise TypeError("Lock D payload must be exactly LockDRevealPayload")
    return strict_revalidate_contract_model(value)


def _commitment_set_hash(
    truth_assets: tuple[TruthAssetCommitment, ...],
) -> str:
    return canonical_sha256(
        {
            "schema_id": "d2t_rna.truth_commitment_set",
            "schema_version": "1.0",
            "truth_assets": truth_assets,
        }
    )


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


def make_lock_d_link(
    *,
    chain_id: str,
    payload: LockDRevealPayload,
    previous_link: LockLink,
) -> LockLink:
    """Build D only from a strict reveal bundle and the exact Lock C link."""

    payload = _strict_d_payload(payload)
    previous_link = _strict_lock_link(previous_link)
    if payload.chain_id != chain_id:
        raise ValueError("D reveal payload belongs to a different chain")
    if previous_link.chain_id != chain_id:
        raise ValueError("Lock C predecessor belongs to a different chain")
    if previous_link.stage is not LockStage.C:
        raise ValueError("Lock D requires the immediately preceding Lock C")
    return make_topology_link(
        chain_id=chain_id,
        stage=LockStage.D,
        payload_schema_id=payload.schema_id,
        payload_schema_version=payload.schema_version,
        payload_hash=canonical_sha256(payload),
        previous_lock_hash=previous_link.lock_hash,
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


def _validate_d_payload_binding(
    link: LockLink,
    payload: LockDRevealPayload,
) -> None:
    link = _strict_lock_link(link)
    payload = _strict_d_payload(payload)
    if link.stage is not LockStage.D or payload.stage is not LockStage.D:
        raise ValueError("D payload binding requires Lock D")
    if link.chain_id != payload.chain_id:
        raise ValueError("D link and payload chain IDs differ")
    if link.payload_schema_id != payload.schema_id:
        raise ValueError("D link payload schema ID mismatch")
    if link.payload_schema_version != payload.schema_version:
        raise ValueError("D link payload schema version mismatch")
    if link.payload_hash != canonical_sha256(payload):
        raise ValueError("D link payload hash mismatch")


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
    payloads: list[SealedTruthLockPayload] = []
    for raw_link, raw_payload in records:
        link = parse_contract_json(LockLink, raw_link)
        payload = parse_contract_json(SealedTruthLockPayload, raw_payload)
        validate_lock_payload_binding(link, payload)
        links.append(link)
        payloads.append(payload)
    validate_lock_topology(links, require_complete=False)
    if links[-1].stage is not expected_terminal_stage:
        raise ValueError("pre-reveal chain ended at the wrong stage")
    commitment_roots = {
        _commitment_set_hash(payload.truth_assets) for payload in payloads
    }
    if len(commitment_roots) != 1:
        raise ValueError(
            "A-C truth commitment set changed after initial registration"
        )
    return tuple(links)


def validate_complete_payload_bound_chain(
    records: Sequence[tuple[RawJson, RawJson]],
    *,
    planning_package_roots: tuple[str | Path, str | Path, str | Path],
) -> LockDVerificationCredential:
    """Replay raw A-D records and bind every reveal byte before scoring."""

    if len(records) != 4:
        raise ValueError("complete payload-bound chain requires four raw records")
    if type(planning_package_roots) is not tuple:
        raise TypeError("planning package roots must be an exact A-B-C tuple")
    if len(planning_package_roots) != 3:
        raise ValueError("planning package roots must contain exactly A, B, C")

    pre_links = validate_pre_reveal_chain(
        records[:3],
        expected_terminal_stage=LockStage.C,
    )
    sealed_payloads = tuple(
        parse_contract_json(SealedTruthLockPayload, raw_payload)
        for _, raw_payload in records[:3]
    )
    d_link = parse_contract_json(LockLink, records[3][0])
    d_payload = parse_contract_json(LockDRevealPayload, records[3][1])
    _validate_d_payload_binding(d_link, d_payload)

    all_links = (*pre_links, d_link)
    validate_lock_topology(all_links, require_complete=True)
    if d_payload.chain_id != pre_links[0].chain_id:
        raise ValueError("D reveal is bound to a different chain")
    if (
        d_payload.claimed_pre_reveal_audit_status
        != "NO_EARLY_REVEAL_OBSERVED"
    ):
        raise ValueError(
            "pre-reveal access audit invalidated or incomplete; scoring stops"
        )

    commitment_roots = tuple(
        _commitment_set_hash(payload.truth_assets)
        for payload in sealed_payloads
    )
    if len(set(commitment_roots)) != 1:
        raise ValueError("A-C commitment set drift detected")
    commitment_set_hash = commitment_roots[0]
    commitments = sealed_payloads[0].truth_assets
    commitments_by_id = {
        commitment.truth_asset_id: commitment for commitment in commitments
    }

    from d2t_rna.data.sanitize import (
        HISTORICAL_EXPOSURE_REGISTRY,
        assert_pre_reveal_audit_clean,
        audit_planning_package,
        sanitizer_report_hash,
    )

    sanitizer_reports = tuple(
        audit_planning_package(
            evaluation_id=d_payload.evaluation_id,
            stage=payload.stage,
            package_root=package_root,
        )
        for payload, package_root in zip(
            sealed_payloads,
            planning_package_roots,
            strict=True,
        )
    )
    for payload, receipt, report in zip(
        sealed_payloads,
        d_payload.sanitizer_receipts,
        sanitizer_reports,
        strict=True,
    ):
        assert_pre_reveal_audit_clean(report)
        if receipt.stage is not payload.stage:
            raise ValueError("sanitizer receipt stage does not match lock stage")
        if report.stage is not payload.stage:
            raise ValueError("replayed sanitizer report stage mismatch")
        if report.evaluation_id != d_payload.evaluation_id:
            raise ValueError("replayed sanitizer evaluation mismatch")
        if receipt.disposition != "NO_REGISTERED_LEAKAGE_DETECTED":
            raise ValueError("pre-D sanitizer invalidated or incomplete")
        if (
            receipt.planning_package_root_hash
            != payload.public_payload_hash
            or report.source_package_hash != payload.public_payload_hash
        ):
            raise ValueError(
                "sanitizer receipt is bound to a different planning package"
            )
        if (
            receipt.sanitizer_report_hash
            != sanitizer_report_hash(report)
        ):
            raise ValueError("sanitizer report hash does not replay")

    package_ids = tuple(
        package.truth_asset_id
        for package in d_payload.truth_asset_packages
    )
    committed_ids = tuple(commitments_by_id)
    if package_ids != committed_ids:
        raise ValueError(
            "D reveal assets do not exactly equal the A-C commitment set"
        )

    revealed_assets: list[DecisionTruthBindingReveal] = []
    asset_manifest: list[dict[str, object]] = []
    decision_binding_hash: str | None = None
    for package in d_payload.truth_asset_packages:
        commitment = commitments_by_id[package.truth_asset_id]
        reveal = parse_truth_reveal_package(package.raw_package_json)
        if reveal.truth_asset_id != package.truth_asset_id:
            raise ValueError("D reveal wrapper and package asset IDs differ")
        if (
            reveal.contract_hash != FROZEN_CONTRACT_SHA256
            or reveal.evaluation_id != d_payload.evaluation_id
            or reveal.chain_id != d_payload.chain_id
        ):
            raise ValueError(
                "truth reveal contract, evaluation, or chain context mismatch"
            )
        observed_asset_hash = truth_reveal_asset_hash(
            package.raw_package_json
        )
        if observed_asset_hash != commitment.asset_hash:
            raise ValueError("exact raw reveal package hash mismatch")
        if (
            reveal.sequence_identity_hash
            != commitment.sequence_identity_hash
            or reveal.condition_spec_hash != commitment.condition_spec_hash
            or reveal.measurement_modality
            != commitment.measurement_modality
            or reveal.eligibility_status_without_direction
            != commitment.eligibility_status_without_direction
        ):
            raise ValueError("truth reveal context does not match commitment")
        if (
            reveal.numeric_payload_hash
            != commitment.numeric_payload_hash
        ):
            raise ValueError("numeric reveal commitment mismatch")
        if (
            reveal.semantic_payload_hash
            != commitment.semantic_payload_hash
        ):
            raise ValueError("semantic reveal commitment mismatch")

        current_binding_hash = canonical_sha256(reveal.decision_binding)
        if decision_binding_hash is None:
            decision_binding_hash = current_binding_hash
        elif current_binding_hash != decision_binding_hash:
            raise ValueError(
                "truth assets are bound to different scoring inputs"
            )
        revealed_assets.append(reveal)
        asset_manifest.append(
            {
                "binding_payload_hash": reveal.binding_payload_hash,
                "condition_spec_hash": reveal.condition_spec_hash,
                "numeric_payload_hash": reveal.numeric_payload_hash,
                "raw_asset_hash": observed_asset_hash,
                "semantic_payload_hash": reveal.semantic_payload_hash,
                "sequence_identity_hash": reveal.sequence_identity_hash,
                "truth_asset_id": reveal.truth_asset_id,
            }
        )

    if not revealed_assets:
        raise ValueError("D reveal did not validate any truth assets")
    common_binding = revealed_assets[0].decision_binding
    return LockDVerificationCredential(
        status="STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED",
        scoring_allowed=False,
        authorization_blocker=(
            "AUTHENTICATED_CHRONOLOGY_AND_BOUND_ARTIFACT_REPLAY_UNAVAILABLE"
        ),
        contract_hash=FROZEN_CONTRACT_SHA256,
        evaluation_id=d_payload.evaluation_id,
        chain_id=d_payload.chain_id,
        a_to_d_lock_hashes=tuple(link.lock_hash for link in all_links),
        terminal_lock_hash=d_link.lock_hash,
        commitment_set_hash=commitment_set_hash,
        reveal_payload_hash=canonical_sha256(d_payload),
        raw_asset_package_manifest_hash=canonical_sha256(
            {
                "assets": tuple(asset_manifest),
                "schema_id": "d2t_rna.raw_asset_package_manifest",
                "schema_version": "1.0",
            }
        ),
        validated_truth_asset_ids=tuple(
            reveal.truth_asset_id for reveal in revealed_assets
        ),
        certificate_hash=common_binding.certificate_hash,
        frozen_decision_output_hash=(
            common_binding.frozen_decision_output_hash
        ),
        evaluation_plan_hash=common_binding.evaluation_plan_hash,
        scoring_spec_hash=common_binding.scoring_spec_hash,
        decision_binding_hash=canonical_sha256(common_binding),
        claimed_pre_reveal_audit_hash=d_payload.pre_reveal_audit_hash,
        sanitizer_report_hashes=tuple(
            sanitizer_report_hash(report)
            for report in sanitizer_reports
        ),
        verifier_code_hash=current_lock_verifier_code_hash(),
        historical_exposure_registry_hash=canonical_sha256(
            HISTORICAL_EXPOSURE_REGISTRY
        ),
    )


def validate_lock_d_credential_against_raw(
    records: Sequence[tuple[RawJson, RawJson]],
    credential: object,
    *,
    planning_package_roots: tuple[str | Path, str | Path, str | Path],
) -> None:
    """Rerun raw verification; serialized credentials are never bearer tokens."""

    if type(credential) is not LockDVerificationCredential:
        raise TypeError(
            "scoring requires exactly a LockDVerificationCredential"
        )
    credential = strict_revalidate_contract_model(credential)
    replayed = validate_complete_payload_bound_chain(
        records,
        planning_package_roots=planning_package_roots,
    )
    if canonical_sha256(credential) != canonical_sha256(replayed):
        raise ValueError(
            "Lock D credential does not match replayed raw evaluation inputs"
        )


def require_lock_d_scoring_authorization(
    credential: object,
) -> None:
    """Fail closed until chronology, access, and artifact replay are verified."""

    if type(credential) is not LockDVerificationCredential:
        raise TypeError(
            "scoring requires exactly a LockDVerificationCredential"
        )
    credential = strict_revalidate_contract_model(credential)
    if credential.scoring_allowed is not True:
        raise RuntimeError(credential.authorization_blocker)
