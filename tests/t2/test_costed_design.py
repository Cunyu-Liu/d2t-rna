"""Tests for T2-4 costed design and no-go corollary (contract 5.4 / T2-4).

Covers the exact LP relaxation, dual certificate / dual burden lower bound,
integer covering optimum, integrality gap, no-go certificate, certified-
interval path (integrated with the T2c Hellinger information interval), and
the independent checker receipts (contract 10.3).
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from d2t_rna.t2.costed import (
    CostedDesign,
    achievable_integer_design,
    integrality_gap,
    lp_relax_exact,
    no_go_lower_bound,
    no_go_status,
)
from d2t_rna.t2.costed_verify import (
    check_dual_bound,
    check_dual_feasible,
    check_integer_design_feasible,
    check_integrality_gap,
    check_no_go_sign,
)
from d2t_rna.t2.info import hellinger_info_interval

# ---------------------------------------------------------------------------
# Exact-rational microcases
# ---------------------------------------------------------------------------

# Single action, single pair: min n s.t. n*1 >= 3, cost 2 -> IP = LP = 6, gap 0.
SINGLE = CostedDesign(
    action_ids=("a0",),
    costs=(Fraction(2),),
    pair_ids=("p0",),
    thresholds=(Fraction(3),),
    info_lower=((Fraction(1),),),
    info_upper=((Fraction(1),),),
)


def test_single_pair_integral_zero_gap():
    res = lp_relax_exact(SINGLE.info_upper, SINGLE.costs, SINGLE.thresholds)
    assert res.status == "OPTIMAL"
    assert res.objective == Fraction(6)
    cost, n = achievable_integer_design(SINGLE)
    assert cost == Fraction(6)
    assert tuple(n) == (3,)  # 3 repeats of cost 2
    ub, gap = integrality_gap(SINGLE)
    assert ub == Fraction(6)
    assert gap == Fraction(0)


# Fractional-cover microcase: 3 pairs, 3 actions, A = [[1,0,1],[1,1,0],[0,1,1]],
# tau = (1,1,1), c = (1,1,1).  LP optimum 3/2, integer optimum 2, gap 1/3.
FC_A = (
    (Fraction(1), Fraction(0), Fraction(1)),
    (Fraction(1), Fraction(1), Fraction(0)),
    (Fraction(0), Fraction(1), Fraction(1)),
)
FC = CostedDesign(
    action_ids=("a0", "a1", "a2"),
    costs=(Fraction(1), Fraction(1), Fraction(1)),
    pair_ids=("p0", "p1", "p2"),
    thresholds=(Fraction(1), Fraction(1), Fraction(1)),
    info_lower=FC_A,
    info_upper=FC_A,
)


def test_fractional_cover_lp_dual_and_gap():
    res = lp_relax_exact(FC.info_upper, FC.costs, FC.thresholds)
    assert res.status == "OPTIMAL"
    assert res.objective == Fraction(3, 2)
    assert res.dual is not None
    # dual feasible: info^T y <= c, y >= 0
    assert check_dual_feasible(FC, FC.info_upper, res.dual)
    # strong duality: tau^T y == objective
    assert check_dual_bound(FC, res.dual) == res.objective
    # integer optimum is 2, and it is feasible w.r.t. true info
    cost, n = achievable_integer_design(FC)
    assert cost == Fraction(2)
    assert check_integer_design_feasible(FC, FC.info_lower, n)
    ub, gap = integrality_gap(FC)
    assert ub == Fraction(2)
    assert gap == Fraction(1, 3)


def test_fractional_cover_no_go():
    # budget 7/5 < LP lower bound 3/2 -> design class infeasible
    status, lb = no_go_status(FC, Fraction(7, 5))
    assert status == "NO_GO"
    assert lb == Fraction(3, 2)
    # checker signs it independently
    assert check_no_go_sign(Fraction(7, 5), Fraction(3, 2)) == "NO_GO"
    # budget equal to the LP bound is TIGHT (not a strict no-go)
    assert check_no_go_sign(Fraction(3, 2), Fraction(3, 2)) == "TIGHT"


def test_fractional_cover_feasible_within_budget():
    status, _lb = no_go_status(FC, Fraction(2))
    assert status == "FEASIBLE"


# Single action with fractional requirement: min n s.t. n >= 3/2, cost 1.
# IP = 2, LP = 3/2, gap = 1/3.
FRAC_REQ = CostedDesign(
    action_ids=("a0",),
    costs=(Fraction(1),),
    pair_ids=("p0",),
    thresholds=(Fraction(3, 2),),
    info_lower=((Fraction(1),),),
    info_upper=((Fraction(1),),),
)


def test_fractional_requirement_gap():
    res = lp_relax_exact(FRAC_REQ.info_upper, FRAC_REQ.costs, FRAC_REQ.thresholds)
    assert res.objective == Fraction(3, 2)
    cost, n = achievable_integer_design(FRAC_REQ)
    assert cost == Fraction(2)
    assert tuple(n) == (2,)
    ub, gap = integrality_gap(FRAC_REQ)
    assert gap == Fraction(1, 3)


# ---------------------------------------------------------------------------
# Certified-interval path (rational outer bounds on the info)
# ---------------------------------------------------------------------------

def test_certified_interval_path():
    # info truly in [1/2, 3/4]; lower bound used for achievability, upper for no-go.
    intvl = CostedDesign(
        action_ids=("a0",),
        costs=(Fraction(1),),
        pair_ids=("p0",),
        thresholds=(Fraction(1),),
        info_lower=((Fraction(1, 2),),),
        info_upper=((Fraction(3, 4),),),
    )
    lb = no_go_lower_bound(intvl)
    # LP with upper info 3/4: min n s.t. n*(3/4) >= 1 -> n >= 4/3
    assert lb == Fraction(4, 3)
    # achievable with lower info 1/2: ceil(1/(1/2)) = 2
    cost, n = achievable_integer_design(intvl)
    assert cost == Fraction(2)
    assert tuple(n) == (2,)
    ub, gap = integrality_gap(intvl)
    assert gap == Fraction(1, 2)


def test_integration_with_hellinger_interval():
    """Feed the T2c Hellinger information interval (Decimal) into costed via
    exact Decimal->Fraction conversion (outward), and check the no-go lower
    bound is a valid lower bound on the true integer optimum."""
    from d2t_rna.t2.info import Interval

    P0 = (Fraction(1, 4), Fraction(3, 4))
    P1 = (Fraction(1), Fraction(0))
    iv = hellinger_info_interval(P0, P1)  # I ~ ln 2, interval [lo, hi]
    assert isinstance(iv, Interval)
    # Decimal -> Fraction is exact, so these are certified rational outer bounds.
    lo_frac = Fraction(iv.lo)
    hi_frac = Fraction(iv.hi)
    assert lo_frac <= hi_frac
    cd = CostedDesign(
        action_ids=("a0",),
        costs=(Fraction(1),),
        pair_ids=("p0",),
        thresholds=(Fraction(1),),
        info_lower=((lo_frac,),),
        info_upper=((hi_frac,),),
    )
    lb = no_go_lower_bound(cd)
    cost, n = achievable_integer_design(cd)
    # true integer optimum is ceil(1/ln2) = 2
    assert cost == Fraction(2)
    assert tuple(n) == (2,)
    # certified lower bound must not overshoot the true optimum
    assert lb <= Fraction(2)
    assert lb > Fraction(0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_infeasible_pair_returns_none():
    # a pair with positive threshold but no action provides info -> infeasible
    bad = CostedDesign(
        action_ids=("a0", "a1"),
        costs=(Fraction(1), Fraction(1)),
        pair_ids=("p0", "p1"),
        thresholds=(Fraction(1), Fraction(1)),
        info_lower=((Fraction(1), Fraction(0)), (Fraction(1), Fraction(0))),
        info_upper=((Fraction(1), Fraction(0)), (Fraction(1), Fraction(0))),
    )
    cost, n = achievable_integer_design(bad)
    assert cost is None and n is None
    status, lb = no_go_status(bad, Fraction(100))
    assert status == "INFEASIBLE_OR_UNBOUNDED"


def test_zero_threshold_ignored():
    cd = CostedDesign(
        action_ids=("a0",),
        costs=(Fraction(1),),
        pair_ids=("p0", "p1"),
        thresholds=(Fraction(1), Fraction(0)),
        info_lower=((Fraction(1), Fraction(0)),),
        info_upper=((Fraction(1), Fraction(0)),),
    )
    cost, n = achievable_integer_design(cd)
    assert cost == Fraction(1)
    assert tuple(n) == (1,)


def test_checker_receipt_consistency():
    res = lp_relax_exact(FC.info_upper, FC.costs, FC.thresholds)
    y = res.dual
    dual_feas = check_dual_feasible(FC, FC.info_upper, y)
    dual_bound = check_dual_bound(FC, y)
    cost, n = achievable_integer_design(FC)
    int_feas = check_integer_design_feasible(FC, FC.info_lower, n)
    gap = check_integrality_gap(cost, res.objective)
    assert dual_feas
    assert dual_bound == Fraction(3, 2)
    assert int_feas
    assert gap == Fraction(1, 3)


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        CostedDesign(
            action_ids=("a0",),
            costs=(Fraction(1),),
            pair_ids=("p0",),
            thresholds=(Fraction(1),),
            info_lower=((Fraction(1, 2),),),
            info_upper=((Fraction(-1, 2),),),  # negative entry rejected
        )
    with pytest.raises(ValueError):
        CostedDesign(
            action_ids=("a0",),
            costs=(Fraction(0),),  # zero cost not supported
            pair_ids=("p0",),
            thresholds=(Fraction(1),),
            info_lower=((Fraction(1),),),
            info_upper=((Fraction(1),),),
        )