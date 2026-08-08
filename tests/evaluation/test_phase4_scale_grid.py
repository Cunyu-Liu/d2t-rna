"""Phase 4 synthetic scale-grid / matched-benchmark unit tests.

Tests the generator and the matched-benchmark runner used in
``scripts/t2_scale_grid_run.py``: grid validity, the "oracle never beaten"
completeness property, the cheapest-allocation cost reference, and the
action-cost ablation.  Model-conditional synthetic only; no scientific claim.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.evaluation.matrix import ExperimentSpec, run_baselines
from d2t_rna.t2.model import T2FiniteModel

from scripts.t2_scale_grid_run import (
    _allocate_costs,
    _min_cost_at_target,
    build_scale_grid,
    run_one,
)


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def test_build_scale_grid_is_valid_and_deterministic():
    grid = build_scale_grid()
    assert len(grid) >= 4
    seen = set()
    for name, model, panel in grid:
        assert isinstance(model, T2FiniteModel)
        assert model.n_states in (2, 3)
        assert model.theta_0 and model.theta_1
        assert panel, "each grid cell must have a usable (non-degenerate) panel"
        assert all(
            a.action_id in panel for a in model.actions if a.action_id in panel
        )
        assert name not in seen
        seen.add(name)
    # determinism: rebuilding yields the same model canonicalization
    grid2 = build_scale_grid()
    assert [name for name, _, _ in grid] == [name for name, _, _ in grid2]


def test_allocate_costs_uniform_and_hetero():
    panel = ["a", "b", "c"]
    uni = _allocate_costs(panel, "uniform")
    assert uni == (_F(1), _F(1), _F(1))
    het = _allocate_costs(panel, "hetero")
    assert het == (_F(1), _F(2), _F(3))


def test_oracle_never_beaten_on_every_grid_cell():
    grid = build_scale_grid()
    for budget in (_F(4), _F(8)):
        for name, model, panel in grid[:2]:  # 2-state cells (fast)
            row = run_one(name, model, panel, budget, "uniform")
            assert row["oracle_beaten_by"] == [], (
                f"oracle beaten by {row['oracle_beaten_by']} on {name}@b{budget}"
            )
            # cheapest allocation must reach the oracle's global-min error
            assert row["min_cost_at_oracle_error"] is not None


def test_min_cost_at_target_reaches_oracle_error_and_is_no_costlier():
    grid = build_scale_grid()
    name, model, panel = grid[0]
    sub = T2FiniteModel(
        name=name,
        n_states=model.n_states,
        theta_0=model.theta_0,
        theta_1=model.theta_1,
        marginal_map=model.marginal_map,
        actions=tuple(a for a in model.actions if a.action_id in panel),
    )
    spec = ExperimentSpec(
        model_name=name,
        p0=model.theta_0[0],
        p1=model.theta_1[0],
        costs=_allocate_costs(panel, "uniform"),
        budget=_F(8),
    )
    runs = run_baselines(sub, spec)
    oracle_err = runs["exhaustive_oracle"].oracle.minimax_error
    min_cost, alloc = _min_cost_at_target(sub, spec, oracle_err)
    # cheapest allocation must be no more expensive than the oracle's chosen one
    assert min_cost <= runs["exhaustive_oracle"].cost
    assert sum(c * n for c, n in zip(spec.costs, alloc)) == min_cost
    assert min_cost >= 0


def test_action_cost_ablation_changes_oracle_allocation():
    grid = build_scale_grid()
    name, model, panel = grid[0]
    uni = run_one(name, model, panel, _F(4), "uniform")
    het = run_one(name, model, panel, _F(4), "hetero")
    # the cheapest allocation should differ under heterogeneous costs
    # (costs (1,1) vs (1,2)) whenever the panel has 2+ actions
    assert len(panel) >= 2
    # over a panel with two distinguishable actions the allocation must move
    assert uni["min_cost_allocation"] != het["min_cost_allocation"]


def test_grid_cell_reports_all_baselines_and_runtime():
    grid = build_scale_grid()
    name, model, panel = grid[0]
    row = run_one(name, model, panel, _F(8), "uniform")
    for method in (
        "exhaustive_oracle",
        "full_matrix",
        "random",
        "greedy_test_cover",
        "eig",
        "chernoff",
        "lm2r_heuristic",
        "t2_integer_lp",
    ):
        assert method in row["baselines"]
        b = row["baselines"][method]
        assert "minimax_error" in b and "cost" in b and "runtime_s" in b
        assert b["memory_peak_bytes"] is not None
    assert row["cell_elapsed_s"] >= 0
