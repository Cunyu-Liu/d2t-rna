"""Tests for the T2-2 T2b exact collision-or-separation theorem.

Covers contract section 10.1: rational LP primal/dual certificates, the
IFF / NECESSARY_ONLY / SUFFICIENT_ONLY direction determination, positive /
counterexample / near-collision / boundary fixtures, enumeration-vs-LP
cross-check, and strong duality.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.t2.fixtures import (
    cancellation_counterexample,
    exact_collision,
    near_collision,
    no_cycle,
    strict_separation,
    symmetric_states,
    two_by_two_alternating,
    zero_margin,
)
from d2t_rna.t2.theorem import T2bCertificate, collision_or_separation


def test_two_by_two_row_obs_is_collision():
    model = two_by_two_alternating()
    cert = collision_or_separation(model, ["row_obs"])
    assert cert.status == "IFF"
    assert cert.gamma == 0
    assert cert.collision_witness is not None
    assert cert.enumeration_matches_lp is True
    assert cert.lp_strong_duality is True


def test_two_by_two_full_obs_is_separation():
    model = two_by_two_alternating()
    cert = collision_or_separation(model, ["full_obs"])
    assert cert.status == "IFF"
    assert cert.gamma == 1
    assert cert.separation_witness is not None
    assert cert.enumeration_matches_lp is True
    assert cert.lp_strong_duality is True


def test_no_cycle_empty_difference():
    model = no_cycle()
    cert = collision_or_separation(model, ["a"])
    # D empty -> vacuous separation, no collision.
    assert cert.enumeration_gamma is None
    assert cert.collision_witness is None


def test_zero_margin_separates():
    model = zero_margin()
    cert = collision_or_separation(model, ["a"])
    assert cert.status == "IFF"
    assert cert.gamma is not None and cert.gamma > 0
    assert cert.separation_witness is not None


def test_symmetric_states_empty_difference():
    model = symmetric_states()
    cert = collision_or_separation(model, ["a"])
    assert cert.enumeration_gamma is None
    assert cert.collision_witness is None


def test_cancellation_counterexample_is_collision():
    model = cancellation_counterexample()
    cert = collision_or_separation(model, ["b1"])
    assert cert.status == "IFF"
    assert cert.gamma == 0
    assert cert.collision_witness is not None
    assert cert.enumeration_matches_lp is True


def test_exact_collision_certificate():
    model = exact_collision()
    cert = collision_or_separation(model, ["row_obs"])
    assert cert.status == "IFF"
    assert cert.gamma == 0
    assert cert.collision_witness is not None


def test_near_collision_positive_small_separation():
    model = near_collision()
    cert = collision_or_separation(model, ["diag"])
    assert cert.status == "IFF"
    assert cert.gamma == Fraction(1, 4)
    assert 0 < cert.gamma < 1
    assert cert.separation_witness is not None
    assert cert.enumeration_matches_lp is True


def test_strict_separation():
    model = strict_separation()
    cert = collision_or_separation(model, ["full_obs"])
    assert cert.status == "IFF"
    assert cert.gamma == 1
    assert cert.separation_witness is not None


def test_lp_strong_duality_holds_for_all_fixtures():
    for model, panel in [
        (two_by_two_alternating(), "row_obs"),
        (two_by_two_alternating(), "full_obs"),
        (zero_margin(), "a"),
        (cancellation_counterexample(), "b1"),
        (near_collision(), "diag"),
        (strict_separation(), "full_obs"),
    ]:
        cert = collision_or_separation(model, [panel])
        assert cert.status == "IFF"
        assert cert.lp_strong_duality is True, (model.name, panel)
        assert cert.enumeration_matches_lp is True, (model.name, panel)


def test_certificate_is_frozen_dataclass():
    cert = collision_or_separation(two_by_two_alternating(), ["row_obs"])
    assert cert.theorem == "T2b"
    assert isinstance(cert, T2bCertificate)
    # panel is frozen
    with pytest.raises(Exception):
        cert.panel = ("x",)