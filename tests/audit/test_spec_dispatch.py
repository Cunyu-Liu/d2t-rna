"""K1 audit: TheoremSpec dispatch (DISCRETE_CATALOG vs CONVEX_HULL, measures).

The v7 audit found the project mixed the discrete-catalog and convex-hull
uncertainty problems and mislabelled the action-level L1 separation as a
product-law TV.  ``TheoremSpec`` is the single immutable, hash-bound object that
declares the two formerly-ambiguous axes.  This audit file verifies:

  * both uncertainty kinds and all three measures dispatch (construct) without
    silently falling back;
  * ``spec.sha256()`` is deterministic and distinguishes every (kind, measure)
    combination;
  * unknown / unsupported values raise ``ValueError`` (no silent fallback).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.spec import (  # noqa: E402
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)

_KINDS = [UNCERTAINTY_DISCRETE, UNCERTAINTY_CONVEX]
_MEASURES = [MEASURE_ACTION_L1, MEASURE_ACTION_TV, MEASURE_PRODUCT_TV]


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("measure", _MEASURES)
def test_all_kind_measure_combinations_dispatch(kind, measure):
    """Every declared (kind, measure) combination constructs a valid spec with
    the exact declared values (no silent fallback to defaults)."""
    spec = TheoremSpec(kind, measure)
    assert spec.uncertainty_kind == kind
    assert spec.separation_measure == measure


def test_default_is_discrete_action_l1():
    spec = TheoremSpec()
    assert spec.uncertainty_kind == UNCERTAINTY_DISCRETE
    assert spec.separation_measure == MEASURE_ACTION_L1


def test_sha256_is_deterministic():
    a = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    b = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    assert a.sha256() == b.sha256()
    assert a.canonical() == b.canonical()
    assert len(a.sha256()) == 64


def test_sha256_distinguishes_uncertainty_kinds():
    a = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    b = TheoremSpec(UNCERTAINTY_CONVEX, MEASURE_ACTION_L1)
    assert a.sha256() != b.sha256()


def test_sha256_distinguishes_all_measures():
    h = {
        m: TheoremSpec(UNCERTAINTY_DISCRETE, m).sha256() for m in _MEASURES
    }
    assert len(set(h.values())) == 3


def test_sha256_distinguishes_all_six_combinations():
    combos = [(k, m) for k in _KINDS for m in _MEASURES]
    hashes = {TheoremSpec(k, m).sha256() for k, m in combos}
    assert len(hashes) == 6


def test_unknown_uncertainty_kind_raises():
    with pytest.raises(ValueError):
        TheoremSpec("BOGUS_KIND", MEASURE_ACTION_L1)


def test_unknown_measure_raises():
    with pytest.raises(ValueError):
        TheoremSpec(UNCERTAINTY_DISCRETE, "BOGUS_MEASURE")


def test_unknown_values_in_both_axes_raise():
    with pytest.raises(ValueError):
        TheoremSpec("BOGUS_KIND", "BOGUS_MEASURE")


def test_empty_string_not_silently_accepted():
    with pytest.raises(ValueError):
        TheoremSpec("", MEASURE_ACTION_L1)
    with pytest.raises(ValueError):
        TheoremSpec(UNCERTAINTY_DISCRETE, "")


def test_tv_from_l1_half_relationship():
    # The raw separation the engine computes is action-L1; the TV expression of
    # a zero-sum difference is exactly L1 / 2 and must lie in [0, 1].
    from fractions import Fraction

    assert tv_from_l1(0) == 0
    assert tv_from_l1(1) == Fraction(1, 2)
    assert tv_from_l1(2) == 1  # max L1 -> TV 1
    with pytest.raises(ValueError):
        tv_from_l1(-1)
