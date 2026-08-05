"""Fail-closed validator for the Task 6 separated manifest artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from d2t_rna.contracts.base import canonical_sha256, parse_contract_json

from .manifest import (
    REGISTERED_DATASET_IDS,
    PrivateProvenanceManifest,
    PublicPlanningStub,
    RorcStressEligibilityRecord,
    SanitizedActionPackage,
    SealedTruthCommitment,
)


@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: tuple[str, ...]


_REQUIRED = {
    "public_planning_stub.json": PublicPlanningStub,
    "sealed_truth_commitment.json": SealedTruthCommitment,
    "private_provenance_manifest.json": PrivateProvenanceManifest,
    "sanitized_action_package.json": SanitizedActionPackage,
}


def _read(model_type: type, path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlink manifest: {path}")
    return parse_contract_json(model_type, path.read_bytes())


def _validate_dataset(root: Path, dataset_id: str) -> list[str]:
    errors: list[str] = []
    dataset_root = root / dataset_id.replace("-", "_")
    models: dict[str, object] = {}
    try:
        for name, model_type in _REQUIRED.items():
            models[name] = _read(model_type, dataset_root / name)
        if dataset_id == "rorc":
            models["stress_eligibility_record.json"] = _read(
                RorcStressEligibilityRecord,
                dataset_root / "stress_eligibility_record.json",
            )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [f"{dataset_id}: {exc}"]

    public = models["public_planning_stub.json"]
    sealed = models["sealed_truth_commitment.json"]
    private = models["private_provenance_manifest.json"]
    action = models["sanitized_action_package.json"]
    assert isinstance(public, PublicPlanningStub)
    assert isinstance(sealed, SealedTruthCommitment)
    assert isinstance(private, PrivateProvenanceManifest)
    assert isinstance(action, SanitizedActionPackage)
    public_hash = canonical_sha256(public)
    sealed_hash = canonical_sha256(sealed)
    if sealed.planning_stub_hash != public_hash:
        errors.append(f"{dataset_id}: sealed commitment planning stub hash mismatch")
    if private.planning_stub_hash != public_hash:
        errors.append(f"{dataset_id}: private provenance planning stub hash mismatch")
    if private.sealed_commitment_hash != sealed_hash:
        errors.append(f"{dataset_id}: private provenance sealed commitment hash mismatch")
    if action.planning_stub_hash != public_hash:
        errors.append(f"{dataset_id}: sanitized action planning stub hash mismatch")
    if action.sealed_commitment_hash != sealed_hash:
        errors.append(f"{dataset_id}: sanitized action sealed commitment hash mismatch")
    if public.fastq_outcomes_downloaded or public.native_truth_label_generated:
        errors.append(f"{dataset_id}: public manifest crosses the Task 6 stop line")
    if sealed.numeric_truth_revealed or sealed.semantic_truth_revealed or sealed.native_truth_label_generated:
        errors.append(f"{dataset_id}: sealed manifest exposes truth payload")
    if private.raw_fastq_downloaded or private.outcome_interpretation_performed or private.native_truth_label_generated:
        errors.append(f"{dataset_id}: private provenance crosses the Task 6 stop line")
    if action.sequence_payload_present or action.outcome_payload_present or action.native_truth_label_generated:
        errors.append(f"{dataset_id}: sanitized action package crosses the Task 6 stop line")
    if dataset_id == "rorc":
        eligibility = models["stress_eligibility_record.json"]
        assert isinstance(eligibility, RorcStressEligibilityRecord)
        if eligibility.stress_execution_allowed or eligibility.held_out_claim_allowed:
            errors.append("rorc: unresolved metadata cannot authorize stress execution")
    return errors


def validate_manifest_directory(root: Path) -> ValidationResult:
    """Validate all registered bundles and their cross-file bindings."""

    errors: list[str] = []
    for dataset_id in REGISTERED_DATASET_IDS:
        errors.extend(_validate_dataset(root, dataset_id))
    if errors:
        return ValidationResult(status="FAIL", errors=tuple(errors))
    return ValidationResult(
        status="PASS_WITH_FAIL_CLOSED_RORC",
        errors=(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    result = validate_manifest_directory(args.root)
    print(f"TASK6_MANIFEST_VALIDATION_STATUS={result.status}")
    for error in result.errors:
        print(f"TASK6_MANIFEST_VALIDATION_ERROR={error}")
    return 0 if result.status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
