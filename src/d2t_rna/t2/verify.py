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