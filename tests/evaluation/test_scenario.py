from __future__ import annotations

import hashlib
import json

import pytest

import d2t_rna.evaluation.scenario as scenario_runtime
from d2t_rna.contracts.base import (
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
)
from d2t_rna.contracts.enums import (
    CoverageBoundMethod,
    ProbabilityScope,
    RorcReason,
    UnconditionalDerivation,
)
from d2t_rna.contracts.primitives import (
    NamedBound,
    Rational,
    RegistryRef,
)
from d2t_rna.contracts.scenario import ScenarioProof
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.exact import (
    EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
    ConfidenceProcedureSpec,
    ExactDecisionRuleSpec,
    ExactParameterFamily,
    ExactSupportSpec,
    ExactSyntheticCoverageReplayCredential,
    ExactSyntheticCoverageReport,
)
from d2t_rna.evaluation.scenario import (
    BoundEventFlag,
    CertifiedTruncationScenarioProofArtifact,
    ExactEnumerationScenarioProofArtifact,
    ExactSyntheticScenarioProofArtifact,
    ExactScenarioOutcome,
    FiniteScenarioCoverageAggregate,
    MonteCarloScenarioProofArtifact,
    RorcCaseRecord,
    RorcDecision,
    RorcObservedDecision,
    ScenarioCoverageDisposition,
    ScenarioProofManifest,
    VerifiedIntervalScenarioProofArtifact,
    aggregate_finite_scenarios,
    audit_registered_rorc_paths,
    assess_rorc,
    build_exact_enumeration_artifact,
    build_exact_synthetic_scenario_artifact,
    build_rorc_case_manifest,
    build_scenario_proof_manifest,
    compute_rorc_stress_metrics,
    evaluate_registered_exact_synthetic_coverage_report,
    replay_finite_scenario_aggregate,
    replay_rorc_stress_metrics,
    replay_scenario_proof_manifest,
)
from tests.exact.conftest import binary_support, three_region_family


def _r(numerator: int, denominator: int = 1) -> Rational:
    return Rational(numerator=numerator, denominator=denominator)


def _hypothesis() -> RegistryRef:
    return RegistryRef(
        registry_id="hypothesis-region",
        registry_hash="2" * 64,
    )


def _core() -> RegistryRef:
    return RegistryRef(
        registry_id="coverage-core",
        registry_hash="3" * 64,
    )


def _flags(
    bound_id: str,
    occurred: bool,
) -> tuple[BoundEventFlag, ...]:
    return (BoundEventFlag(bound_id=bound_id, occurred=occurred),)


def _exact_artifact(
    scenario_id: str,
    *,
    risk_numerator: int = 1,
    risk_denominator: int = 10,
    hypothesis_region: RegistryRef | None = None,
    coverage_core: RegistryRef | None = None,
    conditioning_hash: str = "4" * 64,
) -> ExactEnumerationScenarioProofArtifact:
    risk = _r(risk_numerator, risk_denominator)
    safe = _r(risk_denominator - risk_numerator, risk_denominator)
    outcomes = (
        ExactScenarioOutcome(
            outcome_id="outcome-risk",
            outcome_payload_sha256="a" * 64,
            probability=risk,
            risk_events=_flags("wrong-decision", True),
            coverage_events=_flags("joint-coverage", False),
        ),
        ExactScenarioOutcome(
            outcome_id="outcome-safe",
            outcome_payload_sha256="b" * 64,
            probability=safe,
            risk_events=_flags("wrong-decision", False),
            coverage_events=_flags("joint-coverage", True),
        ),
    )
    return build_exact_enumeration_artifact(
        scenario_id=scenario_id,
        hypothesis_region=hypothesis_region or _hypothesis(),
        coverage_core_membership=coverage_core or _core(),
        conditioning_sigma_field_hash=conditioning_hash,
        outcomes=outcomes,
    )


def _noncomplementary_exact_artifact(
    scenario_id: str,
    *,
    risk_tenths: int,
    coverage_tenths: int,
) -> ExactEnumerationScenarioProofArtifact:
    gap_tenths = 10 - risk_tenths - coverage_tenths
    outcomes = (
        ExactScenarioOutcome(
            outcome_id="a-risk",
            outcome_payload_sha256="a" * 64,
            probability=_r(risk_tenths, 10),
            risk_events=_flags("wrong-decision", True),
            coverage_events=_flags("joint-coverage", False),
        ),
        ExactScenarioOutcome(
            outcome_id="b-neither",
            outcome_payload_sha256="b" * 64,
            probability=_r(gap_tenths, 10),
            risk_events=_flags("wrong-decision", False),
            coverage_events=_flags("joint-coverage", False),
        ),
        ExactScenarioOutcome(
            outcome_id="c-covered",
            outcome_payload_sha256="c" * 64,
            probability=_r(coverage_tenths, 10),
            risk_events=_flags("wrong-decision", False),
            coverage_events=_flags("joint-coverage", True),
        ),
    )
    return build_exact_enumeration_artifact(
        scenario_id=scenario_id,
        hypothesis_region=_hypothesis(),
        coverage_core_membership=_core(),
        conditioning_sigma_field_hash="4" * 64,
        outcomes=outcomes,
    )


def _task4_exact_artifact(
    scenario_id: str,
) -> ExactSyntheticScenarioProofArtifact:
    support = binary_support()
    family = three_region_family(support)
    decision_rule = ExactDecisionRuleSpec(
        rule_id="decision.confidence-subset.v1",
        implementation_hash=(
            EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256
        ),
        parameter_universe_hash=family.parameter_universe_hash,
    )
    procedure, report = (
        evaluate_registered_exact_synthetic_coverage_report(
            support=support,
            family=family,
            decision_rule=decision_rule,
        )
    )
    return build_exact_synthetic_scenario_artifact(
        scenario_id=scenario_id,
        support=support,
        family=family,
        confidence_procedure=procedure,
        decision_rule=decision_rule,
        confidence_rule_registry_id=(
            "confidence.task5.all-registered-parameters.v1"
        ),
        report=report,
    )


def _risk_certificate(
    *,
    conditioning_sigma_field_hash: str,
) -> RiskCertificate:
    return RiskCertificate(
        h0_wrong_reject_bound=_r(1, 20),
        h1_wrong_certify_bound=_r(1, 20),
        indifference_decisive_output_bound=_r(1, 20),
        confidence_set_uniform_coverage=_r(19, 20),
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        conditioning_sigma_field_hash=conditioning_sigma_field_hash,
        success_event_hash="5" * 64,
        failure_event_policy=RegistryRef(
            registry_id="failure-policy.synthetic.v1",
            registry_hash="6" * 64,
        ),
        conditional_bound=_r(1, 20),
        unconditional_bound=None,
        unconditional_derivation=UnconditionalDerivation.NOT_AVAILABLE,
        conditional_on_effective_molecule_count=False,
        prospective_unconditional_bound=None,
    )


def _proof(
    artifact: object,
    *,
    formal: bool,
) -> ScenarioProof:
    assert hasattr(artifact, "scenario_id")
    return ScenarioProof(
        scenario_id=artifact.scenario_id,
        law_hash=artifact.law_hash,
        hypothesis_region=artifact.hypothesis_region,
        coverage_core_membership=artifact.coverage_core_membership,
        conditioning_sigma_field_hash=(
            artifact.conditioning_sigma_field_hash
        ),
        risk_upper_bounds=artifact.risk_upper_bounds,
        coverage_lower_bounds=artifact.coverage_lower_bounds,
        coverage_bound_method=artifact.coverage_bound_method,
        probability_mass_accounted=artifact.probability_mass_accounted,
        omitted_mass_bound=artifact.omitted_mass_bound,
        numerical_error_bound=artifact.numerical_error_bound,
        proof_artifact_hash=canonical_sha256(artifact),
        formal_guarantee=formal,
    )


def _nonformal_artifact(
    artifact_type: type[
        VerifiedIntervalScenarioProofArtifact
        | CertifiedTruncationScenarioProofArtifact
        | MonteCarloScenarioProofArtifact
    ],
    scenario_id: str,
) -> (
    VerifiedIntervalScenarioProofArtifact
    | CertifiedTruncationScenarioProofArtifact
    | MonteCarloScenarioProofArtifact
):
    exact = _exact_artifact(scenario_id)
    risk_bounds = exact.risk_upper_bounds
    extra: dict[str, object] = {}
    if artifact_type is MonteCarloScenarioProofArtifact:
        certificate = _risk_certificate(
            conditioning_sigma_field_hash=(
                exact.conditioning_sigma_field_hash
            )
        )
        risk_bounds = (
            NamedBound(
                bound_id="h0-wrong-reject",
                value=certificate.h0_wrong_reject_bound,
            ),
            NamedBound(
                bound_id="h1-wrong-certify",
                value=certificate.h1_wrong_certify_bound,
            ),
            NamedBound(
                bound_id="indifference-decisive-output",
                value=certificate.indifference_decisive_output_bound,
            ),
        )
        extra = {"risk_certificate": certificate}
    return artifact_type(
        scenario_id=scenario_id,
        law_hash=exact.law_hash,
        hypothesis_region=exact.hypothesis_region,
        coverage_core_membership=exact.coverage_core_membership,
        conditioning_sigma_field_hash=(
            exact.conditioning_sigma_field_hash
        ),
        risk_upper_bounds=risk_bounds,
        coverage_lower_bounds=exact.coverage_lower_bounds,
        probability_mass_accounted=exact.probability_mass_accounted,
        omitted_mass_bound=exact.omitted_mass_bound,
        numerical_error_bound=exact.numerical_error_bound,
        method_evidence_sha256="e" * 64,
        **extra,
    )


def test_generic_exact_atoms_recompute_but_cannot_self_sign_formal() -> None:
    artifact = _exact_artifact("scenario-a")
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=True),
        artifact,
    )

    assert manifest.coverage_disposition is (
        ScenarioCoverageDisposition.REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
    )
    assert manifest.formal_guarantee is False
    assert manifest.scenario_proof.formal_guarantee is False
    assert manifest.proof_artifact == artifact
    assert manifest.proof_artifact_hash_verified is True
    assert manifest.serialized_bearer_authorization is False
    assert replay_scenario_proof_manifest(manifest) == manifest

    forged_proof = manifest.scenario_proof.model_copy(
        update={
            "risk_upper_bounds": (
                NamedBound(bound_id="wrong-decision", value=_r(1, 5)),
            )
        }
    )
    with pytest.raises(ValueError, match="risk bounds"):
        build_scenario_proof_manifest(forged_proof, artifact)

    with pytest.raises(TypeError, match="ScenarioProofArtifact"):
        build_scenario_proof_manifest(  # type: ignore[arg-type]
            _proof(artifact, formal=True),
            {"opaque": "caller-controlled"},
        )


def test_task4_raw_input_fresh_replay_is_only_formal_exact_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _task4_exact_artifact("scenario-task4")
    assert artifact.schema_version == "2.0"
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=False),
        artifact,
    )

    assert manifest.coverage_disposition is (
        ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
    )
    assert manifest.formal_guarantee is True
    assert manifest.scenario_proof.formal_guarantee is True
    replay_credential = parse_contract_json(
        ExactSyntheticCoverageReplayCredential,
        artifact.exact_replay_credential_json,
    )
    assert replay_credential.live_replay_completed is True
    assert artifact.serialized_bearer_authorization is False
    assert replay_scenario_proof_manifest(manifest) == manifest

    with pytest.raises(ValueError, match="registry ID"):
        build_exact_synthetic_scenario_artifact(
            scenario_id=artifact.scenario_id,
            support=parse_contract_json(
                ExactSupportSpec,
                artifact.support_json,
            ),
            family=parse_contract_json(
                ExactParameterFamily,
                artifact.family_json,
            ),
            confidence_procedure=parse_contract_json(
                ConfidenceProcedureSpec,
                artifact.confidence_procedure_json,
            ),
            decision_rule=parse_contract_json(
                ExactDecisionRuleSpec,
                artifact.decision_rule_json,
            ),
            confidence_rule_registry_id="confidence.caller-controlled",
            report=parse_contract_json(
                ExactSyntheticCoverageReport,
                artifact.exact_synthetic_coverage_report_json,
            ),
        )

    forged = artifact.model_copy(
        update={
            "exact_synthetic_coverage_report_sha256": "f" * 64,
        }
    )
    with pytest.raises(ValueError, match="does not match bytes"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            forged,
        )

    forged_report_payload = json.loads(
        artifact.exact_synthetic_coverage_report_json
    )
    forged_report_payload["evaluation_transcript_hash"] = "0" * 64
    forged_report_json = canonical_json_bytes(
        forged_report_payload
    ).decode("utf-8")
    rehashed_forgery = artifact.model_copy(
        update={
            "exact_synthetic_coverage_report_json": forged_report_json,
            "exact_synthetic_coverage_report_sha256": hashlib.sha256(
                forged_report_json.encode("utf-8")
            ).hexdigest(),
        }
    )
    forged_outer_proof = _proof(rehashed_forgery, formal=True)
    with pytest.raises(ValueError, match="does not replay"):
        build_scenario_proof_manifest(
            forged_outer_proof,
            rehashed_forgery,
        )

    noncanonical_support = artifact.support_json + " "
    noncanonical_payload = artifact.model_dump(mode="python")
    noncanonical_payload.update(
        {
            "support_json": noncanonical_support,
            "support_sha256": hashlib.sha256(
                noncanonical_support.encode("utf-8")
            ).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="canonical JSON"):
        ExactSyntheticScenarioProofArtifact.model_validate(
            noncanonical_payload,
            strict=True,
        )

    duplicate_key_support = '{"schema_id":"a","schema_id":"b"}'
    duplicate_payload = artifact.model_dump(mode="python")
    duplicate_payload.update(
        {
            "support_json": duplicate_key_support,
            "support_sha256": hashlib.sha256(
                duplicate_key_support.encode("utf-8")
            ).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        ExactSyntheticScenarioProofArtifact.model_validate(
            duplicate_payload,
            strict=True,
        )

    def forbidden_replay(**kwargs: object) -> object:
        raise AssertionError("raw JSON cap must fail before Task 4 replay")

    monkeypatch.setattr(
        scenario_runtime,
        "replay_exact_synthetic_coverage_report",
        forbidden_replay,
    )
    huge_report = json.loads(
        artifact.exact_synthetic_coverage_report_json
    )
    huge_report["outcome_count"] = 1 << 512
    huge_report_json = canonical_json_bytes(huge_report).decode("utf-8")
    huge_payload = artifact.model_dump(mode="python")
    huge_payload.update(
        {
            "exact_synthetic_coverage_report_json": huge_report_json,
            "exact_synthetic_coverage_report_sha256": hashlib.sha256(
                huge_report_json.encode("utf-8")
            ).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="256-bit cap"):
        ExactSyntheticScenarioProofArtifact.model_validate(
            huge_payload,
            strict=True,
        )

    nested: object = 0
    for _ in range(66):
        nested = [nested]
    deep_support_json = json.dumps(
        nested,
        separators=(",", ":"),
    )
    deep_payload = artifact.model_dump(mode="python")
    deep_payload.update(
        {
            "support_json": deep_support_json,
            "support_sha256": hashlib.sha256(
                deep_support_json.encode("utf-8")
            ).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="depth cap"):
        ExactSyntheticScenarioProofArtifact.model_validate(
            deep_payload,
            strict=True,
        )


@pytest.mark.parametrize(
    "artifact_type",
    (
        VerifiedIntervalScenarioProofArtifact,
        CertifiedTruncationScenarioProofArtifact,
    ),
)
def test_unimplemented_formal_methods_fail_closed(
    artifact_type: type[
        VerifiedIntervalScenarioProofArtifact
        | CertifiedTruncationScenarioProofArtifact
    ],
) -> None:
    artifact = _nonformal_artifact(artifact_type, "scenario-nonformal")
    with pytest.raises(ValueError, match="formal replay unavailable"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            artifact,
        )

    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=False),
        artifact,
    )
    assert manifest.coverage_disposition is (
        ScenarioCoverageDisposition.REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
    )
    assert manifest.formal_guarantee is False


def test_monte_carlo_is_predicted_nonformal_and_not_upgradeable() -> None:
    artifact = _nonformal_artifact(
        MonteCarloScenarioProofArtifact,
        "scenario-mc",
    )
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=True),
        artifact,
    )
    assert manifest.coverage_disposition is (
        ScenarioCoverageDisposition.RISK_CERTIFIED_COVERAGE_PREDICTED
    )
    assert manifest.formal_guarantee is False
    assert manifest.scenario_proof.formal_guarantee is False
    assert (
        artifact.risk_certificate_sha256
        == canonical_sha256(artifact.risk_certificate)
    )

    payload = manifest.model_dump(mode="python")
    payload["coverage_disposition"] = (
        ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
    )
    payload["formal_guarantee"] = True
    with pytest.raises(ValueError, match="manifest replay"):
        ScenarioProofManifest(**payload)

    forged = manifest.model_copy(
        update={
            "coverage_disposition": (
                ScenarioCoverageDisposition
                .FORMAL_REGISTERED_SCENARIO_COVERAGE
            ),
            "formal_guarantee": True,
        }
    )
    with pytest.raises(ValueError, match="manifest replay"):
        replay_scenario_proof_manifest(forged)

    forged_certificate = artifact.risk_certificate.model_copy(
        update={"confidence_set_uniform_coverage": _r(9, 10)}
    )
    forged_artifact = artifact.model_copy(
        update={
            "risk_certificate": forged_certificate,
            "risk_certificate_sha256": canonical_sha256(forged_certificate),
        }
    )
    with pytest.raises(ValueError, match="uniform confidence-set coverage"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=False),
            forged_artifact,
        )

    payload = artifact.model_dump(mode="python")
    del payload["risk_certificate"]
    del payload["risk_certificate_sha256"]
    with pytest.raises(ValueError, match="risk_certificate"):
        MonteCarloScenarioProofArtifact.model_validate(payload, strict=True)


def test_finite_aggregate_replays_max_risk_min_coverage_only() -> None:
    artifact_a = _exact_artifact("scenario-a")
    artifact_b = _exact_artifact(
        "scenario-b",
        risk_numerator=1,
        risk_denominator=5,
    )
    manifests = tuple(
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            artifact,
        )
        for artifact in (artifact_a, artifact_b)
    )
    aggregate = aggregate_finite_scenarios(
        manifests,
        scenario_probabilities={
            "scenario-a": _r(1, 2),
            "scenario-b": _r(1, 2),
        },
    )

    assert aggregate.risk_upper_bounds[0].value == _r(1, 5)
    assert aggregate.coverage_lower_bounds[0].value == _r(4, 5)
    assert aggregate.scenario_coverage_union_bound == _r(3, 10)
    assert aggregate.scenario_probability_mass_accounted == _r(1)
    assert aggregate.formal_guarantee is False
    assert aggregate.coverage_disposition is (
        ScenarioCoverageDisposition.REGISTERED_SCENARIO_COVERAGE_NOT_FORMAL
    )
    assert aggregate.claim_scope == "FINITE_REGISTERED_SCENARIOS_ONLY"
    assert aggregate.continuous_uncertainty_set_claim is False
    assert aggregate.interpolation_authorized is False
    assert aggregate.serialized_bearer_authorization is False
    assert "UNION_BOUND" in aggregate.union_bound_derivation_id
    assert replay_finite_scenario_aggregate(aggregate) == aggregate


def test_finite_aggregate_is_formal_only_for_task4_raw_replay_path() -> None:
    artifact = _task4_exact_artifact("scenario-task4")
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=False),
        artifact,
    )
    aggregate = aggregate_finite_scenarios(
        (manifest,),
        scenario_probabilities={"scenario-task4": _r(1)},
    )

    assert aggregate.formal_guarantee is True
    assert aggregate.coverage_disposition is (
        ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
    )
    assert aggregate.scenario_coverage_union_bound == _r(0)
    assert replay_finite_scenario_aggregate(aggregate) == aggregate


def test_union_bound_uses_coverage_failure_not_decision_risk() -> None:
    artifacts = (
        _noncomplementary_exact_artifact(
            "scenario-a",
            risk_tenths=1,
            coverage_tenths=6,
        ),
        _noncomplementary_exact_artifact(
            "scenario-b",
            risk_tenths=2,
            coverage_tenths=7,
        ),
    )
    manifests = tuple(
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            artifact,
        )
        for artifact in artifacts
    )
    aggregate = aggregate_finite_scenarios(
        manifests,
        scenario_probabilities={
            "scenario-a": _r(1, 2),
            "scenario-b": _r(1, 2),
        },
    )

    assert aggregate.risk_upper_bounds[0].value == _r(1, 5)
    assert aggregate.coverage_lower_bounds[0].value == _r(3, 5)
    assert aggregate.scenario_coverage_union_bound == _r(7, 10)
    assert aggregate.scenario_coverage_union_bound != _r(3, 10)
    assert replay_finite_scenario_aggregate(aggregate) == aggregate


def test_union_bound_sums_mutually_exclusive_failures_within_scenario() -> None:
    outcomes = (
        ExactScenarioOutcome(
            outcome_id="a-fails-first",
            outcome_payload_sha256="a" * 64,
            probability=_r(2, 5),
            risk_events=_flags("wrong-decision", False),
            coverage_events=(
                BoundEventFlag(bound_id="coverage-first", occurred=False),
                BoundEventFlag(bound_id="coverage-second", occurred=True),
            ),
        ),
        ExactScenarioOutcome(
            outcome_id="b-fails-second",
            outcome_payload_sha256="b" * 64,
            probability=_r(2, 5),
            risk_events=_flags("wrong-decision", False),
            coverage_events=(
                BoundEventFlag(bound_id="coverage-first", occurred=True),
                BoundEventFlag(bound_id="coverage-second", occurred=False),
            ),
        ),
        ExactScenarioOutcome(
            outcome_id="c-covered",
            outcome_payload_sha256="c" * 64,
            probability=_r(1, 5),
            risk_events=_flags("wrong-decision", False),
            coverage_events=(
                BoundEventFlag(bound_id="coverage-first", occurred=True),
                BoundEventFlag(bound_id="coverage-second", occurred=True),
            ),
        ),
    )
    artifact = build_exact_enumeration_artifact(
        scenario_id="scenario-mutually-exclusive-failures",
        hypothesis_region=_hypothesis(),
        coverage_core_membership=_core(),
        conditioning_sigma_field_hash="4" * 64,
        outcomes=outcomes,
    )
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=True),
        artifact,
    )
    aggregate = aggregate_finite_scenarios(
        (manifest,),
        scenario_probabilities={
            "scenario-mutually-exclusive-failures": _r(1),
        },
    )

    assert aggregate.coverage_lower_bounds == (
        NamedBound(bound_id="coverage-first", value=_r(3, 5)),
        NamedBound(bound_id="coverage-second", value=_r(3, 5)),
    )
    assert aggregate.scenario_coverage_union_bound == _r(4, 5)


def test_aggregate_rejects_incomparable_semantics_and_bad_weights() -> None:
    artifact_a = _exact_artifact("scenario-a")
    artifact_b = _exact_artifact(
        "scenario-b",
        conditioning_hash="9" * 64,
    )
    manifests = tuple(
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            artifact,
        )
        for artifact in (artifact_a, artifact_b)
    )
    with pytest.raises(ValueError, match="conditioning"):
        aggregate_finite_scenarios(
            manifests,
            scenario_probabilities={
                "scenario-a": _r(1, 2),
                "scenario-b": _r(1, 2),
            },
        )

    comparable_b = _exact_artifact("scenario-b")
    comparable = (
        manifests[0],
        build_scenario_proof_manifest(
            _proof(comparable_b, formal=True),
            comparable_b,
        ),
    )
    with pytest.raises(ValueError, match="sum to one"):
        aggregate_finite_scenarios(
            comparable,
            scenario_probabilities={
                "scenario-a": _r(1, 2),
                "scenario-b": _r(2, 5),
            },
        )
    with pytest.raises(ValueError, match="canonical order"):
        aggregate_finite_scenarios(
            tuple(reversed(comparable)),
            scenario_probabilities={
                "scenario-a": _r(1, 2),
                "scenario-b": _r(1, 2),
            },
        )


def test_direct_constructor_cannot_upgrade_mc_aggregate() -> None:
    artifact = _nonformal_artifact(
        MonteCarloScenarioProofArtifact,
        "scenario-mc",
    )
    manifest = build_scenario_proof_manifest(
        _proof(artifact, formal=False),
        artifact,
    )
    aggregate = aggregate_finite_scenarios(
        (manifest,),
        scenario_probabilities={"scenario-mc": _r(1)},
    )
    payload = aggregate.model_dump(mode="python")
    payload["coverage_disposition"] = (
        ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
    )
    payload["formal_guarantee"] = True
    with pytest.raises(ValueError, match="aggregate replay"):
        FiniteScenarioCoverageAggregate(**payload)

    forged = aggregate.model_copy(
        update={
            "coverage_disposition": (
                ScenarioCoverageDisposition
                .FORMAL_REGISTERED_SCENARIO_COVERAGE
            ),
            "formal_guarantee": True,
        }
    )
    with pytest.raises(ValueError, match="aggregate replay"):
        replay_finite_scenario_aggregate(forged)


def test_bounds_are_unique_canonical_and_probabilities() -> None:
    artifact = _exact_artifact("scenario-a")
    invalid_outcomes = artifact.outcomes[0].model_copy(
        update={
            "risk_events": (
                BoundEventFlag(bound_id="z", occurred=True),
                BoundEventFlag(bound_id="a", occurred=False),
            )
        }
    )
    forged = artifact.model_copy(
        update={"outcomes": (invalid_outcomes, artifact.outcomes[1])}
    )
    with pytest.raises(ValueError, match="canonical"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=True),
            forged,
        )


def test_bound_registry_binds_semantics_not_only_ids() -> None:
    artifact = _exact_artifact("scenario-semantics")
    first = artifact.bound_semantics[0]
    forged_semantics = (
        first.model_copy(
            update={
                "event_semantics": (
                    "Caller changed the event while preserving its bound ID."
                )
            }
        ),
        *artifact.bound_semantics[1:],
    )
    forged = artifact.model_copy(
        update={"bound_semantics": forged_semantics}
    )

    with pytest.raises(ValueError, match="does not replay"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=False),
            forged,
        )


def test_scenario_runtime_replacement_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _exact_artifact("scenario-runtime")

    def forged_probability(value: Rational, *, label: str):
        return scenario_runtime.Fraction(0)

    monkeypatch.setattr(
        scenario_runtime,
        "_probability",
        forged_probability,
    )
    with pytest.raises(RuntimeError, match="runtime dependency identity"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=False),
            artifact,
        )


def test_scenario_runtime_model_method_mutation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _exact_artifact("scenario-model-runtime")

    def forged_manifest_validator(self: object) -> object:
        return self

    monkeypatch.setattr(
        ScenarioProofManifest,
        "replay_manifest",
        forged_manifest_validator,
    )
    with pytest.raises(RuntimeError, match="runtime model method changed"):
        build_scenario_proof_manifest(
            _proof(artifact, formal=False),
            artifact,
        )


def test_rational_component_cap_fails_before_fraction_work() -> None:
    with pytest.raises(ValueError, match="256-bit rational component cap"):
        ExactScenarioOutcome(
            outcome_id="huge",
            outcome_payload_sha256="a" * 64,
            probability=Rational(
                numerator=1 << 512,
                denominator=(1 << 512) + 1,
            ),
            risk_events=_flags("wrong-decision", False),
            coverage_events=_flags("joint-coverage", True),
        )


def _case(
    case_id: str,
    decision: RorcObservedDecision,
    *,
    correct: bool,
    covered: bool,
    covered_without_third: bool,
    reasons: tuple[RorcReason, ...] = (),
) -> RorcCaseRecord:
    return RorcCaseRecord(
        case_id=case_id,
        case_input_sha256=case_id[0] * 64,
        decision_artifact_sha256=case_id[-1] * 64,
        observed_decision=decision,
        reasons=reasons,
        decision_correct=correct,
        covered_with_registered_state_dictionary=covered,
        covered_after_omitting_third_state=covered_without_third,
    )


def test_rorc_case_manifest_replays_metrics_and_records_increase() -> None:
    cases = (
        _case(
            "a-case",
            RorcObservedDecision.ABSTAIN,
            correct=True,
            covered=False,
            covered_without_third=True,
        ),
        _case(
            "b-case",
            RorcObservedDecision.CERTIFY,
            correct=False,
            covered=True,
            covered_without_third=True,
            reasons=(RorcReason.RIVAL_SUPPORT_INCOMPLETE,),
        ),
        _case(
            "c-case",
            RorcObservedDecision.REJECT,
            correct=True,
            covered=False,
            covered_without_third=True,
        ),
    )
    manifest = build_rorc_case_manifest(cases)
    metrics = compute_rorc_stress_metrics(manifest)

    assert manifest.cases[0].reasons == (
        RorcReason.ABSTAIN_INDETERMINATE,
    )
    assert metrics.total_cases == 3
    assert metrics.decisive_output_count == 2
    assert metrics.incorrect_decisive_output_count == 1
    assert metrics.decisive_output_probability == _r(2, 3)
    assert metrics.incorrect_decisive_output_probability == _r(1, 3)
    assert metrics.observed_case_set_all_abstain is False
    assert metrics.observational_case_set_complete is False
    assert metrics.observational_decision_execution_verified is False
    assert "all_registered_paths_abstain" not in type(metrics).model_fields
    assert metrics.coverage_change_after_omitting_third_state == _r(2, 3)
    assert metrics.coverage_decline_after_omitting_third_state == _r(-2, 3)
    assert metrics.coverage_increase_observed is True
    assert metrics.held_out_claim_authorized is False
    assert metrics.serialized_bearer_authorization is False
    assert replay_rorc_stress_metrics(metrics) == metrics

    forged = metrics.model_copy(update={"decisive_output_count": 0})
    with pytest.raises(ValueError, match="metrics replay"):
        replay_rorc_stress_metrics(forged)


def test_registered_rorc_path_audit_executes_complete_reason_powerset() -> None:
    audit = audit_registered_rorc_paths()

    assert audit.expected_path_count == 16
    assert len(audit.path_replays) == 16
    supplied_reason_paths = tuple(
        path.supplied_reasons for path in audit.path_replays
    )
    assert len(set(supplied_reason_paths)) == 16
    assert set(supplied_reason_paths) == {
        tuple(
            reason
            for reason_index, reason in enumerate(tuple(RorcReason))
            if mask & (1 << reason_index)
        )
        for mask in range(16)
    }
    assert audit.registered_path_set_complete is True
    assert audit.paths_executed_via_assess_rorc is True
    assert audit.all_registered_paths_abstain is True
    assert all(
        path.assessment.decision is RorcDecision.ABSTAIN
        for path in audit.path_replays
    )
    assert audit.serialized_bearer_authorization is False

    forged = audit.model_copy(
        update={"registered_path_registry_root_sha256": "0" * 64}
    )
    with pytest.raises(ValueError, match="does not replay"):
        scenario_runtime.RegisteredRorcPathAudit.model_validate(
            forged.model_dump(mode="python"),
            strict=True,
        )


def test_registered_rorc_path_audit_rejects_path_generator_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scenario_runtime,
        "_registered_rorc_reason_paths",
        lambda: ((),) * 16,
    )
    with pytest.raises(RuntimeError, match="runtime dependency identity changed"):
        scenario_runtime.audit_registered_rorc_paths()


def test_rorc_case_ids_are_canonical_and_reasons_stable() -> None:
    record = _case(
        "a-case",
        RorcObservedDecision.ABSTAIN,
        correct=True,
        covered=True,
        covered_without_third=True,
        reasons=(
            RorcReason.RIVAL_SUPPORT_INCOMPLETE,
            RorcReason.REGISTERED_MODEL_CLASS_REJECTED,
            RorcReason.RIVAL_SUPPORT_INCOMPLETE,
        ),
    )
    assert record.reasons == (
        RorcReason.REGISTERED_MODEL_CLASS_REJECTED,
        RorcReason.RIVAL_SUPPORT_INCOMPLETE,
    )
    with pytest.raises(ValueError, match="canonical"):
        build_rorc_case_manifest(
            (
                _case(
                    "b-case",
                    RorcObservedDecision.ABSTAIN,
                    correct=True,
                    covered=True,
                    covered_without_third=True,
                ),
                record,
            )
        )


def test_rorc_assessment_always_abstains_and_never_claims_held_out() -> None:
    assessment = assess_rorc(
        (
            RorcReason.RIVAL_SUPPORT_INCOMPLETE,
            RorcReason.REGISTERED_MODEL_CLASS_REJECTED,
            RorcReason.RIVAL_SUPPORT_INCOMPLETE,
        )
    )
    assert assessment.decision is RorcDecision.ABSTAIN
    assert assessment.reasons == (
        RorcReason.REGISTERED_MODEL_CLASS_REJECTED,
        RorcReason.RIVAL_SUPPORT_INCOMPLETE,
    )
    assert assessment.held_out_claim_authorized is False

    indeterminate = assess_rorc(())
    assert indeterminate.reasons == (RorcReason.ABSTAIN_INDETERMINATE,)
    assert indeterminate.scientific_conclusion_authorized is False
    with pytest.raises(TypeError, match="RorcReason"):
        assess_rorc((RorcReason.RIVAL_SUPPORT_INCOMPLETE.value,))
