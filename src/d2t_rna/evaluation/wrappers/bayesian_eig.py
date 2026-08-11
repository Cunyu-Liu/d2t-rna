"""wrappers.bayesian_eig -- faithful Bayesian-EIG (decision-region) wrapper.

Faithful to Bayesian expected-information-gain experimental design (Lindley
1956; DeGroot 1962): the method scores each action by its expected information
gain (Hellinger-information surrogate) and greedily allocates the budget to
maximise information.  This is the ``eig`` comparator of the frozen decision
registry.

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
from .helpers import action_law, hellinger_info


class BayesianEIGWrapper(FaithfulWrapper):
    wrapper_id = "bayesian_eig"
    method_id = "eig"
    external_category = "bayesian_eig_decision_region"

    def run(self, spec: dict) -> dict:
        p0 = tuple(Fraction(x) for x in spec["p0"])
        p1 = tuple(Fraction(x) for x in spec["p1"])
        costs = [Fraction(c) for c in spec["costs"]]
        budget = Fraction(spec["budget"])
        scores = []
        for channel in spec["actions"]:
            q0 = action_law(channel, p0)
            q1 = action_law(channel, p1)
            scores.append(hellinger_info(q0, q1))
        alloc, spent = greedy_allocate(scores, costs, budget)
        return {"method_id": self.method_id, "allocation": list(alloc),
                "cost": str(spent)}

    def toy_case(self) -> dict:
        return {
            "name": "eig_CA_p1_budget8",
            "description": (
                "Bayesian-EIG allocation on the CA_p1 microcase. The published "
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
                "No verified published toy value available for Bayesian EIG / "
                "decision-region determination; NOT headline-eligible."
            ),
        )


def wrapper() -> BayesianEIGWrapper:
    return BayesianEIGWrapper()
