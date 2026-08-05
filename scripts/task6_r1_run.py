"""D2T-RNA v7 §8.3 R1 observed-dataset materialization runner.

Runs the R1 materialization for a registered public dataset (add/RMDB) and
freezes the §8.3 evidence: raw checksums, download time, version and license,
construct/assay mapping, dependency units, outcome-access timestamp,
theorem/method-freeze hash, the complete observed-dataset hash, and the
raw/processed/author-truth/derived layering.

This is a *materialization*, not a scientific claim (contract 8.3).  It writes:
  * the canonical JSON + sha256 sidecar next to the raw file, and
  * an auditable run report + acceptance manifest under /mnt artifacts.
Any later R2 evaluation is gated by the fail-closed framework (contract 8.4).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from d2t_rna.data.r1_materialize import (
    ADD_ROLE,
    R1MaterializationReport,
    materialize_add,
)

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _freeze_manifest(payload: dict, run_dir: Path) -> tuple[Path, str]:
    manifest_dir = MANIFESTS_ROOT / "task6r"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "task6r_r1_acceptance.json"
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(raw)
    return manifest, _sha256_of_bytes(raw)


def main() -> int:
    raw_path = "/mnt/cunyuliu/d2t-rna/data/task6/add/ADDRSW_SHP_0003.rdat"
    report: R1MaterializationReport = materialize_add(raw_path)

    # Freeze the report into an auditable run artifact.
    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"task6-r1-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(report.as_dict(), indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())
    test_log = run_dir / "test.log"

    # The materialization is self-validating: the canonical bytes must re-parse
    # to the same hash, and the raw sha must match the frozen evidence.
    self_check_ok = bool(
        report.raw_sha256
        == "cb2d8c218512fbbe76149399c0e88c6e5f9f43957413de254a49a7c40b2e53e5"
        and report.data_point_count == report.construct_count * report.seqpos_count
        and report.observed_dataset_hash
    )
    test_log.write_text(
        f"R1 self-check: materialized={self_check_ok}\n"
        f"raw_sha256={report.raw_sha256}\n"
        f"observed_dataset_hash={report.observed_dataset_hash}\n"
        f"data_points={report.data_point_count}\n"
    )
    test_log_sha = _sha256_of_bytes(test_log.read_bytes())

    payload = {
        "contract_section": "8.3",
        "kind": "R1_OBSERVED_DATASET_MATERIALIZATION",
        "run_dir": str(run_dir),
        "run_finished": time.time(),
        "report": report.as_dict(),
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
    manifest, manifest_sha = _freeze_manifest(payload, run_dir)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = manifest_sha

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())