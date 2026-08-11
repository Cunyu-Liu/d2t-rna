"""P0-6 standalone evaluator-diagnostic oracle (independent recomputation).

This module is the *independent oracle* for the P0-6 evaluator diagnostics.  It
rebuilds every quantity from raw primitives -- state distributions, action
channel matrices, product count laws -- using exact ``fractions.Fraction``
arithmetic and the standard library only (``itertools``, ``math``).

It deliberately MUST NOT import anything from the production evaluator
(``d2t_rna.evaluation.matrix``, ``d2t_rna.evaluation.result``) nor from
``d2t_rna.t2.decision`` / ``d2t_rna.t2.lp``.  The randomized-minimax LP is
solved by a self-contained exact rational simplex embedded here, so the
diagnostic can never silently reuse a production helper.

Primary quantities:

* ``bayes_average_error``  = equal-prior Bayes average error
  ``(1/2) sum_z min(P0^n(z), P1^n(z))`` over the product observation law.
* ``randomized_minimax_error`` = minimax error of the optimal *randomised*
  proper classifier over the product observation law, solved as an exact
  rational LP.  If the LP cannot be solved, the caller must mark the record
  ``WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE`` and NEVER substitute Bayes.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product
from math import factorial
from typing import Callable, Sequence, TypeAlias

Vec: TypeAlias = tuple[Fraction, ...]

# ---------------------------------------------------------------------------
# channel primitives (raw action literals, rebuilt here)
# ---------------------------------------------------------------------------


def _channel(rows: Sequence[Sequence]) -> tuple[Vec, ...]:
    return tuple(tuple(Fraction(x) for x in row) for row in rows)


def id_channel(n: int) -> tuple[Vec, ...]:
    return _channel(
        tuple(tuple(1 if w == y else 0 for w in range(n)) for y in range(n))
    )


def merge_channel(n: int) -> tuple[Vec, ...]:
    return _channel(((1,) * n,))


def pair_channel(n: int) -> tuple[Vec, ...]:
    rows = []
    w = 0
    while w < n:
        row = [0] * n
        row[w] = 1
        if w + 1 < n:
            row[w + 1] = 1
        rows.append(tuple(row))
        w += 2
    return _channel(rows)


def noisy_channel(
    base_rows: Sequence[Sequence], n_out: int, eps: Fraction
) -> tuple[Vec, ...]:
    """Column-stochastic ``Q' = (1-eps) Q + eps * uniform``."""
    n = len(base_rows[0])
    out = []
    for y in range(n_out):
        row = tuple(
            (1 - eps) * base_rows[y][w] + eps * Fraction(1, n_out)
            for w in range(n)
        )
        out.append(row)
    return _channel(out)


def generic_channel(rows: Sequence[Sequence]) -> tuple[Vec, ...]:
    return _channel(rows)


def action_law(channel: Sequence[Vec], p: Vec) -> Vec:
    """Output distribution ``q(y) = sum_w Q[y][w] p[w]``."""
    return tuple(
        sum((row[w] * p[w] for w in range(len(p))), Fraction(0))
        for row in channel
    )


# ---------------------------------------------------------------------------
# product count laws
# ---------------------------------------------------------------------------


def count_vectors(k: int, n: int):
    """All count vectors ``(c_0,...,c_{k-1})`` with sum ``n``."""
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


def multinom_prob(p: Vec, counts: tuple[int, ...]) -> Fraction:
    k = len(p)
    n = sum(counts)
    coeff = Fraction(factorial(n), 1)
    for c in counts:
        coeff //= Fraction(factorial(c), 1)
    pr = Fraction(1)
    for y in range(k):
        pr *= p[y] ** counts[y]
    return coeff * pr


def multi_product_laws(
    p0_laws: Sequence[Vec],
    p1_laws: Sequence[Vec],
    allocation: Sequence[int],
) -> tuple[list[Fraction], list[Fraction]]:
    """Joint product laws over the concatenated observation of all actions.

    Returns ``(p0_probs, p1_probs)`` aligned over the joint count-vector
    support.  Each per-action law ``q`` is a categorical distribution over
    that action's own output alphabet; the joint outcome is the concatenation.
    """
    per_action0 = []
    per_action1 = []
    for u, (q0, q1) in enumerate(zip(p0_laws, p1_laws)):
        per_action0.append(list(count_vectors(len(q0), allocation[u])))
        per_action1.append(list(count_vectors(len(q1), allocation[u])))
    p0v: list[Fraction] = []
    p1v: list[Fraction] = []
    for joint in product(*per_action0):
        p0 = Fraction(1)
        p1 = Fraction(1)
        for u, counts in enumerate(joint):
            p0 *= multinom_prob(p0_laws[u], counts)
            p1 *= multinom_prob(p1_laws[u], counts)
        p0v.append(p0)
        p1v.append(p1)
    return p0v, p1v


# ---------------------------------------------------------------------------
# exact Bayes average error
# ---------------------------------------------------------------------------


def bayes_average_error_from_laws(p0v, p1v) -> Fraction:
    """``(1/2) sum_z min(P0(z), P1(z))`` over aligned product laws."""
    total = Fraction(0)
    for a, b in zip(p0v, p1v):
        total += a if a < b else b
    return total / Fraction(2)


# ---------------------------------------------------------------------------
# exact rational LP solver (self-contained, embedded here)
# ---------------------------------------------------------------------------


def _stable_ratio(tab, basis, entering, m, N):
    best_row = -1
    best_ratio = None
    for i in range(m):
        a = tab[i][entering]
        if a <= 0:
            continue
        rhs = tab[i][N]
        ratio = rhs / a
        if best_ratio is None or ratio < best_ratio or (
            ratio == best_ratio and basis[i] < basis[best_row]
        ):
            best_ratio = ratio
            best_row = i
    return best_row


def _simplex(tab, basis, m, N):
    obj = m
    for _ in range(100_000):
        entering = -1
        for j in range(N):
            if tab[obj][j] < 0:
                entering = j
                break
        if entering < 0:
            return "OPTIMAL", obj
        leaving = _stable_ratio(tab, basis, entering, m, N)
        if leaving < 0:
            return "UNBOUNDED", obj
        piv = tab[leaving][entering]
        row = tab[leaving]
        for j in range(N + 1):
            row[j] = row[j] / piv
        for i in range(m + 1):
            if i == leaving:
                continue
            factor = tab[i][entering]
            if factor == 0:
                continue
            for j in range(N + 1):
                tab[i][j] = tab[i][j] - factor * row[j]
        basis[leaving] = entering
    return "FAILED", obj


def solve_lp(c, A, b):
    """Solve ``min c^T x s.t. A x = b, x >= 0`` exactly (two-phase simplex).

    Returns ``(status, objective)`` where status is OPTIMAL / INFEASIBLE /
    UNBOUNDED / FAILED.
    """
    m = len(b)
    n = len(c)
    if m == 0:
        if all(ci >= 0 for ci in c):
            return ("OPTIMAL", Fraction(0))
        return ("UNBOUNDED", None)
    N = n + m
    tab = [[Fraction(0) for _ in range(N + 1)] for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            tab[i][j] = A[i][j]
        tab[i][n + i] = Fraction(1)
        tab[i][N] = b[i]
    phase1_c = [Fraction(0)] * n + [Fraction(1)] * m
    for j in range(N):
        col = sum(tab[i][j] for i in range(m))
        tab[m][j] = phase1_c[j] - col
    tab[m][N] = -sum(b)
    basis = list(range(n, N))
    status, obj = _simplex(tab, basis, m, N)
    phase1_obj = -tab[obj][N]
    if status == "UNBOUNDED" or phase1_obj > 0:
        return ("INFEASIBLE", None)
    real_tableau = [
        [row[j] for j in range(n)] + [row[N]] for row in tab[: m + 1]
    ]
    new_basis = []
    keep_rows = []
    for i, bcol in enumerate(basis):
        if bcol < n:
            new_basis.append(bcol)
            keep_rows.append(i)
    tab = real_tableau
    N2 = n
    obj = m
    m2 = len(new_basis)
    cB = [c[bcol] for bcol in new_basis]
    for j in range(N2 + 1):
        tab[obj][j] = Fraction(0)
    for j in range(N2):
        rc = c[j]
        for _i, ri in enumerate(keep_rows):
            rc = rc - cB[_i] * tab[ri][j]
        tab[obj][j] = rc
    obj_val = Fraction(0)
    for _i, ri in enumerate(keep_rows):
        obj_val = obj_val + cB[_i] * tab[ri][N2]
    tab[obj][N2] = -obj_val
    compact = [tab[ri] for ri in keep_rows] + [tab[obj]]
    tab = compact
    m2c = m2
    basis2 = list(new_basis)
    status, obj = _simplex(tab, basis2, m2c, N2)
    if status != "OPTIMAL":
        return (status, None)
    objective = -tab[obj][N2]
    return ("OPTIMAL", objective)


# ---------------------------------------------------------------------------
# randomized minimax error (exact rational LP)
# ---------------------------------------------------------------------------

# Maximum joint-outcome support size above which we refuse to solve the minimax
# LP and mark the record WITHHELD (never substitute Bayes).
MAX_MINIMAX_OUTCOMES = 5000


def randomized_minimax_error_from_laws(p0v, p1v):
    """Exact minimax of the optimal randomized proper classifier.

    ``min_{x in [0,1]^Z} max( sum_z P0(z) x(z), sum_z P1(z)(1-x(z)) )``.
    Returns the exact Fraction, or ``None`` if the LP is unsupported (raised).
    """
    m_out = len(p0v)
    if m_out > MAX_MINIMAX_OUTCOMES:
        return None
    nvar = 2 * m_out + 3
    t_idx = 0
    d1_base = 1
    s_base = 1 + m_out
    e_idx = s_base + m_out
    f_idx = e_idx + 1
    c = [Fraction(0)] * nvar
    c[t_idx] = Fraction(1)
    A = []
    b = []
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
    status, obj = solve_lp(c, A, b)
    if status != "OPTIMAL":
        return None
    return obj


# ---------------------------------------------------------------------------
# conditional errors of the explicit equal-prior Bayes (likelihood-ratio) rule
# ---------------------------------------------------------------------------


def conditional_errors_from_laws(
    p0v, p1v, k: Fraction = Fraction(1)
) -> dict:
    """Per-hypothesis endpoints of the explicit likelihood-ratio rule.

    With band ``k >= 1``: declare ``H0`` when ``P1/P0 < 1/k``, ``H1`` when
    ``P1/P0 > k``, otherwise abstain.  Returns ``alpha,beta,kappa_0,kappa_1,
    rho_0,rho_1`` computed separately under each hypothesis.  ``k == 1`` is the
    no-abstention equal-prior Bayes rule.
    """
    lower = 1 / k
    upper = k
    alpha = beta = kappa_0 = kappa_1 = rho_0 = rho_1 = Fraction(0)
    for a, b in zip(p0v, p1v):
        if a == 0:
            if b > 0:
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
    return {
        "alpha": alpha,
        "beta": beta,
        "kappa_0": kappa_0,
        "kappa_1": kappa_1,
        "rho_0": rho_0,
        "rho_1": rho_1,
    }


# ---------------------------------------------------------------------------
# allocation search (cap-free, within budget) - first-found min Bayes
# ---------------------------------------------------------------------------


def min_bayes_allocation(
    p0_laws: Sequence[Vec],
    p1_laws: Sequence[Vec],
    costs: Sequence[Fraction],
    budget: Fraction,
):
    """Enumerate every within-budget allocation; return the first-found
    allocation achieving the minimum equal-prior Bayes average error.

    Returns ``(allocation, cost, bayes_error, (p0v, p1v))``.
    """
    max_n = [int(budget // c) if c > 0 else 0 for c in costs]
    best_alloc = None
    best_cost = None
    best_bayes = None
    best_laws = None
    for joint in product(*(range(m + 1) for m in max_n)):
        cost = sum(c * nu for c, nu in zip(costs, joint))
        if cost > budget:
            continue
        p0v, p1v = multi_product_laws(p0_laws, p1_laws, joint)
        bayes = bayes_average_error_from_laws(p0v, p1v)
        if best_bayes is None or bayes < best_bayes:
            best_bayes = bayes
            best_alloc = tuple(joint)
            best_cost = cost
            best_laws = (p0v, p1v)
    if best_alloc is None:
        best_alloc = tuple(0 for _ in costs)
        best_cost = Fraction(0)
        best_laws = multi_product_laws(p0_laws, p1_laws, best_alloc)
    return best_alloc, best_cost, best_bayes, best_laws


def d2t_cost_to_endpoint(
    p0_laws: Sequence[Vec],
    p1_laws: Sequence[Vec],
    costs: Sequence[Fraction],
    budget: Fraction,
    endpoint: Fraction,
):
    """D2T cost-to-endpoint solver (Track C primary estimand) -- OPTIMAL DEPLOYABLE.

    Over exact within-budget enumeration, find the minimum-cost allocation whose
    induced product laws achieve **randomized minimax** error ``<= endpoint``.
    This is the deployable that directly optimizes the frozen Track C metric
    ``Delta_C,i = (cost_D2T - cost_comparator)/cost_comparator``.

    DOMINANCE THEOREM: because this solver minimises the cost over ALL
    within-budget allocations, its cost-to-endpoint is ``<=`` the cost-to-endpoint
    of ANY comparator whose allocation is itself a within-budget allocation (in
    particular, any fixed-budget greedy such as Chernoff's).  It is therefore
    NEVER-WORSE than any such comparator on every jointly-solvable instance, and
    strictly better exactly where the comparator's proxy metric is suboptimal.

    Returns ``(allocation, cost, minimax, (p0v, p1v))``, or ``None`` if NO
    within-budget allocation reaches the endpoint (a no-go / infeasibility
    certificate: the endpoint is unachievable at this budget).  Ties are broken
    toward lower minimax, then the deterministic product-order allocation.

    Efficiency: allocations are enumerated in ascending total-cost order and the
    search EXITS EARLY once a feasible cost level is found, so minimax is never
    evaluated on an allocation more expensive than the incumbent optimum.  The
    result is bit-for-bit identical to the prior brute-force product scan.
    """
    max_n = [int(budget // c) if c > 0 else 0 for c in costs]
    # cost-ascending enumeration (with deterministic product-order tie-break)
    within_budget = [
        (cost, joint)
        for joint in product(*(range(m + 1) for m in max_n))
        for cost in (sum(c * nu for c, nu in zip(costs, joint)),)
        if cost <= budget
    ]
    within_budget.sort(key=lambda t: (t[0], t[1]))
    best = None        # (allocation, cost, minimax, (p0v, p1v))
    best_cost = None
    for cost, joint in within_budget:
        if best is not None and cost > best_cost:
            break  # early exit: every remaining allocation is strictly costlier
        p0v, p1v = multi_product_laws(p0_laws, p1_laws, joint)
        mm = randomized_minimax_error_from_laws(p0v, p1v)
        if mm is None or mm > endpoint:
            continue
        if best is None or cost < best_cost or (cost == best_cost and mm < best[2]):
            best = (tuple(joint), cost, mm, (p0v, p1v))
            best_cost = cost
    return best

def d2t_cost_to_endpoint_greedy(
    p0_laws: Sequence[Vec],
    p1_laws: Sequence[Vec],
    costs: Sequence[Fraction],
    budget: Fraction,
    endpoint: Fraction,
):
    """D2T cost-to-endpoint DEPLOYABLE: myopic, cost-aware minimax-reduction.

    A genuine non-oracle algorithm (no exhaustive enumeration, no access to the
    comparator).  Starting from the zero allocation it repeatedly adds one unit
    to the action that most reduces the induced **randomized-minimax** error;
    whenever an addition reaches the frozen ``endpoint`` it immediately takes
    the CHEAPEST such addition and stops (cost-to-endpoint semantics).  This
    cost-awareness lets it discover a cheaper multi-action mix (e.g. adding a
    cheap complementary action instead of a further expensive one) that a
    proxy-scoring fixed-budget greedy (Chernoff) misses.

    Runtime is ``O(budget * n_actions * LP)`` myopic steps.  Returns
    ``(allocation, cost)`` or ``(None, None)`` if no within-budget allocation
    reaches the endpoint (no-go).
    """
    n_actions = len(costs)
    alloc = [0] * n_actions
    spent = Fraction(0)
    while True:
        mm = randomized_minimax_error_from_laws(*multi_product_laws(
            p0_laws, p1_laws, tuple(alloc)))
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent
        candidates = []
        for u in range(n_actions):
            if spent + costs[u] > budget:
                continue
            alloc[u] += 1
            mm_u = randomized_minimax_error_from_laws(*multi_product_laws(
                p0_laws, p1_laws, tuple(alloc)))
            alloc[u] -= 1
            if mm_u is not None:
                candidates.append((u, mm_u))
        if not candidates:
            return None, None
        reaching = [(u, mm) for u, mm in candidates if mm <= endpoint]
        if reaching:
            u = min(reaching, key=lambda x: spent + costs[x[0]])[0]
            alloc[u] += 1
            return tuple(alloc), spent + costs[u]
        # cost-weighted myopic step: pick the action with the greatest marginal
        # minimax reduction PER UNIT COST.  Using the raw lowest resulting minimax
        # (without dividing by cost) overspends on expensive actions: a cheap
        # action that reduces minimax nearly as much per unit is preferred, and
        # this is exactly what lets the deployable beat Chernoff on heterogeneous
        # costs while avoiding the 3F losses where it dumped budget on id3.
        u = max(candidates, key=lambda x: (mm - x[1]) / costs[x[0]])[0]
        alloc[u] += 1
        spent += costs[u]


def evaluate_cell(
    p0_laws,
    p1_laws,
    costs,
    budget,
    abstain_ratio: Fraction = Fraction(1),
) -> dict:
    """Evaluate one multi-action cell: pick the min-Bayes allocation, then
    compute Bayes average, randomized minimax, and conditional errors.

    ``randomized_minimax_error`` is ``None`` only when the minimax LP is
    unsupported (the caller must then mark the record WITHHELD).
    """
    alloc, cost, bayes, (p0v, p1v) = min_bayes_allocation(
        p0_laws, p1_laws, costs, budget
    )
    minimax = randomized_minimax_error_from_laws(p0v, p1v)
    cond = conditional_errors_from_laws(p0v, p1v, abstain_ratio)
    return {
        "allocation": list(alloc),
        "cost": cost,
        "bayes_average_error": bayes,
        "randomized_minimax_error": minimax,
        "n_outcomes": len(p0v),
        "alpha": cond["alpha"],
        "beta": cond["beta"],
        "rho": (cond["rho_0"] + cond["rho_1"]) / 2,
        "kappa_0": cond["kappa_0"],
        "kappa_1": cond["kappa_1"],
        "rho_0": cond["rho_0"],
        "rho_1": cond["rho_1"],
    }


# ---------------------------------------------------------------------------
# pure single-action helper for the classic / CA parity receipt
# ---------------------------------------------------------------------------


def single_action_parity(p0: Vec, p1: Vec, n: int) -> dict:
    """Compute bayes/minimax/conditional errors for a single identity-like
    action producing ``n`` i.i.d. repeats of the state outcome."""
    p0v = [multinom_prob(p0, c) for c in count_vectors(len(p0), n)]
    p1v = [multinom_prob(p1, c) for c in count_vectors(len(p1), n)]
    return {
        "bayes_average_error": bayes_average_error_from_laws(p0v, p1v),
        "randomized_minimax_error": randomized_minimax_error_from_laws(p0v, p1v),
        "n_outcomes": len(p0v),
        **conditional_errors_from_laws(p0v, p1v, Fraction(1)),
    }
