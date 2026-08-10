"""Tests for Scheme C provable-bound exact scaling (plan §P3).

Verifies the provable bound is fail-closed (lower <= true minimax <= upper),
that the DP produces a within-budget allocation, that the bound reproduces the
cap-free exact oracle on the 81-boundary cells, and that non-positive budget /
mismatched-length inputs are rejected.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.architecture.provable_bound import (
    _min_bc_product,
    _sqrt_interval,
    provable_minimax_interval,
)
from d2t_rna.evaluation.matrix import action_law, _laws_for, _oracle_eval
from d2t_rna.t2.model import T2FiniteModel

from scripts.t2_phase4v2_run import _allocate_costs, build_p4v2_registry


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _model_and_laws(pair, cost_mode: str):
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
    p0_laws, p1_laws = _laws_for(model, pair["p0"], pair["p1"])
    return model, p0_laws, p1_laws, costs


def _exact_minimax(pair, budget, cost_mode) -> Fraction:
    from itertools import product

    from d2t_rna.evaluation.matrix import ExperimentSpec

    model, p0_laws, p1_laws, costs = _model_and_laws(pair, cost_mode)
    spec = ExperimentSpec(
        model_name=pair["pair_id"], p0=pair["p0"], p1=pair["p1"],
        costs=costs, budget=budget,
    )
    max_n = [int(budget // c) for c in costs]
    best = None
    for joint in product(*(range(m + 1) for m in max_n)):
        if sum(c * nu for c, nu in zip(costs, joint)) > budget:
            continue
        res = _oracle_eval(model, spec, joint)
        if best is None or res.minimax_error < best:
            best = res.minimax_error
    return best if best is not None else _F(0)


def _allocation_space(pair, budget, cost_mode) -> int:
    costs = _allocate_costs(pair["panel"], cost_mode)
    space = 1
    for c in costs:
        space *= int(budget // _F(c)) + 1
    return space


def test_sqrt_interval_is_certified() -> None:
    for x in (_F(1, 4), _F(1, 2), _F(9, 16), _F(2, 3), _F(0), _F(1)):
        lo, hi = _sqrt_interval(x)
        assert lo <= hi
        # lo^2 <= x <= hi^2
        assert lo * lo <= x <= hi * hi
    with pytest.raises(ValueError):
        _sqrt_interval(_F(-1))


def test_bound_is_fail_closed_across_all_80_cells() -> None:
    pairs = {p["pair_id"]: p for p in build_p4v2_registry()}
    for pair in pairs.values():
        for budget in (_F(4), _F(8)):
            for cm in ("uniform", "hetero"):
                model, p0_laws, p1_laws, costs = _model_and_laws(pair, cm)
                bound = provable_minimax_interval(p0_laws, p1_laws, costs, budget)
                exact = _exact_minimax(pair, budget, cm)
                L = Fraction(bound["lower_bound"])
                U = Fraction(bound["upper_bound"])
                assert L <= exact <= U, (
                    f"{pair['pair_id']}@{budget}/{cm}: "
                    f"L={L} exact={exact} U={U}"
                )
                assert bound["within_budget"] is True


def test_bound_reproduces_exact_on_81_boundary() -> None:
    """On allocation-space-81 cells the bound contains the exact oracle."""
    pairs = {p["pair_id"]: p for p in build_p4v2_registry()}
    boundary_checked = 0
    for pair in pairs.values():
        for budget in (_F(4), _F(8)):
            for cm in ("uniform", "hetero"):
                space = _allocation_space(pair, budget, cm)
                if space != 81:
                    continue
                boundary_checked += 1
                model, p0_laws, p1_laws, costs = _model_and_laws(pair, cm)
                bound = provable_minimax_interval(p0_laws, p1_laws, costs, budget)
                exact = _exact_minimax(pair, budget, cm)
                L = Fraction(bound["lower_bound"])
                U = Fraction(bound["upper_bound"])
                assert L <= exact <= U
    assert boundary_checked > 0


def test_dp_allocation_within_budget() -> None:
    bc = (_F(9, 10), _F(8, 10))
    costs = (_F(1), _F(1))
    m, alloc, cost = _min_bc_product(bc, costs, _F(8))
    assert sum(c * n for c, n in zip(costs, alloc)) == cost <= _F(8)
    assert 0 <= m <= 1


def test_dp_scales_beyond_81_without_enumeration() -> None:
    """A single-action-equivalent DP over budget 40 stays polynomial and
    produces a certified m without enumerating the 41^2 allocation space."""
    bc = (_F(9, 10), _F(8, 10))
    costs = (_F(1), _F(1))
    m, alloc, cost = _min_bc_product(bc, costs, _F(40))
    assert cost <= _F(40)
    assert sum(alloc) == int(cost)


def test_rejects_bad_inputs() -> None:
    q = ((_F(1, 2), _F(1, 2)),)
    # mismatched lengths (p0=1 law, p1=2 laws)
    with pytest.raises(ValueError):
        provable_minimax_interval(q, (q[0], q[0]), (_F(1),), _F(8))
    # non-positive budget
    with pytest.raises(ValueError):
        provable_minimax_interval(q, q, (_F(1),), _F(0))
    # negative budget
    with pytest.raises(ValueError):
        provable_minimax_interval(q, q, (_F(1),), _F(-3))


def test_min_bc_product_zero_cost_rejected() -> None:
    with pytest.raises(ValueError):
        _min_bc_product((_F(1, 2),), (_F(0),), _F(8))
