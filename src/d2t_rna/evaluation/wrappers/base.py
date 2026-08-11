"""wrappers.base -- shared protocol for faithful external-method wrappers (P0-9).

A *faithful wrapper* re-implements an external comparator method on the D2T task
(same action set / information / cost / horizon / endpoint).  A wrapper is only
"headline-eligible" if its ORIGINAL PAPER TOY CASE is reproduced (toy parity)
BEFORE the D2T task is run.

Because this auditor could not verify a published toy value from the original
full text for any of the wrapped methods, the default toy-parity status is
``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and ``headline_eligible=False``.  We
never invent a parity number.  Where an exact repo-oracle value is available we
still record an internal-consistency check, but that does NOT confer headline
eligibility (headline requires a verified *published* value).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

UNKNOWN = "UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING"

TOY_PARITY_PASS = "PASS"
TOY_PARITY_FAIL = "FAIL"
TOY_PARITY_UNKNOWN = UNKNOWN


@dataclass(frozen=True)
class ToyParityResult:
    """Outcome of running one wrapper's own toy case."""

    wrapper_id: str
    method_id: str
    toy_case_name: str
    # the published value from the original paper, or None if not verifiable
    published_value: Optional[str]
    # the value actually observed by running the wrapper's toy case
    observed_value: Optional[str]
    # PASS / FAIL / UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING
    status: str
    # True only when status == PASS AND the published value was verified
    headline_eligible: bool
    detail: str

    def to_dict(self) -> dict:
        return {
            "wrapper_id": self.wrapper_id,
            "method_id": self.method_id,
            "toy_case_name": self.toy_case_name,
            "published_value": self.published_value,
            "observed_value": self.observed_value,
            "status": self.status,
            "headline_eligible": self.headline_eligible,
            "detail": self.detail,
        }


class FaithfulWrapper:
    """Base class for a faithful external-method wrapper."""

    wrapper_id: str = "base"
    method_id: str = "base"
    external_category: str = ""

    def run(self, spec: dict) -> dict:
        """Run the faithful method on a D2T task spec.

        ``spec`` must carry at least: ``p0``, ``p1`` (Fraction tuples),
        ``actions`` (list of channel matrices), ``costs`` (Fraction tuple) and
        ``budget`` (Fraction).  Returns ``{"method_id", "allocation", "cost"}``.
        """
        raise NotImplementedError

    def toy_case(self) -> dict:
        """Metadata for the wrapper's own toy case."""
        raise NotImplementedError

    def run_toy_parity(self) -> ToyParityResult:
        """Run the wrapper's toy case and record PASS/FAIL/UNKNOWN."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# shared greedy allocation (cost-weighted, integer, within budget)
# ---------------------------------------------------------------------------


def greedy_allocate(
    score: list[float], costs: list, budget
) -> tuple:
    """Greedy cost-weighted integer allocation of ``budget`` repeats.

    Repeatedly adds one repeat to the action maximising ``score_u / cost_u``
    until the budget is exhausted.  Mirrors the repo's ``_allocate_budget``.
    Returns ``(allocation, total_cost)`` with ``total_cost <= budget``.
    """
    from fractions import Fraction

    U = len(score)
    alloc = [0] * U
    spent = Fraction(0)
    while True:
        best_u = None
        best_v = -1.0
        for u in range(U):
            c = Fraction(costs[u])
            if c > 0:
                v = float(score[u]) / float(c)
                if v > best_v:
                    best_v = v
                    best_u = u
        if best_u is None:
            break
        c = Fraction(costs[best_u])
        if spent + c > Fraction(budget):
            break
        alloc[best_u] += 1
        spent += c
    return tuple(alloc), spent


def total_cost(alloc: tuple, costs) -> object:
    from fractions import Fraction

    return sum(Fraction(c) * Fraction(n) for c, n in zip(costs, alloc))
