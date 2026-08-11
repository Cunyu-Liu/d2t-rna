"""wrappers.helpers -- self-contained separation scores for faithful wrappers.

These are local re-implementations (independent of the production evaluator)
so a wrapper can faithfully reproduce its external method's selection rule
without coupling to ``evaluation.matrix``.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O  # exact channel/law primitives


def action_law(channel, p):
    """Output distribution ``q(y) = sum_w Q[y][w] p[w]`` (Fraction)."""
    return O.action_law(channel, p)


def chernoff_information(q0, q1) -> float:
    """Chernoff information ``C = -log min_{0<=s<=1} sum_y q0^s q1^(1-s)``.

    Faithful to the controlled-sensing / Chernoff-information selection rule.

    Correct handling of disjoint support: if the two laws have disjoint support
    the minimum of ``sum_y q0^s q1^(1-s)`` over ``s in [0,1]`` is ``0``, giving
    Chernoff information ``+infinity`` (perfect, error-free separation).
    Returning ``0.0`` in that case would make a perfectly-separating channel
    look uninformative and mis-rank actions, so we return ``+inf``.
    """
    import math

    def tilde(s: float) -> float:
        return sum(
            (abs(float(a)) ** s) * (abs(float(b)) ** (1.0 - s))
            for a, b in zip(q0, q1)
        )

    best = tilde(0.5)
    best_s = 0.5
    for i in range(0, 101):
        s = i / 100.0
        v = tilde(s)
        if v < best:
            best = v
            best_s = s
    lo = max(0.0, best_s - 0.01)
    hi = min(1.0, best_s + 0.01)
    for _ in range(60):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if tilde(m1) < tilde(m2):
            hi = m2
        else:
            lo = m1
    best = min(best, tilde((lo + hi) / 2.0))
    if best <= 0.0:
        return float("inf")
    return float(-math.log(best))


def hellinger_info(q0, q1) -> float:
    """Hellinger-information score used by the Bayesian-EIG style greedy rule.

    ``I = -log BC`` where ``BC = sum_y sqrt(q0 q1)`` is the Bhattacharyya
    coefficient.  Disjoint support gives ``+infinity`` (perfect separation).
    """
    import math

    bc = sum((float(a) * float(b)) ** 0.5 for a, b in zip(q0, q1))
    if bc <= 0.0:
        return float("inf")
    return float(-math.log(bc))


def per_action_tv(q0, q1) -> Fraction:
    """Total-variation separation ``sum_y |q0-q1|/2`` (Test-Cover score)."""
    return sum(abs(a - b) for a, b in zip(q0, q1)) / Fraction(2)
