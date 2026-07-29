from __future__ import annotations

from d2t_rna.contracts.enums import (
    CoverageBoundMethod,
    ProbabilityScope,
    SplitRelation,
    UnconditionalDerivation,
)
from d2t_rna.contracts.primitives import (
    NamedBound,
    ObjectCommitment,
    OverlapCount,
    ProofArtifactRef,
    Rational,
    RegistryRef,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.scenario import ScenarioProof
from d2t_rna.contracts.splits import SplitRelationSpec

from .conftest import SHA_A, SHA_B, SHA_C, SHA_D, SHA_E, SHA_F


def test_probability_space_exposes_every_registered_field() -> None:
    spec = ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.FINITE_OBSERVED_DATASET_SUBSAMPLING,
        fixed_objects=(
            ObjectCommitment(object_id="dataset.D_obs", object_hash=SHA_A),
        ),
        random_objects=(
            ObjectCommitment(object_id="subsample.index.I", object_hash=SHA_B),
        ),
        sampling_law_hash=SHA_C,
        parameter_space_hash=SHA_D,
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=SHA_F,
        estimand=RegistryRef(
            registry_id="estimand.empirical_feature_distribution",
            registry_hash=SHA_A,
        ),
        target=RegistryRef(
            registry_id="target.full_observed_dataset_empirical_feature_distribution",
            registry_hash=SHA_B,
        ),
        formal_scientific_risk_guarantee=False,
    )
    assert set(spec.model_dump(mode="json")) == {
        "schema_id",
        "schema_version",
        "probability_scope",
        "fixed_objects",
        "random_objects",
        "sampling_law_hash",
        "parameter_space_hash",
        "conditioning_sigma_field_hash",
        "observation_model_hash",
        "estimand",
        "target",
        "formal_scientific_risk_guarantee",
    }


def test_split_relation_uses_structured_dependency_evidence() -> None:
    spec = SplitRelationSpec(
        split_relation=SplitRelation.CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE,
        dependency_unit_level=RegistryRef(
            registry_id="dependency.umi_family",
            registry_hash=SHA_A,
        ),
        planning_partition_hash=SHA_B,
        certificate_partition_hash=SHA_C,
        conditioning_sigma_field_hash=SHA_D,
        selection_inference_independence_proof=ProofArtifactRef(
            proof_id="proof.conditional_independence",
            artifact_hash=SHA_E,
        ),
        overlap_counts=(
            OverlapCount(
                left_partition_id="planning",
                right_partition_id="certificate",
                dependency_unit_level=RegistryRef(
                    registry_id="dependency.umi_family",
                    registry_hash=SHA_A,
                ),
                count=0,
            ),
        ),
        split_seed=11,
    )
    assert spec.overlap_counts[0].count == 0


def test_risk_certificate_schema_preserves_all_bound_types() -> None:
    bound = Rational(numerator=1, denominator=20)
    cert = RiskCertificate(
        h0_wrong_reject_bound=bound,
        h1_wrong_certify_bound=bound,
        indifference_decisive_output_bound=bound,
        confidence_set_uniform_coverage=Rational(numerator=19, denominator=20),
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        conditioning_sigma_field_hash=SHA_A,
        success_event_hash=SHA_B,
        failure_event_policy=RegistryRef(
            registry_id="failure.abstain_all_registered",
            registry_hash=SHA_C,
        ),
        conditional_bound=bound,
        unconditional_bound=bound,
        unconditional_derivation=UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE,
        conditional_on_effective_molecule_count=False,
        prospective_unconditional_bound=None,
    )
    assert cert.indifference_decisive_output_bound == bound


def test_scenario_proof_schema_has_reproducibility_fields() -> None:
    proof = ScenarioProof(
        scenario_id="scenario.micro.001",
        law_hash=SHA_A,
        hypothesis_region=RegistryRef(
            registry_id="hypothesis.indifference",
            registry_hash=SHA_B,
        ),
        coverage_core_membership=RegistryRef(
            registry_id="core.registered",
            registry_hash=SHA_C,
        ),
        conditioning_sigma_field_hash=SHA_D,
        risk_upper_bounds=(
            NamedBound(
                bound_id="risk.incorrect_decisive_output",
                value=Rational(numerator=1, denominator=20),
            ),
        ),
        coverage_lower_bounds=(
            NamedBound(
                bound_id="coverage.registered_core",
                value=Rational(numerator=19, denominator=20),
            ),
        ),
        coverage_bound_method=CoverageBoundMethod.EXACT_ENUMERATION,
        probability_mass_accounted=Rational(numerator=1, denominator=1),
        omitted_mass_bound=Rational(numerator=0, denominator=1),
        numerical_error_bound=Rational(numerator=0, denominator=1),
        proof_artifact_hash=SHA_E,
        formal_guarantee=True,
    )
    assert proof.coverage_bound_method is CoverageBoundMethod.EXACT_ENUMERATION


def test_json_schemas_forbid_additional_properties() -> None:
    for model in (
        ProbabilitySpaceSpec,
        SplitRelationSpec,
        RiskCertificate,
        ScenarioProof,
    ):
        assert model.model_json_schema()["additionalProperties"] is False
