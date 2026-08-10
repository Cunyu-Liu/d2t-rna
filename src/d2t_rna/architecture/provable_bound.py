"""Scheme C (plan §P3, ``C_EXACT_SCALING_BB_CP_CG``): provable-bound exact scaling.

The Phase-1 scalability report locates two coupled bottlenecks:

* the cap-free exhaustive oracle is exact only within an allocation space
  ``<= 81``; beyond that scale is ``UNKNOWN_NOT_ASSERTED``;
* ``t2_integer_lp`` reaches only 80% coverage (16 fail-closed withheld
  certificates) because the plain integer LP exceeds budget on those cells.

Scheme C minimal implementation (from ``phase3_protocol``):
    "a provable-bound approximation for one catalog class that certifies the
     cells currently withheld (allocation space > 81)"
Success threshold:
    "provable bound reproduces the exact oracle on the 81-boundary and
     certifies withheld cells without exceeding budget; gap reported"

This module implements that provable bound.  For a fixed multi-action
allocation ``n`` the equal-prior minimax error of the product test is
``P_e(n) = (1/2) * sum_joint min(P0_joint, P1_joint)``.  With per-action
Bhattacharyya coefficients ``BC_u = sum_y sqrt(q0_u[y] q1_u[y])`` the product
Bhattacharyya coefficient is ``BC(n) = prod_u BC_u^{n_u}``, and the classical
two-sided bound holds:

    (1/2) * (1 - sqrt(1 - BC(n)^2))  <=  P_e(n)  <=  (1/2) * BC(n)

The optimal error over within-budget allocations is ``E* = min_n P_e(n)``.
Because both the lower and upper expressions are monotone in ``BC(n)``, let

    m  =  min over within-budget allocations of  prod_u BC_u^{n_u}.

Then

    L* = (1/2) * (1 - sqrt(1 - m^2))   <=  E*  <=  m/2 = U*.

``m`` is a separable, monotone knapsack-style minimum over the budget, which
this module solves with a single forward DP over cost (polynomial in budget,
**not** exponential in allocation space).  This is what extends the exact
boundary beyond 81: the certificate is produced without exhaustive allocation
enumeration.  All arithmetic is done with ``Fraction`` and certified rational
sqrt intervals, so the reported ``[L*, U*]`` is a rigorous (fail-closed) bound
on the true optimal minimax error of the cell.  No unproven heuristic value is
reported as a fact.
"""

from __future__ import annotations

from fractions import Fraction
from math import isqrt
from typing import Sequence

Vec = tuple[Fraction, ...]

# ---------------------------------------------------------------------------
# certified rational sqrt interval
# ---------------------------------------------------------------------------

# Precision scale for the certified sqrt interval: the interval width is
# ~1/(SCALE * q), so SCALE=2**24 gives a ~1e-7 relative certified width.  This
# keeps the Scheme C bound meaningful (non-trivial upper bound) while remaining
# rigorously correct (lo <= sqrt(x) <= hi always).
_SQRT_SCALE = 1 << 24


def _sqrt_interval(x: Fraction) -> tuple[Fraction, Fraction]:
    """Certified rational interval [lo, hi] containing sqrt(x) for x >= 0.

    ``sqrt(p/q) = sqrt(p*q) / q``.  We bound ``sqrt(p*q)`` with an integer
    isqrt at scale ``_SQRT_SCALE`` so the certified width is ``~1/(SCALE*q)``,
    tight enough for a meaningful provable bound while rigorously correct.
    """
    if x < 0:
        raise ValueError("sqrt of a negative rational is not real")
    if x == 0:
        return Fraction(0), Fraction(0)
    p, q = x.numerator, x.denominator
    # sqrt(p/q) = sqrt(p*q)/q; bound sqrt(p*q) at high scale:
    #   s/SCALE <= sqrt(p*q) <= (s+1)/SCALE,  s = isqrt(p*q * SCALE^2)
    s = isqrt(p * q * _SQRT_SCALE * _SQRT_SCALE)
    lo = Fraction(s, q * _SQRT_SCALE)
    hi = Fraction(s + 1, q * _SQRT_SCALE)
    return lo, hi


def _bhattacharyya_interval(q0: Vec, q1: Vec) -> tuple[Fraction, Fraction]:
    """Certified [lo, hi] for BC_u = sum_y sqrt(q0[y] q1[y])."""
    lo = Fraction(0)
    hi = Fraction(0)
    for a, b in zip(q0, q1):
        t = a * b
        if t == 0:
            continue
        alo, ahi = _sqrt_interval(t)
        lo += alo
        hi += ahi
    return lo, hi


# ---------------------------------------------------------------------------
# monotone knapsack DP for m = min over within-budget allocations of prod BC^n
# ---------------------------------------------------------------------------


def _min_bc_product(
    bc_vals: Sequence[Fraction], costs: Sequence[Fraction], budget: Fraction
) -> tuple[Fraction, tuple[int, ...], Fraction]:
    """Minimize ``prod_u bc_u^{n_u}`` s.t. ``sum_u cost_u n_u <= budget``.

    Returns ``(m, argmin_allocation, argmin_cost)``.  bc_vals are per-action
    Bhattacharyya coefficients (each in [0, 1]).  ``budget`` must be a positive
    integer multiple of unit cost (all cells in this project use integer
    budgets and integer costs); we normalize to integer units.
    """
    U = len(bc_vals)
    if U == 0:
        return Fraction(1), (), Fraction(0)
    int_costs = [int(c) for c in costs]
    int_budget = int(budget)
    if any(c <= 0 for c in int_costs):
        raise ValueError("provable-bound DP requires strictly positive integer costs")
    # best[c] = (min product, allocation) for spending exactly c units.
    best: dict[int, tuple[Fraction, tuple[int, ...]]] = {
        0: (Fraction(1), tuple([0] * U))
    }
    for c in range(int_budget + 1):
        if c not in best:
            continue
        prod, alloc = best[c]
        for u in range(U):
            nc = c + int_costs[u]
            if nc > int_budget:
                continue
            nprod = prod * bc_vals[u]
            nalloc = list(alloc)
            nalloc[u] += 1
            nalloc = tuple(nalloc)
            cur = best.get(nc)
            if cur is None or nprod < cur[0]:
                best[nc] = (nprod, nalloc)
    m = Fraction(1)
    arg_alloc = tuple([0] * U)
    arg_cost = Fraction(0)
    for c, (prod, alloc) in best.items():
        if prod < m:
            m = prod
            arg_alloc = alloc
            arg_cost = Fraction(c)
    return m, arg_alloc, arg_cost


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def provable_minimax_interval(
    p0_laws: Sequence[Vec],
    p1_laws: Sequence[Vec],
    costs: Sequence[Fraction],
    budget: Fraction,
) -> dict:
    """Certified interval [lower_bound, upper_bound] on the cell's optimal
    minimax error, plus the certified allocation, cost, and reported gap.

    Both bounds derive from ``m = min over within-budget allocations of
    prod_u BC_u^{n_u}`` (a polynomial DP).  Because each ``BC_u`` may be
    irrational, we run the DP on the certified per-action intervals:

    * ``m_hi`` (using the upper interval endpoints) drives the upper bound
      ``U* = m_hi / 2``;
    * ``m_lo`` (lower endpoints) drives the lower bound
      ``L* = (1/2)(1 - sqrt_hi(1 - m_lo^2))``, where ``sqrt_hi`` is the
      certified upper sqrt (making the lower bound conservative).

    The result is fail-closed: ``L* <= true_optimal_error <= U*`` always.
    """
    if len(p0_laws) != len(p1_laws) != len(costs):
        raise ValueError("p0_laws, p1_laws and costs must have equal length")
    if budget <= 0:
        raise ValueError("budget must be strictly positive")

    bc_lo: list[Fraction] = []
    bc_hi: list[Fraction] = []
    for q0, q1 in zip(p0_laws, p1_laws):
        lo, hi = _bhattacharyya_interval(q0, q1)
        bc_lo.append(lo)
        bc_hi.append(hi)

    m_lo, alloc_lo, cost_lo = _min_bc_product(bc_lo, costs, budget)
    m_hi, alloc_hi, cost_hi = _min_bc_product(bc_hi, costs, budget)

    # upper bound: U* = m_hi / 2
    upper = m_hi / 2

    # lower bound: L* = (1/2)(1 - sqrt_hi(1 - m_lo^2))
    x = Fraction(1) - m_lo * m_lo
    if x < 0:
        # numerically m_lo must be in [0,1]; clamp to a safe certified x
        x = Fraction(0)
    _slo, shi = _sqrt_interval(x)
    lower = Fraction(1, 2) * (Fraction(1) - shi)

    # both allocations spend within budget by construction of the DP
    if cost_lo > budget or cost_hi > budget:
        raise AssertionError("DP returned an allocation that exceeds budget")

    return {
        "lower_bound": str(lower),
        "upper_bound": str(upper),
        "gap": str(upper - lower),
        "m_lo": str(m_lo),
        "m_hi": str(m_hi),
        "allocation": [int(x) for x in alloc_hi],
        "allocation_cost": str(cost_hi),
        "within_budget": cost_hi <= budget,
        "bound": "BHATTACHARYYA_PRODUCT_TWO_SIDED",
        "scale": "DP_OVER_BUDGET_NOT_ALLOCATION_ENUMERATION",
    }
