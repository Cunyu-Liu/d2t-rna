"""D2T-RNA v7 §12.3 submission-readiness gate.

Evaluates the eight §12.3 conditions that must *all* hold for the unique
submission-ready terminal state ``READY_FOR_THEORETICAL_RNA_METHODS_SUBMISSION``.

Per the §12.3-6 authority amendment (2026-08-05), condition 6 no longer requires
an add-specific full-matrix replay.  It is replaced by::

    QUALIFIED_RETROSPECTIVE_CASE OR COMPLETE_FAIL_CLOSED_ONLY_AUDIT

where

- ``QUALIFIED_RETROSPECTIVE_CASE``: at least one registered dataset reaches
  ``ESTABLISHED`` (a qualified quantitative retrospective instance); and
- ``COMPLETE_FAIL_CLOSED_ONLY_AUDIT``: every registered dataset is audited and
  reported with a documented terminal outcome (``ESTABLISHED`` /
  ``NOT_APPLICABLE`` / ``NOT_COMPARABLE_BY_*`` / ``NOT_ESTABLISHED``) and no
  dataset is left un-audited.

This is a *gate-preserving* change: it does not weaken the requirement that the
retrospective evidence be audited and reported (contract §8.4), it only removes
the add-specific hard requirement that is structurally impossible under a
continuous (non-categorical) observation modality.  T2 theorem readiness
remains independent of add / SAM-III / RORC eligibility (contract §12.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

ESTABLISHED = "ESTABLISHED"
NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL = (
    "NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL"
)
NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE = (
    "NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE"
)
NOT_ESTABLISHED = "NOT_ESTABLISHED"

# Every audit-supplied terminal outcome counts as a documented fail-closed (or
# qualified) case.  A dataset may not be silently omitted.
_TERMINAL_OUTCOMES = frozenset(
    {
        ESTABLISHED,
        NOT_APPLICABLE,
        NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL,
        NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE,
        NOT_ESTABLISHED,
    }
)

QUALIFIED_RETROSPECTIVE_CASE = "QUALIFIED_RETROSPECTIVE_CASE"
COMPLETE_FAIL_CLOSED_ONLY_AUDIT = "COMPLETE_FAIL_CLOSED_ONLY_AUDIT"

SUBMISSION_READY = "READY_FOR_THEORETICAL_RNA_METHODS_SUBMISSION"


@dataclass(frozen=True)
class SubmissionGateResult:
    """Result of the §12.3 submission-readiness evaluation."""

    conditions: dict[str, bool] = field(default_factory=dict)
    condition_6_mode: str | None = None
    submission_ready: bool = False
    gate_state: str = "NOT_SUBMISSION_READY"
    certificate_guard: str = "NOT_ESTABLISHED"
    scientific_claim_authorized: bool = False

    def as_dict(self) -> dict:
        return {
            "conditions": dict(self.conditions),
            "condition_6_mode": self.condition_6_mode,
            "submission_ready": self.submission_ready,
            "gate_state": self.gate_state,
            "certificate_guard": self.certificate_guard,
            "scientific_claim_authorized": self.scientific_claim_authorized,
        }


def _condition_6(
    r2_outcomes: Sequence[str], r2_audited: bool
) -> tuple[bool, str | None]:
    """Evaluate the amended §12.3-6 condition.

    Returns ``(pass, mode)`` where ``mode`` is the satisfied branch
    (``QUALIFIED_RETROSPECTIVE_CASE`` or ``COMPLETE_FAIL_CLOSED_ONLY_AUDIT``) or
    ``None`` when neither branch holds.
    """
    if not r2_audited:
        return False, None
    if any(o == ESTABLISHED for o in r2_outcomes):
        return True, QUALIFIED_RETROSPECTIVE_CASE
    if r2_outcomes and all(o in _TERMINAL_OUTCOMES for o in r2_outcomes):
        return True, COMPLETE_FAIL_CLOSED_ONLY_AUDIT
    return False, None


def evaluate_submission_gate(
    *,
    task5_closure_complete: bool,
    t2b_exact_collision_separation: bool,
    t2c_finite_sample: bool,
    executable_certificate: bool,
    oracle_baselines_misspecification_pass: bool,
    r2_outcomes: Sequence[str],
    r2_audited: bool,
    data_role_dependency_claim_audit_pass: bool,
    reproducible: bool,
) -> SubmissionGateResult:
    """Evaluate the eight §12.3 conditions (condition 6 amended).

    ``r2_outcomes`` is the per-dataset terminal outcome from the R2 report, and
    ``r2_audited`` is True when every registered dataset was audited and reported
    (no dataset omitted).  All eight conditions must hold for the submission-ready
    state.  ``scientific_claim_authorized`` stays False: this is an internal
    evidence gate, not a publication-success claim.
    """
    cond_6, mode = _condition_6(r2_outcomes, r2_audited)
    conditions = {
        "task5_closure_complete": task5_closure_complete,
        "t2b_exact_collision_separation": t2b_exact_collision_separation,
        "t2c_finite_sample": t2c_finite_sample,
        "executable_certificate": executable_certificate,
        "oracle_baselines_misspecification_pass": oracle_baselines_misspecification_pass,
        "retrospective_qualified_or_complete_fail_closed": cond_6,
        "data_role_dependency_claim_audit_pass": data_role_dependency_claim_audit_pass,
        "reproducible": reproducible,
    }
    all_pass = all(conditions.values())
    return SubmissionGateResult(
        conditions=conditions,
        condition_6_mode=mode,
        submission_ready=all_pass,
        gate_state=SUBMISSION_READY if all_pass else "NOT_SUBMISSION_READY",
        certificate_guard="ESTABLISHED" if all_pass else "NOT_ESTABLISHED",
        scientific_claim_authorized=False,
    )