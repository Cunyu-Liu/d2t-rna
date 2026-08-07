"""T2-3 exhaustive decision enumeration for microcase crosscheck (contract 5.3).

For discriminating two simple hypotheses ``H0``, ``H1`` with complete laws
``p0``, ``p1`` over an alphabet of size ``k`` from ``n`` i.i.d. repeats, the
exact *equal-prior Bayes average* error is

    P_err_Bayes = (1/2) sum_z min(P0^n(z), P1^n(z)) = (1/2)(1 - TV(P0^n, P1^n)).

This is NOT the minimax error of the optimal (possibly randomised) proper
classifier, which is a distinct quantity obtained from an exact rational LP
(:func:`exact_randomized_minimax_error`).  The two can differ (e.g.
``P0=(1,0)``, ``P1=(1/2,1/2)``, ``n=1``: Bayes average ``1/4`` vs minimax
``1/3``).  The audit document (v7 §3.4) requires the two to be computed and
labelled separately, never conflated.

This module enumerates every distinct outcome-count vector exactly (multinomial
probabilities in ``Fraction``) and returns the exact Bayes average error, the
exact product-law TV, the exact product-law Bhattacharyya coefficient, the
exact randomized minimax error, and the per-hypothesis conditional decision
quantities ``alpha,beta,kappa_0,kappa_1,rho_0,rho_1`` of an explicit
likelihood-ratio rule.

These exact microcase values are compared, in the T2c / decision-semantics
tests, against the certified T2c upper/lower bounds to demonstrate validity
and tightness.

This is deliberately a brute-force oracle: it is only used on tiny alphabets
and tiny ``n``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .info import product_law, tv


def _count_vectors(k: int, n: int):
    """Yield all count vectors ``(c_0,...,c_{k-1})`` with sum ``n``."""
    if k == 1:
        yield (n,)
        return
    if n == 0:
        yield (0,) * k
        return

    def rec(remaining_k, remaining_n, prefix):
        if remaining_k == 1:
            yield tuple(prefix) + (remaining_n,)
            return
        for c in range(remaining_n + 1):
            yield from rec(remaining_k - 1, remaining_n - c, prefix + [c])

    yield from rec(k, n, [])


def _prob_of_counts(p: Sequence[Fraction], counts: tuple[int, ...]) -> Fraction:
    from math import factorial

    k = len(p)
    n = sum(counts)
    coeff = Fraction(factorial(n), 1)
    for c in counts:
        coeff //= Fraction(factorial(c), 1)
    pr = Fraction(1)
    for y in range(k):
        pr *= p[y] ** counts[y]
    return coeff * pr


def exact_bayes_average_error(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact equal-prior Bayes average error ``(1/2) sum_z min(P0^n(z), P1^n(z))``.

    This is the *average* error of the Neyman-Pearson / likelihood-ratio test
    under the equal-prior mixture.  It is **not** the minimax error; see
    :func:`exact_randomized_minimax_error`.
    """
    k = len(p0)
    total = Fraction(0)
    for counts in _count_vectors(k, n):
        a = _prob_of_counts(p0, counts)
        b = _prob_of_counts(p1, counts)
        total += min(a, b)
    return total / Fraction(2)


def exact_randomized_minimax_error(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact minimax error of the optimal randomized proper classifier.

    Over the product observation space (count vectors ``z`` with laws ``P0 = p0^n``,
    ``P1 = p1^n``), the minimax error of a proper (no-abstention) randomized rule
    ``x(z) = P(declare H1 | z)`` is

        min_{x in [0,1]^Z} max( sum_z P0(z) x(z), sum_z P1(z) (1 - x(z)) ).

    This is solved exactly as a rational LP in standard form ``min t`` subject to
    equality constraints via :func:`d2t_rna.t2.lp.solve_lp`.

    This is distinct from :func:`exact_bayes_average_error`.  The audit
    counterexample ``P0=(1,0)``, ``P1=(1/2,1/2)``, ``n=1`` gives Bayes average
    ``1/4`` but true randomized minimax ``1/3``.
    """
    from .lp import solve_lp

    counts_list = list(_count_vectors(len(p0), n))
    m_out = len(counts_list)
    p0v = [_prob_of_counts(p0, c) for c in counts_list]
    p1v = [_prob_of_counts(p1, c) for c in counts_list]

    # Variables layout (all non-negative):
    #   x[t]  = t                 (cost 1)
    #   x[d1_base + j] = d1(z_j)
    #   x[s_base + j]  = slack s_j  (d1_j + s_j = 1)
    #   x[e_idx] = slack e           (sum_z P0(z) d1(z) - t + e = 0)
    #   x[f_idx] = surplus f         (sum_z P1(z) d1(z) + t - f = 1)
    nvar = 2 * m_out + 3
    t_idx = 0
    d1_base = 1
    s_base = 1 + m_out
    e_idx = s_base + m_out
    f_idx = e_idx + 1

    c = [Fraction(0)] * nvar
    c[t_idx] = Fraction(1)

    A: list[list[Fraction]] = []
    b: list[Fraction] = []
    for j in range(m_out):
        row = [Fraction(0)] * nvar
        row[d1_base + j] = Fraction(1)
        row[s_base + j] = Fraction(1)
        A.append(row)
        b.append(Fraction(1))
    row = [Fraction(0)] * nvar
    row[t_idx] = Fraction(-1)
    for j in range(m_out):
        row[d1_base + j] = p0v[j]
    row[e_idx] = Fraction(1)
    A.append(row)
    b.append(Fraction(0))
    row = [Fraction(0)] * nvar
    row[t_idx] = Fraction(1)
    for j in range(m_out):
        row[d1_base + j] = p1v[j]
    row[f_idx] = Fraction(-1)
    A.append(row)
    b.append(Fraction(1))

    res = solve_lp(c, A, b)
    if res.status != "OPTIMAL":
        raise ValueError(f"randomized minimax LP failed: {res.status}")
    return res.objective  # type: ignore[return-value]


@dataclass(frozen=True)
class ConditionalDecision:
    """Per-hypothesis conditional quantities of an explicit decision rule.

    ``alpha``  = P(declare H1 | H0)   (type-I error)
    ``beta``   = P(declare H0 | H1)   (type-II error)
    ``kappa_0``= P(correctly declare H0 | H0)
    ``kappa_1``= P(correctly declare H1 | H1)
    ``rho_0``  = P(abstain | H0)
    ``rho_1``  = P(abstain | H1)

    For every outcome the rule either declares H0, declares H1, or abstains, so
    ``alpha + kappa_0 + rho_0 == 1`` and ``beta + kappa_1 + rho_1 == 1``.
    """

    alpha: Fraction
    beta: Fraction
    kappa_0: Fraction
    kappa_1: Fraction
    rho_0: Fraction
    rho_1: Fraction

    def sums_to_one(self) -> bool:
        return (
            self.alpha + self.kappa_0 + self.rho_0 == 1
            and self.beta + self.kappa_1 + self.rho_1 == 1
        )


def conditional_rule_errors(
    p0: Sequence[Fraction],
    p1: Sequence[Fraction],
    n: int,
    lower: Fraction,
    upper: Fraction,
) -> ConditionalDecision:
    """Per-hypothesis conditional quantities of an explicit likelihood-ratio rule.

    Enumerates every count vector ``z`` and applies the explicit rule:
    declare ``H0`` when ``P1(z)/P0(z) < lower``, declare ``H1`` when
    ``P1(z)/P0(z) > upper``, otherwise abstain.  Returns ``alpha,beta,
    kappa_0,kappa_1,rho_0,rho_1`` computed *separately under each hypothesis*
    (contract requires per-hypothesis endpoints, not a single equal-prior
    average).
    """
    alpha = beta = kappa_0 = kappa_1 = rho_0 = rho_1 = Fraction(0)
    for counts in _count_vectors(len(p0), n):
        a = _prob_of_counts(p0, counts)
        b = _prob_of_counts(p1, counts)
        if a == 0:
            if b > 0:
                # outcome only reachable under H1 -> declare H1
                kappa_1 += b
            continue
        ratio = b / a
        if ratio < lower:
            kappa_0 += a
            beta += b
        elif ratio > upper:
            alpha += a
            kappa_1 += b
        else:
            rho_0 += a
            rho_1 += b
    return ConditionalDecision(alpha, beta, kappa_0, kappa_1, rho_0, rho_1)


def exact_product_law_tv(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact TV between the two product laws (equivalently ``1 - 2*P_err_Bayes``)."""
    return tv(product_law(p0, n), product_law(p1, n))


def exact_product_bhattacharyya(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact product Bhattacharyya coefficient ``BC^n``.

    ``BC = sum_y sqrt(p0(y) p1(y))`` is generally irrational, so this is only
    exact when every ``p0(y) p1(y)`` is a perfect rational square (as in the
    hand-built microcases).
    """
    k = len(p0)
    bc = Fraction(0)
    for y in range(k):
        prod = p0[y] * p1[y]
        root = _rational_sqrt(prod)
        if root is None:
            raise ValueError("not a perfect rational square; cannot be exact")
        bc += root
    return bc ** n


def _rational_sqrt(x: Fraction) -> Fraction | None:
    """Return the exact rational square root of ``x``, or ``None``."""
    if x < 0:
        return None
    num, den = x.numerator, x.denominator
    rn = _int_sqrt(num)
    rd = _int_sqrt(den)
    if rn is None or rd is None:
        return None
    return Fraction(rn, rd)


def _int_sqrt(n: int) -> int | None:
    if n < 0:
        return None
    r = int(n**0.5)
    while r * r > n:
        r -= 1
    while (r + 1) * (r + 1) <= n:
        r += 1
    if r * r == n:
        return r
    return None