from __future__ import annotations

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.primitives import Rational, RegistryRef

from .conftest import SHA_A


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (2, 4, (1, 2)),
        (2, -4, (-1, 2)),
        (0, -9, (0, 1)),
        (-6, -8, (3, 4)),
    ],
)
def test_rational_has_one_canonical_representation(
    numerator: int,
    denominator: int,
    expected: tuple[int, int],
) -> None:
    value = Rational(numerator=numerator, denominator=denominator)
    assert (value.numerator, value.denominator) == expected


@pytest.mark.parametrize(
    ("numerator", "denominator"),
    [
        (1, 0),
        (True, 1),
        (1, False),
        (1.0, 2),
        (1, 2.0),
    ],
)
def test_rational_rejects_invalid_or_coerced_values(
    numerator: object,
    denominator: object,
) -> None:
    with pytest.raises(ValidationError):
        Rational(numerator=numerator, denominator=denominator)


def test_hash_fields_require_lowercase_sha256() -> None:
    RegistryRef(registry_id="registry.example", registry_hash=SHA_A)
    with pytest.raises(ValidationError):
        RegistryRef(registry_id="registry.example", registry_hash=SHA_A.upper())
    with pytest.raises(ValidationError):
        RegistryRef(registry_id="registry.example", registry_hash="a" * 63)
