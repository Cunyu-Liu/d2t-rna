from __future__ import annotations

from math import comb

import pytest
from pydantic import ValidationError

import d2t_rna.exact.enumerate as enumerate_module
from d2t_rna.exact.enumerate import iter_joint_outcomes
from d2t_rna.exact.support import (
    JOINT_SUPPORT_LIMIT,
    EnumerationTooLarge,
    ExactActionSpec,
    ExactSupportPlan,
    ExactSupportSpec,
    replay_support_plan,
    validate_and_size_support,
)


def _action(action_id: str, sample_size: int, alphabet_size: int) -> ExactActionSpec:
    return ExactActionSpec(
        action_id=action_id,
        sample_size=sample_size,
        alphabet=tuple(
            f"symbol.{action_id}.{index}" for index in range(alphabet_size)
        ),
    )


def _spec(sample_sizes: tuple[int, ...], alphabet_size: int = 4) -> ExactSupportSpec:
    return ExactSupportSpec(
        state_ids=("state.0", "state.1", "state.2"),
        actions=tuple(
            _action(f"action.{index}", sample_size, alphabet_size)
            for index, sample_size in enumerate(sample_sizes)
        ),
    )


def test_support_formula_and_cap_crossing_are_exact() -> None:
    allowed = validate_and_size_support(_spec((8, 9, 9)))
    assert allowed.per_action_support_sizes == (
        comb(11, 3),
        comb(12, 3),
        comb(12, 3),
    )
    assert allowed.joint_support_size == 7_986_000
    assert allowed.joint_support_size <= JOINT_SUPPORT_LIMIT

    with pytest.raises(EnumerationTooLarge) as exc_info:
        validate_and_size_support(_spec((9, 9, 9)))
    assert exc_info.value.limit == JOINT_SUPPORT_LIMIT
    assert exc_info.value.partial_product <= JOINT_SUPPORT_LIMIT
    assert exc_info.value.next_factor == comb(12, 3)


def test_oversized_support_fails_before_joint_iterator_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_iterator(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("joint iterator was created before support preflight")

    monkeypatch.setattr(
        enumerate_module,
        "_joint_outcome_generator",
        forbidden_iterator,
    )
    with pytest.raises(EnumerationTooLarge):
        iter_joint_outcomes(_spec((13, 13, 14)))
    assert calls == 0


def test_raw_dimension_caps_fail_before_support_combinatorics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def forbidden_comb(*args: object, **kwargs: object) -> int:
        nonlocal calls
        calls += 1
        raise AssertionError("comb called before raw dimension checks")

    monkeypatch.setattr("d2t_rna.exact.support.comb", forbidden_comb)
    with pytest.raises(ValidationError):
        ExactActionSpec(
            action_id="action.invalid",
            sample_size=1,
            alphabet=tuple(f"symbol.{index}" for index in range(5)),
        )
    with pytest.raises(ValidationError):
        ExactSupportSpec(
            state_ids=("s0", "s1", "s2", "s3"),
            actions=(_action("action.0", 1, 2),),
        )
    with pytest.raises(ValidationError):
        _spec((10, 10, 10, 10), alphabet_size=2)
    assert calls == 0


def test_m16_n80_raises_enumeration_too_large_before_iterator() -> None:
    with pytest.raises(EnumerationTooLarge) as exc_info:
        ExactActionSpec(
            action_id="action.invalid-large",
            sample_size=80,
            alphabet=tuple(f"symbol.{index:02d}" for index in range(16)),
        )
    assert exc_info.value.limit == JOINT_SUPPORT_LIMIT
    assert exc_info.value.partial_product == 1
    assert exc_info.value.next_factor > JOINT_SUPPORT_LIMIT


def test_single_action_and_joint_total_limits_are_distinct() -> None:
    single = ExactSupportSpec(
        state_ids=("state.0",),
        actions=(_action("action.0", 80, 4),),
    )
    assert validate_and_size_support(single).joint_support_size == comb(83, 3)

    with pytest.raises(ValidationError):
        ExactSupportSpec(
            state_ids=("state.0",),
            actions=(_action("action.0", 81, 4),),
        )
    assert validate_and_size_support(_spec((20, 20), 2)).joint_support_size > 0
    with pytest.raises(ValidationError):
        _spec((20, 21), 2)


@pytest.mark.parametrize(
    "state_ids",
    [
        (),
        ("state.0", "state.1", "state.2", "state.3"),
        ("state.0", "state.0"),
        ("state.1", "state.0"),
    ],
)
def test_state_registry_is_nonempty_bounded_unique_and_canonical(
    state_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        ExactSupportSpec(
            state_ids=state_ids,
            actions=(_action("action.0", 1, 2),),
        )


def test_action_and_alphabet_registries_reject_duplicate_or_unsorted_ids() -> None:
    for alphabet in (
        ("symbol.0", "symbol.0"),
        ("symbol.1", "symbol.0"),
    ):
        with pytest.raises(ValidationError):
            ExactActionSpec(
                action_id="action.0",
                sample_size=1,
                alphabet=alphabet,
            )

    action_zero = _action("action.0", 1, 2)
    action_one = _action("action.1", 1, 2)
    for actions in (
        (action_zero, action_zero),
        (action_one, action_zero),
    ):
        with pytest.raises(ValidationError):
            ExactSupportSpec(
                state_ids=("state.0",),
                actions=actions,
            )


def test_support_plan_cannot_expand_cap_or_impersonate_another_spec() -> None:
    with pytest.raises(ValidationError):
        ExactSupportPlan(
            support_spec_hash="a" * 64,
            per_action_support_sizes=(1, 1, 1, 1),
            joint_support_size=1,
            joint_support_limit=JOINT_SUPPORT_LIMIT,
        )
    with pytest.raises(ValidationError):
        ExactSupportPlan.model_validate(
            {
                "support_spec_hash": "a" * 64,
                "per_action_support_sizes": (JOINT_SUPPORT_LIMIT + 1,),
                "joint_support_size": JOINT_SUPPORT_LIMIT + 1,
                "joint_support_limit": JOINT_SUPPORT_LIMIT + 1,
            },
            strict=True,
        )

    spec = _spec((1,), alphabet_size=2)
    authentic = validate_and_size_support(spec)
    forged = authentic.model_copy(
        update={
            "per_action_support_sizes": (1,),
            "joint_support_size": 1,
        }
    )
    with pytest.raises(ValueError, match="replay"):
        replay_support_plan(spec, forged)
