"""Strict, deeply immutable primitives for contract schemas."""

from __future__ import annotations

from math import gcd
from typing import Annotated, Any

from pydantic import Field, StrictInt, StrictStr, model_validator

from .base import FrozenContractModel


Sha256Hex = Annotated[
    StrictStr,
    Field(pattern=r"^[0-9a-f]{64}$"),
]
RegisteredId = Annotated[
    StrictStr,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
]
SchemaVersion = Annotated[
    StrictStr,
    Field(pattern=r"^[0-9]+(?:\.[0-9]+){1,2}$"),
]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class Rational(FrozenContractModel):
    """A unique exact rational representation."""

    numerator: StrictInt
    denominator: StrictInt

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return data
        result = dict(data)
        numerator = result.get("numerator")
        denominator = result.get("denominator")
        if (
            type(numerator) is not int
            or type(denominator) is not int
            or denominator == 0
        ):
            return result
        if numerator == 0:
            result["numerator"] = 0
            result["denominator"] = 1
            return result
        if denominator < 0:
            numerator = -numerator
            denominator = -denominator
        divisor = gcd(abs(numerator), denominator)
        result["numerator"] = numerator // divisor
        result["denominator"] = denominator // divisor
        return result

    @model_validator(mode="after")
    def denominator_is_positive(self) -> "Rational":
        if self.denominator <= 0:
            raise ValueError("rational denominator must be positive")
        return self


class RegistryRef(FrozenContractModel):
    """Hash-addressed reference for a field whose member registry is external."""

    registry_id: RegisteredId
    registry_hash: Sha256Hex


class ObjectCommitment(FrozenContractModel):
    object_id: RegisteredId
    object_hash: Sha256Hex


class ProofArtifactRef(FrozenContractModel):
    proof_id: RegisteredId
    artifact_hash: Sha256Hex


class OverlapCount(FrozenContractModel):
    left_partition_id: RegisteredId
    right_partition_id: RegisteredId
    dependency_unit_level: RegistryRef
    count: NonNegativeInt


class NamedBound(FrozenContractModel):
    bound_id: RegisteredId
    value: Rational
