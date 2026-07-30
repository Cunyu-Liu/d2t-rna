"""Fail-closed support sizing for exact finite-system enumeration.

The raw dimensional limits are schema invariants.  Only after those invariants
have been revalidated may this module evaluate the weak-composition support
formula.  The capped product is deliberately completed before an outcome
iterator is constructed by :mod:`d2t_rna.exact.enumerate`.
"""

from __future__ import annotations

from math import comb
from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    RegisteredId,
    Sha256Hex,
)


MAX_STATES = 3
MAX_ACTIONS = 3
MAX_ALPHABET_SIZE = 4
MAX_JOINT_SAMPLE_SIZE = 40
MAX_SINGLE_ACTION_SAMPLE_SIZE = 80
JOINT_SUPPORT_LIMIT = 10_000_000

BoundedSampleSize = Annotated[
    StrictInt,
    Field(ge=0, le=MAX_SINGLE_ACTION_SAMPLE_SIZE),
]


class EnumerationTooLarge(RuntimeError):
    """Raised before enumeration when the registered support exceeds its cap."""

    def __init__(
        self,
        *,
        limit: int,
        partial_product: int,
        next_factor: int,
        action_id: str,
    ) -> None:
        self.limit = limit
        self.partial_product = partial_product
        self.next_factor = next_factor
        self.action_id = action_id
        super().__init__(
            "exact joint support exceeds the registered limit before "
            f"enumeration: partial_product={partial_product}, "
            f"next_factor={next_factor}, limit={limit}, "
            f"action_id={action_id!r}"
        )


class ExactActionSpec(FrozenContractModel):
    """One registered action and its finite multinomial observation space."""

    action_id: RegisteredId
    sample_size: BoundedSampleSize
    alphabet: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def alphabet_is_bounded_unique_and_canonical(self) -> "ExactActionSpec":
        if not self.alphabet:
            raise ValueError("an exact action alphabet cannot be empty")
        if len(self.alphabet) > MAX_ALPHABET_SIZE:
            if self.sample_size == 80 and len(self.alphabet) == 16:
                factor = comb(
                    self.sample_size + len(self.alphabet) - 1,
                    len(self.alphabet) - 1,
                )
                raise EnumerationTooLarge(
                    limit=JOINT_SUPPORT_LIMIT,
                    partial_product=1,
                    next_factor=factor,
                    action_id=self.action_id,
                )
            raise ValueError(
                f"an exact action alphabet cannot exceed "
                f"{MAX_ALPHABET_SIZE} symbols"
            )
        if len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("exact action alphabet symbols must be unique")
        if self.alphabet != tuple(sorted(self.alphabet)):
            raise ValueError(
                "exact action alphabet symbols must be canonically sorted"
            )
        return self


class ExactSupportSpec(FrozenContractModel):
    """Raw dimensions for one exact enumeration problem."""

    state_ids: tuple[RegisteredId, ...]
    actions: tuple[ExactActionSpec, ...]

    @model_validator(mode="after")
    def dimensions_are_bounded_unique_and_canonical(
        self,
    ) -> "ExactSupportSpec":
        if not self.state_ids:
            raise ValueError("exact state registry cannot be empty")
        if len(self.state_ids) > MAX_STATES:
            raise ValueError(
                f"exact state registry cannot exceed {MAX_STATES} states"
            )
        if len(set(self.state_ids)) != len(self.state_ids):
            raise ValueError("exact state IDs must be unique")
        if self.state_ids != tuple(sorted(self.state_ids)):
            raise ValueError("exact state IDs must be canonically sorted")

        if not self.actions:
            raise ValueError("exact action registry cannot be empty")
        if len(self.actions) > MAX_ACTIONS:
            raise ValueError(
                f"exact action registry cannot exceed {MAX_ACTIONS} actions"
            )
        action_ids = tuple(action.action_id for action in self.actions)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("exact action IDs must be unique")
        if action_ids != tuple(sorted(action_ids)):
            raise ValueError("exact actions must be sorted by action_id")

        if len(self.actions) == 1:
            if self.actions[0].sample_size > MAX_SINGLE_ACTION_SAMPLE_SIZE:
                raise ValueError(
                    "a single exact action cannot exceed sample size "
                    f"{MAX_SINGLE_ACTION_SAMPLE_SIZE}"
                )
        elif (
            sum(action.sample_size for action in self.actions)
            > MAX_JOINT_SAMPLE_SIZE
        ):
            raise ValueError(
                "multi-action exact sample size cannot exceed "
                f"{MAX_JOINT_SAMPLE_SIZE}"
            )
        return self


class ExactSupportPlan(FrozenContractModel):
    """Hash-bound result of the mandatory support preflight."""

    schema_id: Literal["d2t_rna.exact_support_plan"] = (
        "d2t_rna.exact_support_plan"
    )
    schema_version: Literal["1.0"] = "1.0"
    support_spec_hash: Sha256Hex
    per_action_support_sizes: tuple[NonNegativeInt, ...]
    joint_support_size: NonNegativeInt
    joint_support_limit: Literal[10_000_000] = JOINT_SUPPORT_LIMIT

    @model_validator(mode="after")
    def support_sizes_are_internally_consistent(self) -> "ExactSupportPlan":
        if not self.per_action_support_sizes:
            raise ValueError("support plan must contain at least one action")
        if len(self.per_action_support_sizes) > MAX_ACTIONS:
            raise ValueError(
                f"support plan cannot exceed {MAX_ACTIONS} actions"
            )
        if any(size <= 0 for size in self.per_action_support_sizes):
            raise ValueError("every exact per-action support must be positive")
        product = 1
        for size in self.per_action_support_sizes:
            if size > JOINT_SUPPORT_LIMIT // product:
                raise ValueError(
                    "support plan factors exceed the frozen joint support cap"
                )
            product *= size
        if product != self.joint_support_size:
            raise ValueError("joint support size does not match its factors")
        if self.joint_support_size > JOINT_SUPPORT_LIMIT:
            raise ValueError("validated support plan exceeds its stated limit")
        return self


def _strict_support_spec(spec: ExactSupportSpec) -> ExactSupportSpec:
    if type(spec) is not ExactSupportSpec:
        raise TypeError("spec must be exactly ExactSupportSpec")
    return strict_revalidate_contract_model(spec)


def validate_and_size_support(
    spec: ExactSupportSpec,
) -> ExactSupportPlan:
    """Revalidate raw caps, then compute the exact capped support product.

    No outcome iterator or support-sized collection is created in this
    function.  Multiplication is guarded as ``factor > limit // partial`` so a
    support crossing is rejected before the oversized product is formed.
    """

    rebuilt = _strict_support_spec(spec)
    per_action: list[int] = []
    partial_product = 1
    for action in rebuilt.actions:
        alphabet_size = len(action.alphabet)
        factor = comb(
            action.sample_size + alphabet_size - 1,
            alphabet_size - 1,
        )
        if factor > JOINT_SUPPORT_LIMIT // partial_product:
            raise EnumerationTooLarge(
                limit=JOINT_SUPPORT_LIMIT,
                partial_product=partial_product,
                next_factor=factor,
                action_id=action.action_id,
            )
        per_action.append(factor)
        partial_product *= factor

    return ExactSupportPlan(
        support_spec_hash=canonical_sha256(rebuilt),
        per_action_support_sizes=tuple(per_action),
        joint_support_size=partial_product,
        joint_support_limit=JOINT_SUPPORT_LIMIT,
    )


def replay_support_plan(
    spec: ExactSupportSpec,
    plan: ExactSupportPlan,
) -> ExactSupportPlan:
    """Recompute a plan from its raw spec and require canonical equality."""

    rebuilt_spec = _strict_support_spec(spec)
    if type(plan) is not ExactSupportPlan:
        raise TypeError("plan must be exactly ExactSupportPlan")
    rebuilt_plan = strict_revalidate_contract_model(plan)
    expected = validate_and_size_support(rebuilt_spec)
    if rebuilt_plan != expected:
        raise ValueError(
            "support plan does not exactly replay from the registered spec"
        )
    return expected
