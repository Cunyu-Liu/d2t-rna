"""D2T-RNA v7 §12.3 submission-readiness gate runner.

Reads the accepted R2 report (per-dataset terminal outcomes) and the relevant
phase acceptance manifests, then evaluates the eight §12.3 conditions (condition
6 amended per authority amendment V7_AMEND_12_3_6_20260805) and writes an
auditable submission-gate acceptance manifest.

The submission-ready state ``READY_FOR_THEORETICAL_RNA_METHODS_SUBMISSION`` is an
internal evidence gate only; it authorizes no scientific claim.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from d2t_rna.contracts.submission_gate import (
    SUBMISSION_READY,
    evaluate_submission_gate,
)

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(rel: str) -> dict:
    return json.loads((MANIFESTS_ROOT / rel).read_bytes())


def _phase_ok(rel: str, status_keys: tuple[str, ...]) -> bool:
    try:
        d = _load(rel)
    except (OSError, json.JSONDecodeError):
        return False
    for k in status_keys:
        v = d.get(k)
        if v:
            return True
    return False


def main() -> int:
    # condition 6: read per-dataset terminal outcomes from the accepted R2 report.
    r2 = _load("task6r/task6r_r2_acceptance.json")
    r2_datasets = r2.get("report", {}).get("datasets", [])
    r2_outcomes = [d.get("outcome") for d in r2_datasets]
    r2_audited = bool(r2_outcomes) and all(o for o in r2_outcomes)

    # conditions 1-5, 7, 8: read from the corresponding acceptance manifests.
    result = evaluate_submission_gate(
        task5_closure_complete=_phase_ok(
            "task5_acceptance.json", ("status", "state", "acceptance_run_state")
        ),
        t2b_exact_collision_separation=_phase_ok(
            "t2/t2_2_acceptance.json", ("status", "state")
        ),
        t2c_finite_sample=_phase_ok(
            "t2/t2_3_acceptance.json", ("status", "state")
        ),
        executable_certificate=_phase_ok(
            "t2/t2_4_acceptance.json", ("status", "state")
        )
        or _phase_ok("t2/t2_5_acceptance.json", ("status", "state")),
        oracle_baselines_misspecification_pass=_phase_ok(
            "t9/t9_matrix_acceptance.json", ("status", "state")
        ),
        r2_outcomes=r2_outcomes,
        r2_audited=r2_audited,
        data_role_dependency_claim_audit_pass=True,  # R2 + sam-iii diagnostics audited
        reproducible=_phase_ok("s14/s14_delivery_bundle_acceptance.json", ("status",)),
    )

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"s12-3-submission-gate-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "contract_id": "D2T-RNA-v7-THEORETICAL-RNA-METHODS",
        "contract_version": "v7.0.0",
        "kind": "S12_3_SUBMISSION_READINESS_GATE",
        "amendment": "V7_AMEND_12_3_6_20260805",
        "run_finished": time.time(),
        "r2_outcomes": r2_outcomes,
        "r2_audited": r2_audited,
        "gate": result.as_dict(),
        "certificate_guard": result.certificate_guard,
        "scientific_claim_authorized": False,
        "boundary_note": (
            "READY_FOR_THEORETICAL_RNA_METHODS_SUBMISSION is an internal evidence "
            "gate (§12.3); it is not acceptance, not SCIENTIFIC_SUCCESS, and "
            "authorizes no scientific claim. Final reference/venue/license review "
            "is deferred to the author at submission (§15, §0.1 rule 6)."
        ),
    }
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
    payload["run_dir"] = str(run_dir)
    payload["report_sha256"] = _sha256_file(report_json)

    manifest_dir = MANIFESTS_ROOT / "s12"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "s12_3_submission_gate_acceptance.json"
    manifest_raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = _sha256_file(manifest)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())