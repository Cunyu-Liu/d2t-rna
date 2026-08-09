"""K5 audit: Phase4->5 metric identity (no forbidden recomputation).

The v7 audit found the Bayes average error mislabelled as minimax across
pipeline stages.  The Phase4/5 evaluation oracle (:class:`MultiActionOracle` and
the theory-side :mod:`d2t_rna.t2.decision`) must report the *same estimand* in
the *same cell*, byte-identical across stages, and must never derive the primary
metric from the forbidden recomputation

    wrong = 1 - correct - abstain
    minimax_error = (wrong + abstain) / 2

This audit file verifies:

  * with no abstention, ``minimax_error == wrong_decl == bayes_average_error``
    (the Bayes-average cell is identical across evaluation and decision stages);
  * ``product_tv == 1 - 2 * minimax_error`` (identity of the same cell);
  * the forbidden recomputation is NOT used: with abstention,
    ``minimax_error != (wrong_decl + abstain) / 2`` and minimax_error is
    invariant to abstention (it is the Bayes average, computed independently).
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from d2t_rna.evaluation.matrix import MultiActionOracle  # noqa: E402
from d2t_rna.t2.decision import exact_bayes_average_error  # noqa: E402


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _run(q0, q1, n, abstain_ratio):
    return MultiActionOracle(
        p0_laws=(q0,),
        p1_laws=(q1,),
        costs=(_F(1),),
        n=(n,),
        abstain_ratio=abstain_ratio,
    ).evaluate()


def test_no_abstention_bayes_average_equals_wrong_decl():
    """Phase4->5 identity: with no abstention the Bayes-average cell is
    byte-identical to the wrong-declaration cell and to the decision-stage
    ``exact_bayes_average_error``."""
    q0 = (_F(1, 4), _F(3, 4))
    q1 = (_F(1), _F(0))
    oracle = _run(q0, q1, 1, _F(1))  # abstain_ratio == 1 -> no abstention
    assert oracle.abstain == 0
    # same estimand, same cell, identical across evaluation and decision stages
    assert oracle.minimax_error == oracle.wrong_decl
    assert oracle.minimax_error == exact_bayes_average_error(q0, q1, 1)
    # the identity cell relationship
    assert oracle.product_tv == 1 - 2 * oracle.minimax_error
    # the partition identity
    assert oracle.correct_decl + oracle.wrong_decl + oracle.abstain == 1


def test_forbidden_recomputation_is_not_the_primary_metric():
    """With abstention, the production reports a minimax_error that is NOT
    ``(wrong_decl + abstain) / 2`` and is invariant to abstention -- proving the
    primary metric is computed independently as the Bayes average, not via the
    forbidden recomputation."""
    q0 = (_F(1, 3), _F(2, 3))
    q1 = (_F(1, 2), _F(1, 2))
    no_abs = _run(q0, q1, 1, _F(1))
    with_abs = _run(q0, q1, 1, _F(2))
    # The Bayes-average cell is invariant to abstention.
    assert no_abs.minimax_error == with_abs.minimax_error
    assert no_abs.minimax_error == exact_bayes_average_error(q0, q1, 1)
    # With abstention the forbidden recomputation gives a different number, so
    # the production value cannot have come from it.
    assert with_abs.abstain > 0
    forbidden = (with_abs.wrong_decl + with_abs.abstain) / 2
    assert with_abs.minimax_error != forbidden
    # And the direct identity (not the forbidden one) holds.
    assert with_abs.minimax_error == (1 - with_abs.product_tv) / 2


def test_wrong_equals_one_minus_correct_minus_abstain_is_not_primary():
    """The primary Bayes-average cell is byte-identical across the evaluation
    and decision stages, and obeys the direct identity ``minimax_error =
    (1 - product_tv)/2`` -- it is never masked or re-derived from the forbidden
    ``wrong = 1 - correct - abstain`` recomputation."""
    q0 = (_F(1, 3), _F(2, 3))
    q1 = (_F(1, 2), _F(1, 2))
    oracle = _run(q0, q1, 1, _F(2))
    # Byte-identical estimand across stages.
    assert oracle.minimax_error == exact_bayes_average_error(q0, q1, 1)
    # Direct identity of the same cell.
    assert oracle.minimax_error == (1 - oracle.product_tv) / 2
    # The Bayes-average cell is the honest primary metric and is not masked.
    assert oracle.minimax_error > 0
    assert oracle.minimax_error <= Fraction(1, 2)
