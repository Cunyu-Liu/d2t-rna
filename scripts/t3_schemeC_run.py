"""P1 6.6+ / §P3 Scheme C: provable-bound exact scaling (one catalog class).

Scheme C (``C_EXACT_SCALING_BB_CP_CG``) minimal implementation: "a
provable-bound approximation for one catalog class that certifies the cells
currently withheld (allocation space > 81)".  Success threshold: "provable
bound reproduces the exact oracle on the 81-boundary and certifies withheld
cells without exceeding budget; gap reported".

This runner:

* takes one catalog class (default ``CA``, the 2-state class whose 16 cells
  the integer LP fails closed on in the Phase-1 grid);
* for that class builds a synthetic budget sweep whose cap-free within-budget
  allocation space spans the 81-boundary and reaches beyond it (budgets such
  that ``prod_u (floor(budget/cost_u)+1)`` crosses 81);
* on cells within the 81-boundary, computes the cap-free exhaustive oracle as
  the correctness reference and verifies the provable bound reproduces it
  (``lower <= exact <= upper``);
* on cells beyond 81, certifies them with the provable bound (DP over budget,
  no allocation enumeration) and reports the gap; the exact oracle there is
  reported ``NOT_RUN`` (beyond the exact boundary, per the scalability
  fail-closed rule) rather than a fabricated number;
* writes a deterministic Scheme-C scaling artifact + a bound manifest to
  ``manifests/audit`` (SHA-bound, deterministic, no timestamp in payload).

Engineering scaling record on synthetic finite models; no formal scientific /
SOTA claim (``scientific_claim_authorized=false``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from fractions import Fraction

from d2t_rna.architecture.provable_bound import provable_minimax_interval
from d2t_rna.evaluation.matrix import action_law
from d2t_rna.t2.model import T2FiniteModel

from scripts.t2_phase4v2_run import _allocate_costs, build_p4v2_registry

ARTIFACT_DIR = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4v2")
MANIFEST_DIR = pathlib.Path("manifests/audit")


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _allocation_space(pair, budget: Fraction, cost_mode: str) -> int:
    panel = pair["panel"]
    costs = _allocate_costs(panel, cost_mode)
    space = 1
    for c in costs:
        space *= int(budget // _F(c)) + 1
    return int(space)


def _exact_minimax(pair, budget: Fraction, cost_mode: str) -> Fraction:
    """Cap-free exhaustive oracle (same semantics as run_baselines oracle)."""
    from scripts.t2_scale_grid_run import _id_channel
    from d2t_rna.evaluation.matrix import _oracle_eval, _laws_for

    panel = pair["panel"]
    model = T2FiniteModel(
        name=pair["pair_id"],
        n_states=pair["n_states"],
        theta_0=(pair["p0"],),
        theta_1=(pair["p1"],),
        marginal_map=pair["marginal_map"],
        actions=tuple(a for a in pair["actions"] if a.action_id in panel),
    )
    costs = _allocate_costs(panel, cost_mode)
    from d2t_rna.evaluation.matrix import ExperimentSpec

    spec = ExperimentSpec(
        model_name=pair["pair_id"], p0=pair["p0"], p1=pair["p1"],
        costs=costs, budget=budget,
    )
    p0_laws, p1_laws = _laws_for(model, pair["p0"], pair["p1"])
    # exhaustive over within-budget allocations (identical to run_baselines)
    max_n = [int(budget // c) for c in costs]
    best = None
    from itertools import product

    for joint in product(*(range(m + 1) for m in max_n)):
        cand_cost = sum(c * nu for c, nu in zip(costs, joint))
        if cand_cost > budget:
            continue
        res = _oracle_eval(model, spec, joint)
        if best is None or res.minimax_error < best:
            best = res.minimax_error
    if best is None:
        return _F(0)
    return best


def _pair_laws(pair, cost_mode: str):
    panel = pair["panel"]
    model = T2FiniteModel(
        name=pair["pair_id"],
        n_states=pair["n_states"],
        theta_0=(pair["p0"],),
        theta_1=(pair["p1"],),
        marginal_map=pair["marginal_map"],
        actions=tuple(a for a in pair["actions"] if a.action_id in panel),
    )
    costs = _allocate_costs(panel, cost_mode)
    p0_laws = tuple(action_law(model, a, pair["p0"]) for a in model.actions)
    p1_laws = tuple(action_law(model, a, pair["p1"]) for a in model.actions)
    return p0_laws, p1_laws, costs


def _head() -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def build_schemeC_report(catalog_class: str = "CA") -> dict:
    """Build the Scheme-C scaling report for one catalog class."""
    pairs = [p for p in build_p4v2_registry() if p["catalog_class"] == catalog_class]
    if not pairs:
        raise ValueError(f"catalog class {catalog_class} has no pairs")

    # budget sweep for the 2-state class: spans <=81 and >81 allocation space.
    # (For class CA the panel is 2 actions at cost 1 each in uniform mode.)
    budgets = (_F(4), _F(8), _F(12), _F(16), _F(20))
    cost_modes = ("uniform", "hetero")

    cells = []
    boundary_cells = []          # exact reproduction on <=81
    beyond_cells = []            # certified beyond 81 (exact NOT_RUN)
    for pair in pairs:
        for budget in budgets:
            for cm in cost_modes:
                space = _allocation_space(pair, budget, cm)
                p0_laws, p1_laws, costs = _pair_laws(pair, cm)
                bound = provable_minimax_interval(p0_laws, p1_laws, costs, budget)
                cell = {
                    "pair_id": pair["pair_id"],
                    "catalog_class": catalog_class,
                    "budget": str(budget),
                    "cost_mode": cm,
                    "allocation_space": space,
                    "within_budget": bound["within_budget"],
                    "lower_bound": bound["lower_bound"],
                    "upper_bound": bound["upper_bound"],
                    "gap": bound["gap"],
                    "allocation": bound["allocation"],
                }
                if space <= 81:
                    exact = _exact_minimax(pair, budget, cm)
                    cell["exact_minimax_error"] = str(exact)
                    cell["exact_status"] = "RUN"
                    L = Fraction(cell["lower_bound"])
                    U = Fraction(cell["upper_bound"])
                    cell["bound_reproduces_exact"] = bool(L <= exact <= U)
                    boundary_cells.append(cell)
                else:
                    cell["exact_minimax_error"] = None
                    cell["exact_status"] = "NOT_RUN_BEYOND_EXACT_BOUNDARY"
                    cell["bound_reproduces_exact"] = None
                    beyond_cells.append(cell)
                cells.append(cell)

    max_space = max(c["allocation_space"] for c in cells)
    n_reproduced = sum(1 for c in boundary_cells if c["bound_reproduces_exact"])
    n_beyond = len(beyond_cells)
    n_beyond_in_budget = sum(1 for c in beyond_cells if c["within_budget"])
    n_gap_reported = sum(1 for c in beyond_cells if c["gap"] is not None)

    return {
        "schema": "d2t_rna.v7_p3_schemeC_scaling.v1",
        "phase": "P3",
        "authority_role": "SCHEME_C_SCALING_RECORD",
        "status": "SCHEME_C_PROVABLE_BOUND_SYNTHETIC",
        "scientific_claim_authorized": False,
        "scheme": "C_EXACT_SCALING_BB_CP_CG",
        "catalog_class": catalog_class,
        "n_pairs": len(pairs),
        "budget_sweep": [str(b) for b in budgets],
        "cost_modes": list(cost_modes),
        "boundary": {
            "exact_oracle_max_allocation_space": 81,
            "schemeC_max_allocation_space": max_space,
            "extended_beyond_81": max_space > 81,
        },
        "summary": {
            "n_cells": len(cells),
            "n_boundary_cells": len(boundary_cells),
            "n_boundary_reproduced": n_reproduced,
            "n_beyond_cells": n_beyond,
            "n_beyond_within_budget": n_beyond_in_budget,
            "n_beyond_gap_reported": n_gap_reported,
        },
        "cells": cells,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog-class", default="CA")
    ap.add_argument(
        "--out-artifact",
        default=str(ARTIFACT_DIR / "schemeC_scaling.json"),
    )
    ap.add_argument(
        "--out-manifest",
        default=str(MANIFEST_DIR / "v7_p3_schemeC_v1.json"),
    )
    args = ap.parse_args(argv)

    report = build_schemeC_report(args.catalog_class)
    head = _head()
    artifact_path = pathlib.Path(args.out_artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    artifact_sha = _sha256_text(artifact_path.read_text())

    manifest = {
        "schema": "d2t_rna.v7_p3_schemeC_manifest.v1",
        "phase": "P3",
        "head": head,
        "state": "SCHEME_C_PROVABLE_BOUND_IMPLEMENTED",
        "selected_scheme": "C_EXACT_SCALING_BB_CP_CG",
        "summary": report["summary"],
        "boundary": report["boundary"],
        "artifact": {
            "path": str(artifact_path),
            "sha256": artifact_sha,
        },
        "scientific_claim_authorized": False,
    }
    manifest_path = pathlib.Path(args.out_manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    s = report["summary"]
    print(
        f"wrote artifact {artifact_path} (sha256={artifact_sha[:16]}...) and "
        f"manifest {manifest_path}: cells={s['n_cells']} "
        f"boundary_reproduced={s['n_boundary_reproduced']}/{s['n_boundary_cells']} "
        f"beyond={s['n_beyond_cells']} within_budget={s['n_beyond_within_budget']} "
        f"max_space={report['boundary']['schemeC_max_allocation_space']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
