"""Batch 1 minimal verification: authority-file invariants for D2T-RNA v7 evidence repair.

Checks that the four Batch 1 authority manifests exist, are valid JSON with required
schema, and satisfy the minimal provisional-terminalization invariants (claim freeze,
no READY submission status while claim unauthorized, ReactFlow evidence count = 0).
"""
import json
from pathlib import Path

import pytest

AUDIT_DIR = Path("manifests/audit")

AUTHORITY_FILES = [
    "v7_p0_repair_snapshot.json",
    "v7_claim_freeze.json",
    "v7_provisional_tombstones.json",
    "v7_artifact_authority_index.json",
]


@pytest.mark.parametrize("name", AUTHORITY_FILES)
def test_authority_file_valid_json_and_schema(name):
    path = AUDIT_DIR / name
    assert path.exists(), f"missing authority file {name}"
    data = json.loads(path.read_text())
    assert "schema" in data, f"{name} missing schema"
    assert "payload" in data, f"{name} missing canonical payload"
    assert "generator_commit" in data, f"{name} missing generator_commit"
    # Non-deterministic metadata separated from canonical payload
    assert "receipt" in data, f"{name} missing receipt wrapper"


def test_claim_freeze_blocks_readiness_when_unauthorized():
    freeze = json.loads((AUDIT_DIR / "v7_claim_freeze.json").read_text())["payload"]
    assert freeze["scientific_claim_authorized"] is False
    assert freeze["submission_status"] == "SCIENTIFIC_SUBMISSION_BLOCKED"
    assert freeze["reactflow_evidence_count_allowed"] == 0


def test_claim_freeze_allowed_labels_are_exact_superset():
    freeze = json.loads((AUDIT_DIR / "v7_claim_freeze.json").read_text())["payload"]
    assert set(freeze["allowed_claim_labels"]) == {
        "CONFIRMED_FACT",
        "REASONED_INFERENCE",
        "UNKNOWN_NOT_ASSERTED",
        "NEW_EVIDENCE_REQUIRED",
    }
    assert set(freeze["allowed_artifact_status"]) == {
        "CURRENT_VALID",
        "LEGACY_VALID",
        "LEGACY_INVALID",
        "EXTERNAL_ONLY",
        "UNKNOWN_NOT_REPLAYED",
    }


def test_provisional_tombstones_do_not_delete_bytes():
    tombstones = json.loads(
        (AUDIT_DIR / "v7_provisional_tombstones.json").read_text()
    )["payload"]
    assert tombstones["principle"].startswith("Old artifacts keep bytes")
    for t in tombstones["tombstones"]:
        assert "file_integrity" in t
        assert "scientific_interpretation" in t
        # Every tombstoned family must be non-current for scientific interpretation
        assert t["scientific_interpretation"] in {
            "LEGACY_INVALID",
            "DESCRIPTIVE_ONLY",
        }


def test_authority_index_is_role_sensitive():
    index = json.loads(
        (AUDIT_DIR / "v7_artifact_authority_index.json").read_text()
    )["payload"]
    for entry in index["index"]:
        assert "role" in entry
        assert "status" in entry
    # phase4 phase5 file-integrity LEGACY_VALID but scientific LEGACY_INVALID
    p4 = next(e for e in index["index"] if e["artifact"].endswith("phase4_acceptance.json"))
    assert p4["status"] == "LEGACY_VALID"
    assert "LEGACY_INVALID" in p4["note"]


def test_snapshot_head_frozen():
    snap = json.loads(
        (AUDIT_DIR / "v7_p0_repair_snapshot.json").read_text()
    )["payload"]
    assert snap["scientific_claim_authorized"] is False
    assert snap["current_stage"] == "A"
    assert snap["head"]
