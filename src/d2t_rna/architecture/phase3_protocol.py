"""Conditional Phase 3 (plan §P3): architecture-iteration protocol.

Per plan §P3, core architecture may only be reconsidered once prior
experiments *locate a concrete computational bottleneck*.  The Phase 1
scalability report (`v7_p1_scalability_report.v1`) does exactly that:

* the cap-free exhaustive oracle is exact only within an allocation space
  ``<= 81`` (``max_allocation_space``), and ``beyond_exact_scale`` is
  ``UNKNOWN_NOT_ASSERTED``;
* ``t2_integer_lp`` reaches only 80% coverage (64/80 cells executed OK); the
  other 16 cells are fail-closed withheld certificates because the integer LP
  exceeds its budget;
* current LP dimensions are tiny (2 decision variables, 1 threshold
  constraint per catalog class), so the exact kernel has not yet been shown to
  scale.

This module pre-registers the *protocol* for the at-most-three candidate
architecture schemes required by §P3 (typed exact kernel/certificate; robust
catalog worst-pair/mixture objective; exact-scaling branch-and-bound /
cutting-plane / column generation / provable-bound approximation), each with
the ten required fields (bottleneck, why-current-insufficient, new-capability,
basis, minimal implementation, risk, control, ablation, success threshold,
failure rollback).  It binds the actual scalability / baseline-suite artifact
SHAs and computes the bottleneck facts from the real artifact payload (no
fabricated numbers).  The manifest is deterministic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# status / decision vocabulary
# ---------------------------------------------------------------------------

PHASE3_STATE = "BOTTLENECK_IDENTIFIED_PROTOCOL_PRE_REGISTERED"
PHASE3_IMPLEMENTATION = "NOT_IMPLEMENTED_AWAITING_PROTOCOL_SELECTION"
MAX_SCHEMES = 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _bottleneck_facts(scalability: dict, baseline_suite: dict) -> dict:
    """Derive the measured bottleneck facts from the real artifacts."""
    coverage = scalability.get("coverage", {})
    oracle_cov = coverage.get("exhaustive_oracle", {}).get("coverage")
    intlp_cov = coverage.get("t2_integer_lp", {}).get("coverage")
    oracle_ok = coverage.get("exhaustive_oracle", {}).get("executed_ok_cells")
    intlp_ok = coverage.get("t2_integer_lp", {}).get("executed_ok_cells")

    boundary = scalability.get("exact_oracle_boundary", {})
    max_alloc = boundary.get("max_allocation_space")
    beyond = boundary.get("beyond_exact_scale", "UNKNOWN_NOT_ASSERTED")

    lp_dims = scalability.get("lp_dims_by_catalog_class", {})
    lp_max_vars = max(
        (c.get("n_decision_variables", 0) for c in lp_dims.values()), default=0
    )
    lp_max_cons = max(
        (c.get("n_threshold_constraints", 0) for c in lp_dims.values()), default=0
    )

    n_cells = scalability.get("n_cells")
    withheld = (n_cells - intlp_ok) if (n_cells and intlp_ok is not None) else None

    return {
        "n_cells": n_cells,
        "oracle_coverage": oracle_cov,
        "oracle_executed_ok": oracle_ok,
        "integer_lp_coverage": intlp_cov,
        "integer_lp_executed_ok": intlp_ok,
        "integer_lp_withheld_certificates": withheld,
        "exact_oracle_max_allocation_space": max_alloc,
        "exact_oracle_boundary": boundary.get("exact_solvable_boundary"),
        "beyond_exact_scale": beyond,
        "lp_max_decision_variables": lp_max_vars,
        "lp_max_threshold_constraints": lp_max_cons,
    }


def _scheme_typed_exact_kernel() -> dict:
    return {
        "id": "A_TYPED_EXACT_KERNEL_CERTIFICATE",
        "name": "typed exact kernel / certificate",
        "bottleneck": (
            "exact engine is exact only within allocation space <= 81 and is "
            "not asserted beyond it; correctness depends on hand-built "
            "formulation/checks with no sealed independent replay at scale"
        ),
        "why_current_insufficient": (
            "the Phase-1 exact oracle and LP carry 2-variable formulations and "
            "do not yet demonstrate a typed, reusable kernel whose certificate "
            "replays on larger catalogs without re-deriving A,b,c by hand"
        ),
        "new_capability": (
            "a single typed spec->solver->certificate->independent-checker "
            "pipeline (DISCRETE_CATALOG x ACTION_L1/TV) with canonical "
            "fraction certificates and machine-derived measures"
        ),
        "basis": "P0 Batch 2 typed-theorem dispatch and certificate-v2 round-trip tests",
        "minimal_implementation": (
            "extend the existing exact kernel to expose a typed dispatch entry "
            "and an independent oracle over raw serialized matrices, covering "
            "allocation spaces up to the measured 81-boundary"
        ),
        "risk": "moderate: certificate/checker must stay byte-exact across solver versions",
        "control": "cap-free exhaustive oracle as correctness reference; independent raw oracle",
        "ablation": "dispatch on uncertainty_set x separation_measure; convex/product-TV left UNSUPPORTED",
        "success_threshold": (
            "independent oracle matches production on all 80 cells; certificate "
            "tamper-tests pass at allocation space == 81"
        ),
        "failure_rollback": "revert to current exact kernel; no architecture change",
    }


def _scheme_robust_catalog_objective() -> dict:
    return {
        "id": "B_ROBUST_CATALOG_WORST_PAIR_MIXTURE",
        "name": "robust catalog worst-pair / mixture objective",
        "bottleneck": (
            "per-pair benchmarks report worst single pair, but a catalog-level "
            "decision is not yet optimized against a worst-pair or mixture "
            "objective, so no single allocation is certified across the whole "
            "catalog"
        ),
        "why_current_insufficient": (
            "Phase4-v2 ranks comparable baselines per 80 cells independently; "
            "there is no catalog-level certificate that one allocation is "
            "minimax-valid across all pre-registered pairs"
        ),
        "new_capability": (
            "a robust catalog objective (worst-pair or mixture) producing a "
            "single certificate whose risk is valid for every pair in the "
            "sealed family"
        ),
        "basis": "P1-6.1 sealed family split + P1-6.2 catalog registry (4 classes x 5 pairs)",
        "minimal_implementation": (
            "compute the worst-pair and mixture objectives over the 20 "
            "pre-registered pairs; bind to the sealed family split"
        ),
        "risk": "medium: worst-pair may be dominated by one adversarial pair; must pre-register mixture weights",
        "control": "per-pair Phase4-v2 cells as reference; no pair excluded post hoc",
        "ablation": "worst-pair vs equal-weight mixture vs per-pair-only",
        "success_threshold": (
            "a single robust allocation is certified for all 20 pairs with "
            "provable risk, without lowering any per-pair bound"
        ),
        "failure_rollback": "drop the robust objective; keep per-pair reporting only",
    }


def _scheme_exact_scaling() -> dict:
    return {
        "id": "C_EXACT_SCALING_BB_CP_CG",
        "name": "exact scaling (branch-and-bound / cutting-plane / column generation / provable bound)",
        "bottleneck": (
            "exhaustive oracle is exact only up to allocation space 81 and the "
            "integer LP reaches only 80% coverage (16 fail-closed withheld "
            "certificates); beyond this scale is UNKNOWN_NOT_ASSERTED"
        ),
        "why_current_insufficient": (
            "the cap-free exhaustive enumeration and the plain integer LP do "
            "not provably scale; t2_integer_lp exceeds budget on 20% of cells"
        ),
        "new_capability": (
            "branch-and-bound / cutting-plane / column generation, or a "
            "provable-bound approximation, that extends the exact-solvable "
            "boundary beyond 81 and brings the integer LP back within budget"
        ),
        "basis": "scalability report: integer_lp coverage 0.8, max_allocation_space 81",
        "minimal_implementation": (
            "a provable-bound approximation for one catalog class that certifies "
            "the cells currently withheld (allocation space > 81)"
        ),
        "risk": "high: bounding must be rigorous; an unproven heuristic is not allowed",
        "control": "cap-free exhaustive oracle on cells within the 81 boundary",
        "ablation": "exact vs provable-bound on allocation spaces 41..81 vs >81",
        "success_threshold": (
            "provable bound reproduces the exact oracle on the 81-boundary and "
            "certifies withheld cells without exceeding budget; gap reported"
        ),
        "failure_rollback": "keep exhaustive oracle boundary; mark beyond-scale UNKNOWN_NOT_ASSERTED",
    }


def build_phase3_protocol(
    scalability_artifact: Path,
    baseline_suite_artifact: Path,
    *,
    head: str = "",
) -> dict:
    """Build the deterministic Phase 3 architecture-iteration protocol manifest.

    Bottleneck facts are read from the real scalability and baseline-suite
    artifacts (SHA-bound); the three candidate scheme analyses are the
    pre-registered protocol content.
    """
    scalability = _load(scalability_artifact)
    baseline_suite = _load(baseline_suite_artifact)
    facts = _bottleneck_facts(scalability, baseline_suite)

    schemes = [
        _scheme_typed_exact_kernel(),
        _scheme_robust_catalog_objective(),
        _scheme_exact_scaling(),
    ]

    return {
        "schema": "d2t_rna.v7_phase3_protocol.v1",
        "phase": "P3",
        "head": head,
        "state": PHASE3_STATE,
        "implementation": PHASE3_IMPLEMENTATION,
        "bottleneck_identified_from": "v7_p1_scalability_report.v1 + v7_p1_baseline_suite.v1",
        "bottleneck_facts": facts,
        "max_schemes_considered": MAX_SCHEMES,
        "schemes": schemes,
        "selection": {
            "selected_scheme": "NONE_YET_PROTOCOL_PRE_REGISTERED",
            "selection_criteria": [
                "must close at least one measured bottleneck (coverage or allocation-space boundary)",
                "must keep fail-closed semantics (no unproven heuristic as fact)",
                "must bind to a pre-registered sealed family split",
            ],
        },
        "input_artifacts_sha256": {
            scalability_artifact.name: _sha256(scalability_artifact),
            baseline_suite_artifact.name: _sha256(baseline_suite_artifact),
        },
    }
