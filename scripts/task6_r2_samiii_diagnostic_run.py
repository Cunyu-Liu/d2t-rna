"""D2T-RNA v7 §8.5 SAM-III R2 modality-transfer diagnostic runner.

Consumes the §8.3 R1 materialized canonical data
(``sam-iii.canonical.json``) and runs the fail-closed modality-transfer
diagnostic (contract 8.4/8.5).  Because DMS reactivity is a continuous
per-nucleotide measure and is not a registered categorical observation
channel over latent structural states, the action semantics are never
comparable by the registered action space; the diagnostic closes
``NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE`` and authorizes no claim.

Writes an auditable run report + test log and freezes the acceptance
manifest (``scientific_claim_authorized=false``).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from d2t_rna.data.r2_sam_iii_diagnostic import (
    NOT_COMPARABLE,
    sam_iii_modality_diagnostic,
)

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")
CANONICAL = "/mnt/cunyuliu/d2t-rna/data/task6/sam-iii/sam-iii.canonical.json"


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    canonical = Path(CANONICAL)
    if not canonical.exists():
        print("ERROR: canonical sam-iii data not materialized (run R1 first)", file=sys.stderr)
        return 1

    diag = sam_iii_modality_diagnostic(canonical)

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"task6-r2-samiii-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "contract_section": "8.5",
        "kind": "R2_SAMIII_MODALITY_TRANSFER_DIAGNOSTIC",
        "canonical_source": str(canonical),
        "run_finished": time.time(),
        "diagnostic": diag.as_dict(),
        "verdict": diag.verdict,
        "condition_count": len(diag.conditions),
        "scientific_claim_authorized": False,
        "boundary_note": (
            "R2 sam-iii is a post-freeze modality-transfer diagnostic, not a "
            "merged benchmark or prospective/blinded/held-out validation "
            "(contract 8.4/8.5). DMS reactivity is continuous per-nucleotide "
            "and not a registered categorical observation channel over latent "
            "states, so action semantics are not comparable by the registered "
            "action space."
        ),
    }
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(report, indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())

    # Self-check: all 10 conditions materialized (5 constructs x 2 conditions),
    # each with a positive covered-position count, verdict is fail-closed.
    self_check_ok = bool(
        diag.verdict in (NOT_COMPARABLE,)
        and len(diag.conditions) == 10
        and all(c.n_positions > 0 for c in diag.conditions)
        and all(c.covered > 0 for c in diag.conditions)
    )
    test_log = run_dir / "test.log"
    test_log.write_text(
        f"R2 sam-iii self-check: diagnostic_ok={self_check_ok}\n"
        f"verdict={diag.verdict}\n"
        f"action_semantics_comparable={diag.action_semantics_comparable}\n"
        f"conditions={len(diag.conditions)}\n"
    )
    test_log_sha = _sha256_of_bytes(test_log.read_bytes())

    payload = {
        "contract_section": "8.5",
        "kind": "R2_SAMIII_MODALITY_TRANSFER_DIAGNOSTIC",
        "run_dir": str(run_dir),
        "run_finished": time.time(),
        "report": report,
        "report_sha256": report_sha,
        "test_log_sha256": test_log_sha,
        "self_check_ok": self_check_ok,
        "verdict": diag.verdict,
        "status": "DIAGNOSTIC_RUN",
        "scientific_claim_authorized": False,
        "boundary_note": report["boundary_note"],
    }
    manifest_dir = MANIFESTS_ROOT / "task6r"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "task6r_r2_samiii_diagnostic_acceptance.json"
    manifest_raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = _sha256_of_bytes(manifest_raw)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())