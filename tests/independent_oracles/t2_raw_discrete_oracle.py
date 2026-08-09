"""Independent discrete-catalog oracle for D2T-RNA T2b (Batch 2).

This module is a *verification oracle*, deliberately independent of the
production engine.  It MUST NOT import anything from ``d2t_rna.t2.witness``,
``d2t_rna.t2.lp``, ``d2t_rna.t2.theorem``, ``d2t_rna.t2.verify`` or any
production certificate checker.  It rebuilds every quantity from raw
primitives -- distribution normalization, catalog membership, action image,
difference vector, and L1 norm -- using exact ``fractions.Fraction``
arithmetic.  It may use the standard library, ``numpy`` and ``scipy``.

It consumes *raw* sequences (never ``T2FiniteModel`` objects) so it cannot
silently reuse a production helper:

  * ``theta_0`` / ``theta_1`` : sequences of state distributions (Fraction)
  * ``marginal_map``          : the linear-functional rows of ``M``
  * ``channels``              : ``{action_id: [[q(y|w)]]}`` raw channel matrices
  * ``panel``                 : sequence of action ids

It computes the discrete-catalog robust action-image separation
``gamma(S) = inf_{v in D} max_{u in S} ||B_u v||_1`` by enumerating the finite
cross-class difference set ``D`` exactly, and a raw collision witness search.
It also provides an honest confusion-accounting over per-case verdict dicts.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence, TypeAlias

Vec: TypeAlias = tuple[Fraction, ...]


# ---------------------------------------------------------------------------
# raw primitives (rebuilt here, never imported from production)
# ---------------------------------------------------------------------------

def _dot(row: Sequence[Fraction], v: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(row, v)), Fraction(0))


def _l1(v: Sequence[Fraction]) -> Fraction:
    return sum((abs(x) for x in v), Fraction(0))


def _is_distribution(p: Sequence[Fraction]) -> bool:
    if not p:
        return False
    total = Fraction(0)
    for x in p:
        if x < 0 or x > 1:
            return False
        total += x
    return total == 1


def _in_catalog(p: Sequence[Fraction], catalog) -> bool:
    return any(tuple(p) == tuple(q) for q in catalog)


def raw_marginal_of(marginal_map, p: Sequence[Fraction]) -> list:
    """Apply the raw marginal map ``M`` to ``p``."""
    return [_dot(row, p) for row in marginal_map]


def raw_action_image(channel, v: Sequence[Fraction]) -> list:
    """``(B v)[y] = sum_w Q[y][w] v[w]`` from a raw channel matrix."""
    return [_dot(row, v) for row in channel]


def iter_admissible_differences(theta_0, theta_1, marginal_map):
    """Yield ``(p0, p1, v = p1 - p0)`` for every admissible cross-class pair
    with ``M p0 == M p1`` and ``v != 0``.  Raw Fraction arithmetic only."""
    seen: set[bytes] = set()
    for p0 in theta_0:
        m0 = raw_marginal_of(marginal_map, p0)
        for p1 in theta_1:
            if raw_marginal_of(marginal_map, p1) != m0:
                continue
            v = tuple(p1[w] - p0[w] for w in range(len(p0)))
            if all(x == 0 for x in v):
                continue
            key = repr(v).encode("utf-8")
            if key in seen:
                continue
            seen.add(key)
            yield p0, p1, v


def _panel_worst(channels, panel, v) -> Fraction:
    return max(_l1(raw_action_image(channels[u], v)) for u in panel)


# ---------------------------------------------------------------------------
# discrete-catalog oracle queries
# ---------------------------------------------------------------------------

def raw_separation_gamma(
    theta_0, theta_1, marginal_map, channels, panel
) -> Fraction | None:
    """``inf_{v in D} max_{u in S} ||B_u v||_1`` (exact Fraction), or ``None``
    when the discrete difference set ``D`` is empty (vacuous separation)."""
    best: Fraction | None = None
    for _p0, _p1, v in iter_admissible_differences(theta_0, theta_1, marginal_map):
        worst = _panel_worst(channels, panel, v)
        if best is None or worst < best:
            best = worst
    return best


def raw_collision_witness(
    theta_0, theta_1, marginal_map, channels, panel
) -> Vec | None:
    """Return a nonzero admissible ``v`` whose action image is zero under every
    panel action, or ``None`` if no such collision witness exists."""
    for _p0, _p1, v in iter_admissible_differences(theta_0, theta_1, marginal_map):
        if all(all(x == 0 for x in raw_action_image(channels[u], v)) for u in panel):
            return v
    return None


def raw_separation_witness(
    theta_0, theta_1, marginal_map, channels, panel
):
    """Return ``(gamma, p0, p1, v)`` attaining the discrete infimum, or
    ``(None, None, None, None)`` when ``D`` is empty."""
    best_gamma: Fraction | None = None
    best: tuple | None = None
    for p0, p1, v in iter_admissible_differences(theta_0, theta_1, marginal_map):
        worst = _panel_worst(channels, panel, v)
        if best_gamma is None or worst < best_gamma:
            best_gamma = worst
            best = (p0, p1, v)
    if best_gamma is None:
        return None, None, None, None
    p0, p1, v = best
    return best_gamma, p0, p1, v


def raw_registered_admissible_pair(theta_0, theta_1, marginal_map, v):
    """Return a registered ``(p0, p1)`` catalog pair with ``v == p1 - p0`` and
    ``M p0 == M p1``, or ``None`` if none exists."""
    for p0 in theta_0:
        for p1 in theta_1:
            if tuple(p1[i] - p0[i] for i in range(len(p0))) == tuple(v) and (
                raw_marginal_of(marginal_map, p0)
                == raw_marginal_of(marginal_map, p1)
            ):
                return p0, p1
    return None


# ---------------------------------------------------------------------------
# honest confusion accounting
# ---------------------------------------------------------------------------

def oracle_confusion_accounting(verdicts: Sequence[dict]) -> dict:
    """Full confusion accounting over per-case verdict dicts.

    Each verdict dict carries:
      * ``issued``           : production emitted a formal certificate
      * ``positive_claim``   : the issued certificate asserted a positive
                               result (separation gamma>0 or collision gamma=0)
      * ``oracle_positive``  : the independent oracle established a non-vacuous
                               positive result exists
      * ``oracle_disagrees`` : the oracle value conflicts with the positive claim
      * ``eligible``         : the instance is well-posed / eligible for a
                               formal certificate
      * ``declared_no_go``   : production explicitly signalled NO_GO

    This is an *honest* accounting: it reports correct-withholding and
    unsupported counts (not merely "no errors among issued certificates"), so a
    production path that quietly withholds real certificates is exposed through
    ``false_no_go`` / ``incorrect_rejection`` / ``correct_withholding``.
    """
    total = len(verdicts)
    issued = sum(1 for v in verdicts if v["issued"])
    withheld = total - issued
    eligible = sum(1 for v in verdicts if v["eligible"])
    positive = sum(1 for v in verdicts if v["positive_claim"])

    false_certificate = sum(
        1 for v in verdicts
        if v["issued"] and v["positive_claim"]
        and (not v["oracle_positive"] or v["oracle_disagrees"])
    )
    false_no_go = sum(
        1 for v in verdicts
        if not v["issued"] and v["oracle_positive"] and v["declared_no_go"]
    )
    incorrect_rejection = sum(
        1 for v in verdicts
        if not v["issued"] and v["oracle_positive"] and v["eligible"]
    )
    correct_withholding = sum(
        1 for v in verdicts
        if not v["issued"] and not (v["oracle_positive"] and v["eligible"])
    )
    vacuous_count = sum(1 for v in verdicts if not v["oracle_positive"])
    unsupported_count = sum(
        1 for v in verdicts if not (v["oracle_positive"] and v["eligible"])
    )
    coverage = (issued / eligible) if eligible else 0.0

    return {
        "total": total,
        "eligible_count": eligible,
        "issued_count": issued,
        "withheld_count": withheld,
        "positive_count": positive,
        "false_certificate": false_certificate,
        "false_no_go": false_no_go,
        "incorrect_rejection": incorrect_rejection,
        "correct_withholding": correct_withholding,
        "vacuous_count": vacuous_count,
        "unsupported_count": unsupported_count,
        "coverage": coverage,
        "all_issued_agree": false_certificate == 0,
    }
