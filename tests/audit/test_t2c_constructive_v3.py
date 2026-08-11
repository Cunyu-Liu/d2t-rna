"""P0-4 audit: production T2CertificateV3 + independent verifier + constructive T2c.

Verifies (contract P0-4):

* ``T2CertificateV3`` round-trips through ``to_dict/from_dict``;
* a valid discrete certificate verifies through ``verify_certificate_v3`` using
  only the certificate + registered raw model;
* tampering any bound field (schema/model/spec/catalog/panel/allocation/
  measure/value/p0/p1/witness/receipt) fails verification;
* convex certificates are not fabricated / rejected;
* legacy V2 certificates are only readable as ``LEGACY_UNVERIFIED`` (never
  silently aliased);
* ``constructive_feasibility_v3`` recomputes alpha/beta/rho/cost internally and
  only returns ``CONSTRUCTIVELY_FEASIBLE`` when the independent exact-risk
  receipt matches and thresholds/budget hold; forged ``alpha=beta=0`` fails;
* information-only gates never return ``CONSTRUCTIVELY_FEASIBLE``.
"""

from __future__ import annotations

import copy
import os
import sys
from dataclasses import replace
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.bounds import (  # noqa: E402
    T2cConstructiveStatus,
    constructive_feasibility_status,
    constructive_feasibility_v3,
    information_only_status,
    _recomputed_risk_receipt,
)
from d2t_rna.t2.certificate_v3 import (  # noqa: E402
    SCHEMA_ID,
    T2CertificateV3,
    LegacyCertificateReadError,
    generate_certificate_v3,
    legacy_certificate_reader,
)
from d2t_rna.t2.decision import conditional_rule_errors  # noqa: E402
from d2t_rna.t2.model import Action, T2FiniteModel  # noqa: E402
from d2t_rna.t2.spec import (  # noqa: E402
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
)
from d2t_rna.t2.verify import verify_certificate_v3  # noqa: E402


def _F(n, d=1):
    return Fraction(n, d)


def _make_model() -> T2FiniteModel:
    """A 2-state model whose discrete difference set is non-empty.

    ``theta_0 = {(1,0)}``, ``theta_1 = {(1/2,1/2)}``; the passive marginal map
    is the total-mass row ``(1,1)`` so both catalogs share the same marginal.
    The single identity action separates them with ``gamma_l1 = 1`` and the
    admissible difference witness ``(-1/2, 1/2)``.
    """
    return T2FiniteModel(
        name="p04-fixture",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(1, 2), _F(1, 2)),),
        marginal_map=((_F(1), _F(1)),),
        actions=(Action("id", ((_F(1), _F(0)), (_F(0), _F(1)))),),
    )


def _make_cert(model=None):
    model = model if model is not None else _make_model()
    return generate_certificate_v3(
        model=model,
        panel=("id",),
        gamma_l1=_F(1),
        status="IFF",
        p0=(_F(1), _F(0)),
        p1=(_F(1, 2), _F(1, 2)),
        difference_witness=(_F(-1, 2), _F(1, 2)),
        separation_measure=MEASURE_ACTION_L1,
        uncertainty_kind=UNCERTAINTY_DISCRETE,
        allocation=None,
        generator_commit="deadbeef",
        generator_tree="cafebabe",
    )


@pytest.fixture(scope="module")
def model():
    return _make_model()


@pytest.fixture(scope="module")
def v3(model):
    return _make_cert(model)


def test_roundtrip_preserves_equality(v3):
    d = v3.to_dict()
    back = T2CertificateV3.from_dict(copy.deepcopy(d))
    assert back.to_dict() == d
    assert back.canonical_payload_hash() == v3.canonical_payload_hash()


def test_valid_certificate_verifies(v3, model):
    out = verify_certificate_v3(v3, model)
    assert out["verified"] is True, out["failures"]


def test_schema_id_and_version(v3):
    assert v3.schema_id == SCHEMA_ID
    assert v3.schema_version == "3"


def test_tamper_model_fails(v3):
    other = T2FiniteModel(
        name="other",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(1, 3), _F(2, 3)),),
        marginal_map=((_F(1), _F(1)),),
        actions=(Action("id", ((_F(1), _F(0)), (_F(0), _F(1)))),),
    )
    out = verify_certificate_v3(v3, other)
    assert out["verified"] is False
    assert any("model_hash" in f or "catalog_hash" in f for f in out["failures"])


def test_tamper_gamma_fails(v3, model):
    tampered = replace(v3, gamma_l1=_F(3, 4))
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False
    assert any("gamma_l1" in f for f in out["failures"])


def test_tamper_panel_fails(v3, model):
    tampered = replace(v3, panel=("ghost",))
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False


def test_tamper_witness_fails(v3, model):
    tampered = replace(v3, difference_witness=(_F(-1, 3), _F(1, 3)))
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False
    assert any("difference_witness" in f for f in out["failures"])


def test_tamper_receipt_fails(v3, model):
    tampered = replace(v3, primal_receipt="deadbeef")
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False
    assert any("primal_receipt" in f for f in out["failures"])


def test_tamper_spec_convex_fails(v3, model):
    tampered = replace(v3, uncertainty_kind=UNCERTAINTY_CONVEX)
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False
    assert any("convex" in f for f in out["failures"])


def test_tamper_measure_semantics_fails(v3, model):
    # switching separation_measure to ACTION_TV makes gamma_tv mandatory; the
    # L1-built certificate carries gamma_tv=None so it must fail.
    tampered = replace(v3, separation_measure=MEASURE_ACTION_TV, gamma_tv=None)
    out = verify_certificate_v3(tampered, model)
    assert out["verified"] is False


def test_legacy_reader_never_aliases(v3):
    assert legacy_certificate_reader(object()) == "LEGACY_UNVERIFIED"
    with pytest.raises(LegacyCertificateReadError):
        legacy_certificate_reader(v3)


def test_convex_not_fabricated():
    # generate_certificate_v3 always builds a discrete certificate; a caller
    # cannot sneak convex weights into a discrete certificate.
    model = _make_model()
    cert = _make_cert(model)
    assert cert.convex_mixture_weights is None


def test_constructive_v3_valid_receipt_is_feasible():
    p0 = (_F(1), _F(0))
    p1 = (_F(1, 2), _F(1, 2))
    rule = conditional_rule_errors(p0, p1, 1, _F(1), _F(1))
    receipt = _recomputed_risk_receipt(
        p0, p1, 1, _F(1), _F(1), (_F(1),), (1,),
        rule.alpha, rule.beta, rule.rho_0, rule.rho_1, Fraction(1),
    )
    out = constructive_feasibility_v3(
        p0=p0, p1=p1, n=1, costs=(_F(1),), allocation=(1,),
        lower=_F(1), upper=_F(1), budget=_F(2),
        alpha_max=_F(1), beta_max=_F(1), checker_receipt=receipt,
    )
    assert out.status == T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE
    # alpha/beta were recomputed internally, not taken from the caller
    assert out.alpha == rule.alpha
    assert out.beta == rule.beta


def test_constructive_v3_forged_alpha_beta_zero_fails():
    # A fabricated receipt claiming alpha=beta=0 does not match the recomputed
    # risks, so it must NOT return CONSTRUCTIVELY_FEASIBLE.
    p0 = (_F(1), _F(0))
    p1 = (_F(1, 2), _F(1, 2))
    forged = _recomputed_risk_receipt(
        p0, p1, 1, _F(1), _F(1), (_F(1),), (1,),
        _F(0), _F(0), _F(0), _F(0), _F(0),
    )
    out = constructive_feasibility_v3(
        p0=p0, p1=p1, n=1, costs=(_F(1),), allocation=(1,),
        lower=_F(1), upper=_F(1), budget=_F(2),
        alpha_max=_F(1), beta_max=_F(1), checker_receipt=forged,
    )
    assert out.status == T2cConstructiveStatus.NOT_ESTABLISHED


def test_constructive_v3_over_budget_fails():
    p0 = (_F(1), _F(0))
    p1 = (_F(1, 2), _F(1, 2))
    rule = conditional_rule_errors(p0, p1, 1, _F(1), _F(1))
    receipt = _recomputed_risk_receipt(
        p0, p1, 1, _F(1), _F(1), (_F(1),), (1,),
        rule.alpha, rule.beta, rule.rho_0, rule.rho_1, Fraction(1),
    )
    out = constructive_feasibility_v3(
        p0=p0, p1=p1, n=1, costs=(_F(1),), allocation=(1,),
        lower=_F(1), upper=_F(1), budget=_F(0),
        alpha_max=_F(1), beta_max=_F(1), checker_receipt=receipt,
    )
    assert out.status == T2cConstructiveStatus.NO_GO


def test_information_only_never_feasible():
    for cf in [
        information_only_status(),
        information_only_status(
            product_laws_registered=True, allocation_registered=True
        ),
        information_only_status(
            product_laws_registered=True,
            allocation_registered=True,
            decision_rule_registered=True,
        ),
    ]:
        assert cf.status != T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE


def test_bool_alpha_path_never_feasible():
    # The four-bool + caller alpha/beta API must never produce a positive verdict.
    kwargs = dict(
        product_laws_registered=True,
        allocation_registered=True,
        decision_rule_registered=True,
        budget_cost_verified=True,
        alpha=_F(1, 10),
        beta=_F(1, 10),
        alpha_max=_F(1, 2),
        beta_max=_F(1, 2),
    )
    cf = constructive_feasibility_status(**kwargs)
    assert cf.status == T2cConstructiveStatus.NECESSARY_ONLY
    assert cf.status != T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE
