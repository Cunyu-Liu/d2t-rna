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
