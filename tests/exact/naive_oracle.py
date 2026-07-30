"""Deliberately independent raw-sequence oracle for Task 4 micro-cases.

This module does not import the production support enumerator, multinomial PMF,
confidence decision helper, or coverage accumulator.  It enumerates raw symbol
sequences, collapses them to count vectors, and independently recomputes every
pointwise and aggregate risk/coverage quantity.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import product
from typing import TypeAlias

from d2t_rna.exact.confidence import ExactParameterFamily
from d2t_rna.exact.support import ExactSupportSpec


JointOutcome: TypeAlias = tuple[tuple[int, ...], ...]
MembersRule: TypeAlias = Callable[[JointOutcome], tuple[str, ...]]
RationalPair: TypeAlias = tuple[int, int]

_ZERO: RationalPair = (0, 1)
_ONE: RationalPair = (1, 1)


def _euclidean_gcd(left: int, right: int) -> int:
    """Return a non-negative gcd without sharing the production arithmetic."""

    first = abs(left)
    second = abs(right)
    while second:
        first, second = second, first % second
    return first


def _normalize(numerator: int, denominator: int) -> RationalPair:
    if type(numerator) is not int or type(denominator) is not int:
        raise TypeError("oracle rational components must be exact integers")
    if denominator == 0:
        raise ZeroDivisionError("oracle rational denominator cannot be zero")
    if numerator == 0:
        return _ZERO
    if denominator < 0:
        numerator = -numerator
        denominator = -denominator
    divisor = _euclidean_gcd(numerator, denominator)
    return numerator // divisor, denominator // divisor


def _from_exact_components(value: object) -> RationalPair:
    numerator = getattr(value, "numerator")
    denominator = getattr(value, "denominator")
    if type(numerator) is not int or type(denominator) is not int:
        raise TypeError(
            "oracle inputs must expose exact int numerator/denominator"
        )
    return _normalize(numerator, denominator)


def _add(left: RationalPair, right: RationalPair) -> RationalPair:
    return _normalize(
        left[0] * right[1] + right[0] * left[1],
        left[1] * right[1],
    )


def _subtract(left: RationalPair, right: RationalPair) -> RationalPair:
    return _normalize(
        left[0] * right[1] - right[0] * left[1],
        left[1] * right[1],
    )


def _multiply(left: RationalPair, right: RationalPair) -> RationalPair:
    return _normalize(left[0] * right[0], left[1] * right[1])


def _divide(left: RationalPair, right: RationalPair) -> RationalPair:
    if right[0] == 0:
        raise ZeroDivisionError("oracle rational division by zero")
    return _normalize(left[0] * right[1], left[1] * right[0])


def _compare(left: RationalPair, right: RationalPair) -> int:
    difference = _subtract(left, right)
    return (difference[0] > 0) - (difference[0] < 0)


def _maximum(values: tuple[RationalPair, ...]) -> RationalPair:
    if not values:
        raise ValueError("oracle maximum requires at least one value")
    result = values[0]
    for value in values[1:]:
        if _compare(value, result) > 0:
            result = value
    return result


def _minimum(values: tuple[RationalPair, ...]) -> RationalPair:
    if not values:
        raise ValueError("oracle minimum requires at least one value")
    result = values[0]
    for value in values[1:]:
        if _compare(value, result) < 0:
            result = value
    return result


def _region(loss: object, tau0: object, epsilon: object) -> str:
    value = _from_exact_components(loss)
    if _compare(value, _from_exact_components(tau0)) <= 0:
        return "H0"
    if _compare(value, _from_exact_components(epsilon)) >= 0:
        return "H1"
    return "INDIFFERENCE"


def _one_action_raw_sequence_distribution(
    *,
    sample_size: int,
    probabilities: tuple[RationalPair, ...],
) -> dict[tuple[int, ...], RationalPair]:
    collapsed: dict[tuple[int, ...], RationalPair] = {}
    for sequence in product(range(len(probabilities)), repeat=sample_size):
        counts = tuple(
            sequence.count(symbol)
            for symbol in range(len(probabilities))
        )
        probability = _ONE
        for symbol in sequence:
            probability = _multiply(probability, probabilities[symbol])
        collapsed[counts] = _add(
            collapsed.get(counts, _ZERO),
            probability,
        )
    return collapsed


def raw_sequence_distribution(
    support: ExactSupportSpec,
    probability_rows: tuple[tuple[RationalPair, ...], ...],
) -> dict[JointOutcome, RationalPair]:
    per_action = tuple(
        _one_action_raw_sequence_distribution(
            sample_size=action.sample_size,
            probabilities=probabilities,
        )
        for action, probabilities in zip(
            support.actions,
            probability_rows,
            strict=True,
        )
    )
    joint: dict[JointOutcome, RationalPair] = {}
    for action_rows in product(
        *(tuple(distribution.items()) for distribution in per_action)
    ):
        outcome = tuple(item[0] for item in action_rows)
        probability = _ONE
        for _, action_probability in action_rows:
            probability = _multiply(probability, action_probability)
        joint[outcome] = probability
    return joint


def naive_risk_coverage_report(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    members_rule: MembersRule,
) -> dict[str, object]:
    point_regions = {
        point.parameter_id: _region(
            point.loss,
            family.thresholds.tau0,
            family.thresholds.epsilon,
        )
        for point in family.points
    }
    point_distributions = {}
    for point in family.points:
        probability_rows = tuple(
            tuple(
                _from_exact_components(value)
                for value in action.probabilities
            )
            for action in point.law.action_probabilities
        )
        point_distributions[point.parameter_id] = raw_sequence_distribution(
            support,
            probability_rows,
        )

    canonical_support = tuple(
        sorted(next(iter(point_distributions.values())))
    )
    results: dict[str, dict[str, object]] = {}
    h0_errors: list[RationalPair] = []
    h1_errors: list[RationalPair] = []
    indifference_errors: list[RationalPair] = []
    coverage_values: list[RationalPair] = []
    for point in family.points:
        accumulator: dict[str, RationalPair] = {
            "total": _ZERO,
            "coverage": _ZERO,
            "certify": _ZERO,
            "reject": _ZERO,
            "abstain": _ZERO,
        }
        distribution = point_distributions[point.parameter_id]
        for outcome in canonical_support:
            probability = distribution[outcome]
            members = members_rule(outcome)
            member_regions = {
                point_regions[member] for member in members
            }
            if members and member_regions == {"H0"}:
                decision = "C"
            elif members and member_regions == {"H1"}:
                decision = "R"
            else:
                decision = "ABSTAIN"
            accumulator["total"] = _add(
                accumulator["total"],
                probability,
            )
            if point.parameter_id in members:
                accumulator["coverage"] = _add(
                    accumulator["coverage"],
                    probability,
                )
            if decision == "C":
                accumulator["certify"] = _add(
                    accumulator["certify"],
                    probability,
                )
            elif decision == "R":
                accumulator["reject"] = _add(
                    accumulator["reject"],
                    probability,
                )
            else:
                accumulator["abstain"] = _add(
                    accumulator["abstain"],
                    probability,
                )
        region = point_regions[point.parameter_id]
        if region == "H0":
            error = accumulator["reject"]
            h0_errors.append(error)
        elif region == "H1":
            error = accumulator["certify"]
            h1_errors.append(error)
        else:
            error = _add(
                accumulator["certify"],
                accumulator["reject"],
            )
            indifference_errors.append(error)
        coverage_values.append(accumulator["coverage"])
        results[point.parameter_id] = {
            **accumulator,
            "region": region,
            "error": error,
        }

    return {
        "outcome_count": len(canonical_support),
        "point_results": results,
        "h0_wrong_reject_bound": _maximum(tuple(h0_errors)),
        "h1_wrong_certify_bound": _maximum(tuple(h1_errors)),
        "indifference_decisive_output_bound": _maximum(
            tuple(indifference_errors)
        ),
        "confidence_set_uniform_coverage": _minimum(
            tuple(coverage_values)
        ),
    }
