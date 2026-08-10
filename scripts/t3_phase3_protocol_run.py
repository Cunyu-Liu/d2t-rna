"""P3 runner: generate the Conditional Phase 3 architecture protocol manifest.

Reads the real Phase 1 scalability and baseline-suite artifacts, derives the
measured bottleneck facts, and writes the deterministic protocol manifest
``manifests/audit/v7_phase3_protocol_v1.json``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from d2t_rna.architecture.phase3_protocol import build_phase3_protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4v2")
SCALABILITY = ARTIFACTS / "scalability.json"
BASELINE_SUITE = ARTIFACTS / "baseline_suite.json"
OUT_PATH = PROJECT_ROOT / "manifests" / "audit" / "v7_phase3_protocol_v1.json"


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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not SCALABILITY.is_file() or not BASELINE_SUITE.is_file():
        print(f"fatal: missing artifacts in {ARTIFACTS}", file=sys.stderr)
        return 1
    head = _head()
    manifest = build_phase3_protocol(SCALABILITY, BASELINE_SUITE, head=head)

    receipt = {
        "schema": manifest["schema"],
        "phase": "P3",
        "head": head,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(OUT_PATH),
        "output_sha256": _sha256(json.dumps(manifest, sort_keys=True).encode()),
        "state": manifest["state"],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
