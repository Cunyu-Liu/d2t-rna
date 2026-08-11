"""Independent verifier for T2 collision / separation results.

This module deliberately does **not** import any helper from
:mod:`d2t_rna.t2.witness` or :mod:`d2t_rna.t2.model`.  It re-derives the
linear algebra from raw primitives (``fractions.Fraction``) so that a bug in
the production path cannot be mirrored into the checker.  It independently
re-verifies:

* membership of a submitted witness in the declared catalogs and that the
  submitted distributions are normalized (P0-3 forged-checker gate);
* consistency of the difference vector ``v = p_1 - p_0``;
* marginal collision of a witness (``M p_0 == M p_1``);
* action-level law equality/separation (``B_u v`` computed from scratch);
* the reported separation value.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence

# Re-build the smallest primitives locally so no production helper is shared.
Fraction  # noqa: B018  (imported for exact arithmetic)


def _dot(row: Sequence[Fraction], v: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(row, v)), Fraction(0))


def _l1(v: Sequence[Fraction]) -> Fraction:
    return sum((abs(x) for x in v), Fraction(0))


def _action_image_from_raw(
    channel: Sequence[Sequence[Fraction]],
    v: Sequence[Fraction],
) -> list[Fraction]:
    """``(B v)[y] = sum_w Q[y][w] v[w]`` computed from a raw channel."""
    return [_dot(row, v) for row in channel]


def _is_distribution(p: Sequence[Fraction]) -> bool:
    """True iff ``p`` is a non-empty probability vector (entries in [0,1],
    summing to 1)."""
    if not p:
        return False
    total = Fraction(0)
    for x in p:
        if x < 0 or x > 1:
            return False
        total += x
    return total == 1


def _in_catalog(p: Sequence[Fraction], catalog) -> bool:
    """True iff ``p`` is exactly one of the declared catalog distributions."""
    return any(tuple(p) == tuple(q) for q in catalog)


def verify_collision(
    *,
    theta_0: Sequence[Sequence[Fraction]],
    theta_1: Sequence[Sequence[Fraction]],
    marginal_map: Sequence[Sequence[Fraction]],
    channels: dict[str, Sequence[Sequence[Fraction]]],
    panel: Sequence[str],
    witness_v: Sequence[Fraction],
    witness_p0: Sequence[Fraction],
    witness_p1: Sequence[Fraction],
) -> dict[str, object]:
    """Independently verify that ``witness_v`` is a true collision witness:
    a nonzero admissible difference whose action-image is zero under every
    panel action.

    The submitted ``(p_0, p_1, v)`` triple is only accepted when it is a
    *registered* triple: ``p_0`` and ``p_1`` are members of the declared
    catalogs, they are normalized distributions, and ``v == p_1 - p_0``.
    Without these checks the checker would accept catalog-outside witnesses
    (the audit's forged-checker counterexample).
    """
    failures: list[str] = []

    if not _is_distribution(witness_p0):
        failures.append("witness_p0 is not a normalized distribution")
    if not _is_distribution(witness_p1):
        failures.append("witness_p1 is not a normalized distribution")
    if not _in_catalog(witness_p0, theta_0):
        failures.append("witness_p0 not a member of theta_0 catalog")
    if not _in_catalog(witness_p1, theta_1):
        failures.append("witness_p1 not a member of theta_1 catalog")
    if tuple(witness_v) != tuple(
        x - y for x, y in zip(witness_p1, witness_p0)
    ):
        failures.append("witness_v != witness_p1 - witness_p0")

    def marginal_of(p: Sequence[Fraction]) -> list[Fraction]:
        return [_dot(row, p) for row in marginal_map]

    m0 = marginal_of(witness_p0)
    m1 = marginal_of(witness_p1)
    if m0 != m1:
        failures.append("marginal images differ")
    if all(x == 0 for x in witness_v):
        failures.append("witness is zero vector")
    for action_id in panel:
        channel = channels[action_id]
        image = _action_image_from_raw(channel, witness_v)
        if not all(x == 0 for x in image):
            failures.append(f"action {action_id!r} residual nonzero")
    return {
        "verified": not failures,
        "failures": failures,
        "marginal_collision": m0 == m1,
        "action_residuals_zero": failures == [],
        "registered_triple": (
            _in_catalog(witness_p0, theta_0)
            and _in_catalog(witness_p1, theta_1)
            and tuple(witness_v)
            == tuple(x - y for x, y in zip(witness_p1, witness_p0))
        ),
    }


def verify_separation(
    *,
    theta_0: Sequence[Sequence[Fraction]],
    theta_1: Sequence[Sequence[Fraction]],
    marginal_map: Sequence[Sequence[Fraction]],
    channels: dict[str, Sequence[Sequence[Fraction]]],
    panel: Sequence[str],
    reported_gamma: Fraction,
    reported_p0: Sequence[Fraction],
    reported_p1: Sequence[Fraction],
) -> dict[str, object]:
    """Independently recompute the separation attained at the reported witness.

    Verifies (a) the witness is admissible, (b) the reported gamma equals the
    max L1 action-image at that witness, and (c) no admissible difference in
    the (small, enumerated here) catalog attains a strictly smaller value.
    Also verifies the reported witness is a registered catalog pair (P0-3
    forged-checker gate).
    """
    failures: list[str] = []
    if not _is_distribution(reported_p0):
        failures.append("reported_p0 is not a normalized distribution")
    if not _is_distribution(reported_p1):
        failures.append("reported_p1 is not a normalized distribution")
    if not _in_catalog(reported_p0, theta_0):
        failures.append("reported_p0 not a member of theta_0 catalog")
    if not _in_catalog(reported_p1, theta_1):
        failures.append("reported_p1 not a member of theta_1 catalog")
    m0 = [_dot(row, reported_p0) for row in marginal_map]
    m1 = [_dot(row, reported_p1) for row in marginal_map]
    if m0 != m1:
        failures.append("reported witness not marginally admissible")

    # gamma at the reported witness
    worst = _l1(_action_image_from_raw(channels[panel[0]], _diff(reported_p1, reported_p0)))
    for action_id in panel[1:]:
        img = _l1(_action_image_from_raw(channels[action_id], _diff(reported_p1, reported_p0)))
        if img > worst:
            worst = img
    if worst != reported_gamma:
        failures.append(
            f"reported gamma {reported_gamma} != recomputed {worst}"
        )

    # global infimum over the full (small) catalog
    best: Fraction | None = None
    for p0 in theta_0:
        m0c = [_dot(row, p0) for row in marginal_map]
        for p1 in theta_1:
            if [_dot(row, p1) for row in marginal_map] != m0c:
                continue
            v = _diff(p1, p0)
            if all(x == 0 for x in v):
                continue
            val = max(_l1(_action_image_from_raw(channels[a], v)) for a in panel)
            if best is None or val < best:
                best = val
    if best is None:
        best = Fraction("inf")
    if reported_gamma != best:
        failures.append(
            f"reported gamma {reported_gamma} != infimum over catalog {best}"
        )
    return {
        "verified": not failures,
        "failures": failures,
        "reported_gamma": reported_gamma,
        "infimum_over_catalog": best,
    }


def _diff(a: Sequence[Fraction], b: Sequence[Fraction]) -> list[Fraction]:
    return [x - y for x, y in zip(a, b)]

# ---------------------------------------------------------------------------
# P0-4: independent verifier for a T2CertificateV3
# ---------------------------------------------------------------------------

def _local_infimum_gamma(theta_0, theta_1, marginal_map, channels, panel):
    """Local exact infimum over the discrete admissible difference set.

    This deliberately re-derives the linear algebra from raw primitives in this
    module (no import of the production solver), so a production bug cannot be
    mirrored into the checker.  Returns ``(Fraction, best_p0, best_p1, best_v)``
    or ``(None, None, None, None)`` when the difference set is empty.
    """
    best = None
    best_triple = None
    for p0 in theta_0:
        m0 = [_dot(row, p0) for row in marginal_map]
        for p1 in theta_1:
            if [_dot(row, p1) for row in marginal_map] != m0:
                continue
            v = _diff(p1, p0)
            if all(x == 0 for x in v):
                continue
            val = max(_l1(_action_image_from_raw(channels[a], v)) for a in panel)
            if best is None or val < best:
                best = val
                best_triple = (p0, p1, v)
    if best is None:
        return None, None, None, None
    return best, best_triple[0], best_triple[1], best_triple[2]


def verify_certificate_v3(cert, model) -> dict:
    """Independently verify a :class:`T2CertificateV3` against the registered
    raw model.

    Depends only on ``cert`` and ``model`` (no second set of unbound inputs).
    Recomputes every bound hash, the exact discrete gamma by local enumeration,
    the measure semantics and the primal/dual receipts.  Any tampering of
    schema/model/spec/catalog/panel/allocation/measure/value/witness/receipt
    fails verification.
    """
    from .certificate_v3 import (
        SCHEMA_ID,
        action_panel_hash,
        allocation_hash,
        catalog_hash,
        model_hash,
        spec_hash,
        _receipts,
    )
    from .spec import (
        MEASURE_ACTION_TV,
        MEASURE_PRODUCT_TV,
        UNCERTAINTY_CONVEX,
        TheoremSpec,
        tv_from_l1,
    )

    failures: list[str] = []

    # --- schema identity
    if cert.schema_id != SCHEMA_ID:
        failures.append(f"schema_id mismatch: {cert.schema_id!r}")
    if getattr(cert, "schema_version", None) != "3":
        failures.append("not a v3 certificate")

    # --- spec validity
    try:
        TheoremSpec(cert.uncertainty_kind, cert.separation_measure)
    except ValueError as exc:
        failures.append(f"invalid spec: {exc}")

    # --- bound input hashes (recomputed from cert + model only)
    if cert.model_hash != model_hash(model):
        failures.append("model_hash mismatch (model tampered)")
    if cert.spec_hash != spec_hash(TheoremSpec(cert.uncertainty_kind, cert.separation_measure)):
        failures.append("spec_hash mismatch")
    if cert.catalog_hash != catalog_hash(model):
        failures.append("catalog_hash mismatch (catalog tampered)")
    _by_id = {a.action_id: a for a in model.actions}
    if any(aid not in _by_id for aid in cert.panel):
        failures.append("action_panel_hash mismatch (panel/channel tampered)")
    elif cert.action_panel_hash != action_panel_hash(model, cert.panel):
        failures.append("action_panel_hash mismatch (panel/channel tampered)")
    if cert.allocation_hash != allocation_hash(cert.allocation):
        failures.append("allocation_hash mismatch")

    # --- measure semantics
    tv = tv_from_l1(cert.gamma_l1) if cert.gamma_l1 is not None else None
    if cert.separation_measure in (MEASURE_ACTION_TV, MEASURE_PRODUCT_TV):
        if cert.gamma_tv != tv:
            failures.append("gamma_tv != tv_from_l1(gamma_l1)")
        if not (cert.gamma_tv is None or 0 <= cert.gamma_tv <= 1):
            failures.append("gamma_tv out of [0,1]")
    if cert.separation_measure == MEASURE_PRODUCT_TV and cert.allocation is None:
        failures.append("PRODUCT_TV without allocation is unsupported")

    # --- uncertainty kind / convex not fabricated
    if cert.uncertainty_kind == UNCERTAINTY_CONVEX:
        failures.append(
            "convex certificates unsupported; convex weights must not be "
            "fabricated"
        )

    # --- independent discrete recomputation
    by_id = {a.action_id: a for a in model.actions}
    panel = list(cert.panel)
    unknown = [aid for aid in panel if aid not in by_id]
    if unknown:
        failures.append(f"panel references unknown action(s): {unknown}")
    else:
        theta_0 = model.theta_0
        theta_1 = model.theta_1
        marginal_map = model.marginal_map
        channels = {aid: by_id[aid].channel for aid in panel}
        gamma, g_p0, g_p1, g_v = _local_infimum_gamma(
            theta_0, theta_1, marginal_map, channels, panel
        )
        if gamma is None:
            if not cert.collapsed:
                failures.append("discrete difference set empty but not collapsed")
        elif cert.gamma_l1 != gamma:
            failures.append(
                f"reported gamma_l1 {cert.gamma_l1} != independent {gamma}"
            )
            # even a tampered witness must not pass
        # witness consistency, if a witness is claimed
        if cert.difference_witness is not None and gamma is not None:
            p0 = cert.p0
            p1 = cert.p1
            if p0 is None or p1 is None:
                failures.append("difference_witness present but p0/p1 missing")
            elif tuple(x - y for x, y in zip(p1, p0)) != tuple(cert.difference_witness):
                failures.append("difference_witness != p1 - p0")
            else:
                worst = max(
                    _l1(_action_image_from_raw(channels[a], cert.difference_witness))
                    for a in panel
                )
                if worst != cert.gamma_l1:
                    failures.append(
                        f"claimed witness attains {worst} != gamma_l1"
                    )

    # --- receipts (deterministic, recomputed)
    try:
        primal, dual = _receipts(cert)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"receipt recompute failed: {exc}")
        primal = dual = None
    if primal is not None and cert.primal_receipt != primal:
        failures.append("primal_receipt mismatch")
    if dual is not None and cert.dual_receipt != dual:
        failures.append("dual_receipt mismatch")

    return {
        "verified": not failures,
        "failures": failures,
    }
