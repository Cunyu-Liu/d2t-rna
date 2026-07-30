#!/usr/bin/env python3
"""Build the registered Task 4 exact-synthetic acceptance artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import sys

import pydantic

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.primitives import (
    ObjectCommitment,
    ProofArtifactRef,
    Rational,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.exact import (
    EXACT_DECISION_RULE_V1_IMPLEMENTATION_SHA256,
    ConfidenceProcedureSpec,
    ExactActionSpec,
    ExactDecisionRuleSpec,
    ExactParameterFamily,
    ExactParameterPoint,
    ExactSamplingLawEntry,
    ExactSamplingLawManifest,
    ExactSupportSpec,
    HypothesisThresholds,
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
    confidence_module_sha256,
    confidence_rule_implementation_sha256,
    coverage_module_sha256,
    evaluate_exact_synthetic_risk_coverage,
    exact_parameter_registry_hash,
    replay_exact_synthetic_coverage_report,
    replay_outer_approximation_assessment,
    replay_probability_mass_audit,
    verify_outer_approximation,
    verify_probability_mass,
)
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
    load_trusted_task2_registry,
)
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
)


ARTIFACT_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
REGISTERED_FIXTURE_CALLBACK_MODULE = (
    "d2t_rna.exact.registered_task4_fixture"
)
SHA_CHANNEL = "1" * 64
SHA_OBSERVATION = "2" * 64
SHA_CONDITIONING = "3" * 64
SHA_REGISTRATION_PROOF = "4" * 64


def _rational(numerator: int, denominator: int = 1) -> Rational:
    return Rational(numerator=numerator, denominator=denominator)


def _law(
    support: ExactSupportSpec,
    *,
    law_id: str,
    first_probability: Rational,
) -> IndependentMultinomialLaw:
    first = _rational(
        first_probability.numerator,
        first_probability.denominator,
    )
    second = _rational(
        first.denominator - first.numerator,
        first.denominator,
    )
    return IndependentMultinomialLaw(
        law_id=law_id,
        support_spec_hash=canonical_sha256(support),
        action_probabilities=(
            IndependentActionProbabilities(
                action_id="action.0",
                probabilities=(first, second),
            ),
        ),
    )


def _build_family(
    project_root: Path,
    support: ExactSupportSpec,
) -> ExactParameterFamily:
    thresholds = HypothesisThresholds(
        tau0=_rational(1),
        epsilon=_rational(3),
    )
    points = (
        ExactParameterPoint(
            parameter_id="omega.h0",
            loss=_rational(1),
            law=_law(
                support,
                law_id="law.acceptance.h0",
                first_probability=_rational(1),
            ),
        ),
        ExactParameterPoint(
            parameter_id="omega.h1",
            loss=_rational(3),
            law=_law(
                support,
                law_id="law.acceptance.h1",
                first_probability=_rational(0),
            ),
        ),
        ExactParameterPoint(
            parameter_id="omega.indifference",
            loss=_rational(2),
            law=_law(
                support,
                law_id="law.acceptance.indifference",
                first_probability=_rational(1, 20),
            ),
        ),
    )
    support_hash = canonical_sha256(support)
    law_manifest = ExactSamplingLawManifest(
        support_spec_hash=support_hash,
        entries=tuple(
            ExactSamplingLawEntry(
                parameter_id=point.parameter_id,
                law_hash=canonical_sha256(point.law),
            )
            for point in points
        ),
    )
    law_manifest_hash = canonical_sha256(law_manifest)
    registry_path = (
        project_root / "manifests" / "task2_semantic_registry.json"
    )
    registry = load_trusted_task2_registry(registry_path.read_bytes())
    probability_space = ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(
                object_id="channel.synthetic.known",
                object_hash=SHA_CHANNEL,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="synthetic.observation",
                object_hash=SHA_OBSERVATION,
            ),
        ),
        sampling_law_hash=law_manifest_hash,
        parameter_space_hash=exact_parameter_registry_hash(
            thresholds,
            points,
        ),
        conditioning_sigma_field_hash=SHA_CONDITIONING,
        observation_model_hash=SHA_CHANNEL,
        estimand=registry.ref(
            "estimand.synthetic_known_channel_decision_risk",
            SemanticRegistryRole.SYNTHETIC_ESTIMAND,
        ),
        target=registry.ref(
            "target.synthetic_known_channel_risk_coverage",
            SemanticRegistryRole.SYNTHETIC_TARGET,
        ),
        formal_scientific_risk_guarantee=True,
    )
    prerequisites = SyntheticKnownChannelPrerequisites(
        known_channel_object_id="channel.synthetic.known",
        known_channel_object_hash=SHA_CHANNEL,
        sampling_law_hash=law_manifest_hash,
        support_definition_hash=support_hash,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.task4.acceptance.synthetic-channel",
            artifact_hash=SHA_REGISTRATION_PROOF,
        ),
    )
    return ExactParameterFamily(
        support_spec_hash=support_hash,
        semantic_registry=registry,
        probability_space=probability_space,
        synthetic_prerequisites=prerequisites,
        sampling_law_manifest=law_manifest,
        thresholds=thresholds,
        points=points,
    )


def _confidence_rule():
    def rule(
        outcome: tuple[tuple[int, ...], ...],
    ) -> tuple[tuple[str, ...], None]:
        if outcome == ((1, 0),):
            members = ("omega.h0",)
        else:
            members = ("omega.h1", "omega.indifference")
        return members, None

    rule.__module__ = REGISTERED_FIXTURE_CALLBACK_MODULE
    return rule


def _write_canonical(path: Path, value: object) -> str:
    payload = canonical_json_bytes(value) + b"\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def build_fixture(
    *,
    project_root: Path,
    output_dir: Path,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    resolved_output = output_dir.resolve()
    resolved_artifact_root = artifact_root.resolve()
    try:
        resolved_output.relative_to(resolved_artifact_root)
    except ValueError as exc:
        raise ValueError(
            "Task 4 artifacts must remain under "
            f"{resolved_artifact_root}"
        ) from exc
    resolved_output.mkdir(parents=True, exist_ok=False)

    support = ExactSupportSpec(
        state_ids=("state.0", "state.1"),
        actions=(
            ExactActionSpec(
                action_id="action.0",
                sample_size=1,
                alphabet=("symbol.0", "symbol.1"),
            ),
        ),
    )
    family = _build_family(project_root, support)
    universe_hash = family.parameter_universe_hash
    exact_rule = _confidence_rule()
    outer_rule = _confidence_rule()
    exact_procedure = ConfidenceProcedureSpec(
        procedure_id="confidence.task4.acceptance.exact",
        implementation_hash=confidence_rule_implementation_sha256(
            exact_rule
        ),
        parameter_universe_hash=universe_hash,
    )
    outer_procedure = ConfidenceProcedureSpec(
        procedure_id="confidence.task4.acceptance.outer",
        implementation_hash=confidence_rule_implementation_sha256(
            outer_rule
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
    fixture_definition_hash = canonical_sha256(
        {
            "fixture_id": "task4.registered.synthetic-microcase.v1",
            "support": support,
            "family": family,
            "exact_procedure": exact_procedure,
            "outer_procedure": outer_procedure,
            "decision_rule": decision_rule,
        }
    )

    engine_hash = coverage_module_sha256()
    report = evaluate_exact_synthetic_risk_coverage(
        support=support,
        family=family,
        confidence_procedure=exact_procedure,
        decision_rule=decision_rule,
        confidence_rule=exact_rule,
        engine_code_hash=engine_hash,
    )
    report_replay = replay_exact_synthetic_coverage_report(
        support=support,
        family=family,
        confidence_procedure=exact_procedure,
        decision_rule=decision_rule,
        confidence_rule=exact_rule,
        engine_code_hash=engine_hash,
        report=report,
    )
    outer_assessment = verify_outer_approximation(
        support=support,
        family=family,
        exact_procedure=exact_procedure,
        outer_procedure=outer_procedure,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
    )
    outer_replay = replay_outer_approximation_assessment(
        support=support,
        family=family,
        exact_procedure=exact_procedure,
        outer_procedure=outer_procedure,
        decision_rule=decision_rule,
        exact_rule=exact_rule,
        outer_rule=outer_rule,
        assessment=outer_assessment,
    )
    mass_audits = tuple(
        verify_probability_mass(support, point.law)
        for point in family.points
    )
    for point, audit in zip(family.points, mass_audits, strict=True):
        replay_probability_mass_audit(support, point.law, audit)

    artifacts: dict[str, str] = {}
    values = {
        "exact_synthetic_report.json": report,
        "exact_synthetic_replay_credential.json": report_replay,
        "outer_assessment.json": outer_assessment,
        "outer_replay_credential.json": outer_replay,
        "probability_mass_audits.json": mass_audits,
    }
    for filename, value in values.items():
        artifacts[filename] = _write_canonical(
            resolved_output / filename,
            value,
        )

    manifest = {
        "schema": "d2t_rna.task4_acceptance_fixture_manifest.v2",
        "fixture_id": "task4.registered.synthetic-microcase.v1",
        "fixture_definition_hash": fixture_definition_hash,
        "contract_sha256": (
            "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
        ),
        "runtime": {
            "implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_cache_tag": sys.implementation.cache_tag,
            "pydantic_version": pydantic.__version__,
        },
        "artifact_model_schemas": {
            "exact_synthetic_report.json": (
                "d2t_rna.exact_synthetic_coverage_report@1.0"
            ),
            "exact_synthetic_replay_credential.json": (
                "d2t_rna.exact_coverage_replay_credential@1.0"
            ),
            "outer_assessment.json": (
                "d2t_rna.outer_approximation_assessment@1.0"
            ),
            "outer_replay_credential.json": (
                "d2t_rna.outer_approximation_replay_credential@1.0"
            ),
            "probability_mass_audits.json": (
                "tuple[d2t_rna.probability_mass_audit@1.0]"
            ),
        },
        "mass_audit_count": len(mass_audits),
        "support_spec_hash": canonical_sha256(support),
        "parameter_universe_hash": universe_hash,
        "coverage_engine_code_hash": engine_hash,
        "outer_verifier_code_hash": confidence_module_sha256(),
        "report_hash": canonical_sha256(report),
        "report_replay_credential_hash": canonical_sha256(report_replay),
        "outer_assessment_hash": canonical_sha256(outer_assessment),
        "outer_replay_credential_hash": canonical_sha256(outer_replay),
        "mathematical_statement_verified": (
            report.mathematical_statement_verified
        ),
        "risk_certificate_issued": report.risk_certificate_issued,
        "formal_scientific_certificate_authorized": (
            report.formal_scientific_certificate_authorized
        ),
        "prospective_claim_authorized": (
            report.prospective_claim_authorized
        ),
        "new_library_claim_authorized": (
            report.new_library_claim_authorized
        ),
        "serialized_bearer_authorization": (
            report_replay.serialized_bearer_authorization
        ),
        "external_source_anchor_required": (
            report_replay.external_source_anchor_required
        ),
        "artifacts_sha256": artifacts,
    }
    manifest_sha = _write_canonical(
        resolved_output / "fixture_manifest.json",
        manifest,
    )
    return {
        "output_dir": str(resolved_output),
        "fixture_manifest_sha256": manifest_sha,
        **manifest,
    }


def main() -> None:
    if (
        platform.python_implementation() != "CPython"
        or sys.version_info[:2] != (3, 11)
    ):
        raise RuntimeError(
            "Task 4 acceptance fixture CLI requires CPython 3.11"
        )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    summary = build_fixture(
        project_root=project_root,
        output_dir=args.output_dir,
    )
    print(canonical_json_bytes(summary).decode("utf-8"))


if __name__ == "__main__":
    main()
