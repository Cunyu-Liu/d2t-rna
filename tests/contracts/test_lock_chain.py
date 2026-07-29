from __future__ import annotations

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import DuplicateJsonKeyError, canonical_sha256
from d2t_rna.contracts.enums import LockStage, TruthVisibility
from d2t_rna.contracts.locks import (
    LockLink,
    SealedTruthLockPayload,
    make_pre_reveal_lock_link,
    make_topology_link,
    validate_complete_payload_bound_chain,
    validate_lock_payload_binding,
    validate_lock_topology,
    validate_pre_reveal_chain,
)
from d2t_rna.contracts.primitives import RegistryRef
from d2t_rna.contracts.truth import TruthAssetCommitment

from .conftest import SHA_A, SHA_B, SHA_C, SHA_D, SHA_E, SHA_F


def make_commitment() -> TruthAssetCommitment:
    return TruthAssetCommitment(
        truth_asset_id="truth.synthetic.001",
        asset_hash=SHA_A,
        sequence_identity_hash=SHA_B,
        condition_spec_hash=SHA_C,
        measurement_modality=RegistryRef(
            registry_id="modality.synthetic_counts",
            registry_hash=SHA_D,
        ),
        eligibility_status_without_direction=RegistryRef(
            registry_id="eligibility.registered_without_direction",
            registry_hash=SHA_E,
        ),
        numeric_payload_hash=SHA_F,
        semantic_payload_hash=SHA_A,
        visibility=TruthVisibility.HASH_ONLY,
    )


def make_full_chain():
    links = []
    sealed_payloads = []
    previous = None
    for stage in LockStage:
        if stage is not LockStage.D:
            payload = SealedTruthLockPayload(
                stage=stage,
                public_payload_hash=canonical_sha256(
                    {"stage": stage.value, "registered_payload": stage.value.lower()}
                ),
                truth_assets=(make_commitment(),),
            )
            link = make_pre_reveal_lock_link(
                chain_id="chain.synthetic.001",
                payload=payload,
                previous_link=links[-1] if links else None,
            )
            sealed_payloads.append(payload)
        else:
            link = make_topology_link(
                chain_id="chain.synthetic.001",
                stage=stage,
                payload_schema_id="d2t_rna.decision_truth_binding_reveal",
                payload_schema_version="1.0",
                payload_hash=canonical_sha256(
                    {"stage": stage.value, "task3_reveal_placeholder": True}
                ),
                previous_lock_hash=previous,
            )
        links.append(link)
        previous = link.lock_hash
    return tuple(links), tuple(sealed_payloads)


@pytest.mark.parametrize("stage", [LockStage.A, LockStage.B, LockStage.C])
def test_pre_reveal_lock_payload_accepts_only_hash_commitments(
    stage: LockStage,
) -> None:
    payload = SealedTruthLockPayload(
        stage=stage,
        public_payload_hash=SHA_B,
        truth_assets=(make_commitment(),),
    )
    assert payload.truth_assets[0].visibility is TruthVisibility.HASH_ONLY
    raw = payload.model_dump(mode="python")
    raw["population_estimate"] = {"numerator": 1, "denominator": 2}
    with pytest.raises(ValidationError):
        SealedTruthLockPayload.model_validate(raw)


def test_full_a_b_c_d_topology_validates_but_payload_bundle_fails_closed() -> None:
    links, sealed_payloads = make_full_chain()
    validate_lock_topology(links, require_complete=True)
    records = tuple(
        (link.model_dump_json(), payload.model_dump_json())
        for link, payload in zip(links[:3], sealed_payloads, strict=True)
    ) + (
        (
            links[3].model_dump_json(),
            '{"schema_id":"d2t_rna.decision_truth_binding_reveal",'
            '"schema_version":"1.0","task3_placeholder":true}',
        ),
    )
    with pytest.raises(NotImplementedError):
        validate_complete_payload_bound_chain(records)


def test_a_to_c_links_are_bound_to_the_actual_registered_payloads() -> None:
    links, sealed_payloads = make_full_chain()
    for link, payload in zip(links[:3], sealed_payloads, strict=True):
        validate_lock_payload_binding(link, payload)

    records = tuple(
        (link.model_dump_json(), payload.model_dump_json())
        for link, payload in zip(links[:3], sealed_payloads, strict=True)
    )
    assert validate_pre_reveal_chain(
        records,
        expected_terminal_stage=LockStage.C,
    ) == links[:3]

    changed = sealed_payloads[1].model_copy(
        update={"public_payload_hash": SHA_F},
    )
    with pytest.raises((ValidationError, ValueError)):
        validate_lock_payload_binding(links[1], changed)


def test_nested_unchecked_truth_fields_cannot_bypass_payload_binding() -> None:
    links, sealed_payloads = make_full_chain()
    changed_commitment = make_commitment().model_copy(
        update={"population_estimate": "directional-secret"},
    )
    changed_payload = sealed_payloads[0].model_copy(
        update={"truth_assets": (changed_commitment,)},
    )
    with pytest.raises((ValidationError, ValueError)):
        validate_lock_payload_binding(links[0], changed_payload)


def test_pre_reveal_raw_records_reject_duplicate_payload_keys() -> None:
    links, sealed_payloads = make_full_chain()
    raw_payload = sealed_payloads[0].model_dump_json().replace(
        '"stage":"A"',
        '"stage":"A","stage":"B"',
    )
    with pytest.raises(DuplicateJsonKeyError):
        validate_pre_reveal_chain(
            ((links[0].model_dump_json(), raw_payload),),
            expected_terminal_stage=LockStage.A,
        )


def test_pre_reveal_link_rejects_an_arbitrary_claimed_payload_schema() -> None:
    payload = SealedTruthLockPayload(
        stage=LockStage.A,
        public_payload_hash=SHA_A,
        truth_assets=(make_commitment(),),
    )
    with pytest.raises((TypeError, ValueError)):
        make_topology_link(
            chain_id="chain.synthetic.001",
            stage=LockStage.A,
            payload_schema_id="truth.numeric.directional",
            payload_schema_version="1.0",
            payload_hash=canonical_sha256(payload),
            previous_lock_hash=None,
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda links: (links[0], links[2], links[3]),
        lambda links: (links[1], links[0], links[2], links[3]),
        lambda links: (
            links[0],
            links[1].model_copy(update={"payload_hash": SHA_F}),
            links[2],
            links[3],
        ),
        lambda links: (
            links[0],
            links[1],
            links[2].model_copy(update={"chain_id": "chain.other"}),
            links[3],
        ),
    ],
)
def test_skip_reorder_tamper_or_chain_splice_is_detected(mutator) -> None:
    links, _ = make_full_chain()
    with pytest.raises(ValueError):
        validate_lock_topology(mutator(links), require_complete=True)


def test_partial_chain_must_be_a_forward_prefix() -> None:
    links, _ = make_full_chain()
    validate_lock_topology(links[:2], require_complete=False)
    with pytest.raises(ValueError):
        validate_lock_topology(links[1:3], require_complete=False)


@pytest.mark.parametrize(
    "tampered_link",
    [
        lambda link: link.model_copy(update={"schema_id": "evil.lock_link"}),
        lambda link: link.model_copy(update={"schema_version": "9.9"}),
        lambda link: link.model_copy(update={"unregistered_truth": "ON"}),
        lambda link: type(link).model_construct(
            **{
                **link.model_dump(mode="python"),
                "schema_id": "evil.lock_link",
                "schema_version": "9.9",
            }
        ),
    ],
)
def test_unchecked_pydantic_construction_cannot_bypass_chain_validation(
    tampered_link,
) -> None:
    links, _ = make_full_chain()
    changed = (tampered_link(links[0]), *links[1:])
    with pytest.raises((ValidationError, ValueError)):
        validate_lock_topology(changed, require_complete=True)


def test_unregistered_lock_link_subclass_cannot_extend_the_committed_shape() -> None:
    class DirectionalLockLink(LockLink):
        directional_truth: str

    links, _ = make_full_chain()
    injected = DirectionalLockLink(
        **links[0].model_dump(mode="python"),
        directional_truth="ON",
    )
    with pytest.raises((TypeError, ValueError)):
        validate_lock_topology((injected, *links[1:]), require_complete=True)
