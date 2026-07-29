"""Pinned semantic registry for Task 2 probability contracts.

Registry membership authenticates an identifier and its declared role.  It does
not establish that a referenced scientific proof is correct.  Proof replay is a
separate gate in :mod:`d2t_rna.probability.risk`.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import (
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)


class SemanticRegistryError(ValueError):
    """Base class for pinned-registry failures."""


class UntrustedSemanticRegistryError(SemanticRegistryError):
    """Raised when a registry snapshot is not the Task 2 pinned snapshot."""


class RegistryResolutionError(SemanticRegistryError):
    """Raised when a reference cannot be resolved at its required role."""


class SemanticRegistryRole(str, Enum):
    OBSERVED_DATASET = "OBSERVED_DATASET"
    SUBSAMPLING_INDEX = "SUBSAMPLING_INDEX"
    OBSERVED_ESTIMAND = "OBSERVED_ESTIMAND"
    OBSERVED_TARGET = "OBSERVED_TARGET"
    SYNTHETIC_KNOWN_CHANNEL = "SYNTHETIC_KNOWN_CHANNEL"
    SYNTHETIC_ESTIMAND = "SYNTHETIC_ESTIMAND"
    SYNTHETIC_TARGET = "SYNTHETIC_TARGET"
    WITHIN_LIBRARY_ESTIMAND = "WITHIN_LIBRARY_ESTIMAND"
    WITHIN_LIBRARY_TARGET = "WITHIN_LIBRARY_TARGET"
    DEPENDENCY_UNIT = "DEPENDENCY_UNIT"
    OBSERVATION_WEIGHTING_LAW = "OBSERVATION_WEIGHTING_LAW"
    DUPLICATE_ESS_POLICY = "DUPLICATE_ESS_POLICY"
    FAILURE_POLICY = "FAILURE_POLICY"
    TEST_FIXTURE_VERIFIER = "TEST_FIXTURE_VERIFIER"
    FORMAL_PROOF_VERIFIER = "FORMAL_PROOF_VERIFIER"


class SemanticRegistryMember(FrozenContractModel):
    registry_id: RegisteredId
    role: SemanticRegistryRole
    member_hash: Sha256Hex


class TrustedSemanticRegistry(FrozenContractModel):
    schema_id: Literal["d2t_rna.semantic_registry"] = (
        "d2t_rna.semantic_registry"
    )
    schema_version: Literal["1.0"] = "1.0"
    members: tuple[SemanticRegistryMember, ...]

    @model_validator(mode="after")
    def members_are_unique_and_canonically_ordered(
        self,
    ) -> "TrustedSemanticRegistry":
        identifiers = tuple(member.registry_id for member in self.members)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("semantic registry contains duplicate member IDs")
        if identifiers != tuple(sorted(identifiers)):
            raise ValueError(
                "semantic registry members must be ordered by registry_id"
            )
        return self

    def ref(
        self,
        registry_id: str,
        expected_role: SemanticRegistryRole,
    ) -> RegistryRef:
        registry = ensure_trusted_task2_registry(self)
        member = _find_member(registry, registry_id)
        if member.role is not expected_role:
            raise RegistryResolutionError(
                f"{registry_id!r} has role {member.role.value}, "
                f"expected {expected_role.value}"
            )
        return RegistryRef(
            registry_id=member.registry_id,
            registry_hash=member.member_hash,
        )

TRUSTED_TASK2_REGISTRY_SHA256 = (
    "25604dac2cf94384d3c908293e2139c2f96321cb1582668647b651923fbb2c28"
)


def ensure_trusted_task2_registry(
    registry: TrustedSemanticRegistry,
) -> TrustedSemanticRegistry:
    """Strictly rebuild and authenticate the pinned Task 2 registry."""

    if type(registry) is not TrustedSemanticRegistry:
        raise TypeError("registry must be exactly TrustedSemanticRegistry")
    rebuilt = strict_revalidate_contract_model(registry)
    observed_hash = canonical_sha256(rebuilt)
    if observed_hash != TRUSTED_TASK2_REGISTRY_SHA256:
        raise UntrustedSemanticRegistryError(
            "semantic registry root mismatch: "
            f"expected {TRUSTED_TASK2_REGISTRY_SHA256}, got {observed_hash}"
        )
    return rebuilt


def _find_member(
    registry: TrustedSemanticRegistry,
    registry_id: str,
) -> SemanticRegistryMember:
    """Non-overridable lookup over an already exact, trusted registry."""

    if type(registry_id) is not str:
        raise TypeError("registry_id must be exactly str")
    for member in registry.members:
        if member.registry_id == registry_id:
            return member
    raise RegistryResolutionError(
        f"unregistered semantic member: {registry_id!r}"
    )


def load_trusted_task2_registry(
    raw: str | bytes | bytearray,
) -> TrustedSemanticRegistry:
    """Parse duplicate-safe JSON and authenticate its canonical root."""

    registry = parse_contract_json(TrustedSemanticRegistry, raw)
    return ensure_trusted_task2_registry(registry)


def resolve_registry_ref(
    reference: RegistryRef,
    registry: TrustedSemanticRegistry,
    expected_role: SemanticRegistryRole,
) -> SemanticRegistryMember:
    """Resolve an exact hash-addressed member at one required semantic role."""

    trusted = ensure_trusted_task2_registry(registry)
    if type(reference) is not RegistryRef:
        raise TypeError("reference must be exactly RegistryRef")
    rebuilt_reference = strict_revalidate_contract_model(reference)
    member = _find_member(trusted, rebuilt_reference.registry_id)
    if member.role is not expected_role:
        raise RegistryResolutionError(
            f"{member.registry_id!r} has role {member.role.value}, "
            f"expected {expected_role.value}"
        )
    if member.member_hash != rebuilt_reference.registry_hash:
        raise RegistryResolutionError(
            f"registry hash mismatch for {member.registry_id!r}"
        )
    return member


def require_registered_id(
    registry_id: str,
    registry: TrustedSemanticRegistry,
    expected_role: SemanticRegistryRole,
) -> SemanticRegistryMember:
    """Resolve an ID whose per-dataset content hash lives in another object."""

    trusted = ensure_trusted_task2_registry(registry)
    member = _find_member(trusted, registry_id)
    if member.role is not expected_role:
        raise RegistryResolutionError(
            f"{member.registry_id!r} has role {member.role.value}, "
            f"expected {expected_role.value}"
        )
    return member
