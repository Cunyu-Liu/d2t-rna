from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import (
    DuplicateJsonKeyError,
    canonical_json_bytes,
    canonical_sha256,
)
from d2t_rna.contracts.enums import LockStage, TruthVisibility
from d2t_rna.contracts.locks import (
    LockDRevealPayload,
    LockDVerificationCredential,
    RawTruthAssetPackage,
    SanitizerReceiptBinding,
    SealedTruthLockPayload,
    make_lock_d_link,
    make_pre_reveal_lock_link,
    require_lock_d_scoring_authorization,
    validate_complete_payload_bound_chain,
    validate_lock_d_credential_against_raw,
    validate_pre_reveal_chain,
)
from d2t_rna.contracts.primitives import NamedBound, Rational, RegistryRef
from d2t_rna.contracts.truth import (
    DecisionBindingPayload,
    DecisionTruthBindingReveal,
    NumericTruthPayload,
    RationalInterval,
    SemanticTruthPayload,
    TruthAssetCommitment,
    build_decision_truth_binding_reveal,
    serialize_truth_reveal_package,
    truth_reveal_asset_hash,
)
from d2t_rna.data.sanitize import (
    audit_planning_package,
    sanitizer_report_hash,
)


EVALUATION_ID = "evaluation.synthetic.001"
CHAIN_ID = "chain.synthetic.001"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def registry(identifier: str) -> RegistryRef:
    return RegistryRef(
        registry_id=identifier,
        registry_hash=digest(f"registry:{identifier}"),
    )


def build_reveal(
    asset_id: str,
    *,
    suffix: str,
    evaluation_id: str = EVALUATION_ID,
    chain_id: str = CHAIN_ID,
    numeric_nonce_label: str | None = None,
) -> DecisionTruthBindingReveal:
    return build_decision_truth_binding_reveal(
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        truth_asset_id=asset_id,
        sequence_identity_hash=digest(f"sequence:{suffix}"),
        condition_spec_hash=digest(f"condition:{suffix}"),
        measurement_modality=registry("modality.synthetic_counts"),
        eligibility_status_without_direction=registry(
            "eligibility.registered_without_direction"
        ),
        numeric_nonce=digest(
            numeric_nonce_label or f"numeric-nonce:{suffix}"
        ),
        numeric_payload=NumericTruthPayload(
            population_estimate=Rational(numerator=3, denominator=5),
            confidence_region=RationalInterval(
                lower=Rational(numerator=1, denominator=2),
                upper=Rational(numerator=7, denominator=10),
            ),
            projected_state_proportions=(
                NamedBound(
                    bound_id="state.alpha",
                    value=Rational(numerator=2, denominator=5),
                ),
                NamedBound(
                    bound_id="state.beta",
                    value=Rational(numerator=3, denominator=5),
                ),
            ),
        ),
        semantic_nonce=digest(f"semantic-nonce:{suffix}"),
        semantic_payload=SemanticTruthPayload(
            directional_evidence=(registry("direction.registered.alpha"),),
            state_preservation_result=registry("state.preserved"),
            action_effect_labels=(registry("action.registered.alpha"),),
        ),
        binding_nonce=digest(f"binding-nonce:{suffix}"),
        decision_binding=DecisionBindingPayload(
            h0_binding=registry("hypothesis.h0.registered"),
            h1_binding=registry("hypothesis.h1.registered"),
            coverage_core_binding=registry("coverage.core.registered"),
            certificate_hash=digest("certificate"),
            frozen_decision_output_hash=digest("decision-output"),
            evaluation_plan_hash=digest("evaluation-plan"),
            scoring_spec_hash=digest("scoring-spec"),
        ),
        native_t4_eligible=False,
    )


def commitment_for(reveal: DecisionTruthBindingReveal) -> TruthAssetCommitment:
    raw = serialize_truth_reveal_package(reveal)
    return TruthAssetCommitment(
        truth_asset_id=reveal.truth_asset_id,
        asset_hash=truth_reveal_asset_hash(raw),
        sequence_identity_hash=reveal.sequence_identity_hash,
        condition_spec_hash=reveal.condition_spec_hash,
        measurement_modality=reveal.measurement_modality,
        eligibility_status_without_direction=(
            reveal.eligibility_status_without_direction
        ),
        numeric_payload_hash=reveal.numeric_payload_hash,
        semantic_payload_hash=reveal.semantic_payload_hash,
        visibility=TruthVisibility.HASH_ONLY,
    )


def build_chain(
    tmp_path: Path,
    reveals: tuple[DecisionTruthBindingReveal, ...] | None = None,
    *,
    evaluation_id: str = EVALUATION_ID,
    chain_id: str = CHAIN_ID,
    claimed_pre_reveal_audit_status: str = "NO_EARLY_REVEAL_OBSERVED",
    run_label: str = "default",
):
    if reveals is None:
        reveals = (
            build_reveal(
                "truth.synthetic.001",
                suffix="one",
                evaluation_id=evaluation_id,
                chain_id=chain_id,
            ),
        )
    commitments = tuple(
        sorted(
            (commitment_for(reveal) for reveal in reveals),
            key=lambda item: item.truth_asset_id,
        )
    )
    links = []
    sealed_payloads = []
    receipts = []
    package_roots = []
    previous = None
    package_base = tmp_path / f"packages-{run_label}"
    for stage in (LockStage.A, LockStage.B, LockStage.C):
        root = package_base / stage.value.lower()
        root.mkdir(parents=True)
        (root / "public.txt").write_text(
            f"masked stage {stage.value}\n",
            encoding="utf-8",
        )
        report = audit_planning_package(
            evaluation_id=evaluation_id,
            stage=stage,
            package_root=root,
        )
        payload = SealedTruthLockPayload(
            stage=stage,
            public_payload_hash=report.source_package_hash,
            truth_assets=commitments,
        )
        link = make_pre_reveal_lock_link(
            chain_id=chain_id,
            payload=payload,
            previous_link=previous,
        )
        links.append(link)
        sealed_payloads.append(payload)
        package_roots.append(root)
        receipts.append(
            SanitizerReceiptBinding(
                stage=stage,
                planning_package_root_hash=report.source_package_hash,
                sanitizer_report_hash=sanitizer_report_hash(report),
                disposition="NO_REGISTERED_LEAKAGE_DETECTED",
            )
        )
        previous = link

    d_payload = LockDRevealPayload(
        evaluation_id=evaluation_id,
        chain_id=chain_id,
        claimed_pre_reveal_audit_status=(
            claimed_pre_reveal_audit_status
        ),
        pre_reveal_audit_hash=digest("claimed-pre-reveal-access-audit"),
        sanitizer_receipts=tuple(receipts),
        truth_asset_packages=tuple(
            RawTruthAssetPackage(
                truth_asset_id=reveal.truth_asset_id,
                raw_package_json=serialize_truth_reveal_package(reveal),
            )
            for reveal in sorted(reveals, key=lambda item: item.truth_asset_id)
        ),
    )
    d_link = make_lock_d_link(
        chain_id=chain_id,
        payload=d_payload,
        previous_link=previous,
    )
    links.append(d_link)
    records = tuple(
        (
            canonical_json_bytes(link).decode("utf-8"),
            canonical_json_bytes(payload).decode("utf-8"),
        )
        for link, payload in zip(links[:3], sealed_payloads, strict=True)
    ) + (
        (
            canonical_json_bytes(d_link).decode("utf-8"),
            canonical_json_bytes(d_payload).decode("utf-8"),
        ),
    )
    return (
        records,
        tuple(links),
        tuple(sealed_payloads),
        d_payload,
        tuple(package_roots),
    )


def rebuilt_d_record(
    links,
    d_payload: LockDRevealPayload,
) -> tuple[str, str]:
    d_link = make_lock_d_link(
        chain_id=d_payload.chain_id,
        payload=d_payload,
        previous_link=links[2],
    )
    return (
        canonical_json_bytes(d_link).decode("utf-8"),
        canonical_json_bytes(d_payload).decode("utf-8"),
    )


def test_component_hashes_are_domain_separated_nonce_and_context_bound() -> None:
    base = build_reveal("truth.synthetic.001", suffix="one")
    new_nonce = build_reveal(
        "truth.synthetic.001",
        suffix="one",
        numeric_nonce_label="different-numeric-nonce",
    )
    new_evaluation = build_reveal(
        "truth.synthetic.001",
        suffix="one",
        evaluation_id="evaluation.synthetic.002",
    )
    assert base.numeric_payload == new_nonce.numeric_payload
    assert base.numeric_payload_hash != new_nonce.numeric_payload_hash
    assert base.semantic_payload_hash == new_nonce.semantic_payload_hash
    assert base.binding_payload_hash != new_nonce.binding_payload_hash
    assert base.numeric_payload_hash != new_evaluation.numeric_payload_hash
    assert base.semantic_payload_hash != new_evaluation.semantic_payload_hash
    assert len(
        {
            base.numeric_payload_hash,
            base.semantic_payload_hash,
            base.binding_payload_hash,
        }
    ) == 3

    with pytest.raises(ValidationError):
        DecisionTruthBindingReveal.model_validate(
            {
                **base.model_dump(mode="python"),
                "numeric_nonce": digest("wrong-nonce"),
            }
        )


def test_a_b_c_require_one_nonempty_identical_sorted_asset_set(
    tmp_path: Path,
) -> None:
    first = build_reveal("truth.synthetic.001", suffix="one")
    second = build_reveal("truth.synthetic.002", suffix="two")
    records, links, payloads, _, _ = build_chain(
        tmp_path,
        (first, second),
    )
    validate_pre_reveal_chain(
        records[:3],
        expected_terminal_stage=LockStage.C,
    )

    with pytest.raises(ValidationError):
        SealedTruthLockPayload(
            stage=LockStage.A,
            public_payload_hash=digest("root"),
            truth_assets=tuple(reversed(payloads[0].truth_assets)),
        )

    changed_b = SealedTruthLockPayload(
        stage=LockStage.B,
        public_payload_hash=payloads[1].public_payload_hash,
        truth_assets=payloads[1].truth_assets[:1],
    )
    changed_b_link = make_pre_reveal_lock_link(
        chain_id=CHAIN_ID,
        payload=changed_b,
        previous_link=links[0],
    )
    changed_c = SealedTruthLockPayload(
        stage=LockStage.C,
        public_payload_hash=payloads[2].public_payload_hash,
        truth_assets=payloads[2].truth_assets[:1],
    )
    changed_c_link = make_pre_reveal_lock_link(
        chain_id=CHAIN_ID,
        payload=changed_c,
        previous_link=changed_b_link,
    )
    changed_records = (
        records[0],
        (
            canonical_json_bytes(changed_b_link).decode("utf-8"),
            canonical_json_bytes(changed_b).decode("utf-8"),
        ),
        (
            canonical_json_bytes(changed_c_link).decode("utf-8"),
            canonical_json_bytes(changed_c).decode("utf-8"),
        ),
    )
    with pytest.raises(ValueError, match="commitment set changed"):
        validate_pre_reveal_chain(
            changed_records,
            expected_terminal_stage=LockStage.C,
        )


def test_public_truth_stub_identifier_cannot_encode_registered_direction() -> None:
    reveal = build_reveal("truth.synthetic.001", suffix="one")
    commitment = commitment_for(reveal).model_copy(
        update={"truth_asset_id": "truth.synthetic.ON"}
    )
    with pytest.raises((ValidationError, ValueError)):
        SealedTruthLockPayload(
            stage=LockStage.A,
            public_payload_hash=digest("root"),
            truth_assets=(commitment,),
        )


def test_complete_replay_returns_structural_non_scoring_credential(
    tmp_path: Path,
) -> None:
    records, links, _, d_payload, roots = build_chain(tmp_path)
    credential = validate_complete_payload_bound_chain(
        records,
        planning_package_roots=roots,
    )
    assert type(credential) is LockDVerificationCredential
    assert credential.status == "STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED"
    assert credential.scoring_allowed is False
    assert credential.a_to_d_lock_hashes == tuple(
        link.lock_hash for link in links
    )
    assert credential.reveal_payload_hash == canonical_sha256(d_payload)
    validate_lock_d_credential_against_raw(
        records,
        credential,
        planning_package_roots=roots,
    )
    with pytest.raises(RuntimeError, match="AUTHENTICATED_CHRONOLOGY"):
        require_lock_d_scoring_authorization(credential)


def test_topology_or_forged_credential_cannot_authorize(
    tmp_path: Path,
) -> None:
    records, links, _, _, roots = build_chain(tmp_path)
    with pytest.raises(TypeError):
        validate_lock_d_credential_against_raw(
            records,
            links,
            planning_package_roots=roots,
        )

    genuine = validate_complete_payload_bound_chain(
        records,
        planning_package_roots=roots,
    )
    forged = genuine.model_copy(
        update={"reveal_payload_hash": digest("unrelated-reveal")}
    )
    with pytest.raises((ValidationError, ValueError)):
        validate_lock_d_credential_against_raw(
            records,
            forged,
            planning_package_roots=roots,
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda package: package.model_copy(
            update={"truth_asset_id": "truth.synthetic.extra"}
        ),
        lambda package: package.model_copy(
            update={
                "raw_package_json": package.raw_package_json.replace(
                    '"native_t4_eligible":false',
                    '"native_t4_eligible":true',
                )
            }
        ),
        lambda package: package.model_copy(
            update={"raw_package_json": f" {package.raw_package_json}"}
        ),
    ],
)
def test_any_inner_reveal_or_raw_byte_mismatch_stops_after_valid_outer_link(
    tmp_path: Path,
    mutator,
) -> None:
    records, links, _, d_payload, roots = build_chain(tmp_path)
    changed_package = mutator(d_payload.truth_asset_packages[0])
    changed_d = d_payload.model_copy(
        update={"truth_asset_packages": (changed_package,)}
    )
    changed_records = (*records[:3], rebuilt_d_record(links, changed_d))
    with pytest.raises((ValidationError, ValueError)):
        validate_complete_payload_bound_chain(
            changed_records,
            planning_package_roots=roots,
        )


def test_cross_asset_splice_fails_after_rebuilt_d_link(tmp_path: Path) -> None:
    first = build_reveal("truth.synthetic.001", suffix="one")
    second = build_reveal("truth.synthetic.002", suffix="two")
    records, links, _, d_payload, roots = build_chain(
        tmp_path,
        (first, second),
    )
    second_wrapper = d_payload.truth_asset_packages[1].model_copy(
        update={
            "raw_package_json": (
                d_payload.truth_asset_packages[0].raw_package_json
            )
        }
    )
    spliced = d_payload.model_copy(
        update={
            "truth_asset_packages": (
                d_payload.truth_asset_packages[0],
                second_wrapper,
            )
        }
    )
    changed_records = (*records[:3], rebuilt_d_record(links, spliced))
    with pytest.raises(ValueError):
        validate_complete_payload_bound_chain(
            changed_records,
            planning_package_roots=roots,
        )


def test_revealed_package_cannot_be_replayed_under_another_chain(
    tmp_path: Path,
) -> None:
    reveal = build_reveal("truth.synthetic.001", suffix="one")
    records, _, _, _, roots = build_chain(
        tmp_path,
        (reveal,),
        evaluation_id="evaluation.synthetic.002",
        chain_id="chain.synthetic.002",
        run_label="other",
    )
    with pytest.raises(ValueError, match="context mismatch"):
        validate_complete_payload_bound_chain(
            records,
            planning_package_roots=roots,
        )


def test_actual_package_replay_rejects_forged_receipt_or_changed_file(
    tmp_path: Path,
) -> None:
    records, links, _, d_payload, roots = build_chain(tmp_path)
    forged_receipt = d_payload.sanitizer_receipts[0].model_copy(
        update={"sanitizer_report_hash": digest("forged-clean-report")}
    )
    forged_d = d_payload.model_copy(
        update={
            "sanitizer_receipts": (
                forged_receipt,
                *d_payload.sanitizer_receipts[1:],
            )
        }
    )
    forged_records = (*records[:3], rebuilt_d_record(links, forged_d))
    with pytest.raises(ValueError, match="report hash"):
        validate_complete_payload_bound_chain(
            forged_records,
            planning_package_roots=roots,
        )

    (roots[1] / "public.txt").write_text(
        "changed but still semantically masked\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="different planning package"):
        validate_complete_payload_bound_chain(
            records,
            planning_package_roots=roots,
        )


def test_early_reveal_or_incomplete_claim_is_hard_stop(
    tmp_path: Path,
) -> None:
    for index, status in enumerate(
        (
            "EVALUATION_INVALID_EARLY_REVEAL",
            "AUDIT_INCOMPLETE_FAIL_CLOSED",
        )
    ):
        records, _, _, _, roots = build_chain(
            tmp_path,
            claimed_pre_reveal_audit_status=status,
            run_label=f"early-{index}",
        )
        with pytest.raises(ValueError, match="pre-reveal"):
            validate_complete_payload_bound_chain(
                records,
                planning_package_roots=roots,
            )


def test_duplicate_key_in_d_or_raw_asset_is_rejected(
    tmp_path: Path,
) -> None:
    records, links, _, d_payload, roots = build_chain(tmp_path)
    duplicate_d = records[3][1].replace(
        '"stage":"D"',
        '"stage":"D","stage":"D"',
    )
    with pytest.raises(DuplicateJsonKeyError):
        validate_complete_payload_bound_chain(
            (*records[:3], (records[3][0], duplicate_d)),
            planning_package_roots=roots,
        )

    raw = d_payload.truth_asset_packages[0].raw_package_json
    duplicate_asset = raw.replace(
        '"schema_version":"1.0"',
        '"schema_version":"1.0","schema_version":"1.0"',
        1,
    )
    changed_d = d_payload.model_copy(
        update={
            "truth_asset_packages": (
                d_payload.truth_asset_packages[0].model_copy(
                    update={"raw_package_json": duplicate_asset}
                ),
            )
        }
    )
    changed_records = (*records[:3], rebuilt_d_record(links, changed_d))
    with pytest.raises(DuplicateJsonKeyError):
        validate_complete_payload_bound_chain(
            changed_records,
            planning_package_roots=roots,
        )
