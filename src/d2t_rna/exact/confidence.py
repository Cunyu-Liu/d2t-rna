"""Exact confidence-set semantics for the registered synthetic micro-system.

This module deliberately stops at mathematical, synthetic verification.  Its
outer-approximation receipt cannot authorize a formal scientific certificate.
"""

from __future__ import annotations

import builtins as python_builtins
import hashlib
import dis
import numbers as python_numbers
import re
import sys
from collections.abc import Callable
from enum import Enum
from fractions import Fraction
from pathlib import Path
from types import (
    BuiltinFunctionType,
    BuiltinMethodType,
    CodeType,
    FunctionType,
    ModuleType,
)
from typing import Literal, TypeAlias, TypeVar

import pydantic
from pydantic import model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    Rational,
    RegisteredId,
    Sha256Hex,
)
from d2t_rna.probability.registry import (
    TrustedSemanticRegistry,
    ensure_trusted_task2_registry,
)
from d2t_rna.probability.scopes import (
    ProbabilityScopeDisposition,
    SyntheticKnownChannelPrerequisites,
    assess_probability_scope,
)

from .enumerate import (
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
    ProbabilityMassAudit,
    iter_joint_outcome_probabilities,
    iter_joint_outcomes,
)
from .support import (
    ExactActionSpec,
    ExactSupportPlan,
    ExactSupportSpec,
    validate_and_size_support,
)

_TYPE_GETATTRIBUTE = type.__getattribute__
_MODULE_GETATTRIBUTE = ModuleType.__getattribute__

JointOutcome: TypeAlias = tuple[tuple[int, ...], ...]
ConfidenceRuleOutput: TypeAlias = tuple[tuple[str, ...], str | None]
ConfidenceRule: TypeAlias = Callable[[JointOutcome], ConfidenceRuleOutput]

FROZEN_CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)
EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256 = canonical_sha256(
    {
        "rule_id": "decision.confidence-subset.v1",
        "empty": "ABSTAIN",
        "all_h0": "C",
        "all_h1": "R",
        "mixed_or_indifference": "ABSTAIN",
    }
)
OUTER_APPROXIMATION_VERIFIER_V1_SHA256 = canonical_sha256(
    {
        "verifier_id": "d2t_rna.outer_approximation.v1",
        "contract_sha256": FROZEN_CONTRACT_SHA256,
        "requirements": (
            "FULL_SUPPORT",
            "EXACT_SUBSET_OUTER",
            "NO_NEW_DECISIVE",
            "NO_DECISION_FLIP",
            "PAIRED_TRANSCRIPT",
            "CALLABLE_REPLAY",
        ),
    }
)
_PURE_BUILTIN_NAMES: frozenset[str] = frozenset()
_STRICT_PURITY_ALLOWED_OPCODES = frozenset(
    {
        "BINARY_OP",
        "BINARY_SLICE",
        "BINARY_SUBSCR",
        "BUILD_SLICE",
        "BUILD_TUPLE",
        "COMPARE_OP",
        "CONTAINS_OP",
        "COPY",
        "COPY_FREE_VARS",
        "END_FOR",
        "FOR_ITER",
        "GET_ITER",
        "JUMP_BACKWARD",
        "JUMP_BACKWARD_NO_INTERRUPT",
        "JUMP_FORWARD",
        "JUMP_IF_FALSE_OR_POP",
        "JUMP_IF_TRUE_OR_POP",
        "LOAD_CONST",
        "LOAD_DEREF",
        "LOAD_FAST",
        "LOAD_FAST_CHECK",
        "LOAD_FAST_LOAD_FAST",
        "LOAD_GLOBAL",
        "NOP",
        "POP_JUMP_BACKWARD_IF_FALSE",
        "POP_JUMP_BACKWARD_IF_NONE",
        "POP_JUMP_BACKWARD_IF_NOT_NONE",
        "POP_JUMP_BACKWARD_IF_TRUE",
        "POP_JUMP_FORWARD_IF_FALSE",
        "POP_JUMP_FORWARD_IF_NONE",
        "POP_JUMP_FORWARD_IF_NOT_NONE",
        "POP_JUMP_FORWARD_IF_TRUE",
        "POP_JUMP_IF_FALSE",
        "POP_JUMP_IF_NONE",
        "POP_JUMP_IF_NOT_NONE",
        "POP_JUMP_IF_TRUE",
        "POP_TOP",
        "RESUME",
        "RETURN_CONST",
        "RETURN_VALUE",
        "STORE_FAST",
        "STORE_FAST_STORE_FAST",
        "SWAP",
        "TO_BOOL",
        "UNARY_INVERT",
        "UNARY_NEGATIVE",
        "UNARY_NOT",
        "UNARY_POSITIVE",
        "UNPACK_EX",
        "UNPACK_SEQUENCE",
    }
)
_STRICT_PURITY_FORBIDDEN_OPCODES = frozenset(
    {
        "DELETE_ATTR",
        "DELETE_DEREF",
        "DELETE_GLOBAL",
        "DELETE_NAME",
        "DELETE_SUBSCR",
        "BUILD_CONST_KEY_MAP",
        "BUILD_LIST",
        "BUILD_MAP",
        "BUILD_SET",
        "DICT_MERGE",
        "DICT_UPDATE",
        "BINARY_MODULO",
        "BUILD_STRING",
        "FORMAT_SIMPLE",
        "FORMAT_VALUE",
        "FORMAT_WITH_SPEC",
        "IMPORT_FROM",
        "IMPORT_NAME",
        "IS_OP",
        "LIST_APPEND",
        "LIST_EXTEND",
        "LOAD_ATTR",
        "LOAD_BUILD_CLASS",
        "LOAD_METHOD",
        "MAP_ADD",
        "MAKE_FUNCTION",
        "MATCH_CLASS",
        "MATCH_KEYS",
        "MATCH_MAPPING",
        "MATCH_SEQUENCE",
        "COPY_DICT_WITHOUT_KEYS",
        "SET_ADD",
        "SET_UPDATE",
        "STORE_ATTR",
        "STORE_DEREF",
        "STORE_GLOBAL",
        "STORE_NAME",
        "STORE_SUBSCR",
    }
)
_CONFIDENCE_MODEL_RUNTIME_BASELINES: tuple[
    tuple[type, str, object],
    ...,
] = ()
_FRACTION_RUNTIME_BASELINES: tuple[
    tuple[type, str, object],
    ...,
] = ()


def confidence_module_sha256() -> str:
    """Hash the complete local source/runtime closure used by this verifier."""

    _assert_confidence_model_runtime_integrity()
    d2t_rna_root = Path(__file__).resolve().parents[1]
    files = {
        "exact.confidence": Path(__file__).resolve(),
        "exact.enumerate": Path(__file__).with_name("enumerate.py").resolve(),
        "exact.support": Path(__file__).with_name("support.py").resolve(),
        "contracts.base": d2t_rna_root / "contracts" / "base.py",
        "contracts.primitives": (
            d2t_rna_root / "contracts" / "primitives.py"
        ),
        "contracts.enums": d2t_rna_root / "contracts" / "enums.py",
        "contracts.probability": (
            d2t_rna_root / "contracts" / "probability.py"
        ),
        "probability.registry": (
            d2t_rna_root / "probability" / "registry.py"
        ),
        "probability.scopes": (
            d2t_rna_root / "probability" / "scopes.py"
        ),
    }
    file_hashes: dict[str, str] = {}
    for module_name, path in files.items():
        if not path.is_file():
            raise RuntimeError(
                f"verifier source dependency is unavailable: {module_name}"
            )
        file_hashes[module_name] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    runtime_function_names = (
        "_strict_exact",
        "_fraction",
        "_normalized_code_sha256",
        "_normalized_code_descriptor",
        "_normalized_constant_descriptor",
        "_global_lookup_names",
        "_module_file_sha256",
        "_runtime_callable_surface_descriptor",
        "_code_symbol_names",
        "_fraction_dependency_surface_descriptor",
        "_raw_type_attribute",
        "_raw_module_namespace",
        "_fraction_runtime_surface_descriptor",
        "_collect_fraction_dependency_identities",
        "_fraction_runtime_identity_token",
        "_fraction_arithmetic_canary",
        "_fraction_numeric_abc_canary",
        "_type_runtime_surface_descriptor",
        "_type_runtime_identity_token",
        "_runtime_identity_matches",
        "_fraction_runtime_identity_matches",
        "_assert_fraction_runtime_integrity",
        "_assert_confidence_model_runtime_integrity",
        "_dependency_descriptor",
        "_function_dependency_descriptor",
        "python_function_execution_sha256",
        "confidence_rule_implementation_sha256",
        "_is_registered_id",
        "_validate_confidence_rule_output",
        "_confidence_output_record",
        "_execute_rule_twice",
        "_validate_joint_outcome",
        "_update_transcript",
        "classify_hypothesis_region",
        "decision_from_confidence_set",
        "_decision_from_validated_members",
        "exact_parameter_registry_hash",
        "verify_outer_approximation",
        "replay_outer_approximation_assessment",
        "canonical_json_bytes",
        "canonical_sha256",
        "strict_revalidate_contract_model",
        "ensure_trusted_task2_registry",
        "assess_probability_scope",
        "iter_joint_outcome_probabilities",
        "iter_joint_outcomes",
        "validate_and_size_support",
    )
    runtime_function_hashes: dict[str, str] = {}
    for name in runtime_function_names:
        function = globals().get(name)
        if type(function) is not FunctionType:
            raise RuntimeError(
                f"confidence runtime dependency was replaced: {name}"
            )
        runtime_function_hashes[name] = (
            python_function_execution_sha256(
                function,
                purpose=f"CONFIDENCE_RUNTIME_DEPENDENCY:{name}",
                strict_pure=False,
            )
        )
    return canonical_sha256(
        {
            "schema": "d2t_rna.confidence_execution_closure.v1",
            "files": file_hashes,
            "runtime_function_hashes": runtime_function_hashes,
            "python_cache_tag": sys.implementation.cache_tag,
            "python_version": tuple(sys.version_info[:3]),
            "pydantic_version": pydantic.__version__,
        }
    )


class HypothesisRegion(str, Enum):
    """The exact three-way partition fixed by the frozen thresholds."""

    H0 = "H0"
    H1 = "H1"
    INDIFFERENCE = "INDIFFERENCE"


class DecisionOutcome(str, Enum):
    """C certifies H0, R rejects H0, and all ambiguity abstains."""

    CERTIFY = "C"
    REJECT = "R"
    ABSTAIN = "ABSTAIN"


class OuterApproximationViolation(ValueError):
    """Raised when an alleged outer set is not pointwise conservative."""


class HypothesisThresholds(FrozenContractModel):
    schema_id: Literal["d2t_rna.hypothesis_thresholds"] = (
        "d2t_rna.hypothesis_thresholds"
    )
    schema_version: Literal["1.0"] = "1.0"
    tau0: Rational
    epsilon: Rational

    @model_validator(mode="after")
    def thresholds_are_strictly_ordered(self) -> "HypothesisThresholds":
        if _fraction(self.tau0) >= _fraction(self.epsilon):
            raise ValueError("hypothesis thresholds require tau0 < epsilon")
        return self


class ExactParameterPoint(FrozenContractModel):
    """One registered truth point and its exact known-channel law."""

    schema_id: Literal["d2t_rna.exact_parameter_point"] = (
        "d2t_rna.exact_parameter_point"
    )
    schema_version: Literal["1.0"] = "1.0"
    parameter_id: RegisteredId
    loss: Rational
    law: IndependentMultinomialLaw


class ExactSamplingLawEntry(FrozenContractModel):
    parameter_id: RegisteredId
    law_hash: Sha256Hex


class ExactSamplingLawManifest(FrozenContractModel):
    schema_id: Literal["d2t_rna.exact_sampling_law_manifest"] = (
        "d2t_rna.exact_sampling_law_manifest"
    )
    schema_version: Literal["1.0"] = "1.0"
    support_spec_hash: Sha256Hex
    entries: tuple[ExactSamplingLawEntry, ...]

    @model_validator(mode="after")
    def entries_are_nonempty_unique_and_canonical(
        self,
    ) -> "ExactSamplingLawManifest":
        identifiers = tuple(entry.parameter_id for entry in self.entries)
        if not identifiers:
            raise ValueError("sampling-law manifest cannot be empty")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("sampling-law manifest IDs must be unique")
        if identifiers != tuple(sorted(identifiers)):
            raise ValueError(
                "sampling-law manifest must be sorted by parameter_id"
            )
        return self


def exact_parameter_registry_hash(
    thresholds: HypothesisThresholds,
    points: tuple[ExactParameterPoint, ...],
) -> str:
    """Hash the finite loss/law registry without circular family fields."""

    checked_thresholds = strict_revalidate_contract_model(thresholds)
    checked_points = tuple(
        strict_revalidate_contract_model(point) for point in points
    )
    return canonical_sha256(
        {
            "schema": "d2t_rna.exact_parameter_registry.v1",
            "thresholds": checked_thresholds,
            "points": checked_points,
        }
    )


class ExactParameterFamily(FrozenContractModel):
    """Canonical finite parameter universe for one exact support."""

    schema_id: Literal["d2t_rna.exact_parameter_family"] = (
        "d2t_rna.exact_parameter_family"
    )
    schema_version: Literal["1.0"] = "1.0"
    support_spec_hash: Sha256Hex
    semantic_registry: TrustedSemanticRegistry
    probability_space: ProbabilitySpaceSpec
    synthetic_prerequisites: SyntheticKnownChannelPrerequisites
    sampling_law_manifest: ExactSamplingLawManifest
    thresholds: HypothesisThresholds
    points: tuple[ExactParameterPoint, ...]

    @model_validator(mode="after")
    def points_are_complete_canonical_and_support_bound(
        self,
    ) -> "ExactParameterFamily":
        parameter_ids = tuple(point.parameter_id for point in self.points)
        if not parameter_ids:
            raise ValueError("exact parameter family cannot be empty")
        if len(set(parameter_ids)) != len(parameter_ids):
            raise ValueError("exact parameter IDs must be unique")
        if parameter_ids != tuple(sorted(parameter_ids)):
            raise ValueError("exact parameter points must be sorted by parameter_id")
        if any(
            point.law.support_spec_hash != self.support_spec_hash
            for point in self.points
        ):
            raise ValueError(
                "every exact parameter law must bind the family support hash"
            )
        trusted_registry = ensure_trusted_task2_registry(
            self.semantic_registry
        )
        if (
            self.probability_space.probability_scope
            is not ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL
        ):
            raise ValueError(
                "exact parameter family requires SYNTHETIC_KNOWN_CHANNEL"
            )
        if (
            self.synthetic_prerequisites.support_definition_hash
            != self.support_spec_hash
        ):
            raise ValueError(
                "synthetic prerequisite support hash does not match"
            )
        parameter_registry_hash = exact_parameter_registry_hash(
            self.thresholds,
            self.points,
        )
        if (
            self.probability_space.parameter_space_hash
            != parameter_registry_hash
        ):
            raise ValueError(
                "probability-space parameter registry hash does not replay"
            )
        manifest_hash = canonical_sha256(self.sampling_law_manifest)
        if (
            self.sampling_law_manifest.support_spec_hash
            != self.support_spec_hash
            or self.probability_space.sampling_law_hash != manifest_hash
            or self.synthetic_prerequisites.sampling_law_hash
            != manifest_hash
        ):
            raise ValueError(
                "sampling-law manifest bindings do not replay"
            )
        expected_entries = tuple(
            ExactSamplingLawEntry(
                parameter_id=point.parameter_id,
                law_hash=canonical_sha256(point.law),
            )
            for point in self.points
        )
        if self.sampling_law_manifest.entries != expected_entries:
            raise ValueError(
                "sampling-law manifest must list every point law exactly once"
            )
        scope = assess_probability_scope(
            self.probability_space,
            trusted_registry,
            self.synthetic_prerequisites,
        )
        if (
            scope.disposition
            is not ProbabilityScopeDisposition.SYNTHETIC_PENDING_TASK_4
            or scope.formal_scientific_risk_authorized
            or not scope.risk_certificate_must_abstain
        ):
            raise ValueError(
                "Task 2 synthetic scope did not remain pending and fail closed"
            )
        return self

    @property
    def parameter_universe_hash(self) -> str:
        """Canonical digest used by procedures, results, and decision rules."""

        return canonical_sha256(self)

    @property
    def probability_space_hash(self) -> str:
        return canonical_sha256(self.probability_space)

    @property
    def synthetic_prerequisites_hash(self) -> str:
        return canonical_sha256(self.synthetic_prerequisites)

    @property
    def sampling_law_manifest_hash(self) -> str:
        return canonical_sha256(self.sampling_law_manifest)


class ConfidenceProcedureSpec(FrozenContractModel):
    """Hash-addressed confidence procedure; execution remains caller supplied."""

    schema_id: Literal["d2t_rna.confidence_procedure_spec"] = (
        "d2t_rna.confidence_procedure_spec"
    )
    schema_version: Literal["1.0"] = "1.0"
    procedure_id: RegisteredId
    implementation_hash: Sha256Hex
    parameter_universe_hash: Sha256Hex


class ExactDecisionRuleSpec(FrozenContractModel):
    """The sole registered confidence-subset three-way decision rule."""

    schema_id: Literal["d2t_rna.exact_decision_rule_spec"] = (
        "d2t_rna.exact_decision_rule_spec"
    )
    schema_version: Literal["1.0"] = "1.0"
    rule_id: Literal["decision.confidence-subset.v1"]
    implementation_hash: Sha256Hex
    parameter_universe_hash: Sha256Hex

    @model_validator(mode="after")
    def implementation_is_the_frozen_rule(self) -> "ExactDecisionRuleSpec":
        if (
            self.implementation_hash
            != EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ):
            raise ValueError(
                "decision rule implementation hash is not the frozen v1 rule"
            )
        return self


class ConfidenceSetResult(FrozenContractModel):
    """One finite confidence set or an explicit empty-set failure."""

    schema_id: Literal["d2t_rna.confidence_set_result"] = (
        "d2t_rna.confidence_set_result"
    )
    schema_version: Literal["1.0"] = "1.0"
    parameter_universe_hash: Sha256Hex
    members: tuple[RegisteredId, ...]
    failure_reason: RegisteredId | None

    @model_validator(mode="after")
    def membership_and_failure_shape_is_exact(self) -> "ConfidenceSetResult":
        if len(set(self.members)) != len(self.members):
            raise ValueError("confidence-set members must be unique")
        if self.members != tuple(sorted(self.members)):
            raise ValueError("confidence-set members must be canonically sorted")
        if not self.members and self.failure_reason is None:
            raise ValueError(
                "empty confidence set requires an explicit failure reason"
            )
        if self.members and self.failure_reason is not None:
            raise ValueError(
                "nonempty confidence set cannot carry a failure reason"
            )
        return self


class OuterApproximationAssessment(FrozenContractModel):
    """Successful pointwise conservativeness check over the entire support."""

    schema_id: Literal["d2t_rna.outer_approximation_assessment"] = (
        "d2t_rna.outer_approximation_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    support_spec_hash: Sha256Hex
    support_plan_hash: Sha256Hex
    parameter_universe_hash: Sha256Hex
    probability_space_hash: Sha256Hex
    synthetic_prerequisites_hash: Sha256Hex
    sampling_law_manifest_hash: Sha256Hex
    exact_procedure_hash: Sha256Hex
    outer_procedure_hash: Sha256Hex
    decision_rule_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    verifier_code_hash: Sha256Hex
    verifier_configuration_hash: Sha256Hex
    exact_result_decision_transcript_hash: Sha256Hex
    outer_result_decision_transcript_hash: Sha256Hex
    paired_comparison_transcript_hash: Sha256Hex
    transcript_complete: Literal[True] = True
    inclusion_verified: Literal[True] = True
    outcome_count: NonNegativeInt
    deterministic_decision_removed_count: NonNegativeInt
    new_decisive_count: Literal[0] = 0
    decision_flip_count: Literal[0] = 0
    formal_scientific_certificate_authorized: Literal[False] = False

    @model_validator(mode="after")
    def receipt_shape_is_nonvacuous(
        self,
    ) -> "OuterApproximationAssessment":
        if self.outcome_count <= 0:
            raise ValueError("outer assessment cannot be vacuous")
        if self.deterministic_decision_removed_count > self.outcome_count:
            raise ValueError(
                "removed decision count cannot exceed outcome count"
            )
        if self.verifier_code_hash != confidence_module_sha256():
            raise ValueError("outer assessment verifier code hash is stale")
        if (
            self.verifier_configuration_hash
            != OUTER_APPROXIMATION_VERIFIER_V1_SHA256
        ):
            raise ValueError(
                "outer assessment verifier configuration is unregistered"
            )
        return self


class OuterApproximationReplayCredential(FrozenContractModel):
    """Non-bearer record emitted only after a live full-support replay.

    The credential is intentionally a different type from the assessment.  A
    serialized assessment therefore cannot claim that it has been replayed.
    This audit record is still not an authority token: consumers must perform
    their own live replay and compare the verifier source to an external,
    trusted source-manifest anchor.
    """

    schema_id: Literal["d2t_rna.outer_approximation_replay_credential"] = (
        "d2t_rna.outer_approximation_replay_credential"
    )
    schema_version: Literal["1.0"] = "1.0"
    assessment_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    exact_result_decision_transcript_hash: Sha256Hex
    outer_result_decision_transcript_hash: Sha256Hex
    paired_comparison_transcript_hash: Sha256Hex
    verifier_code_hash: Sha256Hex
    verifier_configuration_hash: Sha256Hex
    live_replay_completed: Literal[True] = True
    external_source_anchor_required: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    formal_scientific_certificate_authorized: Literal[False] = False

    @model_validator(mode="after")
    def credential_remains_non_bearer_and_runtime_bound(
        self,
    ) -> "OuterApproximationReplayCredential":
        if self.verifier_code_hash != confidence_module_sha256():
            raise ValueError("outer replay verifier code hash is stale")
        if (
            self.verifier_configuration_hash
            != OUTER_APPROXIMATION_VERIFIER_V1_SHA256
        ):
            raise ValueError(
                "outer replay verifier configuration is unregistered"
            )
        return self


ModelT = TypeVar("ModelT", bound=FrozenContractModel)


def _strict_exact(
    value: object,
    expected_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    if type(value) is not expected_type:
        raise TypeError(f"{label} must be exactly {expected_type.__name__}")
    return strict_revalidate_contract_model(value)


def _fraction(value: Rational) -> Fraction:
    return Fraction(value.numerator, value.denominator)


def _module_file_sha256(module: ModuleType) -> str | None:
    if _MODULE_GETATTRIBUTE is not ModuleType.__getattribute__:
        raise RuntimeError("ModuleType.__getattribute__ alias changed")
    namespace = _MODULE_GETATTRIBUTE(module, "__dict__")
    raw_path = namespace.get("__file__")
    if not isinstance(raw_path, str):
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_code_sha256(code: CodeType) -> str:
    """Hash executable bytecode without paths or adaptive interpreter state."""

    return canonical_sha256(_normalized_code_descriptor(code))


def _normalized_constant_descriptor(value: object) -> object:
    """Describe a Python code constant with exact, JSON-safe type semantics."""

    if type(value) is CodeType:
        return {
            "kind": "CODE",
            "value": _normalized_code_descriptor(value),
        }
    if value is None:
        return {"kind": "NONE"}
    if value is Ellipsis:
        return {"kind": "ELLIPSIS"}
    if type(value) is bool:
        return {"kind": "BOOL", "value": value}
    if type(value) is int:
        return {"kind": "INT", "value": value}
    if type(value) is str:
        return {"kind": "STR", "value": value}
    if type(value) is bytes:
        return {"kind": "BYTES", "hex": value.hex()}
    if type(value) is float:
        return {"kind": "FLOAT", "hex": value.hex()}
    if type(value) is complex:
        return {
            "kind": "COMPLEX",
            "real_hex": value.real.hex(),
            "imag_hex": value.imag.hex(),
        }
    if type(value) is tuple:
        return {
            "kind": "TUPLE",
            "items": tuple(
                _normalized_constant_descriptor(item)
                for item in value
            ),
        }
    if type(value) is frozenset:
        items = tuple(
            _normalized_constant_descriptor(item)
            for item in value
        )
        return {
            "kind": "FROZENSET",
            "items": tuple(sorted(items, key=canonical_sha256)),
        }
    raise TypeError(
        "registered executable contains an unsupported code constant: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _normalized_code_descriptor(code: CodeType) -> object:
    """Describe executable semantics without `co_filename` or quickening."""

    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "baseline_instructions": tuple(
            {
                "offset": instruction.offset,
                "opname": instruction.opname,
                "arg": instruction.arg,
            }
            for instruction in dis.get_instructions(
                code,
                show_caches=True,
                adaptive=False,
            )
        ),
        "constants": tuple(
            _normalized_constant_descriptor(value)
            for value in code.co_consts
        ),
        "names": code.co_names,
        "varnames": code.co_varnames,
        "freevars": code.co_freevars,
        "cellvars": code.co_cellvars,
        "name": code.co_name,
        "qualname": code.co_qualname,
        "firstlineno": code.co_firstlineno,
        "linetable_hex": code.co_linetable.hex(),
        "exceptiontable_hex": code.co_exceptiontable.hex(),
    }


def _global_lookup_names(code: CodeType) -> tuple[str, ...]:
    """Return names actually resolved through globals/builtins, recursively."""

    names: set[str] = set()
    for instruction in dis.get_instructions(code):
        if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}:
            if isinstance(instruction.argval, str):
                names.add(instruction.argval)
    for value in code.co_consts:
        if type(value) is CodeType:
            names.update(_global_lookup_names(value))
    return tuple(sorted(names))


def _assert_strictly_pure_constant(value: object) -> None:
    """Accept only reflexive immutable constants with value-only semantics."""

    if type(value) is frozenset:
        raise TypeError(
            "confidence rule contains an unordered frozenset constant"
        )
    if type(value) in (float, complex):
        raise TypeError(
            "confidence rule contains a non-reflexive-capable numeric constant"
        )
    if value is None or value is Ellipsis:
        return
    if type(value) in (bool, int, str, bytes):
        return
    if type(value) is tuple:
        for item in value:
            _assert_strictly_pure_constant(item)
        return
    if type(value) is CodeType:
        raise TypeError(
            "confidence rule contains a nested executable code constant"
        )
    raise TypeError(
        "confidence rule contains a constant outside the strict immutable "
        f"allowlist: {type(value).__module__}.{type(value).__qualname__}"
    )


def _assert_strictly_pure_code(code: CodeType) -> None:
    """Reject bytecode that can hide mutable or dynamic dispatch state."""

    if code.co_exceptiontable:
        raise TypeError(
            "confidence rule cannot contain exception-handling control flow"
        )
    for instruction in dis.get_instructions(code):
        if instruction.opname in _STRICT_PURITY_FORBIDDEN_OPCODES:
            raise TypeError(
                "confidence rule contains a forbidden strict-purity opcode: "
                f"{instruction.opname}"
            )
        if instruction.opname not in _STRICT_PURITY_ALLOWED_OPCODES:
            raise TypeError(
                "confidence rule contains an opcode outside the strict "
                f"allowlist: {instruction.opname}"
            )
        if (
            instruction.opname == "BINARY_OP"
            and instruction.argrepr in {"%", "%="}
        ):
            raise TypeError(
                "confidence rule contains forbidden strict-purity "
                "percent formatting"
            )
    for value in code.co_consts:
        _assert_strictly_pure_constant(value)


_TYPE_RUNTIME_CALLABLE_NAMES = (
    "__new__",
    "__init__",
    "__eq__",
    "__hash__",
    "__setattr__",
    "model_validate",
    "model_validate_json",
    "model_construct",
    "model_copy",
    "model_dump",
    "model_dump_json",
    "model_json_schema",
)
_FRACTION_RUNTIME_ATTRIBUTE_NAMES = (
    "__new__",
    "__init__",
    "__hash__",
    "__bool__",
    "__int__",
    "__float__",
    "__floor__",
    "__ceil__",
    "__round__",
    "__trunc__",
    "__eq__",
    "__ne__",
    "__lt__",
    "__le__",
    "__gt__",
    "__ge__",
    "__add__",
    "__radd__",
    "__iadd__",
    "__sub__",
    "__rsub__",
    "__isub__",
    "__mul__",
    "__rmul__",
    "__imul__",
    "__truediv__",
    "__rtruediv__",
    "__itruediv__",
    "__floordiv__",
    "__rfloordiv__",
    "__ifloordiv__",
    "__mod__",
    "__rmod__",
    "__imod__",
    "__divmod__",
    "__rdivmod__",
    "__pow__",
    "__rpow__",
    "__ipow__",
    "__neg__",
    "__pos__",
    "__abs__",
    "numerator",
    "denominator",
)
_FRACTION_RUNTIME_ATTRIBUTE_NAMES = tuple(
    sorted(
        set(_FRACTION_RUNTIME_ATTRIBUTE_NAMES)
        | set(Fraction.__dict__)
        | {
            "__getattribute__",
            "__getattr__",
            "__setattr__",
            "__delattr__",
            "__instancecheck__",
            "_numerator",
            "_denominator",
            "_richcmp",
            "from_float",
            "as_integer_ratio",
        }
    )
)
_RE_PATTERN_TYPE = type(re.compile(""))


def _runtime_callable_surface_descriptor(value: object) -> object:
    """Describe a class callable without serializing process addresses."""

    function = getattr(value, "__func__", value)
    if type(function) is FunctionType:
        return {
            "kind": "PYTHON_FUNCTION",
            "module": function.__module__,
            "qualname": function.__qualname__,
            "code_sha256": _normalized_code_sha256(function.__code__),
        }
    if isinstance(function, (BuiltinFunctionType, BuiltinMethodType)):
        return {
            "kind": "BUILTIN_CALLABLE",
            "module": getattr(function, "__module__", None),
            "qualname": getattr(function, "__qualname__", None),
        }
    return {
        "kind": "DESCRIPTOR",
        "type_module": type(function).__module__,
        "type_qualname": type(function).__qualname__,
        "name": getattr(function, "__name__", None),
        "qualname": getattr(function, "__qualname__", None),
    }


def _code_symbol_names(code: CodeType) -> tuple[str, ...]:
    """Return every name referenced by a code object and nested code."""

    names = set(code.co_names)
    for constant in code.co_consts:
        if type(constant) is CodeType:
            names.update(_code_symbol_names(constant))
    return tuple(sorted(names))


def _fraction_dependency_surface_descriptor(
    value: object,
    *,
    seen: dict[int, int],
    module_attribute_names: tuple[str, ...] = (),
) -> object:
    """Describe the complete mutable execution closure of Fraction methods."""

    if not isinstance(value, ModuleType):
        value = getattr(value, "__func__", value)
    if value is None:
        return {"kind": "NONE"}
    if value is Ellipsis:
        return {"kind": "ELLIPSIS"}
    if value is NotImplemented:
        return {"kind": "NOT_IMPLEMENTED"}
    if type(value) is bool:
        return {"kind": "BOOL", "value": value}
    if type(value) is int:
        return {"kind": "INT", "value": value}
    if type(value) is str:
        return {"kind": "STR", "value": value}
    if type(value) is bytes:
        return {"kind": "BYTES", "hex": value.hex()}
    if type(value) is float:
        return {"kind": "FLOAT", "hex": value.hex()}
    if type(value) is complex:
        return {
            "kind": "COMPLEX",
            "real_hex": value.real.hex(),
            "imag_hex": value.imag.hex(),
        }

    object_id = id(value)
    if object_id in seen:
        if isinstance(value, ModuleType) and module_attribute_names:
            namespace = _raw_module_namespace(value)
            return {
                "kind": "MODULE_REFERENCE",
                "node_id": seen[object_id],
                "runtime_type_module": _TYPE_GETATTRIBUTE(
                    type(value),
                    "__module__",
                ),
                "runtime_type_qualname": _TYPE_GETATTRIBUTE(
                    type(value),
                    "__qualname__",
                ),
                "referenced_attributes": tuple(
                    (
                        name,
                        (
                            _fraction_dependency_surface_descriptor(
                                namespace[name],
                                seen=seen,
                            )
                            if name in namespace
                            else {"kind": "MISSING"}
                        ),
                    )
                    for name in module_attribute_names
                ),
            }
        return {"kind": "REFERENCE", "node_id": seen[object_id]}
    node_id = len(seen)
    seen[object_id] = node_id

    if type(value) in (tuple, list):
        return {
            "kind": type(value).__name__.upper(),
            "node_id": node_id,
            "items": tuple(
                _fraction_dependency_surface_descriptor(
                    item,
                    seen=seen,
                )
                for item in value
            ),
        }
    if type(value) is frozenset:
        items = tuple(
            _fraction_dependency_surface_descriptor(item, seen=seen)
            for item in value
        )
        return {
            "kind": "FROZENSET",
            "node_id": node_id,
            "items": tuple(sorted(items, key=canonical_sha256)),
        }
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError(
                "Fraction runtime dependency mappings require string keys"
            )
        return {
            "kind": "DICT",
            "node_id": node_id,
            "items": tuple(
                (
                    key,
                    _fraction_dependency_surface_descriptor(
                        value[key],
                        seen=seen,
                    ),
                )
                for key in sorted(value)
            ),
        }
    if type(value) is CodeType:
        return {
            "kind": "CODE",
            "node_id": node_id,
            "descriptor": _normalized_code_descriptor(value),
        }
    if type(value) is FunctionType:
        raw_builtins = value.__builtins__
        if isinstance(raw_builtins, ModuleType):
            builtins_mapping = raw_builtins.__dict__
        elif type(raw_builtins) is dict:
            builtins_mapping = raw_builtins
        else:
            raise TypeError("Fraction function has an invalid builtins mapping")
        symbol_names = _code_symbol_names(value.__code__)
        referenced_globals: list[tuple[str, object]] = []
        for name in _global_lookup_names(value.__code__):
            if name in value.__globals__:
                resolved = value.__globals__[name]
                resolution = "GLOBAL"
            elif name in builtins_mapping:
                resolved = builtins_mapping[name]
                resolution = "BUILTIN"
            else:
                raise TypeError(
                    "Fraction function has an unresolved runtime name: "
                    f"{name}"
                )
            referenced_globals.append(
                (
                    name,
                    {
                        "resolution": resolution,
                        "dependency": (
                            _fraction_dependency_surface_descriptor(
                                resolved,
                                seen=seen,
                                module_attribute_names=(
                                    symbol_names
                                    if isinstance(resolved, ModuleType)
                                    else ()
                                ),
                            )
                        ),
                    },
                )
            )
        return {
            "kind": "PYTHON_FUNCTION",
            "node_id": node_id,
            "module": value.__module__,
            "qualname": value.__qualname__,
            "code": _normalized_code_descriptor(value.__code__),
            "defaults": _fraction_dependency_surface_descriptor(
                value.__defaults__,
                seen=seen,
            ),
            "keyword_defaults": (
                _fraction_dependency_surface_descriptor(
                    value.__kwdefaults__,
                    seen=seen,
                )
            ),
            "closure": tuple(
                _fraction_dependency_surface_descriptor(
                    cell.cell_contents,
                    seen=seen,
                )
                for cell in value.__closure__ or ()
            ),
            "referenced_globals": tuple(referenced_globals),
        }
    if type(value) is property:
        return {
            "kind": "PROPERTY",
            "node_id": node_id,
            "fget": _fraction_dependency_surface_descriptor(
                value.fget,
                seen=seen,
            ),
            "fset": _fraction_dependency_surface_descriptor(
                value.fset,
                seen=seen,
            ),
            "fdel": _fraction_dependency_surface_descriptor(
                value.fdel,
                seen=seen,
            ),
        }
    if isinstance(value, (BuiltinFunctionType, BuiltinMethodType)):
        module_name = getattr(value, "__module__", None)
        module = (
            sys.modules.get(module_name)
            if type(module_name) is str
            else None
        )
        return {
            "kind": "BUILTIN_CALLABLE",
            "node_id": node_id,
            "module": module_name,
            "qualname": getattr(value, "__qualname__", None),
            "module_file_sha256": (
                _module_file_sha256(module)
                if isinstance(module, ModuleType)
                else None
            ),
        }
    if isinstance(value, ModuleType):
        namespace = _raw_module_namespace(value)
        attributes = tuple(
            (
                name,
                (
                    _fraction_dependency_surface_descriptor(
                        namespace[name],
                        seen=seen,
                    )
                    if name in namespace
                    else {"kind": "MISSING"}
                ),
            )
            for name in module_attribute_names
        )
        return {
            "kind": "MODULE",
            "node_id": node_id,
            "name": namespace.get("__name__"),
            "runtime_type_module": _TYPE_GETATTRIBUTE(
                type(value),
                "__module__",
            ),
            "runtime_type_qualname": _TYPE_GETATTRIBUTE(
                type(value),
                "__qualname__",
            ),
            "file_sha256": _module_file_sha256(value),
            "referenced_attributes": attributes,
        }
    if type(value) is _RE_PATTERN_TYPE:
        return {
            "kind": "REGEX_PATTERN",
            "node_id": node_id,
            "pattern": value.pattern,
            "flags": value.flags,
        }
    if isinstance(value, type):
        module_name = _TYPE_GETATTRIBUTE(value, "__module__")
        qualname = _TYPE_GETATTRIBUTE(value, "__qualname__")
        module = sys.modules.get(module_name)
        return {
            "kind": "TYPE",
            "node_id": node_id,
            "module": module_name,
            "qualname": qualname,
            "module_file_sha256": (
                _module_file_sha256(module)
                if isinstance(module, ModuleType)
                else None
            ),
        }
    return {
        "kind": "DESCRIPTOR",
        "node_id": node_id,
        "type_module": type(value).__module__,
        "type_qualname": type(value).__qualname__,
        "name": getattr(value, "__name__", None),
        "qualname": getattr(value, "__qualname__", None),
        "owner_module": getattr(
            getattr(value, "__objclass__", None),
            "__module__",
            None,
        ),
        "owner_qualname": getattr(
            getattr(value, "__objclass__", None),
            "__qualname__",
            None,
        ),
    }


def _raw_type_attribute(value: type, name: str) -> object:
    """Resolve a raw class/metaclass descriptor without dynamic dispatch."""

    if not isinstance(value, type):
        raise TypeError("raw descriptor lookup requires a runtime type")
    if type(name) is not str or not name:
        raise TypeError("raw descriptor lookup requires a nonempty name")
    if _TYPE_GETATTRIBUTE is not python_builtins.type.__getattribute__:
        raise RuntimeError("builtin type.__getattribute__ alias changed")
    for base in _TYPE_GETATTRIBUTE(value, "__mro__"):
        namespace = _TYPE_GETATTRIBUTE(base, "__dict__")
        if name in namespace:
            return namespace[name]
    metaclass_type = type(value)
    for metaclass in _TYPE_GETATTRIBUTE(metaclass_type, "__mro__"):
        namespace = _TYPE_GETATTRIBUTE(metaclass, "__dict__")
        if name in namespace:
            return namespace[name]
    return None


def _raw_module_namespace(value: ModuleType) -> dict[str, object]:
    """Read a module's real namespace through the immutable base descriptor."""

    if not isinstance(value, ModuleType):
        raise TypeError("raw module lookup requires a module")
    if _MODULE_GETATTRIBUTE is not ModuleType.__getattribute__:
        raise RuntimeError("ModuleType.__getattribute__ alias changed")
    namespace = _MODULE_GETATTRIBUTE(value, "__dict__")
    if type(namespace) is not dict:
        raise RuntimeError("module namespace is not an exact dictionary")
    return namespace


def _fraction_runtime_surface_descriptor() -> object:
    """Return a deterministic descriptor of the exact arithmetic protocol."""

    if _TYPE_GETATTRIBUTE is not python_builtins.type.__getattribute__:
        raise RuntimeError("builtin type.__getattribute__ alias changed")
    if _MODULE_GETATTRIBUTE is not ModuleType.__getattribute__:
        raise RuntimeError("ModuleType.__getattribute__ alias changed")
    fraction_module_name = _TYPE_GETATTRIBUTE(Fraction, "__module__")
    fraction_qualname = _TYPE_GETATTRIBUTE(Fraction, "__qualname__")
    fraction_class_dict = _TYPE_GETATTRIBUTE(Fraction, "__dict__")
    fraction_mro = _TYPE_GETATTRIBUTE(Fraction, "__mro__")
    fraction_module = sys.modules.get(fraction_module_name)
    seen = {id(Fraction): 0}
    return {
        "schema": "d2t_rna.fraction_runtime_protocol.v1",
        "type_module": fraction_module_name,
        "type_qualname": fraction_qualname,
        "class_dict_keys": tuple(sorted(fraction_class_dict)),
        "module_file_sha256": (
            _module_file_sha256(fraction_module)
            if isinstance(fraction_module, ModuleType)
            else None
        ),
        "mro": tuple(
            {
                "module": _TYPE_GETATTRIBUTE(base, "__module__"),
                "qualname": _TYPE_GETATTRIBUTE(base, "__qualname__"),
                "new": _fraction_dependency_surface_descriptor(
                    _raw_type_attribute(base, "__new__"),
                    seen=seen,
                ),
                "metaclass_module": _TYPE_GETATTRIBUTE(
                    type(base),
                    "__module__",
                ),
                "metaclass_qualname": _TYPE_GETATTRIBUTE(
                    type(base),
                    "__qualname__",
                ),
                "metaclass_instancecheck": (
                    _fraction_dependency_surface_descriptor(
                        _raw_type_attribute(
                            type(base),
                            "__instancecheck__",
                        ),
                        seen=seen,
                    )
                ),
            }
            for base in fraction_mro
        ),
        "numeric_abc_types": tuple(
            (
                name,
                _fraction_dependency_surface_descriptor(
                    abc_type,
                    seen=seen,
                ),
            )
            for name, abc_type in (
                ("Integral", python_numbers.Integral),
                ("Rational", python_numbers.Rational),
                ("Real", python_numbers.Real),
                ("Complex", python_numbers.Complex),
            )
        ),
        "attributes": tuple(
            (
                name,
                _fraction_dependency_surface_descriptor(
                    _raw_type_attribute(Fraction, name),
                    seen=seen,
                ),
            )
            for name in _FRACTION_RUNTIME_ATTRIBUTE_NAMES
        ),
    }


def _collect_fraction_dependency_identities(
    value: object,
    *,
    path: str,
    seen: set[int],
    rows: list[tuple[str, object]],
    module_attribute_names: tuple[str, ...] = (),
) -> None:
    """Collect live dependency identities without serializing their addresses."""

    if not isinstance(value, ModuleType):
        value = getattr(value, "__func__", value)
    rows.append((path, value))
    object_id = id(value)
    if object_id in seen:
        if isinstance(value, ModuleType):
            namespace = _raw_module_namespace(value)
            rows.extend(
                (
                    (f"{path}.__class__", type(value)),
                    (f"{path}.__dict__", namespace),
                )
            )
            for name in module_attribute_names:
                if name in namespace:
                    _collect_fraction_dependency_identities(
                        namespace[name],
                        path=f"{path}.{name}",
                        seen=seen,
                        rows=rows,
                    )
                else:
                    rows.append((f"{path}.{name}.missing", None))
        return
    seen.add(object_id)

    if type(value) is FunctionType:
        rows.extend(
            (
                (f"{path}.code", value.__code__),
                (f"{path}.defaults", value.__defaults__),
                (f"{path}.kwdefaults", value.__kwdefaults__),
                (f"{path}.closure", value.__closure__),
                (f"{path}.globals", value.__globals__),
                (f"{path}.builtins", value.__builtins__),
            )
        )
        for index, cell in enumerate(value.__closure__ or ()):
            rows.append((f"{path}.closure[{index}].cell", cell))
            _collect_fraction_dependency_identities(
                cell.cell_contents,
                path=f"{path}.closure[{index}].value",
                seen=seen,
                rows=rows,
            )
        symbol_names = _code_symbol_names(value.__code__)
        raw_builtins = value.__builtins__
        builtins_mapping = (
            raw_builtins.__dict__
            if isinstance(raw_builtins, ModuleType)
            else raw_builtins
        )
        for name in _global_lookup_names(value.__code__):
            if name in value.__globals__:
                resolved = value.__globals__[name]
            elif type(builtins_mapping) is dict and name in builtins_mapping:
                resolved = builtins_mapping[name]
            else:
                rows.append((f"{path}.global[{name}].missing", None))
                continue
            _collect_fraction_dependency_identities(
                resolved,
                path=f"{path}.global[{name}]",
                seen=seen,
                rows=rows,
                module_attribute_names=(
                    symbol_names
                    if isinstance(resolved, ModuleType)
                    else ()
                ),
            )
        return
    if type(value) is property:
        for name, accessor in (
            ("fget", value.fget),
            ("fset", value.fset),
            ("fdel", value.fdel),
        ):
            _collect_fraction_dependency_identities(
                accessor,
                path=f"{path}.{name}",
                seen=seen,
                rows=rows,
            )
        return
    if isinstance(value, ModuleType):
        namespace = _raw_module_namespace(value)
        rows.extend(
            (
                (f"{path}.__class__", type(value)),
                (f"{path}.__dict__", namespace),
            )
        )
        for name in module_attribute_names:
            if name in namespace:
                _collect_fraction_dependency_identities(
                    namespace[name],
                    path=f"{path}.{name}",
                    seen=seen,
                    rows=rows,
                )
            else:
                rows.append((f"{path}.{name}.missing", None))
        return
    if type(value) in (tuple, list):
        for index, item in enumerate(value):
            _collect_fraction_dependency_identities(
                item,
                path=f"{path}[{index}]",
                seen=seen,
                rows=rows,
            )
        return
    if type(value) is dict:
        for key in sorted(value):
            if type(key) is str:
                _collect_fraction_dependency_identities(
                    value[key],
                    path=f"{path}[{key}]",
                    seen=seen,
                    rows=rows,
                )


def _fraction_runtime_identity_token() -> tuple[tuple[str, object], ...]:
    """Capture every live object that implements the Fraction protocol."""

    if _TYPE_GETATTRIBUTE is not python_builtins.type.__getattribute__:
        raise RuntimeError("builtin type.__getattribute__ alias changed")
    if _MODULE_GETATTRIBUTE is not ModuleType.__getattribute__:
        raise RuntimeError("ModuleType.__getattribute__ alias changed")
    fraction_mro = _TYPE_GETATTRIBUTE(Fraction, "__mro__")
    rows: list[tuple[str, object]] = [
        ("Fraction", Fraction),
        ("Fraction.__mro__", fraction_mro),
    ]
    seen = {id(Fraction)}
    for name, abc_type in (
        ("Integral", python_numbers.Integral),
        ("Rational", python_numbers.Rational),
        ("Real", python_numbers.Real),
        ("Complex", python_numbers.Complex),
    ):
        rows.extend(
            (
                (f"numbers.{name}", abc_type),
                (f"numbers.{name}.metaclass", type(abc_type)),
            )
        )
    for index, base in enumerate(fraction_mro):
        rows.extend(
            (
                (f"Fraction.__mro__[{index}]", base),
                (f"Fraction.__mro__[{index}].metaclass", type(base)),
            )
        )
        _collect_fraction_dependency_identities(
            _raw_type_attribute(base, "__new__"),
            path=f"Fraction.__mro__[{index}].__new__",
            seen=seen,
            rows=rows,
        )
        _collect_fraction_dependency_identities(
            _raw_type_attribute(
                type(base),
                "__instancecheck__",
            ),
            path=(
                f"Fraction.__mro__[{index}]."
                "metaclass.__instancecheck__"
            ),
            seen=seen,
            rows=rows,
        )
    for name in _FRACTION_RUNTIME_ATTRIBUTE_NAMES:
        _collect_fraction_dependency_identities(
            _raw_type_attribute(Fraction, name),
            path=f"Fraction.{name}",
            seen=seen,
            rows=rows,
        )
    return tuple(rows)


def _fraction_arithmetic_canary() -> bool:
    """Check the concrete integer-rational semantics used by Task 4."""

    def is_pair(value: object, numerator: int, denominator: int) -> bool:
        return (
            type(value) is Fraction
            and type(value.numerator) is int
            and type(value.denominator) is int
            and value.numerator == numerator
            and value.denominator == denominator
        )

    half = Fraction(2, 4)
    third = Fraction(1, 3)
    two_thirds = Fraction(2, 3)
    return (
        is_pair(half, 1, 2)
        and is_pair(Fraction(half), 1, 2)
        and is_pair(half + third, 5, 6)
        and is_pair(half + 1, 3, 2)
        and is_pair(1 + half, 3, 2)
        and is_pair(half - third, 1, 6)
        and is_pair(1 - half, 1, 2)
        and is_pair(half * two_thirds, 1, 3)
        and is_pair(2 * half, 1, 1)
        and is_pair(half / two_thirds, 3, 4)
        and is_pair(1 / half, 2, 1)
        and is_pair(half**3, 1, 8)
        and is_pair(-half, -1, 2)
        and is_pair(+half, 1, 2)
        and is_pair(abs(-half), 1, 2)
        and (half == Fraction(1, 2)) is True
        and (half != third) is True
        and (third < half) is True
        and (third <= half) is True
        and (half > third) is True
        and (half >= third) is True
        and (half < 1) is True
        and (half <= 1) is True
        and (half > 0) is True
        and (half >= 0) is True
    )


def _fraction_numeric_abc_canary() -> bool:
    """Freeze the exact int/Fraction ABC dispatch domain used by CPython."""

    zero_fraction = Fraction(0, 1)
    return (
        isinstance(0, python_numbers.Integral) is True
        and isinstance(0, python_numbers.Rational) is True
        and isinstance(0, python_numbers.Real) is True
        and isinstance(0, python_numbers.Complex) is True
        and isinstance(zero_fraction, python_numbers.Rational) is True
        and isinstance(zero_fraction, python_numbers.Real) is True
        and isinstance(zero_fraction, python_numbers.Complex) is True
    )


def _type_runtime_surface_descriptor(
    value: type,
    *,
    attribute_names: tuple[str, ...] = _TYPE_RUNTIME_CALLABLE_NAMES,
) -> object:
    """Bind the mutable construction/validation surface of a runtime class."""

    model_fields = getattr(value, "model_fields", None)
    return {
        "module": value.__module__,
        "qualname": value.__qualname__,
        "mro": tuple(
            (base.__module__, base.__qualname__) for base in value.__mro__
        ),
        "critical_callables": tuple(
            (
                name,
                _runtime_callable_surface_descriptor(
                    getattr(value, name, None)
                ),
            )
            for name in attribute_names
        ),
        "pydantic_field_names": (
            tuple(model_fields)
            if type(model_fields) is dict
            else None
        ),
        "pydantic_validator_type": (
            (
                type(value.__pydantic_validator__).__module__,
                type(value.__pydantic_validator__).__qualname__,
            )
            if hasattr(value, "__pydantic_validator__")
            else None
        ),
        "pydantic_serializer_type": (
            (
                type(value.__pydantic_serializer__).__module__,
                type(value.__pydantic_serializer__).__qualname__,
            )
            if hasattr(value, "__pydantic_serializer__")
            else None
        ),
    }


def _type_runtime_identity_token(
    value: type,
    *,
    attribute_names: tuple[str, ...] = _TYPE_RUNTIME_CALLABLE_NAMES,
) -> object:
    """Capture live objects whose replacement changes class execution."""

    callable_tokens = []
    for name in attribute_names:
        raw = getattr(value, name, None)
        function = getattr(raw, "__func__", raw)
        callable_tokens.append(
            (
                name,
                function,
                getattr(function, "__code__", None),
                getattr(function, "__defaults__", None),
                getattr(function, "__kwdefaults__", None),
                getattr(function, "__closure__", None),
            )
        )
    return {
        "mro": value.__mro__,
        "callables": tuple(callable_tokens),
        "pydantic_validator": getattr(
            value,
            "__pydantic_validator__",
            None,
        ),
        "pydantic_serializer": getattr(
            value,
            "__pydantic_serializer__",
            None,
        ),
        "pydantic_core_schema": getattr(
            value,
            "__pydantic_core_schema__",
            None,
        ),
        "model_fields": getattr(value, "model_fields", None),
    }


def _runtime_identity_matches(left: object, right: object) -> bool:
    """Compare captured runtime tokens strictly by object identity."""

    if type(left) is not dict or type(right) is not dict:
        return False
    if left["mro"] != right["mro"]:
        return False
    left_callables = left["callables"]
    right_callables = right["callables"]
    if len(left_callables) != len(right_callables):
        return False
    for left_row, right_row in zip(
        left_callables,
        right_callables,
        strict=True,
    ):
        if left_row[0] != right_row[0]:
            return False
        if any(
            left_value is not right_value
            for left_value, right_value in zip(
                left_row[1:],
                right_row[1:],
                strict=True,
            )
        ):
            return False
    return all(
        left[key] is right[key]
        for key in (
            "pydantic_validator",
            "pydantic_serializer",
            "pydantic_core_schema",
            "model_fields",
        )
    )


def _fraction_runtime_identity_matches(
    left: object,
    right: object,
) -> bool:
    """Compare recursively captured Fraction dependencies by identity."""

    if type(left) is not tuple or type(right) is not tuple:
        return False
    if len(left) != len(right):
        return False
    return all(
        type(left_row) is tuple
        and type(right_row) is tuple
        and len(left_row) == 2
        and len(right_row) == 2
        and left_row[0] == right_row[0]
        and left_row[1] is right_row[1]
        for left_row, right_row in zip(left, right, strict=True)
    )


def _assert_fraction_runtime_integrity(
    *,
    module_aliases: tuple[tuple[str, object], ...] = (),
) -> None:
    """Reject mutation of the exact arithmetic protocol after clean import."""

    if len(_FRACTION_RUNTIME_BASELINES) != 1:
        raise RuntimeError(
            "Fraction runtime protocol baseline was not initialized"
        )
    for (
        fraction_type,
        expected_hash,
        expected_identity,
    ) in _FRACTION_RUNTIME_BASELINES:
        if Fraction is not fraction_type:
            raise RuntimeError(
                "Task 4 confidence Fraction alias changed after import"
            )
        for module_name, alias in module_aliases:
            if type(module_name) is not str or not module_name:
                raise TypeError(
                    "Task 4 Fraction alias labels must be nonempty strings"
                )
            if alias is not fraction_type:
                raise RuntimeError(
                    "Task 4 module Fraction alias changed after import: "
                    f"{module_name}"
                )
        actual_hash = canonical_sha256(
            _fraction_runtime_surface_descriptor()
        )
        actual_identity = _fraction_runtime_identity_token()
        if (
            fraction_type is not Fraction
            or actual_hash != expected_hash
            or not _fraction_runtime_identity_matches(
                actual_identity,
                expected_identity,
            )
        ):
            raise RuntimeError(
                "fractions.Fraction runtime protocol was mutated after import"
            )
        try:
            canary_valid = (
                _fraction_arithmetic_canary()
                and _fraction_numeric_abc_canary()
            )
        except Exception as exc:
            raise RuntimeError(
                "fractions.Fraction arithmetic canary raised unexpectedly"
            ) from exc
        if canary_valid is not True:
            raise RuntimeError(
                "fractions.Fraction arithmetic canary changed semantics"
            )


def _assert_confidence_model_runtime_integrity() -> None:
    """Reject class mutation relative to the clean module-import baseline."""

    _assert_fraction_runtime_integrity()
    if not _CONFIDENCE_MODEL_RUNTIME_BASELINES:
        raise RuntimeError(
            "confidence model runtime baseline was not initialized"
        )
    for (
        model_type,
        expected_hash,
        expected_identity,
    ) in _CONFIDENCE_MODEL_RUNTIME_BASELINES:
        actual_hash = canonical_sha256(
            _type_runtime_surface_descriptor(model_type)
        )
        actual_identity = _type_runtime_identity_token(model_type)
        if (
            actual_hash != expected_hash
            or not _runtime_identity_matches(
                actual_identity,
                expected_identity,
            )
        ):
            raise RuntimeError(
                "confidence verifier runtime class was mutated after import: "
                f"{model_type.__module__}.{model_type.__qualname__}"
            )


def _dependency_descriptor(
    value: object,
    *,
    seen: dict[int, int],
    strict_pure: bool,
) -> object:
    """Return a canonical descriptor or fail closed for an unknown dependency."""

    if value is Ellipsis:
        return {"kind": "ELLIPSIS"}
    if value is NotImplemented:
        return {"kind": "NOT_IMPLEMENTED"}
    if strict_pure:
        if value is None:
            return {"kind": "NONE"}
        if type(value) is bool:
            return {"kind": "BOOL", "value": value}
        if type(value) is int:
            return {"kind": "INT", "value": value}
        if type(value) is str:
            return {"kind": "STR", "value": value}
        if type(value) is bytes:
            return {"kind": "BYTES", "hex": value.hex()}
        if type(value) is tuple:
            return {
                "kind": "TUPLE",
                "items": tuple(
                    _dependency_descriptor(
                        item,
                        seen=seen,
                        strict_pure=True,
                    )
                    for item in value
                ),
            }
        if type(value) is FunctionType:
            raise TypeError(
                "confidence rule cannot bind helper functions; the strict "
                "callback must be self-contained"
            )
        if isinstance(value, type):
            raise TypeError(
                "confidence rule cannot bind or construct runtime classes"
            )
        if not isinstance(
            value,
            (BuiltinFunctionType, BuiltinMethodType),
        ):
            raise TypeError(
                "confidence rule references a dependency outside the "
                "strict immutable allowlist: "
                f"{type(value).__module__}.{type(value).__qualname__}"
            )
    if type(value) in (tuple, list):
        return {
            "kind": type(value).__name__.upper(),
            "items": tuple(
                _dependency_descriptor(
                    item,
                    seen=seen,
                    strict_pure=strict_pure,
                )
                for item in value
            ),
        }
    if type(value) is frozenset:
        return {
            "kind": "FROZENSET",
            "items": tuple(
                sorted(
                    (
                        _dependency_descriptor(
                            item,
                            seen=seen,
                            strict_pure=strict_pure,
                        )
                        for item in value
                    ),
                    key=canonical_sha256,
                )
            ),
        }
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError(
                "confidence dependency dictionaries require string keys"
            )
        return {
            "kind": "DICT",
            "items": tuple(
                (
                    key,
                    _dependency_descriptor(
                        value[key],
                        seen=seen,
                        strict_pure=strict_pure,
                    ),
                )
                for key in sorted(value)
            ),
        }
    try:
        canonical_json_bytes(value)
    except (TypeError, ValueError):
        pass
    else:
        return {"kind": "CANONICAL_VALUE", "value": value}

    object_id = id(value)
    if object_id in seen:
        return {
            "kind": "REFERENCE",
            "node_id": seen[object_id],
        }
    node_id = len(seen)
    seen[object_id] = node_id

    if type(value) is FunctionType:
        return {
            "node_id": node_id,
            **_function_dependency_descriptor(
                value,
                seen=seen,
                strict_pure=strict_pure,
            ),
        }
    if isinstance(value, (BuiltinFunctionType, BuiltinMethodType)):
        callable_name = getattr(value, "__name__", None)
        if strict_pure:
            if (
                callable_name not in _PURE_BUILTIN_NAMES
                or value
                is not getattr(
                    python_builtins,
                    callable_name,
                    None,
                )
            ):
                raise TypeError(
                    "confidence rule global builtin alias must resolve to "
                    "an allowlisted canonical builtin"
                )
            return {
                "kind": "ALLOWLISTED_PURE_BUILTIN",
                "node_id": node_id,
                "module": getattr(value, "__module__", None),
                "qualname": getattr(value, "__qualname__", None),
            }
        module_name = getattr(value, "__module__", None)
        module = (
            sys.modules.get(module_name)
            if isinstance(module_name, str)
            else None
        )
        bound_self = getattr(value, "__self__", None)
        if isinstance(bound_self, ModuleType):
            bound_self_descriptor = {
                "kind": "MODULE",
                "name": bound_self.__name__,
                "file_sha256": _module_file_sha256(bound_self),
            }
        elif bound_self is None:
            bound_self_descriptor = None
        else:
            bound_self_descriptor = _dependency_descriptor(
                bound_self,
                seen=seen,
                strict_pure=False,
            )
        return {
            "kind": "BUILTIN_CALLABLE",
            "node_id": node_id,
            "module": module_name,
            "qualname": getattr(value, "__qualname__", None),
            "bound_self": bound_self_descriptor,
            "module_file_sha256": (
                _module_file_sha256(module)
                if isinstance(module, ModuleType)
                else None
            ),
        }
    if isinstance(value, ModuleType):
        if strict_pure:
            raise TypeError(
                "confidence rule cannot resolve behavior through a module"
            )
        return {
            "kind": "MODULE",
            "node_id": node_id,
            "name": value.__name__,
            "file_sha256": _module_file_sha256(value),
        }
    if isinstance(value, type):
        if strict_pure:
            raise TypeError(
                "confidence rule cannot bind or construct runtime classes"
            )
        module = sys.modules.get(value.__module__)
        return {
            "kind": "TYPE",
            "node_id": node_id,
            "module": value.__module__,
            "qualname": value.__qualname__,
            "module_file_sha256": (
                _module_file_sha256(module)
                if isinstance(module, ModuleType)
                else None
            ),
        }
    raise TypeError(
        "confidence rule references an unsupported unbound dependency: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def _function_dependency_descriptor(
    function: FunctionType,
    *,
    seen: dict[int, int],
    strict_pure: bool,
) -> object:
    if strict_pure:
        _assert_strictly_pure_code(function.__code__)
        if function.__dict__:
            raise TypeError(
                "confidence rule helper functions cannot carry runtime "
                "attributes"
            )
    closure = tuple(
        _dependency_descriptor(
            cell.cell_contents,
            seen=seen,
            strict_pure=strict_pure,
        )
        for cell in function.__closure__ or ()
    )
    referenced_globals: list[tuple[str, object]] = []
    raw_builtins = function.__builtins__
    if isinstance(raw_builtins, ModuleType):
        builtins_mapping = raw_builtins.__dict__
    elif type(raw_builtins) is dict:
        builtins_mapping = raw_builtins
    else:
        raise TypeError("confidence rule has an invalid builtins mapping")
    for name in _global_lookup_names(function.__code__):
        if name in function.__globals__:
            resolved = function.__globals__[name]
            resolution = "GLOBAL"
        elif name in builtins_mapping:
            if strict_pure and name not in _PURE_BUILTIN_NAMES:
                raise TypeError(
                    "confidence rule references a non-allowlisted builtin: "
                    f"{name}"
                )
            resolved = builtins_mapping[name]
            if strict_pure and resolved is not getattr(
                python_builtins,
                name,
                None,
            ):
                raise TypeError(
                    "confidence rule builtin does not resolve to the "
                    f"canonical builtins.{name} object"
                )
            resolution = "BUILTIN"
        else:
            raise TypeError(
                "confidence rule contains an unresolved global lookup: "
                f"{name}"
            )
        if strict_pure and resolution == "BUILTIN":
            dependency = {
                "kind": "ALLOWLISTED_PURE_BUILTIN",
                "module": getattr(resolved, "__module__", None),
                "qualname": getattr(resolved, "__qualname__", None),
            }
        elif not strict_pure and name == "_TYPE_GETATTRIBUTE":
            if resolved is not python_builtins.type.__getattribute__:
                raise TypeError(
                    "builtin type.__getattribute__ dependency changed"
                )
            dependency = {
                "kind": "TRUSTED_TYPE_GETATTRIBUTE",
                "type_module": type(resolved).__module__,
                "type_qualname": type(resolved).__qualname__,
                "name": getattr(resolved, "__name__", None),
                "owner_module": getattr(
                    getattr(resolved, "__objclass__", None),
                    "__module__",
                    None,
                ),
                "owner_qualname": getattr(
                    getattr(resolved, "__objclass__", None),
                    "__qualname__",
                    None,
                ),
            }
        elif not strict_pure and name == "_MODULE_GETATTRIBUTE":
            if resolved is not ModuleType.__getattribute__:
                raise TypeError(
                    "builtin ModuleType.__getattribute__ dependency changed"
                )
            dependency = {
                "kind": "TRUSTED_MODULE_GETATTRIBUTE",
                "type_module": type(resolved).__module__,
                "type_qualname": type(resolved).__qualname__,
                "name": getattr(resolved, "__name__", None),
                "owner_module": getattr(
                    getattr(resolved, "__objclass__", None),
                    "__module__",
                    None,
                ),
                "owner_qualname": getattr(
                    getattr(resolved, "__objclass__", None),
                    "__qualname__",
                    None,
                ),
            }
        elif (
            not strict_pure
            and name
            in {
                "_CONFIDENCE_MODEL_RUNTIME_BASELINES",
                "_COVERAGE_MODEL_RUNTIME_BASELINES",
                "_FRACTION_RUNTIME_BASELINES",
            }
        ):
            if type(resolved) is not tuple or any(
                type(row) is not tuple
                or len(row) != 3
                or not isinstance(row[0], (type, FunctionType))
                or type(row[1]) is not str
                for row in resolved
            ):
                raise TypeError(
                    "runtime model integrity baseline has invalid shape"
                )
            dependency = {
                "kind": "RUNTIME_MODEL_INTEGRITY_BASELINE",
                "entries": tuple(
                    (
                        model_type.__module__,
                        model_type.__qualname__,
                        surface_hash,
                    )
                    for model_type, surface_hash, _identity in resolved
                ),
            }
        else:
            dependency = _dependency_descriptor(
                resolved,
                seen=seen,
                strict_pure=strict_pure,
            )
        referenced_globals.append(
            (
                name,
                {
                    "resolution": resolution,
                    "dependency": dependency,
                },
            )
        )
    keyword_defaults = function.__kwdefaults__ or {}
    return {
        "kind": "FUNCTION",
        "module": function.__module__,
        "qualname": function.__qualname__,
        "code_sha256": _normalized_code_sha256(function.__code__),
        "defaults": _dependency_descriptor(
            function.__defaults__,
            seen=seen,
            strict_pure=strict_pure,
        ),
        "keyword_defaults": tuple(
            (
                key,
                _dependency_descriptor(
                    keyword_defaults[key],
                    seen=seen,
                    strict_pure=strict_pure,
                ),
            )
            for key in sorted(keyword_defaults)
        ),
        "closure": closure,
        "function_attributes": tuple(
            (
                key,
                _dependency_descriptor(
                    function.__dict__[key],
                    seen=seen,
                    strict_pure=strict_pure,
                ),
            )
            for key in sorted(function.__dict__)
        ),
        "referenced_globals": tuple(referenced_globals),
    }


def python_function_execution_sha256(
    function: FunctionType,
    *,
    purpose: str,
    strict_pure: bool,
) -> str:
    """Hash a plain function's code and recursively bound execution closure."""

    if type(function) is not FunctionType:
        raise TypeError("registered executable must be exactly a Python function")
    if type(purpose) is not str or not purpose:
        raise TypeError("registered executable purpose must be a nonempty string")
    envelope = {
        "schema": "d2t_rna.python_function_execution_closure.v2",
        "purpose": purpose,
        "strict_pure": strict_pure,
        "function": _function_dependency_descriptor(
            function,
            seen={id(function): 0},
            strict_pure=strict_pure,
        ),
        "python_cache_tag": sys.implementation.cache_tag,
        "python_version": tuple(sys.version_info[:3]),
    }
    try:
        return canonical_sha256(envelope)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "registered executable dependencies are outside the canonical "
            "contract domain"
        ) from exc


def confidence_rule_implementation_sha256(rule: ConfidenceRule) -> str:
    """Hash a self-contained confidence callback in the strict Task 4 DSL.

    Task 4 accepts only an exact plain Python function whose bound values and
    return value are immutable data tuples.  Helper functions, runtime classes,
    call opcodes, mutable or unordered state, builtins, exception handlers, and
    dynamic dispatch fail before enumeration.  The accepted closure is
    re-hashed after evaluation.
    """

    _assert_confidence_model_runtime_integrity()
    return python_function_execution_sha256(
        rule,
        purpose="CONFIDENCE_RULE",
        strict_pure=True,
    )


def _is_registered_id(value: object) -> bool:
    """Check the frozen RegisteredId grammar without a mutable model class."""

    if type(value) is not str or not 1 <= len(value) <= 128:
        return False
    first = value[0]
    if not (
        "A" <= first <= "Z"
        or "a" <= first <= "z"
        or "0" <= first <= "9"
    ):
        return False
    return all(
        "A" <= character <= "Z"
        or "a" <= character <= "z"
        or "0" <= character <= "9"
        or character in "._:-"
        for character in value[1:]
    )


def _validate_confidence_rule_output(
    value: object,
    *,
    label: str,
) -> ConfidenceRuleOutput:
    """Validate the callback's exact data-only output without class dispatch."""

    if type(value) is not tuple or len(value) != 2:
        raise TypeError(
            f"{label} confidence rule must return exactly "
            "(members_tuple, failure_reason)"
        )
    members, failure_reason = value
    if type(members) is not tuple:
        raise TypeError(f"{label} confidence members must be exactly tuple")
    if any(not _is_registered_id(member) for member in members):
        raise ValueError(
            f"{label} confidence members contain an invalid registered ID"
        )
    if len(set(members)) != len(members):
        raise ValueError(f"{label} confidence members must be unique")
    if members != tuple(sorted(members)):
        raise ValueError(
            f"{label} confidence members must be canonically sorted"
        )
    if failure_reason is not None and not _is_registered_id(failure_reason):
        raise ValueError(
            f"{label} confidence failure reason is not a registered ID"
        )
    if not members and failure_reason is None:
        raise ValueError(
            f"{label} empty confidence set requires a failure reason"
        )
    if members and failure_reason is not None:
        raise ValueError(
            f"{label} nonempty confidence set cannot carry a failure reason"
        )
    return members, failure_reason


def _confidence_output_record(
    output: ConfidenceRuleOutput,
    *,
    parameter_universe_hash: str,
) -> dict[str, object]:
    """Create the canonical trusted transcript record for a raw callback."""

    return {
        "schema_id": "d2t_rna.confidence_set_result",
        "schema_version": "1.0",
        "parameter_universe_hash": parameter_universe_hash,
        "members": output[0],
        "failure_reason": output[1],
    }


def _execute_rule_twice(
    rule: ConfidenceRule,
    outcome: JointOutcome,
    *,
    label: str,
) -> ConfidenceRuleOutput:
    checked_first = _validate_confidence_rule_output(
        rule(outcome),
        label=label,
    )
    checked_second = _validate_confidence_rule_output(
        rule(outcome),
        label=f"{label} replay",
    )
    if checked_first != checked_second:
        raise OuterApproximationViolation(
            f"{label} confidence rule is not deterministic on replay"
        )
    return checked_first


def _validate_joint_outcome(
    outcome: object,
    support: ExactSupportSpec,
) -> JointOutcome:
    """Validate one streamed outcome without allocating support-sized state."""

    if type(outcome) is not tuple:
        raise OuterApproximationViolation(
            "support iterator emitted a non-tuple outcome"
        )
    if len(outcome) != len(support.actions):
        raise OuterApproximationViolation(
            "support iterator emitted an outcome with wrong action dimension"
        )
    for action, counts in zip(support.actions, outcome, strict=True):
        if type(counts) is not tuple:
            raise OuterApproximationViolation(
                "support iterator emitted a non-tuple count vector"
            )
        if len(counts) != len(action.alphabet):
            raise OuterApproximationViolation(
                "support iterator emitted an outcome with wrong alphabet "
                f"dimension for action {action.action_id!r}"
            )
        if any(type(count) is not int or count < 0 for count in counts):
            raise OuterApproximationViolation(
                "support iterator emitted a non-integer or negative count"
            )
        if sum(counts) != action.sample_size:
            raise OuterApproximationViolation(
                "support iterator emitted counts that do not sum to the "
                f"registered sample size for action {action.action_id!r}"
            )
    return outcome


def _update_transcript(
    digest: "hashlib._Hash",
    value: object,
) -> None:
    """Append one unambiguous canonical record to a streaming SHA-256."""

    payload = canonical_json_bytes(value)
    digest.update(len(payload).to_bytes(8, byteorder="big", signed=False))
    digest.update(payload)


def classify_hypothesis_region(
    loss: Rational,
    thresholds: HypothesisThresholds,
) -> HypothesisRegion:
    """Derive H0/I/H1 from exact loss without accepting a caller label."""

    exact_loss = _strict_exact(loss, Rational, label="loss")
    exact_thresholds = _strict_exact(
        thresholds,
        HypothesisThresholds,
        label="thresholds",
    )
    loss_value = _fraction(exact_loss)
    if loss_value <= _fraction(exact_thresholds.tau0):
        return HypothesisRegion.H0
    if loss_value >= _fraction(exact_thresholds.epsilon):
        return HypothesisRegion.H1
    return HypothesisRegion.INDIFFERENCE


def decision_from_confidence_set(
    result: ConfidenceSetResult,
    family: ExactParameterFamily,
    decision_rule: ExactDecisionRuleSpec,
) -> DecisionOutcome:
    """Apply the fixed subset rule; empty, mixed, and I sets abstain."""

    checked_result = _strict_exact(
        result,
        ConfidenceSetResult,
        label="confidence result",
    )
    checked_family = _strict_exact(
        family,
        ExactParameterFamily,
        label="parameter family",
    )
    checked_rule = _strict_exact(
        decision_rule,
        ExactDecisionRuleSpec,
        label="decision rule",
    )
    universe_hash = checked_family.parameter_universe_hash
    if (
        checked_result.parameter_universe_hash != universe_hash
        or checked_rule.parameter_universe_hash != universe_hash
    ):
        raise ValueError(
            "confidence result, decision rule, and family universe differ"
        )
    return _decision_from_validated_members(
        checked_result.members,
        family=checked_family,
        decision_rule=checked_rule,
    )


def _decision_from_validated_members(
    members: tuple[str, ...],
    *,
    family: ExactParameterFamily,
    decision_rule: ExactDecisionRuleSpec,
) -> DecisionOutcome:
    """Apply the fixed decision rule to already shape-validated member IDs."""

    if decision_rule.parameter_universe_hash != family.parameter_universe_hash:
        raise ValueError(
            "decision rule and parameter family universe differ"
        )
    point_by_id = {
        point.parameter_id: point for point in family.points
    }
    unknown = tuple(
        member for member in members if member not in point_by_id
    )
    if unknown:
        raise ValueError(
            "confidence set contains members outside the parameter universe"
        )
    if not members:
        return DecisionOutcome.ABSTAIN

    regions = {
        classify_hypothesis_region(
            point_by_id[member].loss,
            family.thresholds,
        )
        for member in members
    }
    if regions == {HypothesisRegion.H0}:
        return DecisionOutcome.CERTIFY
    if regions == {HypothesisRegion.H1}:
        return DecisionOutcome.REJECT
    return DecisionOutcome.ABSTAIN


def verify_outer_approximation(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    exact_procedure: ConfidenceProcedureSpec,
    outer_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    exact_rule: ConfidenceRule,
    outer_rule: ConfidenceRule,
) -> OuterApproximationAssessment:
    """Verify inclusion and the decision-information order for every outcome."""

    actual_verifier_code_hash = confidence_module_sha256()
    checked_support = _strict_exact(
        support,
        ExactSupportSpec,
        label="support",
    )
    checked_family = _strict_exact(
        family,
        ExactParameterFamily,
        label="parameter family",
    )
    checked_exact = _strict_exact(
        exact_procedure,
        ConfidenceProcedureSpec,
        label="exact procedure",
    )
    checked_outer = _strict_exact(
        outer_procedure,
        ConfidenceProcedureSpec,
        label="outer procedure",
    )
    checked_rule = _strict_exact(
        decision_rule,
        ExactDecisionRuleSpec,
        label="decision rule",
    )
    support_hash = canonical_sha256(checked_support)
    universe_hash = checked_family.parameter_universe_hash
    if checked_family.support_spec_hash != support_hash:
        raise OuterApproximationViolation(
            "parameter family belongs to a different support"
        )
    if any(
        value != universe_hash
        for value in (
            checked_exact.parameter_universe_hash,
            checked_outer.parameter_universe_hash,
            checked_rule.parameter_universe_hash,
        )
    ):
        raise OuterApproximationViolation(
            "outer-approximation inputs use different parameter universes"
        )
    if not callable(exact_rule) or not callable(outer_rule):
        raise TypeError("exact_rule and outer_rule must be callable")
    exact_callable_hash = confidence_rule_implementation_sha256(exact_rule)
    outer_callable_hash = confidence_rule_implementation_sha256(outer_rule)
    if checked_exact.implementation_hash != exact_callable_hash:
        raise OuterApproximationViolation(
            "exact procedure hash does not bind the supplied implementation"
        )
    if checked_outer.implementation_hash != outer_callable_hash:
        raise OuterApproximationViolation(
            "outer procedure hash does not bind the supplied implementation"
        )
    for point in checked_family.points:
        # Binding is synchronous; the returned iterator is deliberately not
        # consumed because outer-set semantics do not require probability mass.
        iter_joint_outcome_probabilities(checked_support, point.law)

    support_plan = validate_and_size_support(checked_support)
    support_plan_hash = canonical_sha256(support_plan)
    exact_procedure_hash = canonical_sha256(checked_exact)
    outer_procedure_hash = canonical_sha256(checked_outer)
    decision_rule_hash = canonical_sha256(checked_rule)
    evaluation_input_bundle_hash = canonical_sha256(
        {
            "schema": "d2t_rna.outer_evaluation_input_bundle.v1",
            "contract_sha256": FROZEN_CONTRACT_SHA256,
            "support_spec_hash": support_hash,
            "support_plan_hash": support_plan_hash,
            "parameter_universe_hash": universe_hash,
            "probability_space_hash": (
                checked_family.probability_space_hash
            ),
            "synthetic_prerequisites_hash": (
                checked_family.synthetic_prerequisites_hash
            ),
            "sampling_law_manifest_hash": (
                checked_family.sampling_law_manifest_hash
            ),
            "exact_procedure_hash": exact_procedure_hash,
            "outer_procedure_hash": outer_procedure_hash,
            "decision_rule_hash": decision_rule_hash,
            "verifier_code_hash": actual_verifier_code_hash,
            "verifier_configuration_hash": (
                OUTER_APPROXIMATION_VERIFIER_V1_SHA256
            ),
        }
    )
    exact_transcript = hashlib.sha256()
    outer_transcript = hashlib.sha256()
    paired_transcript = hashlib.sha256()
    _update_transcript(
        exact_transcript,
        {
            "transcript_schema": (
                "d2t_rna.exact_result_decision_transcript.v1"
            ),
            "support_spec_hash": support_hash,
            "support_plan_hash": support_plan_hash,
            "parameter_universe_hash": universe_hash,
            "procedure_hash": exact_procedure_hash,
            "decision_rule_hash": decision_rule_hash,
        },
    )
    _update_transcript(
        paired_transcript,
        {
            "transcript_schema": (
                "d2t_rna.outer_paired_comparison_transcript.v1"
            ),
            "evaluation_input_bundle_hash": evaluation_input_bundle_hash,
        },
    )
    _update_transcript(
        outer_transcript,
        {
            "transcript_schema": (
                "d2t_rna.outer_result_decision_transcript.v1"
            ),
            "support_spec_hash": support_hash,
            "support_plan_hash": support_plan_hash,
            "parameter_universe_hash": universe_hash,
            "procedure_hash": outer_procedure_hash,
            "decision_rule_hash": decision_rule_hash,
        },
    )

    previous_outcome: JointOutcome | None = None
    outcome_count = 0
    removed_count = 0
    for raw_outcome in iter_joint_outcomes(checked_support):
        outcome = _validate_joint_outcome(raw_outcome, checked_support)
        if previous_outcome is not None and outcome <= previous_outcome:
            raise OuterApproximationViolation(
                "support iterator outcomes must be strictly increasing"
            )
        if outcome_count >= support_plan.joint_support_size:
            raise OuterApproximationViolation(
                "support iterator emitted more outcomes than its preflight count"
            )
        previous_outcome = outcome
        outcome_count += 1

        exact_result = _execute_rule_twice(
            exact_rule,
            outcome,
            label="exact",
        )
        outer_result = _execute_rule_twice(
            outer_rule,
            outcome,
            label="outer",
        )

        if not set(exact_result[0]).issubset(outer_result[0]):
            raise OuterApproximationViolation(
                "outer confidence set does not contain the exact confidence set"
            )
        exact_decision = _decision_from_validated_members(
            exact_result[0],
            family=checked_family,
            decision_rule=checked_rule,
        )
        outer_decision = _decision_from_validated_members(
            outer_result[0],
            family=checked_family,
            decision_rule=checked_rule,
        )
        if (
            exact_decision is DecisionOutcome.ABSTAIN
            and outer_decision is not DecisionOutcome.ABSTAIN
        ):
            raise OuterApproximationViolation(
                "outer approximation produced a new decisive outcome"
            )
        if (
            exact_decision is not DecisionOutcome.ABSTAIN
            and outer_decision is not DecisionOutcome.ABSTAIN
            and exact_decision is not outer_decision
        ):
            raise OuterApproximationViolation(
                "outer approximation flipped a deterministic decision"
            )
        if (
            exact_decision is not DecisionOutcome.ABSTAIN
            and outer_decision is DecisionOutcome.ABSTAIN
        ):
            removed_count += 1
        _update_transcript(
            exact_transcript,
            {
                "outcome_index": outcome_count - 1,
                "outcome": outcome,
                "confidence_result": _confidence_output_record(
                    exact_result,
                    parameter_universe_hash=universe_hash,
                ),
                "decision": exact_decision,
            },
        )
        _update_transcript(
            outer_transcript,
            {
                "outcome_index": outcome_count - 1,
                "outcome": outcome,
                "confidence_result": _confidence_output_record(
                    outer_result,
                    parameter_universe_hash=universe_hash,
                ),
                "decision": outer_decision,
            },
        )
        _update_transcript(
            paired_transcript,
            {
                "outcome_index": outcome_count - 1,
                "outcome": outcome,
                "exact_confidence_result": _confidence_output_record(
                    exact_result,
                    parameter_universe_hash=universe_hash,
                ),
                "outer_confidence_result": _confidence_output_record(
                    outer_result,
                    parameter_universe_hash=universe_hash,
                ),
                "exact_decision": exact_decision,
                "outer_decision": outer_decision,
                "inclusion_verified": True,
                "decision_order_verified": True,
            },
        )

    if outcome_count != support_plan.joint_support_size:
        raise OuterApproximationViolation(
            "support iterator outcome count does not match its preflight count"
        )
    if confidence_rule_implementation_sha256(
        exact_rule
    ) != exact_callable_hash:
        raise OuterApproximationViolation(
            "exact confidence implementation state changed during evaluation"
        )
    if confidence_rule_implementation_sha256(
        outer_rule
    ) != outer_callable_hash:
        raise OuterApproximationViolation(
            "outer confidence implementation state changed during evaluation"
        )
    if confidence_module_sha256() != actual_verifier_code_hash:
        raise OuterApproximationViolation(
            "outer verifier runtime changed during evaluation"
        )
    completion_footer = {
        "expected_outcome_count": support_plan.joint_support_size,
        "observed_outcome_count": outcome_count,
        "transcript_complete": True,
    }
    _update_transcript(exact_transcript, completion_footer)
    _update_transcript(outer_transcript, completion_footer)
    _update_transcript(paired_transcript, completion_footer)
    assessment = OuterApproximationAssessment(
        support_spec_hash=support_hash,
        support_plan_hash=support_plan_hash,
        parameter_universe_hash=universe_hash,
        probability_space_hash=checked_family.probability_space_hash,
        synthetic_prerequisites_hash=(
            checked_family.synthetic_prerequisites_hash
        ),
        sampling_law_manifest_hash=(
            checked_family.sampling_law_manifest_hash
        ),
        exact_procedure_hash=exact_procedure_hash,
        outer_procedure_hash=outer_procedure_hash,
        decision_rule_hash=decision_rule_hash,
        evaluation_input_bundle_hash=evaluation_input_bundle_hash,
        verifier_code_hash=actual_verifier_code_hash,
        verifier_configuration_hash=(
            OUTER_APPROXIMATION_VERIFIER_V1_SHA256
        ),
        exact_result_decision_transcript_hash=exact_transcript.hexdigest(),
        outer_result_decision_transcript_hash=outer_transcript.hexdigest(),
        paired_comparison_transcript_hash=paired_transcript.hexdigest(),
        transcript_complete=True,
        inclusion_verified=True,
        outcome_count=outcome_count,
        deterministic_decision_removed_count=removed_count,
        new_decisive_count=0,
        decision_flip_count=0,
        formal_scientific_certificate_authorized=False,
    )
    if confidence_module_sha256() != actual_verifier_code_hash:
        raise OuterApproximationViolation(
            "outer verifier runtime changed before assessment completion"
        )
    return assessment


def replay_outer_approximation_assessment(
    *,
    support: ExactSupportSpec,
    family: ExactParameterFamily,
    exact_procedure: ConfidenceProcedureSpec,
    outer_procedure: ConfidenceProcedureSpec,
    decision_rule: ExactDecisionRuleSpec,
    exact_rule: ConfidenceRule,
    outer_rule: ConfidenceRule,
    assessment: OuterApproximationAssessment,
) -> OuterApproximationReplayCredential:
    """Re-run raw inputs and return a distinct, explicitly non-bearer record."""

    _assert_fraction_runtime_integrity()
    rebuilt = _strict_exact(
        assessment,
        OuterApproximationAssessment,
        label="outer assessment",
    )
    expected = verify_outer_approximation(
        support=support,
        family=family,
        exact_procedure=exact_procedure,
        outer_procedure=outer_procedure,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
    )
    if rebuilt != expected:
        raise OuterApproximationViolation(
            "outer assessment does not replay from the registered raw inputs"
        )
    credential = OuterApproximationReplayCredential(
        assessment_hash=canonical_sha256(expected),
        evaluation_input_bundle_hash=(
            expected.evaluation_input_bundle_hash
        ),
        exact_result_decision_transcript_hash=(
            expected.exact_result_decision_transcript_hash
        ),
        outer_result_decision_transcript_hash=(
            expected.outer_result_decision_transcript_hash
        ),
        paired_comparison_transcript_hash=(
            expected.paired_comparison_transcript_hash
        ),
        verifier_code_hash=expected.verifier_code_hash,
        verifier_configuration_hash=(
            expected.verifier_configuration_hash
        ),
        live_replay_completed=True,
        external_source_anchor_required=True,
        serialized_bearer_authorization=False,
        formal_scientific_certificate_authorized=False,
    )
    _assert_fraction_runtime_integrity()
    return credential


_CONFIDENCE_RUNTIME_MODEL_TYPES = (
    FrozenContractModel,
    Rational,
    ProbabilitySpaceSpec,
    TrustedSemanticRegistry,
    SyntheticKnownChannelPrerequisites,
    ExactActionSpec,
    ExactSupportSpec,
    ExactSupportPlan,
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
    ProbabilityMassAudit,
    HypothesisRegion,
    DecisionOutcome,
    HypothesisThresholds,
    ExactParameterPoint,
    ExactSamplingLawEntry,
    ExactSamplingLawManifest,
    ExactParameterFamily,
    ConfidenceProcedureSpec,
    ExactDecisionRuleSpec,
    ConfidenceSetResult,
    OuterApproximationAssessment,
    OuterApproximationReplayCredential,
)
_FRACTION_RUNTIME_BASELINES = (
    (
        Fraction,
        canonical_sha256(_fraction_runtime_surface_descriptor()),
        _fraction_runtime_identity_token(),
    ),
)
_CONFIDENCE_MODEL_RUNTIME_BASELINES = tuple(
    (
        model_type,
        canonical_sha256(_type_runtime_surface_descriptor(model_type)),
        _type_runtime_identity_token(model_type),
    )
    for model_type in _CONFIDENCE_RUNTIME_MODEL_TYPES
)
