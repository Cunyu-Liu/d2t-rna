"""P0-4: T2c/T2d decision and bound semantics.

Regression tests for the decision-semantics rebuild mandated by the v7 audit:

* ``exact_minimax_error`` was a misnomer: it computed the equal-prior Bayes
  average error.  The true randomized minimax error is a distinct quantity
  (:func:`exact_randomized_minimax_error`).  The audit counterexample
  ``P0=(1,0)``, ``P1=(1/2,1/2)``, ``n=1`` gives Bayes average ``1/4`` but
  minimax ``1/3``.
* Per-hypothesis conditional quantities (``alpha,beta,kappa_0,kappa_1,
  rho_0,rho_1``) are computed separately, not collapsed to a scalar.
* ``FEASIBLE`` is issued only by an explicit rule, never by crossing the
  necessary information threshold (:func:`no_go_status`).
* The false inequality in ``supplementary.tex:98`` is recorded as a
  counterexample and the corrected bound is asserted.
* T2d interval direction: no-go uses the certified *upper* information bound,
  constructive achievability uses the *lower* bound.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from d2t_rna.t2.info import Interval
from d2t_rna.t2.decision import (
    ConditionalDecision,
    exact_bayes_average_error,
    exact_randomized_minimax_error,
    conditional_rule_errors,
)
from d2t_rna.t2.bounds import T2cNoGoStatus, no_go_status
from d2t_rna.t2.costed import (
    CostedDesign,
    no_go_lower_bound,
    achievable_integer_design,
)
from d2t_rna.t2.costed import no_go_status as costed_no_go_status


# ---------------------------------------------------------------------------
# 1. Minimax vs Bayes-average semantics
# ---------------------------------------------------------------------------

def test_audit_minimax_counterexample():
    """P0=(1,0), P1=(1/2,1/2), n=1: Bayes average 1/4, minimax 1/3."""
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    bayes = exact_bayes_average_error(p0, p1, 1)
    minimax = exact_randomized_minimax_error(p0, p1, 1)
    assert bayes == Fraction(1, 4)
    assert minimax == Fraction(1, 3)
    assert minimax > bayes


@pytest.mark.parametrize(
    "p0,p1,n",
    [
        ((Fraction(1, 4), Fraction(3, 4)), (Fraction(1), Fraction(0)), 1),
        ((Fraction(1, 4), Fraction(3, 4)), (Fraction(1), Fraction(0)), 2),
        ((Fraction(1, 2), Fraction(1, 2)), (Fraction(1), Fraction(0)), 1),
        ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)), 1),
    ],
)
def test_minimax_ge_bayes_average(p0, p1, n):
    bayes = exact_bayes_average_error(p0, p1, n)
    minimax = exact_randomized_minimax_error(p0, p1, n)
    assert minimax >= bayes
    assert 0 <= minimax <= 1


def test_minimax_identical_laws_is_half():
    p = (Fraction(1, 2), Fraction(1, 2))
    mm = exact_randomized_minimax_error(p, p, 1)
    assert mm == Fraction(1, 2)


def test_minimax_disjoint_support_is_zero():
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(0), Fraction(1))
    mm = exact_randomized_minimax_error(p0, p1, 1)
    assert mm == Fraction(0)


def test_minimax_upper_bound_respected():
    """The certified T2c achievability bound (1/2)exp(-I) may be loose, but the
    true minimax error must never *exceed* the trivial guessing rate 1/2."""
    p0 = (Fraction(1, 4), Fraction(3, 4))
    p1 = (Fraction(1), Fraction(0))
    for n in range(1, 4):
        mm = exact_randomized_minimax_error(p0, p1, n)
        assert mm <= Fraction(1, 2)


# ---------------------------------------------------------------------------
# 2. Per-hypothesis conditional decision quantities
# ---------------------------------------------------------------------------

def test_conditional_rule_errors_sums_to_one():
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    rule = conditional_rule_errors(p0, p1, 1, Fraction(1), Fraction(1))
    assert isinstance(rule, ConditionalDecision)
    assert rule.sums_to_one()
    # explicit ties-abstain LR rule at threshold 1
    assert rule.alpha == Fraction(0)
    assert rule.beta == Fraction(1, 2)
    assert rule.kappa_0 == Fraction(1)
    assert rule.kappa_1 == Fraction(1, 2)
    assert rule.rho_0 == Fraction(0)
    assert rule.rho_1 == Fraction(0)


def test_conditional_rule_errors_separate_per_hypothesis():
    """alpha and kappa_0 (H0-side) and beta/kappa_1 (H1-side) are computed
    independently; they are not a single equal-prior average."""
    p0 = (Fraction(1, 4), Fraction(3, 4))
    p1 = (Fraction(1), Fraction(0))
    rule = conditional_rule_errors(p0, p1, 1, Fraction(1), Fraction(1))
    assert rule.sums_to_one()
    assert rule.kappa_0 != rule.kappa_1  # separately computed
    assert rule.alpha != rule.beta


def test_conditional_rule_abstention_region():
    """With a wide abstention band, the rule abstains on tied/ambiguous
    outcomes and the abstention probabilities are exposed per hypothesis."""
    p0 = (Fraction(1, 2), Fraction(1, 2))
    p1 = (Fraction(1, 2), Fraction(1, 2))  # identical -> always abstain
    rule = conditional_rule_errors(p0, p1, 1, Fraction(1), Fraction(1))
    assert rule.sums_to_one()
    assert rule.rho_0 == Fraction(1)
    assert rule.rho_1 == Fraction(1)
    assert rule.kappa_0 == Fraction(0) and rule.kappa_1 == Fraction(0)


# ---------------------------------------------------------------------------
# 3. no_go_status: FEASIBLE only by an explicit rule
# ---------------------------------------------------------------------------

def test_feasible_only_by_explicit_rule():
    """kappa=0.8: necessary threshold ~0.223, explicit-rule (sufficient)
    threshold ~0.916.  I=0.5 crosses the necessary threshold but the explicit
    rule only certifies correct-decl >= 1-(1/2)exp(-0.5) ~ 0.697 < kappa, so
    the status is AMBIGUOUS, *not* FEASIBLE."""
    kappa = Fraction(8, 10)
    info = Interval(Decimal("0.5"), Decimal("0.5"))
    status, req = no_go_status(info, kappa)
    assert info.hi >= req.lo  # necessary threshold not crossed => not NO_GO
    assert status == T2cNoGoStatus.AMBIGUOUS


def test_feasible_when_explicit_rule_reaches_kappa():
    """I=1.2 certifies correct-decl >= 1-(1/2)exp(-1.2) ~ 0.849 >= kappa=0.8,
    so the explicit rule reaches the target => FEASIBLE."""
    kappa = Fraction(8, 10)
    info = Interval(Decimal("1.2"), Decimal("1.2"))
    status, _req = no_go_status(info, kappa)
    assert status == T2cNoGoStatus.FEASIBLE


def test_no_go_uses_upper_info():
    """kappa=0.99 requires I >= ~1.614; total_info.hi=ln2~0.693 is below it,
    so no rule can reach the target => NO_GO (uses the upper info bound)."""
    kappa = Fraction(99, 100)
    info = Interval(Decimal("0.693"), Decimal("0.693"))
    status, _req = no_go_status(info, kappa)
    assert status == T2cNoGoStatus.NO_GO


# ---------------------------------------------------------------------------
# 4. False inequality in supplementary.tex:98 recorded
# ---------------------------------------------------------------------------

def test_false_inequality_recorded():
    rho = Fraction(1, 2)
    nn = 1
    lhs = (rho ** nn) / (1 + rho ** nn)
    half = Fraction(1, 2) * (rho ** nn)
    full = rho ** nn
    # supplementary.tex:98 asserted lhs <= half; this is FALSE at rho=1/2,n=1.
    assert not (lhs <= half)
    # The corrected bound the proof actually needs (and that is trivially true):
    assert lhs <= full


# ---------------------------------------------------------------------------
# 5. T2d interval direction: no-go uses upper info, achievability uses lower
# ---------------------------------------------------------------------------

def test_costed_interval_direction():
    """A 1-action, 1-pair instance with certified info bounds [1,2] and
    threshold 3, unit cost.

    * no-go lower bound uses the *upper* info bound (2): LP opt = 3/2.
    * achievable integer design uses the *lower* info bound (1): n=3, cost 3.
    """
    cd = CostedDesign(
        action_ids=("a",),
        costs=(Fraction(1),),
        pair_ids=("w",),
        thresholds=(Fraction(3),),
        info_lower=((Fraction(1),),),
        info_upper=((Fraction(2),),),
    )
    lb = no_go_lower_bound(cd)
    assert lb is not None and lb == Fraction(3, 2)
    cost, n = achievable_integer_design(cd)
    assert cost == Fraction(3) and n == (3,)


def test_costed_no_go_respects_upper_bound():
    """If budget < upper-bound-derived lower bound, the design is NO_GO even
    though the lower info bound would allow a cheaper 'feasible-looking' plan."""
    cd = CostedDesign(
        action_ids=("a",),
        costs=(Fraction(1),),
        pair_ids=("w",),
        thresholds=(Fraction(3),),
        info_lower=((Fraction(1),),),
        info_upper=((Fraction(2),),),
    )
    status, lb = costed_no_go_status(cd, Fraction(7, 5))
    assert lb == Fraction(3, 2)
    assert status == "NO_GO"