"""Exact, fail-closed RiskCertificate semantic validation.

Task 2 validates candidate arithmetic and complete input bindings.  It cannot
authorize a scientific certificate: a reference is not a proof verdict, and
the only registered verifier is explicitly a structural test fixture.
"""

from __future__ import annotations

from enum import Enum
from fractions import Fraction
from typing import Literal

from pydantic import StrictStr, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.enums import (
    ProbabilityScope,
    UnconditionalDerivation,
)
from d2t_rna.contracts.primitives import (
    NonNegativeInt,
    ProofArtifactRef,
    Rational,
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.splits import SplitRelationSpec

from .registry import (
    TRUSTED_TASK2_REGISTRY_SHA256,
    RegistryResolutionError,
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    ensure_trusted_task2_registry,
    resolve_registry_ref,
)
from .scopes import (
    ProbabilityScopeDisposition,
    ScopePrerequisites,
    SyntheticKnownChannelPrerequisites,
    WithinLibraryPrerequisites,
    assess_probability_scope,
)
from .splits import (
    NuisanceHandlingEvidence,
    SplitDisposition,
    assess_split_relation,
)


TASK2_FIXTURE_VERIFIER_CONFIGURATION_SHA256 = (
    "627e9556dd1e2023ea65e7094653a1562271ce9a89de82a2ed498ecb960071d4"
)
TASK2_FIXTURE_CLAIM_SET_SHA256 = (
    "c998ce1e6775baec5f4167f236945ab405826c0183144b565f800514af76ec17"
)


class RiskSemanticError(ValueError):
    """Raised when a candidate contradicts the frozen semantics."""


class FailureAction(str, Enum):
    ABSTAIN = "ABSTAIN"
    CONTINUE_DECISION = "CONTINUE_DECISION"


class RegisteredFailure(str, Enum):
    QC = "QC"
    GOF = "GOF"
    SOLVER = "SOLVER"
    YIELD = "YIELD"


class FailureBranch(FrozenContractModel):
    failure: RegisteredFailure
    action: FailureAction


class FailurePolicyDefinition(FrozenContractModel):
    """Canonical preimage committed by the failure-policy registry member."""

    schema_id: Literal["d2t_rna.failure_policy_definition"] = (
        "d2t_rna.failure_policy_definition"
    )
    schema_version: Literal["1.0"] = "1.0"
    branches: tuple[FailureBranch, ...]
    unknown_failure_action: FailureAction

    @model_validator(mode="after")
    def every_registered_and_unknown_failure_abstains(
        self,
    ) -> "FailurePolicyDefinition":
        failures = tuple(branch.failure for branch in self.branches)
        if len(set(failures)) != len(failures):
            raise ValueError("failure policy contains duplicate branches")
        if failures != tuple(RegisteredFailure):
            raise ValueError(
                "failure branches must list QC, GOF, SOLVER, YIELD exactly "
                "once in registered order"
            )
        if any(
            branch.action is not FailureAction.ABSTAIN
            for branch in self.branches
        ):
            raise ValueError(
                "QC, GOF, solver, and yield failures must ABSTAIN"
            )
        if self.unknown_failure_action is not FailureAction.ABSTAIN:
            raise ValueError("unknown failures must ABSTAIN")
        return self


class RegisteredFailurePolicy(FrozenContractModel):
    schema_id: Literal["d2t_rna.registered_failure_policy"] = (
        "d2t_rna.registered_failure_policy"
    )
    schema_version: Literal["1.0"] = "1.0"
    policy_ref: RegistryRef
    definition: FailurePolicyDefinition

    @property
    def definition_hash(self) -> str:
        return canonical_sha256(self.definition)


def action_for_failure(
    policy: RegisteredFailurePolicy,
    failure: RegisteredFailure | str,
) -> FailureAction:
    """Return the registered action, defaulting every unknown failure to abstain."""

    if type(policy) is not RegisteredFailurePolicy:
        raise TypeError("policy must be exactly RegisteredFailurePolicy")
    rebuilt = strict_revalidate_contract_model(policy)
    if isinstance(failure, RegisteredFailure):
        for branch in rebuilt.definition.branches:
            if branch.failure is failure:
                return branch.action
    return rebuilt.definition.unknown_failure_action


def _as_fraction(value: Rational, *, label: str) -> Fraction:
    if type(value) is not Rational:
        raise TypeError(f"{label} must be exactly Rational")
    rebuilt = strict_revalidate_contract_model(value)
    result = Fraction(rebuilt.numerator, rebuilt.denominator)
    if result < 0 or result > 1:
        raise RiskSemanticError(f"{label} must be in the exact interval [0, 1]")
    return result


def _from_fraction(value: Fraction) -> Rational:
    return Rational(numerator=value.numerator, denominator=value.denominator)


def _equal(left: Rational, right: Rational) -> bool:
    return _as_fraction(left, label="left bound") == _as_fraction(
        right,
        label="right bound",
    )


def _leq(left: Rational, right: Rational) -> bool:
    return _as_fraction(left, label="left bound") <= _as_fraction(
        right,
        label="right bound",
    )


def good_event_union_bound(delta: Rational, rho: Rational) -> Rational:
    """Return the exact candidate bound ``delta + (1-delta) * rho``."""

    delta_fraction = _as_fraction(delta, label="conditional risk delta")
    rho_fraction = _as_fraction(rho, label="validity failure probability rho")
    return _from_fraction(
        delta_fraction + (Fraction(1, 1) - delta_fraction) * rho_fraction
    )


class UnconditionalRiskEvidence(FrozenContractModel):
    """Canonical derivation inputs; proof correctness still requires replay."""

    schema_id: Literal["d2t_rna.unconditional_risk_evidence"] = (
        "d2t_rna.unconditional_risk_evidence"
    )
    schema_version: Literal["1.0"] = "1.0"
    validity_event_id: RegisteredId
    validity_event_hash: Sha256Hex
    derivation: UnconditionalDerivation
    validity_failure_probability: Rational | None
    validity_event_failure_action: FailureAction
    derivation_proof: ProofArtifactRef | None

    @model_validator(mode="after")
    def derivation_shape_is_exact(self) -> "UnconditionalRiskEvidence":
        if self.validity_failure_probability is not None:
            _as_fraction(
                self.validity_failure_probability,
                label="validity failure probability",
            )
        if self.derivation is UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE:
            if self.validity_failure_probability is not None:
                raise ValueError("tower derivation does not take rho")
            if self.validity_event_failure_action is not FailureAction.ABSTAIN:
                raise ValueError("tower derivation uses canonical ABSTAIN action")
            if self.derivation_proof is None:
                raise ValueError("tower derivation requires a proof artifact")
        elif (
            self.derivation
            is UnconditionalDerivation.ABSTAIN_OUTSIDE_VALIDITY_EVENT
        ):
            if self.validity_failure_probability is not None:
                raise ValueError(
                    "abstain-outside derivation does not use a rho value"
                )
            if self.validity_event_failure_action is not FailureAction.ABSTAIN:
                raise ValueError(
                    "ABSTAIN_OUTSIDE_VALIDITY_EVENT requires ABSTAIN"
                )
            if self.derivation_proof is None:
                raise ValueError(
                    "abstain-outside derivation requires a proof artifact"
                )
        elif (
            self.derivation
            is UnconditionalDerivation.GOOD_EVENT_UNION_BOUND
        ):
            if self.validity_failure_probability is None:
                raise ValueError("GOOD_EVENT_UNION_BOUND requires rho")
            if (
                self.validity_event_failure_action
                is not FailureAction.CONTINUE_DECISION
            ):
                raise ValueError(
                    "GOOD_EVENT_UNION_BOUND requires CONTINUE_DECISION"
                )
            if self.derivation_proof is None:
                raise ValueError(
                    "good-event union derivation requires a proof artifact"
                )
        elif self.derivation is UnconditionalDerivation.NOT_AVAILABLE:
            if self.validity_failure_probability is not None:
                raise ValueError("NOT_AVAILABLE cannot carry rho")
            if self.validity_event_failure_action is not FailureAction.ABSTAIN:
                raise ValueError("NOT_AVAILABLE uses canonical ABSTAIN action")
            if self.derivation_proof is not None:
                raise ValueError("NOT_AVAILABLE cannot carry a proof artifact")
        else:  # pragma: no cover - defensive against future enum extension
            raise ValueError("unregistered unconditional derivation")
        return self


def derive_unconditional_bound(
    conditional_bound: Rational,
    evidence: UnconditionalRiskEvidence,
) -> Rational | None:
    """Compute unverified candidate arithmetic for the four registered forms."""

    if type(evidence) is not UnconditionalRiskEvidence:
        raise TypeError("evidence must be exactly UnconditionalRiskEvidence")
    delta = strict_revalidate_contract_model(conditional_bound)
    _as_fraction(delta, label="conditional risk bound")
    rebuilt = strict_revalidate_contract_model(evidence)
    if rebuilt.derivation in {
        UnconditionalDerivation.TOWER_UNIFORM_ALMOST_SURE,
        UnconditionalDerivation.ABSTAIN_OUTSIDE_VALIDITY_EVENT,
    }:
        return delta
    if rebuilt.derivation is UnconditionalDerivation.GOOD_EVENT_UNION_BOUND:
        assert rebuilt.validity_failure_probability is not None
        return good_event_union_bound(
            delta,
            rebuilt.validity_failure_probability,
        )
    if rebuilt.derivation is UnconditionalDerivation.NOT_AVAILABLE:
        return None
    raise RiskSemanticError("unregistered unconditional derivation")


class EffectiveMoleculeConditioningSpec(FrozenContractModel):
    """Hash-bound effective-N conditioning object for realized-library risk."""

    schema_id: Literal["d2t_rna.effective_molecule_conditioning"] = (
        "d2t_rna.effective_molecule_conditioning"
    )
    schema_version: Literal["1.0"] = "1.0"
    conditioning_id: RegisteredId
    dependency_unit_level: RegistryRef
    realized_library_object_id: RegisteredId
    realized_library_object_hash: Sha256Hex
    observed_effective_molecule_count: NonNegativeInt
    count_definition_hash: Sha256Hex
    parent_conditioning_sigma_field_hash: Sha256Hex
    counting_proof: ProofArtifactRef


class RiskEvidenceBindings(FrozenContractModel):
    """Complete candidate input bundle; references are not proof verdicts."""

    schema_id: Literal["d2t_rna.risk_evidence_bindings"] = (
        "d2t_rna.risk_evidence_bindings"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_space_hash: Sha256Hex
    split_relation_hash: Sha256Hex
    scope_prerequisites_hash: Sha256Hex | None
    nuisance_handling_hash: Sha256Hex | None
    uniform_confidence_set_proof: ProofArtifactRef
    indifference_decisive_implies_noncoverage_proof: ProofArtifactRef
    split_independence_proof: ProofArtifactRef | None
    failure_policy_definition_hash: Sha256Hex
    unconditional: UnconditionalRiskEvidence
    effective_molecule_conditioning: EffectiveMoleculeConditioningSpec | None

    @property
    def definition_hash(self) -> str:
        return canonical_sha256(self)


class ProofEvidenceGrade(str, Enum):
    TEST_FIXTURE_ONLY = "TEST_FIXTURE_ONLY"
    FORMAL_PROOF_REPLAY = "FORMAL_PROOF_REPLAY"


class ProofVerificationOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class RiskEvaluationInputBundle(FrozenContractModel):
    schema_id: Literal["d2t_rna.risk_evaluation_input_bundle"] = (
        "d2t_rna.risk_evaluation_input_bundle"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_space_hash: Sha256Hex
    split_relation_hash: Sha256Hex
    scope_prerequisites_hash: Sha256Hex | None
    nuisance_handling_hash: Sha256Hex | None
    risk_certificate_hash: Sha256Hex
    risk_evidence_hash: Sha256Hex
    failure_policy_definition_hash: Sha256Hex
    semantic_registry_root_hash: Sha256Hex

    @property
    def bundle_hash(self) -> str:
        return canonical_sha256(self)


class ProofVerificationReceipt(FrozenContractModel):
    """Structural receipt rebound to the complete evaluation input bundle."""

    schema_id: Literal["d2t_rna.proof_verification_receipt"] = (
        "d2t_rna.proof_verification_receipt"
    )
    schema_version: Literal["1.0"] = "1.0"
    receipt_id: RegisteredId
    probability_space_hash: Sha256Hex
    split_relation_hash: Sha256Hex
    scope_prerequisites_hash: Sha256Hex | None
    nuisance_handling_hash: Sha256Hex | None
    risk_certificate_hash: Sha256Hex
    risk_evidence_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    semantic_registry_root_hash: Sha256Hex
    verifier: RegistryRef
    verifier_code_hash: Sha256Hex
    verifier_configuration_hash: Sha256Hex
    claim_set_hash: Sha256Hex
    verification_log_hash: Sha256Hex
    evidence_grade: ProofEvidenceGrade
    outcome: ProofVerificationOutcome


class RiskAssessmentDisposition(str, Enum):
    NOT_ISSUED_EMPIRICAL_QA_ONLY = "NOT_ISSUED_EMPIRICAL_QA_ONLY"
    NOT_ISSUED_NEW_LIBRARY_HARD_NO_GO = (
        "NOT_ISSUED_NEW_LIBRARY_HARD_NO_GO"
    )
    NOT_ISSUED_SCOPE_OR_SPLIT_ABSTAIN = (
        "NOT_ISSUED_SCOPE_OR_SPLIT_ABSTAIN"
    )
    NOT_ISSUED_PENDING_PROOF_REPLAY = "NOT_ISSUED_PENDING_PROOF_REPLAY"
    NOT_ISSUED_PROOF_VERIFICATION_FAILED = (
        "NOT_ISSUED_PROOF_VERIFICATION_FAILED"
    )
    NOT_ISSUED_FORMAL_VERIFIER_UNAVAILABLE = (
        "NOT_ISSUED_FORMAL_VERIFIER_UNAVAILABLE"
    )
    NOT_ISSUED_SYNTHETIC_PENDING_TASK_4 = (
        "NOT_ISSUED_SYNTHETIC_PENDING_TASK_4"
    )
    TEST_FIXTURE_BINDINGS_MATCHED = "TEST_FIXTURE_BINDINGS_MATCHED"


class RiskCertificateAssessment(FrozenContractModel):
    schema_id: Literal["d2t_rna.risk_certificate_assessment"] = (
        "d2t_rna.risk_certificate_assessment"
    )
    schema_version: Literal["1.0"] = "1.0"
    probability_space_hash: Sha256Hex
    split_relation_hash: Sha256Hex
    scope_prerequisites_hash: Sha256Hex | None
    nuisance_handling_hash: Sha256Hex | None
    risk_certificate_hash: Sha256Hex
    risk_evidence_hash: Sha256Hex
    failure_policy_definition_hash: Sha256Hex
    semantic_registry_root_hash: Sha256Hex
    evaluation_input_bundle_hash: Sha256Hex
    proof_verification_receipt_hash: Sha256Hex | None
    disposition: RiskAssessmentDisposition
    certificate_issued: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False
    reason_codes: tuple[StrictStr, ...]


def validate_uniform_indifference_control(
    *,
    coverage: Rational,
    decisive_bound: Rational,
) -> None:
    """Use the exact noncoverage complement absent a separate tighter proof."""

    coverage_value = _as_fraction(coverage, label="uniform coverage")
    decisive_value = _as_fraction(
        decisive_bound,
        label="indifference decisive bound",
    )
    if coverage_value < Fraction(19, 20):
        raise RiskSemanticError("uniform confidence-set coverage must be >= 19/20")
    if decisive_value != Fraction(1, 1) - coverage_value:
        raise RiskSemanticError(
            "indifference decisive bound must equal the exact noncoverage "
            "complement when only decisive-implies-noncoverage is registered"
        )


def _validate_certificate_arithmetic(
    certificate: RiskCertificate,
    evidence: RiskEvidenceBindings,
) -> None:
    named_bounds = {
        "h0 wrong-reject bound": certificate.h0_wrong_reject_bound,
        "h1 wrong-certify bound": certificate.h1_wrong_certify_bound,
        "indifference decisive bound": (
            certificate.indifference_decisive_output_bound
        ),
        "confidence-set uniform coverage": (
            certificate.confidence_set_uniform_coverage
        ),
        "conditional bound": certificate.conditional_bound,
    }
    if certificate.unconditional_bound is not None:
        named_bounds["unconditional bound"] = certificate.unconditional_bound
    if certificate.prospective_unconditional_bound is not None:
        named_bounds["prospective unconditional bound"] = (
            certificate.prospective_unconditional_bound
        )
    for label, value in named_bounds.items():
        _as_fraction(value, label=label)

    validate_uniform_indifference_control(
        coverage=certificate.confidence_set_uniform_coverage,
        decisive_bound=certificate.indifference_decisive_output_bound,
    )
    for label, value in (
        ("h0 wrong-reject", certificate.h0_wrong_reject_bound),
        ("h1 wrong-certify", certificate.h1_wrong_certify_bound),
        (
            "indifference decisive",
            certificate.indifference_decisive_output_bound,
        ),
    ):
        if not _leq(value, certificate.conditional_bound):
            raise RiskSemanticError(
                f"{label} bound exceeds the registered conditional bound"
            )

    if certificate.success_event_hash != evidence.unconditional.validity_event_hash:
        raise RiskSemanticError(
            "certificate success event does not match derivation validity event"
        )
    if certificate.unconditional_derivation is not evidence.unconditional.derivation:
        raise RiskSemanticError(
            "certificate and evidence unconditional derivations differ"
        )
    expected_unconditional = derive_unconditional_bound(
        certificate.conditional_bound,
        evidence.unconditional,
    )
    if expected_unconditional is None:
        if certificate.unconditional_bound is not None:
            raise RiskSemanticError(
                "NOT_AVAILABLE derivation requires null unconditional bound"
            )
    elif certificate.unconditional_bound is None or not _equal(
        certificate.unconditional_bound,
        expected_unconditional,
    ):
        raise RiskSemanticError(
            "unconditional bound does not match the registered exact derivation"
        )

    if certificate.prospective_unconditional_bound is not None:
        raise RiskSemanticError(
            "prospective unconditional bounds are forbidden in v1"
        )
    if certificate.conditional_on_effective_molecule_count:
        if evidence.effective_molecule_conditioning is None:
            raise RiskSemanticError(
                "effective-molecule conditioning requires a structured spec"
            )
    elif evidence.effective_molecule_conditioning is not None:
        raise RiskSemanticError(
            "effective-molecule spec supplied to an unconditional-on-N candidate"
        )


def _validate_evidence_bindings(
    *,
    certificate: RiskCertificate,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    prerequisites: ScopePrerequisites | None,
    nuisance_handling: NuisanceHandlingEvidence | None,
    evidence: RiskEvidenceBindings,
    registry: TrustedSemanticRegistry,
) -> None:
    probability_hash = canonical_sha256(probability_space)
    split_hash = canonical_sha256(split_relation)
    prerequisites_hash = (
        canonical_sha256(prerequisites) if prerequisites is not None else None
    )
    nuisance_handling_hash = (
        canonical_sha256(nuisance_handling)
        if nuisance_handling is not None
        else None
    )
    if evidence.probability_space_hash != probability_hash:
        raise RiskSemanticError("risk evidence probability-space hash mismatch")
    if evidence.split_relation_hash != split_hash:
        raise RiskSemanticError("risk evidence split-relation hash mismatch")
    if evidence.scope_prerequisites_hash != prerequisites_hash:
        raise RiskSemanticError("risk evidence prerequisite hash mismatch")
    if evidence.nuisance_handling_hash != nuisance_handling_hash:
        raise RiskSemanticError("risk evidence nuisance-handling hash mismatch")

    split_proof = split_relation.selection_inference_independence_proof
    if evidence.split_independence_proof != split_proof:
        raise RiskSemanticError(
            "risk evidence independence proof differs from split relation"
        )
    if type(prerequisites) is WithinLibraryPrerequisites:
        if (
            nuisance_handling is not None
            and nuisance_handling.nuisance_parameter_space_hash
            != prerequisites.nuisance_parameter_space_hash
        ):
            raise RiskSemanticError(
                "nuisance handling parameter-space hash mismatch"
            )
        if (
            evidence.uniform_confidence_set_proof
            != prerequisites.uniform_confidence_set_proof
        ):
            raise RiskSemanticError(
                "risk evidence uniform-CS proof differs from prerequisite"
            )
        effective = evidence.effective_molecule_conditioning
        if effective is not None:
            if effective.observed_effective_molecule_count <= 0:
                raise RiskSemanticError(
                    "effective-molecule count must be positive for a candidate"
                )
            if (
                effective.parent_conditioning_sigma_field_hash
                != certificate.conditioning_sigma_field_hash
            ):
                raise RiskSemanticError(
                    "effective-molecule conditioning sigma-field mismatch"
                )
            if (
                effective.realized_library_object_id
                != prerequisites.realized_library_object_id
                or effective.realized_library_object_hash
                != prerequisites.realized_library_object_hash
            ):
                raise RiskSemanticError(
                    "effective-molecule source library binding mismatch"
                )
            if effective.dependency_unit_level != split_relation.dependency_unit_level:
                raise RiskSemanticError(
                    "effective-molecule dependency-unit binding mismatch"
                )
            try:
                resolve_registry_ref(
                    effective.dependency_unit_level,
                    registry,
                    SemanticRegistryRole.DEPENDENCY_UNIT,
                )
            except RegistryResolutionError as exc:
                raise RiskSemanticError(
                    f"effective-molecule dependency registration failed: {exc}"
                ) from exc
    elif evidence.effective_molecule_conditioning is not None:
        raise RiskSemanticError(
            "effective-molecule conditioning is only valid within a realized library"
        )

    if type(prerequisites) is SyntheticKnownChannelPrerequisites:
        if evidence.effective_molecule_conditioning is not None:
            raise RiskSemanticError(
                "synthetic candidates cannot use realized-library effective N"
            )


def _make_input_bundle(
    *,
    probability_space_hash: str,
    split_relation_hash: str,
    prerequisites_hash: str | None,
    nuisance_handling_hash: str | None,
    certificate_hash: str,
    evidence_hash: str,
    failure_policy_hash: str,
) -> RiskEvaluationInputBundle:
    return RiskEvaluationInputBundle(
        probability_space_hash=probability_space_hash,
        split_relation_hash=split_relation_hash,
        scope_prerequisites_hash=prerequisites_hash,
        nuisance_handling_hash=nuisance_handling_hash,
        risk_certificate_hash=certificate_hash,
        risk_evidence_hash=evidence_hash,
        failure_policy_definition_hash=failure_policy_hash,
        semantic_registry_root_hash=TRUSTED_TASK2_REGISTRY_SHA256,
    )


def _assessment(
    *,
    bundle: RiskEvaluationInputBundle,
    disposition: RiskAssessmentDisposition,
    reasons: tuple[str, ...],
    receipt: ProofVerificationReceipt | None = None,
) -> RiskCertificateAssessment:
    return RiskCertificateAssessment(
        probability_space_hash=bundle.probability_space_hash,
        split_relation_hash=bundle.split_relation_hash,
        scope_prerequisites_hash=bundle.scope_prerequisites_hash,
        nuisance_handling_hash=bundle.nuisance_handling_hash,
        risk_certificate_hash=bundle.risk_certificate_hash,
        risk_evidence_hash=bundle.risk_evidence_hash,
        failure_policy_definition_hash=bundle.failure_policy_definition_hash,
        semantic_registry_root_hash=bundle.semantic_registry_root_hash,
        evaluation_input_bundle_hash=bundle.bundle_hash,
        proof_verification_receipt_hash=(
            canonical_sha256(receipt) if receipt is not None else None
        ),
        disposition=disposition,
        certificate_issued=False,
        scientific_claim_authorized=False,
        reason_codes=reasons,
    )


def _validate_receipt_bindings(
    receipt: ProofVerificationReceipt,
    bundle: RiskEvaluationInputBundle,
) -> None:
    observed = {
        "probability_space_hash": receipt.probability_space_hash,
        "split_relation_hash": receipt.split_relation_hash,
        "scope_prerequisites_hash": receipt.scope_prerequisites_hash,
        "nuisance_handling_hash": receipt.nuisance_handling_hash,
        "risk_certificate_hash": receipt.risk_certificate_hash,
        "risk_evidence_hash": receipt.risk_evidence_hash,
        "evaluation_input_bundle_hash": receipt.evaluation_input_bundle_hash,
        "semantic_registry_root_hash": receipt.semantic_registry_root_hash,
    }
    expected = {
        "probability_space_hash": bundle.probability_space_hash,
        "split_relation_hash": bundle.split_relation_hash,
        "scope_prerequisites_hash": bundle.scope_prerequisites_hash,
        "nuisance_handling_hash": bundle.nuisance_handling_hash,
        "risk_certificate_hash": bundle.risk_certificate_hash,
        "risk_evidence_hash": bundle.risk_evidence_hash,
        "evaluation_input_bundle_hash": bundle.bundle_hash,
        "semantic_registry_root_hash": bundle.semantic_registry_root_hash,
    }
    mismatched = tuple(
        key for key in expected if observed[key] != expected[key]
    )
    if mismatched:
        raise RiskSemanticError(
            "proof receipt binding mismatch: " + ", ".join(mismatched)
        )


def evaluate_risk_certificate(
    *,
    certificate: RiskCertificate,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    scope_prerequisites: ScopePrerequisites | None,
    failure_policy: RegisteredFailurePolicy,
    evidence: RiskEvidenceBindings,
    registry: TrustedSemanticRegistry,
    proof_verification_receipt: ProofVerificationReceipt | None,
    nuisance_handling: NuisanceHandlingEvidence | None = None,
) -> RiskCertificateAssessment:
    """Validate a candidate while preserving Task 2's no-issuance boundary."""

    exact_inputs = (
        (certificate, RiskCertificate, "certificate"),
        (probability_space, ProbabilitySpaceSpec, "probability_space"),
        (split_relation, SplitRelationSpec, "split_relation"),
        (failure_policy, RegisteredFailurePolicy, "failure_policy"),
        (evidence, RiskEvidenceBindings, "evidence"),
        (registry, TrustedSemanticRegistry, "registry"),
    )
    for value, expected_type, label in exact_inputs:
        if type(value) is not expected_type:
            raise TypeError(f"{label} must be exactly {expected_type.__name__}")
    if scope_prerequisites is not None and type(scope_prerequisites) not in {
        WithinLibraryPrerequisites,
        SyntheticKnownChannelPrerequisites,
    }:
        raise TypeError(
            "scope_prerequisites must be an exact registered Task 2 type"
        )
    if nuisance_handling is not None and type(
        nuisance_handling
    ) is not NuisanceHandlingEvidence:
        raise TypeError(
            "nuisance_handling must be exactly NuisanceHandlingEvidence"
        )
    if proof_verification_receipt is not None and type(
        proof_verification_receipt
    ) is not ProofVerificationReceipt:
        raise TypeError(
            "proof_verification_receipt must be exactly "
            "ProofVerificationReceipt"
        )
    cert = strict_revalidate_contract_model(certificate)
    probability = strict_revalidate_contract_model(probability_space)
    split = strict_revalidate_contract_model(split_relation)
    prerequisites = (
        strict_revalidate_contract_model(scope_prerequisites)
        if scope_prerequisites is not None
        else None
    )
    nuisance = (
        strict_revalidate_contract_model(nuisance_handling)
        if nuisance_handling is not None
        else None
    )
    policy = strict_revalidate_contract_model(failure_policy)
    bindings = strict_revalidate_contract_model(evidence)
    trusted = ensure_trusted_task2_registry(registry)

    probability_hash = canonical_sha256(probability)
    split_hash = canonical_sha256(split)
    prerequisites_hash = (
        canonical_sha256(prerequisites) if prerequisites is not None else None
    )
    nuisance_hash = canonical_sha256(nuisance) if nuisance is not None else None
    certificate_hash = canonical_sha256(cert)
    evidence_hash = canonical_sha256(bindings)

    if cert.probability_scope is not probability.probability_scope:
        raise RiskSemanticError(
            "certificate probability scope does not match ProbabilitySpaceSpec"
        )
    if (
        cert.conditioning_sigma_field_hash
        != probability.conditioning_sigma_field_hash
    ):
        raise RiskSemanticError(
            "certificate conditioning sigma-field does not match probability space"
        )
    if cert.failure_event_policy != policy.policy_ref:
        raise RiskSemanticError(
            "certificate failure policy reference does not match supplied policy"
        )
    try:
        policy_member = resolve_registry_ref(
            policy.policy_ref,
            trusted,
            SemanticRegistryRole.FAILURE_POLICY,
        )
    except RegistryResolutionError as exc:
        raise RiskSemanticError(f"failure-policy registration failed: {exc}") from exc
    if policy.definition_hash != policy_member.member_hash:
        raise RiskSemanticError(
            "failure-policy definition is not the registered hash preimage"
        )
    if bindings.failure_policy_definition_hash != policy.definition_hash:
        raise RiskSemanticError("failure-policy definition hash mismatch")

    _validate_evidence_bindings(
        certificate=cert,
        probability_space=probability,
        split_relation=split,
        prerequisites=prerequisites,
        nuisance_handling=nuisance,
        evidence=bindings,
        registry=trusted,
    )
    _validate_certificate_arithmetic(cert, bindings)
    scope = assess_probability_scope(probability, trusted, prerequisites)
    split_assessment = assess_split_relation(
        split,
        trusted,
        expected_conditioning_sigma_field_hash=(
            probability.conditioning_sigma_field_hash
        ),
        nuisance_handling=nuisance,
    )
    bundle = _make_input_bundle(
        probability_space_hash=probability_hash,
        split_relation_hash=split_hash,
        prerequisites_hash=prerequisites_hash,
        nuisance_handling_hash=nuisance_hash,
        certificate_hash=certificate_hash,
        evidence_hash=evidence_hash,
        failure_policy_hash=policy.definition_hash,
    )

    if (
        probability.probability_scope
        is ProbabilityScope.NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL
    ):
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition.NOT_ISSUED_NEW_LIBRARY_HARD_NO_GO
            ),
            reasons=("NO_GO_NEW_LIBRARY_RISK_CERTIFICATE",),
        )
    if (
        probability.probability_scope
        is ProbabilityScope.FINITE_OBSERVED_DATASET_SUBSAMPLING
    ):
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition.NOT_ISSUED_EMPIRICAL_QA_ONLY
            ),
            reasons=(
                "EMPIRICAL_QA_TARGET_ONLY",
                "LATENT_RISK_CERTIFICATE_FORBIDDEN",
            ),
        )
    split_forces_abstain = (
        split_assessment.disposition is SplitDisposition.ABSTAIN
        or split_assessment.disposition
        is SplitDisposition.SHARED_OR_UNKNOWN_DEPENDENCE
        or split_assessment.disposition
        is SplitDisposition.FINITE_POPULATION_JOINT_LAW_ONLY
    )
    if (
        scope.disposition is ProbabilityScopeDisposition.ABSTAIN
        or split_forces_abstain
    ):
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition.NOT_ISSUED_SCOPE_OR_SPLIT_ABSTAIN
            ),
            reasons=scope.reason_codes + split_assessment.reason_codes,
        )
    if probability.probability_scope is ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL:
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition
                .NOT_ISSUED_SYNTHETIC_PENDING_TASK_4
            ),
            reasons=("EXACT_PROOF_ENGINE_PENDING_TASK_4",),
        )

    if proof_verification_receipt is None:
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition.NOT_ISSUED_PENDING_PROOF_REPLAY
            ),
            reasons=(
                "HASH_REFERENCES_ARE_NOT_PROOF_VERDICTS",
                "TRUSTED_PROOF_REPLAY_RECEIPT_MISSING",
            ),
        )

    receipt = strict_revalidate_contract_model(proof_verification_receipt)
    _validate_receipt_bindings(receipt, bundle)
    if receipt.outcome is ProofVerificationOutcome.FAIL:
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition
                .NOT_ISSUED_PROOF_VERIFICATION_FAILED
            ),
            reasons=("REGISTERED_PROOF_REPLAY_FAILED",),
            receipt=receipt,
        )
    if receipt.evidence_grade is ProofEvidenceGrade.FORMAL_PROOF_REPLAY:
        return _assessment(
            bundle=bundle,
            disposition=(
                RiskAssessmentDisposition
                .NOT_ISSUED_FORMAL_VERIFIER_UNAVAILABLE
            ),
            reasons=(
                "TASK_2_HAS_NO_AUTHENTICATED_FORMAL_REPLAY_RUNNER",
                "CALLER_SUPPLIED_RECEIPT_CANNOT_AUTHORIZE_SCIENCE",
            ),
            receipt=receipt,
        )

    try:
        verifier_member = resolve_registry_ref(
            receipt.verifier,
            trusted,
            SemanticRegistryRole.TEST_FIXTURE_VERIFIER,
        )
    except RegistryResolutionError as exc:
        raise RiskSemanticError(
            f"fixture verifier registration failed: {exc}"
        ) from exc
    if receipt.verifier_code_hash != verifier_member.member_hash:
        raise RiskSemanticError("fixture verifier code hash mismatch")
    if (
        receipt.verifier_configuration_hash
        != TASK2_FIXTURE_VERIFIER_CONFIGURATION_SHA256
    ):
        raise RiskSemanticError("fixture verifier configuration hash mismatch")
    if receipt.claim_set_hash != TASK2_FIXTURE_CLAIM_SET_SHA256:
        raise RiskSemanticError("fixture verifier claim-set hash mismatch")
    return _assessment(
        bundle=bundle,
        disposition=RiskAssessmentDisposition.TEST_FIXTURE_BINDINGS_MATCHED,
        reasons=(
            "CALLER_SUPPLIED_TEST_FIXTURE_BINDINGS_MATCHED",
            "PROOF_AND_LOG_CONTENT_NOT_AUTHENTICATED",
            "SCIENTIFIC_CERTIFICATE_NOT_ISSUED",
        ),
        receipt=receipt,
    )
