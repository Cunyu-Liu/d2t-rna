from __future__ import annotations

from fractions import Fraction
import operator
from pathlib import Path
from types import FunctionType, ModuleType

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import (
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import ProbabilityScope
import d2t_rna.exact.confidence as confidence_runtime
import d2t_rna.exact.coverage as coverage_runtime
import d2t_rna.exact.enumerate as enumerate_runtime
from d2t_rna.exact.confidence import (
    EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
    ConfidenceProcedureSpec,
    ExactDecisionRuleSpec,
    ExactParameterFamily,
    ExactParameterPoint,
    HypothesisThresholds,
    confidence_module_sha256,
    confidence_rule_implementation_sha256,
)
from d2t_rna.exact.enumerate import (
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
)
from d2t_rna.exact.support import ExactActionSpec, ExactSupportSpec
from d2t_rna.exact.coverage import (
    CoverageSemanticError,
    ExactSyntheticCoverageReport,
    ExactSyntheticCoverageReplayCredential,
    H0PointRiskCoverage,
    H1PointRiskCoverage,
    IndifferencePointRiskCoverage,
    coverage_module_sha256,
    evaluate_exact_synthetic_risk_coverage,
    replay_exact_synthetic_coverage_report,
)

from .conftest import (
    SHA_A,
    SHA_B,
    SHA_C,
    binary_support,
    law,
    parameter_family,
    rational,
    run_task4_isolated_child,
    three_region_family,
)
from .naive_oracle import naive_risk_coverage_report


def _evaluation_inputs(
    family: ExactParameterFamily,
    *,
    support=None,
):
    if support is None:
        support = binary_support()
    universe_hash = family.parameter_universe_hash
    decision_rule = ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=(
            EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=universe_hash,
    )
    non_h0_members = tuple(
        point.parameter_id
        for point in family.points
        if point.parameter_id != "omega.h0"
    )

    def confidence_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        if outcome == ((1, 0),):
            return ("omega.h0",), None
        return non_h0_members, None

    procedure = ConfidenceProcedureSpec(
        procedure_id="confidence.fixture.v1",
        implementation_hash=confidence_rule_implementation_sha256(
            confidence_rule
        ),
        parameter_universe_hash=universe_hash,
    )
    return support, family, procedure, decision_rule, confidence_rule


def _evaluate(
    family: ExactParameterFamily,
    *,
    support=None,
):
    (
        checked_support,
        checked_family,
        procedure,
        decision_rule,
        confidence_rule,
    ) = _evaluation_inputs(family, support=support)
    return evaluate_exact_synthetic_risk_coverage(
        support=checked_support,
        family=checked_family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=confidence_rule,
        engine_code_hash=coverage_module_sha256(),
    )


def test_full_evaluator_rejects_dynamic_mapping_subclass_dependency() -> None:
    class SneakyDict(dict[str, tuple[str, ...]]):
        mode = "h0"

        def __getitem__(self, key: str) -> tuple[str, ...]:
            if key == "members" and self.mode == "h1":
                return ("omega.h1",)
            return super().__getitem__(key)

    support = binary_support()
    family = three_region_family(support)
    universe_hash = family.parameter_universe_hash
    state = SneakyDict(members=("omega.h0",))

    def confidence_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        return state["members"], None

    procedure = ConfidenceProcedureSpec(
        procedure_id="confidence.sneaky-mapping",
        implementation_hash="a" * 64,
        parameter_universe_hash=universe_hash,
    )
    decision_rule = ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=(
            EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=universe_hash,
    )
    with pytest.raises(TypeError, match="strict immutable allowlist"):
        evaluate_exact_synthetic_risk_coverage(
            support=support,
            family=family,
            confidence_procedure=procedure,
            decision_rule=decision_rule,
            confidence_rule=confidence_rule,
            engine_code_hash=coverage_module_sha256(),
        )


def test_exact_indifference_boundary_and_claim_scope() -> None:
    support = binary_support()
    family = three_region_family(support)
    (
        checked_support,
        checked_family,
        procedure,
        decision_rule,
        confidence_rule,
    ) = _evaluation_inputs(family, support=support)
    report = evaluate_exact_synthetic_risk_coverage(
        support=checked_support,
        family=checked_family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=confidence_rule,
        engine_code_hash=coverage_module_sha256(),
    )
    assert report.indifference_decisive_output_bound == rational(1, 20)
    assert report.confidence_set_uniform_coverage == rational(19, 20)
    assert report.h0_wrong_reject_bound == rational(0)
    assert report.h1_wrong_certify_bound == rational(0)
    assert report.mathematical_statement_verified is True
    assert report.probability_scope is ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL
    assert report.claim_domain == "EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY"
    assert report.evidence_grade == "EXACT_RATIONAL_ENUMERATION"
    assert report.risk_certificate_issued is False
    assert report.formal_scientific_certificate_authorized is False
    assert report.prospective_claim_authorized is False
    assert report.new_library_claim_authorized is False
    assert report.probability_mass_accounted == rational(1)
    assert report.omitted_mass_bound == rational(0)
    assert report.numerical_error_bound == rational(0)
    assert not isinstance(
        report,
        ExactSyntheticCoverageReplayCredential,
    )
    assert not hasattr(report, "live_replay_completed")
    replay = replay_exact_synthetic_coverage_report(
        support=checked_support,
        family=checked_family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=confidence_rule,
        engine_code_hash=coverage_module_sha256(),
        report=report,
    )
    assert isinstance(replay, ExactSyntheticCoverageReplayCredential)
    assert replay.report_hash == canonical_sha256(report)
    assert replay.evaluation_input_bundle_hash == (
        report.evaluation_input_bundle_hash
    )
    assert replay.live_replay_completed is True
    assert replay.external_source_anchor_required is True
    assert replay.serialized_bearer_authorization is False
    assert replay.formal_scientific_certificate_authorized is False
    forged = report.model_copy(
        update={"evaluation_transcript_hash": "f" * 64}
    )
    try:
        replay_exact_synthetic_coverage_report(
            support=checked_support,
            family=checked_family,
            confidence_procedure=procedure,
            decision_rule=decision_rule,
            confidence_rule=confidence_rule,
            engine_code_hash=coverage_module_sha256(),
            report=forged,
        )
    except CoverageSemanticError as exc:
        assert "replay" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("forged exact report replayed successfully")


def test_bad_indifference_point_cannot_hide_in_average() -> None:
    support = binary_support()
    thresholds = HypothesisThresholds(
        tau0=rational(1),
        epsilon=rational(3),
    )
    family = parameter_family(
        support,
        thresholds=thresholds,
        points=(
            ExactParameterPoint(
                parameter_id="omega.h0",
                loss=rational(1),
                law=law(
                    support,
                    ((1, 1), (0, 1)),
                    law_id="law.h0",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.h1",
                loss=rational(3),
                law=law(
                    support,
                    ((0, 1), (1, 1)),
                    law_id="law.h1",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.i.bad",
                loss=rational(2),
                law=law(
                    support,
                    ((3, 50), (47, 50)),
                    law_id="law.i.bad",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.i.safe",
                loss=rational(5, 2),
                law=law(
                    support,
                    ((0, 1), (1, 1)),
                    law_id="law.i.safe",
                ),
            ),
        ),
    )
    report = _evaluate(family, support=support)
    assert report.indifference_decisive_output_bound == rational(3, 50)
    assert report.indifference_worst_parameter_id == "omega.i.bad"
    assert report.mathematical_statement_verified is False

    h0_results = tuple(
        item for item in report.point_results if isinstance(item, H0PointRiskCoverage)
    )
    h1_results = tuple(
        item for item in report.point_results if isinstance(item, H1PointRiskCoverage)
    )
    indifference_results = tuple(
        item
        for item in report.point_results
        if isinstance(item, IndifferencePointRiskCoverage)
    )
    assert len(h0_results) == 1
    assert len(h1_results) == 1
    assert len(indifference_results) == 2
    assert h0_results[0].wrong_reject_probability == rational(0)
    assert h1_results[0].wrong_certify_probability == rational(0)


def test_indifference_error_is_unconditional_not_decision_conditioned() -> None:
    support = binary_support()
    report = _evaluate(three_region_family(support), support=support)
    indifference = next(
        item
        for item in report.point_results
        if isinstance(item, IndifferencePointRiskCoverage)
    )
    assert indifference.p_certify == rational(1, 20)
    assert indifference.p_abstain == rational(19, 20)
    assert indifference.decisive_probability == rational(1, 20)


def test_registered_indifference_set_cannot_vacuously_pass() -> None:
    support = binary_support()
    thresholds = HypothesisThresholds(
        tau0=rational(1),
        epsilon=rational(3),
    )
    family = parameter_family(
        support,
        thresholds=thresholds,
        points=(
            ExactParameterPoint(
                parameter_id="omega.h0",
                loss=rational(1),
                law=law(
                    support,
                    ((1, 1), (0, 1)),
                    law_id="law.h0",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.h1",
                loss=rational(3),
                law=law(
                    support,
                    ((0, 1), (1, 1)),
                    law_id="law.h1",
                ),
            ),
        ),
    )
    try:
        _evaluate(family, support=support)
    except CoverageSemanticError as exc:
        assert "indifference" in str(exc).lower()
    else:  # pragma: no cover - fail loudly if the gate becomes vacuous
        raise AssertionError("empty registered indifference set was accepted")


def test_multi_action_end_to_end_matches_independent_naive_oracle() -> None:
    support = ExactSupportSpec(
        state_ids=("state.0", "state.1"),
        actions=(
            ExactActionSpec(
                action_id="action.0",
                sample_size=2,
                alphabet=("symbol.0", "symbol.1"),
            ),
            ExactActionSpec(
                action_id="action.1",
                sample_size=1,
                alphabet=("symbol.0", "symbol.1"),
            ),
        ),
    )

    def multi_law(
        law_id: str,
        rows: tuple[tuple[tuple[int, int], ...], ...],
    ) -> IndependentMultinomialLaw:
        return IndependentMultinomialLaw(
            law_id=law_id,
            support_spec_hash=canonical_sha256(support),
            action_probabilities=tuple(
                IndependentActionProbabilities(
                    action_id=f"action.{index}",
                    probabilities=tuple(
                        rational(numerator, denominator)
                        for numerator, denominator in row
                    ),
                )
                for index, row in enumerate(rows)
            ),
        )

    thresholds = HypothesisThresholds(
        tau0=rational(1),
        epsilon=rational(3),
    )
    family = parameter_family(
        support,
        thresholds=thresholds,
        points=(
            ExactParameterPoint(
                parameter_id="omega.h0",
                loss=rational(1),
                law=multi_law(
                    "law.multi.h0",
                    (
                        ((1, 1), (0, 1)),
                        ((1, 1), (0, 1)),
                    ),
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.h1",
                loss=rational(3),
                law=multi_law(
                    "law.multi.h1",
                    (
                        ((0, 1), (1, 1)),
                        ((0, 1), (1, 1)),
                    ),
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.indifference",
                loss=rational(2),
                law=multi_law(
                    "law.multi.indifference",
                    (
                        ((1, 4), (3, 4)),
                        ((1, 4), (3, 4)),
                    ),
                ),
            ),
        ),
    )
    universe_hash = family.parameter_universe_hash

    def members_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[str, ...]:
        if outcome == ((2, 0), (1, 0)):
            return ("omega.h0",)
        return ("omega.h1", "omega.indifference")

    def confidence_rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        if outcome == ((2, 0), (1, 0)):
            members = ("omega.h0",)
        else:
            members = ("omega.h1", "omega.indifference")
        return members, None

    procedure = ConfidenceProcedureSpec(
        procedure_id="confidence.multi-action.oracle",
        implementation_hash=confidence_rule_implementation_sha256(
            confidence_rule
        ),
        parameter_universe_hash=universe_hash,
    )
    decision_rule = ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=(
            EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=universe_hash,
    )
    exact = evaluate_exact_synthetic_risk_coverage(
        support=support,
        family=family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule=confidence_rule,
        engine_code_hash=coverage_module_sha256(),
    )
    naive = naive_risk_coverage_report(
        support=support,
        family=family,
        members_rule=members_rule,
    )

    def integer_pair(value: object) -> tuple[int, int]:
        numerator = getattr(value, "numerator")
        denominator = getattr(value, "denominator")
        assert type(numerator) is int
        assert type(denominator) is int
        return numerator, denominator

    assert exact.outcome_count == naive["outcome_count"] == 6
    assert naive["h0_wrong_reject_bound"] == (0, 1)
    assert naive["h1_wrong_certify_bound"] == (0, 1)
    assert naive["indifference_decisive_output_bound"] == (1, 64)
    assert naive["confidence_set_uniform_coverage"] == (63, 64)
    assert (
        integer_pair(exact.h0_wrong_reject_bound)
        == naive["h0_wrong_reject_bound"]
    )
    assert (
        integer_pair(exact.h1_wrong_certify_bound)
        == naive["h1_wrong_certify_bound"]
    )
    assert (
        integer_pair(exact.indifference_decisive_output_bound)
        == naive["indifference_decisive_output_bound"]
    )
    assert (
        integer_pair(exact.confidence_set_uniform_coverage)
        == naive["confidence_set_uniform_coverage"]
    )

    exact_by_id = {
        result.parameter_id: result for result in exact.point_results
    }
    assert naive["point_results"]["omega.indifference"]["certify"] == (
        1,
        64,
    )
    assert naive["point_results"]["omega.indifference"]["coverage"] == (
        63,
        64,
    )
    for parameter_id, expected in naive["point_results"].items():
        observed = exact_by_id[parameter_id]
        assert integer_pair(observed.total_probability) == expected["total"]
        assert integer_pair(observed.coverage) == expected["coverage"]
        assert integer_pair(observed.p_certify) == expected["certify"]
        assert integer_pair(observed.p_reject) == expected["reject"]
        assert integer_pair(observed.p_abstain) == expected["abstain"]


def test_runtime_enumerator_replacement_invalidates_clean_engine_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    (
        checked_support,
        checked_family,
        procedure,
        decision_rule,
        confidence_rule,
    ) = _evaluation_inputs(family, support=support)
    clean_engine_hash = coverage_module_sha256()
    original = coverage_runtime.iter_joint_outcome_probabilities

    def replacement(support_spec, registered_law):
        yield from original(support_spec, registered_law)

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        replacement,
    )
    assert coverage_module_sha256() != clean_engine_hash
    with pytest.raises(CoverageSemanticError, match="engine_code_hash"):
        evaluate_exact_synthetic_risk_coverage(
            support=checked_support,
            family=checked_family,
            confidence_procedure=procedure,
            decision_rule=decision_rule,
            confidence_rule=confidence_rule,
            engine_code_hash=clean_engine_hash,
        )


def test_cold_python311_fixture_build_has_stable_engine_hash(
    tmp_path: Path,
) -> None:
    script = """
from pathlib import Path
import sys
from scripts.build_task4_acceptance_fixture import build_fixture

artifact_root = Path(sys.argv[1])
summary = build_fixture(
    project_root=Path.cwd(),
    output_dir=artifact_root / "fixture",
    artifact_root=artifact_root,
)
assert summary["mathematical_statement_verified"] is True
assert summary["risk_certificate_issued"] is False
"""
    completed = run_task4_isolated_child(
        child_artifact_dir=tmp_path / "cold-fixture-child",
        source=script,
        arguments=(str(tmp_path),),
    )
    assert completed.returncode == 0, completed.stderr


def test_local_coverage_helper_replacement_invalidates_engine_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    inputs = _evaluation_inputs(family, support=support)
    clean_engine_hash = coverage_module_sha256()
    original = coverage_runtime._build_point_result

    def replacement(*args, **kwargs):
        return original(*args, **kwargs)

    monkeypatch.setattr(
        coverage_runtime,
        "_build_point_result",
        replacement,
    )
    assert coverage_module_sha256() != clean_engine_hash
    with pytest.raises(CoverageSemanticError, match="engine_code_hash"):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=clean_engine_hash,
        )


def test_coverage_report_class_mutation_invalidates_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_engine_hash = coverage_module_sha256()

    def replacement_init(self, **kwargs) -> None:
        object.__setattr__(
            self,
            "formal_scientific_certificate_authorized",
            True,
        )

    monkeypatch.setattr(
        ExactSyntheticCoverageReport,
        "__init__",
        replacement_init,
    )
    with pytest.raises(RuntimeError, match="mutated after import"):
        coverage_module_sha256()
    assert clean_engine_hash


def test_fraction_protocol_mutation_invalidates_all_engine_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    inputs = _evaluation_inputs(family, support=support)
    clean_confidence_hash = confidence_module_sha256()
    clean_coverage_hash = coverage_module_sha256()

    def forged_less_equal(self, other):
        return True

    with monkeypatch.context() as patch:
        patch.setattr(Fraction, "__le__", forged_less_equal)
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            coverage_module_sha256()
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            evaluate_exact_synthetic_risk_coverage(
                support=inputs[0],
                family=inputs[1],
                confidence_procedure=inputs[2],
                decision_rule=inputs[3],
                confidence_rule=inputs[4],
                engine_code_hash=clean_coverage_hash,
            )

    assert confidence_module_sha256() == clean_confidence_hash
    assert coverage_module_sha256() == clean_coverage_hash


def test_fraction_nested_execution_dependencies_are_identity_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_hash = confidence_module_sha256()
    function_cell = next(
        cell
        for cell in Fraction.__add__.__closure__ or ()
        if type(cell.cell_contents) is FunctionType
    )
    original_cell_value = function_cell.cell_contents

    def replacement(*args, **kwargs):
        return original_cell_value(*args, **kwargs)

    try:
        function_cell.cell_contents = replacement
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()
    finally:
        function_cell.cell_contents = original_cell_value

    with monkeypatch.context() as patch:
        patch.setattr(operator, "le", replacement)
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()

    numerator_getter = Fraction.numerator.fget
    denominator_getter = Fraction.denominator.fget
    assert numerator_getter is not None
    assert denominator_getter is not None
    with monkeypatch.context() as patch:
        patch.setattr(
            numerator_getter,
            "__code__",
            denominator_getter.__code__,
        )
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()

    assert confidence_module_sha256() == clean_hash


def test_fraction_internal_alias_and_module_dispatch_are_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_confidence_hash = confidence_module_sha256()
    clean_coverage_hash = coverage_module_sha256()
    original_richcmp = Fraction._richcmp

    def replacement(*args, **kwargs):
        return original_richcmp(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Fraction, "_richcmp", replacement)
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()

    with monkeypatch.context() as patch:
        patch.setattr(coverage_runtime, "Fraction", object)
        with pytest.raises(RuntimeError, match="coverage"):
            coverage_module_sha256()

    with monkeypatch.context() as patch:
        patch.setattr(enumerate_runtime, "Fraction", object)
        with pytest.raises(RuntimeError, match="enumerate"):
            coverage_module_sha256()

    class AlternateModuleType(ModuleType):
        pass

    original_module_type = operator.__class__
    try:
        operator.__class__ = AlternateModuleType
        with pytest.raises(RuntimeError, match="Fraction runtime protocol"):
            confidence_module_sha256()
    finally:
        operator.__class__ = original_module_type

    with monkeypatch.context() as patch:
        patch.setattr(
            confidence_runtime,
            "_TYPE_GETATTRIBUTE",
            replacement,
        )
        with pytest.raises(
            (RuntimeError, TypeError),
            match="type.__getattribute__",
        ):
            confidence_module_sha256()

    assert confidence_module_sha256() == clean_confidence_hash
    assert coverage_module_sha256() == clean_coverage_hash


def test_fraction_numeric_abc_dispatch_mutation_fails_in_isolated_process(
    tmp_path: Path,
) -> None:
    script = """
import abc
import numbers
from d2t_rna.exact.confidence import confidence_module_sha256

clean_confidence_hash = confidence_module_sha256()

class EmptyIntegralRegistry(metaclass=abc.ABCMeta):
    pass

class EmptyRationalRegistry(metaclass=abc.ABCMeta):
    pass

original_integral_registry = numbers.Integral._abc_impl
original_rational_registry = numbers.Rational._abc_impl
try:
    numbers.Integral._abc_impl = EmptyIntegralRegistry._abc_impl
    numbers.Rational._abc_impl = EmptyRationalRegistry._abc_impl
    try:
        confidence_module_sha256()
    except RuntimeError:
        pass
    else:
        raise SystemExit("Fraction numeric ABC mutation was accepted")
finally:
    numbers.Integral._abc_impl = original_integral_registry
    numbers.Rational._abc_impl = original_rational_registry

assert numbers.Integral._abc_impl is original_integral_registry
assert numbers.Rational._abc_impl is original_rational_registry
assert confidence_module_sha256() == clean_confidence_hash
"""
    completed = run_task4_isolated_child(
        child_artifact_dir=tmp_path / "fraction-abc-child",
        source=script,
    )
    assert completed.returncode == 0, completed.stderr


def test_non_fraction_probability_stream_is_rejected_at_coverage_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    inputs = _evaluation_inputs(family, support=support)
    original = coverage_runtime.iter_joint_outcome_probabilities

    def float_stream(support_spec, registered_law):
        for outcome, probability in original(
            support_spec,
            registered_law,
        ):
            yield outcome, float(probability)

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        float_stream,
    )
    with pytest.raises(CoverageSemanticError, match="exactly Fraction"):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
        )


def test_duplicate_short_long_and_reversed_law_streams_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    inputs = _evaluation_inputs(family, support=support)
    original = coverage_runtime.iter_joint_outcome_probabilities

    def duplicate_stream(support_spec, registered_law):
        rows = tuple(original(support_spec, registered_law))
        yield rows[0]
        yield rows[0]
        yield from rows[1:]

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        duplicate_stream,
    )
    with pytest.raises(CoverageSemanticError, match="strictly increasing"):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
        )

    def short_one_stream(support_spec, registered_law):
        rows = tuple(original(support_spec, registered_law))
        if registered_law.law_id == "law.indifference":
            yield from rows[:-1]
        else:
            yield from rows

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        short_one_stream,
    )
    with pytest.raises(
        CoverageSemanticError,
        match="different lengths",
    ):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
        )

    def long_one_stream(support_spec, registered_law):
        rows = tuple(original(support_spec, registered_law))
        yield from rows
        if registered_law.law_id == "law.indifference":
            yield rows[-1]

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        long_one_stream,
    )
    with pytest.raises(
        CoverageSemanticError,
        match="different lengths",
    ):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
        )

    def reversed_stream(support_spec, registered_law):
        yield from reversed(
            tuple(original(support_spec, registered_law))
        )

    monkeypatch.setattr(
        coverage_runtime,
        "iter_joint_outcome_probabilities",
        reversed_stream,
    )
    with pytest.raises(CoverageSemanticError, match="strictly increasing"):
        evaluate_exact_synthetic_risk_coverage(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
        )


@pytest.mark.parametrize(
    ("family_field", "nested_field"),
    (
        ("probability_space", "parameter_space_hash"),
        ("synthetic_prerequisites", "sampling_law_hash"),
        ("sampling_law_manifest", "support_spec_hash"),
    ),
)
def test_typed_registration_objects_replay_before_evaluation(
    family_field: str,
    nested_field: str,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    nested = getattr(family, family_field).model_copy(
        update={nested_field: "f" * 64}
    )
    forged_family = family.model_copy(update={family_field: nested})
    with pytest.raises(ValidationError):
        strict_revalidate_contract_model(forged_family)


@pytest.mark.parametrize(
    "binding_field",
    (
        "support_spec_hash",
        "support_plan_hash",
        "parameter_universe_hash",
        "probability_space_hash",
        "synthetic_prerequisites_hash",
        "sampling_law_manifest_hash",
        "hypothesis_partition_hash",
        "confidence_procedure_hash",
        "decision_rule_hash",
        "evaluation_input_bundle_hash",
        "evaluation_transcript_hash",
    ),
)
def test_tampered_report_binding_cannot_replay(
    binding_field: str,
) -> None:
    support = binary_support()
    family = three_region_family(support)
    inputs = _evaluation_inputs(family, support=support)
    report = evaluate_exact_synthetic_risk_coverage(
        support=inputs[0],
        family=inputs[1],
        confidence_procedure=inputs[2],
        decision_rule=inputs[3],
        confidence_rule=inputs[4],
        engine_code_hash=coverage_module_sha256(),
    )
    forged = report.model_copy(update={binding_field: "f" * 64})
    with pytest.raises((CoverageSemanticError, ValidationError)):
        replay_exact_synthetic_coverage_report(
            support=inputs[0],
            family=inputs[1],
            confidence_procedure=inputs[2],
            decision_rule=inputs[3],
            confidence_rule=inputs[4],
            engine_code_hash=coverage_module_sha256(),
            report=forged,
        )
