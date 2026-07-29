from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)


def test_frozen_contract_snapshot_matches_registered_raw_file_hash() -> None:
    contract = ROOT / "contracts" / "D2T-RNA-v6.1-frozen-plan.md"
    assert hashlib.sha256(contract.read_bytes()).hexdigest() == (
        EXPECTED_CONTRACT_SHA256
    )


def test_project_manifest_points_to_the_same_frozen_contract() -> None:
    manifest = json.loads(
        (ROOT / "manifests" / "project_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["contract_sha256"] == EXPECTED_CONTRACT_SHA256
    assert (
        ROOT / manifest["contract_path"]
    ).resolve() == (
        ROOT / "contracts" / "D2T-RNA-v6.1-frozen-plan.md"
    ).resolve()
    assert manifest["preflight_status"] == "PASS_WITH_REGISTERED_CONSTRAINTS"
