"""P2 runner: generate the Conditional Phase 2 real-data protocol manifest.

Writes ``manifests/audit/v7_phase2_protocol_v1.json`` (deterministic canonical
payload bound to the per-domain qualification v2 manifests) and prints a short
receipt.  The current-data REAL_DATA_ROUTE is recorded as
TERMINATED_FOR_CURRENT_DATA per plan §P2.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from d2t_rna.data.phase2_protocol import build_phase2_protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DATA = PROJECT_ROOT / "manifests" / "data"
OUT_PATH = PROJECT_ROOT / "manifests" / "audit" / "v7_phase2_protocol_v1.json"


def _head() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "UNKNOWN"


def main() -> int:
    if not MANIFESTS_DATA.is_dir():
        print(f"fatal: no manifests/data dir at {MANIFESTS_DATA}", file=sys.stderr)
        return 1

    head = _head()
    manifest = build_phase2_protocol(MANIFESTS_DATA, head=head)

    # canonical payload is fully deterministic; created_at is receipt-only
    receipt = {
        "schema": manifest["schema"],
        "phase": "P2",
        "head": head,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(OUT_PATH),
        "output_sha256": _sha256(json.dumps(manifest, sort_keys=True).encode()),
        "real_data_route_for_current_data": manifest["real_data_route_for_current_data"],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
