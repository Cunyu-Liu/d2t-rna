"""K3 audit: separation-measure dispatch (ACTION_L1 vs ACTION_TV vs PRODUCT_TV).

The v7 audit found the action-level L1 separation mislabelled as a product-law
TV.  This audit file verifies:

  * for a certified separation, ``gamma`` is the raw action-L1 value and
    ``gamma_tv == gamma / 2`` (ACTION_TV), with ``0 <= gamma_tv <= 1``;
  * the bare ``gamma`` is never propagated alone as a TV value (a TV claim must
    carry the halved value, never the raw L1);
  * ``PRODUCT_TV`` requested without allocation/repeats is UNSUPPORTED_SPEC --
    it must not be silently certified as a product-law TV on the T2b object.
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.fixtures import near_collision, strict_separation  # noqa: E402
from d2t_rna.t2.spec import (  # noqa: E402
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)
from d2t_rna.t2.theorem import collision_or_separation  # noqa: E402

UNSUPPORTED_SPEC = "UNSUPPORTED_SPEC"


def _product_tv_supported(spec, allocation=None, repeats=None):
    """Independent gate: a PRODUCT_TV separation object requires a declared
    allocation and repeat count; without them it is unsupported (no product law
    exists to express a TV over)."""
    if spec.separation_measure != MEASURE_PRODUCT_TV:
        return True
    return allocation is not None and repeats is not None


@pytest.mark.parametrize(
    "model,panel,gamma",
    [
        (strict_separation(), ["full_obs"], Fraction(1)),
        (near_collision(), ["diag"], Fraction(1, 4)),
    ],
)
@pytest.mark.parametrize(
    "measure",
    [MEASURE_ACTION_L1, MEASURE_ACTION_TV],
)
def test_tv_is_half_of_l1_and_in_unit_interval(model, panel, gamma, measure):
    spec = TheoremSpec(UNCERTAINTY_DISCRETE, measure)
    cert = collision_or_separation(model, panel, spec)
    assert cert.gamma == gamma
    # gamma is the raw action-L1 value; the TV expression is exactly gamma/2.
    assert cert.gamma_tv == tv_from_l1(cert.gamma)
    assert cert.gamma_tv == gamma / 2
    assert 0 <= cert.gamma_tv <= 1


@pytest.mark.parametrize(
    "model,panel,gamma",
    [
        (strict_separation(), ["full_obs"], Fraction(1)),
        (near_collision(), ["diag"], Fraction(1, 4)),
    ],
)
def test_bare_gamma_never_propagated_alone_as_tv(model, panel, gamma):
    """The bare action-L1 ``gamma`` must never be reported as the TV: whenever a
    TV is requested the certificate carries the halved ``gamma_tv``, never the
    raw L1 value itself (except trivially at gamma == 0)."""
    spec = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_TV)
    cert = collision_or_separation(model, panel, spec)
    assert cert.gamma_tv == gamma / 2
    assert cert.gamma_tv != cert.gamma  # raw L1 is not TV for gamma > 0
    # and the certificate distinguishes the two fields by name
    assert cert.gamma is not None
    assert cert.gamma_tv is not None


def test_product_tv_without_allocation_is_unsupported():
    """A PRODUCT_TV separation object without allocation/repeats has no product
    law to express a TV over -> it must be UNSUPPORTED_SPEC, never silently
    certified as a product-law TV."""
    spec = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_PRODUCT_TV)
    assert _product_tv_supported(spec) is False
    # With an allocation and repeat count it becomes supported.
    assert _product_tv_supported(
        spec, allocation=("full_obs",), repeats=(1,)
    ) is True


def test_action_tv_is_supported_without_allocation():
    """ACTION_TV (and ACTION_L1) are supported on the T2b object without an
    allocation -- they express the *action-level* separation, not a product TV."""
    l1 = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_L1)
    tv = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_ACTION_TV)
    assert _product_tv_supported(l1) is True
    assert _product_tv_supported(tv) is True


def test_product_tv_spec_is_not_silently_certified_as_product_tv():
    """A PRODUCT_TV separation object without allocation/repeats is not part of
    the formally supported face (DISCRETE x ACTION_L1/ACTION_TV).  It must return
    UNSUPPORTED_SPEC and never be silently certified as a product-law TV, and the
    raw action-L1 separation must not be relabelled as product TV."""
    model = strict_separation()
    spec = TheoremSpec(UNCERTAINTY_DISCRETE, MEASURE_PRODUCT_TV)
    cert = collision_or_separation(model, ["full_obs"], spec)
    assert cert.status == UNSUPPORTED_SPEC
    assert cert.gamma is None
    assert cert.gamma_tv is None
    assert _product_tv_supported(spec) is False
