"""Strict model policy and canonical JSON for D2T-RNA contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict


class CanonicalizationError(ValueError):
    """Raised when a value is outside the frozen canonical JSON domain."""


class DuplicateJsonKeyError(CanonicalizationError):
    """Raised when raw JSON contains a duplicate object key."""


class FrozenContractModel(BaseModel):
    """Base policy shared by every registered contract object."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )


def _normalize_canonical(value: object, *, path: str = "$") -> object:
    if isinstance(value, BaseModel):
        return _normalize_canonical(
            value.model_dump(
                mode="python",
                by_alias=True,
                exclude_none=False,
                exclude_unset=False,
                exclude_defaults=False,
            ),
            path=path,
        )
    if isinstance(value, Enum):
        return _normalize_canonical(value.value, path=path)
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        raise CanonicalizationError(
            f"{path}: binary floats are not in the canonical contract domain"
        )
    if isinstance(value, (list, tuple)):
        return [
            _normalize_canonical(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise CanonicalizationError(
                    f"{path}: object key {key!r} is not a string"
                )
            normalized[key] = _normalize_canonical(item, path=f"{path}.{key}")
        return normalized
    raise CanonicalizationError(
        f"{path}: unsupported canonical value type {type(value).__name__}"
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return the frozen compact UTF-8 JSON representation without a newline."""

    normalized = _normalize_canonical(value)
    try:
        text = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc
    return text.encode("utf-8")


def canonical_sha256(value: object) -> str:
    """Hash the exact frozen canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_token(token: str) -> None:
    raise CanonicalizationError(f"non-finite JSON token is forbidden: {token}")


ModelT = TypeVar("ModelT", bound=FrozenContractModel)


def validate_contract_json_syntax(
    raw: str | bytes | bytearray,
) -> str:
    """Return decoded JSON only after the shared raw-input safety checks."""

    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, (bytes, bytearray)):
        text = bytes(raw).decode("utf-8", errors="strict")
    else:
        raise TypeError("raw contract JSON must be str, bytes, or bytearray")

    try:
        loaded = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite_token,
        )
    except DuplicateJsonKeyError:
        raise
    except CanonicalizationError:
        raise
    except json.JSONDecodeError as exc:
        raise CanonicalizationError(str(exc)) from exc

    _normalize_canonical(loaded)
    return text


def parse_contract_json(
    model_type: type[ModelT],
    raw: str | bytes | bytearray,
) -> ModelT:
    """Parse strict JSON after duplicate-key and canonical-domain checks."""

    text = validate_contract_json_syntax(raw)
    return model_type.model_validate_json(text, strict=True)


def strict_revalidate_contract_model(value: ModelT) -> ModelT:
    """Rebuild an instance after detecting unchecked Pydantic field injection."""

    if not isinstance(value, FrozenContractModel):
        raise TypeError("value must be a FrozenContractModel instance")
    _assert_registered_model_storage(value)
    model_type = type(value)
    dumped = value.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=False,
        exclude_unset=False,
        exclude_defaults=False,
        round_trip=True,
    )
    return model_type.model_validate(dumped, strict=True)


def _assert_registered_model_storage(
    value: object,
    *,
    path: str = "$",
) -> None:
    if isinstance(value, FrozenContractModel):
        model_type = type(value)
        declared_fields = set(model_type.model_fields)
        stored_fields = set(vars(value))
        unexpected_fields = stored_fields - declared_fields
        missing_fields = declared_fields - stored_fields
        if unexpected_fields:
            names = ", ".join(sorted(unexpected_fields))
            raise ValueError(
                f"{path}: unchecked unregistered model fields: {names}"
            )
        if missing_fields:
            names = ", ".join(sorted(missing_fields))
            raise ValueError(f"{path}: unchecked missing model fields: {names}")
        for field_name in sorted(declared_fields):
            _assert_registered_model_storage(
                getattr(value, field_name),
                path=f"{path}.{field_name}",
            )
        return
    if isinstance(value, BaseModel):
        raise ValueError(
            f"{path}: nested model does not inherit FrozenContractModel"
        )
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_registered_model_storage(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_registered_model_storage(item, path=f"{path}.{key}")
