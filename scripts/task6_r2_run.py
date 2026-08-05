"""D2T-RNA v7 §8.4 R2 fail-closed retrospective report runner.

Reads the current Task6-R manifest state (read-only) and maps it to the §8.4
R2 gates, producing an auditable fail-closed report.  Real empirical R2 metrics
(compression / degradation / abstention / reason-code / structural mapping) are
only possible once the observed data is materialized within the registered
fixed dataset and the observation model / dependency graph / independence proof
are established; until then every dataset closes as ``NOT_ESTABLISHED``.
"""

from __future__ import annotations

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


def _gate_profile(manifests_root: Path, dataset_id: str) -> dict[str, bool]:
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
        "observed_data_materialized": bool(private.raw_fastq_downloaded),
        "observation_model_available": obs_available,
        "dependency_graph_available": dep_status == "REGISTERED",
        "independence_proof_available": False,
        "no_held_out_blinded_prospective": True,
    }


def main() -> int:
    manifests_root = Path("/home/cunyuliu/d2t-rna/manifests")
    profiles = {did: _gate_profile(manifests_root, did) for did in REGISTERED_DATASETS}
    report = r2_evaluate_all(profiles)
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
        "scientific_claim_authorized": False,
        "boundary_note": (
            "R2 is confined to a fixed observed dataset; no held-out/blinded/"
            "prospective/independent-validation claim. Empirical metrics are "
            "gated on R1 materialization and observation-model/dependency-graph/"
            "independence proof (fail-closed, contract 8.4)."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())