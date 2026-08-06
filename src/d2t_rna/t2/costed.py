"""T2-4 costed design and no-go corollary (contract sections 5.4 / 7 T2-4).

Given a complete likelihood catalog over a finite registered set of candidate
pairs ``w``, we solve the integer covering problem

    minimize   sum_u c_u n_u
    subject to sum_u n_u I_uw >= tau_w   for all w
               n_u in Z_+                 (integer panel)

where ``c_u`` is the per-repeat cost of action ``u`` and ``I_uw`` is the
per-(action, pair) Hellinger/Bhattacharyya information from T2c.  Only the
registered finite pair catalog is covered; no composite-continuous-class
uniform guarantee is claimed (contract 5.4).

Because ``I_uw = -log sum_y sqrt(p0 p1)`` is generally irrational, the module
accepts a certified *interval* per entry and keeps the two directions rigorous:

* **No-go / lower bound** uses the *upper* info bounds ``I_uw.hi``.  Any
  dual-feasible ``y >= 0`` with ``sum_w y_w I_uw.hi <= c_u`` for all ``u``
  yields ``cost >= tau^T y`` for every feasible design (since ``I_uw.hi >=
  I_uw``), so ``tau^T y`` is a valid lower bound.  When a budget ``B`` is
  given and this lower bound strictly exceeds ``B``, the design class is
  infeasible: a structural no-go certificate (contract 5.4).

* **Achievability / upper bound** uses the *lower* info bounds ``I_uw.lo``.
  An integer ``n`` with ``sum_u n_u I_uw.lo >= tau_w`` is guaranteed feasible
  w.r.t. the true information, so its cost is an achievable upper bound.

The LP relaxation ``min c^T n s.t. A n >= tau, n >= 0`` is solved exactly with
the rational simplex of :mod:`d2t_rna.t2.lp` (slack formulation), which also
recovers the dual certificate ``y``.  For exact-rational microcases the
info_upper == info_lower == exact matrix, so the gap is the genuine
(integer - LP)/LP gap; in the interval case the reported gap is conservative.

All quantities are exact ``fractions.Fraction``.  This produces model-
conditional synthetic certificates only; it cannot authorize any formal
scientific claim (``scientific_claim_authorized=false``).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .lp import solve_lp

Vec = tuple[Fraction, ...]
Matrix = tuple[Vec, ...]


def _ceil_div(a: Fraction, b: Fraction) -> int:
    """Smallest integer ``q`` with ``q * b >= a`` (``b > 0``)."""
    if a <= 0:
        return 0
    q, r = divmod(a, b)
    if r > 0:
        q += 1
    return q


@dataclass(frozen=True)
class CostedDesign:
    """A finite registered costed-design instance.

    ``info_lower[u][w]`` / ``info_upper[u][w]`` are certified lower/upper
    bounds on ``I_uw``; for exact-rational microcases they coincide.
    ``costs[u]`` is ``c_u`` and ``thresholds[w]`` is ``tau_w``.
    """

    action_ids: tuple[str, ...]
    costs: tuple[Fraction, ...]
    pair_ids: tuple[str, ...]
    thresholds: tuple[Fraction, ...]
    info_lower: Matrix  # (rows=actions U, cols=pairs W)
    info_upper: Matrix  # (rows=actions U, cols=pairs W)

    def __post_init__(self) -> None:
        U = len(self.action_ids)
        W = len(self.pair_ids)
        if len(self.costs) != U:
            raise ValueError("costs length must match action_ids")
        if len(self.thresholds) != W:
            raise ValueError("thresholds length must match pair_ids")
        for name, mat in (("info_lower", self.info_lower), ("info_upper", self.info_upper)):
            if len(mat) != U:
                raise ValueError(f"{name} row count must equal action count")
            for u, row in enumerate(mat):
                if len(row) != W:
                    raise ValueError(f"{name}[{u}] column count must equal pair count")
                for x in row:
                    if x < 0:
                        raise ValueError(f"{name}[{u}] entries must be >= 0")
        for c in self.costs:
            if c < 0:
                raise ValueError("costs must be >= 0")
            if c == 0:
                raise ValueError("costs must be > 0 (zero-cost free actions not supported)")
        for t in self.thresholds:
            if t < 0:
                raise ValueError("thresholds must be >= 0")


# --------------------------------------------------------------------------
# Exact LP relaxation + dual certificate
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LpRelaxation:
    """Exact LP-relaxation result for ``min c^T n s.t. A n >= tau, n >= 0``."""

    status: str  # OPTIMAL / INFEASIBLE / UNBOUNDED / FAILED
    objective: Fraction | None
    primal: Vec | None          # n_u
    dual: Vec | None            # y_w  (shadow prices / dual feasible point)
    dual_available: bool


def lp_relax_exact(
    info: Matrix, costs: Sequence[Fraction], thresholds: Sequence[Fraction]
) -> LpRelaxation:
    """Solve the LP relaxation exactly with the rational simplex.

    Standard form ``min c'^T x s.t. M x = tau, x >= 0`` with ``x = (n, s)``
    and ``M[w, u] = info[u][w]``, ``M[w, U + w] = -1`` (slack).  The returned
    dual is the ``y`` of ``max tau^T y s.t. info^T y <= c, y >= 0``.
    """
    U = len(costs)
    W = len(thresholds)
    N = U + W
    M: list[list[Fraction]] = [[Fraction(0) for _ in range(N)] for _ in range(W)]
    for w in range(W):
        for u in range(U):
            M[w][u] = info[u][w]
        M[w][U + w] = Fraction(-1)
    c_prime = [Fraction(0) for _ in range(N)]
    for u in range(U):
        c_prime[u] = costs[u]
    b = list(thresholds)
    res = solve_lp(c_prime, M, b)
    if res.status != "OPTIMAL":
        return LpRelaxation(
            status=res.status,
            objective=res.objective,
            primal=None,
            dual=None,
            dual_available=False,
        )
    primal = tuple(res.primal[u] for u in range(U))
    objective = res.objective
    dual = res.dual
    return LpRelaxation(
        status="OPTIMAL",
        objective=objective,
        primal=primal,
        dual=tuple(dual) if dual is not None else None,
        dual_available=res.dual_available,
    )


# --------------------------------------------------------------------------
# No-go lower bound, achievable integer design, integrality gap
# --------------------------------------------------------------------------

def no_go_lower_bound(cd: CostedDesign) -> Fraction | None:
    """A certified lower bound on the cost of any feasible design.

    Uses the *upper* info bounds, so the LP optimum is a valid lower bound on
    every feasible design's cost (contract 5.4 dual burden lower bound).
    Returns ``None`` when the relaxation is infeasible/unbounded.
    """
    res = lp_relax_exact(cd.info_upper, cd.costs, cd.thresholds)
    return res.objective


def no_go_status(cd: CostedDesign, budget: Fraction) -> tuple[str, Fraction | None]:
    """Sign a no-go certificate when the certified lower bound exceeds budget.

    Returns ``(status, lower_bound)`` where status is ``NO_GO`` when no
    feasible design can stay within ``budget``, ``FEASIBLE`` when the
    achievable design cost is certified within budget, or ``AMBIGUOUS``.
    """
    lb = no_go_lower_bound(cd)
    if lb is None:
        return "INFEASIBLE_OR_UNBOUNDED", lb
    if lb > budget:
        return "NO_GO", lb
    ub_cost, _n = achievable_integer_design(cd)
    if ub_cost is not None and ub_cost <= budget:
        return "FEASIBLE", lb
    return "AMBIGUOUS", lb


def achievable_integer_design(
    cd: CostedDesign,
) -> tuple[Fraction | None, tuple[int, ...] | None]:
    """Exact integer covering optimum using the *lower* info bounds.

    Minimizes ``c^T n`` over ``n in Z_+`` with ``info_lower^T n >= tau`` (rows
    = pairs).  Because it uses the lower bounds, the returned design is
    guaranteed feasible w.r.t. the true information.  Uses branch-and-bound;
    returns ``(cost, n)`` or ``(None, None)`` if infeasible.
    """
    U = len(cd.costs)
    W = len(cd.thresholds)
    info = cd.info_lower
    # Active constraints (tau > 0).
    active = [w for w in range(W) if cd.thresholds[w] > 0]
    if not active:
        return Fraction(0), tuple(0 for _ in range(U))

    # Per-action upper bound: beyond covering the tightest constraint it helps.
    ub: list[int] = []
    for u in range(U):
        m = 0
        for w in active:
            if info[u][w] > 0:
                m = max(m, _ceil_div(cd.thresholds[w], info[u][w]))
        ub.append(m)

    best_cost: Fraction | None = None
    best_n: tuple[int, ...] | None = None
    coverage0 = [Fraction(0) for _ in range(W)]

    def dfs(u: int, n_partial: list[int], cost: Fraction, coverage: list[Fraction]) -> None:
        nonlocal best_cost, best_n
        if best_cost is not None and cost >= best_cost:
            return
        if u == U:
            if all(coverage[w] >= cd.thresholds[w] for w in active):
                best_cost = cost
                best_n = tuple(n_partial)
            return
        row = info[u]
        cu = cd.costs[u]
        for nu in range(0, ub[u] + 1):
            new_cost = cost + cu * nu
            if best_cost is not None and new_cost >= best_cost:
                break
            new_coverage = [coverage[w] + row[w] * nu for w in range(W)]
            dfs(u + 1, n_partial + [nu], new_cost, new_coverage)

    dfs(0, [], Fraction(0), coverage0)
    return best_cost, best_n


def greedy_test_cover_design(
    cd: CostedDesign,
) -> tuple[Fraction | None, tuple[int, ...] | None]:
    """Greedy Test-Cover design cost (baseline for the certificate integer design).

    A widely used heuristic for assay/experiment design is a *greedy Test-Cover*:
    repeatedly add one repeat of the action that yields the largest marginal
    information-per-cost toward the still-unsatisfied pairs, using the certified
    *lower* info bounds (so any greedy design it returns is guaranteed feasible
    w.r.t. the true information, exactly like
    :func:`achievable_integer_design`).  The loop stops when every active pair
    threshold is met.

    ``greedy_cost`` is the total cost ``sum_u c_u n_u`` of that greedy design.
    Comparing ``greedy_cost`` against the optimal integer cost returned by
    :func:`achievable_integer_design` quantifies how much a *certified integer
    design* (T2d) beats the greedy Test-Cover baseline on a heterogeneous
    multi-action, multi-pair instance.  On a single-pair, unit-cost instance the
    two coincide (the best probe dominates any mix); strictly positive
    ``greedy_cost - optimal_cost`` requires heterogeneous pairwise coverage.

    Returns ``(greedy_cost, n)`` or ``(None, None)`` if infeasible (some active
    pair has threshold > 0 but no action provides positive info toward it).
    """
    U = len(cd.costs)
    W = len(cd.thresholds)
    info = cd.info_lower
    active = [w for w in range(W) if cd.thresholds[w] > 0]
    if not active:
        return Fraction(0), tuple(0 for _ in range(U))

    # Fail closed if any active pair is unreachable by every action.
    for w in active:
        if all(info[u][w] <= 0 for u in range(U)):
            return None, None

    n = [0] * U
    coverage = [Fraction(0) for _ in range(W)]
    guard = 1_000_000
    while any(coverage[w] < cd.thresholds[w] for w in active):
        guard -= 1
        if guard <= 0:
            raise RuntimeError("greedy Test-Cover did not terminate")
        best_u = None
        best_marginal = Fraction(-1)
        for u in range(U):
            # Marginal certified info-per-cost toward the still-unsatisfied pairs.
            marginal = Fraction(0)
            for w in active:
                remaining = cd.thresholds[w] - coverage[w]
                if remaining > 0 and info[u][w] > 0:
                    marginal += min(info[u][w], remaining)
            v = marginal / cd.costs[u]
            if v > best_marginal:
                best_marginal = v
                best_u = u
        if best_u is None:
            return None, None
        n[best_u] += 1
        for w in range(W):
            coverage[w] += info[best_u][w]
    cost = sum(cd.costs[u] * n[u] for u in range(U))
    return cost, tuple(n)


def integrality_gap(cd: CostedDesign) -> tuple[Fraction | None, Fraction | None]:
    """Return ``(upper_cost, gap)`` where ``gap = (upper - lower)/lower``.

    ``upper`` is the achievable integer cost (guaranteed feasible), ``lower``
    is the no-go/LP lower bound.  For exact-rational microcases this is the
    genuine integer-vs-LP integrality gap; for interval info it is a
    conservative upper bound on the gap.  ``gap`` is ``None`` when ``lower``
    is not a positive finite value.
    """
    ub_cost, _n = achievable_integer_design(cd)
    lb = no_go_lower_bound(cd)
    if ub_cost is None or lb is None or lb <= 0:
        return ub_cost, None
    gap = (ub_cost - lb) / lb
    return ub_cost, gap