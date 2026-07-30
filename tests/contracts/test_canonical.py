from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import (
    CanonicalizationError,
    DuplicateJsonKeyError,
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
)
from d2t_rna.contracts.primitives import RegistryRef
from tests.exact.conftest import run_task4_isolated_child


GOLDEN_BYTES = b'{"a":1,"b":["x",true,null]}'
GOLDEN_SHA256 = "19fb8ce7a758416c9e53d8c73205499a05e0dbd8ecf36912bda14c7699a5afe1"


def test_canonical_json_has_a_golden_vector() -> None:
    value = {"b": ["x", True, None], "a": 1}
    assert canonical_json_bytes(value) == GOLDEN_BYTES
    assert canonical_sha256(value) == GOLDEN_SHA256


def test_key_order_does_not_change_bytes_or_hash() -> None:
    left = {"b": ["x", True, None], "a": 1}
    right = {"a": 1, "b": ["x", True, None]}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_sha256(left) == canonical_sha256(right)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), 0.5])
def test_all_binary_floats_are_rejected(bad: float) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({"nested": [bad]})


def test_raw_json_rejects_duplicate_keys() -> None:
    raw = b'{"registry_id":"first","registry_id":"second","registry_hash":"' + (
        b"a" * 64
    ) + b'"}'
    with pytest.raises(DuplicateJsonKeyError):
        parse_contract_json(RegistryRef, raw)


@pytest.mark.parametrize(
    "token",
    [b"NaN", b"Infinity", b"-Infinity"],
)
def test_raw_json_rejects_nonfinite_number_tokens(token: bytes) -> None:
    raw = b'{"registry_id":"x","registry_hash":' + token + b"}"
    with pytest.raises(CanonicalizationError):
        parse_contract_json(RegistryRef, raw)


def test_raw_json_rejects_invalid_utf8() -> None:
    with pytest.raises(UnicodeDecodeError):
        parse_contract_json(RegistryRef, b'{"registry_id":"\xff"}')


def test_raw_json_still_rejects_type_coercion() -> None:
    raw = b'{"registry_id":1,"registry_hash":"' + (b"a" * 64) + b'"}'
    with pytest.raises(ValidationError):
        parse_contract_json(RegistryRef, raw)


def test_hash_is_stable_across_processes_and_hash_seeds(
    tmp_path: Path,
) -> None:
    code = (
        "import json;"
        "from d2t_rna.contracts.base import canonical_sha256;"
        "print(json.dumps({"
        "'digest':canonical_sha256({'b':['x',True,None],'a':1}),"
        "'hash_probe':hash('d2t-rna-task4-seed-probe')"
        "},sort_keys=True))"
    )
    outputs: list[dict[str, object]] = []
    for process_index in range(4):
        completed = run_task4_isolated_child(
            child_artifact_dir=(
                tmp_path / f"canonical-hash-child-{process_index}"
            ),
            source=code,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(json.loads(completed.stdout))

    assert [output["digest"] for output in outputs] == [
        GOLDEN_SHA256
    ] * len(outputs)
    assert len({output["hash_probe"] for output in outputs}) > 1
