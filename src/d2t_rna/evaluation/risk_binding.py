"""Replayable Task 2 semantic binding for Task 5 risk inputs.

The frozen :class:`~d2t_rna.contracts.risk.RiskCertificate` schema is a data
container, not an issuance verdict.  Task 5 therefore carries every raw input
needed by the Task 2 production evaluator and re-evaluates those inputs instead
of trusting certificate fields or a serialized assessment.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
    strict_revalidate_contract_model,
)
from d2t_rna.contracts.primitives import Sha256Hex
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.contracts.risk import RiskCertificate
from d2t_rna.contracts.splits import SplitRelationSpec
from d2t_rna.exact.confidence import python_function_execution_sha256
import d2t_rna.probability.risk as task2_risk
from d2t_rna.probability.registry import TrustedSemanticRegistry
from d2t_rna.probability.risk import (
    ProofVerificationReceipt,
    RegisteredFailurePolicy,
    RiskCertificateAssessment,
    RiskEvidenceBindings,
)
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
    WithinLibraryPrerequisites,
)
from d2t_rna.probability.splits import NuisanceHandlingEvidence


RiskScopePrerequisites = (
    WithinLibraryPrerequisites | SyntheticKnownChannelPrerequisites
)
_TASK2_EVALUATOR_PURPOSE = "TASK5_RISK_CERTIFICATE_SEMANTIC_REPLAY"
_TASK5_RISK_BINDING_PURPOSE = "TASK5_RISK_BINDING_WRAPPER_REPLAY"
_TASK2_RISK_EVALUATOR = task2_risk.evaluate_risk_certificate
_EXECUTION_HASHER = python_function_execution_sha256


def _task2_evaluator_execution_sha256() -> str:
    """Bind the live Task 2 evaluator and its recursively referenced globals."""

    if (
        task2_risk.evaluate_risk_certificate is not _TASK2_RISK_EVALUATOR
        or python_function_execution_sha256 is not _EXECUTION_HASHER
    ):
        raise RuntimeError(
            "Task 2 risk semantic evaluator runtime identity changed"
        )
    return python_function_execution_sha256(
        _TASK2_RISK_EVALUATOR,
        purpose=_TASK2_EVALUATOR_PURPOSE,
        strict_pure=False,
    )


_TASK2_EVALUATOR_EXECUTION_BASELINE_SHA256 = (
    _task2_evaluator_execution_sha256()
)


def _assert_task2_evaluator_execution_closure() -> str:
    observed = _task2_evaluator_execution_sha256()
    if observed != _TASK2_EVALUATOR_EXECUTION_BASELINE_SHA256:
        raise RuntimeError(
            "Task 2 risk semantic evaluator execution closure changed"
        )
    return observed


class RiskCertificateEvaluationInputs(FrozenContractModel):
    """Complete serializable preimage for ``evaluate_risk_certificate``."""

    schema_id: Literal["d2t_rna.risk_certificate_evaluation_inputs"] = (
        "d2t_rna.risk_certificate_evaluation_inputs"
    )
    schema_version: Literal["1.0"] = "1.0"
    risk_certificate: RiskCertificate
    probability_space: ProbabilitySpaceSpec
    split_relation: SplitRelationSpec
    scope_prerequisites: RiskScopePrerequisites | None
    failure_policy: RegisteredFailurePolicy
    evidence: RiskEvidenceBindings
    registry: TrustedSemanticRegistry
    proof_verification_receipt: ProofVerificationReceipt | None
    nuisance_handling: NuisanceHandlingEvidence | None

    @model_validator(mode="after")
    def raw_inputs_use_only_registered_exact_types(
        self,
    ) -> "RiskCertificateEvaluationInputs":
        exact_inputs = (
            (self.risk_certificate, RiskCertificate, "risk_certificate"),
            (self.probability_space, ProbabilitySpaceSpec, "probability_space"),
            (self.split_relation, SplitRelationSpec, "split_relation"),
            (
                self.failure_policy,
                RegisteredFailurePolicy,
                "failure_policy",
            ),
            (self.evidence, RiskEvidenceBindings, "evidence"),
            (self.registry, TrustedSemanticRegistry, "registry"),
        )
        for value, expected_type, label in exact_inputs:
            if type(value) is not expected_type:
                raise TypeError(
                    f"{label} must be exactly {expected_type.__name__}"
                )
        if self.scope_prerequisites is not None and type(
            self.scope_prerequisites
        ) not in {
            WithinLibraryPrerequisites,
            SyntheticKnownChannelPrerequisites,
        }:
            raise TypeError(
                "scope_prerequisites must be an exact registered Task 2 type"
            )
        if self.proof_verification_receipt is not None and type(
            self.proof_verification_receipt
        ) is not ProofVerificationReceipt:
            raise TypeError(
                "proof_verification_receipt must be exactly "
                "ProofVerificationReceipt"
            )
        if self.nuisance_handling is not None and type(
            self.nuisance_handling
        ) is not NuisanceHandlingEvidence:
            raise TypeError(
                "nuisance_handling must be exactly NuisanceHandlingEvidence"
            )
        return self

    @property
    def inputs_sha256(self) -> str:
        return canonical_sha256(self)


def _evaluate_inputs(
    inputs: RiskCertificateEvaluationInputs,
) -> RiskCertificateAssessment:
    if type(inputs) is not RiskCertificateEvaluationInputs:
        raise TypeError(
            "inputs must be exactly RiskCertificateEvaluationInputs"
        )
    execution_pre = _assert_task2_evaluator_execution_closure()
    checked = strict_revalidate_contract_model(inputs)
    assessment = _TASK2_RISK_EVALUATOR(
        certificate=checked.risk_certificate,
        probability_space=checked.probability_space,
        split_relation=checked.split_relation,
        scope_prerequisites=checked.scope_prerequisites,
        failure_policy=checked.failure_policy,
        evidence=checked.evidence,
        registry=checked.registry,
        proof_verification_receipt=checked.proof_verification_receipt,
        nuisance_handling=checked.nuisance_handling,
    )
    execution_post = _assert_task2_evaluator_execution_closure()
    if execution_post != execution_pre:
        raise RuntimeError(
            "Task 2 risk semantic evaluator changed during replay"
        )
    return assessment


_RISK_BINDING_INPUT_EVALUATOR = _evaluate_inputs


def _risk_binding_evaluator_execution_sha256() -> str:
    """Bind the Task 5 wrapper that validates and dispatches Task 2 replay."""

    if (
        globals().get("_evaluate_inputs")
        is not _RISK_BINDING_INPUT_EVALUATOR
    ):
        raise RuntimeError(
            "Task 5 risk binding evaluator runtime identity changed"
        )
    if python_function_execution_sha256 is not _EXECUTION_HASHER:
        raise RuntimeError(
            "Task 5 risk binding execution hasher runtime identity changed"
        )
    return python_function_execution_sha256(
        _RISK_BINDING_INPUT_EVALUATOR,
        purpose=_TASK5_RISK_BINDING_PURPOSE,
        strict_pure=False,
    )


_TASK5_RISK_BINDING_EXECUTION_BASELINE_SHA256 = (
    _risk_binding_evaluator_execution_sha256()
)


def _assert_risk_binding_evaluator_execution_closure() -> str:
    observed = _risk_binding_evaluator_execution_sha256()
    if observed != _TASK5_RISK_BINDING_EXECUTION_BASELINE_SHA256:
        raise RuntimeError(
            "Task 5 risk binding evaluator execution closure changed"
        )
    return observed


class RiskCertificateReplayBundle(FrozenContractModel):
    """Raw Task 2 inputs plus an assessment that must replay byte-for-byte."""

    schema_id: Literal["d2t_rna.risk_certificate_replay_bundle"] = (
        "d2t_rna.risk_certificate_replay_bundle"
    )
    schema_version: Literal["3.0"] = "3.0"
    inputs: RiskCertificateEvaluationInputs
    risk_evaluation_inputs_sha256: Sha256Hex
    risk_certificate_sha256: Sha256Hex
    assessment: RiskCertificateAssessment
    risk_certificate_assessment_sha256: Sha256Hex
    task2_semantic_evaluator_execution_sha256: Sha256Hex
    task5_risk_binding_evaluator_execution_sha256: Sha256Hex
    task2_semantic_evaluator_replayed: Literal[True] = True
    task5_risk_binding_evaluator_replayed: Literal[True] = True
    serialized_bearer_authorization: Literal[False] = False
    certificate_issued: Literal[False] = False
    scientific_claim_authorized: Literal[False] = False

    @model_validator(mode="after")
    def assessment_replays_from_raw_task2_inputs(
        self,
    ) -> "RiskCertificateReplayBundle":
        wrapper_execution_pre = (
            _assert_risk_binding_evaluator_execution_closure()
        )
        if type(self.inputs) is not RiskCertificateEvaluationInputs:
            raise TypeError(
                "inputs must be exactly RiskCertificateEvaluationInputs"
            )
        checked_inputs = strict_revalidate_contract_model(self.inputs)
        if type(self.assessment) is not RiskCertificateAssessment:
            raise TypeError(
                "assessment must be exactly RiskCertificateAssessment"
            )
        checked_assessment = strict_revalidate_contract_model(self.assessment)

        if (
            canonical_sha256(checked_inputs)
            != self.risk_evaluation_inputs_sha256
        ):
            raise ValueError("risk evaluation input hash does not replay")
        certificate_sha256 = canonical_sha256(
            checked_inputs.risk_certificate
        )
        if certificate_sha256 != self.risk_certificate_sha256:
            raise ValueError("risk certificate hash does not replay")
        if checked_assessment.risk_certificate_hash != certificate_sha256:
            raise ValueError(
                "Task 2 assessment is bound to a different risk certificate"
            )
        if (
            canonical_sha256(checked_assessment)
            != self.risk_certificate_assessment_sha256
        ):
            raise ValueError("risk certificate assessment hash does not replay")

        replayed = _RISK_BINDING_INPUT_EVALUATOR(checked_inputs)
        if (
            self.task2_semantic_evaluator_execution_sha256
            != _assert_task2_evaluator_execution_closure()
        ):
            raise ValueError(
                "Task 2 risk semantic evaluator execution hash is stale"
            )
        if (
            self.task5_risk_binding_evaluator_execution_sha256
            != wrapper_execution_pre
        ):
            raise ValueError(
                "Task 5 risk binding evaluator execution hash is stale"
            )
        if (
            canonical_json_bytes(replayed)
            != canonical_json_bytes(checked_assessment)
        ):
            raise ValueError(
                "serialized risk assessment does not match fresh Task 2 "
                "semantic evaluation"
            )
        if replayed.certificate_issued or replayed.scientific_claim_authorized:
            raise ValueError(
                "Task 2 risk replay cannot authorize a certificate or "
                "scientific claim"
            )
        wrapper_execution_post = (
            _assert_risk_binding_evaluator_execution_closure()
        )
        if wrapper_execution_post != wrapper_execution_pre:
            raise RuntimeError(
                "Task 5 risk binding evaluator changed during replay"
            )
        return self

    @property
    def bundle_sha256(self) -> str:
        return canonical_sha256(self)


def build_risk_certificate_replay_bundle(
    *,
    risk_certificate: RiskCertificate,
    probability_space: ProbabilitySpaceSpec,
    split_relation: SplitRelationSpec,
    scope_prerequisites: RiskScopePrerequisites | None,
    failure_policy: RegisteredFailurePolicy,
    evidence: RiskEvidenceBindings,
    registry: TrustedSemanticRegistry,
    proof_verification_receipt: ProofVerificationReceipt | None,
    nuisance_handling: NuisanceHandlingEvidence | None = None,
) -> RiskCertificateReplayBundle:
    """Evaluate all raw inputs and return a non-authorizing replay bundle."""

    inputs = RiskCertificateEvaluationInputs(
        risk_certificate=risk_certificate,
        probability_space=probability_space,
        split_relation=split_relation,
        scope_prerequisites=scope_prerequisites,
        failure_policy=failure_policy,
        evidence=evidence,
        registry=registry,
        proof_verification_receipt=proof_verification_receipt,
        nuisance_handling=nuisance_handling,
    )
    wrapper_execution_pre = _assert_risk_binding_evaluator_execution_closure()
    assessment = _RISK_BINDING_INPUT_EVALUATOR(inputs)
    wrapper_execution_post = _assert_risk_binding_evaluator_execution_closure()
    if wrapper_execution_post != wrapper_execution_pre:
        raise RuntimeError(
            "Task 5 risk binding evaluator changed during bundle build"
        )
    return RiskCertificateReplayBundle(
        inputs=inputs,
        risk_evaluation_inputs_sha256=canonical_sha256(inputs),
        risk_certificate_sha256=canonical_sha256(inputs.risk_certificate),
        assessment=assessment,
        risk_certificate_assessment_sha256=canonical_sha256(assessment),
        task2_semantic_evaluator_execution_sha256=(
            _assert_task2_evaluator_execution_closure()
        ),
        task5_risk_binding_evaluator_execution_sha256=(
            wrapper_execution_pre
        ),
        task2_semantic_evaluator_replayed=True,
        task5_risk_binding_evaluator_replayed=True,
        serialized_bearer_authorization=False,
        certificate_issued=False,
        scientific_claim_authorized=False,
    )


def replay_risk_certificate_replay_bundle(
    bundle: RiskCertificateReplayBundle,
) -> RiskCertificateReplayBundle:
    """Strictly rebuild and freshly re-evaluate a serialized risk bundle."""

    if type(bundle) is not RiskCertificateReplayBundle:
        raise TypeError(
            "bundle must be exactly RiskCertificateReplayBundle"
        )
    try:
        wrapper_execution_pre = (
            _assert_risk_binding_evaluator_execution_closure()
        )
        checked = strict_revalidate_contract_model(bundle)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"risk certificate replay bundle failed structural replay: {exc}"
        ) from exc
    replayed_assessment = _RISK_BINDING_INPUT_EVALUATOR(checked.inputs)
    if (
        canonical_json_bytes(replayed_assessment)
        != canonical_json_bytes(checked.assessment)
    ):
        raise ValueError(
            "risk certificate replay bundle does not match fresh Task 2 "
            "semantic evaluation"
        )
    wrapper_execution_post = _assert_risk_binding_evaluator_execution_closure()
    if wrapper_execution_post != wrapper_execution_pre:
        raise RuntimeError(
            "Task 5 risk binding evaluator changed during bundle replay"
        )
    return checked
