"""Tests for the T2-1 witness / collision engine (contract sections 10.1)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.t2.fixtures import (
    cancellation_counterexample,
    exact_collision,
    near_collision,
    no_cycle,
    repeated_action,
    strict_separation,
    symmetric_states,
    three_way_fixed_marginal,
    two_by_two_alternating,
    zero_margin,
)
from d2t_rna.t2.model import T2FiniteModel, canonicalize_model
from d2t_rna.t2.verify import verify_collision, verify_separation
from d2t_rna.t2.witness import (
    collision_witness,
    fiber_basis,
    iter_differences,
    panel_separation,
    separate_by_generators,
)


def _channels(model: T2FiniteModel) -> dict[str, tuple[tuple[Fraction, ...], ...]]:
    return {a.action_id: a.channel for a in model.actions}


class TestTwoByTwoAlternating:
    def test_single_admissible_difference(self):
        model = two_by_two_alternating()
        diffs = list(iter_differences(model))
        assert len(diffs) == 1
        _p0, _p1, v = diffs[0]
        assert v == (
            Fraction(1, 4), Fraction(-1, 4), Fraction(-1, 4), Fraction(1, 4),
        )

    def test_row_observation_collides(self):
        model = two_by_two_alternating()
        w = collision_witness(model, ["row_obs"])
        assert w is not None
        assert panel_separation(model, ["row_obs"]).gamma == 0

    def test_full_observation_separates(self):
        model = two_by_two_alternating()
        assert collision_witness(model, ["full_obs"]) is None
        assert panel_separation(model, ["full_obs"]).gamma == 1

    def test_verifier_agrees(self):
        model = two_by_two_alternating()
        w = collision_witness(model, ["row_obs"])
        assert w is not None
        res = verify_collision(
            theta_0=model.theta_0,
            theta_1=model.theta_1,
            marginal_map=model.marginal_map,
            channels=_channels(model),
            panel=["row_obs"],
            witness_v=w,
            witness_p0=model.theta_0[0],
            witness_p1=model.theta_1[0],
        )
        assert res["verified"] is True

        sep = panel_separation(model, ["full_obs"])
        vres = verify_separation(
            theta_0=model.theta_0,
            theta_1=model.theta_1,
            marginal_map=model.marginal_map,
            channels=_channels(model),
            panel=["full_obs"],
            reported_gamma=sep.gamma,
            reported_p0=sep.witness_p0,
            reported_p1=sep.witness_p1,
        )
        assert vres["verified"] is True


class TestNoCycle:
    def test_empty_difference_set(self):
        model = no_cycle()
        assert list(iter_differences(model)) == []
        assert collision_witness(model, ["a"]) is None
        assert panel_separation(model, ["a"]).gamma is None


class TestZeroMargin:
    def test_full_difference_and_no_collision(self):
        model = zero_margin()
        diffs = list(iter_differences(model))
        assert len(diffs) == 1
        assert collision_witness(model, ["a"]) is None
        assert panel_separation(model, ["a"]).gamma > 0


class TestSymmetricStates:
    def test_no_difference(self):
        model = symmetric_states()
        assert list(iter_differences(model)) == []
        assert panel_separation(model, ["a"]).gamma is None


class TestRepeatedAction:
    def test_duplicate_channel_still_collides(self):
        model = repeated_action()
        w = collision_witness(model, ["row_obs", "row_obs_dup"])
        assert w is not None
        assert panel_separation(model, ["row_obs", "row_obs_dup"]).gamma == 0


class TestCancellationCounterexample:
    def test_generators_hit_but_combination_cancels(self):
        model = cancellation_counterexample()
        # the fibre has multiple independent directions
        assert len(fiber_basis(model)) >= 2
        # per-generator audit: at least one generator is individually hit
        audit = separate_by_generators(model, ["b1"])
        assert audit is not None
        hit = any(
            any(r.residual > 0 for r in gen) for gen in audit
        )
        assert hit is True
        # yet the admissible difference (a combination) is a collision
        w = collision_witness(model, ["b1"])
        assert w is not None
        assert panel_separation(model, ["b1"]).gamma == 0


class TestThreeWayFixedMarginal:
    def test_fiber_needs_more_than_one_generator(self):
        model = three_way_fixed_marginal()
        assert len(fiber_basis(model)) >= 2


class TestExactCollision:
    def test_collision(self):
        model = exact_collision()
        assert collision_witness(model, ["row_obs"]) is not None
        assert panel_separation(model, ["row_obs"]).gamma == 0


class TestNearCollision:
    def test_no_exact_collision_positive_small_separation(self):
        model = near_collision()
        assert collision_witness(model, ["diag"]) is None
        sep = panel_separation(model, ["diag"])
        assert sep.gamma is not None
        assert sep.gamma == Fraction(1, 4)
        assert 0 < sep.gamma < 1


class TestStrictSeparation:
    def test_positive_separation(self):
        model = strict_separation()
        assert collision_witness(model, ["full_obs"]) is None
        assert panel_separation(model, ["full_obs"]).gamma == 1


class TestCanonicalization:
    def test_reordered_catalog_same_hash(self):
        model = two_by_two_alternating()
        shuffled = T2FiniteModel(
            name=model.name,
            n_states=model.n_states,
            theta_0=tuple(reversed(model.theta_0)),
            theta_1=tuple(reversed(model.theta_1)),
            marginal_map=model.marginal_map,
            actions=tuple(reversed(model.actions)),
        )
        _a, h1 = canonicalize_model(model)
        _b, h2 = canonicalize_model(shuffled)
        assert h1 == h2

    def test_different_models_different_hash(self):
        m1 = two_by_two_alternating()
        m2 = no_cycle()
        _a, h1 = canonicalize_model(m1)
        _b, h2 = canonicalize_model(m2)
        assert h1 != h2


class TestPublicApi:
    def test_exports(self):
        from d2t_rna import t2 as t2_pkg

        for name in (
            "T2FiniteModel",
            "Action",
            "canonicalize_model",
            "collision_witness",
            "iter_differences",
            "panel_separation",
            "verify_collision",
            "verify_separation",
        ):
            assert hasattr(t2_pkg, name), name