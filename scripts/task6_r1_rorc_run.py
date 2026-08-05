"""D2T-RNA v7 §8.3 R1 materialization decision for rorc (contract 8.5).

rorc has no public official accession to materialize: its public planning stub
reports ``accession_status: NOT_RESOLVED``, the only source is the internal
audit document ``docs/audit/task-3-truth-locks.md``, and the stress-eligibility
record is ``INELIGIBLE_UNRESOLVED_METADATA`` with
``reason_code: NO_PRIMARY_OFFICIAL_ACCESSION_RESOLVED`` and
``stress_execution_allowed: false``.

Therefore R1 observed-dataset materialization is NOT APPLICABLE for rorc.  This
is a fail-closed decision (contract 8.4): we do not substitute an internal
audit file for a public observed dataset, and we do not fabricate a materialized
observed-dataset hash.  The runner writes an auditable record.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    stub = json.loads(
        (Path("/home/cunyuliu/d2t-rna/manifests/rorc/public_planning_stub.json")).read_bytes()
    )
    elig = json.loads(
        (Path("/home/cunyuliu/d2t-rna/manifests/rorc/stress_eligibility_record.json")).read_bytes()
    )
    accession_status = stub["accession_status"]
    eligibility_status = elig["status"]
    reason = elig["reason_code"]
    stress_allowed = elig["stress_execution_allowed"]

    applicable = bool(
        accession_status == "RESOLVED"
        and eligibility_status == "ELIGIBLE"
        and stress_allowed
    )

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"task6-r1-rorc-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "dataset_id": "rorc",
        "contract_section": "8.3",
        "kind": "R1_MATERIALIZATION_DECISION",
        "decision": "NOT_APPLICABLE" if not applicable else "APPLICABLE",
        "accession_status": accession_status,
        "eligibility_status": eligibility_status,
        "reason_code": reason,
        "stress_execution_allowed": stress_allowed,
        "observed_data_materialized": False,
        "explanation": (
            "rorc has no public official accession to materialize; its only "
            "source is the internal audit document.  R1 is NOT APPLICABLE; "
            "observed-data materialization is not fabricated (fail-closed, "
            "contract 8.4/8.5)."
        ),
        "status": "NOT_APPLICABLE",
        "scientific_claim_authorized": False,
        "run_finished": time.time(),
    }
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(report, indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())
    report["report_sha256"] = report_sha

    manifest_dir = MANIFESTS_ROOT / "task6r"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "task6r_r1_rorc_decision.json"
    manifest_raw = json.dumps(report, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    report["manifest_path"] = str(manifest)
    report["manifest_sha256"] = _sha256_of_bytes(manifest_raw)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())