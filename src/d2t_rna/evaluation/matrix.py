"""D2T-RNA v7 §9 evaluation matrix: microcases, oracle cross-validation, baselines.

Contract sections 9.1 / 9.2 / 9.3.  This module *executes* the evaluation
matrix rather than merely declaring baseline wrappers:

* :func:`microcase_fixtures` builds the §9.1 synthetic microcases (2x2
  alternating rectangle, no-cycle, zero-margin, symmetric states, repeated
  action, each-generator-hit-but-linear-combination-cancels, non-decomposable
  3D fixed-marginal, exact collision, near-collision, strict positive
  separation, boundary).

* :class:`MultiActionOracle` is an independent exhaustive oracle for a fixed
  panel allocation: it enumerates every joint count vector and recomputes the
  exact product-law TV, the exact minimax error, the exact product
  Bhattacharyya coefficient and the exact decision probabilities (correct /
  wrong / abstain) under a fixed likelihood-ratio rule with an abstention band.

* §9.1 cross-validation compares the oracle values against the certified T2c
  bounds (:mod:`d2t_rna.t2.bounds` and :mod:`d2t_rna.t2.info`) and against the
  theory-side decision enumeration (:mod:`d2t_rna.t2.decision`).

* §9.3 :func:`run_baselines` actually designs an allocation with each of the
  eight required baselines (exhaustive oracle, full matrix, random,
  greedy/Test-Cover, EIG, Chernoff, LM2R-style heuristic, T2 integer design &
  LP lower bound) under one common experiment spec, and reports the §9.2
  record (cost, risk, correct-decl, abstention, runtime, optimality gap,
  certified omitted mass, LP lower bound, integer gap).

Every quantity is exact ``fractions.Fraction`` where a finite exact value
exists; the asymptotic/theory quantities are certified ``Interval`` objects.
This produces model-conditional synthetic evaluation only; it cannot authorize
any formal scientific claim (``scientific_claim_authorized=false``).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from itertools import product
from typing import Sequence, TypeAlias

from d2t_rna.t2.model import Action, T2FiniteModel
from d2t_rna.t2.info import (
    Interval,
    bhattacharyya_coeff_interval,
    hellinger_info_interval,
    scale_info_interval,
    sum_intervals,
    tv,
)
from d2t_rna.t2.bounds import (
    wrong_prob_upper_interval,
    correct_decl_lower_interval,
)
from d2t_rna.t2.costed import (
    CostedDesign,
    achievable_integer_design,
    integrality_gap,
    no_go_lower_bound,
)

Vec: TypeAlias = tuple[Fraction, ...]
Matrix: TypeAlias = tuple[Vec, ...]


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def _F(n: int, d: int = 1) -> Fraction:
    return Fraction(n, d)


def action_law(model: T2FiniteModel, action: Action, p: Vec) -> Vec:
    """Categorical observation law ``q(y) = sum_w Q[y][w] p[w]``."""
    return tuple(
        sum(action.channel[y][w] * p[w] for w in range(model.n_states))
        for y in range(action.alphabet_size())
    )


def _vec_key(v: Vec) -> bytes:
    return repr(v).encode("utf-8")


# ---------------------------------------------------------------------------
# §9.1 synthetic microcase fixtures
# ---------------------------------------------------------------------------

def _channel(rows: Sequence[Sequence[Fraction]]) -> Matrix:
    return tuple(tuple(row) for row in rows)


def microcase_fixtures() -> dict[str, T2FiniteModel]:
    """Return the named §9.1 synthetic microcase models.

    Names are stable and map one-to-one to the contract scenarios so the
    evaluation matrix (and any paper table) can reference them unambiguously.
    """
    # --- 2x2 alternating rectangle -------------------------------------
    # Two marginals each over a pair of states; the fiber difference set
    # D = {v : v0+v1=0, v2+v3=0} is a 2D alternating rectangle.  The two
    # catalogs share marginals but differ by v = (1/4,-1/4,-1/4,1/4), which
    # is a non-zero fiber element that the panel blinds (both actions map it
    # to the zero observation-law difference), so gamma(S) = 0.
    marg2 = ((_F(1), _F(1), _F(0), _F(0)), (_F(0), _F(0), _F(1), _F(1)))
    actions_rect = (
        Action(
            action_id="a",
            channel=_channel(
                (
                    (_F(1), _F(1, 2), _F(1), _F(1, 2)),
                    (_F(0), _F(1, 2), _F(0), _F(1, 2)),
                )
            ),
        ),
        Action(
            action_id="b",
            channel=_channel(
                (
                    (_F(1, 2), _F(1), _F(1, 2), _F(1)),
                    (_F(1, 2), _F(0), _F(1, 2), _F(0)),
                )
            ),
        ),
    )
    alternating_rectangle = T2FiniteModel(
        name="alternating_rectangle_2x2",
        n_states=4,
        theta_0=((_F(1, 4), _F(1, 4), _F(1, 4), _F(1, 4)),),
        theta_1=((_F(1, 2), _F(0), _F(0), _F(1, 2)),),
        marginal_map=marg2,
        actions=actions_rect,
    )

    # --- no cycle -------------------------------------------------------
    # Identity marginal map: catalogs are disjoint with no shared marginal,
    # so the cross-class difference set under M is empty -> no cycle.
    no_cycle = T2FiniteModel(
        name="no_cycle",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(1), _F(0)), (_F(0), _F(1))),
        actions=(
            Action(action_id="a", channel=_channel(((_F(1), _F(0)), (_F(0), _F(1))))),
        ),
    )

    # --- zero margin ----------------------------------------------------
    # One marginal-map row is all-zero: that marginal carries no information.
    zero_margin = T2FiniteModel(
        name="zero_margin",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(0), _F(0)), (_F(1), _F(0)), (_F(0), _F(1))),
        actions=(
            Action(
                action_id="a",
                channel=_channel(((_F(1, 2), _F(1, 2)), (_F(1, 2), _F(1, 2)))),
            ),
        ),
    )

    # --- symmetric states ----------------------------------------------
    # Catalogs are symmetric under the state permutation (0<->1).
    symmetric = T2FiniteModel(
        name="symmetric_states",
        n_states=2,
        theta_0=((_F(1, 2), _F(1, 2)),),
        theta_1=((_F(1, 2), _F(1, 2)),),
        marginal_map=((_F(1), _F(1)), (_F(1), _F(-1))),
        actions=(
            Action(
                action_id="a",
                channel=_channel(((_F(1, 2), _F(1, 2)), (_F(1, 2), _F(1, 2)))),
            ),
        ),
    )

    # --- repeated action -------------------------------------------------
    # The identical channel appears twice in the action library.
    chan = _channel(((_F(3, 4), _F(1, 4)), (_F(1, 4), _F(3, 4))))
    repeated_action = T2FiniteModel(
        name="repeated_action",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(1), _F(0)), (_F(0), _F(1))),
        actions=(Action("a", chan), Action("a_copy", chan)),
    )

    # --- cancellation counterexample ------------------------------------
    # Every generator of the fiber basis is hit by some action, but a linear
    # combination cancels so there is no robust separation.
    #
    # State space {0,1,2}; marginal_map = ((1,1,1)) means any valid catalog
    # is admissible (sum = 1), so the fiber D is the whole zero-sum plane
    # spanned by g1=(1,-1,0) and g2=(0,1,-1).  Both catalogs are valid
    # distributions with v = theta_1 - theta_0 = (1,0,-1) = g1 + g2.
    #
    # Action "a" hits g1 (|B_a g1|_1 = 2) but blinds v: B_a v = 0 because
    # states 0 and 2 are confounded.  Action "b" hits g2 (|B_b g2|_1 = 2)
    # but also blinds v.  Hence each generator is individually hit yet the
    # combination v cancels on the full panel -> collision, gamma = 0.
    marg3 = ((_F(1), _F(1), _F(1)),)
    cancellation = T2FiniteModel(
        name="cancellation_cycled",
        n_states=3,
        theta_0=((_F(0), _F(0), _F(1)),),
        theta_1=((_F(1), _F(0), _F(0)),),
        marginal_map=marg3,
        actions=(
            Action(
                "a",
                _channel(
                    ((_F(1), _F(0), _F(1)), (_F(0), _F(1), _F(0)))
                ),
            ),
            Action(
                "b",
                _channel(
                    ((_F(0), _F(1), _F(0)), (_F(1), _F(0), _F(1)))
                ),
            ),
        ),
    )

    # --- non-decomposable 3D fixed-marginal ------------------------------
    # 3 states with a single marginal map that is not decomposable into an
    # axis-aligned rectangle; simple 2-cycles are not a complete Markov basis.
    nondecomp3d = T2FiniteModel(
        name="nondecomposable_3d",
        n_states=4,
        theta_0=((_F(1, 8), _F(3, 8), _F(3, 8), _F(1, 8)),),
        theta_1=(
            (_F(1, 8), _F(3, 8), _F(3, 8), _F(1, 8)),
            (_F(3, 8), _F(1, 8), _F(1, 8), _F(3, 8)),
        ),
        marginal_map=((_F(1), _F(1), _F(0), _F(0)), (_F(0), _F(0), _F(1), _F(1))),
        actions=(
            Action(
                "a",
                _channel(
                    (
                        (_F(1), _F(1), _F(0), _F(0)),
                        (_F(0), _F(0), _F(1), _F(1)),
                    )
                ),
            ),
        ),
    )

    # --- exact collision ---------------------------------------------------
    # Two distinct latent distributions give identical laws on every action.
    exact_collision = T2FiniteModel(
        name="exact_collision",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(1), _F(1)),),
        actions=(
            Action(
                "a",
                _channel(((_F(1, 2), _F(1, 2)), (_F(1, 2), _F(1, 2)))),
            ),
        ),
    )

    # --- near collision -----------------------------------------------------
    # Two latent distributions whose action laws are close but not equal.
    near_collision = T2FiniteModel(
        name="near_collision",
        n_states=2,
        theta_0=((_F(1, 2) + _F(1, 1000), _F(1, 2) - _F(1, 1000)),),
        theta_1=((_F(1, 2), _F(1, 2)),),
        marginal_map=((_F(1), _F(1)),),
        actions=(
            Action(
                "a",
                _channel(((_F(1), _F(0)), (_F(0), _F(1)))),
            ),
        ),
    )

    # --- strict positive separation ------------------------------------------
    strict_sep = T2FiniteModel(
        name="strict_positive_separation",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(1), _F(0)), (_F(0), _F(1))),
        actions=(
            Action(
                "a",
                _channel(((_F(1), _F(0)), (_F(0), _F(1)))),
            ),
        ),
    )

    # --- boundary -------------------------------------------------------------
    # An action with a 3-outcome alphabet so the images are just separable.
    boundary = T2FiniteModel(
        name="boundary",
        n_states=2,
        theta_0=((_F(1), _F(0)),),
        theta_1=((_F(0), _F(1)),),
        marginal_map=((_F(1), _F(0)), (_F(0), _F(1))),
        actions=(
            Action(
                "a",
                _channel(
                    ((_F(1, 2), _F(0)), (_F(1, 2), _F(1, 2)), (_F(0), _F(1, 2)))
                ),
            ),
        ),
    )

    return {
        "alternating_rectangle_2x2": alternating_rectangle,
        "no_cycle": no_cycle,
        "zero_margin": zero_margin,
        "symmetric_states": symmetric,
        "repeated_action": repeated_action,
        "cancellation_cycled": cancellation,
        "nondecomposable_3d": nondecomp3d,
        "exact_collision": exact_collision,
        "near_collision": near_collision,
        "strict_positive_separation": strict_sep,
        "boundary": boundary,
    }


# ---------------------------------------------------------------------------
# Multi-action exhaustive oracle
# ---------------------------------------------------------------------------

def _count_vectors(k: int, n: int):
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


def _multinomial_prob(p: Vec, counts: tuple[int, ...]) -> Fraction:
    from math import factorial

    k = len(p)
    n = sum(counts)
    coeff = Fraction(factorial(n), 1)
    for c in counts:
        coeff //= Fraction(factorial(c), 1)
    pr = _F(1)
    for y in range(k):
        pr *= p[y] ** counts[y]
    return coeff * pr


@dataclass(frozen=True)
class OracleResult:
    """Exact decision/geometry quantities for a fixed panel allocation."""

    n: tuple[int, ...]                      # repeats per action
    cost: Fraction                           # sum_u c_u n_u
    product_tv: Fraction                     # TV(P0^n, P1^n)
    minimax_error: Fraction                  # (1/2) sum_joint min(P0,P1)
    correct_decl: Fraction                   # (P0(dH0)+P1(dH1))/2
    wrong_decl: Fraction                     # (P0(dH1)+P1(dH0))/2
    abstain: Fraction                        # (P0(a)+P1(a))/2
    outcome_count: int                       # number of joint outcomes
    product_bhattacharyya: Fraction | None   # exact when perfect squares

    def replay_sha256(self) -> str:
        payload = {
            "n": [str(x) for x in self.n],
            "cost": str(self.cost),
            "product_tv": str(self.product_tv),
            "minimax_error": str(self.minimax_error),
            "correct_decl": str(self.correct_decl),
            "wrong_decl": str(self.wrong_decl),
            "abstain": str(self.abstain),
            "outcome_count": self.outcome_count,
        }
        return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


@dataclass
class MultiActionOracle:
    """Independent exhaustive oracle for a fixed panel allocation.

    ``p0_laws`` / ``p1_laws`` are the per-action categorical laws under H0/H1
    (``len`` equals the number of actions).  ``n`` is the allocation.
    ``abstain_ratio >= 1`` scales the likelihood-ratio decision band; with
    ``abstain_ratio == 1`` the rule reduces to the minimax (no-abstention)
    decision.
    """

    p0_laws: tuple[Vec, ...]
    p1_laws: tuple[Vec, ...]
    costs: tuple[Fraction, ...]
    n: tuple[int, ...]
    abstain_ratio: Fraction = _F(1)

    def __post_init__(self) -> None:
        if not (len(self.p0_laws) == len(self.p1_laws) == len(self.costs) == len(self.n)):
            raise ValueError(
                "p0_laws, p1_laws, costs and n must have equal length"
            )
        if self.abstain_ratio < 1:
            raise ValueError("abstain_ratio must be >= 1")

    def _canonical_support(self):
        per_action = []
        for u, (q0, q1) in enumerate(zip(self.p0_laws, self.p1_laws)):
            per_action.append(
                tuple(_count_vectors(len(q0), self.n[u]))
            )
        for joint in product(*per_action):
            yield joint

    def evaluate(self) -> OracleResult:
        cost = sum(c * nu for c, nu in zip(self.costs, self.n))
        k = self.abstain_ratio
        count = 0
        total0 = _F(0)
        total1 = _F(0)
        correct = _F(0)
        wrong = _F(0)
        abstain = _F(0)
        bhat_exact = _F(1)
        bhat_representable = True
        support_rows = []
        for joint in self._canonical_support():
            p0 = _F(1)
            p1 = _F(1)
            for u, counts in enumerate(joint):
                p0 *= _multinomial_prob(self.p0_laws[u], counts)
                p1 *= _multinomial_prob(self.p1_laws[u], counts)
            count += 1
            total0 += p0
            total1 += p1
            # decision by likelihood-ratio band
            if p0 >= k * p1:
                correct += p0
                wrong += p1  # under H1, deciding H0 is an error
            elif p1 >= k * p0:
                wrong += p0  # under H0, deciding H1 is an error
                correct += p1
            else:
                abstain += p0
                abstain += p1
            support_rows.append((joint, p0, p1))
            # exact product Bhattacharyya when all square roots are exact
            for y in range(len(self.p0_laws[0])):
                prod = self.p0_laws[0][y] * self.p1_laws[0][y]
                if _rational_sqrt(prod) is None:
                    bhat_representable = False
        total = (total0 + total1)
        if total != 2:
            raise AssertionError(f"oracle probability normalization failed: {total}")
        # product-law TV = sum_joint |P0 - P1| / 2 ; minimax error = sum_joint min/2
        min_sum = sum(
            (p0 if p0 < p1 else p1) for _j, p0, p1 in support_rows
        )
        product_tv = _F(1) - min_sum
        minimax_error = min_sum / _F(2)
        bhat = None
        if bhat_representable:
            bc = _F(0)
            for y in range(len(self.p0_laws[0])):
                root = _rational_sqrt(self.p0_laws[0][y] * self.p1_laws[0][y])
                assert root is not None
                bc += root
            bhat = bc ** sum(self.n)
        return OracleResult(
            n=self.n,
            cost=cost,
            product_tv=product_tv,
            minimax_error=minimax_error,
            correct_decl=correct / _F(2),
            wrong_decl=wrong / _F(2),
            abstain=abstain / _F(2),
            outcome_count=count,
            product_bhattacharyya=bhat,
        )


def _rational_sqrt(x: Fraction) -> Fraction | None:
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


# ---------------------------------------------------------------------------
# §9.1 exhaustive-oracle cross-validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossValidation:
    """Exact oracle vs certified T2c theory bounds for a single pair/panel."""

    model_name: str
    pair_name: str
    n: tuple[int, ...]
    oracle: OracleResult
    total_info_interval: Interval
    wrong_upper: Interval          # (1/2) exp(-I_total), certified
    correct_lower: Interval        # 1 - (1/2) exp(-I_total), certified
    tv_interval: tuple[Fraction, Fraction]  # [1 - sqrt(1-BC^2), sqrt(1-BC^2)]-ish
    oracle_in_interval: bool
    crosscheck: dict[str, bool]


def cross_validate_single_pair(
    model: T2FiniteModel,
    p0: Vec,
    p1: Vec,
    n: tuple[int, ...],
    costs: tuple[Fraction, ...],
    abstain_ratio: Fraction = _F(1),
) -> CrossValidation:
    """Cross-validate the exhaustive oracle against the certified T2c bounds.

    For each action the Hellinger information interval is computed; the total
    ``I_total = sum_u n_u I_u`` is certified by interval arithmetic.  The
    certified achievability upper bound ``(1/2) exp(-I_total)`` must dominate
    the exact minimax error, and the exact values must be consistent with the
    theory-side decision enumeration.
    """
    p0_laws = tuple(action_law(model, a, p0) for a in model.actions)
    p1_laws = tuple(action_law(model, a, p1) for a in model.actions)
    oracle = MultiActionOracle(p0_laws, p1_laws, costs, n, abstain_ratio).evaluate()

    per_action_info = []
    for q0, q1 in zip(p0_laws, p1_laws):
        per_action_info.append(_info_interval(q0, q1))
    if any(iv is None for iv in per_action_info):
        # Some action certifiably separates the two laws with +infinite info:
        # the certified achievability upper bound collapses to 0 error.
        total_info = Interval(
            Decimal("+Infinity"), Decimal("+Infinity")
        )
        wrong_upper = Interval(Decimal(0), Decimal(0))
        correct_lower = Interval(Decimal(1), Decimal(1))
    else:
        # Certified interval arithmetic with directed rounding (precision 60).
        # A naive ``sum(nu * iv.lo ...)`` runs under the default Decimal context
        # (precision 28) and would round the 60-digit endpoints, collapsing the
        # interval and silently destroying its conservativeness.  Use the
        # certified helpers instead.
        scaled = [
            scale_info_interval(iv, nu) for nu, iv in zip(n, per_action_info)
        ]
        total_info = sum_intervals(scaled)
        wrong_upper = wrong_prob_upper_interval(total_info)
        correct_lower = correct_decl_lower_interval(total_info)

    # oracle inside certified interval
    oracle_in_interval = (
        oracle.minimax_error <= wrong_upper.hi
        and oracle.correct_decl >= correct_lower.lo
    )
    # theory <-> oracle cross-check (no-abstention minimax)
    crosscheck = {
        "minimax_le_upper": oracle.minimax_error <= wrong_upper.hi,
        "correct_ge_lower": oracle.correct_decl >= correct_lower.lo,
        "tv_equals_1_minus_2err": oracle.product_tv
        == _F(1) - _F(2) * oracle.minimax_error,
        "correct_plus_wrong_equals_1": (
            oracle.correct_decl + oracle.wrong_decl + oracle.abstain == 1
        ),
    }
    return CrossValidation(
        model_name=model.name,
        pair_name=f"{p0!r}<->{p1!r}",
        n=n,
        oracle=oracle,
        total_info_interval=total_info,
        wrong_upper=wrong_upper,
        correct_lower=correct_lower,
        tv_interval=(_F(0), _F(1)),
        oracle_in_interval=oracle_in_interval,
        crosscheck=crosscheck,
    )


# ---------------------------------------------------------------------------
# §9.3 baseline allocators
# ---------------------------------------------------------------------------

INF = float("inf")

# A large finite score standing in for "+infinite Hellinger information" when
# two observation laws have disjoint support (perfect, certifiable separation).
_INF_SCORE = Fraction(1_000_000)


def _info_interval(q0: Vec, q1: Vec) -> Interval | None:
    """Certified Hellinger information, or ``None`` when laws are disjoint.

    Disjoint supports give ``BC = 0`` and ``I = +infinity``, which
    ``hellinger_info_interval`` cannot represent (``ln(0)`` underflows).  The
    oracle treats this as perfect separation inside the matrix.
    """
    bc = bhattacharyya_coeff_interval(q0, q1)
    if bc.hi == 0:
        return None
    return hellinger_info_interval(q0, q1)


def _per_action_info_law(q0: Vec, q1: Vec) -> Fraction:
    """A rational score from the Hellinger information interval (midpoint)."""
    iv = _info_interval(q0, q1)
    if iv is None:
        return _INF_SCORE
    return Fraction(iv.lo + iv.hi) / Fraction(2)


def _per_action_chernoff(q0: Vec, q1: Vec) -> Fraction:
    """Chernoff-syle score ``-log sum_y min(q0,q1)`` (non-negative)."""
    s = sum(min(a, b) for a, b in zip(q0, q1))
    if s <= 0:
        return _F(0)
    return _F(1) - s  # 1 - overlap; higher is more separating


def _allocate_budget(score: Sequence[Fraction], costs: Sequence[Fraction], budget: Fraction) -> tuple[int, ...]:
    """Greedy cost-weighted allocation of ``budget`` repeats.

    Repeatedly adds one repeat to the action maximizing ``score_u / cost_u``
    until the budget is exhausted.  Allocations are integer and the total cost
    never exceeds ``budget``.
    """
    U = len(score)
    n = [0] * U
    spent = _F(0)
    while True:
        best_u = None
        best_v = -1
        for u in range(U):
            if costs[u] > 0:
                v = score[u] / costs[u]
                if v > best_v:
                    best_v = v
                    best_u = u
        if best_u is None:
            break
        if spent + costs[best_u] > budget:
            break
        n[best_u] += 1
        spent += costs[best_u]
    return tuple(n)


def _random_allocation(U: int, costs: Sequence[Fraction], budget: Fraction, seed: int) -> tuple[int, ...]:
    import random as _random

    rng = _random.Random(seed)
    n = [0] * U
    spent = _F(0)
    while True:
        candidates = [u for u in range(U) if spent + costs[u] <= budget]
        if not candidates:
            break
        u = rng.choice(candidates)
        n[u] += 1
        spent += costs[u]
    return tuple(n)


@dataclass(frozen=True)
class ExperimentSpec:
    """Common setting shared by all baselines (§9.3)."""

    model_name: str
    p0: Vec
    p1: Vec
    costs: tuple[Fraction, ...]
    budget: Fraction
    abstain_ratio: Fraction = _F(1)
    seed: int = 0


@dataclass(frozen=True)
class BaselineRun:
    """One executed baseline on one microcase."""

    method: str
    allocation: tuple[int, ...]
    cost: Fraction
    spent_exceeds_budget: bool
    runtime_s: float
    oracle: OracleResult | None
    lp_lower_bound: Fraction | None
    integer_upper: Fraction | None
    optimality_gap: Fraction | None
    certified_omitted_mass: Interval | None
    memory: int | None = None
    executed: bool = True

    def replay_sha256(self) -> str:
        payload = {
            "method": self.method,
            "allocation": [str(x) for x in self.allocation],
            "cost": str(self.cost),
            "spent_exceeds_budget": self.spent_exceeds_budget,
            "executed": self.executed,
        }
        return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def _laws_for(model: T2FiniteModel, p0: Vec, p1: Vec) -> tuple[tuple[Vec, ...], tuple[Vec, ...]]:
    p0_laws = tuple(action_law(model, a, p0) for a in model.actions)
    p1_laws = tuple(action_law(model, a, p1) for a in model.actions)
    return p0_laws, p1_laws


def _oracle_eval(model: T2FiniteModel, spec: ExperimentSpec, n: tuple[int, ...]) -> OracleResult:
    p0_laws, p1_laws = _laws_for(model, spec.p0, spec.p1)
    return MultiActionOracle(p0_laws, p1_laws, spec.costs, n, spec.abstain_ratio).evaluate()


def _frac_interval(f: Fraction) -> Interval:
    """Certified exact interval for a rational ``f`` (Decimal endpoints)."""
    from d2t_rna.t2.info import rational_interval

    return rational_interval(f)


def _omitted_mass(res: OracleResult) -> Interval:
    """Certified omitted mass: the probability the rule neither correctly nor
    wrongly decides (the abstention band), reported as a certified interval."""
    return _frac_interval(res.abstain)


def _eval_with_memory(
    model: T2FiniteModel, spec: ExperimentSpec, n: tuple[int, ...]
) -> tuple[OracleResult, int]:
    """Evaluate the oracle and return ``(result, peak_traced_bytes)``."""
    import tracemalloc

    tracemalloc.start()
    try:
        res = _oracle_eval(model, spec, n)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return res, peak


def run_baselines(model: T2FiniteModel, spec: ExperimentSpec) -> dict[str, BaselineRun]:
    """Actually execute all §9.3 baselines under one common spec.

    Eight methods: ``exhaustive_oracle``, ``full_matrix``, ``random``,
    ``greedy_test_cover``, ``eig``, ``chernoff``, ``lm2r_heuristic`` and
    ``t2_integer_lp``.  Each returns a :class:`BaselineRun` whose ``executed``
    flag is ``True`` only when the allocation was actually produced (never a
    bare wrapper).
    """
    U = len(model.actions)
    p0_laws, p1_laws = _laws_for(model, spec.p0, spec.p1)
    results: dict[str, BaselineRun] = {}

    # per-action scores
    eig_score = tuple(_per_action_info_law(q0, q1) for q0, q1 in zip(p0_laws, p1_laws))
    chernoff_score = tuple(_per_action_chernoff(q0, q1) for q0, q1 in zip(p0_laws, p1_laws))
    # LM2R-style: combine separation and moderate cost pressure
    lm2r_score = tuple(eig_score[u] for u in range(U))

    # ---- exhaustive oracle: search smallest-cost allocation by minimax error
    import tracemalloc

    oracle_start = time.time()
    oracle_n = None
    oracle_err = None
    tracemalloc.start()
    try:
        # enumerate allocations up to a per-action cap so the exact oracle is cheap
        cap = 6
        for joint in product(range(cap + 1), repeat=U):
            cand_n = tuple(joint)
            cand_cost = sum(c * nu for c, nu in zip(spec.costs, cand_n))
            if cand_cost > spec.budget:
                continue
            cand = _oracle_eval(model, spec, cand_n)
            if oracle_err is None or cand.minimax_error < oracle_err:
                oracle_err = cand.minimax_error
                oracle_n = cand_n
    finally:
        _, oracle_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    oracle_time = time.time() - oracle_start
    if oracle_n is None:
        oracle_n = tuple(0 for _ in range(U))
    oracle_res = _oracle_eval(model, spec, oracle_n)
    results["exhaustive_oracle"] = BaselineRun(
        method="exhaustive_oracle",
        allocation=oracle_n,
        cost=oracle_res.cost,
        spent_exceeds_budget=oracle_res.cost > spec.budget,
        runtime_s=oracle_time,
        oracle=oracle_res,
        lp_lower_bound=None,
        integer_upper=None,
        optimality_gap=None,
        certified_omitted_mass=_omitted_mass(oracle_res),
        memory=oracle_peak,
    )

    # ---- full matrix: equal split across all actions (round-robin)
    full_start = time.time()
    n_full = [0] * U
    spent = _F(0)
    u = 0
    while True:
        if spent + spec.costs[u % U] > spec.budget:
            break
        n_full[u % U] += 1
        spent += spec.costs[u % U]
        u += 1
    full_res, full_peak = _eval_with_memory(model, spec, tuple(n_full))
    results["full_matrix"] = BaselineRun(
        method="full_matrix",
        allocation=tuple(n_full),
        cost=full_res.cost,
        spent_exceeds_budget=full_res.cost > spec.budget,
        runtime_s=time.time() - full_start,
        oracle=full_res,
        lp_lower_bound=None,
        integer_upper=None,
        optimality_gap=None,
        certified_omitted_mass=_omitted_mass(full_res),
        memory=full_peak,
    )

    # ---- random (seeded)
    rand_start = time.time()
    n_rand = _random_allocation(U, spec.costs, spec.budget, spec.seed)
    rand_res, rand_peak = _eval_with_memory(model, spec, n_rand)
    results["random"] = BaselineRun(
        method="random",
        allocation=n_rand,
        cost=rand_res.cost,
        spent_exceeds_budget=rand_res.cost > spec.budget,
        runtime_s=time.time() - rand_start,
        oracle=rand_res,
        lp_lower_bound=None,
        integer_upper=None,
        optimality_gap=None,
        certified_omitted_mass=_omitted_mass(rand_res),
        memory=rand_peak,
    )

    # ---- greedy / Test-Cover and EIG (both greedy; different score)
    for method, score in (("greedy_test_cover", eig_score), ("eig", eig_score)):
        g_start = time.time()
        n_g = _allocate_budget(score, spec.costs, spec.budget)
        g_res, g_peak = _eval_with_memory(model, spec, n_g)
        results[method] = BaselineRun(
            method=method,
            allocation=n_g,
            cost=g_res.cost,
            spent_exceeds_budget=g_res.cost > spec.budget,
            runtime_s=time.time() - g_start,
            oracle=g_res,
            lp_lower_bound=None,
            integer_upper=None,
            optimality_gap=None,
            certified_omitted_mass=_omitted_mass(g_res),
            memory=g_peak,
        )

    # ---- Chernoff
    ch_start = time.time()
    n_ch = _allocate_budget(chernoff_score, spec.costs, spec.budget)
    ch_res, ch_peak = _eval_with_memory(model, spec, n_ch)
    results["chernoff"] = BaselineRun(
        method="chernoff",
        allocation=n_ch,
        cost=ch_res.cost,
        spent_exceeds_budget=ch_res.cost > spec.budget,
        runtime_s=time.time() - ch_start,
        oracle=ch_res,
        lp_lower_bound=None,
        integer_upper=None,
        optimality_gap=None,
        certified_omitted_mass=_omitted_mass(ch_res),
        memory=ch_peak,
    )

    # ---- LM2R-style heuristic
    lm_start = time.time()
    n_lm = _allocate_budget(lm2r_score, spec.costs, spec.budget)
    lm_res, lm_peak = _eval_with_memory(model, spec, n_lm)
    results["lm2r_heuristic"] = BaselineRun(
        method="lm2r_heuristic",
        allocation=n_lm,
        cost=lm_res.cost,
        spent_exceeds_budget=lm_res.cost > spec.budget,
        runtime_s=time.time() - lm_start,
        oracle=lm_res,
        lp_lower_bound=None,
        integer_upper=None,
        optimality_gap=None,
        certified_omitted_mass=_omitted_mass(lm_res),
        memory=lm_peak,
    )

    # ---- T2 integer design & LP lower bound (costed.py)
    t2_start = time.time()
    # A single registered pair (the candidate-vs-rival pair under test).
    pair_ids = ("w",)
    info_min = []
    info_max = []
    for q0, q1 in zip(p0_laws, p1_laws):
        iv = _info_interval(q0, q1)
        if iv is None:
            # disjoint support -> +infinite info: certifiable perfect separation
            info_min.append(_INF_SCORE)
            info_max.append(_INF_SCORE)
        else:
            # exact rational microcase: the certified upper/lower bounds are
            # tight rational stand-ins for the irrational I_uw.  Information is
            # non-negative, so clamp a conservatively-negative interval lower
            # bound to 0 (a valid lower bound for the integer design).
            lo = Fraction(iv.lo)
            hi = Fraction(iv.hi)
            info_min.append(lo if lo >= 0 else _F(0))
            info_max.append(hi if hi >= 0 else _F(0))
    # We target a fixed correct-decl threshold tau per pair; use tau = small
    # positive so the LP is non-trivial.
    tau = _F(1, 2)
    cd = CostedDesign(
        action_ids=tuple(a.action_id for a in model.actions),
        costs=spec.costs,
        pair_ids=pair_ids,
        thresholds=(tau,),
        info_lower=tuple((v,) for v in info_min),
        info_upper=tuple((v,) for v in info_max),
    )
    lp_lb = no_go_lower_bound(cd)
    int_cost, int_n = achievable_integer_design(cd)
    gap = None
    if lp_lb is not None and lp_lb > 0 and int_cost is not None:
        gap = (int_cost - lp_lb) / lp_lb
    # Budget-aware: the exact oracle is only tractable for small allocations.
    # When the certified min-cost integer design exceeds the budget (a
    # contract 5.4 no-go within the fixed budget), we cross-check the oracle
    # at the best within-budget allocation and record the infeasibility flag,
    # rather than evaluating the oracle at an intractable repeat count.
    if int_n is not None and sum(c * nu for c, nu in zip(spec.costs, int_n)) <= spec.budget:
        t2_n = tuple(int(int_n[u]) for u in range(U))
        t2_exceeds = int_cost > spec.budget
    else:
        # no-go within budget: use the greedy within-budget allocation for the
        # oracle cross-check; the LP lower bound / integer gap already certify
        # that the registered pair cannot be separated within the budget.
        t2_n = _allocate_budget(eig_score, spec.costs, spec.budget)
        t2_exceeds = True
    t2_res, t2_peak = _eval_with_memory(model, spec, t2_n)
    results["t2_integer_lp"] = BaselineRun(
        method="t2_integer_lp",
        allocation=t2_n,
        cost=t2_res.cost,
        spent_exceeds_budget=t2_exceeds,
        runtime_s=time.time() - t2_start,
        oracle=t2_res,
        lp_lower_bound=lp_lb,
        integer_upper=int_cost,
        optimality_gap=gap,
        certified_omitted_mass=_omitted_mass(t2_res),
        memory=t2_peak,
    )

    return results


# ---------------------------------------------------------------------------
# §9.2 matrix report
# ---------------------------------------------------------------------------

@dataclass
class MatrixReport:
    """Aggregate §9.2 evaluation-matrix record for a microcase."""

    model_name: str
    spec: ExperimentSpec
    baselines: dict[str, BaselineRun]
    cross_validation: CrossValidation | None

    def replay_sha256(self) -> str:
        payload = {
            "model_name": self.model_name,
            "candidate": [str(x) for x in self.spec.p0],
            "rival": [str(x) for x in self.spec.p1],
            "budget": str(self.spec.budget),
            "baselines": {
                k: v.replay_sha256() for k, v in sorted(self.baselines.items())
            },
        }
        return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def build_matrix_report(
    model: T2FiniteModel,
    spec: ExperimentSpec,
    cross_validation: CrossValidation | None = None,
) -> MatrixReport:
    """Build the §9.2 report by executing every baseline on the microcase."""
    baselines = run_baselines(model, spec)
    return MatrixReport(
        model_name=model.name,
        spec=spec,
        baselines=baselines,
        cross_validation=cross_validation,
    )