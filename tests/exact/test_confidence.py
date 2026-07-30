from __future__ import annotations

from fractions import Fraction
import sys
from types import FunctionType

import pytest
from pydantic import ValidationError

import d2t_rna.exact.confidence as confidence_runtime
from d2t_rna.contracts.base import (
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.exact.confidence import (
    EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
    ConfidenceProcedureSpec,
    ConfidenceSetResult,
    DecisionOutcome,
    ExactDecisionRuleSpec,
    HypothesisRegion,
    HypothesisThresholds,
    OuterApproximationReplayCredential,
    OuterApproximationViolation,
    classify_hypothesis_region,
    confidence_module_sha256,
    confidence_rule_implementation_sha256,
    decision_from_confidence_set,
    python_function_execution_sha256,
    replay_outer_approximation_assessment,
    verify_outer_approximation,
)

from .conftest import SHA_A, SHA_B, binary_support, rational, three_region_family


def _members_helper_a(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return ("omega.h0",)


def _members_helper_b(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return ("omega.h1",)


_GLOBAL_MEMBERS_HELPER = _members_helper_a


def _rule_using_global_helper(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return _GLOBAL_MEMBERS_HELPER


class _OpaqueDependency:
    pass


_OPAQUE_DEPENDENCY = _OpaqueDependency()


def _rule_using_opaque_global(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return _OPAQUE_DEPENDENCY


def _builtin_dispatch_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return dispatch(outcome)  # type: ignore[name-defined]


def _module_dispatch_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return helper_module.dispatch(outcome)  # type: ignore[name-defined]


def _class_dispatch_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return HelperClass.dispatch(outcome)  # type: ignore[name-defined]


def _inline_import_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    import task4_inline_helper

    return task4_inline_helper.dispatch(outcome)


def _function_attribute_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return helper_with_attributes(outcome)  # type: ignore[name-defined]


def _confidence_result_attribute_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return ConfidenceSetResult.dispatch(outcome)  # type: ignore[attr-defined]


def _global_callable_alias_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return lookup  # type: ignore[name-defined]


def _global_unordered_dependency_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return _CHOICES  # type: ignore[name-defined]


def _constant_iteration_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return ("omega.h0", "omega.h1")


def _set_builtin_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return set


def _class_fstring_template(
    outcome: tuple[tuple[int, ...], ...],
) -> str:
    return f"{ConfidenceSetResult}"


def _class_percent_template(
    outcome: tuple[tuple[int, ...], ...],
) -> str:
    return "%s" % ConfidenceSetResult


def _identity_template(
    outcome: tuple[tuple[int, ...], ...],
) -> bool:
    left = ("omega.h0",)
    right = ("omega.h0",)
    return left is right


def _float_constant_template(
    outcome: tuple[tuple[int, ...], ...],
) -> float:
    return 1.5


def _match_class_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    match outcome:
        case tuple():
            return ("omega.h0",), None
    return ("omega.h1",), None


def _int_builtin_template(
    outcome: tuple[tuple[int, ...], ...],
) -> object:
    return int


def _exception_control_flow_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    try:
        return ("omega.h0",)
    except BaseException:
        return ("omega.h1",)


def _alias_leaf_h0(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return ("omega.h0",)


def _alias_leaf_h1(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    return ("omega.h1",)


def _alias_binder_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return _H0(outcome), _H1(outcome)  # type: ignore[name-defined]


def _alias_root_template(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    _BINDER(outcome)  # type: ignore[name-defined]
    return _TARGET(outcome)  # type: ignore[name-defined]


_GLOBAL_HELPER_STATE = {"calls": 0}


def _stateful_members_helper(
    outcome: tuple[tuple[int, ...], ...],
) -> tuple[str, ...]:
    _GLOBAL_HELPER_STATE["calls"] += 1
    if _GLOBAL_HELPER_STATE["calls"] % 2:
        return ("omega.h0",)
    return ("omega.h1",)


def _procedure(
    family_hash: str,
    *,
    procedure_id: str,
    implementation_hash: str,
) -> ConfidenceProcedureSpec:
    return ConfidenceProcedureSpec(
        procedure_id=procedure_id,
        implementation_hash=implementation_hash,
        parameter_universe_hash=family_hash,
    )


def _decision_rule(family_hash: str) -> ExactDecisionRuleSpec:
    return ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=(
            EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=family_hash,
    )


def test_threshold_partition_uses_exact_closed_boundaries() -> None:
    thresholds = HypothesisThresholds(
        tau0=rational(1, 3),
        epsilon=rational(2, 3),
    )
    assert classify_hypothesis_region(rational(1, 3), thresholds) is HypothesisRegion.H0
    assert (
        classify_hypothesis_region(rational(1, 2), thresholds)
        is HypothesisRegion.INDIFFERENCE
    )
    assert classify_hypothesis_region(rational(2, 3), thresholds) is HypothesisRegion.H1
    with pytest.raises(ValidationError):
        HypothesisThresholds(tau0=rational(1), epsilon=rational(1))


def test_empty_confidence_set_is_explicit_failure_and_abstains() -> None:
    support = binary_support()
    family = three_region_family(support)
    result = ConfidenceSetResult(
        parameter_universe_hash=family.parameter_universe_hash,
        members=(),
        failure_reason="EMPTY_CONFIDENCE_SET",
    )
    decision = decision_from_confidence_set(
        result,
        family,
        _decision_rule(family.parameter_universe_hash),
    )
    assert decision is DecisionOutcome.ABSTAIN
    with pytest.raises(ValidationError):
        ConfidenceSetResult(
            parameter_universe_hash=family.parameter_universe_hash,
            members=(),
            failure_reason=None,
        )


def test_data_only_callback_output_validator_matches_frozen_shape() -> None:
    validate = confidence_runtime._validate_confidence_rule_output
    assert validate(
        (("omega.h0",), None),
        label="test",
    ) == (("omega.h0",), None)
    assert validate(
        ((), "EMPTY_CONFIDENCE_SET"),
        label="test",
    ) == ((), "EMPTY_CONFIDENCE_SET")
    for invalid in (
        [("omega.h0",), None],
        (("omega.h0", "omega.h0"), None),
        (("omega.indifference", "omega.h0"), None),
        (("not allowed",), None),
        ((), None),
        (("omega.h0",), "FAILURE"),
    ):
        with pytest.raises((TypeError, ValueError)):
            validate(invalid, label="test")


def test_outer_approximation_can_only_remove_deterministic_decisions() -> None:
    support = binary_support()
    family = three_region_family(support)
    universe_hash = family.parameter_universe_hash
    decision_rule = _decision_rule(universe_hash)

    def exact_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0",), None

    def outer_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0", "omega.indifference"), None

    exact = _procedure(
        universe_hash,
        procedure_id="confidence.exact",
        implementation_hash=confidence_rule_implementation_sha256(
            exact_rule
        ),
    )
    outer = _procedure(
        universe_hash,
        procedure_id="confidence.outer",
        implementation_hash=confidence_rule_implementation_sha256(
            outer_rule
        ),
    )
    assessment = verify_outer_approximation(
        support=support,
        family=family,
        exact_procedure=exact,
        outer_procedure=outer,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
    )
    assert assessment.inclusion_verified is True
    assert assessment.new_decisive_count == 0
    assert assessment.decision_flip_count == 0
    assert assessment.outcome_count == 2
    assert assessment.formal_scientific_certificate_authorized is False
    replayed = verify_outer_approximation(
        support=support,
        family=family,
        exact_procedure=exact,
        outer_procedure=outer,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
    )
    assert (
        replayed.exact_result_decision_transcript_hash
        == assessment.exact_result_decision_transcript_hash
    )
    assert (
        replayed.outer_result_decision_transcript_hash
        == assessment.outer_result_decision_transcript_hash
    )
    assert not isinstance(
        assessment,
        OuterApproximationReplayCredential,
    )
    assert not hasattr(assessment, "live_replay_completed")
    replay = replay_outer_approximation_assessment(
        support=support,
        family=family,
        exact_procedure=exact,
        outer_procedure=outer,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
        assessment=assessment,
    )
    assert isinstance(replay, OuterApproximationReplayCredential)
    assert replay.assessment_hash == canonical_sha256(assessment)
    assert replay.live_replay_completed is True
    assert replay.external_source_anchor_required is True
    assert replay.serialized_bearer_authorization is False
    assert replay.formal_scientific_certificate_authorized is False
    forged_transcript = assessment.model_copy(
        update={"paired_comparison_transcript_hash": "f" * 64}
    )
    with pytest.raises(OuterApproximationViolation, match="replay"):
        replay_outer_approximation_assessment(
            support=support,
            family=family,
            exact_procedure=exact,
            outer_procedure=outer,
            decision_rule=decision_rule,
            exact_rule=exact_rule,
            outer_rule=outer_rule,
            assessment=forged_transcript,
        )
    with pytest.raises(ValidationError):
        strict_revalidate_contract_model(
            assessment.model_copy(
                update={
                    "formal_scientific_certificate_authorized": True,
                }
            )
        )
    with pytest.raises(ValidationError):
        strict_revalidate_contract_model(
            assessment.model_copy(update={"outcome_count": 0})
        )
    with pytest.raises(ValidationError):
        strict_revalidate_contract_model(
            assessment.model_copy(
                update={
                    "deterministic_decision_removed_count": (
                        assessment.outcome_count + 1
                    )
                }
            )
        )


def test_outer_approximation_rejects_missing_members_and_new_decisions() -> None:
    support = binary_support()
    family = three_region_family(support)
    universe_hash = family.parameter_universe_hash
    decision_rule = _decision_rule(universe_hash)

    def exact_nonempty(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0", "omega.indifference"), None

    def missing_member(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0",), None

    exact = _procedure(
        universe_hash,
        procedure_id="confidence.exact",
        implementation_hash=confidence_rule_implementation_sha256(
            exact_nonempty
        ),
    )
    outer = _procedure(
        universe_hash,
        procedure_id="confidence.outer",
        implementation_hash=confidence_rule_implementation_sha256(
            missing_member
        ),
    )
    with pytest.raises(OuterApproximationViolation, match="contain"):
        verify_outer_approximation(
            support=support,
            family=family,
            exact_procedure=exact,
            outer_procedure=outer,
            decision_rule=decision_rule,
            exact_rule=exact_nonempty,
            outer_rule=missing_member,
        )

    def exact_empty(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], str]:
        return (), "EMPTY_CONFIDENCE_SET"

    with pytest.raises(OuterApproximationViolation, match="decisive"):
        empty_exact = _procedure(
            universe_hash,
            procedure_id="confidence.exact-empty",
            implementation_hash=confidence_rule_implementation_sha256(
                exact_empty
            ),
        )
        verify_outer_approximation(
            support=support,
            family=family,
            exact_procedure=empty_exact,
            outer_procedure=outer,
            decision_rule=decision_rule,
            exact_rule=exact_empty,
            outer_rule=missing_member,
        )


def test_confidence_result_rejects_unknown_unsorted_or_wrong_universe_members() -> None:
    support = binary_support()
    family = three_region_family(support)
    with pytest.raises(ValidationError):
        ConfidenceSetResult(
            parameter_universe_hash=family.parameter_universe_hash,
            members=("omega.indifference", "omega.h0"),
            failure_reason=None,
        )

    wrong_universe = ConfidenceSetResult(
        parameter_universe_hash="f" * 64,
        members=("omega.h0",),
        failure_reason=None,
    )
    with pytest.raises(ValueError, match="universe"):
        decision_from_confidence_set(
            wrong_universe,
            family,
            _decision_rule(family.parameter_universe_hash),
        )
    assert canonical_sha256(family) == family.parameter_universe_hash


def test_outer_binds_actual_callable_and_rejects_state_change() -> None:
    support = binary_support()
    family = three_region_family(support)
    universe_hash = family.parameter_universe_hash
    decision_rule = _decision_rule(universe_hash)

    def stable_outer(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0", "omega.indifference"), None

    def stable_exact(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0",), None

    mismatched = _procedure(
        universe_hash,
        procedure_id="confidence.mismatched",
        implementation_hash="f" * 64,
    )
    outer = _procedure(
        universe_hash,
        procedure_id="confidence.outer.stable",
        implementation_hash=confidence_rule_implementation_sha256(
            stable_outer
        ),
    )
    with pytest.raises(OuterApproximationViolation, match="does not bind"):
        verify_outer_approximation(
            support=support,
            family=family,
            exact_procedure=mismatched,
            outer_procedure=outer,
            decision_rule=decision_rule,
            exact_rule=stable_exact,
            outer_rule=stable_outer,
        )

    mutable_state = {"calls": 0}

    def stateful_exact(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        mutable_state["calls"] += 1
        return ("omega.h0",), None

    with pytest.raises(TypeError, match="STORE_SUBSCR|mutable execution state"):
        confidence_rule_implementation_sha256(
            stateful_exact
        )


def test_callback_hash_ignores_source_path_and_rejects_helper_or_opaque_global(
) -> None:
    def self_contained_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0",), None

    baseline = confidence_rule_implementation_sha256(self_contained_rule)
    relocated = FunctionType(
        self_contained_rule.__code__.replace(
            co_filename="/different/source/root/test_confidence.py"
        ),
        self_contained_rule.__globals__,
        self_contained_rule.__name__,
        self_contained_rule.__defaults__,
        self_contained_rule.__closure__,
    )
    relocated.__module__ = self_contained_rule.__module__
    relocated.__qualname__ = self_contained_rule.__qualname__
    assert confidence_rule_implementation_sha256(relocated) == baseline

    with pytest.raises(TypeError, match="self-contained"):
        confidence_rule_implementation_sha256(_rule_using_global_helper)
    with pytest.raises(TypeError, match="strict immutable allowlist"):
        confidence_rule_implementation_sha256(_rule_using_opaque_global)


def test_callback_rejects_custom_builtins_module_and_helper_class() -> None:
    custom_builtin_rule = FunctionType(
        _builtin_dispatch_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": {"dispatch": _members_helper_a},
        },
        "custom_builtin_rule",
    )
    with pytest.raises(
        TypeError,
        match=r"outside the strict allowlist: (?:PRECALL|CALL)",
    ):
        confidence_rule_implementation_sha256(custom_builtin_rule)

    spoofed_len_rule = FunctionType(
        _builtin_dispatch_template.__code__.replace(
            co_names=("len",),
        ),
        {
            "__name__": __name__,
            "__builtins__": {"len": _members_helper_a},
        },
        "spoofed_len_rule",
    )
    with pytest.raises(
        TypeError,
        match=r"outside the strict allowlist: (?:PRECALL|CALL)",
    ):
        confidence_rule_implementation_sha256(spoofed_len_rule)

    from types import ModuleType

    helper_module = ModuleType("task4_dynamic_helper")
    helper_module.dispatch = _members_helper_a
    module_rule = FunctionType(
        _module_dispatch_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "helper_module": helper_module,
        },
        "module_rule",
    )
    with pytest.raises(TypeError, match=r"LOAD_(?:ATTR|METHOD)"):
        confidence_rule_implementation_sha256(module_rule)

    class HelperClass:
        dispatch = staticmethod(_members_helper_a)

    class_rule = FunctionType(
        _class_dispatch_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "HelperClass": HelperClass,
        },
        "class_rule",
    )
    with pytest.raises(TypeError, match=r"LOAD_(?:ATTR|METHOD)"):
        confidence_rule_implementation_sha256(class_rule)

    with pytest.raises(TypeError, match="IMPORT_NAME"):
        confidence_rule_implementation_sha256(_inline_import_template)

    def helper_with_attributes(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[str, ...]:
        return ("omega.h0",)

    helper_with_attributes.members = ("omega.h0",)
    attribute_rule = FunctionType(
        _function_attribute_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "helper_with_attributes": helper_with_attributes,
        },
        "attribute_rule",
    )
    with pytest.raises(
        TypeError,
        match=r"outside the strict allowlist: (?:PRECALL|CALL)",
    ):
        confidence_rule_implementation_sha256(attribute_rule)

    with pytest.raises(TypeError, match="LOAD_ATTR"):
        confidence_rule_implementation_sha256(
            _confidence_result_attribute_template
        )


def test_callback_rejects_bound_builtin_and_import_aliases() -> None:
    state = {"members": ("omega.h0",)}
    bound_method_rule = FunctionType(
        _global_callable_alias_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "ConfidenceSetResult": ConfidenceSetResult,
            "lookup": state.get,
            "universe_hash": "a" * 64,
        },
        "bound_method_rule",
    )
    with pytest.raises(TypeError, match="allowlisted canonical builtin"):
        confidence_rule_implementation_sha256(bound_method_rule)

    non_strict_before = python_function_execution_sha256(
        bound_method_rule,
        purpose="TEST_BOUND_METHOD_SELF",
        strict_pure=False,
    )
    state["members"] = ("omega.h1",)
    non_strict_after = python_function_execution_sha256(
        bound_method_rule,
        purpose="TEST_BOUND_METHOD_SELF",
        strict_pure=False,
    )
    assert non_strict_before != non_strict_after

    import_alias_rule = FunctionType(
        _global_callable_alias_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "lookup": __import__,
        },
        "import_alias_rule",
    )
    with pytest.raises(TypeError, match="allowlisted canonical builtin"):
        confidence_rule_implementation_sha256(import_alias_rule)


def test_callback_rejects_container_subclasses_and_unordered_dependencies() -> None:
    class SneakyDict(dict[str, tuple[str, ...]]):
        mode = "h0"

        def __getitem__(self, key: str) -> tuple[str, ...]:
            if key == "members" and self.mode == "h1":
                return ("omega.h1",)
            return super().__getitem__(key)

    state = SneakyDict(members=("omega.h0",))

    def subclass_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return state["members"], None

    with pytest.raises(TypeError, match="strict immutable allowlist"):
        confidence_rule_implementation_sha256(subclass_rule)

    unordered_rule = FunctionType(
        _global_unordered_dependency_template.__code__,
        {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "ConfidenceSetResult": ConfidenceSetResult,
            "_CHOICES": frozenset({"omega.h0", "omega.h1"}),
            "universe_hash": "a" * 64,
        },
        "unordered_rule",
    )
    with pytest.raises(TypeError, match="strict immutable allowlist"):
        confidence_rule_implementation_sha256(unordered_rule)

    with pytest.raises(TypeError, match="non-allowlisted builtin"):
        confidence_rule_implementation_sha256(_set_builtin_template)


def test_callback_rejects_frozenset_code_constant_after_code_replacement() -> None:
    replaced_constants = tuple(
        (
            frozenset({"omega.h0", "omega.h1"})
            if value == ("omega.h0", "omega.h1")
            else value
        )
        for value in _constant_iteration_template.__code__.co_consts
    )
    assert any(type(value) is frozenset for value in replaced_constants)
    rule = FunctionType(
        _constant_iteration_template.__code__.replace(
            co_consts=replaced_constants
        ),
        _constant_iteration_template.__globals__,
        "frozenset_constant_rule",
    )
    with pytest.raises(TypeError, match="unordered frozenset constant"):
        confidence_rule_implementation_sha256(rule)


def test_callback_rejects_object_formatting_identity_and_float_constants() -> None:
    with pytest.raises(TypeError, match=r"FORMAT_(?:VALUE|SIMPLE)"):
        confidence_rule_implementation_sha256(_class_fstring_template)
    with pytest.raises(TypeError, match="percent formatting|BINARY_MODULO"):
        confidence_rule_implementation_sha256(_class_percent_template)
    with pytest.raises(TypeError, match="IS_OP"):
        confidence_rule_implementation_sha256(_identity_template)
    with pytest.raises(TypeError, match="non-reflexive-capable"):
        confidence_rule_implementation_sha256(_float_constant_template)
    with pytest.raises(TypeError, match="MATCH_CLASS"):
        confidence_rule_implementation_sha256(_match_class_template)
    with pytest.raises(TypeError, match="non-allowlisted builtin"):
        confidence_rule_implementation_sha256(_int_builtin_template)
    with pytest.raises(TypeError, match="exception-handling control flow"):
        confidence_rule_implementation_sha256(
            _exception_control_flow_template
        )


def test_non_strict_dependency_graph_binds_function_alias_target() -> None:
    h0 = FunctionType(
        _alias_leaf_h0.__code__,
        _alias_leaf_h0.__globals__,
        "shared_leaf",
    )
    h1 = FunctionType(
        _alias_leaf_h1.__code__,
        _alias_leaf_h1.__globals__,
        "shared_leaf",
    )
    for leaf in (h0, h1):
        leaf.__module__ = "task4.alias_graph"
        leaf.__qualname__ = "shared_leaf"
    binder = FunctionType(
        _alias_binder_template.__code__,
        {
            "__name__": "task4.alias_graph",
            "__builtins__": __builtins__,
            "_H0": h0,
            "_H1": h1,
        },
        "binder",
    )
    root_globals = {
        "__name__": "task4.alias_graph",
        "__builtins__": __builtins__,
        "_BINDER": binder,
        "_TARGET": h0,
    }
    root = FunctionType(
        _alias_root_template.__code__,
        root_globals,
        "root",
    )
    before = python_function_execution_sha256(
        root,
        purpose="TEST_ALIAS_GRAPH",
        strict_pure=False,
    )
    root_globals["_TARGET"] = h1
    after = python_function_execution_sha256(
        root,
        purpose="TEST_ALIAS_GRAPH",
        strict_pure=False,
    )
    assert before != after


def test_runtime_model_class_mutation_fails_before_callback_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raw_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return ("omega.h0",), None

    baseline = confidence_rule_implementation_sha256(raw_rule)

    def replacement_init(self, **kwargs) -> None:
        object.__setattr__(self, "members", ("omega.h1",))

    monkeypatch.setattr(
        ConfidenceSetResult,
        "__init__",
        replacement_init,
    )
    with pytest.raises(RuntimeError, match="mutated after import"):
        confidence_rule_implementation_sha256(raw_rule)
    with pytest.raises(RuntimeError, match="mutated after import"):
        confidence_module_sha256()
    assert baseline


def test_outer_runtime_hash_binds_local_helper_and_task2_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean = confidence_module_sha256()
    original_execute = confidence_runtime._execute_rule_twice

    def replacement_execute(*args, **kwargs):
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(
        confidence_runtime,
        "_execute_rule_twice",
        replacement_execute,
    )
    assert confidence_module_sha256() != clean

    monkeypatch.setattr(
        confidence_runtime,
        "_execute_rule_twice",
        original_execute,
    )
    restored = confidence_module_sha256()
    original_scope = confidence_runtime.assess_probability_scope

    def replacement_scope(*args, **kwargs):
        return original_scope(*args, **kwargs)

    monkeypatch.setattr(
        confidence_runtime,
        "assess_probability_scope",
        replacement_scope,
    )
    assert confidence_module_sha256() != restored


def test_stateful_global_helper_is_rejected_before_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "_GLOBAL_HELPER_STATE", {"calls": 0})
    support = binary_support()
    family = three_region_family(support)
    universe_hash = family.parameter_universe_hash

    def stateful_via_global_helper(
        outcome: tuple[tuple[int, ...], ...],
    ) -> object:
        return _stateful_members_helper

    with pytest.raises(TypeError, match="self-contained"):
        confidence_rule_implementation_sha256(
            stateful_via_global_helper
        )


def test_exact_public_api_exports_every_declared_symbol() -> None:
    import d2t_rna.exact as exact_api

    assert exact_api.__all__
    assert all(hasattr(exact_api, name) for name in exact_api.__all__)
    assert exact_api.OuterApproximationReplayCredential is (
        OuterApproximationReplayCredential
    )
