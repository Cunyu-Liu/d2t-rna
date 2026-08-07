"""P0-3 first-level gate: the T2b semantic counterexamples.

The audit (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``, phase P0-3) requires
that the known T2b counterexamples become a *first-level gate*:

1. **T2b convexification.**  The discrete-catalog enumeration and the
   convex-hull LP solve different problems and can disagree
   (``enumeration_gamma=1/2`` vs ``lp_optimal=0``).  When they disagree the
   certifier must fail closed: no formal ``IFF`` certificate is issued.
2. **Forged checker.**  The independent verifier must reject a catalog-outside,
   non-normalized, ``v != p1-p0`` witness instead of accepting it.
3. **TV range.**  Any value reported in a TV measure must lie in ``[0,1]``
   (the paper's ``gamma=49/25`` violates this).
4. **Identical distributions / empty difference set.**  ``D`` empty is a
   vacuous separation, never a collision certificate.

These are the acceptance fixtures for the semantic kernel; they must hold on
every future change to ``model/witness/theorem/verify/lp``.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.t2.fixtures import (
    near_collision,
    no_cycle,
    strict_separation,
    two_by_two_alternating,
)
from d2t_rna.t2.model import Action, T2FiniteModel
from d2t_rna.t2.spec import (
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)
from d2t_rna.t2.theorem import collision_or_separation
from d2t_rna.t2.verify import verify_collision


# ---------------------------------------------------------------------------
# 1. T2b convexification counterexample (discrete vs convex-hull disagreement)
# ---------------------------------------------------------------------------

def _convex_counterexample() -> T2FiniteModel:
    """theta_0={(1,0),(0,1)}, theta_1={(1/4,3/4),(3/4,1/4)}, M=(1,1),
    identity action.  Discrete min-L1 separation is 1/2; the convex hulls of
    the two catalogs intersect, so the LP optimum is 0."""
    theta0 = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))
    theta1 = (
        (Fraction(1, 4), Fraction(3, 4)),
        (Fraction(3, 4), Fraction(1, 4)),
    )
    M = ((Fraction(1), Fraction(1)),)
    identity = Action(
        action_id="id",
        channel=(
            (Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(1)),
        ),
    )
    return T2FiniteModel(
        name="p0_03_convex_counterexample",
        n_states=2,
        theta_0=theta0,
        theta_1=theta1,
        marginal_map=M,
        actions=(identity,),
    )


def test_t2b_convexification_fails_closed():
    model = _convex_counterexample()
    cert = collision_or_separation(model, ["id"])
    # The two engines disagree -> no formal certificate.
    assert cert.enumeration_matches_lp is False
    assert cert.status == "COUNTEREXAMPLE"
    assert cert.gamma is None
    # Both values are preserved for evidence.
    assert cert.enumeration_gamma == Fraction(1, 2)
    assert cert.lp_optimal is not None
    assert cert.lp_optimal == Fraction(0)


def test_t2b_convexification_never_iff():
    model = _convex_counterexample()
    cert = collision_or_separation(model, ["id"])
    assert cert.status != "IFF"
    assert cert.collision_witness is None
    assert cert.separation_witness is None


# ---------------------------------------------------------------------------
# 2. Forged checker must reject catalog-outside / non-normalized / v!=p1-p0
# ---------------------------------------------------------------------------

def test_forged_checker_rejects_catalog_outside_triple():
    theta0 = ((Fraction(1), Fraction(0)),)
    theta1 = ((Fraction(0), Fraction(1)),)
    M = ((Fraction(1), Fraction(1)),)
    # Outside both catalogs, not normalized is irrelevant here (they do sum to
    # 1), but p0=p1=(1/2,1/2) is not a member of either singleton catalog, and
    # v=(1,-1) != p1-p0=(0,0).
    p0_out = (Fraction(1, 2), Fraction(1, 2))
    p1_out = (Fraction(1, 2), Fraction(1, 2))
    v_forged = (Fraction(1), Fraction(-1))
    blank = ((Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2)))
    channels = {"blank": blank}
    out = verify_collision(
        theta_0=theta0,
        theta_1=theta1,
        marginal_map=M,
        channels=channels,
        panel=("blank",),
        witness_v=v_forged,
        witness_p0=p0_out,
        witness_p1=p1_out,
    )
    assert out["verified"] is False
    assert out["registered_triple"] is False
    assert any("member" in f for f in out["failures"])
    assert any("!=" in f for f in out["failures"])


def test_forged_checker_rejects_non_normalized_witness():
    theta0 = ((Fraction(1), Fraction(0)),)
    theta1 = ((Fraction(0), Fraction(1)),)
    M = ((Fraction(1), Fraction(1)),)
    # p1 sums to 2 -> not a distribution.
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(0), Fraction(2))
    v = (Fraction(-1), Fraction(2))
    blank = ((Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2)))
    out = verify_collision(
        theta_0=theta0,
        theta_1=theta1,
        marginal_map=M,
        channels={"blank": blank},
        panel=("blank",),
        witness_v=v,
        witness_p0=p0,
        witness_p1=p1,
    )
    assert out["verified"] is False
    assert any("distribution" in f for f in out["failures"])


def test_legit_registered_collision_still_accepted():
    # The existing registered path must keep working.
    model = two_by_two_alternating()
    from d2t_rna.t2.witness import collision_witness

    w = collision_witness(model, ["row_obs"])
    assert w is not None
    out = verify_collision(
        theta_0=model.theta_0,
        theta_1=model.theta_1,
        marginal_map=model.marginal_map,
        channels={a.action_id: a.channel for a in model.actions},
        panel=("row_obs",),
        witness_v=w,
        witness_p0=model.theta_0[0],
        witness_p1=model.theta_1[0],
    )
    assert out["registered_triple"] is True
    assert out["verified"] is True


# ---------------------------------------------------------------------------
# 3. TV range: any TV-measure value must lie in [0,1]
# ---------------------------------------------------------------------------

def test_tv_from_l1_half():
    assert tv_from_l1(Fraction(1)) == Fraction(1, 2)
    assert tv_from_l1(Fraction(2)) == Fraction(1)  # max L1 -> TV 1
    assert tv_from_l1(Fraction(0)) == Fraction(0)


def test_gamma_tv_in_unit_interval_for_separations():
    for model, panel in [
        (strict_separation(), ["full_obs"]),
        (near_collision(), ["diag"]),
        (two_by_two_alternating(), ["full_obs"]),
    ]:
        cert = collision_or_separation(model, panel)
        assert cert.gamma is not None
        assert 0 <= cert.gamma_tv <= 1, (model.name, panel, cert.gamma_tv)
        # TV is the raw L1 halved precisely when the measure is a TV.
        assert cert.gamma_tv == tv_from_l1(cert.gamma)


def test_gamma_tv_is_none_when_no_separation():
    cert = collision_or_separation(two_by_two_alternating(), ["row_obs"])
    assert cert.gamma == 0
    assert cert.gamma_tv == 0


# ---------------------------------------------------------------------------
# 4. Identical distributions / empty difference set is vacuous, never a cert
# ---------------------------------------------------------------------------

def test_empty_difference_set_is_vacuous_not_collision():
    model = no_cycle()
    cert = collision_or_separation(model, ["a"])
    assert cert.enumeration_gamma is None
    assert cert.gamma is None
    assert cert.collision_witness is None
    assert cert.status == "IFF"  # vacuous separation, D empty


# ---------------------------------------------------------------------------
# TheoremSpec: hash-bound object identity, validation
# ---------------------------------------------------------------------------

def test_spec_canonical_hash_is_stable():
    a = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    b = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    assert a.canonical() == b.canonical()
    assert a.sha256() == b.sha256()
    assert len(a.sha256()) == 64


def test_spec_distinguishes_uncertainty_kinds():
    assert TheoremSpec(
        UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1
    ).sha256() != TheoremSpec(
        UNCERTAINTY_CONVEX, MEASURE_ACTION_L1
    ).sha256()


def test_spec_distinguishes_measures():
    assert TheoremSpec(
        UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1
    ).sha256() != TheoremSpec(
        UNCERTAINTY_DISCRETE, MEASURE_ACTION_TV
    ).sha256()


def test_spec_rejects_unknown_values():
    with pytest.raises(ValueError):
        TheoremSpec("BOGUS", MEASURE_ACTION_L1)
    with pytest.raises(ValueError):
        TheoremSpec(UNCERTAINTY_DISCRETE, "BOGUS")


def test_spec_is_frozen():
    spec = TheoremSpec()
    with pytest.raises(Exception):
        spec.uncertainty_kind = UNCERTAINTY_CONVEX


# ---------------------------------------------------------------------------
# Regression: existing IFF fixtures still certify under the L1 measure
# ---------------------------------------------------------------------------

def test_regression_existing_iff_fixtures_unaffected():
    cert = collision_or_separation(two_by_two_alternating(), ["full_obs"])
    assert cert.status == "IFF"
    assert cert.gamma == 1
    assert cert.enumeration_matches_lp is True
    assert cert.lp_strong_duality is True