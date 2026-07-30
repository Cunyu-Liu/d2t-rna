from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import product

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import canonical_sha256
import d2t_rna.exact.enumerate as enumerate_module
from d2t_rna.exact.enumerate import (
    ExactLawError,
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
    iter_joint_outcomes,
    joint_outcome_probability,
    replay_probability_mass_audit,
    verify_probability_mass,
)

from .conftest import binary_support, law, rational


def _sequence_oracle(
    sample_size: int,
    probabilities: tuple[Fraction, ...],
) -> dict[tuple[int, ...], Fraction]:
    result: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
    for sequence in product(range(len(probabilities)), repeat=sample_size):
        counts = tuple(sequence.count(index) for index in range(len(probabilities)))
        mass = Fraction(1, 1)
        for symbol in sequence:
            mass *= probabilities[symbol]
        result[counts] += mass
    return dict(result)


def test_histograms_are_complete_unique_and_canonical() -> None:
    support = binary_support(sample_size=3)
    outcomes = tuple(iter_joint_outcomes(support))
    assert outcomes == (
        ((0, 3),),
        ((1, 2),),
        ((2, 1),),
        ((3, 0),),
    )
    assert len(outcomes) == len(set(outcomes)) == 4
    assert all(sum(outcome[0]) == 3 for outcome in outcomes)
    assert all(count >= 0 for outcome in outcomes for count in outcome[0])


def test_multinomial_fraction_mass_matches_independent_sequence_oracle() -> None:
    support = binary_support(sample_size=2)
    exact_law = law(
        support,
        ((1, 3), (2, 3)),
        law_id="law.binomial.two",
    )
    observed = {
        outcome[0]: joint_outcome_probability(support, exact_law, outcome)
        for outcome in iter_joint_outcomes(support)
    }
    expected = _sequence_oracle(2, (Fraction(1, 3), Fraction(2, 3)))
    assert observed == expected
    assert observed == {
        (0, 2): Fraction(4, 9),
        (1, 1): Fraction(4, 9),
        (2, 0): Fraction(1, 9),
    }

    audit = verify_probability_mass(support, exact_law)
    assert audit.total_probability == rational(1)
    assert audit.absolute_error == rational(0)
    assert audit.numerical_error_bound == rational(0)
    assert audit.outcome_count == 3
    assert audit.support_spec_hash == canonical_sha256(support)


def test_zero_probability_uses_exact_zero_to_zero_semantics() -> None:
    support = binary_support(sample_size=2)
    exact_law = law(
        support,
        ((0, 1), (1, 1)),
        law_id="law.degenerate",
    )
    probabilities = tuple(
        joint_outcome_probability(support, exact_law, outcome)
        for outcome in iter_joint_outcomes(support)
    )
    assert probabilities == (Fraction(1, 1), Fraction(0, 1), Fraction(0, 1))
    assert sum(probabilities, Fraction(0, 1)) == 1


def test_invalid_probability_laws_fail_closed_without_normalization() -> None:
    support = binary_support()
    support_hash = canonical_sha256(support)
    with pytest.raises(ValidationError):
        IndependentActionProbabilities(
            action_id="action.0",
            probabilities=(rational(-1, 2), rational(3, 2)),
        )
    with pytest.raises(ValidationError):
        IndependentActionProbabilities(
            action_id="action.0",
            probabilities=(rational(1, 3), rational(1, 3)),
        )
    with pytest.raises(ValidationError):
        IndependentActionProbabilities.model_validate(
            {
                "action_id": "action.0",
                "probabilities": (
                    {"numerator": 0.5, "denominator": 1},
                    {"numerator": 1, "denominator": 2},
                ),
            },
            strict=True,
        )

    spliced = IndependentMultinomialLaw(
        law_id="law.spliced",
        support_spec_hash=support_hash,
        action_probabilities=(
            IndependentActionProbabilities(
                action_id="action.other",
                probabilities=(rational(1, 2), rational(1, 2)),
            ),
        ),
    )
    with pytest.raises(ExactLawError, match="action"):
        verify_probability_mass(support, spliced)


def test_duplicate_missing_and_partial_streams_cannot_issue_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support(sample_size=2)
    exact_law = law(
        support,
        ((0, 1), (1, 1)),
        law_id="law.degenerate.stream-integrity",
    )
    canonical_outcomes = tuple(iter_joint_outcomes(support))

    monkeypatch.setattr(
        enumerate_module,
        "_joint_outcome_generator",
        lambda checked_support, plan: iter(
            (
                canonical_outcomes[0],
                canonical_outcomes[1],
                canonical_outcomes[1],
            )
        ),
    )
    with pytest.raises(ExactLawError, match="duplicate|increasing"):
        verify_probability_mass(support, exact_law)

    monkeypatch.setattr(
        enumerate_module,
        "_joint_outcome_generator",
        lambda checked_support, plan: iter(
            (
                canonical_outcomes[0],
                canonical_outcomes[2],
            )
        ),
    )
    with pytest.raises(ExactLawError, match="missing|partially"):
        verify_probability_mass(support, exact_law)

    def interrupted_stream(
        checked_support: object,
        plan: object,
    ):
        yield canonical_outcomes[0]
        raise RuntimeError("synthetic stream interruption")

    monkeypatch.setattr(
        enumerate_module,
        "_joint_outcome_generator",
        interrupted_stream,
    )
    with pytest.raises(RuntimeError, match="stream interruption"):
        verify_probability_mass(support, exact_law)


def test_probability_mass_audit_requires_full_raw_replay() -> None:
    support = binary_support(sample_size=2)
    exact_law = law(
        support,
        ((1, 3), (2, 3)),
        law_id="law.audit-replay",
    )
    authentic = verify_probability_mass(support, exact_law)
    assert (
        replay_probability_mass_audit(support, exact_law, authentic)
        == authentic
    )

    for forged in (
        authentic.model_copy(update={"outcome_count": 999}),
        authentic.model_copy(
            update={"enumeration_trace_hash": "f" * 64}
        ),
        authentic.model_copy(update={"law_hash": "e" * 64}),
        authentic.model_copy(update={"support_plan_hash": "d" * 64}),
    ):
        with pytest.raises(ExactLawError, match="replay"):
            replay_probability_mass_audit(support, exact_law, forged)
