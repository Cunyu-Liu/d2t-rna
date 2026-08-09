"""K4 audit: Bayes / minimax / abstention metric identity.

The v7 audit found the equal-prior Bayes average error mislabelled as minimax.
This audit file verifies, by calling the production functions (never hardcoding
then pretending), that for the classic counterexample
``P0=(1,0)``, ``P1=(1/2,1/2)``, ``n=1``:

  * ``exact_bayes_average_error == 1/4``;
  * ``exact_randomized_minimax_error == 1/3`` (distinct, strictly larger);
  * the per-hypothesis conditional quantities ``alpha,beta,kappa_0,kappa_1,
    rho_0,rho_1`` from ``conditional_rule_errors`` satisfy the identity
    ``alpha + kappa_0 + rho_0 == 1`` and ``beta + kappa_1 + rho_1 == 1``;
  * abstention is handled (identical laws abstain entirely).
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from d2t_rna.t2.decision import (  # noqa: E402
    ConditionalDecision,
    conditional_rule_errors,
    exact_bayes_average_error,
    exact_randomized_minimax_error,
)

P0 = (Fraction(1), Fraction(0))
P1 = (Fraction(1, 2), Fraction(1, 2))


def test_audit_minimax_counterexample_by_calling_production():
    """Call the production functions; do not hardcode and pretend."""
    bayes = exact_bayes_average_error(P0, P1, 1)
    minimax = exact_randomized_minimax_error(P0, P1, 1)
    assert bayes == Fraction(1, 4)
    assert minimax == Fraction(1, 3)
    # The two are genuinely distinct quantities, never conflated.
    assert minimax > bayes


def test_bayes_average_error_from_tv():
    """Bayes average = (1/2)(1 - TV(P0^n, P1^n)) for n=1."""
    tv_p01 = Fraction(1, 2) * (abs(P0[0] - P1[0]) + abs(P0[1] - P1[1]))
    # TV(P0,P1) = (1/2)(|1-1/2| + |0-1/2|) = (1/2)(1/2+1/2) = 1/2
    assert tv_p01 == Fraction(1, 2)
    assert exact_bayes_average_error(P0, P1, 1) == Fraction(1, 2) * (1 - tv_p01)


def test_conditional_rule_errors_quantities():
    rule = conditional_rule_errors(P0, P1, 1, Fraction(1), Fraction(1))
    assert isinstance(rule, ConditionalDecision)
    # explicit ties-abstain likelihood-ratio rule at threshold 1
    assert rule.alpha == Fraction(0)
    assert rule.beta == Fraction(1, 2)
    assert rule.kappa_0 == Fraction(1)
    assert rule.kappa_1 == Fraction(1, 2)
    assert rule.rho_0 == Fraction(0)
    assert rule.rho_1 == Fraction(0)
    # per-hypothesis partition identities
    assert rule.sums_to_one()
    assert rule.alpha + rule.kappa_0 + rule.rho_0 == 1
    assert rule.beta + rule.kappa_1 + rule.rho_1 == 1


def test_abstention_handling_identical_laws():
    p = (Fraction(1, 2), Fraction(1, 2))
    rule = conditional_rule_errors(p, p, 1, Fraction(1), Fraction(1))
    assert rule.sums_to_one()
    # identical laws -> every outcome is ambiguous -> full abstention
    assert rule.rho_0 == Fraction(1)
    assert rule.rho_1 == Fraction(1)
    assert rule.kappa_0 == Fraction(0)
    assert rule.kappa_1 == Fraction(0)


def test_abstention_region_exposed_per_hypothesis():
    """With a wide abstention band (lower < upper), tied/ambiguous outcomes
    abstain and the abstention probabilities are exposed separately under each
    hypothesis."""
    q0 = (Fraction(1, 3), Fraction(2, 3))
    q1 = (Fraction(1, 2), Fraction(1, 2))
    # ratios are 3/2 and 3/4, both inside (1/2, 2) -> every outcome abstains
    rule = conditional_rule_errors(q0, q1, 1, Fraction(1, 2), Fraction(2))
    assert rule.sums_to_one()
    assert rule.rho_0 == Fraction(1)
    assert rule.rho_1 == Fraction(1)
    assert rule.alpha == Fraction(0)
    assert rule.beta == Fraction(0)
