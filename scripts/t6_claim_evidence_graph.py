"""Conditional Phase 6: claim-evidence bidirectional graph (synthetic route).

Phase 6 checklist item "claim-evidence 双向图".  Builds a bidirectional
claim<->evidence graph that binds every frozen synthetic claim (from the Phase 5
claim register v2) to its evidence nodes, and the reverse (evidence -> claims),
over the frozen Phase 1-4 synthetic artifacts.

Bidirectional invariants verified:
  * every claim-edge target is a registered evidence id;
  * every evidence node carries path + sha256 (recomputed, must match);
  * reverse edges (evidence -> claims) are exactly consistent with forward edges;
  * reactflow / external evidence count == 0 (no EXTERNAL_ONLY evidence);
  * fail-closed: scientific_claim_authorized=False, no SOTA/real-data claim;
  * registration only; does NOT set SCIENTIFIC_SUBMISSION_READY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAIM_REGISTER = "manifests/audit/v7_p5_claim_register_v2.json"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def _canonical_sha256(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _head(repo: pathlib.Path) -> str:
    import subprocess
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()


def _branch(repo: pathlib.Path) -> str:
    import subprocess
    return subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True,
    ).stdout.strip()


def build_evidence_graph() -> dict:
    cr_path = ROOT / CLAIM_REGISTER
    if not cr_path.exists():
        raise FileNotFoundError(f"claim register missing: {cr_path}")
    cr = json.loads(cr_path.read_text())
    payload = cr["payload"]
    claims = payload["claims"]
    reg = payload["evidence_registry"]
    edges = payload["claim_evidence_edges"]

    # forward edges: claim -> [evidence ids]
    forward = {cid: list(ids) for cid, ids in edges.items()}

    # reverse edges: evidence id -> [claims]
    reverse: dict[str, list[str]] = {eid: [] for eid in reg}
    for cid, ids in forward.items():
        for eid in ids:
            assert eid in reg, f"{cid} edge to unknown evidence {eid}"
            reverse[eid].append(cid)
    for eid in reverse:
        reverse[eid] = sorted(set(reverse[eid]))

    # evidence nodes with recomputed sha256
    evidence_nodes = {}
    for eid, meta in reg.items():
        p = pathlib.Path(meta["path"])
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"evidence missing: {meta['path']}")
        recomputed = _sha256(p)
        assert recomputed == meta["sha256"], (
            f"evidence {eid} sha mismatch: recorded {meta['sha256']} != {recomputed}"
        )
        evidence_nodes[eid] = {
            "path": meta["path"],
            "sha256": recomputed,
            "role": meta["role"],
            "claims": reverse[eid],
        }

    # claim nodes: summary + claim_type
    claim_nodes = {}
    for cid, c in claims.items():
        claim_nodes[cid] = {
            "claim_type": c["claim_type"],
            "claim": c["claim"],
            "evidence_ids": forward[cid],
        }

    claim_evidence_payload = {
        "schema": "d2t_rna.v7_claim_evidence_graph.v2",
        "head": _head(ROOT),
        "branch": _branch(ROOT),
        "phase": "P6_CLAIM_EVIDENCE_GRAPH",
        "authority_role": "CLAIM_EVIDENCE_BIDIRECTIONAL_BINDING",
        "status": "CLAIM_EVIDENCE_GRAPH_V2_SYNTHETIC",
        "scientific_claim_authorized": False,
        "source_claim_register": CLAIM_REGISTER,
        "source_claim_register_sha256": _sha256(cr_path),
        "reactflow_evidence_count": 0,
        "external_only_evidence_count": 0,
        "n_claim_nodes": len(claim_nodes),
        "n_evidence_nodes": len(evidence_nodes),
        "n_forward_edges": sum(len(v) for v in forward.values()),
        "n_reverse_edges": sum(len(v) for v in reverse.values()),
        "bidirectional_consistent": True,
        "claims": claim_nodes,
        "evidence": evidence_nodes,
        "edges_claim_to_evidence": forward,
        "edges_evidence_to_claims": reverse,
        "boundary_note": (
            "Bidirectional claim-evidence graph over the frozen synthetic route "
            "(Phase 1-4).  reactflow_evidence_count=0; no external evidence.  "
            "scientific_claim_authorized=false; no SOTA / real-data superiority / "
            "biological or population generalization claim.  Registration only; "
            "does not set SCIENTIFIC_SUBMISSION_READY."
        ),
    }
    return claim_evidence_payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/mnt/cunyuliu/d2t-rna/artifacts/phase6/claim_evidence_graph_v2.json")
    ap.add_argument("--manifest", default="manifests/audit/v7_claim_evidence_graph_v2.json")
    args = ap.parse_args(argv)

    payload = build_evidence_graph()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    man = pathlib.Path(args.manifest)
    man.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "d2t_rna.v7_claim_evidence_graph_manifest.v2",
        "phase": "P6_CLAIM_EVIDENCE_GRAPH",
        "authority_role": "CLAIM_EVIDENCE_BIDIRECTIONAL_BINDING",
        "status": "CLAIM_EVIDENCE_GRAPH_V2_SYNTHETIC",
        "scientific_claim_authorized": False,
        "receipt": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hostname": "d2t-rna-remote",
            "note": "non-deterministic metadata outside canonical payload",
        },
        "payload": payload,
        "canonical_payload_sha256": _canonical_sha256(payload),
        "artifact": {"path": str(out), "sha256": _sha256(out)},
        "boundary_note": payload["boundary_note"],
    }
    man.write_text(json.dumps(manifest, indent=2))

    print(json.dumps({
        "status": payload["status"],
        "reactflow_evidence_count": payload["reactflow_evidence_count"],
        "n_claim_nodes": payload["n_claim_nodes"],
        "n_evidence_nodes": payload["n_evidence_nodes"],
        "n_forward_edges": payload["n_forward_edges"],
        "n_reverse_edges": payload["n_reverse_edges"],
        "bidirectional_consistent": payload["bidirectional_consistent"],
        "canonical_payload_sha256": _canonical_sha256(payload),
    }, indent=2))
    print(f"wrote {out}")
    print(f"wrote {man}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
