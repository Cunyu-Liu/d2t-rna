"""Independent checker for the T2-4 costed design (contract 10.3).

The checker re-derives every claim from first principles using exact rational
arithmetic, without trusting the LP solver's internal state:
* dual feasibility / budget-certificate feasibility,
* dual lower bound ``tau^T y``,
* no-go sign,
* integer-design feasibility and cost accounting,
* integrality-gap arithmetic.

It deliberately recomputes sums and inequalities independently of
:mod:`d2t_rna.t2.costed` so that solver status, floating tolerance, or a mere
re-run of the same implementation are not treated as proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from .costed import CostedDesign

Vec = tuple[Fraction, ...]


def check_dual_feasible(
    cd: CostedDesign, info_used: Sequence[Sequence[Fraction]], y: Sequence[Fraction]
) -> bool:
    """Verify ``y >= 0`` and ``info_used^T y <= c`` for every action."""
    U = len(cd.costs)
    W = len(cd.pair_ids)
    if len(y) != W:
        return False
    for w in range(W):
        if y[w] < 0:
            return False
    for u in range(U):
        lhs = sum(y[w] * info_used[u][w] for w in range(W))
        if lhs > cd.costs[u]:
            return False
    return True


def check_dual_bound(
    cd: CostedDesign, y: Sequence[Fraction]
) -> Fraction:
    """Recompute ``tau^T y`` from first principles."""
    return sum(y[w] * cd.thresholds[w] for w in range(len(cd.pair_ids)))


def check_no_go_sign(budget: Fraction, dual_bound: Fraction) -> str:
    """Sign ``NO_GO`` exactly when ``dual_bound > budget``."""
    if dual_bound > budget:
        return "NO_GO"
    if dual_bound == budget:
        return "TIGHT"
    return "BELOW"


def check_integer_design_feasible(
    cd: CostedDesign, info_used: Sequence[Sequence[Fraction]], n: Sequence[int]
) -> bool:
    """Verify ``sum_u n_u info_used[u][w] >= tau_w`` for every active pair."""
    W = len(cd.pair_ids)
    for w in range(W):
        if cd.thresholds[w] <= 0:
            continue
        lhs = sum(n[u] * info_used[u][w] for u in range(len(cd.costs)))
        if lhs < cd.thresholds[w]:
            return False
    return True


def check_design_cost(cd: CostedDesign, n: Sequence[int]) -> Fraction:
    """Recompute ``c^T n`` from first principles."""
    return sum(cd.costs[u] * n[u] for u in range(len(cd.costs)))


def check_integrality_gap(
    upper_cost: Fraction, lower_bound: Fraction
) -> Fraction | None:
    """Recompute ``(upper - lower)/lower`` from first principles."""
    if upper_cost is None or lower_bound is None or lower_bound <= 0:
        return None
    return (upper_cost - lower_bound) / lower_bound


@dataclass(frozen=True)
class CostedCheckReceipt:
    """Aggregate independent-checker verdict for a costed design."""

    dual_feasible: bool
    dual_bound: Fraction | None
    no_go_sign: str | None
    integer_feasible: bool
    integer_cost: Fraction | None
    gap: Fraction | None
    consistent: bool

    def as_dict(self) -> dict:
        return {
            "dual_feasible_lower_bound": self.dual_feasible,
            "dual_bound_tau_y": str(self.dual_bound) if self.dual_bound is not None else None,
            "no_go_sign": self.no_go_sign,
            "integer_design_feasible": self.integer_feasible,
            "integer_design_cost": str(self.integer_cost) if self.integer_cost is not None else None,
            "integrality_gap": str(self.gap) if self.gap is not None else None,
            "consistent": self.consistent,
        }