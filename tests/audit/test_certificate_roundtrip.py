"""K6 audit: T2b certificate round-trip + tamper detection.

A certificate must survive a canonical (Fraction-as-{numerator,denominator})
serialize/deserialize round-trip unchanged, and any tampering of
``model/spec/catalog/panel/measure/gamma/p0/p1/witness/weights`` must be caught
by independent verification.  The canonical payload hash must be invariant to
non-deterministic metadata such as a timestamp field.

The verifier uses the *independent discrete oracle* (and the spec/measure
semantics) so a tampered certificate cannot pass by mirroring a production bug.
"""

from __future__ import annotations

import hashlib
import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.fixtures import two_by_two_alternating  # noqa: E402
from d2t_rna.t2.spec import (  # noqa: E402
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)
from d2t_rna.t2.theorem import T2bCertificate, collision_or_separation  # noqa: E402

from tests.independent_oracles.t2_raw_discrete_oracle import (  # noqa: E402
    raw_action_image,
    raw_marginal_of,
    raw_separation_gamma,
)
from tests.independent_oracles.t2_raw_convex_oracle import (  # noqa: E402
    convex_point,
    raw_convex_gamma,
)

MODEL = two_by_two_alternating()
PANEL = ("full_obs",)
CERT = collision_or_separation(MODEL, ["full_obs"])  # gamma == 1 separation


# ---------------------------------------------------------------------------
# canonical serialize / deserialize of a T2bCertificate
# ---------------------------------------------------------------------------

def _frac_to_dict(x):
    return None if x is None else {"numerator": x.numerator, "denominator": x.denominator}


def _frac_from_dict(d):
    return None if d is None else Fraction(d["numerator"], d["denominator"])


def serialize_cert(cert: T2bCertificate) -> dict:
    return {
        "theorem": cert.theorem,
        "status": cert.status,
        "gamma": _frac_to_dict(cert.gamma),
        "gamma_tv": _frac_to_dict(cert.gamma_tv),
        "collision_witness": None if cert.collision_witness is None
            else [_frac_to_dict(x) for x in cert.collision_witness],
        "separation_witness": None if cert.separation_witness is None
            else [_frac_to_dict(x) for x in cert.separation_witness],
        "panel": list(cert.panel),
        "lp_optimal": _frac_to_dict(cert.lp_optimal),
        "lp_primal_feasible": cert.lp_primal_feasible,
        "lp_dual_feasible": cert.lp_dual_feasible,
        "lp_strong_duality": cert.lp_strong_duality,
        "enumeration_gamma": _frac_to_dict(cert.enumeration_gamma),
        "enumeration_matches_lp": cert.enumeration_matches_lp,
        "collapsed": cert.collapsed,
        "spec": {
            "uncertainty_kind": cert.spec.uncertainty_kind,
            "separation_measure": cert.spec.separation_measure,
        },
        "notes": list(cert.notes),
    }


def deserialize_cert(d: dict) -> T2bCertificate:
    return T2bCertificate(
        theorem=d["theorem"],
        status=d["status"],
        gamma=_frac_from_dict(d["gamma"]),
        gamma_tv=_frac_from_dict(d["gamma_tv"]),
        collision_witness=None if d["collision_witness"] is None
            else tuple(_frac_from_dict(x) for x in d["collision_witness"]),
        separation_witness=None if d["separation_witness"] is None
            else tuple(_frac_from_dict(x) for x in d["separation_witness"]),
        panel=tuple(d["panel"]),
        lp_optimal=_frac_from_dict(d["lp_optimal"]),
        lp_primal_feasible=d["lp_primal_feasible"],
        lp_dual_feasible=d["lp_dual_feasible"],
        lp_strong_duality=d["lp_strong_duality"],
        enumeration_gamma=_frac_from_dict(d["enumeration_gamma"]),
        enumeration_matches_lp=d["enumeration_matches_lp"],
        collapsed=d["collapsed"],
        spec=TheoremSpec(
            d["spec"]["uncertainty_kind"], d["spec"]["separation_measure"]
        ),
        notes=tuple(d["notes"]),
    )


# ---------------------------------------------------------------------------
# canonical payload with witness / weights, and its verifier
# ---------------------------------------------------------------------------

def build_payload() -> dict:
    """Build the certificate evidence payload: raw model, panel, spec, the
    certified gamma, the registered witness pair (p0,p1), the witness vector v,
    and the convex mixture weights (one-hot for single-point catalogs)."""
    p0 = MODEL.theta_0[0]
    p1 = MODEL.theta_1[0]
    v = tuple(p1[i] - p0[i] for i in range(MODEL.n_states))
    return {
        "theta_0": [[_frac_to_dict(x) for x in p] for p in MODEL.theta_0],
        "theta_1": [[_frac_to_dict(x) for x in p] for p in MODEL.theta_1],
        "marginal_map": [[_frac_to_dict(x) for x in row] for row in MODEL.marginal_map],
        "channels": {
            a.action_id: [[_frac_to_dict(x) for x in row] for row in a.channel]
            for a in MODEL.actions
        },
        "panel": list(PANEL),
        "spec": {
            "uncertainty_kind": UNCERTAINTY_DISCRETE,
            "separation_measure": MEASURE_ACTION_L1,
        },
        "gamma": _frac_to_dict(CERT.gamma),
        "gamma_tv": _frac_to_dict(CERT.gamma_tv),
        "p0": [_frac_to_dict(x) for x in p0],
        "p1": [_frac_to_dict(x) for x in p1],
        "witness": [_frac_to_dict(x) for x in v],
        "weights": {
            "lambda0": [1.0] * len(MODEL.theta_0),
            "lambda1": [1.0] * len(MODEL.theta_1),
        },
        "timestamp": "2026-08-09T00:00:00Z",  # non-deterministic metadata
    }


def _raw_from_payload(payload):
    theta_0 = [tuple(_frac_from_dict(x) for x in p) for p in payload["theta_0"]]
    theta_1 = [tuple(_frac_from_dict(x) for x in p) for p in payload["theta_1"]]
    marginal_map = [
        tuple(_frac_from_dict(x) for x in row) for row in payload["marginal_map"]
    ]
    channels = {
        aid: [[_frac_from_dict(x) for x in row] for row in ch]
        for aid, ch in payload["channels"].items()
    }
    panel = tuple(payload["panel"])
    return theta_0, theta_1, marginal_map, channels, panel


def verify_payload(payload: dict) -> dict:
    """Independently verify a certificate evidence payload.  Recomputes the
    discrete oracle gamma from the raw model, checks the registered witness pair
    and the convex weights, and enforces the spec/measure semantics."""
    failures: list[str] = []
    theta_0, theta_1, marginal_map, channels, panel = _raw_from_payload(payload)
    gamma = _frac_from_dict(payload["gamma"])
    gamma_tv = _frac_from_dict(payload["gamma_tv"])
    p0 = tuple(_frac_from_dict(x) for x in payload["p0"])
    p1 = tuple(_frac_from_dict(x) for x in payload["p1"])
    witness = tuple(_frac_from_dict(x) for x in payload["witness"])
    spec = payload["spec"]
    kind = spec["uncertainty_kind"]
    measure = spec["separation_measure"]

    # spec validity
    try:
        TheoremSpec(kind, measure)
    except ValueError as exc:
        failures.append(f"invalid spec: {exc}")

    # oracle recomputation
    og = raw_separation_gamma(theta_0, theta_1, marginal_map, channels, panel)
    if og is None:
        failures.append("oracle: discrete difference set empty")
    elif gamma != og:
        failures.append(f"gamma {gamma} != oracle {og}")

    # registered witness pair & difference vector
    if tuple(p1[i] - p0[i] for i in range(len(p0))) != witness:
        failures.append("witness != p1 - p0")
    if raw_marginal_of(marginal_map, p0) != raw_marginal_of(marginal_map, p1):
        failures.append("witness pair not marginally admissible")
    worst = max(
        sum(abs(x) for x in raw_action_image(channels[u], witness)) for u in panel
    )
    if worst != gamma:
        failures.append(f"witness max image {worst} != gamma {gamma}")

    # convex mixture weights consistency
    lam0 = payload["weights"]["lambda0"]
    lam1 = payload["weights"]["lambda1"]
    x0 = convex_point(theta_0, lam0)
    x1 = convex_point(theta_1, lam1)
    v2 = x1 - x0
    if max(abs(a - b) for a, b in zip(v2, [float(x) for x in witness])) > 1e-9:
        failures.append("weights do not reproduce the witness")

    # measure semantics
    if measure in (MEASURE_ACTION_TV, MEASURE_PRODUCT_TV):
        if gamma_tv != tv_from_l1(gamma):
            failures.append("gamma_tv != tv_from_l1(gamma)")
        if not (0 <= gamma_tv <= 1):
            failures.append("gamma_tv out of [0,1]")
        if measure == MEASURE_PRODUCT_TV and not (
            "allocation" in payload and "repeats" in payload
        ):
            failures.append("PRODUCT_TV without allocation/repeats is unsupported")

    # uncertainty-kind semantics
    if kind == UNCERTAINTY_CONVEX:
        cg, _l0, _l1 = raw_convex_gamma(
            theta_0, theta_1, marginal_map, channels, panel
        )
        if cg is None or abs(cg - float(gamma)) > 1e-6:
            failures.append("convex gamma disagrees with reported gamma")

    return {"verified": not failures, "failures": failures}


def canonical_payload_hash(payload: dict) -> str:
    """Canonical hash that excludes non-deterministic metadata keys
    (e.g. timestamp), so metadata changes never alter the evidentiary hash."""
    ignored = {"timestamp"}
    body = {
        k: v for k, v in payload.items() if k not in ignored
    }
    return hashlib.sha256(repr(body).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# round-trip
# ---------------------------------------------------------------------------

def test_certificate_roundtrip_preserves_equality():
    d = serialize_cert(CERT)
    back = deserialize_cert(d)
    assert back == CERT
    # and the fields survive exactly
    assert back.gamma == CERT.gamma
    assert back.gamma_tv == CERT.gamma_tv
    assert back.separation_witness == CERT.separation_witness
    assert back.spec == CERT.spec


def test_certificate_roundtrip_fraction_exact():
    assert CERT.gamma == 1
    d = serialize_cert(CERT)
    # Fraction must be serialized as {numerator, denominator}, not a float/str.
    assert d["gamma"] == {"numerator": 1, "denominator": 1}
    assert _frac_from_dict(d["gamma"]) == Fraction(1)


# ---------------------------------------------------------------------------
# tamper detection
# ---------------------------------------------------------------------------

def _mutate_and_verify(**changes):
    payload = build_payload()
    for key, val in changes.items():
        payload[key] = val
    return verify_payload(payload)


def test_tamper_gamma_fails():
    out = _mutate_and_verify(gamma={"numerator": 2, "denominator": 1})
    assert out["verified"] is False


def test_tamper_witness_fails():
    payload = build_payload()
    # shift the first witness coordinate
    payload["witness"][0]["numerator"] += 1
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_p0_fails():
    payload = build_payload()
    payload["p0"][0]["numerator"] += 1  # no longer a catalog member / not v=p1-p0
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_p1_fails():
    payload = build_payload()
    payload["p1"][0]["numerator"] += 1
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_panel_fails():
    # panel swapped to a collision-blind action -> oracle gamma becomes 0 != 1
    payload = build_payload()
    payload["panel"] = ["row_obs"]
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_catalog_fails():
    payload = build_payload()
    # alter a theta_1 distribution -> oracle recompute no longer equals gamma
    payload["theta_1"][0][0]["numerator"] += 1
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_model_marginal_fails():
    payload = build_payload()
    payload["marginal_map"][0][0]["numerator"] += 1
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_weights_fails():
    payload = build_payload()
    # break the convex weights so they no longer reproduce the witness
    payload["weights"]["lambda1"] = [0.0]
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_measure_fails():
    # declare ACTION_TV but leave gamma_tv as the raw L1 (not halved) -> mismatch
    payload = build_payload()
    payload["spec"]["separation_measure"] = MEASURE_ACTION_TV
    payload["gamma_tv"] = {"numerator": 1, "denominator": 1}  # should be 1/2
    out = verify_payload(payload)
    assert out["verified"] is False


def test_tamper_spec_uncertainty_kind_invalid_fails():
    payload = build_payload()
    payload["spec"]["uncertainty_kind"] = "BOGUS"
    out = verify_payload(payload)
    assert out["verified"] is False


def test_uncertainty_kind_to_convex_is_checked():
    """A CONVEX relabel is only accepted when the independent convex oracle
    confirms it: for this single-point model convex == discrete, so the relabel
    passes -- the verifier actively re-derives the convex value rather than
    blindly trusting the label."""
    payload = build_payload()
    payload["spec"]["uncertainty_kind"] = UNCERTAINTY_CONVEX
    out = verify_payload(payload)
    assert out["verified"] is True, out["failures"]


def test_convex_claim_with_wrong_gamma_fails():
    """Claiming CONVEX with a gamma the convex oracle rejects must fail."""
    payload = build_payload()
    payload["spec"]["uncertainty_kind"] = UNCERTAINTY_CONVEX
    payload["gamma"] = {"numerator": 3, "denominator": 2}  # convex opt is 1
    out = verify_payload(payload)
    assert out["verified"] is False
    assert any("convex" in f for f in out["failures"])


def test_valid_payload_verifies():
    out = verify_payload(build_payload())
    assert out["verified"] is True, out["failures"]


# ---------------------------------------------------------------------------
# canonical payload hash invariance to timestamp
# ---------------------------------------------------------------------------

def test_payload_hash_invariant_to_timestamp():
    p1 = build_payload()
    h1 = canonical_payload_hash(p1)
    p2 = build_payload()
    p2["timestamp"] = "2026-08-09T12:00:00Z"  # only metadata changes
    assert canonical_payload_hash(p2) == h1


def test_payload_hash_changes_when_evidence_changes():
    p1 = build_payload()
    h1 = canonical_payload_hash(p1)
    p2 = build_payload()
    p2["gamma"] = {"numerator": 2, "denominator": 1}
    assert canonical_payload_hash(p2) != h1
