"""Independent exact checker for small, bounded integer feasibility models.

This module deliberately does not call the registered planner.  It validates a
canonical finite model, computes the complete scoped state count before
iteration, and uses exact rational arithmetic.  An infeasibility receipt is
therefore accepted only when a fresh replay completes the same enumeration.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from fractions import Fraction
from itertools import product
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.exact.confidence import python_function_execution_sha256


_PYTHON_FUNCTION_EXECUTION_SHA256_BASELINE = python_function_execution_sha256


MAX_EXACT_STATES = 1_000_000
MAX_VARIABLES = 64
MAX_CONSTRAINTS = 256
MAX_TERMS_PER_CONSTRAINT = 64
MAX_TOTAL_TERMS = 4_096
MAX_INTEGER_MAGNITUDE = (1 << 63) - 1
MAX_RATIONAL_COMPONENT_BITS = 256
MAX_FIXED_HORIZON = 1_024

PositiveInt = Annotated[StrictInt, Field(ge=1)]
StateLimit = Annotated[
    StrictInt,
    Field(ge=1, le=MAX_EXACT_STATES),
]
BoundedInteger = Annotated[
    StrictInt,
    Field(
        ge=-MAX_INTEGER_MAGNITUDE,
        le=MAX_INTEGER_MAGNITUDE,
    ),
]
HorizonIndex = Annotated[
    StrictInt,
    Field(ge=0, le=MAX_FIXED_HORIZON - 1),
]


class ConstraintSense(str, Enum):
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    EQUAL = "EQUAL"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"


class FeasibilityScope(str, Enum):
    AVAILABLE_CONTROL_LIBRARY = "AVAILABLE_CONTROL_LIBRARY"
    REGISTERED_FIXED_HORIZON_DESIGN_CLASS = (
        "REGISTERED_FIXED_HORIZON_DESIGN_CLASS"
    )


class MilpCheckStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNRESOLVED = "UNRESOLVED"


class MilpTerminationReason(str, Enum):
    EXACT_WITNESS_FOUND = "EXACT_WITNESS_FOUND"
    EXHAUSTIVE_INFEASIBILITY = "EXHAUSTIVE_INFEASIBILITY"
    STATE_LIMIT_EXCEEDED_BEFORE_ENUMERATION = (
        "STATE_LIMIT_EXCEEDED_BEFORE_ENUMERATION"
    )


class MilpReceiptReplayError(ValueError):
    """Raised when serialized checker evidence does not exactly replay."""


def _fraction(value: Rational, *, label: str) -> Fraction:
    if type(value) is not Rational:
        raise TypeError(f"{label} must be exactly Rational")
    rebuilt = strict_revalidate_contract_model(value)
    return Fraction(rebuilt.numerator, rebuilt.denominator)


def _validate_rational_bits(value: Rational, *, label: str) -> None:
    if type(value) is not Rational:
        raise TypeError(f"{label} must be exactly Rational")
    if (
        abs(value.numerator).bit_length() > MAX_RATIONAL_COMPONENT_BITS
        or value.denominator.bit_length() > MAX_RATIONAL_COMPONENT_BITS
    ):
        raise ValueError(
            f"{label} numerator/denominator bit length exceeds "
            f"{MAX_RATIONAL_COMPONENT_BITS}"
        )


class VariableKind(str, Enum):
    BINARY = "BINARY"
    NONNEGATIVE = "NONNEGATIVE"
    AUXILIARY = "AUXILIARY"


class IntegerVariable(FrozenContractModel):
    variable_id: RegisteredId
    kind: VariableKind = VariableKind.NONNEGATIVE
    horizon_index: HorizonIndex | None = 0
    lower_bound: BoundedInteger
    upper_bound: BoundedInteger

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> "IntegerVariable":
        if self.lower_bound > self.upper_bound:
            raise ValueError("integer variable lower_bound exceeds upper_bound")
        if self.kind is VariableKind.BINARY and (
            self.lower_bound < 0 or self.upper_bound > 1
        ):
            raise ValueError("binary variable bounds must lie in {0, 1}")
        if (
            self.kind is VariableKind.NONNEGATIVE
            and self.lower_bound < 0
        ):
            raise ValueError("nonnegative variable lower_bound must be >= 0")
        if self.kind is VariableKind.AUXILIARY:
            if self.horizon_index is not None:
                raise ValueError(
                    "auxiliary variables must set horizon_index=None"
                )
        elif self.horizon_index is None:
            raise ValueError(
                "binary/nonnegative variables require a horizon_index"
            )
        return self


class LinearTerm(FrozenContractModel):
    variable_id: RegisteredId
    coefficient: Rational

    @model_validator(mode="after")
    def coefficient_is_nonzero(self) -> "LinearTerm":
        _validate_rational_bits(self.coefficient, label="coefficient")
        if _fraction(self.coefficient, label="coefficient") == 0:
            raise ValueError(
                "zero coefficients must be omitted from the canonical model"
            )
        return self


class LinearConstraint(FrozenContractModel):
    constraint_id: RegisteredId
    terms: tuple[LinearTerm, ...]
    sense: ConstraintSense
    rhs: Rational

    @model_validator(mode="after")
    def terms_are_unique_and_canonical(self) -> "LinearConstraint":
        if len(self.terms) > MAX_TERMS_PER_CONSTRAINT:
            raise ValueError(
                f"constraint terms exceed {MAX_TERMS_PER_CONSTRAINT}"
            )
        _validate_rational_bits(self.rhs, label="constraint rhs")
        variable_ids = tuple(term.variable_id for term in self.terms)
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("constraint terms contain duplicate variable IDs")
        if variable_ids != tuple(sorted(variable_ids)):
            raise ValueError(
                "constraint terms must be canonically sorted by variable_id"
            )
        return self


class BoundedMilpModel(FrozenContractModel):
    """Canonical finite integer model for the independent checker."""

    schema_id: Literal["d2t_rna.bounded_milp_model"] = (
        "d2t_rna.bounded_milp_model"
    )
    schema_version: Literal["1.0"] = "1.0"
    model_id: RegisteredId
    fixed_horizon: Annotated[
        StrictInt,
        Field(ge=1, le=MAX_FIXED_HORIZON),
    ]
    available_control_library: RegistryRef
    registered_design_class: RegistryRef
    variables: tuple[IntegerVariable, ...]
    available_control_variable_ids: tuple[RegisteredId, ...]
    registered_noop: StrictBool = False
    membership_semantics: Literal[
        "EXACT_MODEL_VARIABLE_ID_MEMBERSHIP"
    ] = "EXACT_MODEL_VARIABLE_ID_MEMBERSHIP"
    horizon_semantics: Literal[
        "ZERO_BASED_INDEX_WITHIN_FIXED_HORIZON"
    ] = "ZERO_BASED_INDEX_WITHIN_FIXED_HORIZON"
    available_control_membership_sha256: Sha256Hex | None = None
    registered_design_membership_sha256: Sha256Hex | None = None
    horizon_semantics_sha256: Sha256Hex | None = None
    constraints: tuple[LinearConstraint, ...]

    @model_validator(mode="after")
    def registries_and_rows_are_canonical(self) -> "BoundedMilpModel":
        if not self.variables:
            raise ValueError("bounded model variables cannot be empty")
        if len(self.variables) > MAX_VARIABLES:
            raise ValueError(
                f"bounded model variables exceed {MAX_VARIABLES}"
            )
        if len(self.constraints) > MAX_CONSTRAINTS:
            raise ValueError(
                f"bounded model constraints exceed {MAX_CONSTRAINTS}"
            )
        total_terms = sum(
            len(constraint.terms) for constraint in self.constraints
        )
        if total_terms > MAX_TOTAL_TERMS:
            raise ValueError(
                f"bounded model total terms exceed {MAX_TOTAL_TERMS}"
            )
        variable_ids = tuple(variable.variable_id for variable in self.variables)
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("bounded model contains duplicate variable IDs")
        if variable_ids != tuple(sorted(variable_ids)):
            raise ValueError(
                "bounded model variables must be canonically sorted by "
                "variable_id"
            )

        available_ids = self.available_control_variable_ids
        if len(available_ids) != len(set(available_ids)):
            raise ValueError(
                "available control variable IDs must be unique"
            )
        if available_ids != tuple(sorted(available_ids)):
            raise ValueError(
                "available control variable IDs must be canonically sorted"
            )
        unknown_available = set(available_ids) - set(variable_ids)
        if unknown_available:
            raise ValueError(
                "available control library references unknown variables: "
                + ", ".join(sorted(unknown_available))
            )
        if not available_ids and not self.registered_noop:
            raise ValueError(
                "empty available control library requires "
                "registered_noop=true"
            )

        available_set = set(available_ids)
        for variable in self.variables:
            if (
                variable.horizon_index is not None
                and variable.horizon_index >= self.fixed_horizon
            ):
                raise ValueError(
                    f"variable {variable.variable_id!r} horizon_index is "
                    "outside fixed_horizon"
                )
            if (
                variable.variable_id in available_set
                and variable.kind is VariableKind.AUXILIARY
            ):
                raise ValueError(
                    "available control membership cannot name an auxiliary "
                    f"variable: {variable.variable_id!r}"
                )
            if (
                variable.variable_id not in available_set
                and variable.kind is not VariableKind.AUXILIARY
                and not (
                    variable.lower_bound <= 0 <= variable.upper_bound
                )
            ):
                raise ValueError(
                    "variables outside the available control library must "
                    "admit the inactive value zero"
                )

        constraint_ids = tuple(
            constraint.constraint_id for constraint in self.constraints
        )
        if len(constraint_ids) != len(set(constraint_ids)):
            raise ValueError("bounded model contains duplicate constraint IDs")
        if constraint_ids != tuple(sorted(constraint_ids)):
            raise ValueError(
                "bounded model constraints must be canonically sorted by "
                "constraint_id"
            )
        known_variables = set(variable_ids)
        for constraint in self.constraints:
            unknown_terms = {
                term.variable_id for term in constraint.terms
            } - known_variables
            if unknown_terms:
                raise ValueError(
                    f"constraint {constraint.constraint_id!r} references "
                    "unknown variables: "
                    + ", ".join(sorted(unknown_terms))
                )

        expected_available_hash = canonical_sha256(
            {
                "semantics": self.membership_semantics,
                "registry": self.available_control_library,
                "variable_ids": available_ids,
                "registered_noop": self.registered_noop,
            }
        )
        expected_design_hash = canonical_sha256(
            {
                "semantics": self.membership_semantics,
                "registry": self.registered_design_class,
                "variables": self.variables,
            }
        )
        expected_horizon_hash = canonical_sha256(
            {
                "semantics": self.horizon_semantics,
                "fixed_horizon": self.fixed_horizon,
                "variable_horizon_indices": tuple(
                    (
                        variable.variable_id,
                        variable.horizon_index,
                    )
                    for variable in self.variables
                ),
            }
        )
        observed_expected = (
            (
                "available_control_membership_sha256",
                self.available_control_membership_sha256,
                expected_available_hash,
            ),
            (
                "registered_design_membership_sha256",
                self.registered_design_membership_sha256,
                expected_design_hash,
            ),
            (
                "horizon_semantics_sha256",
                self.horizon_semantics_sha256,
                expected_horizon_hash,
            ),
        )
        for field_name, observed, expected in observed_expected:
            if observed is not None and observed != expected:
                raise ValueError(f"{field_name} does not replay")
            object.__setattr__(self, field_name, expected)
        return self

    @property
    def model_sha256(self) -> str:
        return canonical_sha256(self)


class IntegerWitnessValue(FrozenContractModel):
    variable_id: RegisteredId
    value: BoundedInteger


INDEPENDENT_MILP_CHECKER_CONFIGURATION_SHA256 = canonical_sha256(
    {
        "checker": "d2t_rna.independent_bounded_integer_feasibility",
        "version": "1.0",
        "arithmetic": "EXACT_RATIONAL",
        "enumeration": "CANONICAL_ASCENDING_CARTESIAN_PRODUCT",
        "available_library_semantics": "NON_LIBRARY_VARIABLES_FIXED_TO_ZERO",
        "cap_semantics": "PRE_ENUMERATION_UNRESOLVED",
        "infeasibility_semantics": "COMPLETE_ENUMERATION_ONLY",
        "receipt_semantics": "MANDATORY_FRESH_REPLAY",
        "hard_state_cap": MAX_EXACT_STATES,
        "execution_integrity": "PRE_AND_POST_EXECUTION_CLOSURE_HASH",
    }
)


class MilpCheckReceipt(FrozenContractModel):
    schema_id: Literal["d2t_rna.bounded_milp_check_receipt"] = (
        "d2t_rna.bounded_milp_check_receipt"
    )
    schema_version: Literal["1.0"] = "1.0"
    model_sha256: Sha256Hex
    scope: FeasibilityScope
    status: MilpCheckStatus
    termination_reason: MilpTerminationReason
    state_limit: StateLimit
    state_space_size: NonNegativeInt
    states_examined: NonNegativeInt
    witness: tuple[IntegerWitnessValue, ...]
    exhaustive: StrictBool
    witness_verified: StrictBool
    enumeration_trace_sha256: Sha256Hex
    checker_configuration_sha256: Literal[
        INDEPENDENT_MILP_CHECKER_CONFIGURATION_SHA256
    ] = INDEPENDENT_MILP_CHECKER_CONFIGURATION_SHA256
    checker_execution_sha256: Sha256Hex
    verification_receipt_sha256: Sha256Hex

    @model_validator(mode="after")
    def status_fields_and_self_hash_are_consistent(self) -> "MilpCheckReceipt":
        witness_ids = tuple(item.variable_id for item in self.witness)
        if len(witness_ids) != len(set(witness_ids)):
            raise ValueError("MILP witness contains duplicate variable IDs")
        if witness_ids != tuple(sorted(witness_ids)):
            raise ValueError(
                "MILP witness values must be canonically sorted by variable_id"
            )
        if self.state_space_size < 1:
            raise ValueError("bounded model state space cannot be empty")
        if self.states_examined > self.state_space_size:
            raise ValueError("states_examined exceeds the finite state space")

        if self.status is MilpCheckStatus.FEASIBLE:
            if self.termination_reason is not (
                MilpTerminationReason.EXACT_WITNESS_FOUND
            ):
                raise ValueError("feasible receipt has the wrong termination")
            if self.states_examined < 1:
                raise ValueError("feasible receipt examined no state")
            if self.exhaustive:
                raise ValueError(
                    "existential witness receipts are not infeasibility proofs"
                )
            if not self.witness_verified:
                raise ValueError("feasible receipt must verify its exact witness")
        elif self.status is MilpCheckStatus.INFEASIBLE:
            if self.termination_reason is not (
                MilpTerminationReason.EXHAUSTIVE_INFEASIBILITY
            ):
                raise ValueError(
                    "infeasible receipt has the wrong termination"
                )
            if self.witness:
                raise ValueError("infeasible receipt cannot contain a witness")
            if not self.exhaustive:
                raise ValueError(
                    "infeasibility requires complete independent enumeration"
                )
            if self.states_examined != self.state_space_size:
                raise ValueError(
                    "infeasibility receipt did not examine every state"
                )
            if self.witness_verified:
                raise ValueError(
                    "infeasibility receipt cannot mark a witness verified"
                )
        else:
            if self.termination_reason is not (
                MilpTerminationReason.STATE_LIMIT_EXCEEDED_BEFORE_ENUMERATION
            ):
                raise ValueError(
                    "unresolved receipt has the wrong termination"
                )
            if self.witness:
                raise ValueError("unresolved receipt cannot contain a witness")
            if self.states_examined != 0:
                raise ValueError(
                    "state-cap failure must occur before partial enumeration"
                )
            if self.state_space_size <= self.state_limit:
                raise ValueError(
                    "unresolved state-cap receipt does not exceed its cap"
                )
            if self.exhaustive or self.witness_verified:
                raise ValueError(
                    "unresolved receipt cannot claim proof completion"
                )

        payload = self.model_dump(
            mode="python",
            exclude={"verification_receipt_sha256"},
        )
        if canonical_sha256(payload) != self.verification_receipt_sha256:
            raise ValueError("MILP verification receipt hash does not match")
        return self


def _strict_model(model: BoundedMilpModel) -> BoundedMilpModel:
    if type(model) is not BoundedMilpModel:
        raise TypeError("model must be exactly BoundedMilpModel")
    return strict_revalidate_contract_model(model)


def _strict_witness(
    witness: tuple[IntegerWitnessValue, ...],
) -> tuple[IntegerWitnessValue, ...]:
    if type(witness) is not tuple:
        raise TypeError("witness must be a tuple")
    rebuilt: list[IntegerWitnessValue] = []
    for item in witness:
        if type(item) is not IntegerWitnessValue:
            raise TypeError(
                "every witness entry must be exactly IntegerWitnessValue"
            )
        rebuilt.append(strict_revalidate_contract_model(item))
    return tuple(rebuilt)


def _scope_variable_ids(
    model: BoundedMilpModel,
    scope: FeasibilityScope,
) -> tuple[str, ...]:
    if type(scope) is not FeasibilityScope:
        raise TypeError("scope must be exactly FeasibilityScope")
    if scope is FeasibilityScope.AVAILABLE_CONTROL_LIBRARY:
        return tuple(
            sorted(
                set(model.available_control_variable_ids)
                | {
                    variable.variable_id
                    for variable in model.variables
                    if variable.kind is VariableKind.AUXILIARY
                }
            )
        )
    return tuple(variable.variable_id for variable in model.variables)


def _assignment_satisfies_constraints(
    model: BoundedMilpModel,
    assignment: dict[str, int],
) -> bool:
    for constraint in model.constraints:
        lhs = Fraction(0, 1)
        for term in constraint.terms:
            lhs += _fraction(
                term.coefficient,
                label=(
                    f"constraint {constraint.constraint_id!r} coefficient"
                ),
            ) * assignment[term.variable_id]
        rhs = _fraction(
            constraint.rhs,
            label=f"constraint {constraint.constraint_id!r} rhs",
        )
        if constraint.sense is ConstraintSense.LESS_THAN_OR_EQUAL:
            satisfied = lhs <= rhs
        elif constraint.sense is ConstraintSense.EQUAL:
            satisfied = lhs == rhs
        else:
            satisfied = lhs >= rhs
        if not satisfied:
            return False
    return True


def verify_milp_witness(
    model: BoundedMilpModel,
    *,
    scope: FeasibilityScope,
    witness: tuple[IntegerWitnessValue, ...],
) -> bool:
    """Verify a complete canonical assignment using exact rational arithmetic."""

    checked_model = _strict_model(model)
    checked_witness = _strict_witness(witness)
    expected_ids = tuple(
        variable.variable_id for variable in checked_model.variables
    )
    observed_ids = tuple(item.variable_id for item in checked_witness)
    if observed_ids != expected_ids:
        return False

    assignment = {item.variable_id: item.value for item in checked_witness}
    by_id = {
        variable.variable_id: variable for variable in checked_model.variables
    }
    for variable_id, value in assignment.items():
        variable = by_id[variable_id]
        if value < variable.lower_bound or value > variable.upper_bound:
            return False

    active_ids = set(_scope_variable_ids(checked_model, scope))
    for variable_id in expected_ids:
        if variable_id not in active_ids and assignment[variable_id] != 0:
            return False
    return _assignment_satisfies_constraints(checked_model, assignment)


def _state_space_size(
    model: BoundedMilpModel,
    active_ids: tuple[str, ...],
) -> int:
    by_id = {variable.variable_id: variable for variable in model.variables}
    size = 1
    for variable_id in active_ids:
        variable = by_id[variable_id]
        size *= variable.upper_bound - variable.lower_bound + 1
    return size


def _trace_hasher(
    *,
    model_sha256: str,
    scope: FeasibilityScope,
    active_ids: tuple[str, ...],
    state_limit: int,
    state_space_size: int,
) -> object:
    hasher = hashlib.sha256()
    hasher.update(
        canonical_json_bytes(
            {
                "model_sha256": model_sha256,
                "scope": scope,
                "active_variable_ids": active_ids,
                "state_limit": state_limit,
                "state_space_size": state_space_size,
                "checker_configuration_sha256": (
                    INDEPENDENT_MILP_CHECKER_CONFIGURATION_SHA256
                ),
            }
        )
    )
    return hasher


def _receipt(
    *,
    model_sha256: str,
    scope: FeasibilityScope,
    status: MilpCheckStatus,
    termination_reason: MilpTerminationReason,
    state_limit: int,
    state_space_size: int,
    states_examined: int,
    witness: tuple[IntegerWitnessValue, ...],
    exhaustive: bool,
    witness_verified: bool,
    enumeration_trace_sha256: str,
    checker_execution_sha256: str,
) -> MilpCheckReceipt:
    payload = {
        "schema_id": "d2t_rna.bounded_milp_check_receipt",
        "schema_version": "1.0",
        "model_sha256": model_sha256,
        "scope": scope,
        "status": status,
        "termination_reason": termination_reason,
        "state_limit": state_limit,
        "state_space_size": state_space_size,
        "states_examined": states_examined,
        "witness": witness,
        "exhaustive": exhaustive,
        "witness_verified": witness_verified,
        "enumeration_trace_sha256": enumeration_trace_sha256,
        "checker_configuration_sha256": (
            INDEPENDENT_MILP_CHECKER_CONFIGURATION_SHA256
        ),
        "checker_execution_sha256": checker_execution_sha256,
    }
    return MilpCheckReceipt(
        **payload,
        verification_receipt_sha256=canonical_sha256(payload),
    )


def _check_bounded_milp_core(
    model: BoundedMilpModel,
    *,
    scope: FeasibilityScope,
    state_limit: int,
    checker_execution_sha256: str,
) -> MilpCheckReceipt:
    """Check finite feasibility independently, or fail closed at the state cap."""

    checked_model = _strict_model(model)
    if type(state_limit) is not int or state_limit < 1:
        raise ValueError("state_limit must be a positive exact integer")
    if state_limit > MAX_EXACT_STATES:
        raise ValueError(
            f"state_limit cannot exceed MAX_EXACT_STATES={MAX_EXACT_STATES}"
        )
    active_ids = _scope_variable_ids(checked_model, scope)
    state_space_size = _state_space_size(checked_model, active_ids)
    model_sha256 = canonical_sha256(checked_model)
    trace = _trace_hasher(
        model_sha256=model_sha256,
        scope=scope,
        active_ids=active_ids,
        state_limit=state_limit,
        state_space_size=state_space_size,
    )
    if state_space_size > state_limit:
        return _receipt(
            model_sha256=model_sha256,
            scope=scope,
            status=MilpCheckStatus.UNRESOLVED,
            termination_reason=(
                MilpTerminationReason.STATE_LIMIT_EXCEEDED_BEFORE_ENUMERATION
            ),
            state_limit=state_limit,
            state_space_size=state_space_size,
            states_examined=0,
            witness=(),
            exhaustive=False,
            witness_verified=False,
            enumeration_trace_sha256=trace.hexdigest(),
            checker_execution_sha256=checker_execution_sha256,
        )

    variable_by_id = {
        variable.variable_id: variable for variable in checked_model.variables
    }
    domains = tuple(
        range(
            variable_by_id[variable_id].lower_bound,
            variable_by_id[variable_id].upper_bound + 1,
        )
        for variable_id in active_ids
    )
    all_variable_ids = tuple(variable_by_id)
    states_examined = 0
    for values in product(*domains):
        states_examined += 1
        assignment = {variable_id: 0 for variable_id in all_variable_ids}
        assignment.update(zip(active_ids, values, strict=True))
        satisfied = _assignment_satisfies_constraints(
            checked_model,
            assignment,
        )
        trace.update(
            b"\x00"
            + canonical_json_bytes(
                {
                    "state_index": states_examined,
                    "assignment": tuple(
                        {
                            "variable_id": variable_id,
                            "value": assignment[variable_id],
                        }
                        for variable_id in all_variable_ids
                    ),
                    "satisfied": satisfied,
                }
            )
        )
        if satisfied:
            witness = tuple(
                IntegerWitnessValue(
                    variable_id=variable_id,
                    value=assignment[variable_id],
                )
                for variable_id in all_variable_ids
            )
            if not verify_milp_witness(
                checked_model,
                scope=scope,
                witness=witness,
            ):
                raise RuntimeError(
                    "independent checker produced an invalid exact witness"
                )
            return _receipt(
                model_sha256=model_sha256,
                scope=scope,
                status=MilpCheckStatus.FEASIBLE,
                termination_reason=MilpTerminationReason.EXACT_WITNESS_FOUND,
                state_limit=state_limit,
                state_space_size=state_space_size,
                states_examined=states_examined,
                witness=witness,
                exhaustive=False,
                witness_verified=True,
                enumeration_trace_sha256=trace.hexdigest(),
                checker_execution_sha256=checker_execution_sha256,
            )

    return _receipt(
        model_sha256=model_sha256,
        scope=scope,
        status=MilpCheckStatus.INFEASIBLE,
        termination_reason=MilpTerminationReason.EXHAUSTIVE_INFEASIBILITY,
        state_limit=state_limit,
        state_space_size=state_space_size,
        states_examined=states_examined,
        witness=(),
        exhaustive=True,
        witness_verified=False,
        enumeration_trace_sha256=trace.hexdigest(),
        checker_execution_sha256=checker_execution_sha256,
    )


def _current_checker_execution_sha256() -> str:
    if (
        python_function_execution_sha256
        is not _PYTHON_FUNCTION_EXECUTION_SHA256_BASELINE
    ):
        raise RuntimeError(
            "MILP checker execution closure has a replaced hash verifier"
        )
    try:
        return python_function_execution_sha256(
            _check_bounded_milp_core,
            purpose="TASK5_INDEPENDENT_BOUNDED_MILP_CHECKER",
            strict_pure=False,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "MILP checker execution closure cannot be verified"
        ) from exc


EXPECTED_MILP_CHECKER_EXECUTION_SHA256 = (
    _current_checker_execution_sha256()
)


def _assert_checker_execution_integrity() -> str:
    observed = _current_checker_execution_sha256()
    if observed != EXPECTED_MILP_CHECKER_EXECUTION_SHA256:
        raise RuntimeError(
            "MILP checker execution closure changed after module import"
        )
    return observed


def check_bounded_milp(
    model: BoundedMilpModel,
    *,
    scope: FeasibilityScope,
    state_limit: int,
) -> MilpCheckReceipt:
    """Run the exact checker only under an unchanged execution closure."""

    before = _assert_checker_execution_integrity()
    receipt = _check_bounded_milp_core(
        model,
        scope=scope,
        state_limit=state_limit,
        checker_execution_sha256=before,
    )
    after = _assert_checker_execution_integrity()
    if after != before or receipt.checker_execution_sha256 != before:
        raise RuntimeError(
            "MILP checker execution closure changed during evaluation"
        )
    return receipt


def replay_bounded_milp_check(
    model: BoundedMilpModel,
    receipt: MilpCheckReceipt,
) -> MilpCheckReceipt:
    """Re-run the exact checker and reject any non-identical receipt."""

    checked_model = _strict_model(model)
    if type(receipt) is not MilpCheckReceipt:
        raise TypeError("receipt must be exactly MilpCheckReceipt")
    try:
        checked_receipt = strict_revalidate_contract_model(receipt)
    except (TypeError, ValueError) as exc:
        raise MilpReceiptReplayError(
            f"MILP receipt failed structural replay: {exc}"
        ) from exc
    if checked_receipt.model_sha256 != canonical_sha256(checked_model):
        raise MilpReceiptReplayError(
            "MILP receipt model hash does not match the supplied model"
        )
    if (
        checked_receipt.checker_execution_sha256
        != EXPECTED_MILP_CHECKER_EXECUTION_SHA256
    ):
        raise MilpReceiptReplayError(
            "MILP receipt execution hash does not match this checker"
        )
    replayed = check_bounded_milp(
        checked_model,
        scope=checked_receipt.scope,
        state_limit=checked_receipt.state_limit,
    )
    if canonical_json_bytes(checked_receipt) != canonical_json_bytes(replayed):
        raise MilpReceiptReplayError(
            "MILP receipt does not match a fresh independent replay"
        )
    return replayed
