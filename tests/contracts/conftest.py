from __future__ import annotations

from typing import Any


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64


def registry_ref(identifier: str = "registered.default") -> dict[str, Any]:
    return {
        "registry_id": identifier,
        "registry_hash": SHA_A,
    }


def proof_ref(identifier: str = "proof.default") -> dict[str, Any]:
    return {
        "proof_id": identifier,
        "artifact_hash": SHA_B,
    }
