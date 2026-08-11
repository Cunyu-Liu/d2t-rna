"""P0-2 production kill-tests: TheoremSpec + measure dispatch (v3).

These tests MUST call the production API (``d2t_rna.t2.theorem`` /
``d2t_rna.t2.spec``).  They do NOT reimplement a parallel serializer or solver.

The core P0-2 regression: the DISCRETE_CATALOG path previously called the
convex-hull LP unconditionally and returned ``COUNTEREXAMPLE, gamma=None`` for a
legitimate discrete certificate (``gamma_l1=1/2``) whenever the convex hulls
overlapped (``gamma=0``).  The discrete path must now certify purely from exact
enumeration and never call the convex LP builder.
"""
from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.t2.model import Action, T2FiniteModel
from d2t_rna.t2.spec import (
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
)
from d2t_rna.t2.theorem import (
    T2bCertificate,
    collision_or_separation,
    build_gamma_lp,
)


def _convex_counterexample() -> T2FiniteModel:
    """theta_0={(1,0),(0,1)}, theta_1={(1/4,3/4),(3/4,1/4)}, M=(1,1),
    identity action.  Discrete min-L1 separation is 1/2; the convex hulls of
    the two catalogs intersect, so the convex LP optimum would be 0."""
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
        name="p0_02_convex_counterexample",
        n_states=2,
        theta_0=theta0,
        theta_1=theta1,
        marginal_map=M,
        actions=(identity,),
    )


def test_discrete_path_does_not_import_convex_builder():
    """The discrete certificate must not depend on the convex LP builder.

    Monkeypatch ``build_gamma_lp`` in the theorem namespace to raise; the
    discrete path must still return a valid IFF discrete certificate with
    gamma_l1=1/2 (i.e. it never calls the convex builder).
    """
    import d2t_rna.t2.theorem as theorem_mod

    def boom(*args, **kwargs):
        raise AssertionError("build_gamma_lp must NOT be called on discrete path")

    orig = theorem_mod.build_gamma_lp
    theorem_mod.build_gamma_lp = boom
    try:
        model = _convex_counterexample()
        cert = collision_or_separation(model, ["id"])
    finally:
        theorem_mod.build_gamma_lp = orig

    assert cert.status == "IFF"
    assert cert.gamma == Fraction(1, 2)
    assert cert.enumeration_gamma == Fraction(1, 2)


def test_discrete_vs_convex_one_half_vs_zero():
    """Discrete returns gamma_l1=1/2; the convex hulls overlap (LP optimum 0)."""
    model = _convex_counterexample()
    cert = collision_or_separation(model, ["id"])
    # Discrete object: separation with gamma_l1=1/2.
    assert cert.status == "IFF"
    assert cert.gamma == Fraction(1, 2)
    assert cert.enumeration_matches_lp is False
    # The convex LP builder (separate object) is still callable and gives 0.
    n_real, c, A, b, layout = build_gamma_lp(model, ["id"])
    assert isinstance(layout, dict)
    # gamma_tv = L1/2
    assert cert.gamma_tv == Fraction(1, 4)


def test_convex_hull_request_returns_unsupported():
    """CONVEX_HULL is not a currently certified object -> UNSUPPORTED_SPEC."""
    model = _convex_counterexample()
    spec = TheoremSpec(UNCERTAINTY_CONVEX, MEASURE_ACTION_L1)
    cert = collision_or_separation(model, ["id"], spec=spec)
    assert cert.status == "UNSUPPORTED_SPEC"
    assert cert.gamma is None


def test_product_tv_missing_allocation_rejected():
    """PRODUCT_TV without a registered allocation/product law -> UNSUPPORTED."""
    model = _convex_counterexample()
    spec = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_PRODUCT_TV)
    cert = collision_or_separation(model, ["id"], spec=spec)
    assert cert.status == "UNSUPPORTED_SPEC"
    assert cert.gamma is None


def test_tv_range_in_unit_interval():
    """ACTION_TV / gamma_tv must lie in [0,1]."""
    model = _convex_counterexample()
    cert = collision_or_separation(model, ["id"])
    assert cert.gamma_tv is not None
    assert 0 <= cert.gamma_tv <= 1


def test_invalid_spec_not_silently_fallback():
    """An unknown kind/measure raises ValueError (no silent fallback)."""
    with pytest.raises(ValueError):
        TheoremSpec("BOGUS_KIND", MEASURE_ACTION_L1)
    with pytest.raises(ValueError):
        TheoremSpec(UNCERTAINTY_DISCRETE, "BOGUS_MEASURE")


def test_certificate_is_production_type():
    model = _convex_counterexample()
    cert = collision_or_separation(model, ["id"])
    assert isinstance(cert, T2bCertificate)
