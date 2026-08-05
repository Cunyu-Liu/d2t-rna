"""T2-3 exact information quantities with certified numerical error bounds.

The T2c finite-sample theorem (contract section 5.3) is driven by the
Bhattacharyya / Hellinger information per (pair, action, repeat):

    I_{uw} = -log sum_y sqrt( p0uw(y) p1uw(y) )

where ``p0uw(y)`` and ``p1uw(y)`` are the complete categorical observation
laws of the target and rival model under action ``u``.

``sqrt`` and ``log`` are irrational, so the module never claims an exact
rational value for ``I_uw``.  Instead every quantity is returned as a
*closed interval* ``[lo, hi]`` of ``decimal.Decimal`` endpoints computed with
directed rounding (``ROUND_FLOOR`` for the lower bound, ``ROUND_CEILING`` for
the upper bound) at a chosen precision.  Because ``Decimal.sqrt``, ``.ln``
and ``.exp`` are correctly rounded under the active context, the true real
value is guaranteed to lie inside the returned interval.  This satisfies the
contract's "certified numerical error" requirement (contract 5.3 / 10.3):
no floating-point tolerance or caller hash is treated as proof.

Exact rational quantities (total-variation distance, product-law TV for
microcases) are computed with ``fractions.Fraction`` arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, localcontext
from fractions import Fraction
from math import prod
from typing import Sequence

_DEFAULT_PREC = 60


@dataclass(frozen=True)
class Interval:
    """A closed real interval ``[lo, hi]`` with ``lo <= hi``."""

    lo: Decimal
    hi: Decimal

    def __post_init__(self) -> None:
        if self.lo > self.hi:
            raise ValueError(f"empty interval [{self.lo}, {self.hi}]")


def _floor_ctx(prec: int = _DEFAULT_PREC):
    return localcontext() if False else None  # placeholder, not used


def rational_interval(f: Fraction, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified interval for a rational ``f`` (exact rational endpoints).

    We simply keep the exact ``Fraction``; exact endpoints are always inside
    any wider interval, so no rounding loss occurs here.
    """
    return _from_fraction(f, prec)


def _from_fraction(f: Fraction, prec: int) -> Interval:
    num = Decimal(f.numerator)
    den = Decimal(f.denominator)
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        lo = num / den
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        hi = num / den
    return Interval(lo, hi)


def mul_interval(a: Interval, b: Interval, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified product interval (endpoints non-negative in our usage)."""
    # For non-negative factors the product range is [a.lo*b.lo, a.hi*b.hi].
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        lo = a.lo * b.lo
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        hi = a.hi * b.hi
    return Interval(lo, hi)


def sum_intervals(items: Sequence[Interval], prec: int = _DEFAULT_PREC) -> Interval:
    """Certified sum interval via directed rounding."""
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        lo = sum((it.lo for it in items), Decimal(0))
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        hi = sum((it.hi for it in items), Decimal(0))
    return Interval(lo, hi)


def _enlarge(center: Decimal, prec: int) -> Interval:
    """Certified enclosure of a correctly-rounded transcendental.

    ``Decimal.sqrt``/``ln``/``exp`` are correctly rounded to the context
    precision regardless of the rounding mode, so the true real value lies
    within ``0.5 ulp`` of ``center``.  We widen by a relative margin of
    ``10^-(prec-1)`` (>> 0.5 ulp) and round the endpoints outward, giving a
    rigorous ``[lo, hi]`` enclosure.
    """
    margin = abs(center) * Decimal(10) ** (-(prec - 1))
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        lo = center - margin
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        hi = center + margin
    return Interval(lo, hi)


def _sqrt_val(x: Decimal, prec: int) -> Decimal:
    with localcontext() as c:
        c.prec = prec + 20
        return x.sqrt()


def _ln_val(x: Decimal, prec: int) -> Decimal:
    with localcontext() as c:
        c.prec = prec + 20
        return x.ln()


def _exp_val(x: Decimal, prec: int) -> Decimal:
    with localcontext() as c:
        c.prec = prec + 20
        return x.exp()


def sqrt_interval(i: Interval, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified square-root interval for a non-negative interval."""
    lo = _enlarge(_sqrt_val(i.lo, prec), prec).lo
    hi = _enlarge(_sqrt_val(i.hi, prec), prec).hi
    return Interval(lo, hi)


def ln_interval(i: Interval, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified natural-log interval for a positive interval."""
    lo = _enlarge(_ln_val(i.lo, prec), prec).lo
    hi = _enlarge(_ln_val(i.hi, prec), prec).hi
    return Interval(lo, hi)


def exp_interval(i: Interval, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified exp interval."""
    lo = _enlarge(_exp_val(i.lo, prec), prec).lo
    hi = _enlarge(_exp_val(i.hi, prec), prec).hi
    return Interval(lo, hi)


def neg_interval(i: Interval, prec: int = _DEFAULT_PREC) -> Interval:
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        lo = -i.hi
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        hi = -i.lo
    return Interval(lo, hi)


# --------------------------------------------------------------------------
# Bhattacharyya coefficient and Hellinger information
# --------------------------------------------------------------------------

def _check_law(p: Sequence) -> None:
    if not p:
        raise ValueError("law must be non-empty")
    total = Fraction(0)
    for x in p:
        if x < 0 or x > 1:
            raise ValueError("law entries must lie in [0,1]")
        total += x
    if total != 1:
        raise ValueError("law must sum to 1")


def bhattacharyya_coeff_interval(
    p0: Sequence[Fraction],
    p1: Sequence[Fraction],
    prec: int = _DEFAULT_PREC,
) -> Interval:
    """Certified interval for ``BC = sum_y sqrt(p0(y) p1(y))``."""
    _check_law(p0)
    _check_law(p1)
    if len(p0) != len(p1):
        raise ValueError("laws must have equal alphabets")
    terms: list[Interval] = []
    for y in range(len(p0)):
        a = _from_fraction(p0[y], prec)
        b = _from_fraction(p1[y], prec)
        terms.append(sqrt_interval(mul_interval(a, b), prec))
    return sum_intervals(terms, prec)


def hellinger_info_interval(
    p0: Sequence[Fraction],
    p1: Sequence[Fraction],
    prec: int = _DEFAULT_PREC,
) -> Interval:
    """Certified interval for ``I = -log sum_y sqrt(p0(y) p1(y))``.

    ``BC in [L,H]`` gives ``I in [-ln_ceil(H), -ln_floor(L)]``.
    """
    bc = bhattacharyya_coeff_interval(p0, p1, prec)
    # ``Decimal.ln`` is correctly rounded to context precision regardless of the
    # rounding mode, so a naive directed-rounding ``bc.lo.ln()`` / ``bc.hi.ln()``
    # would collapse to a single point.  Use the certified ``ln_interval`` which
    # widens each endpoint by a relative margin >= 0.5 ulp, guaranteeing a
    # rigorous enclosure of ``ln(BC)`` in ``[-ln_hi, -ln_lo]``.  Negation uses
    # ``copy_negate`` (exact, no context rounding) to avoid collapsing the
    # widened interval back to a point.
    ln_bc = ln_interval(bc, prec)
    lo = ln_bc.hi.copy_negate()
    hi = ln_bc.lo.copy_negate()
    return Interval(lo, hi)


def product_law_info_interval(
    per_repeat_infos: Sequence[Interval],
    prec: int = _DEFAULT_PREC,
) -> Interval:
    """Certified interval for the total product-law information.

    ``I_total = sum_intervals(per_repeat_infos)``; if a quantity ``n`` of
    independent repeats of the same action is intended, pass the per-repeat
    interval ``n`` times or scale it separately.
    """
    return sum_intervals(list(per_repeat_infos), prec)


def scale_info_interval(i: Interval, n: int, prec: int = _DEFAULT_PREC) -> Interval:
    """Certified ``n * I`` for an integer repeat count ``n >= 0``."""
    if n < 0:
        raise ValueError("repeat count must be non-negative")
    if n == 0:
        return Interval(Decimal(0), Decimal(0))
    return sum_intervals([i] * n, prec)


# --------------------------------------------------------------------------
# Exact rational TV (for microcase crosscheck / tightness)
# --------------------------------------------------------------------------

def tv(a: Sequence[Fraction], b: Sequence[Fraction]) -> Fraction:
    """Exact total-variation distance ``(1/2) sum_y |a(y)-b(y)|``."""
    return sum((abs(a[y] - b[y]) for y in range(len(a))), Fraction(0)) / Fraction(2)


def product_law(p_law: Sequence[Fraction], n: int) -> tuple[Fraction, ...]:
    """Exact product law of ``n`` i.i.d. draws from a categorical law."""
    if n == 0:
        return (Fraction(1),)  # empty sequence -> probability 1 on one outcome
    base = tuple(p_law)
    # convolution-like: the product law is a multinomial over the alphabet.
    # For tiny microcases we enumerate all outcome counts.
    from itertools import product

    k = len(base)
    counts_to_prob: dict[tuple[int, ...], Fraction] = {(0,) * k: Fraction(1)}
    for _ in range(n):
        nxt: dict[tuple[int, ...], Fraction] = {}
        for counts, pr in counts_to_prob.items():
            for y in range(k):
                new_counts = list(counts)
                new_counts[y] += 1
                key = tuple(new_counts)
                nxt[key] = nxt.get(key, Fraction(0)) + pr * base[y]
        counts_to_prob = nxt
    # order outcomes deterministically by the count vector
    keys = sorted(counts_to_prob)
    return tuple(counts_to_prob[k] for k in keys)


def product_law_tv(p0: Sequence[Fraction], p1: Sequence[Fraction], n: int) -> Fraction:
    """Exact TV between two product laws over ``n`` i.i.d. repeats."""
    return tv(product_law(p0, n), product_law(p1, n))