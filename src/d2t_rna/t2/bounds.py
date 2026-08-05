"""T2-3 T2c finite-sample quantitative bounds (contract section 5.3).

Two simple hypotheses ``H0``/``H1`` with complete categorical observation laws
``p0``, ``p1`` are discriminated from ``n`` repeats of a fixed allocation.
The T2c theorem gives *non-asymptotic* bounds driven by the total product-law
Bhattacharyya coefficient ``BC = exp(-I_total)``:

Upper bound (achievability).  The minimax error probability of the best
(possibly randomised) test satisfies

    P_err <= (1/2) BC = (1/2) exp(-I_total).

With a fixed-horizon rule that either decides or abstains, this yields

    wrong-declaration prob   <= (1/2) exp(-I_total),
    correct-declaration prob >= 1 - (1/2) exp(-I_total) - abstention.

Lower bound (no-go / budget consequence).  By Le Cam, ``P_err >= (1/2)(1-TV)``
and ``TV <= sqrt(1-BC^2)``, so achieving a correct-declaration probability of
at least ``kappa`` forces

    I_total >= -(1/2) log(1 - (2*kappa - 1)^2).

If the certified total information is strictly below that threshold, no rule in
the registered design class (fixed-horizon, possible abstention) can reach the
target: a structural no-go / budget lower bound.

All bounds are returned as certified ``Interval`` objects (see
:mod:`d2t_rna.t2.info`); the true value is guaranteed to lie inside the
returned interval.  No floating tolerance or caller hash is treated as proof.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, localcontext
from fractions import Fraction

from .info import Interval, ln_interval

_HALF = Decimal("0.5")


def _exp_floor(x: Decimal, prec: int) -> Decimal:
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_FLOOR
        return x.exp()


def _exp_ceil(x: Decimal, prec: int) -> Decimal:
    with localcontext() as c:
        c.prec = prec
        c.rounding = ROUND_CEILING
        return x.exp()


def wrong_prob_upper_interval(
    total_info: Interval, prec: int = 60
) -> Interval:
    """Certified upper bound on the wrong-declaration probability.

    ``P_err <= (1/2) exp(-I_total)``.  For ``I`` in ``[I_lo, I_hi]`` the true
    error ``(1/2) exp(-I)`` lies in ``[(1/2) exp(-I_hi), (1/2) exp(-I_lo)]``;
    the certified upper edge ``hi`` is the conservative achievability bound we
    assert.
    """
    with localcontext() as c:
        c.prec = prec + 20
        lo = _HALF * _exp_floor(total_info.hi.copy_negate(), prec)
        hi = _HALF * _exp_ceil(total_info.lo.copy_negate(), prec)
    return Interval(lo, hi)


def correct_decl_lower_interval(
    total_info: Interval, prec: int = 60
) -> Interval:
    """Certified lower bound on the correct-declaration probability.

    ``correct >= 1 - (1/2) exp(-I_total)``, worst case at ``I = I_lo``.
    """
    with localcontext() as c:
        c.prec = prec + 20
        worst_err = _HALF * _exp_ceil(total_info.lo.copy_negate(), prec)
        lo = Decimal(1) - worst_err
        hi = Decimal(1)
    return Interval(lo, hi)


def budget_lower_bound_info(
    kappa: Fraction, prec: int = 60
) -> Interval:
    """Certified interval for the minimal total information needed to reach
    correct-declaration probability ``kappa``.

    ``I_req = -(1/2) log(1 - (2*kappa - 1)^2)``, valid for ``kappa in (1/2, 1]``.
    """
    if not (Fraction(1, 2) < kappa <= 1):
        raise ValueError("kappa must lie in (1/2, 1]")
    t = 2 * kappa - 1  # in (0, 1]
    arg = 1 - t * t  # in [0, 1); arg == 0 iff kappa == 1
    if arg == 0:
        # I_req = +infinity: no finite budget can guarantee correct-decl = 1.
        return Interval(Decimal("+Infinity"), Decimal("+Infinity"))
    with localcontext() as c:
        c.prec = prec + 20
        arg_dec = Decimal(arg.numerator) / Decimal(arg.denominator)
    # -log(arg), arg in [0,1): certified via the widened ln_interval.
    ln_arg = ln_interval(Interval(arg_dec, arg_dec), prec)
    with localcontext() as c:
        c.prec = prec + 20
        req_lo = _HALF * ln_arg.hi.copy_negate()
        req_hi = _HALF * ln_arg.lo.copy_negate()
    return Interval(req_lo, req_hi)


class T2cNoGoStatus:
    """Outcome of the no-go comparison (contract 5.3 lower-bound direction)."""

    NO_GO = "NO_GO"
    FEASIBLE = "FEASIBLE"
    AMBIGUOUS = "AMBIGUOUS"


def no_go_status(
    total_info: Interval,
    kappa: Fraction,
    prec: int = 60,
) -> tuple[str, Interval]:
    """Determine whether target ``kappa`` is structurally infeasible.

    Returns ``(status, required_info_interval)`` with status one of
    ``NO_GO`` (``total_info.hi`` strictly below the required lower bound),
    ``FEASIBLE`` (``total_info.lo`` strictly above the required upper bound),
    or ``AMBIGUOUS`` (certified intervals overlap).
    """
    req = budget_lower_bound_info(kappa, prec)
    if req.lo.is_infinite():
        return T2cNoGoStatus.NO_GO, req
    if total_info.hi < req.lo:
        return T2cNoGoStatus.NO_GO, req
    if total_info.lo > req.hi:
        return T2cNoGoStatus.FEASIBLE, req
    return T2cNoGoStatus.AMBIGUOUS, req


def required_repeats(
    per_repeat_info: Interval,
    kappa: Fraction,
    prec: int = 60,
) -> tuple[int, str]:
    """Smallest integer ``n`` of i.i.d. repeats so the certified total
    information ``n * I`` reaches ``kappa`` (or signs ``NO_GO`` if ``I`` is
    certified to be zero).

    Returns ``(n, status)`` where status is ``FEASIBLE`` if a finite ``n``
    suffices and the certified ``n * I`` upper bound clears the required lower
    bound, or ``NO_GO`` if even ``n = 1`` cannot be certified to suffice.
    """
    req = budget_lower_bound_info(kappa, prec)
    if req.lo.is_infinite():
        return 0, T2cNoGoStatus.NO_GO
    if per_repeat_info.hi == 0:
        return 0, T2cNoGoStatus.NO_GO
    # smallest n with n * per_repeat_info.lo > req.hi to be certified FEASIBLE
    n = 1
    while True:
        nu = n * Decimal(per_repeat_info.lo)
        if nu > req.hi:
            return n, T2cNoGoStatus.FEASIBLE
        n += 1
        if n > 1_000_000:
            return 0, T2cNoGoStatus.AMBIGUOUS