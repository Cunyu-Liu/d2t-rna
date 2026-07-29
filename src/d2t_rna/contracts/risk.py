"""Immutable RiskCertificate schema; issuance logic is Task 2."""

from __future__ import annotations

from typing import Literal

from pydantic import StrictBool

from .base import FrozenContractModel
from .enums import ProbabilityScope, UnconditionalDerivation
from .primitives import Rational, RegistryRef, Sha256Hex


class RiskCertificate(FrozenContractModel):
    schema_id: Literal["d2t_rna.risk_certificate"] = (
        "d2t_rna.risk_certificate"
    )
    schema_version: Literal["1.0"] = "1.0"
    h0_wrong_reject_bound: Rational
    h1_wrong_certify_bound: Rational
    indifference_decisive_output_bound: Rational
    confidence_set_uniform_coverage: Rational
    probability_scope: ProbabilityScope
    conditioning_sigma_field_hash: Sha256Hex
    success_event_hash: Sha256Hex
    failure_event_policy: RegistryRef
    conditional_bound: Rational
    unconditional_bound: Rational | None
    unconditional_derivation: UnconditionalDerivation
    conditional_on_effective_molecule_count: StrictBool
    prospective_unconditional_bound: Rational | None
