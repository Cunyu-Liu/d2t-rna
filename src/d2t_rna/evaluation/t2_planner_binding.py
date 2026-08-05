"""T2-5 planner/scenario binding (contract section 6.7 / task T2-5).

Task T2-5 binds the *accepted* T2 artifacts (T2b collision-or-separation,
T2c finite-sample bounds, T2d costed design / no-go) into the existing
exact/planner/scenario layer as a ``T2PlannerBinding``.  The binding is a
replayable common record, not a theorem re-derivation and not a real-data
validation.

Contract section 6.7 fixes the default semantics:

    scientific_claim_authorized             : false
    planner_status_is_theorem_proof         : false

Two reverse-upgrades are forbidden and fail closed here:

* a planner result of ``NO_CERTIFICATE_FOUND`` (or any planner-level
  infeasibility) must never be promoted to a *theorem* no-go; a theorem no-go
  is legitimate only when backed by an accepted T2c budget lower-bound or an
  accepted T2d costed-design no-go certificate;
* a synthetic model-conditional certificate must never be labeled as real-data
  validation.

The builder re-validates the referenced accepted acceptance manifests
(by content hash, status ``PASS``), re-validates the existing
:class:`PlannerClassification`, and emits a binding whose ``scientific_claim_authorized``
and ``real_data_validation_authorized`` are hard-``False``.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import StrictBool, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import Sha256Hex
from d2t_rna.exact.confidence import python_function_execution_sha256

from .planner import (
    PlannerClassification,
    PlannerRunStatus,
)

_T2_BINDING_PURPOSE = "T2_5_PLANNER_SCENARIO_BINDING_REPLAY"
_EXECUTION_HASHER = python_function_execution_sha256


class T2BindingRole(str, Enum):
    """The only uses allowed for accepted T2 artifacts (contract 6.7)."""

    DESIGN_CLASS_OBSTRUCTION = "DESIGN_CLASS_OBSTRUCTION"
    STRUCTURAL_INPUT = "STRUCTURAL_INPUT"


class T2NoGoBasis(str, Enum):
    """What may back a *theorem* no-go claim in a T2-5 binding."""

    NONE = "NONE"
    T2C_BUDGET_LOWER_BOUND = "T2C_BUDGET_LOWER_BOUND"
    T2D_COSTED_NO_GO_CERTIFICATE = "T2D_COSTED_NO_GO_CERTIFICATE"


_THEOREM_NO_GO_BASES = frozenset(
    {
        T2NoGoBasis.T2C_BUDGET_LOWER_BOUND,
        T2NoGoBasis.T2D_COSTED_NO_GO_CERTIFICATE,
    }
)


class T2AcceptedArtifactKind(str, Enum):
    """The accepted T2 acceptance manifests a binding may reference."""

    T2B_COLLISION_OR_SEPARATION = "T2B_COLLISION_OR_SEPARATION"
    T2C_FINITE_SAMPLE_BOUNDS = "T2C_FINITE_SAMPLE_BOUNDS"
    T2D_COSTED_DESIGN_NO_GO = "T2D_COSTED_DESIGN_NO_GO"


class T2AcceptedArtifactRef(FrozenContractModel):
    """Hash-bound reference to an accepted T2 acceptance manifest."""

    schema_id: Literal["d2t_rna.t2_accepted_artifact_ref"] = (
        "d2t_rna.t2_accepted_artifact_ref"
    )
    schema_version: Literal["1.0"] = "1.0"
    kind: T2AcceptedArtifactKind
    acceptance_manifest_sha256: Sha256Hex
    acceptance_status: Literal["PASS"] = "PASS"
    theorem_state: str

    @property
    def ref_sha256(self) -> str:
        return canonical_sha256(self)


def _build_t2_planner_binding_core(
    *,
    binding_role: T2BindingRole,
    accepted_artifacts: tuple[T2AcceptedArtifactRef, ...],
    acceptance_manifests_sha256: tuple[Sha256Hex, ...],
    planner_assessment: PlannerClassification,
    theorem_no_go_claimed: bool,
    theorem_no_go_basis: T2NoGoBasis,
    binding_execution_sha256: str,
) -> T2PlannerBinding:
    """Build a T2-5 binding without authorizing any scientific claim."""

    if type(binding_role) is not T2BindingRole:
        raise TypeError("binding_role must be exactly T2BindingRole")
    if type(theorem_no_go_basis) is not T2NoGoBasis:
        raise TypeError("theorem_no_go_basis must be exactly T2NoGoBasis")
    return T2PlannerBinding(
        binding_role=binding_role,
        accepted_artifacts=accepted_artifacts,
        acceptance_manifests_sha256=acceptance_manifests_sha256,
        planner_assessment=planner_assessment,
        planner_assessment_sha256=canonical_sha256(planner_assessment),
        theorem_no_go_claimed=theorem_no_go_claimed,
        theorem_no_go_basis=theorem_no_go_basis,
        binding_execution_sha256=binding_execution_sha256,
        binding_execution_replayed=True,
        serialized_bearer_authorization=False,
        scientific_claim_authorized=False,
        real_data_validation_authorized=False,
        planner_status_is_theorem_proof=False,
        synthetic_certificate_as_real_data_validation=False,
    )


_BUILDER_CORE = _build_t2_planner_binding_core


def _execution_sha256() -> str:
    if python_function_execution_sha256 is not _EXECUTION_HASHER:
        raise RuntimeError(
            "T2-5 binding execution hasher runtime identity changed"
        )
    if globals().get("_build_t2_planner_binding_core") is not _BUILDER_CORE:
        raise RuntimeError("T2-5 binding builder runtime identity changed")
    return python_function_execution_sha256(
        _BUILDER_CORE,
        purpose=_T2_BINDING_PURPOSE,
        strict_pure=False,
    )


def _assert_execution_closure() -> str:
    observed = _execution_sha256()
    if observed != _EXECUTION_BASELINE_SHA256:
        raise RuntimeError("T2-5 binding execution closure changed")
    return observed


class T2PlannerBinding(FrozenContractModel):
    """Replayable binding of accepted T2 artifacts to the planner layer.

    Every field is a data-container record; validation only re-checks the
    referenced acceptance manifests (status ``PASS``, content hash), re-validates
    the planner classification, and enforces the fail-closed guards below.
    """

    schema_id: Literal["d2t_rna.t2_planner_binding.v1"] = (
        "d2t_rna.t2_planner_binding.v1"
    )
    schema_version: Literal["1.0"] = "1.0"
    binding_role: T2BindingRole
    accepted_artifacts: tuple[T2AcceptedArtifactRef, ...]
    acceptance_manifests_sha256: tuple[Sha256Hex, ...]
    planner_assessment: PlannerClassification
    planner_assessment_sha256: Sha256Hex
    theorem_no_go_claimed: StrictBool
    theorem_no_go_basis: T2NoGoBasis
    binding_execution_sha256: Sha256Hex
    binding_execution_replayed: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    real_data_validation_authorized: Literal[False] = False
    planner_status_is_theorem_proof: Literal[False] = False
    synthetic_certificate_as_real_data_validation: Literal[False] = False

    @model_validator(mode="after")
    def binding_is_fail_closed(self) -> "T2PlannerBinding":
        execution_pre = _assert_execution_closure()

        if type(self.planner_assessment) is not PlannerClassification:
            raise TypeError(
                "planner_assessment must be exactly PlannerClassification"
            )
        checked_planner = strict_revalidate_contract_model(
            self.planner_assessment
        )
        if canonical_sha256(checked_planner) != self.planner_assessment_sha256:
            raise ValueError("planner assessment hash does not replay")

        if not self.accepted_artifacts or not self.acceptance_manifests_sha256:
            raise ValueError(
                "a T2-5 binding must reference at least one accepted T2 "
                "acceptance manifest"
            )
        if len(self.accepted_artifacts) != len(
            self.acceptance_manifests_sha256
        ):
            raise ValueError(
                "accepted artifact refs and manifest hashes must be parallel"
            )
        kinds: set[T2AcceptedArtifactKind] = set()
        for ref, manifest_sha256 in zip(
            self.accepted_artifacts, self.acceptance_manifests_sha256
        ):
            if type(ref) is not T2AcceptedArtifactRef:
                raise TypeError(
                    "accepted_artifacts entries must be exactly "
                    "T2AcceptedArtifactRef"
                )
            checked_ref = strict_revalidate_contract_model(ref)
            if ref.acceptance_status != "PASS":
                raise ValueError(
                    "a T2-5 binding may only reference PASS acceptance "
                    "manifests"
                )
            if ref.acceptance_manifest_sha256 != manifest_sha256:
                raise ValueError(
                    "accepted artifact ref and manifest hash do not agree"
                )
            if ref.kind in kinds:
                raise ValueError("duplicate accepted T2 artifact kind")
            kinds.add(ref.kind)

        # Fail-closed guard 1: a theorem no-go must be backed by an accepted
        # T2c/T2d no-go certificate, never by planner status alone.
        if self.theorem_no_go_claimed:
            if self.theorem_no_go_basis not in _THEOREM_NO_GO_BASES:
                raise ValueError(
                    "a theorem no-go claim requires an accepted T2c or T2d "
                    "no-go certificate basis"
                )
            if (
                self.theorem_no_go_basis is T2NoGoBasis.T2C_BUDGET_LOWER_BOUND
                and T2AcceptedArtifactKind.T2C_FINITE_SAMPLE_BOUNDS
                not in kinds
            ):
                raise ValueError(
                    "T2c-basis theorem no-go requires the accepted T2c "
                    "acceptance manifest"
                )
            if (
                self.theorem_no_go_basis is T2NoGoBasis.T2D_COSTED_NO_GO_CERTIFICATE
                and T2AcceptedArtifactKind.T2D_COSTED_DESIGN_NO_GO not in kinds
            ):
                raise ValueError(
                    "T2d-basis theorem no-go requires the accepted T2d "
                    "acceptance manifest"
                )
        else:
            if self.theorem_no_go_basis in _THEOREM_NO_GO_BASES:
                raise ValueError(
                    "theorem no-go basis requires theorem_no_go_claimed=True"
                )

        # Fail-closed guard 2: a planner NO_CERTIFICATE_FOUND is never a
        # theorem proof or a theorem no-go.
        if (
            checked_planner.planner_status
            is PlannerRunStatus.NO_CERTIFICATE_FOUND
            and self.theorem_no_go_claimed
        ):
            raise ValueError(
                "planner NO_CERTIFICATE_FOUND cannot be promoted to a "
                "theorem no-go"
            )

        # Fail-closed guard 3: a synthetic model-conditional certificate is
        # never real-data validation (hard-Literal above, re-asserted here).
        if self.real_data_validation_authorized:
            raise ValueError("a T2-5 binding never authorizes real-data validation")
        if self.planner_status_is_theorem_proof:
            raise ValueError("planner status is never a theorem proof")
        if self.synthetic_certificate_as_real_data_validation:
            raise ValueError(
                "a synthetic model-conditional certificate is never real-data validation"
            )
        if self.scientific_claim_authorized:
            raise ValueError("a T2-5 binding never authorizes a scientific claim")

        if self.binding_execution_sha256 != execution_pre:
            raise ValueError("T2-5 binding execution hash is stale")
        execution_post = _assert_execution_closure()
        if execution_post != execution_pre:
            raise RuntimeError(
                "T2-5 binding execution closure changed during replay"
            )
        return self

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self)


# Computed only after T2PlannerBinding is defined so the execution-closure
# hasher can resolve the forward global reference in _build_t2_planner_binding_core.
_EXECUTION_BASELINE_SHA256 = _execution_sha256()


def build_t2_planner_binding(
    *,
    binding_role: T2BindingRole,
    accepted_artifacts: tuple[T2AcceptedArtifactRef, ...],
    acceptance_manifests_sha256: tuple[Sha256Hex, ...],
    planner_assessment: PlannerClassification,
    theorem_no_go_claimed: bool = False,
    theorem_no_go_basis: T2NoGoBasis = T2NoGoBasis.NONE,
) -> T2PlannerBinding:
    """Build a T2-5 binding only under an unchanged execution closure."""

    execution_pre = _assert_execution_closure()
    binding = _BUILDER_CORE(
        binding_role=binding_role,
        accepted_artifacts=accepted_artifacts,
        acceptance_manifests_sha256=acceptance_manifests_sha256,
        planner_assessment=planner_assessment,
        theorem_no_go_claimed=theorem_no_go_claimed,
        theorem_no_go_basis=theorem_no_go_basis,
        binding_execution_sha256=execution_pre,
    )
    execution_post = _assert_execution_closure()
    if (
        execution_post != execution_pre
        or binding.binding_execution_sha256 != execution_pre
    ):
        raise RuntimeError(
            "T2-5 binding execution closure changed during build"
        )
    return binding


def replay_t2_planner_binding(
    binding: T2PlannerBinding,
) -> T2PlannerBinding:
    """Strictly rebuild and freshly re-validate a serialized T2-5 binding."""

    if type(binding) is not T2PlannerBinding:
        raise TypeError("binding must be exactly T2PlannerBinding")
    try:
        execution_pre = _assert_execution_closure()
        checked = strict_revalidate_contract_model(binding)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"T2-5 planner binding failed structural replay: {exc}"
        ) from exc
    if checked.binding_execution_sha256 != execution_pre:
        raise ValueError("T2-5 binding execution hash is stale")
    execution_post = _assert_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "T2-5 binding execution closure changed during replay"
        )
    return checked