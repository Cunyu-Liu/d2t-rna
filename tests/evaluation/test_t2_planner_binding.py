"""Tests for T2-5 planner/scenario binding (contract section 6.7 / T2-5).

Covers the fail-closed binding semantics:

* a binding references accepted PASS T2 acceptance manifests (T2b/T2c/T2d);
* a theorem no-go is only allowed when backed by an accepted T2c or T2d
  no-go certificate;
* a planner ``NO_CERTIFICATE_FOUND`` is never promoted to a theorem no-go;
* ``scientific_claim_authorized``, ``real_data_validation_authorized``,
  ``planner_status_is_theorem_proof`` and
  ``synthetic_certificate_as_real_data_validation`` are all hard-``False``;
* builder / replay run under an unchanged execution closure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.enums import PlannerFailureState
from d2t_rna.evaluation.milp_check import (
    BoundedMilpModel,
    ConstraintSense,
    FeasibilityScope,
    IntegerVariable,
    LinearConstraint,
    LinearTerm,
)
from d2t_rna.evaluation.planner import (
    PlannerRunStatus,
    PlannerTerminationReason,
    RegisteredPlannerResult,
    classify_planner_result,
)
from d2t_rna.evaluation.t2_planner_binding import (
    T2AcceptedArtifactKind,
    T2AcceptedArtifactRef,
    T2BindingRole,
    T2NoGoBasis,
    build_t2_planner_binding,
    replay_t2_planner_binding,
)
from d2t_rna.contracts.primitives import Rational, RegistryRef


def _r(value: int) -> Rational:
    return Rational(numerator=value, denominator=1)


def _model() -> BoundedMilpModel:
    return BoundedMilpModel(
        model_id="fixed-horizon-test",
        fixed_horizon=2,
        available_control_library=RegistryRef(
            registry_id="available-controls",
            registry_hash="a" * 64,
        ),
        registered_design_class=RegistryRef(
            registry_id="registered-designs",
            registry_hash="b" * 64,
        ),
        variables=(
            IntegerVariable(
                variable_id="x",
                lower_bound=0,
                upper_bound=1,
            ),
            IntegerVariable(
                variable_id="y",
                lower_bound=0,
                upper_bound=1,
            ),
        ),
        available_control_variable_ids=("x",),
        constraints=(
            LinearConstraint(
                constraint_id="coverage",
                terms=(
                    LinearTerm(variable_id="x", coefficient=_r(1)),
                    LinearTerm(variable_id="y", coefficient=_r(1)),
                ),
                sense=ConstraintSense.GREATER_THAN_OR_EQUAL,
                rhs=_r(2),
            ),
        ),
    )


def _not_found(model: BoundedMilpModel) -> RegisteredPlannerResult:
    return RegisteredPlannerResult(
        model_sha256=model.model_sha256,
        status=PlannerRunStatus.NO_CERTIFICATE_FOUND,
        witness=(),
        states_examined=1,
        termination_reason=PlannerTerminationReason.REGISTERED_SEARCH_EXHAUSTED,
        planner_configuration_sha256="c" * 64,
        planner_code_sha256="d" * 64,
    )


def _t2b_ref() -> T2AcceptedArtifactRef:
    return T2AcceptedArtifactRef(
        kind=T2AcceptedArtifactKind.T2B_COLLISION_OR_SEPARATION,
        acceptance_manifest_sha256="1" * 64,
        acceptance_status="PASS",
        theorem_state="T2_COLLISION_OR_SEPARATION_ACCEPTED",
    )


def _t2c_ref() -> T2AcceptedArtifactRef:
    return T2AcceptedArtifactRef(
        kind=T2AcceptedArtifactKind.T2C_FINITE_SAMPLE_BOUNDS,
        acceptance_manifest_sha256="2" * 64,
        acceptance_status="PASS",
        theorem_state="T2_SAMPLE_COMPLEXITY_BOUND_ACCEPTED",
    )


def _t2d_ref() -> T2AcceptedArtifactRef:
    return T2AcceptedArtifactRef(
        kind=T2AcceptedArtifactKind.T2D_COSTED_DESIGN_NO_GO,
        acceptance_manifest_sha256="3" * 64,
        acceptance_status="PASS",
        theorem_state="T2_COSTED_DESIGN_NO_GO_ACCEPTED",
    )


def _structural_binding() -> "object":
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    assert planner.failure_state is (
        PlannerFailureState.NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER
    )
    return build_t2_planner_binding(
        binding_role=T2BindingRole.STRUCTURAL_INPUT,
        accepted_artifacts=(_t2b_ref(),),
        acceptance_manifests_sha256=("1" * 64,),
        planner_assessment=planner,
        theorem_no_go_claimed=False,
        theorem_no_go_basis=T2NoGoBasis.NONE,
    )


def test_structural_binding_is_fail_closed() -> None:
    binding = _structural_binding()
    assert binding.binding_role is T2BindingRole.STRUCTURAL_INPUT
    assert binding.scientific_claim_authorized is False
    assert binding.real_data_validation_authorized is False
    assert binding.planner_status_is_theorem_proof is False
    assert binding.synthetic_certificate_as_real_data_validation is False
    assert binding.theorem_no_go_claimed is False
    assert binding.binding_execution_replayed is True


def test_replay_structural_binding() -> None:
    binding = _structural_binding()
    replayed = replay_t2_planner_binding(binding)
    assert replayed.binding_sha256 == binding.binding_sha256


def test_planner_no_certificate_cannot_be_theorem_no_go() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.DESIGN_CLASS_OBSTRUCTION,
            accepted_artifacts=(_t2d_ref(),),
            acceptance_manifests_sha256=("3" * 64,),
            planner_assessment=planner,
            theorem_no_go_claimed=True,
            theorem_no_go_basis=T2NoGoBasis.T2D_COSTED_NO_GO_CERTIFICATE,
        )


def test_theorem_no_go_requires_t2c_or_t2d_basis() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    # NONE basis with claimed no-go is rejected even before the planner check.
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.DESIGN_CLASS_OBSTRUCTION,
            accepted_artifacts=(_t2b_ref(),),
            acceptance_manifests_sha256=("1" * 64,),
            planner_assessment=planner,
            theorem_no_go_claimed=True,
            theorem_no_go_basis=T2NoGoBasis.NONE,
        )


def test_t2c_basis_requires_t2c_acceptance() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    # T2c basis but only a T2b manifest referenced -> rejected by planner
    # no-go guard anyway; here we assert the structural rejection surfaces.
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.DESIGN_CLASS_OBSTRUCTION,
            accepted_artifacts=(_t2b_ref(),),
            acceptance_manifests_sha256=("1" * 64,),
            planner_assessment=planner,
            theorem_no_go_claimed=True,
            theorem_no_go_basis=T2NoGoBasis.T2C_BUDGET_LOWER_BOUND,
        )


def test_rejects_non_pass_acceptance() -> None:
    # acceptance_status is Literal["PASS"], so a non-PASS acceptance ref is
    # structurally unrepresentable: the binding fail-closes at construction.
    with pytest.raises(ValidationError):
        T2AcceptedArtifactRef(
            kind=T2AcceptedArtifactKind.T2B_COLLISION_OR_SEPARATION,
            acceptance_manifest_sha256="1" * 64,
            acceptance_status="FAIL",
            theorem_state="T2_COLLISION_OR_SEPARATION_REJECTED",
        )


def test_rejects_duplicate_kind() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.STRUCTURAL_INPUT,
            accepted_artifacts=(_t2b_ref(), _t2c_ref(), _t2c_ref()),
            acceptance_manifests_sha256=(
                "1" * 64,
                "2" * 64,
                "2" * 64,
            ),
            planner_assessment=planner,
            theorem_no_go_claimed=False,
            theorem_no_go_basis=T2NoGoBasis.NONE,
        )


def test_rejects_mismatched_manifest_hash() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.STRUCTURAL_INPUT,
            accepted_artifacts=(_t2b_ref(),),
            acceptance_manifests_sha256=("9" * 64,),  # does not match _t2b_ref
            planner_assessment=planner,
            theorem_no_go_claimed=False,
            theorem_no_go_basis=T2NoGoBasis.NONE,
        )


def test_rejects_empty_artifacts() -> None:
    model = _model()
    planner = classify_planner_result(model, _not_found(model))
    with pytest.raises(ValueError):
        build_t2_planner_binding(
            binding_role=T2BindingRole.STRUCTURAL_INPUT,
            accepted_artifacts=(),
            acceptance_manifests_sha256=(),
            planner_assessment=planner,
            theorem_no_go_claimed=False,
            theorem_no_go_basis=T2NoGoBasis.NONE,
        )