"""Tagged finite, positive-infinity, and unresolved values."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import Field, TypeAdapter

from .base import (
    FrozenContractModel,
    canonical_json_bytes,
    validate_contract_json_syntax,
)
from .enums import ExtendedValueTag
from .primitives import Rational


class FiniteExtendedValue(FrozenContractModel):
    tag: Literal[ExtendedValueTag.FINITE]
    value: Rational


class PositiveInfinityExtendedValue(FrozenContractModel):
    tag: Literal[ExtendedValueTag.POS_INF]


class NotAvailableExtendedValue(FrozenContractModel):
    tag: Literal[ExtendedValueTag.NA]


ExtendedValue: TypeAlias = Annotated[
    FiniteExtendedValue
    | PositiveInfinityExtendedValue
    | NotAvailableExtendedValue,
    Field(discriminator="tag"),
]

_EXTENDED_ADAPTER = TypeAdapter(ExtendedValue)


def parse_extended_value(value: object) -> ExtendedValue:
    if isinstance(value, (str, bytes, bytearray)):
        checked_text = validate_contract_json_syntax(value)
        return _EXTENDED_ADAPTER.validate_json(checked_text, strict=True)
    if isinstance(
        value,
        (
            FiniteExtendedValue,
            PositiveInfinityExtendedValue,
            NotAvailableExtendedValue,
        ),
    ):
        return _EXTENDED_ADAPTER.validate_python(value, strict=True)
    return _EXTENDED_ADAPTER.validate_json(
        canonical_json_bytes(value),
        strict=True,
    )
