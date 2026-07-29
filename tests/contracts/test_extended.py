from __future__ import annotations

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.enums import ExtendedValueTag
from d2t_rna.contracts.extended import (
    FiniteExtendedValue,
    NotAvailableExtendedValue,
    PositiveInfinityExtendedValue,
    parse_extended_value,
)
from d2t_rna.contracts.base import DuplicateJsonKeyError
from d2t_rna.contracts.primitives import Rational


def test_all_extended_states_round_trip_without_bare_nonfinite_values() -> None:
    values = (
        FiniteExtendedValue(
            tag=ExtendedValueTag.FINITE,
            value=Rational(numerator=3, denominator=2),
        ),
        PositiveInfinityExtendedValue(tag=ExtendedValueTag.POS_INF),
        NotAvailableExtendedValue(tag=ExtendedValueTag.NA),
    )
    assert [value.model_dump(mode="json") for value in values] == [
        {"tag": "FINITE", "value": {"numerator": 3, "denominator": 2}},
        {"tag": "POS_INF"},
        {"tag": "NA"},
    ]
    assert parse_extended_value(values[0].model_dump_json()) == values[0]
    assert parse_extended_value(values[1].model_dump_json()) == values[1]
    assert parse_extended_value(values[2].model_dump_json()) == values[2]


@pytest.mark.parametrize(
    "payload",
    [
        {"tag": "FINITE"},
        {"tag": "FINITE", "value": "Infinity"},
        {"tag": "POS_INF", "value": None},
        {"tag": "NA", "value": None},
        {"tag": "NEG_INF"},
    ],
)
def test_extended_states_reject_ambiguous_or_unregistered_shapes(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        parse_extended_value(payload)


def test_extended_raw_json_rejects_duplicate_discriminator_keys() -> None:
    with pytest.raises(DuplicateJsonKeyError):
        parse_extended_value('{"tag":"NA","tag":"POS_INF"}')
