"""Fail-closed real-data qualification for the measured RNA cases (plan Batch 3).

The v7 audit (2026-08-07, 2026-08-09 handover) established that the measured
add / glycine / miniTTR / SAM-III cases treat ``p = clamp(normalized_reactivity,
1/100, 99/100)`` as if it were an independent Bernoulli probability, while the
provenance claimed ``per_position_error_used=True``.  No RDAT/GEO archive
carries per-replicate raw counts; the profiles were historically exposed (they
selected the probe and determined ``n``).  RORC has no official accession.

This module encodes a *fail-closed* qualification verdict per data domain and
the aggregate real-data route, following plan Batch 3 (Sections 3.1-3.7):

  * verdict per domain is one of QUALIFIED / BLOCKED_PENDING_ARCHIVE_QUALIFICATION
    / DESCRIPTIVE_ONLY / INELIGIBLE (never a fuzzy "partially passed");
  * ``per_position_error_used`` is machine-derived from whether the observation
    model actually consumes per-position error, never hand-written;
  * the aggregate REAL_DATA_ROUTE is BLOCKED unless every requirement in
    Section 3.7 (raw per-unit counts, independent-unit crosswalk, calibrated
    likelihood, executable action, real marginal cost) holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

# --- closed status vocabulary (plan Batch 3.7) ------------------------------

DATA_QUALIFIED = "QUALIFIED"
DATA_BLOCKED_ARCHIVE = "BLOCKED_PENDING_ARCHIVE_QUALIFICATION"
DATA_DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
DATA_INELIGIBLE = "INELIGIBLE"

DATA_ROLE_DEVELOPMENT = "development"
DATA_ROLE_SELECTION_EXPOSED = "selection_exposed"
DATA_ROLE_POST_SELECTION_DIAGNOSTIC = "post_selection_diagnostic"
DATA_ROLE_SEALED_CONFIRMATION = "sealed_confirmation"

# Data role names that may NOT be applied to an already-exposed profile
# (plan Batch 3.5).  Renaming an exposed profile to one of these does not
# restore held-out status.
_FORBIDDEN_RENAMES = (
    "held-out",
    "test",
    "independent validation",
    "prospective",
    "blinded",
)

# Units that are NOT independent statistical units (plan Batch 3.5).
_NON_INDEPENDENT_UNITS = (
    "position",
    "read",
    "seed",
    "budget_cell",
    "cost_cell",
    "technical_repeat",
    "action_draw",
)


class QualificationVerdict(str, Enum):
    QUALIFIED = DATA_QUALIFIED
    BLOCKED_PENDING_ARCHIVE_QUALIFICATION = DATA_BLOCKED_ARCHIVE
    DESCRIPTIVE_ONLY = DATA_DESCRIPTIVE_ONLY
    INELIGIBLE = DATA_INELIGIBLE


class ExposureRole(str, Enum):
    DEVELOPMENT = DATA_ROLE_DEVELOPMENT
    SELECTION_EXPOSED = DATA_ROLE_SELECTION_EXPOSED
    POST_SELECTION_DIAGNOSTIC = DATA_ROLE_POST_SELECTION_DIAGNOSTIC
    SEALED_CONFIRMATION = DATA_ROLE_SEALED_CONFIRMATION


@dataclass(frozen=True)
class DataQualification:
    """A fail-closed qualification record for one data domain (Batch 3)."""

    dataset_id: str
    accessions: tuple[str, ...]
    verdict: str
    raw_per_replicate_counts_available: bool
    independent_unit_crosswalk: bool
    calibrated_likelihood: bool
    executable_action: bool
    real_marginal_cost: bool
    per_position_error_used: bool
    exposure_role: str
    reasons: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    # --- fail-closed aggregation ------------------------------------------
    @property
    def real_route_requirements_met(self) -> bool:
        """Every Batch 3.7 requirement must hold for the real route to open."""
        return all(
            (
                self.raw_per_replicate_counts_available,
                self.independent_unit_crosswalk,
                self.calibrated_likelihood,
                self.executable_action,
                self.real_marginal_cost,
            )
        )


@dataclass(frozen=True)
class DataRouteDecision:
    """Aggregate real-data route across all candidate data domains."""

    route: str
    qualified_domains: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def any_qualified(self) -> bool:
        return bool(self.qualified_domains)


REAL_DATA_ROUTE_BLOCKED = "BLOCKED"
REAL_DATA_ROUTE_BLOCKED_PENDING_ARCHIVE = (
    "BLOCKED_PENDING_ARCHIVE_QUALIFICATION"
)
REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA = "TERMINATED_FOR_CURRENT_DATA"


def machine_derived_per_position_error_used(*, model_consumes_error: bool) -> bool:
    """Derive the ``per_position_error_used`` flag from what the observation
    model actually does, never from a hand-written provenance string.

    The audit found provenance claiming ``per_position_error_used=True`` while
    the clamp likelihood never consumed per-position error.  Callers must pass
    ``model_consumes_error`` from the real execution path (whether the fitted
    likelihood reads per-position standard error); a False here makes the
    domain DESCRIPTIVE_ONLY for that dimension.
    """
    return bool(model_consumes_error)


def forbidden_claim_renames(role: str) -> tuple[str, ...]:
    """Claims/roles that cannot be asserted for an exposed profile."""
    if role == DATA_ROLE_SELECTION_EXPOSED:
        return tuple(_FORBIDDEN_RENAMES)
    return ()


def aggregate_real_data_route(
    qualifications: Sequence[DataQualification],
) -> DataRouteDecision:
    """Aggregate the per-domain verdicts into a single fail-closed route.

    * If at least one domain is QUALIFIED (all 3.7 requirements met) the route
      is open for that domain (caller decides further); here we keep it
      fail-closed and require explicit handling.
    * If no domain is QUALIFIED, the route is BLOCKED.
    * Every domain is BLOCKED_PENDING_ARCHIVE_QUALIFICATION if they are
      descriptive-only / blocked but not ineligible; if all are ineligible the
      route is TERMINATED_FOR_CURRENT_DATA.
    """
    qualified = [q.dataset_id for q in qualifications if q.verdict == DATA_QUALIFIED]
    ineligible = [q.dataset_id for q in qualifications if q.verdict == DATA_INELIGIBLE]
    all_domains = [q.dataset_id for q in qualifications]
    non_ineligible = [d for d in all_domains if d not in ineligible]

    if qualified:
        return DataRouteDecision(
            route="OPEN_FOR_QUALIFIED_DOMAINS",
            qualified_domains=tuple(qualified),
            blocked_domains=tuple(d for d in all_domains if d not in qualified),
            reasons=(
                "one or more domains qualified; real quantitative route is "
                "open only for the qualified domains",
            ),
        )
    if not non_ineligible:
        return DataRouteDecision(
            route=REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA,
            qualified_domains=(),
            blocked_domains=tuple(ineligible),
            reasons=(
                "all candidate domains are INELIGIBLE; no raw per-unit counts, "
                "independent units, calibrated likelihood, action or cost exist",
            ),
        )
    return DataRouteDecision(
        route=REAL_DATA_ROUTE_BLOCKED_PENDING_ARCHIVE,
        qualified_domains=(),
        blocked_domains=tuple(non_ineligible),
        reasons=(
            "no domain met all Batch 3.7 real-route requirements; "
            "BLOCKED_PENDING_ARCHIVE_QUALIFICATION",
        ),
    )


# ===========================================================================
# P0-8: v3 seven-scope data-qualification recheck (corrected rules)
#
# The P0-8 audit recheck applies six known corrections on top of the v2
# fail-closed qualification layer.  It records one qualification record per
# *scope* (not per dataset) across seven scopes, using a closed v3 verdict
# vocabulary and a fail-closed aggregate real-data route.
# ===========================================================================

# --- v3 closed verdict vocabulary -----------------------------------------
V3_GO = "GO"
V3_CONDITIONAL = "CONDITIONAL"
V3_TERMINATED_FOR_CURRENT_DATA = "TERMINATED_FOR_CURRENT_DATA"
V3_UNKNOWN_NOT_ASSERTED = "UNKNOWN_NOT_ASSERTED"

V3_VERDICT_VOCABULARY = frozenset(
    {
        V3_GO,
        V3_CONDITIONAL,
        V3_TERMINATED_FOR_CURRENT_DATA,
        V3_UNKNOWN_NOT_ASSERTED,
    }
)

# Correction 2: the three ADD scopes are each their own independent statistical
# unit and MUST NEVER be merged into a single unit.
ADD_SCOPES_NEVER_MERGED = ("ADD71_STD_0001", "ADDAPO_DCP_0000", "ADDRSW_SHP_0003")

# The eight atomic real-data criteria that must ALL be simultaneously satisfied
# for the real-data route to be open (fail-closed aggregate, correction 6).
REAL_DATA_ATOMIC_CRITERIA = (
    "raw_counts",
    "exact_filename_and_hash",
    "source_url_and_retrieval_date",
    "verified_license_text",
    "independent_unit_dag",
    "executable_action",
    "real_marginal_cost",
    "calibrated_likelihood",
)

# Global aggregate state for the current data holdings.  It stays
# TERMINATED_FOR_CURRENT_DATA until ALL eight atomic real-data criteria are
# simultaneously satisfied (they are not; see v7_data_qualification_v3.json).
REAL_DATA_ROUTE = REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA


@dataclass(frozen=True)
class DataQualificationV3:
    """A P0-8 fail-closed qualification record for one scope (v3 schema).

    Verdict is from the closed v3 vocabulary; fail-closed evidence (raw counts,
    executable action, real marginal cost, verified license, independent-unit
    DAG, calibrated likelihood) is carried as booleans so the aggregate route
    can be derived mechanically and never hand-written.
    """

    schema_id: str
    schema_version: str
    scope_id: str
    purpose: str
    paper_eligible: bool
    accession: str
    exact_filename: str
    hash_sha256: str
    source_url: str
    retrieval_date: str
    license_text: str
    license_version: str
    license_receipt: str
    raw_counts_present: bool
    raw_counts: str
    depth: str
    biological_replicate_crosswalk: str
    technical_replicate_crosswalk: str
    merge_history: str
    normalization_history: str
    missingness: str
    error_fields: str
    per_position_error_used_by_likelihood: bool
    historical_exposure: str
    independent_unit: str
    dependency_dag: str
    action_executable: bool
    real_marginal_cost: bool
    calibrated_likelihood: bool
    selection_diagnostic_confirmation_role: str
    verdict: str
    corrections_applied: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    @property
    def fail_closed_evidence_missing(self) -> tuple[str, ...]:
        """Correction 6: raw counts / executable action / real marginal cost."""
        missing: list[str] = []
        if not self.raw_counts_present:
            missing.append("raw_counts")
        if not self.action_executable:
            missing.append("executable_action")
        if not self.real_marginal_cost:
            missing.append("real_marginal_cost")
        return tuple(missing)

    @property
    def real_data_atomic_criteria_met(self) -> bool:
        """True iff ALL eight atomic real-data criteria hold for this scope."""
        return all(
            (
                self.raw_counts_present,
                bool(self.exact_filename and self.hash_sha256),
                bool(self.source_url and self.retrieval_date),
                bool(self.license_receipt == "VERIFIED"),
                bool(self.independent_unit and self.dependency_dag),
                self.action_executable,
                self.real_marginal_cost,
                self.calibrated_likelihood,
            )
        )


# --- corrected-rule helpers (P0-8) ----------------------------------------


def add_scopes_never_merged(unit_accessions: Sequence[str]) -> bool:
    """Correction 2: a single independent statistical unit may contain at most
    one of the three ADD scope accessions; the ADD scopes must never be merged
    into one unit.  Returns True iff no merge is present."""
    hits = [a for a in ADD_SCOPES_NEVER_MERGED if a in unit_accessions]
    return len(hits) <= 1


def license_requires_verified_text(
    *,
    publicly_downloadable: bool,
    verified_license_receipt: bool,
) -> bool:
    """Correction 3: public / accessibility is NOT the same as a license.  A
    scope counts as licensed only when a verified license text/receipt exists,
    never merely because it is publicly downloadable."""
    return bool(verified_license_receipt)


def classify_sample_kind(*, claimed_as: str) -> str:
    """Correction 4: classify a sample-size number by its true kind.  Count
    depth (e.g. Phase2 Bernoulli sensitivity n=9806/1565/388/93/39 reads per
    condition) is count depth, NOT biological replicate N; only a value whose
    kind is actually biological replicates may be reported as biological N."""
    if claimed_as == "biological_replicates":
        return "BIOLOGICAL_N"
    if claimed_as == "count_depth":
        return "COUNT_DEPTH"
    return "UNKNOWN"


def constructed_identical_positions_role(*, constructed: bool) -> str:
    """Correction 5: constructed identical positions are only a zero-separation
    control-flow test, not real data."""
    if constructed:
        return "ZERO_SEPARATION_CONTROL_FLOW_ONLY"
    return "REAL_DATA"


def fail_closed_v3_verdict(
    *,
    raw_counts_present: bool,
    executable_action: bool,
    real_marginal_cost: bool,
) -> str:
    """Correction 6: if any of raw counts / executable action / real marginal
    cost is missing, the scope is TERMINATED_FOR_CURRENT_DATA (fail-closed)."""
    if not (raw_counts_present and executable_action and real_marginal_cost):
        return V3_TERMINATED_FOR_CURRENT_DATA
    return V3_CONDITIONAL  # GO additionally requires all eight atomic criteria


def aggregate_real_data_route_v3(
    records: Sequence[DataQualificationV3],
) -> dict:
    """P0-8 aggregate real-data route (fail-closed).  The route stays
    TERMINATED_FOR_CURRENT_DATA unless some scope satisfies ALL eight atomic
    real-data criteria simultaneously (none do on the current holdings)."""
    verdicts = [r.verdict for r in records]
    satisfying = [
        r.scope_id for r in records if r.real_data_atomic_criteria_met
    ]
    if all(v == V3_TERMINATED_FOR_CURRENT_DATA for v in verdicts):
        return {
            "route": REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA,
            "open": False,
            "satisfying_scopes": [],
            "reason": (
                "all seven scopes fail-closed (missing raw counts, executable "
                "action, and/or real marginal cost); no scope meets all eight "
                "atomic real-data criteria"
            ),
        }
    if satisfying:
        return {
            "route": "OPEN_FOR_SATISFYING_SCOPES",
            "open": True,
            "satisfying_scopes": satisfying,
            "reason": "at least one scope satisfies all eight atomic real-data criteria",
        }
    return {
        "route": REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA,
        "open": False,
        "satisfying_scopes": [],
        "reason": (
            "no scope is GO; remaining scopes do not satisfy all eight atomic "
            "real-data criteria"
        ),
    }
