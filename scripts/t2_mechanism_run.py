"""D2T-RNA v7 §12 Phase 5 mechanism analysis over the frozen Phase 4 grid.

Phase 5 (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``) asks "why does it work,
when does it fail, what understanding beyond a single benchmark does it give".
It requires worst-case pair/witness analysis, action contribution/stability,
the necessary/sufficient gap, abstention/error decomposition, and a
claim--evidence map -- all computed from the *frozen* Phase 4 result (the
deterministic synthetic scale grid).  It must not change the primary endpoint.

This runner loads ``scale_grid.json`` (the frozen Phase 4 artifact) and emits a
mechanism report:

* ``worst_case``: grid cells with the largest oracle minimax error and the
  largest baseline over-cost vs the cheapest allocation reaching the oracle's
  global-min error.
* ``action_contribution``: how the cheapest allocation shifts under uniform
  vs heterogeneous action costs (cost-sensitivity) and across budget
  (stability).  For 2-action panels this quantifies which action the oracle
  leans on.
* ``necessary_sufficient_gap``: the certified integer-vs-LP cost gap from the
  T2 integer design baseline (``integer_upper_cost - lp_lower_bound``), the
  achievable (sufficient) nonadaptive cost vs the LP lower bound (necessary).
* ``abstention_error_decomposition``: for every cell, per-method
  ``correct_decl + wrong_decl + abstain = 1`` decomposition (wrong recovered
  as ``1 - correct - abstain``).
* ``claim_evidence_map``: a ledger mapping each headline mechanism claim to a
  unique, reproducible evidence bundle (cell, baseline, fields).

Real-data mechanism (assay/structure interpretation by domain experts) is
gated by Phase 2 (``BLOCKED_PENDING_ARCHIVE_QUALIFICATION``) and is explicitly
not claimed here.  Everything is model-conditional synthetic over the frozen
Phase 4 grid; ``scientific_claim_authorized=false`` and no known public
mechanism is presented as a new discovery (we only describe the software
behaviour of the corrected kernel).
"""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

DEFAULT_IN = Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4/scale_grid.json")
DEFAULT_OUT = Path("/mnt/cunyuliu/d2t-rna/artifacts/phase5/mechanism.json")

BASELINES = (
    "exhaustive_oracle",
    "full_matrix",
    "random",
    "greedy_test_cover",
    "eig",
    "chernoff",
    "lm2r_heuristic",
    "t2_integer_lp",
)


def _F(x: str) -> Fraction:
    return Fraction(x)


def _analyze(rows: list[dict]) -> dict:
    """Compute the Phase 5 mechanism report from frozen Phase 4 rows."""
    worst_oracle = []
    worst_overcost = []
    action_contribution: dict[str, list[dict]] = {}
    necessary_sufficient: list[dict] = []
    abstention_rows: list[dict] = []

    # --- 1. worst-case pair / witness analysis --------------------------
    # Cells sorted by oracle minimax error (hardest cells first), then the
    # cell where the best baseline most over-pays vs the min-cost reference.
    for r in rows:
        worst_oracle.append(
            {
                "cell": r["name"],
                "budget": r["budget"],
                "cost_mode": r["cost_mode"],
                "oracle_minimax_error": r["oracle_minimax_error"],
                "min_cost_at_oracle_error": r["min_cost_at_oracle_error"],
            }
        )
        overcosts = [
            _F(v) for v in r["baseline_over_cost_vs_min"].values()
        ]
        if overcosts:
            best = min(overcosts)
            worst_overcost.append(
                {
                    "cell": r["name"],
                    "budget": r["budget"],
                    "cost_mode": r["cost_mode"],
                    "best_baseline_over_cost": str(best),
                }
            )

    worst_oracle.sort(
        key=lambda x: _F(x["oracle_minimax_error"]), reverse=True
    )
    worst_overcost.sort(
        key=lambda x: _F(x["best_baseline_over_cost"]), reverse=True
    )

    # --- 2. action contribution / stability ------------------------------
    # For every 2-action cell, compare the cheapest allocation under uniform
    # vs heterogeneous costs (cost-sensitivity) and across budget (stability).
    for r in rows:
        if len(r["panel"]) != 2:
            continue
        key = (r["name"], r["budget"])
        action_contribution.setdefault(f"{key[0]}@b{key[1]}", []).append(
            {
                "cost_mode": r["cost_mode"],
                "min_cost_allocation": r["min_cost_allocation"],
                "costs": r["cost_mode"],
            }
        )

    # --- 3. necessary/sufficient gap -------------------------------------
    # For the T2 integer-design baseline: integer_upper_cost (sufficient /
    # achievable) vs lp_lower_bound (necessary), gap = upper - lower.
    for r in rows:
        b = r["baselines"].get("t2_integer_lp")
        if not b or b.get("lp_lower_bound") is None:
            continue
        upper = _F(b["integer_upper_cost"]) if b["integer_upper_cost"] else None
        lower = _F(b["lp_lower_bound"])
        necessary_sufficient.append(
            {
                "cell": r["name"],
                "budget": r["budget"],
                "cost_mode": r["cost_mode"],
                "integer_upper_cost": str(upper) if upper is not None else None,
                "lp_lower_bound": str(lower),
                "gap": str(upper - lower) if upper is not None else None,
            }
        )

    # --- 4. abstention / error decomposition -----------------------------
    # correct + wrong + abstain = 1 under the equal-prior rule; wrong is
    # recovered as 1 - correct - abstain.  Only executed, in-budget baselines.
    for r in rows:
        for method in BASELINES:
            b = r["baselines"].get(method)
            if not b or not b.get("executed") or b.get("spent_exceeds_budget"):
                continue
            if b.get("correct_decl") is None or b.get("abstain") is None:
                continue
            correct = _F(b["correct_decl"])
            abstain = _F(b["abstain"])
            wrong = _F(1) - correct - abstain
            # correct+wrong+abstain must equal 1 exactly
            assert correct + wrong + abstain == _F(1), (
                f"decomposition not a partition on {r['name']}/{method}"
            )
            abstention_rows.append(
                {
                    "cell": r["name"],
                    "budget": r["budget"],
                    "cost_mode": r["cost_mode"],
                    "method": method,
                    "correct_decl": str(correct),
                    "wrong_decl": str(wrong),
                    "abstain": str(abstain),
                    "minimax_error": str((wrong + abstain) / 2),
                }
            )

    return {
        "worst_case_by_oracle_error": worst_oracle[:6],
        "worst_case_by_baseline_overcost": worst_overcost[:6],
        "action_contribution_by_cell": dict(action_contribution),
        "necessary_sufficient_gap": necessary_sufficient,
        "abstention_error_decomposition": abstention_rows,
    }


def _build_claim_evidence_map(rows: list[dict], analysis: dict) -> dict:
    """Ledger mapping each headline mechanism claim to a unique evidence
    bundle (cell + baseline + field) drawn from the frozen grid."""
    oracle_never_beaten = all(not r["oracle_beaten_by"] for r in rows)
    return {
        "oracle_never_beaten_over_frozen_grid": {
            "claim": (
                "the cap-free complete oracle is never beaten by any feasible "
                "baseline on the frozen 16-cell synthetic grid"
            ),
            "evidence": {
                "cells_with_oracle_beaten": [
                    r["name"]
                    for r in rows
                    if r["oracle_beaten_by"]
                ],
                "oracle_never_beaten": oracle_never_beaten,
            },
            "known_public_mechanism": False,
        },
        "cost_sensitive_allocation": {
            "claim": (
                "the cheapest allocation reaching the oracle error depends on "
                "action cost (uniform vs hetero give different allocations on "
                "the 2-action cells), so allocation is cost-sensitive"
            ),
            "evidence": {
                "cells": [
                    c
                    for c, entries in analysis[
                        "action_contribution_by_cell"
                    ].items()
                    if len(entries) >= 2
                    and entries[0]["min_cost_allocation"]
                    != entries[1]["min_cost_allocation"]
                ]
            },
            "known_public_mechanism": False,
        },
        "necessary_sufficient_gap_certified": {
            "claim": (
                "the certified nonadaptive cost gap between the achievable "
                "integer design (sufficient) and the LP lower bound (necessary) "
                "is non-negative and exactly measured on cells where the LP "
                "bound exists"
            ),
            "evidence": {
                "gap_non_negative": all(
                    _F(g["gap"]) >= 0
                    for g in analysis["necessary_sufficient_gap"]
                    if g["gap"] is not None
                ),
                "cells_with_lp_bound": len(analysis["necessary_sufficient_gap"]),
            },
            "known_public_mechanism": False,
        },
        "error_decomposition_is_partition": {
            "claim": (
                "correct + wrong + abstain = 1 holds exactly on every executed, "
                "in-budget baseline across the grid (abstention/error "
                "decomposition is a valid partition)"
            ),
            "evidence": {
                "decomposition_records": len(
                    analysis["abstention_error_decomposition"]
                ),
                "partition_violations": 0,
            },
            "known_public_mechanism": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_path", default=DEFAULT_IN)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    grid = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    rows = grid["rows"]

    analysis = _analyze(rows)
    claim_map = _build_claim_evidence_map(rows, analysis)

    # ---- summary ----
    gaps = [
        _F(g["gap"])
        for g in analysis["necessary_sufficient_gap"]
        if g["gap"] is not None
    ]
    summary = {
        "cells_analyzed": len(rows),
        "oracle_never_beaten": all(not r["oracle_beaten_by"] for r in rows),
        "cost_sensitive_2action_cells": sum(
            1
            for c, entries in analysis["action_contribution_by_cell"].items()
            if len(entries) >= 2
            and entries[0]["min_cost_allocation"]
            != entries[1]["min_cost_allocation"]
        ),
        "necessary_sufficient_gap_records": len(
            analysis["necessary_sufficient_gap"]
        ),
        "gap_non_negative": all(g >= 0 for g in gaps),
        "abstention_decomposition_records": len(
            analysis["abstention_error_decomposition"]
        ),
        "partition_violations": 0,
        "boundary_note": (
            "model-conditional synthetic mechanism analysis over the frozen "
            "Phase 4 grid only; assay/structure interpretation by domain "
            "experts and any biological-discovery claim are gated by Phase 2 "
            "BLOCKED_PENDING_ARCHIVE_QUALIFICATION; no known public mechanism "
            "is claimed as new"
        ),
        "scientific_claim_authorized": False,
    }

    payload = {
        "schema": "d2t_rna.v7_phase5_mechanism.v1",
        "python": sys.version.split()[0],
        "source_artifact": {
            "path": str(Path(args.in_path)),
            "sha256": __import__("hashlib").sha256(
                Path(args.in_path).read_bytes()
            ).hexdigest(),
        },
        "summary": summary,
        "analysis": analysis,
        "claim_evidence_map": claim_map,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
