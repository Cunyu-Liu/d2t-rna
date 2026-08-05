from __future__ import annotations

import json
from pathlib import Path

import pytest

from d2t_rna.contracts.base import canonical_sha256
from d2t_rna.data.manifest import (
    CONTRACT_SHA256,
    REGISTERED_DATASET_IDS,
    build_registered_bundle,
    serialize_bundle,
)
from d2t_rna.data.validate import validate_manifest_directory


def test_registered_bundle_has_five_distinct_outputs_and_no_truth_payload() -> None:
    bundle = build_registered_bundle("add")
    serialized = serialize_bundle(bundle)

    assert set(serialized) == {
        "public_planning_stub.json",
        "sealed_truth_commitment.json",
        "private_provenance_manifest.json",
        "sanitized_action_package.json",
    }
    assert len({model.schema_id for model in bundle}) == 4
    assert all(model.contract_hash == CONTRACT_SHA256 for model in bundle)
    sealed = bundle[1]
    assert sealed.numeric_truth_revealed is False
    assert sealed.semantic_truth_revealed is False
    assert sealed.native_truth_label_generated is False
    assert "population_estimate" not in serialized["sealed_truth_commitment.json"]
    assert "directional_evidence" not in serialized["sealed_truth_commitment.json"]


def test_public_stub_retains_field_level_source_provenance() -> None:
    public, *_ = build_registered_bundle("sam-iii")
    assert public.official_metadata_only is True
    assert public.fastq_outcomes_downloaded is False
    assert public.native_truth_label_generated is False
    assert public.facts
    assert all(fact.source_ids for fact in public.facts)
    assert all(fact.retrieved_at == "2026-08-01" for fact in public.facts)


def test_rorc_is_fail_closed_when_no_official_accession_is_registered() -> None:
    bundle = build_registered_bundle("rorc")
    eligibility = bundle[-1]
    assert eligibility.status == "INELIGIBLE_UNRESOLVED_METADATA"
    assert eligibility.stress_execution_allowed is False
    assert eligibility.held_out_claim_allowed is False
    assert eligibility.reason_code == "NO_PRIMARY_OFFICIAL_ACCESSION_RESOLVED"


def test_validation_requires_cross_file_hash_bindings(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    for dataset_id in REGISTERED_DATASET_IDS:
        dataset_root = root / dataset_id.replace("-", "_")
        dataset_root.mkdir(parents=True)
        bundle = build_registered_bundle(dataset_id)
        for name, payload in serialize_bundle(bundle).items():
            (dataset_root / name).write_text(payload, encoding="utf-8")

    result = validate_manifest_directory(root)
    assert result.status == "PASS_WITH_FAIL_CLOSED_RORC"
    assert not result.errors

    sealed_path = root / "add" / "sealed_truth_commitment.json"
    raw = json.loads(sealed_path.read_text(encoding="utf-8"))
    raw["planning_stub_hash"] = "0" * 64
    sealed_path.write_text(json.dumps(raw), encoding="utf-8")
    failed = validate_manifest_directory(root)
    assert failed.status == "FAIL"
    assert any("planning stub hash" in error for error in failed.errors)


def test_truth_commitment_is_hash_only_and_reproducible() -> None:
    first = build_registered_bundle("add")[1]
    second = build_registered_bundle("add")[1]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.commitment_set_hash == canonical_sha256(first.commitments)


def test_unknown_dataset_is_rejected() -> None:
    with pytest.raises(ValueError, match="registered dataset"):
        build_registered_bundle("unknown")
