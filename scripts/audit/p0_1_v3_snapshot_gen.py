"""P0-1 generator: v3 snapshot / claim freeze / authority index / terminalization.

Binds to the current frozen HEAD/tree.  Old v2 bytes are preserved untouched;
this step only emits NEW v3 manifests under manifests/audit/ and marks the
affected legacy artifacts paper_eligible=false (authority-level tombstone,
without yet claiming consumer enforcement).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/cunyuliu/d2t-rna")
AUDIT = REPO / "manifests" / "audit"

NOW = datetime.now(timezone.utc).astimezone().isoformat()

# Key artifact roots to terminalize (bytes preserved; science authority revoked).
LEGACY_FAMILIES = [
    # (artifact_family, paths, scientific status)
    ("p0_repair_acceptance", ["manifests/audit/v7_p0_repair_acceptance.json"], "LEGACY_INVALID"),
    ("phase4v2_minimax_catalog", [
        "manifests/audit/v7_phase1_acceptance_v2.json",
        "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase4v2.json",
    ], "LEGACY_INVALID"),
    ("phase5_mechanism", [
        "manifests/audit/v7_p5_claim_register_v2.json",
        "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase5v2_mechanism.json",
        "/mnt/cunyuliu/d2t-rna/artifacts/phase5/mechanism.json",
    ], "LEGACY_INVALID"),
    ("phase4_comparative", [
        "manifests/audit/v7_p4_comparative_v1.json",
        "/mnt/cunyuliu/d2t-rna/artifacts/phase4/p4_comparative.json",
    ], "LEGACY_INVALID"),
    ("real_measured_certificates", [
        "manifests/data/add_qualification_v2.json",
        "manifests/data/glycine_qualification_v2.json",
        "manifests/data/minittr_qualification_v2.json",
    ], "DESCRIPTIVE_ONLY"),
    ("paper_readiness", [
        "manifests/paper/paper_submission_readiness.json",
        "manifests/paper/submission_readiness_report.md",
        "manifests/audit/v7_p6_submission_receipt.json",
    ], "LEGACY_INVALID"),
]


def git(args: list[str]) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO)] + args,
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def sha256_file(path: str) -> str:
    if not os.path.exists(path):
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    head = git(["rev-parse", "HEAD"])
    tree = git(["rev-parse", "HEAD^{tree}"])
    origin = git(["rev-parse", "origin/main"])
    revlist = git(["rev-list", "--left-right", "--count", "origin/main...HEAD"])
    ahead_behind = {"ahead": int(revlist.split()[1]), "behind": int(revlist.split()[0])}
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    status = git(["status", "--short", "--branch"])

    contract_sha = "776662393e42ff2fd5d662cc0ad8ac4896224097d1ace987c60d1ab166e5d67c"
    contract_path = "提示词/D2T-RNA提示词.md"

    # ---- 1) snapshot ----
    snapshot = {
        "schema": "d2t_rna.v7_p0_semantic_repair_snapshot.v3",
        "phase": "P0-1",
        "created_at": NOW,
        "snapshot_kind": "SEMANTIC_REPAIR_PRECONDITION_FREEZE",
        "head": head,
        "tree": tree,
        "origin_main": origin,
        "branch": branch,
        "ahead_behind": ahead_behind,
        "worktree_clean": True,
        "git_status": status,
        "contract": {
            "path": contract_path,
            "sha256": contract_sha,
        },
        "code_scope": "remote /home/cunyuliu/d2t-rna",
        "python": "3.11.15",
        "state": {
            "P0_SEMANTIC_REPAIR": "P0_BLOCKED_WITH_EVIDENCE",
            "SEMANTIC_SOFTWARE_SUCCESS": "WITHDRAWN_PENDING_REPAIR",
            "COMPARATIVE_SYNTHETIC_STATUS": "INVALID_PENDING_METRIC_AND_METHOD_ROLE_REPAIR",
            "REAL_DATA_ROUTE": "TERMINATED_FOR_CURRENT_DATA",
            "SOTA_STATUS": "SOTA_NOT_ADJUDICATED",
            "SCIENTIFIC_SUBMISSION_STATUS": "SCIENTIFIC_SUBMISSION_BLOCKED",
            "CURRENT_STAGE": "A",
        },
        "note": "Snapshot binds the audit object; it does not claim any code repair is complete.",
    }

    # ---- 2) claim freeze v3 ----
    claim_freeze = {
        "schema": "d2t_rna.v7_claim_freeze.v3",
        "authority_role": "CLAIM_FREEZE",
        "generator": "D2T-RNA v7 science-repair execution (P0-1)",
        "generator_commit": head,
        "receipt": {"created_at": NOW, "note": "Non-deterministic metadata."},
        "payload": {
            "head": head,
            "tree": tree,
            "scientific_claim_authorized": False,
            "current_stage": "A",
            "submission_status": "SCIENTIFIC_SUBMISSION_BLOCKED",
            "sota_status": "SOTA_NOT_ADJUDICATED",
            "real_data_route": "TERMINATED_FOR_CURRENT_DATA",
            "prohibited_claims_until_gate": [
                "measured_sample_size", "absolute_probability", "repeat_count",
                "wet_lab_saving", "cross_system_transferability",
                "sota_superiority", "real_measured_certificate_with_bare_gamma_as_TV",
            ],
            "downgraded_measured_claims": {
                "add_miniTTR_n3": "PERMANENT_DESCRIPTIVE_DOWNGRADE",
                "glycine_n15": "PERMANENT_DESCRIPTIVE_DOWNGRADE",
                "sam_iii_n3": "PERMANENT_DESCRIPTIVE_DOWNGRADE",
            },
            "reactflow_evidence_count_allowed": 0,
        },
    }

    # ---- 3) authority index v3 ----
    index = []
    for family, paths, sci in LEGACY_FAMILIES:
        for p in paths:
            index.append({
                "artifact": p,
                "role": "scientific_evidence",
                "file_integrity": "LEGACY_VALID" if os.path.exists(p) else "FILE_NOT_FOUND",
                "scientific_interpretation": sci,
                "paper_eligible": False,
                "terminal_status": "TERMINALIZED",
                "sha256": sha256_file(p),
                "schema": "legacy/authority-tombstone",
                "superseded_by": "phase4v3-diagnostic / corrected v3 lineage",
                "note": "Bytes preserved for audit; scientific authority revoked until v3 regeneration.",
            })
    index.append({
        "artifact": "manifests/audit/v7_claim_evidence_graph_v2.json",
        "role": "claim_graph",
        "file_integrity": "LEGACY_VALID",
        "scientific_interpretation": "LEGACY_INVALID",
        "paper_eligible": False,
        "terminal_status": "TERMINALIZED",
        "sha256": sha256_file("manifests/audit/v7_claim_evidence_graph_v2.json"),
        "schema": "legacy/authority-tombstone",
        "note": "Only 4 synthetic nodes; not full-coverage; requires v3 claim-evidence rebuild.",
    })
    # ReactFlow / external evidence must be 0 in D2T paper scope.
    reactflow = [e for e in index if "reactflow" in e["artifact"].lower()]
    authority_index = {
        "schema": "d2t_rna.v7_artifact_authority_index.v3",
        "authority_role": "ARTIFACT_AUTHORITY_INDEX",
        "generator": "D2T-RNA v7 science-repair execution (P0-1)",
        "generator_commit": head,
        "receipt": {"created_at": NOW},
        "payload": {
            "head": head,
            "tree": tree,
            "authority_principle": "Role-sensitive; bytes preserved, scientific authority revoked.",
            "d2t_paper_eligible_reactflow_evidence_count": len(reactflow),
            "index": index,
        },
    }

    # ---- 4) terminalization v3 ----
    terminalization = {
        "schema": "d2t_rna.v7_artifact_terminalization.v3",
        "authority_role": "FINAL_TERMINALIZATION",
        "generator": "D2T-RNA v7 science-repair execution (P0-1)",
        "generator_commit": head,
        "receipt": {"created_at": NOW, "principle": "Old bytes preserved; authority tombstoned."},
        "payload": {
            "head": head,
            "tree": tree,
            "paper_render_resolution": "RENDERER_MUST_REJECT_INVALID_ID",
            "families": [
                {
                    "artifact_family": fam,
                    "file_integrity": "LEGACY_VALID",
                    "scientific_interpretation": sci,
                    "final_status": sci,
                    "paper_eligible": False,
                    "v3_lineage_slot": "phase4v3-diagnostic / corrected v3",
                }
                for fam, _, sci in LEGACY_FAMILIES
            ],
        },
    }

    outputs = {
        "manifests/audit/v7_p0_semantic_repair_v3_snapshot.json": snapshot,
        "manifests/audit/v7_claim_freeze_v3.json": claim_freeze,
        "manifests/audit/v7_artifact_authority_index_v3.json": authority_index,
        "manifests/audit/v7_artifact_terminalization_v3.json": terminalization,
    }
    for rel, obj in outputs.items():
        out = REPO / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
        print(f"WROTE {rel}  sha256={sha256_file(str(out))}")


if __name__ == "__main__":
    main()
