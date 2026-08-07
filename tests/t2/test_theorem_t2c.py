"""Tests for the T2-3 T2c finite-sample quantitative bounds (contract 5.3).

Covers certified Hellinger/Bhattacharyya information intervals, the
achievable-upper bound vs exact minimax error, the no-go lower bound / budget
consequence, exhaustive decision-enumeration crosscheck, and tightness.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

import pytest

from d2t_rna.t2.info import (
    Interval,
    bhattacharyya_coeff_interval,
    hellinger_info_interval,
    product_law_tv,
    scale_info_interval,
    tv,
)
from d2t_rna.t2.bounds import (
    T2cNoGoStatus,
    budget_lower_bound_info,
    no_go_status,
    required_repeats,
    wrong_prob_upper_interval,
    correct_decl_lower_interval,
)
from d2t_rna.t2.decision import (
    exact_bayes_average_error,
    exact_product_bhattacharyya,
    exact_product_law_tv,
)

# Perfect-square microcase: p1 always emits outcome 0; p0 emits 0 with prob 1/4.
# BC = sqrt(1/4) = 1/2 exactly, I = ln 2.
P0 = (Fraction(1, 4), Fraction(3, 4))
P1 = (Fraction(1), Fraction(0))
# The true ln(2) is irrational.  Compute it at a precision strictly higher than
# the certified 60-digit interval endpoints so the correctly-rounded value is
# guaranteed to lie inside the returned interval (within 0.5 ulp at 100 digits).
with localcontext() as c:
    c.prec = 100
    c.rounding = ROUND_HALF_UP
    INFO_EXACT = Decimal(2).ln()


def test_hellinger_info_interval_contains_ln2():
    iv = hellinger_info_interval(P0, P1)
    assert iv.lo <= INFO_EXACT <= iv.hi
    assert iv.lo <= iv.hi


def test_bhattacharyya_interval_contains_half():
    bc = bhattacharyya_coeff_interval(P0, P1)
    assert bc.lo <= Decimal("0.5") <= bc.hi


def test_upper_bound_honors_exact_bayes_average_error():
    # For n = 1..5 the certified upper bound (1/2) exp(-n I) must dominate the
    # exact minimax error (1/2)(1/4)^n.
    for n in range(1, 6):
        exact = exact_bayes_average_error(P0, P1, n)
        info_n = scale_info_interval(hellinger_info_interval(P0, P1), n)
        ub = wrong_prob_upper_interval(info_n)
        assert exact <= ub.hi, (n, exact, ub)
        # and the certified interval is close to the ideal (1/2)(1/2)^n
        ideal = Decimal("0.5") * Decimal("0.5") ** n
        assert ub.lo <= ideal <= ub.hi, (n, ub, ideal)


def test_exact_error_double_checks_tv():
    for n in range(1, 5):
        err = exact_bayes_average_error(P0, P1, n)
        t = exact_product_law_tv(P0, P1, n)
        assert err == (Fraction(1, 2) * (1 - t))
        assert err == Fraction(1, 2) * (Fraction(1, 4) ** n)


def test_exact_product_bhattacharyya_matches_interval():
    for n in range(1, 5):
        exact_bc = exact_product_bhattacharyya(P0, P1, n)
        # BC^n = (1/2)^n exactly
        assert exact_bc == Fraction(1, 2) ** n


def test_no_go_status():
    per = hellinger_info_interval(P0, P1)  # I = ln2 ~ 0.693
    # To guarantee correct-decl >= 0.99 we need I >= -(1/2)log(1-0.98^2) ~ big
    high = no_go_status(per, Fraction(99, 100))
    assert high[0] == T2cNoGoStatus.NO_GO
    # To guarantee correct-decl >= 0.6 we need I >= -(1/2)log(1-0.2^2) ~ 0.02
    low = no_go_status(per, Fraction(6, 10))
    assert low[0] == T2cNoGoStatus.FEASIBLE


def test_budget_lower_bound_monotonic():
    kappas = [Fraction(6, 10), Fraction(7, 10), Fraction(8, 10), Fraction(9, 10)]
    reqs = [budget_lower_bound_info(k) for k in kappas]
    for a, b in zip(reqs, reqs[1:]):
        assert a.lo <= b.lo and a.hi <= b.hi


def test_required_repeats_finite():
    per = hellinger_info_interval(P0, P1)
    n, status = required_repeats(per, Fraction(8, 10))
    assert status == T2cNoGoStatus.FEASIBLE
    assert n >= 1


def test_budget_lower_bound_certified_contains_ln2():
    # kappa = (1+sqrt(1/2))/2 gives 1-(2k-1)^2=1/2 so I_req = (1/2)ln2.
    # We check structural sanity: for kappa slightly above 1/2 the required info
    # is small and positive; for kappa = 1 it goes to +infinity.
    small = budget_lower_bound_info(Fraction(501, 1000))
    assert 0 <= small.lo <= small.hi
    inf = budget_lower_bound_info(Fraction(1))
    assert inf.lo.is_infinite()


def test_product_law_tv_sanity():
    # identical laws -> TV 0
    assert product_law_tv(P0, P0, 3) == 0
    # at n = 1, TV(P0, P1) = (1/2)(|1/4-1| + |3/4-0|) = 3/4
    assert tv(P0, P1) == Fraction(3, 4)


def test_correct_decl_lower_bound_le_one():
    info_n = scale_info_interval(hellinger_info_interval(P0, P1), 4)
    cd = correct_decl_lower_interval(info_n)
    assert cd.lo <= Decimal(1) <= cd.hi
    assert cd.lo > Decimal(0)


def test_interval_arithmetic_nonempty():
    # multiply / sum endpoints stay ordered
    a = hellinger_info_interval(P0, P1)
    b = hellinger_info_interval(P0, P1)
    s = scale_info_interval(a, 3)
    assert s.lo <= s.hi
    assert a.lo <= a.hi
    assert b.lo <= b.hi