"""T2-3 T2c finite-sample quantitative bounds (contract section 5.3).

Two simple hypotheses ``H0``/``H1`` with complete categorical observation laws
``p0``, ``p1`` are discriminated from ``n`` repeats of a fixed allocation.
The T2c theorem gives *non-asymptotic* bounds driven by the total product-law
Bhattacharyya coefficient ``BC = exp(-I_total)``:

Upper bound (achievability).  The error probability of the best (possibly
randomised) test satisfies

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

**Feasibility semantics.**  The information threshold above is a *necessary*
condition only.  Crossing it does **not** certify feasibility.  ``FEASIBLE`` is
issued (**P0-4**) only when an explicit decision rule is certified to meet the
target, namely when the certified correct-declaration lower bound
:func:`correct_decl_lower_interval` reaches ``kappa``.  Otherwise the status is
``AMBIGUOUS`` (not ``FEASIBLE``).

All bounds are returned as certified ``Interval`` objects (see
:mod:`d2t_rna.t2.info`); the true value is guaranteed to lie inside the
returned interval.  No floating tolerance or caller hash is treated as proof.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

from .info import Interval, ln_interval, exp_interval, scale_info_interval

_HALF = Decimal("0.5")


def wrong_prob_upper_interval(
    total_info: Interval, prec: int = 60
) -> Interval:
    """Certified upper bound on the wrong-declaration probability.

    ``P_err <= (1/2) exp(-I_total)``.  For ``I`` in ``[I_lo, I_hi]`` the true
    error ``(1/2) exp(-I)`` lies in ``[(1/2) exp(-I_hi), (1/2) exp(-I_lo)]``;
    the certified upper edge ``hi`` is the conservative achievability bound we
    assert.

    ``Decimal.exp`` is correctly rounded regardless of the context rounding
    mode, so naive directed rounding (ROUND_FLOOR/ROUND_CEILING) does *not*
    widen the endpoint and the "upper" bound can fall below the true value.
    We therefore use the certified :func:`exp_interval`, which widens each
    endpoint by a relative margin that dominates 0.5 ulp, guaranteeing a
    rigorous enclosure of ``exp(-I)`` in ``[hi_edge_dn, lo_edge_up]``.
    """
    # I in [I_lo, I_hi]  =>  -I in [-I_hi, -I_lo].
    neg = Interval(total_info.hi.copy_negate(), total_info.lo.copy_negate())
    e = exp_interval(neg, prec)
    with localcontext() as c:
        c.prec = prec
        lo = _HALF * e.lo
        hi = _HALF * e.hi
    return Interval(lo, hi)


def correct_decl_lower_interval(
    total_info: Interval, prec: int = 60
) -> Interval:
    """Certified lower bound on the correct-declaration probability.

    ``correct >= 1 - (1/2) exp(-I_total)``, worst case at ``I = I_lo``.  Uses
    the certified :func:`exp_interval` for the same reason as
    :func:`wrong_prob_upper_interval`.
    """
    with localcontext() as c:
        c.prec = prec
        # worst-case error at -I_lo, upper-bounded conservatively.
        e = exp_interval(
            Interval(total_info.lo.copy_negate(), total_info.lo.copy_negate()),
            prec,
        )
        worst_err = _HALF * e.hi
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
    """Outcome of the no-go / feasibility decision (contract 5.3 lower-bound)."""

    NO_GO = "NO_GO"
    FEASIBLE = "FEASIBLE"
    AMBIGUOUS = "AMBIGUOUS"


def no_go_status(
    total_info: Interval,
    kappa: Fraction,
    prec: int = 60,
) -> tuple[str, Interval]:
    """Determine whether target ``kappa`` is structurally infeasible or is
    certified feasible by an explicit rule.

    Returns ``(status, required_info_interval)`` with status one of:

    * ``NO_GO`` -- ``total_info.hi`` is strictly below the *necessary* lower
      bound ``I_req``; no rule in the registered design class can reach
      ``kappa``.  (No-go uses the certified *upper* information bound.)
    * ``FEASIBLE`` -- an **explicit** decision rule is certified to reach
      ``kappa``: the correct-declaration lower bound
      :func:`correct_decl_lower_interval` is at least ``kappa``.  (P0-4:
      feasibility is only ever issued by an explicit rule, never merely by
      crossing the necessary information threshold.)
    * ``AMBIGUOUS`` -- the certified intervals leave the target undecided.
    """
    req = budget_lower_bound_info(kappa, prec)
    if req.lo.is_infinite():
        return T2cNoGoStatus.NO_GO, req
    if total_info.hi < req.lo:
        return T2cNoGoStatus.NO_GO, req
    # FEASIBLE only via an explicit achievability rule (not threshold crossing).
    cd = correct_decl_lower_interval(total_info, prec)
    kappa_dec = Decimal(kappa.numerator) / Decimal(kappa.denominator)
    if cd.lo >= kappa_dec:
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
    suffices and the certified ``n * I`` reaches the target via the explicit
    achievability rule, or ``NO_GO`` if even ``n = 1`` cannot be certified to
    suffice.
    """
    req = budget_lower_bound_info(kappa, prec)
    if req.lo.is_infinite():
        return 0, T2cNoGoStatus.NO_GO
    if per_repeat_info.hi == 0:
        return 0, T2cNoGoStatus.NO_GO
    # smallest n with the explicit correct-declaration lower bound >= kappa
    n = 1
    while True:
        info_n = scale_info_interval(per_repeat_info, n, prec)
        cd = correct_decl_lower_interval(info_n, prec)
        kappa_dec = Decimal(kappa.numerator) / Decimal(kappa.denominator)
        if cd.lo >= kappa_dec:
            return n, T2cNoGoStatus.FEASIBLE
        n += 1
        if n > 1_000_000:
            return 0, T2cNoGoStatus.AMBIGUOUS
# ---------------------------------------------------------------------------
# K8 (plan Batch 2.7): an information bound is NOT constructive feasibility.
#
# A T2c information bound (total_info / kappa) is only ever a *necessary*
# condition.  Crossing it does not certify feasibility.  We therefore expose a
# distinct, explicit constructive-feasibility gate whose only positive status
# is CONSTRUCTIVELY_FEASIBLE, returned only when ALL of the following are
# registered and independently verified:
#
#   * complete registered product laws;
#   * allocation;
#   * decision/abstention rule;
#   * per-hypothesis exact risk (alpha / beta);
#   * independent verification of alpha / beta;
#   * all budget and cost constraints verified.
#
# When only an information bound is available (no rule, or a rule whose risk is
# not certified), the returned status is one of BOUND_ONLY / BOUND_NOT_DECISIVE /
# NOT_ESTABLISHED -- never a generic FEASIBLE.  The marker constant
# K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY is attached to every result to
# make the distinction explicit and machine-checkable.
# ---------------------------------------------------------------------------

from dataclasses import dataclass

K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY = (
    "K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY"
)


class T2cConstructiveStatus:
    NO_GO = "NO_GO"
    BOUND_ONLY = "BOUND_ONLY"
    BOUND_NOT_DECISIVE = "BOUND_NOT_DECISIVE"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    CONSTRUCTIVELY_FEASIBLE = "CONSTRUCTIVELY_FEASIBLE"


@dataclass(frozen=True)
class ConstructiveFeasibility:
    """K8 outcome: whether a registered design is *constructively* feasible."""

    status: str
    marker: str = K8_T2C_BOUND_IS_NOT_CONSTRUCTIVE_FEASIBILITY
    reasons: tuple[str, ...] = ()
    alpha: Fraction | None = None
    beta: Fraction | None = None
    alpha_max: Fraction | None = None
    beta_max: Fraction | None = None


def constructive_feasibility_status(
    *,
    product_laws_registered: bool,
    allocation_registered: bool,
    decision_rule_registered: bool,
    budget_cost_verified: bool,
    alpha: Fraction | None = None,
    beta: Fraction | None = None,
    alpha_max: Fraction | None = None,
    beta_max: Fraction | None = None,
) -> ConstructiveFeasibility:
    """K8 constructive-feasibility gate (never conflates a bound with a design).

    Returns a :class:`ConstructiveFeasibility`.  The only positive status is
    ``CONSTRUCTIVELY_FEASIBLE``; every other status is a bound-only / not-decisive /
    not-established outcome and carries the K8 marker constant.
    """
    reasons: list[str] = []

    if not product_laws_registered or not allocation_registered:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.NOT_ESTABLISHED,
            reasons=(
                "no complete registered product laws / allocation; "
                "observation model not established",
            ),
        )

    if not decision_rule_registered:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.BOUND_ONLY,
            reasons=(
                "information bound present but no explicit decision/abstention "
                "rule registered; bound is not constructive feasibility",
            ),
        )

    if alpha is None or beta is None:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.BOUND_NOT_DECISIVE,
            reasons=(
                "a candidate rule exists but its per-hypothesis risk "
                "(alpha/beta) is not certified",
            ),
        )

    if alpha_max is not None and alpha > alpha_max:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.BOUND_NOT_DECISIVE,
            reasons=(f"candidate rule alpha={alpha} exceeds alpha_max={alpha_max}",),
            alpha=alpha,
            alpha_max=alpha_max,
        )

    if beta_max is not None and beta > beta_max:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.BOUND_NOT_DECISIVE,
            reasons=(f"candidate rule beta={beta} exceeds beta_max={beta_max}",),
            beta=beta,
            beta_max=beta_max,
        )

    if not budget_cost_verified:
        return ConstructiveFeasibility(
            status=T2cConstructiveStatus.NO_GO,
            reasons=(
                "candidate rule meets risk targets but budget/cost constraints "
                "are not verified; cannot certify constructive feasibility",
            ),
        )

    return ConstructiveFeasibility(
        status=T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE,
        reasons=(
            "complete rule with certified per-hypothesis risk and verified "
            "budget/cost constraints",
        ),
        alpha=alpha,
        beta=beta,
    )
