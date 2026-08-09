"""K7/K8 audit: T2c constructive-feasibility status vs information bounds.

The v7 audit requires that a T2c information bound is a *necessary* condition
only, and must never be conflated with constructive feasibility.  This audit
file verifies :func:`constructive_feasibility_status` covers every branch and
that ``CONSTRUCTIVELY_FEASIBLE`` is reserved for a complete, certified,
budget-verified design; it also checks ``no_go_status`` backward compatibility.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.bounds import (  # noqa: E402
    K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY,
    T2cConstructiveStatus,
    T2cNoGoStatus,
    constructive_feasibility_status,
    no_go_status,
)
from d2t_rna.t2.info import Interval  # noqa: E402


def _F(n, d=1):
    return Fraction(n, d)


def _base(**kw):
    kwargs = {
        "product_laws_registered": True,
        "allocation_registered": True,
        "decision_rule_registered": True,
        "budget_cost_verified": True,
        "alpha": _F(1, 10),
        "beta": _F(1, 10),
        "alpha_max": _F(1, 2),
        "beta_max": _F(1, 2),
    }
    kwargs.update(kw)
    return constructive_feasibility_status(**kwargs)


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        # (a) information bound present but no decision rule -> BOUND_ONLY
        ({"decision_rule_registered": False}, T2cConstructiveStatus.BOUND_ONLY),
        # (b) candidate rule but alpha exceeds -> BOUND_NOT_DECISIVE
        ({"alpha": _F(6, 10)}, T2cConstructiveStatus.BOUND_NOT_DECISIVE),
        # (c) candidate rule but beta exceeds -> BOUND_NOT_DECISIVE
        ({"beta": _F(6, 10)}, T2cConstructiveStatus.BOUND_NOT_DECISIVE),
        # (d) candidate rule but budget/cost not verified -> NO_GO
        ({"budget_cost_verified": False}, T2cConstructiveStatus.NO_GO),
        # (e) full rule with certified risk + verified budget -> CONSTRUCTIVELY_FEASIBLE
        ({}, T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE),
    ],
)
def test_constructive_feasibility_all_branches(kwargs, expected):
    cf = _base(**kwargs)
    assert cf.status == expected


def test_marker_constant_attached_everywhere():
    for kwargs in [
        {"decision_rule_registered": False},
        {"alpha": _F(6, 10)},
        {"beta": _F(6, 10)},
        {"budget_cost_verified": False},
        {},
    ]:
        cf = _base(**kwargs)
        assert cf.marker == K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY


def test_only_complete_design_is_constructively_feasible():
    # Any missing piece must NOT be labeled CONSTRUCTIVELY_FEASIBLE.
    non_feasible_cases = [
        {"product_laws_registered": False},
        {"allocation_registered": False},
        {"decision_rule_registered": False},
        {"alpha": None, "beta": None},
        {"alpha": _F(6, 10)},
        {"beta": _F(6, 10)},
        {"budget_cost_verified": False},
    ]
    for kwargs in non_feasible_cases:
        cf = _base(**kwargs)
        assert cf.status != T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE


def test_not_established_without_product_laws_or_allocation():
    cf = _base(product_laws_registered=False)
    assert cf.status == T2cConstructiveStatus.NOT_ESTABLISHED
    cf2 = _base(allocation_registered=False)
    assert cf2.status == T2cConstructiveStatus.NOT_ESTABLISHED


def test_bound_only_never_constructively_feasible():
    """Crossing an information threshold / having a bound but no rule is NEVER
    constructive feasibility."""
    cf = _base(decision_rule_registered=False)
    assert cf.status == T2cConstructiveStatus.BOUND_ONLY
    assert cf.status != T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE


def test_information_threshold_crossing_never_constructively_feasible():
    """``no_go_status`` feasibility (an explicit-rule / threshold decision) is a
    distinct concept and never equals CONSTRUCTIVELY_FEASIBLE: it returns only
    NO_GO / FEASIBLE / AMBIGUOUS."""
    statuses = set()
    # kappa=0.8, I=1.2 -> FEASIBLE (explicit rule reaches the target)
    status, _ = no_go_status(Interval(Decimal("1.2"), Decimal("1.2")), _F(8, 10))
    statuses.add(status)
    assert status == T2cNoGoStatus.FEASIBLE
    # the threshold-crossing status must not collide with constructive feasibility
    assert status != T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE


def test_no_go_status_backward_compat():
    # NO_GO: kappa=0.99 needs I>=~1.61 > 0.693
    status, _ = no_go_status(Interval(Decimal("0.693"), Decimal("0.693")), _F(99, 100))
    assert status == T2cNoGoStatus.NO_GO
    # FEASIBLE: I=1.2 reaches kappa=0.8 by an explicit rule
    status, _ = no_go_status(Interval(Decimal("1.2"), Decimal("1.2")), _F(8, 10))
    assert status == T2cNoGoStatus.FEASIBLE
    # AMBIGUOUS: I=0.5 crosses the necessary threshold but no explicit rule
    status, _ = no_go_status(Interval(Decimal("0.5"), Decimal("0.5")), _F(8, 10))
    assert status == T2cNoGoStatus.AMBIGUOUS


def test_status_classes_are_distinct():
    assert T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE != T2cNoGoStatus.FEASIBLE
