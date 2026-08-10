"""Conditional Phase 5: claim register v2 (claim-evidence binding over the
frozen synthetic route).

After the Phase 4 main result is frozen (``v7_p4_comparative_v1``), this
registers the paper claim set for the synthetic/software route, per plan
"Conditional Phase 5 / 论文最多" contract:

  * exactly ONE core claim + THREE secondary claims;
  * every claim carries: required_evidence, available_evidence,
    missing_evidence, prohibited_overinterpretation;
  * fail-closed: ``scientific_claim_authorized=False``,
    ``status=CLAIM_REGISTER_V2_SYNTHETIC``, no SOTA / no real-data superiority /
    no biological or population generalization claim (real-data route is
    TERMINATED_FOR_CURRENT_DATA);
  * every quantitative/strong claim is bound to a unique evidence ID, whose
    artifact path and sha256 are recorded (bidirectional traceability).

This is a registration artifact only.  It does NOT by itself authorize any
scientific claim and does NOT set SCIENTIFIC_SUBMISSION_READY (Phase 6 gate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# frozen synthetic evidence (path + role).  sha256 computed at build time.
# ---------------------------------------------------------------------------

EVIDENCE = {
    "E0_P0_SEMANTIC_REPAIR": {
        "path": "manifests/audit/v7_p0_repair_acceptance.json",
        "role": "P0 semantic-kernel/decision/certificate/oracle repair acceptance",
    },
    "E1_FAMILY_SPLIT": {
        "path": "manifests/audit/v7_p1_family_split_v1.json",
        "role": "pre-registered train/dev/sealed family split (statistical units)",
    },
    "E2_CATALOG_80CELL": {
        "path": "manifests/audit/v7_p1_catalog_registry_v1.json",
        "role": "Phase4-v2 80-cell catalog registry (4 classes x 5 pairs x 2 budgets x 2 cost modes)",
    },
    "E3_ABLATION_12CELL": {
        "path": "manifests/audit/v7_p1_ablation_registry_v1.json",
        "role": "non-equivalent action ablation (12 cells; identical-channel control)",
    },
    "E4_BASELINE_SUITE": {
        "path": "manifests/audit/v7_p1_baseline_suite_v1.json",
        "role": "comparable-only headline baseline suite (oracle = reference, never ranked)",
    },
    "E5_SCALABILITY": {
        "path": "manifests/audit/v7_p1_scalability_v1.json",
        "role": "Phase4-v2 scalability report (runtime/memory/LP dims/gap/coverage)",
    },
    "E6_MECHANISM_P5V2": {
        "path": "manifests/audit/v7_p1_mechanism_v1.json",
        "role": "Phase5-v2 mechanism over corrected grid; legacy Phase5 INVALID_SUPERSEDED",
    },
    "E7_SCHEME_C": {
        "path": "manifests/audit/v7_p3_schemeC_v1.json",
        "role": "Scheme C provable-bound exact scaling (BC product two-sided; extend boundary)",
    },
    "E8_P4_COMPARATIVE": {
        "path": "manifests/audit/v7_p4_comparative_v1.json",
        "role": "Phase 4 comparative + sealed confirmation (COMPARATIVE_SYNTHETIC_RECORD)",
    },
    "E8_ART_P4_COMPARATIVE": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4/p4_comparative.json",
        "role": "Phase 4 comparative immutable artifact",
    },
    "E2_ART_P4V2_GRID": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase4v2.json",
        "role": "Phase4-v2 80-cell immutable artifact",
    },
    "E3_ART_ABLATION": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/ablation.json",
        "role": "12-cell ablation immutable artifact",
    },
    "E4_ART_BASELINE": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/baseline_suite.json",
        "role": "baseline suite immutable artifact (aggregate_wins)",
    },
    "E5_ART_SCALABILITY": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/scalability.json",
        "role": "scalability immutable artifact",
    },
    "E6_ART_MECHANISM": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase5v2_mechanism.json",
        "role": "Phase5-v2 mechanism immutable artifact",
    },
    "E7_ART_SCHEMEC": {
        "path": "/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/schemeC_scaling.json",
        "role": "Scheme C scaling immutable artifact",
    },
}


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


# ---------------------------------------------------------------------------
# claims (exactly one core + three secondary)
# ---------------------------------------------------------------------------

def _claims() -> dict:
    return {
        "C1": {
            "claim_type": "CORE",
            "claim": (
                "On the executed model-conditional synthetic benchmark "
                "(Phase4-v2 80-cell grid + 5 sealed families), the D2T exact "
                "decision framework returns a minimax error no larger than the "
                "matched strongest comparable heuristic on every same-task "
                "instance (per-block d_i <= 0, verified by D2T optimality), and "
                "strictly smaller on the subset where the heuristic misses the "
                "certified optimum (2 strict improvements; 4 comparator "
                "Pareto-dominated across sealed families)."
            ),
            "required_evidence": [
                "per-instance exact-oracle (D2T) and comparable-baseline minimax "
                "errors on the same task (same action panel / budget / cost mode)",
                "certified optimality of the exact oracle (oracle never beaten)",
                "per-block delta d_i = L(D2T) - L(comparator)",
            ],
            "available_evidence": [
                "E2_CATALOG_80CELL / E2_ART_P4V2_GRID (oracle_never_beaten over 80 cells)",
                "E4_BASELINE_SUITE / E4_ART_BASELINE (chernoff aggregate_wins=60, comparable-only)",
                "E8_P4_COMPARATIVE / E8_ART_P4_COMPARATIVE (d_i <= 0, strict_improvement, "
                "comparator_pareto_dominated, pooled_delta_ci)",
            ],
            "missing_evidence": [
                "real-data confirmation (REAL_DATA_ROUTE=TERMINATED_FOR_CURRENT_DATA)",
                "superiority beyond the matched same-task comparable",
                "SOTA adjudication (SOTA_NOT_ADJUDICATED)",
            ],
            "prohibited_overinterpretation": [
                "any SOTA claim",
                "universal / population-level RNA superiority",
                "real-data generalization or biological advantage",
                "'strictly cheaper' unfair comparison",
            ],
        },
        "S1": {
            "claim_type": "SECONDARY",
            "claim": (
                "The exact allocation-space solvability boundary of the D2T "
                "oracle is reproducibly characterized (<= 81 cells), and the "
                "Scheme C provable bound (Bhattacharyya product two-sided) "
                "extends certified coverage to larger allocation spaces (up to "
                "441) with rigorous, verified error intervals (lower <= exact "
                "<= upper on reproduced cells)."
            ),
            "required_evidence": [
                "allocation-space enumeration + exact-oracle errors",
                "certified BC two-sided interval from polynomial-time budget DP",
                "bound reproduces exact (L <= exact <= U) on reproduced cells",
            ],
            "available_evidence": [
                "E5_SCALABILITY / E5_ART_SCALABILITY (exact-oracle boundary <= 81)",
                "E7_SCHEME_C / E7_ART_SCHEMEC (boundary 441; beyond-81 certified cells)",
                "src/d2t_rna/architecture/provable_bound.py + tests",
            ],
            "missing_evidence": [
                "exact certificate for beyond-81 cells (only certified bound, not exact)",
                "tightness beyond the verified interval",
            ],
            "prohibited_overinterpretation": [
                "claiming exact certificates for cells certified only by bounds",
                "treating BOUND_ONLY as CONSTRUCTIVELY_FEASIBLE",
                "claiming tightness beyond the verified interval",
            ],
        },
        "S2": {
            "claim_type": "SECONDARY",
            "claim": (
                "Non-equivalent action panels change the decision-theoretic "
                "optimum in a controlled, pre-registered way: the 12-cell "
                "ablation includes an identical-channel negative control whose "
                "outcome is labeled PRICE_SUBSTITUTION_OR_TIE_CONTROL (no "
                "informativeness/superiority read), and the exact oracle is "
                "never beaten."
            ),
            "required_evidence": [
                "per-cell oracle risk + per-action risk",
                "identical-channel negative control + interpretation lock",
                "crossing-informativeness panels + fixed tie-break",
            ],
            "available_evidence": [
                "E3_ABLATION_12CELL / E3_ART_ABLATION (12 cells; 2 cost x 2 budget)",
                "oracle_never_beaten across 12 cells",
            ],
            "missing_evidence": [
                "real RNA action/cost qualification (REAL_DATA_ROUTE=TERMINATED)",
                "any biological action interpretation",
            ],
            "prohibited_overinterpretation": [
                "interpreting identical-channel cells as action informativeness",
                "biological mechanism / RNA action-cost claims",
                "population or transfer claims",
            ],
        },
        "S3": {
            "claim_type": "SECONDARY",
            "claim": (
                "The synthetic evaluation respects a pre-registered "
                "train/development/sealed-test family split: the 5 sealed "
                "families use a distinct generation mechanism "
                "(dgrid_den5_pairmerge_narrow_noisy) genuinely held out from "
                "train/dev, the D2T solver was not tuned on them, and "
                "block-level statistical units with family/block bootstrap CI "
                "are used (grid cells/seeds are not independent units)."
            ),
            "required_evidence": [
                "pre-registered family split manifest (train/dev/sealed disjoint)",
                "distinct sealed generation mechanism",
                "solver-not-tuned-on-sealed + block-level CI",
            ],
            "available_evidence": [
                "E1_FAMILY_SPLIT (SEALED mechanism dgrid_den5_pairmerge_narrow_noisy)",
                "E8_P4_COMPARATIVE / E8_ART_P4_COMPARATIVE (statistical_unit=block; "
                "sealed; pooled_delta_ci block bootstrap)",
            ],
            "missing_evidence": [
                "real multi-unit confirmation set (requires new acquisition authorization)",
                "population / biological generalization",
            ],
            "prohibited_overinterpretation": [
                "claiming population / biological generalization",
                "claiming real-data validation",
                "treating grid cells/seeds as independent units",
            ],
        },
    }


# ---------------------------------------------------------------------------
# report assembly
# ---------------------------------------------------------------------------

def build_claim_register() -> dict:
    repo = ROOT
    evidence = {}
    for eid, meta in EVIDENCE.items():
        p = pathlib.Path(meta["path"])
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"evidence missing: {meta['path']}")
        evidence[eid] = {
            "path": meta["path"],
            "sha256": _sha256(p),
            "role": meta["role"],
        }

    claims = _claims()
    n_core = sum(1 for c in claims.values() if c["claim_type"] == "CORE")
    n_secondary = sum(1 for c in claims.values() if c["claim_type"] == "SECONDARY")

    payload = {
        "schema": "d2t_rna.v7_p5_claim_register.v1",
        "head": _head(repo),
        "branch": _branch(repo),
        "phase": "P5_CLAIM_REGISTER",
        "authority_role": "CLAIM_EVIDENCE_BINDING_SYNTHETIC",
        "status": "CLAIM_REGISTER_V2_SYNTHETIC",
        "scientific_claim_authorized": False,
        "n_core_claims": n_core,
        "n_secondary_claims": n_secondary,
        "core_plus_secondary": n_core + n_secondary,
        "real_data_route": "TERMINATED_FOR_CURRENT_DATA",
        "sota_status": "SOTA_NOT_ADJUDICATED",
        "prohibited_present": {
            "sota_superiority": False,
            "real_data_superiority": False,
            "biological_or_population_generalization": False,
            "strictly_cheaper_unfair": False,
        },
        "evidence_registry": evidence,
        "claims": claims,
        "claim_evidence_edges": {
            "C1": ["E2_CATALOG_80CELL", "E2_ART_P4V2_GRID",
                   "E4_BASELINE_SUITE", "E4_ART_BASELINE",
                   "E8_P4_COMPARATIVE", "E8_ART_P4_COMPARATIVE"],
            "S1": ["E5_SCALABILITY", "E5_ART_SCALABILITY",
                   "E7_SCHEME_C", "E7_ART_SCHEMEC"],
            "S2": ["E3_ABLATION_12CELL", "E3_ART_ABLATION"],
            "S3": ["E1_FAMILY_SPLIT",
                   "E8_P4_COMPARATIVE", "E8_ART_P4_COMPARATIVE"],
        },
        "boundary_note": (
            "Phase 5 claim register v2 binds the frozen synthetic route "
            "(Phase 1-4).  Exactly one core claim + three secondary claims; "
            "every claim lists required/available/missing evidence and "
            "prohibited over-interpretation.  Fail-closed: "
            "scientific_claim_authorized=false; no SOTA / no real-data "
            "superiority / no biological or population generalization claim; "
            "registration only, does not set SCIENTIFIC_SUBMISSION_READY."
        ),
    }
    return payload


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def _canonical_sha256(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/mnt/cunyuliu/d2t-rna/artifacts/phase5/p5_claim_register_v2.json")
    ap.add_argument("--manifest", default="manifests/audit/v7_p5_claim_register_v2.json")
    args = ap.parse_args(argv)

    payload = build_claim_register()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))

    man = pathlib.Path(args.manifest)
    man.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "d2t_rna.v7_p5_claim_register_manifest.v1",
        "phase": "P5_CLAIM_REGISTER",
        "authority_role": "CLAIM_EVIDENCE_BINDING_SYNTHETIC",
        "status": "CLAIM_REGISTER_V2_SYNTHETIC",
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
        "scientific_claim_authorized": payload["scientific_claim_authorized"],
        "n_core_claims": payload["n_core_claims"],
        "n_secondary_claims": payload["n_secondary_claims"],
        "n_evidence_ids": len(payload["evidence_registry"]),
        "canonical_payload_sha256": _canonical_sha256(payload),
    }, indent=2))
    print(f"wrote {out}")
    print(f"wrote {man}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
