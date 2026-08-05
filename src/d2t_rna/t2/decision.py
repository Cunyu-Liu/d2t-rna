"""T2-3 exhaustive decision enumeration for microcase crosscheck (contract 5.3).

For discriminating two simple hypotheses ``H0``, ``H1`` with complete laws
``p0``, ``p1`` over an alphabet of size ``k`` from ``n`` i.i.d. repeats, the
optimal (minimax) test is the likelihood-ratio test.  Its *exact* error
probability is

    P_err = (1/2) sum_z min(P0^n(z), P1^n(z)) = (1/2)(1 - TV(P0^n, P1^n)).

This module enumerates every distinct outcome-count vector exactly (multinomial
probabilities in ``Fraction``) and returns the exact minimax error, the exact
product-law TV, and the exact product-law Bhattacharyya coefficient.  These
exact microcase values are compared, in the T2c tests, against the certified
T2c upper/lower bounds to demonstrate validity and tightness.

This is deliberately a brute-force oracle: it is only used on tiny alphabets
and tiny ``n``.
"""

from __future__ import annotations

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


def exact_minimax_error(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact minimax error ``(1/2) sum_z min(P0^n(z), P1^n(z))``."""
    k = len(p0)
    total = Fraction(0)
    for counts in _count_vectors(k, n):
        a = _prob_of_counts(p0, counts)
        b = _prob_of_counts(p1, counts)
        total += min(a, b)
    return total / Fraction(2)


def exact_product_law_tv(
    p0: Sequence[Fraction], p1: Sequence[Fraction], n: int
) -> Fraction:
    """Exact TV between the two product laws (equivalently ``1 - 2*P_err``)."""
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