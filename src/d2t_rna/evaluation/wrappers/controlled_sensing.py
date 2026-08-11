"""wrappers.controlled_sensing -- faithful Chernoff controlled-sensing wrapper.

Faithful to fixed-sample / open-loop controlled sensing (Chernoff 1959;
Nitinawarat-Atia-Veeravalli 2013): the method scores each action by its
Chernoff information between the two induced laws and greedily allocates the
budget (open-loop, non-adaptive).  This is the ``chernoff`` comparator of the
frozen decision registry.

Toy parity: the original full text / a verified published toy value was not
available to this auditor, so the toy-parity status defaults to
``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and the wrapper is NOT
headline-eligible.  We never invent a parity number.
"""

from __future__ import annotations

from fractions import Fraction

from .base import (
    TOY_PARITY_UNKNOWN,
    FaithfulWrapper,
    ToyParityResult,
    greedy_allocate,
)
from .helpers import action_law, chernoff_information


class ControlledSensingWrapper(FaithfulWrapper):
    wrapper_id = "controlled_sensing"
    method_id = "chernoff"
    external_category = "controlled_sensing_fixed_sample_open_loop"

    def run(self, spec: dict) -> dict:
        p0 = tuple(Fraction(x) for x in spec["p0"])
        p1 = tuple(Fraction(x) for x in spec["p1"])
        costs = [Fraction(c) for c in spec["costs"]]
        budget = Fraction(spec["budget"])
        scores = []
        for channel in spec["actions"]:
            q0 = action_law(channel, p0)
            q1 = action_law(channel, p1)
            scores.append(chernoff_information(q0, q1))
        alloc, spent = greedy_allocate(scores, costs, budget)
        return {"method_id": self.method_id, "allocation": list(alloc),
                "cost": str(spent)}

    def toy_case(self) -> dict:
        return {
            "name": "chernoff_CA_p1_budget8",
            "description": (
                "CA_p1 microcase (p0=(1/4,3/4), p1=(0,1)) with two identity "
                "actions, unit cost, budget 8. The published toy value is NOT "
                "verifiable from the original full text; recorded as UNKNOWN."
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
                "No verified published toy value available from the original "
                "full text for the Chernoff controlled-sensing method; the "
                "wrapper is faithfully implemented but is NOT headline-eligible."
            ),
        )


def wrapper() -> ControlledSensingWrapper:
    return ControlledSensingWrapper()
