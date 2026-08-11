"""wrappers.test_cover -- faithful Test-Cover wrapper.

Faithful to the test-cover heuristic (Moret & Shapiro 1985/1991): the method
scores each test (action) by its separation power over the candidate/rival pair
(here the total-variation distance between the two induced laws) and greedily
builds a separating collection within the cost budget.  This is the
``greedy_test_cover`` comparator of the frozen decision registry.

Toy parity: no verified published toy value was available; status is
``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and NOT headline-eligible.
"""

from __future__ import annotations

from fractions import Fraction

from .base import (
    TOY_PARITY_UNKNOWN,
    FaithfulWrapper,
    ToyParityResult,
    greedy_allocate,
)
from .helpers import action_law, per_action_tv


class TestCoverWrapper(FaithfulWrapper):
    wrapper_id = "test_cover"
    method_id = "greedy_test_cover"
    external_category = "test_cover"

    def run(self, spec: dict) -> dict:
        p0 = tuple(Fraction(x) for x in spec["p0"])
        p1 = tuple(Fraction(x) for x in spec["p1"])
        costs = [Fraction(c) for c in spec["costs"]]
        budget = Fraction(spec["budget"])
        scores = []
        for channel in spec["actions"]:
            q0 = action_law(channel, p0)
            q1 = action_law(channel, p1)
            scores.append(float(per_action_tv(q0, q1)))
        alloc, spent = greedy_allocate(scores, costs, budget)
        return {"method_id": self.method_id, "allocation": list(alloc),
                "cost": str(spent)}

    def toy_case(self) -> dict:
        return {
            "name": "test_cover_CA_p1_budget8",
            "description": (
                "Test-Cover allocation on the CA_p1 microcase. The published "
                "toy value is NOT verifiable from the original full text; "
                "recorded as UNKNOWN."
            ),
            "published_value": None,
        }

    def run_toy_parity(self) -> ToyParityResult:
        case = self.toy_case()
        return ToyParityResult(
            wrapper_id=self.wrapper_id,
            method_id=self.method_id,
            toy_case_name=case["name"],
            published_value=None,
            observed_value=None,
            status=TOY_PARITY_UNKNOWN,
            headline_eligible=False,
            detail=(
                "No verified published toy value available for the Moret & "
                "Shapiro test-cover heuristic; NOT headline-eligible."
            ),
        )


def wrapper() -> TestCoverWrapper:
    return TestCoverWrapper()
