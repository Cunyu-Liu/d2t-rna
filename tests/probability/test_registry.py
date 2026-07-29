from __future__ import annotations

from pathlib import Path

import pytest

from d2t_rna.contracts.base import (
    DuplicateJsonKeyError,
    canonical_sha256,
    parse_contract_json,
)
from d2t_rna.contracts.primitives import RegistryRef
from d2t_rna.probability.registry import (
    RegistryResolutionError,
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    UntrustedSemanticRegistryError,
    ensure_trusted_task2_registry,
    load_trusted_task2_registry,
    resolve_registry_ref,
)
from d2t_rna.probability.risk import FailurePolicyDefinition


def _manifest_bytes() -> bytes:
    path = Path(__file__).parents[2] / "manifests" / "task2_semantic_registry.json"
    return path.read_bytes()


def test_registry_manifest_has_a_pinned_canonical_root(
    registry: TrustedSemanticRegistry,
) -> None:
    assert canonical_sha256(registry) == (
        "25604dac2cf94384d3c908293e2139c2f96321cb1582668647b651923fbb2c28"
    )


def test_registry_content_tampering_fails_closed() -> None:
    raw = _manifest_bytes()
    tampered = raw.replace(
        b"eed12fe95f8614b4206efa159725e60a2d7d8023df52e8a92feff647f0764972",
        b"0" * 64,
    )
    with pytest.raises(UntrustedSemanticRegistryError, match="root mismatch"):
        load_trusted_task2_registry(tampered)


def test_registry_duplicate_json_keys_are_rejected() -> None:
    raw = _manifest_bytes()
    duplicate = raw.replace(
        b'"schema_id": "d2t_rna.semantic_registry",',
        (
            b'"schema_id": "d2t_rna.semantic_registry",'
            b'"schema_id": "d2t_rna.semantic_registry",'
        ),
    )
    with pytest.raises(DuplicateJsonKeyError, match="duplicate JSON key"):
        load_trusted_task2_registry(duplicate)


def test_registry_role_and_member_hash_cannot_be_spliced(
    registry: TrustedSemanticRegistry,
) -> None:
    observed_target = registry.ref(
        "target.full_observed_dataset_empirical_feature_distribution",
        SemanticRegistryRole.OBSERVED_TARGET,
    )
    with pytest.raises(RegistryResolutionError, match="expected"):
        resolve_registry_ref(
            observed_target,
            registry,
            SemanticRegistryRole.WITHIN_LIBRARY_TARGET,
        )
    forged = RegistryRef(
        registry_id=observed_target.registry_id,
        registry_hash="0" * 64,
    )
    with pytest.raises(RegistryResolutionError, match="hash mismatch"):
        resolve_registry_ref(
            forged,
            registry,
            SemanticRegistryRole.OBSERVED_TARGET,
        )


def test_failure_policy_registry_hash_has_a_committed_preimage(
    registry: TrustedSemanticRegistry,
) -> None:
    path = (
        Path(__file__).parents[2]
        / "manifests"
        / "task2_failure_policy_abstain_all.json"
    )
    definition = parse_contract_json(
        FailurePolicyDefinition,
        path.read_bytes(),
    )
    reference = registry.ref(
        "failure.abstain_all_registered",
        SemanticRegistryRole.FAILURE_POLICY,
    )
    assert canonical_sha256(definition) == reference.registry_hash


def test_registry_subclass_cannot_override_trusted_lookup(
    registry: TrustedSemanticRegistry,
) -> None:
    class EvilRegistry(TrustedSemanticRegistry):
        def _member(self, registry_id: str) -> object:
            raise AssertionError(f"attacker-controlled lookup: {registry_id}")

    evil = EvilRegistry.model_validate(
        registry.model_dump(mode="python"),
        strict=True,
    )
    assert canonical_sha256(evil) == canonical_sha256(registry)
    with pytest.raises(TypeError, match="exactly TrustedSemanticRegistry"):
        ensure_trusted_task2_registry(evil)
    with pytest.raises(TypeError, match="exactly TrustedSemanticRegistry"):
        evil.ref(
            "target.full_observed_dataset_empirical_feature_distribution",
            SemanticRegistryRole.OBSERVED_TARGET,
        )
