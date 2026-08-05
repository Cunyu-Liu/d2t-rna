"""D2T-RNA v7 §8.4 R2 fail-closed retrospective report runner.

Reads the current Task6-R manifest state (read-only) and maps it to the §8.4
R2 gates, producing an auditable fail-closed report.  Real empirical R2 metrics
(compression / degradation / abstention / reason-code / structural mapping) are
only possible once the observed data is materialized within the registered
fixed dataset and the observation model / dependency graph / independence proof
are established; until then every dataset closes as ``NOT_ESTABLISHED``.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

from d2t_rna.data.manifest import (
    PublicPlanningStub,
    PrivateProvenanceManifest,
)
from d2t_rna.data.r2_evaluation import (
    EVALUATION_LABEL,
    REGISTERED_DATASETS,
    r2_evaluate_all,
)
from d2t_rna.contracts.base import parse_contract_json

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _r1_materialized(data_root: Path, dataset_id: str) -> bool:
    """True when the §8.3 R1 materialization evidence exists on disk.

    R1 writes a canonical JSON + a sha256 sidecar next to the raw data.  For
    add/RMDB the observed data is a reactivity matrix and for sam-iii it is the
    DANCE-MaP reactivity supplement (neither is fastq reads), so the
    materialization state is read from these artifacts, not from the manifest's
    ``raw_fastq_downloaded`` field.  rorc has no public official accession to
    materialize (contract 8.5; INELIGIBLE_UNRESOLVED_METADATA).
    """
    sentinels = {
        "add": ("ADDRSW_SHP_0003.canonical.json", "ADDRSW_SHP_0003.sha256"),
        "sam-iii": ("sam-iii.canonical.json", "sam-iii.sha256"),
    }
    if dataset_id not in sentinels:
        return False
    ds_dir = data_root / "task6" / dataset_id
    return all((ds_dir / name).exists() for name in sentinels[dataset_id])


def _gate_profile(manifests_root: Path, data_root: Path, dataset_id: str) -> dict[str, bool]:
    root = manifests_root / dataset_id.replace("-", "_")
    public = parse_contract_json(PublicPlanningStub, (root / "public_planning_stub.json").read_bytes())
    private = parse_contract_json(
        PrivateProvenanceManifest,
        (root / "private_provenance_manifest.json").read_bytes(),
    )
    dep_status = public.dependency_graph.graph_status
    # observation model availability: only sam-iii registers a structural /
    # probing modality; independence proof is not established for any dataset.
    obs_available = dataset_id == "sam-iii"
    return {
        "within_registered_fixed_dataset": True,
        "observed_data_materialized": _r1_materialized(data_root, dataset_id),
        "observation_model_available": obs_available,
        "dependency_graph_available": dep_status == "REGISTERED",
        "independence_proof_available": False,
        "no_held_out_blinded_prospective": True,
    }


def _sam_iii_diagnostic_verdict(manifests_root: Path) -> str | None:
    """Read the §8.5 sam-iii modality-diagnostic acceptance verdict if present."""
    p = manifests_root / "task6r" / "task6r_r2_samiii_diagnostic_acceptance.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_bytes()).get("verdict")
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    manifests_root = MANIFESTS_ROOT
    data_root = Path("/mnt/cunyuliu/d2t-rna/data")
    profiles = {
        did: _gate_profile(manifests_root, data_root, did)
        for did in REGISTERED_DATASETS
    }
    report = r2_evaluate_all(profiles)
    samiii_verdict = _sam_iii_diagnostic_verdict(manifests_root)

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"task6-r2-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "contract_section": "8.4",
        "kind": "R2_RETROSPECTIVE_FAILL_CLOSED_REPORT",
        "label": EVALUATION_LABEL,
        "run_finished": time.time(),
        "gate_profiles": {did: dict(p) for did, p in profiles.items()},
        "report": report.as_dict(),
        "certificate_guard": (
            "ESTABLISHED" if report.all_established else "NOT_ESTABLISHED"
        ),
        "sam_iii_modality_diagnostic_verdict": samiii_verdict,
        "scientific_claim_authorized": False,
        "boundary_note": (
            "R2 is confined to a fixed observed dataset; no held-out/blinded/"
            "prospective/independent-validation claim. Empirical metrics are "
            "gated on R1 materialization and observation-model/dependency-graph/"
            "independence proof (fail-closed, contract 8.4). Under authority "
            "amendment V7_AMEND_12_3_6_20260805 each dataset's terminal outcome "
            "is classified: add (continuous SHAPE) is "
            "NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL, sam-iii (continuous "
            "DMS) is NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE (§8.5), and rorc "
            "(no public accession) is NOT_APPLICABLE. These are fail-closed "
            "terminal roles, not established quantitative instances."
        ),
    }
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())

    # Self-check: every registered dataset closes fail-closed when any gate is
    # missing; the certificate_guard is NOT_ESTABLISHED unless all pass.
    datasets = report.as_dict()["datasets"]
    self_check_ok = bool(
        all(s["status"] == "NOT_ESTABLISHED" for s in datasets)
        or report.all_established
    )
    test_log = run_dir / "test.log"
    test_log.write_text(
        f"R2 self-check: fail_closed={self_check_ok}\n"
        f"certificate_guard={payload['certificate_guard']}\n"
        f"datasets={[s['dataset_id'] for s in datasets]}\n"
        f"sam_iii_verdict={samiii_verdict}\n"
    )
    test_log_sha = _sha256_of_bytes(test_log.read_bytes())

    payload["run_dir"] = str(run_dir)
    payload["report_sha256"] = report_sha
    payload["test_log_sha256"] = test_log_sha
    payload["self_check_ok"] = self_check_ok

    manifest_dir = MANIFESTS_ROOT / "task6r"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "task6r_r2_acceptance.json"
    manifest_raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = _sha256_of_bytes(manifest_raw)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())