"""Exact lazy enumeration and independent multinomial mass verification."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Literal, TypeAlias

from pydantic import Field, StrictInt, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    Rational,
    RegisteredId,
    Sha256Hex,
)

from .support import (
    JOINT_SUPPORT_LIMIT,
    MAX_ACTIONS,
    MAX_ALPHABET_SIZE,
    ExactSupportPlan,
    ExactSupportSpec,
    replay_support_plan,
    validate_and_size_support,
)


CountVector: TypeAlias = tuple[int, ...]
JointOutcome: TypeAlias = tuple[CountVector, ...]


class ExactLawError(ValueError):
    """Raised when a probability law is not bound to the exact support."""


def _assert_fraction_runtime_integrity() -> None:
    """Defer to the shared guard after the exact package finishes importing."""

    from .confidence import (
        _assert_fraction_runtime_integrity as assert_shared_integrity,
    )

    assert_shared_integrity(
        module_aliases=(("d2t_rna.exact.enumerate", Fraction),)
    )


def _rational_fraction(value: Rational, *, label: str) -> Fraction:
    if type(value) is not Rational:
        raise TypeError(f"{label} must be exactly Rational")
    rebuilt = strict_revalidate_contract_model(value)
    return Fraction(rebuilt.numerator, rebuilt.denominator)


def _as_rational(value: Fraction) -> Rational:
    return Rational(numerator=value.numerator, denominator=value.denominator)


class IndependentActionProbabilities(FrozenContractModel):
    """Exact categorical probabilities for one registered action."""

    action_id: RegisteredId
    probabilities: tuple[Rational, ...]

    @model_validator(mode="after")
    def probabilities_are_exact_normalized_and_bounded(
        self,
    ) -> "IndependentActionProbabilities":
        _assert_fraction_runtime_integrity()
        if not self.probabilities:
            raise ValueError("an exact action probability vector cannot be empty")
        if len(self.probabilities) > MAX_ALPHABET_SIZE:
            raise ValueError(
                "an exact action probability vector cannot exceed "
                f"{MAX_ALPHABET_SIZE} entries"
            )
        total = Fraction(0, 1)
        for index, probability in enumerate(self.probabilities):
            value = _rational_fraction(
                probability,
                label=f"probabilities[{index}]",
            )
            if value < 0 or value > 1:
                raise ValueError(
                    "exact categorical probabilities must lie in [0, 1]"
                )
            total += value
        if total != 1:
            raise ValueError(
                "exact categorical probabilities must sum to exactly one"
            )
        return self


class IndependentMultinomialLaw(FrozenContractModel):
    """A hash-bound product of registered per-action multinomial laws."""

    law_id: RegisteredId
    support_spec_hash: Sha256Hex
    action_probabilities: tuple[IndependentActionProbabilities, ...]

    @model_validator(mode="after")
    def actions_are_nonempty_unique_and_canonical(
        self,
    ) -> "IndependentMultinomialLaw":
        if not self.action_probabilities:
            raise ValueError("an independent multinomial law cannot be empty")
        if len(self.action_probabilities) > MAX_ACTIONS:
            raise ValueError(
                "an independent multinomial law cannot exceed "
                f"{MAX_ACTIONS} actions"
            )
        action_ids = tuple(
            action.action_id for action in self.action_probabilities
        )
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("law action IDs must be unique")
        if action_ids != tuple(sorted(action_ids)):
            raise ValueError("law actions must be sorted by action_id")
        return self


class ProbabilityMassAudit(FrozenContractModel):
    """Canonical exact-enumeration receipt for one support/law pair."""

    schema_id: Literal["d2t_rna.probability_mass_audit"] = (
        "d2t_rna.probability_mass_audit"
    )
    schema_version: Literal["1.0"] = "1.0"
    support_spec_hash: Sha256Hex
    support_plan_hash: Sha256Hex
    law_hash: Sha256Hex
    enumeration_trace_hash: Sha256Hex
    total_probability: Rational
    absolute_error: Rational
    numerical_error_bound: Rational
    outcome_count: NonNegativeInt

    @model_validator(mode="after")
    def receipt_is_an_exact_complete_mass_audit(
        self,
    ) -> "ProbabilityMassAudit":
        _assert_fraction_runtime_integrity()
        if _rational_fraction(
            self.total_probability,
            label="total_probability",
        ) != 1:
            raise ValueError("exact probability mass audit must account for one")
        if _rational_fraction(self.absolute_error, label="absolute_error") != 0:
            raise ValueError("exact probability mass audit error must be zero")
        if (
            _rational_fraction(
                self.numerical_error_bound,
                label="numerical_error_bound",
            )
            != 0
        ):
            raise ValueError(
                "Fraction enumeration must have zero numerical error bound"
            )
        if self.outcome_count <= 0:
            raise ValueError("exact probability mass audit cannot be empty")
        if self.outcome_count > JOINT_SUPPORT_LIMIT:
            raise ValueError(
                "exact probability mass audit exceeds the frozen support cap"
            )
        return self


@dataclass(frozen=True, slots=True)
class _BoundIndependentMultinomialLaw:
    """Runtime-only result of one complete support/law preflight."""

    support: ExactSupportSpec
    plan: ExactSupportPlan
    law: IndependentMultinomialLaw
    support_spec_hash: str
    support_plan_hash: str
    law_hash: str
    probabilities: tuple[tuple[Fraction, ...], ...]


def _strict_support_and_plan(
    support: ExactSupportSpec,
) -> tuple[ExactSupportSpec, ExactSupportPlan]:
    if type(support) is not ExactSupportSpec:
        raise TypeError("support must be exactly ExactSupportSpec")
    rebuilt = strict_revalidate_contract_model(support)
    plan = validate_and_size_support(rebuilt)
    return rebuilt, plan


def _strict_law(law: IndependentMultinomialLaw) -> IndependentMultinomialLaw:
    if type(law) is not IndependentMultinomialLaw:
        raise TypeError("law must be exactly IndependentMultinomialLaw")
    return strict_revalidate_contract_model(law)


def _bind_law(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
) -> IndependentMultinomialLaw:
    rebuilt_law = _strict_law(law)
    observed_support_hash = canonical_sha256(support)
    if rebuilt_law.support_spec_hash != observed_support_hash:
        raise ExactLawError(
            "law support hash does not match the exact support specification"
        )

    support_action_ids = tuple(
        action.action_id for action in support.actions
    )
    law_action_ids = tuple(
        action.action_id for action in rebuilt_law.action_probabilities
    )
    if law_action_ids != support_action_ids:
        raise ExactLawError(
            "law action registry does not exactly match the support actions"
        )
    for action, probabilities in zip(
        support.actions,
        rebuilt_law.action_probabilities,
        strict=True,
    ):
        if len(probabilities.probabilities) != len(action.alphabet):
            raise ExactLawError(
                f"law alphabet dimension does not match action "
                f"{action.action_id!r}"
            )
    return rebuilt_law


def _bind_exact_problem(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
) -> _BoundIndependentMultinomialLaw:
    _assert_fraction_runtime_integrity()
    rebuilt_support, plan = _strict_support_and_plan(support)
    rebuilt_law = _bind_law(rebuilt_support, law)
    return _BoundIndependentMultinomialLaw(
        support=rebuilt_support,
        plan=plan,
        law=rebuilt_law,
        support_spec_hash=canonical_sha256(rebuilt_support),
        support_plan_hash=canonical_sha256(plan),
        law_hash=canonical_sha256(rebuilt_law),
        probabilities=tuple(
            tuple(
                Fraction(value.numerator, value.denominator)
                for value in action.probabilities
            )
            for action in rebuilt_law.action_probabilities
        ),
    )


def _weak_compositions(
    total: int,
    parts: int,
    prefix: CountVector = (),
) -> Iterator[CountVector]:
    if parts == 1:
        yield prefix + (total,)
        return
    for first in range(total + 1):
        yield from _weak_compositions(
            total - first,
            parts - 1,
            prefix + (first,),
        )


def _joint_outcome_generator_inner(
    support: ExactSupportSpec,
) -> Iterator[JointOutcome]:
    """Yield the canonical Cartesian support after a replayed preflight."""
    def visit(
        action_index: int,
        prefix: JointOutcome,
    ) -> Iterator[JointOutcome]:
        if action_index == len(support.actions):
            yield prefix
            return
        action = support.actions[action_index]
        for counts in _weak_compositions(
            action.sample_size,
            len(action.alphabet),
        ):
            yield from visit(action_index + 1, prefix + (counts,))

    yield from visit(0, ())


def _joint_outcome_generator(
    support: ExactSupportSpec,
    plan: ExactSupportPlan,
) -> Iterator[JointOutcome]:
    """Synchronously replay the plan before constructing the inner iterator."""

    replayed = replay_support_plan(support, plan)
    if canonical_sha256(support) != replayed.support_spec_hash:
        raise ExactLawError("support plan hash binding changed before enumeration")
    return _joint_outcome_generator_inner(support)


def iter_joint_outcomes(
    support: ExactSupportSpec,
) -> Iterator[JointOutcome]:
    """Synchronously preflight support, then return its internal generator."""

    rebuilt, plan = _strict_support_and_plan(support)
    return _joint_outcome_generator(rebuilt, plan)


def _validated_outcome(
    support: ExactSupportSpec,
    outcome: JointOutcome,
) -> JointOutcome:
    if type(outcome) is not tuple:
        raise ExactLawError("joint outcome must be exactly a tuple")
    if len(outcome) != len(support.actions):
        raise ExactLawError("joint outcome action dimension mismatch")

    checked: list[CountVector] = []
    for action, counts in zip(support.actions, outcome, strict=True):
        if type(counts) is not tuple:
            raise ExactLawError("each action count vector must be a tuple")
        if len(counts) != len(action.alphabet):
            raise ExactLawError(
                f"outcome alphabet dimension mismatch for "
                f"{action.action_id!r}"
            )
        if any(type(count) is not int or count < 0 for count in counts):
            raise ExactLawError(
                "outcome counts must be non-negative exact integers"
            )
        if sum(counts) != action.sample_size:
            raise ExactLawError(
                f"outcome counts do not sum to sample size for "
                f"{action.action_id!r}"
            )
        checked.append(counts)
    return tuple(checked)


def _multinomial_probability(
    counts: CountVector,
    probabilities: tuple[Fraction, ...],
) -> Fraction:
    coefficient = 1
    remaining = sum(counts)
    for count in counts:
        coefficient *= comb(remaining, count)
        remaining -= count

    result = Fraction(coefficient, 1)
    for count, probability in zip(counts, probabilities, strict=True):
        if count:
            result *= probability**count
    return result


def _joint_probability_bound(
    probabilities: tuple[tuple[Fraction, ...], ...],
    outcome: JointOutcome,
) -> Fraction:
    result = Fraction(1, 1)
    for counts, action_probabilities in zip(
        outcome,
        probabilities,
        strict=True,
    ):
        result *= _multinomial_probability(counts, action_probabilities)
    return result


def joint_outcome_probability(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
    outcome: JointOutcome,
) -> Fraction:
    """Return one exact Fraction mass after full support/law binding checks."""

    _assert_fraction_runtime_integrity()
    bound = _bind_exact_problem(support, law)
    rebuilt_outcome = _validated_outcome(bound.support, outcome)
    result = _joint_probability_bound(bound.probabilities, rebuilt_outcome)
    _assert_fraction_runtime_integrity()
    return result


def _bound_outcome_probability_generator(
    bound: _BoundIndependentMultinomialLaw,
) -> Iterator[tuple[JointOutcome, Fraction]]:
    """Yield a validated complete stream using constant integrity state."""

    previous_outcome: JointOutcome | None = None
    outcome_count = 0
    for raw_outcome in _joint_outcome_generator(bound.support, bound.plan):
        outcome = _validated_outcome(bound.support, raw_outcome)
        if previous_outcome is not None and outcome <= previous_outcome:
            raise ExactLawError(
                "joint outcome stream is duplicate or not strictly increasing"
            )
        outcome_count += 1
        if outcome_count > bound.plan.joint_support_size:
            raise ExactLawError(
                "joint outcome stream exceeds the validated support size"
            )
        yield (
            outcome,
            _joint_probability_bound(bound.probabilities, outcome),
        )
        previous_outcome = outcome

    if outcome_count != bound.plan.joint_support_size:
        raise ExactLawError(
            "joint outcome stream is missing or only partially enumerated"
        )
    _assert_fraction_runtime_integrity()


def iter_joint_outcome_probabilities(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
) -> Iterator[tuple[JointOutcome, Fraction]]:
    """Synchronously bind one law, then stream validated outcome/mass pairs.

    This is the coverage-engine fast path: Pydantic revalidation, support
    sizing, and all support/law/hash checks occur once before the internal
    iterator is returned.  Every yielded outcome is still shape-checked, and
    full exhaustion verifies strict order and completeness without a set.
    """

    bound = _bind_exact_problem(support, law)
    return _bound_outcome_probability_generator(bound)


def _update_trace(
    digest: "hashlib._Hash",
    value: object,
) -> None:
    payload = canonical_json_bytes(value)
    digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
    digest.update(payload)


def verify_probability_mass(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
) -> ProbabilityMassAudit:
    """Stream the entire finite support and issue an exact zero-error receipt."""

    _assert_fraction_runtime_integrity()
    bound = _bind_exact_problem(support, law)

    digest = hashlib.sha256()
    _update_trace(
        digest,
        {
            "enumerator": "d2t_rna.independent_multinomial.v1",
            "support_spec_hash": bound.support_spec_hash,
            "support_plan_hash": bound.support_plan_hash,
            "law_hash": bound.law_hash,
        },
    )

    total = Fraction(0, 1)
    outcome_count = 0
    for outcome, probability in _bound_outcome_probability_generator(bound):
        total += probability
        outcome_count += 1
        _update_trace(
            digest,
            {
                "outcome": outcome,
                "probability": _as_rational(probability),
            },
        )

    if outcome_count != bound.plan.joint_support_size:
        raise ExactLawError(
            "enumerator outcome count does not match the validated support plan"
        )
    absolute_error = abs(total - Fraction(1, 1))
    if absolute_error != 0:
        raise ExactLawError(
            "independent multinomial mass does not sum to exactly one"
        )

    audit = ProbabilityMassAudit(
        support_spec_hash=bound.support_spec_hash,
        support_plan_hash=bound.support_plan_hash,
        law_hash=bound.law_hash,
        enumeration_trace_hash=digest.hexdigest(),
        total_probability=_as_rational(total),
        absolute_error=_as_rational(absolute_error),
        numerical_error_bound=Rational(numerator=0, denominator=1),
        outcome_count=outcome_count,
    )
    _assert_fraction_runtime_integrity()
    return audit


def replay_probability_mass_audit(
    support: ExactSupportSpec,
    law: IndependentMultinomialLaw,
    audit: ProbabilityMassAudit,
) -> ProbabilityMassAudit:
    """Re-enumerate the raw law and require exact receipt equality."""

    _assert_fraction_runtime_integrity()
    if type(audit) is not ProbabilityMassAudit:
        raise TypeError("audit must be exactly ProbabilityMassAudit")
    rebuilt_audit = strict_revalidate_contract_model(audit)
    expected = verify_probability_mass(support, law)
    if rebuilt_audit != expected:
        raise ExactLawError(
            "probability mass audit does not replay from support and law"
        )
    _assert_fraction_runtime_integrity()
    return expected
