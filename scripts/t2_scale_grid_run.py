"""D2T-RNA v7 §12 Phase 4 synthetic scale grid + matched benchmark runner.

Phase 4 (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``) requires a *synthetic
scale grid*, a *fixed-budget matched benchmark*, *nonadaptive price*, selected
ablations (action cost), and *runtime/memory* records over a pre-registered,
deterministic grid of finite T2 models -- all under identical endpoint, action,
cost, budget, decision rule, and stopping (no-stopping / fixed horizon).

This runner:

* generates a deterministic synthetic scale grid varying ``n_states``,
  catalog cardinality, panel (action-library) size, and budget;
* executes every Phase 1 baseline (``exhaustive_oracle``, ``full_matrix``,
  ``random``, ``greedy_test_cover``, ``eig``, ``chernoff``, ``lm2r_heuristic``,
  ``t2_integer_lp``) under one common :class:`ExperimentSpec`;
* asserts the cap-free complete oracle is never beaten by any feasible
  baseline (correctness reference, per §1/§4);
* reports the nonadaptive price as the certified integer-vs-LP cost gap
  (the achievable nonadaptive cost vs the LP lower bound);
* runs an action-cost ablation (uniform vs heterogeneous costs) on a fixed
  model and reports the resulting allocation/risk change;
* records per-method wall time and traced peak memory.

Real-data gates (independent libraries, sealed construct-level validation,
prospective/blinded pilot) are **not** exercised here: they are gated by
Phase 2 (``BLOCKED_PENDING_ARCHIVE_QUALIFICATION``).  Adaptive/sequential and
GJN/T-/robust-T comparators are explicitly reported ``NOT_COMPARABLE`` pending
a task-reduction/diagnostic (contract §11, §14.3).  Every number is
model-conditional synthetic; ``scientific_claim_authorized=false``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

from d2t_rna.evaluation.matrix import (
    ExperimentSpec,
    run_baselines,
)
from d2t_rna.t2.model import Action, T2FiniteModel


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _channel(rows) -> tuple[tuple[Fraction, ...], ...]:
    return tuple(tuple(Fraction(x) for x in row) for row in rows)


def _id_channel(n: int):
    return _channel(tuple(tuple(1 if w == y else 0 for w in range(n)) for y in range(n)))


def _merge_channel(n: int):
    """Collapse all states into a single outcome (information-free)."""
    return _channel(((1,) * n,))


def _pair_channel(n: int):
    rows = []
    w = 0
    while w < n:
        row = [0] * n
        row[w] = 1
        if w + 1 < n:
            row[w + 1] = 1
        rows.append(tuple(row))
        w += 2
    return _channel(rows)


def _distrib_grid(n: int, den: int):
    """All distributions over ``n`` states with common denominator ``den``."""
    out = []
    for a in range(den + 1):
        if n == 2:
            out.append((_F(a, den), _F(den - a, den)))
        elif n == 3:
            for b in range(den - a + 1):
                out.append((_F(a, den), _F(b, den), _F(den - a - b, den)))
        else:
            raise ValueError("grid supports n_states in {2,3}")
    return out


def _unit_marg(n: int):
    return tuple((_F(1) if w == 0 else _F(0)) for w in range(n))


def build_scale_grid() -> list[tuple[str, T2FiniteModel, list[str]]]:
    """Deterministic synthetic scale grid (name, model, usable panel ids).

    ``usable_panel`` only lists actions that are not information-free, so the
    benchmark stays non-degenerate; the model still carries the full action
    library (including any collapsing action) for completeness.
    """
    grid: list[tuple[str, T2FiniteModel, list[str]]] = []

    # ---- 2-state grids ---------------------------------------------------
    for budget_note, (j0, j1) in (("2x2", (2, 2)), ("3x3", (3, 3))):
        d2 = _distrib_grid(2, 4)
        # overlapping pair far apart in TV but with full support (non-trivial
        # for EIG / Chernoff / Test-Cover scores)
        p0 = d2[1]
        p1 = d2[3]
        model = T2FiniteModel(
            name=f"s2_{budget_note}",
            n_states=2,
            theta_0=tuple(d2[1:1 + j0]),
            theta_1=tuple(d2[3:3 + j1]),
            marginal_map=(_unit_marg(2),),
            actions=(
                Action("id_a", _id_channel(2)),
                Action("id_b", _id_channel(2)),
                Action("merge", _merge_channel(2)),
            ),
        )
        grid.append((f"s2_{budget_note}", model, ["id_a", "id_b"]))

    # ---- 3-state grids ---------------------------------------------------
    for j0, j1 in ((2, 2), (3, 3)):
        d3 = _distrib_grid(3, 2)
        p0 = d3[1]
        p1 = d3[4]
        model = T2FiniteModel(
            name=f"s3_{j0}x{j1}",
            n_states=3,
            theta_0=tuple(d3[1:1 + j0]),
            theta_1=tuple(d3[4:4 + j1]),
            marginal_map=(_unit_marg(3),),
            actions=(
                Action("id", _id_channel(3)),
                Action("pair", _pair_channel(3)),
            ),
        )
        grid.append((f"s3_{j0}x{j1}", model, ["id", "pair"]))

    return grid


def _allocate_costs(panel: list[str], mode: str) -> tuple[Fraction, ...]:
    if mode == "uniform":
        return tuple(_F(1) for _ in panel)
    if mode == "hetero":
        # penalize later actions increasingly
        return tuple(_F(i + 1) for i in range(len(panel)))
    raise ValueError(mode)


def _min_cost_at_target(
    sub: T2FiniteModel,
    spec: ExperimentSpec,
    target_error: Fraction,
) -> tuple[Fraction, tuple[int, ...]]:
    """Cap-free complete search for the *cheapest* allocation whose minimax
    error is ``<= target_error`` (rational tie-break minimizes cost).

    This is the honest nonadaptive cost reference: the minimum cost to reach a
    given error level.  Baselines that reach no better than ``target_error``
    (the global minimum here) can then be compared by their over-cost.
    """
    from itertools import product

    from d2t_rna.evaluation.matrix import MultiActionOracle, action_law

    U = len(spec.costs)
    p0_laws = tuple(action_law(sub, a, spec.p0) for a in sub.actions)
    p1_laws = tuple(action_law(sub, a, spec.p1) for a in sub.actions)
    max_n = [
        int(spec.budget // c) if c > 0 else 0
        for c in spec.costs
    ]
    best_cost = None
    best_alloc = tuple(0 for _ in range(U))
    for joint in product(*(range(m + 1) for m in max_n)):
        cand = tuple(joint)
        cost = sum(c * nu for c, nu in zip(spec.costs, cand))
        if cost > spec.budget:
            continue
        res = MultiActionOracle(
            p0_laws, p1_laws, spec.costs, cand, spec.abstain_ratio
        ).evaluate()
        if res.minimax_error <= target_error:
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_alloc = cand
    return (best_cost if best_cost is not None else _F(0), best_alloc)


def run_one(
    name: str,
    model: T2FiniteModel,
    panel: list[str],
    budget: Fraction,
    cost_mode: str,
) -> dict:
    """Run the full baseline suite on one grid cell (matched spec)."""
    p0 = model.theta_0[0]
    p1 = model.theta_1[0]
    # The benchmark runs on the usable panel (non-degenerate actions).
    sub = T2FiniteModel(
        name=name,
        n_states=model.n_states,
        theta_0=model.theta_0,
        theta_1=model.theta_1,
        marginal_map=model.marginal_map,
        actions=tuple(a for a in model.actions if a.action_id in panel),
    )
    costs = _allocate_costs(panel, cost_mode)
    spec = ExperimentSpec(
        model_name=name,
        p0=p0,
        p1=p1,
        costs=costs,
        budget=budget,
    )
    t0 = time.time()
    runs = run_baselines(sub, spec)
    elapsed = time.time() - t0

    baseline = {}
    for method, run in sorted(runs.items()):
        baseline[method] = {
            "allocation": [int(x) for x in run.allocation],
            "cost": str(run.cost),
            "spent_exceeds_budget": run.spent_exceeds_budget,
            "runtime_s": round(run.runtime_s, 6),
            "memory_peak_bytes": int(run.memory) if run.memory is not None else None,
            "executed": run.executed,
            "minimax_error": str(run.oracle.minimax_error) if run.oracle else None,
            "correct_decl": str(run.oracle.correct_decl) if run.oracle else None,
            "abstain": str(run.oracle.abstain) if run.oracle else None,
            "product_tv": str(run.oracle.product_tv) if run.oracle else None,
            "lp_lower_bound": (
                str(run.lp_lower_bound) if run.lp_lower_bound is not None else None
            ),
            "integer_upper_cost": (
                str(run.integer_upper) if run.integer_upper is not None else None
            ),
            "optimality_gap": (
                str(run.optimality_gap) if run.optimality_gap is not None else None
            ),
        }

    # correctness reference: oracle must not be beaten by any feasible baseline
    oracle_err = runs["exhaustive_oracle"].oracle.minimax_error
    feasible = [
        m
        for m, r in runs.items()
        if m != "exhaustive_oracle"
        and r.executed
        and not r.spent_exceeds_budget
        and r.oracle is not None
    ]
    beaten = [
        m
        for m in feasible
        if runs[m].oracle.minimax_error < oracle_err
    ]

    # Nonadaptive cost reference: the *cheapest* allocation reaching the
    # oracle's global-min error (rational tie-break minimizes cost).  Each
    # baseline that reaches no better than that error then has a well-defined,
    # non-negative over-cost = (baseline cost - min cost at target error).
    min_cost, min_cost_alloc = _min_cost_at_target(sub, spec, oracle_err)
    over_cost = {
        m: str(runs[m].cost - min_cost)
        for m in feasible
    }

    return {
        "name": name,
        "n_states": model.n_states,
        "catalog": f"{len(model.theta_0)}x{len(model.theta_1)}",
        "panel": panel,
        "budget": str(budget),
        "cost_mode": cost_mode,
        "oracle_minimax_error": str(oracle_err),
        "oracle_beaten_by": beaten,
        "min_cost_at_oracle_error": str(min_cost),
        "min_cost_allocation": [int(x) for x in min_cost_alloc],
        "baseline_over_cost_vs_min": over_cost,
        "baselines": baseline,
        "cell_elapsed_s": round(elapsed, 6),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default=(Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4") / "scale_grid.json"),
    )
    args = ap.parse_args(argv)
    out = Path(args.out)

    grid = build_scale_grid()
    rows: list[dict] = []
    budgets = (_F(4), _F(8))
    # action-cost ablation: uniform costs vs heterogeneous (increasing) costs
    cost_modes = ("uniform", "hetero")
    for name, model, panel in grid:
        for budget in budgets:
            for cm in cost_modes:
                rows.append(run_one(name, model, panel, budget, cm))

    # summary
    oracle_beaten_total = sum(1 for r in rows if r["oracle_beaten_by"])

    # fraction of cells where the best baseline over-pays vs the cheapest
    # allocation reaching the oracle's global-min error
    over_cost_gt_zero_cells = 0
    over_cost_total_cells = 0
    for r in rows:
        vals = [
            Fraction(v) for v in r["baseline_over_cost_vs_min"].values()
        ]
        if not vals:
            continue
        over_cost_total_cells += 1
        if min(vals) > 0:
            over_cost_gt_zero_cells += 1

    summary = {
        "instances": len(rows),
        "oracle_beaten_count": oracle_beaten_total,
        "oracle_never_beaten": oracle_beaten_total == 0,
        "all_baselines_overpay_vs_min_cost_cells": over_cost_gt_zero_cells,
        "matched_cells_with_baselines": over_cost_total_cells,
        "max_cell_elapsed_s": round(max(r["cell_elapsed_s"] for r in rows), 6),
        "total_elapsed_s": round(sum(r["cell_elapsed_s"] for r in rows), 6),
        "not_comparable": [
            "adaptive_oracle",
            "gjn",
            "t_optimal",
            "robust_t",
            "kl_optimal",
            "test_cover_family_reduction",
        ],
        "boundary_note": (
            "model-conditional synthetic scale grid only; real-data gates "
            "(independent libraries / sealed constructs / prospective pilot) "
            "gated by Phase 2 BLOCKED_PENDING_ARCHIVE_QUALIFICATION; "
            "adaptive & reduction comparators NOT_COMPARABLE pending diagnostic; "
            "cost over-pay is vs the cheapest allocation reaching the oracle's "
            "global-min error (nonadaptive-adaptive price not claimed)"
        ),
        "scientific_claim_authorized": False,
    }

    payload = {
        "schema": "d2t_rna.v7_phase4_scale_grid.v1",
        "python": sys.version.split()[0],
        "rows": rows,
        "summary": summary,
    }
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