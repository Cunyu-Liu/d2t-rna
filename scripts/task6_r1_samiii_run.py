"""D2T-RNA v7 §8.3 R1 observed-dataset materialization runner (sam-iii).

Materializes the SAM-III/GSE278422 DANCE-MaP supplement and freezes the §8.3
evidence, writing an auditable run report and acceptance manifest.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from d2t_rna.data.r1_materialize_sam_iii import materialize_sam_iii

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    raw_dir = "/mnt/cunyuliu/d2t-rna/data/task6/sam-iii/raw"
    report = materialize_sam_iii(raw_dir)

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"task6-r1-samiii-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(report, indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())

    # Self-check: 5 constructs x 2 conditions = 10 condition tables, and the
    # observed-dataset hash is a 64-hex sha256.
    self_check_ok = bool(
        report["condition_count"] == 10
        and len(report["construct_sequences"]) == 5
        and report["observed_dataset_hash"]
        and len(report["observed_dataset_hash"]) == 64
    )
    test_log = run_dir / "test.log"
    test_log.write_text(
        f"R1 self-check: materialized={self_check_ok}\n"
        f"observed_dataset_hash={report['observed_dataset_hash']}\n"
        f"condition_count={report['condition_count']}\n"
    )
    test_log_sha = _sha256_of_bytes(test_log.read_bytes())

    payload = {
        "contract_section": "8.3",
        "kind": "R1_OBSERVED_DATASET_MATERIALIZATION_SAMIII",
        "run_dir": str(run_dir),
        "run_finished": time.time(),
        "report": report,
        "report_sha256": report_sha,
        "test_log_sha256": test_log_sha,
        "self_check_ok": self_check_ok,
        "status": "MATERIALIZED",
        "scientific_claim_authorized": False,
        "boundary_note": (
            "R1 freezes observed-dataset evidence only; it authorizes no claim "
            "and is not a prospective/blinded/held-out validation (contract 8.3)."
        ),
    }
    manifest_dir = MANIFESTS_ROOT / "task6r"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "task6r_r1_samiii_acceptance.json"
    manifest_raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = _sha256_of_bytes(manifest_raw)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())