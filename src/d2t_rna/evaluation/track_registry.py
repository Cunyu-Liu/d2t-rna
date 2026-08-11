"""track_registry.py -- Track R / Track C specification + frozen decision registry
(P0-7).

Two complementary evaluation tracks are specified:

* **Track R** (fixed budget): the primary metric is ``randomized_minimax_error``;
  Bayes, abstention, runtime/memory/coverage are secondary.  Every method must
  use the SAME budget.  A method that cannot be executed within the budget must
  be marked ``WITHHELD`` -- it is NEVER substituted with an EIG allocation while
  retaining a T2/deployable label.

* **Track C** (cost minimization to a fixed endpoint): the primary endpoint is a
  common randomized-minimax risk threshold; the information threshold is only a
  separate *surrogate* track and is NOT a substitute for the primary.  All
  comparators must reach the same endpoint.  ``tau=1/2`` is NOT hardcoded for
  all tasks.

The **global primary/endpoint/strongest-comparator decision registry** is FROZEN
BEFORE any development endpoint computation.  Track C is the global default and
frozen PRIMARY track; Track R is secondary.  There is NO post-hoc co-primary,
and the executing agent must not self-switch primary.  A switch of primary to
Track R requires an explicit signed decision record from the user; without one
the code refuses to switch.

Record convention (shared with the rest of the repo): every registry record
carries ``paper_eligible=false`` and ``purpose=DECISION_REGISTRY_OR_METHOD_ROLE``.
"""

from __future__ import annotations

import hashlib
import json
import random
from fractions import Fraction
from typing import Iterable, Optional, Sequence

from d2t_rna.evaluation.method_role import (
    MethodRole,
    OracleRankingError,
    classify_method_role,
)

PURPOSE = "DECISION_REGISTRY_OR_METHOD_ROLE"
PAPER_ELIGIBLE = False

TRACK_C = "TRACK_C"
TRACK_R = "TRACK_R"

# ---- frozen status sentinels (contract) ------------------------------------
TRACK_C_COST_CAP_NOT_REGISTERED = "TRACK_C_COST_CAP_NOT_REGISTERED"
TRACK_C_ENDPOINT_NOT_IDENTIFIABLE = "TRACK_C_ENDPOINT_NOT_IDENTIFIABLE"
MATCHED_COMPARATOR_NOT_IDENTIFIED = "MATCHED_COMPARATOR_NOT_IDENTIFIED"
TRACK_C_PRIMARY_NOT_SWITCHABLE = "TRACK_C_PRIMARY_NOT_SWITCHABLE"

# ===========================================================================
# 1. frozen primary-decision registry
# ===========================================================================

# The canonical primary-decision payload.  These four fields + track_primary
# MUST be fixed before ANY development endpoint computation.
FROZEN_PRIMARY_DECISION: dict = {
    "max_registered_cost": 8,
    "cost_unit": "REGISTERED_SYNTHETIC_ACTION_COST_UNIT",
    "cost_scale": "ABSOLUTE_INTEGER_TOTAL_COST",
    "cost_cap_source": "PRE_OUTCOME_LEGACY_COMMON_UPPER_BUDGET_8",
    "track_primary": TRACK_C,
}

# field order of the canonical deterministic payload
_CANONICAL_FIELD_ORDER = (
    "max_registered_cost",
    "cost_unit",
    "cost_scale",
    "cost_cap_source",
    "track_primary",
)


class TrackCRegistryError(RuntimeError):
    """Base class for fail-closed registry errors.  ``status`` carries the
    frozen sentinel the contract requires consumers to receive."""

    status: str = "TRACK_C_REGISTRY_ERROR"


class TrackCCostCapNotRegistered(TrackCRegistryError):
    status = TRACK_C_COST_CAP_NOT_REGISTERED


class TrackCEndpointNotIdentifiable(TrackCRegistryError):
    status = TRACK_C_ENDPOINT_NOT_IDENTIFIABLE


class MatchedComparatorNotIdentified(TrackCRegistryError):
    status = MATCHED_COMPARATOR_NOT_IDENTIFIED


class TrackCPrimaryNotSwitchable(TrackCRegistryError):
    status = TRACK_C_PRIMARY_NOT_SWITCHABLE


def canonical_primary_payload(decision: Optional[dict] = None) -> str:
    """Deterministic JSON of the five canonical primary-decision fields.

    Raises :class:`TrackCCostCapNotRegistered` if a canonical field is missing.
    """
    d = decision if decision is not None else FROZEN_PRIMARY_DECISION
    payload = {}
    for field in _CANONICAL_FIELD_ORDER:
        if field not in d or d[field] is None:
            raise TrackCCostCapNotRegistered(
                "primary-decision field missing: " + repr(field) + " -> "
                + TRACK_C_COST_CAP_NOT_REGISTERED
            )
        payload[field] = d[field]
    # deterministic, no key reordering
    return json.dumps(payload, sort_keys=False, separators=(",", ":"),
                      ensure_ascii=False)


def cost_cap_hash(decision: Optional[dict] = None) -> str:
    """sha256 of the canonical primary-decision payload."""
    return hashlib.sha256(
        canonical_primary_payload(decision).encode("utf-8")
    ).hexdigest()


def primary_decision(decision: Optional[dict] = None) -> dict:
    """Return the validated, frozen primary-decision payload with its hash.

    Raises :class:`TrackCCostCapNotRegistered` (status
    ``TRACK_C_COST_CAP_NOT_REGISTERED``) if any canonical field is missing, in
    which case the consumer must stop.
    """
    d = decision if decision is not None else FROZEN_PRIMARY_DECISION
    payload = json.loads(canonical_primary_payload(d))
    payload["track_primary"] = d["track_primary"]
    if d["track_primary"] != TRACK_C:
        raise TrackCPrimaryNotSwitchable(
            "frozen primary must be " + TRACK_C + "; got " + repr(d["track_primary"])
        )
    return {
        "schema": "d2t_rna.track_registry.primary_decision.v3",
        "paper_eligible": PAPER_ELIGIBLE,
        "purpose": PURPOSE,
        "track_primary": d["track_primary"],
        "primary_decision": payload,
        "canonical_payload": canonical_primary_payload(d),
        "cost_cap_hash": cost_cap_hash(d),
    }


def require_track_r_switch_decision(signed_decision_record: Optional[dict]) -> None:
    """Refuse a primary switch to Track R without an explicit signed decision.

    ``signed_decision_record`` must be a dict carrying an external signer and a
    binding tree/commit.  Without it we raise :class:`TrackCPrimaryNotSwitchable`.
    """
    if not signed_decision_record:
        raise TrackCPrimaryNotSwitchable(
            "refusing to switch primary to " + TRACK_R + ": no signed decision "
            "record supplied -> " + TRACK_C_PRIMARY_NOT_SWITCHABLE
        )
    signer = (signed_decision_record.get("signer") or "").strip()
    if not signer:
        raise TrackCPrimaryNotSwitchable(
            "signed decision record has no external signer -> "
            + TRACK_C_PRIMARY_NOT_SWITCHABLE
        )
    target = signed_decision_record.get("primary")
    if target != TRACK_R:
        raise TrackCPrimaryNotSwitchable(
            "signed decision does not request " + TRACK_R + " primary -> "
            + TRACK_C_PRIMARY_NOT_SWITCHABLE
        )


# ===========================================================================
# 2. Track R spec helpers (fixed budget, WITHHELD not aliased)
# ===========================================================================

WITHHELD_STATUS = "WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE"


class WithheldAliasError(RuntimeError):
    """Raised when a WITHHELD method is aliased to a solution while keeping a
    T2/deployable label."""


def assert_withheld_not_aliased(
    *,
    method_id: str,
    status: str,
    reported_allocation: Optional[Sequence] = None,
    claimed_solution_label: Optional[str] = None,
) -> None:
    """Fail-closed: a method that cannot run within the fixed budget must be
    marked WITHHELD and must NOT be substituted with, e.g., an EIG allocation
    while still being presented under a T2/deployable label.
    """
    if status == WITHHELD_STATUS:
        if claimed_solution_label is not None and claimed_solution_label in (
            "T2", "DEPLOYABLE", "D2T", "D2T_SOLUTION",
        ):
            raise WithheldAliasError(
                "method " + repr(method_id) + " is " + status + " but is being "
                "presented as solution label " + repr(claimed_solution_label)
                + "; a WITHHELD method must NOT be aliased to a solution"
            )


# ===========================================================================
# 3. Track C endpoint determination (development only)
# ===========================================================================

# pre-fixed threshold grid (contract)
TRACK_C_THRESHOLD_GRID = (
    Fraction(5, 100),
    Fraction(10, 100),
    Fraction(20, 100),
    Fraction(30, 100),
)
TRACK_C_REACH_FRACTION = Fraction(80, 100)


def determine_track_c_endpoint(
    development_families: Sequence[dict],
    threshold_grid: Sequence = TRACK_C_THRESHOLD_GRID,
    reach_fraction: Fraction = TRACK_C_REACH_FRACTION,
) -> dict:
    """Return the SMALLEST randomized-minimax risk threshold that at least
    ``reach_fraction`` of development families can reach at the registered max
    cost, where each family reports the best randomized-minimax achieved by any
    registered method that passes toy parity at that cost.

    ``development_families``: each is ``{"family_id": str,
    "minimax_at_max_cost": Fraction}`` (the deployable-certified best reachable
    value; only development data, never confirmation outcomes).

    Raises :class:`TrackCEndpointNotIdentifiable` (status
    ``TRACK_C_ENDPOINT_NOT_IDENTIFIABLE``) if no candidate threshold satisfies
    the reach requirement; the consumer must then stop and NOT invent a
    threshold or peek at confirmation outcomes.
    """
    if not development_families:
        raise TrackCEndpointNotIdentifiable(
            "no development families supplied -> " + TRACK_C_ENDPOINT_NOT_IDENTIFIABLE
        )
    n_fam = len(development_families)
    fam_vals = {
        fam["family_id"]: Fraction(fam["minimax_at_max_cost"])
        for fam in development_families
    }
    per_threshold = []
    for t in threshold_grid:
        ft = Fraction(t)
        reach = sum(1 for v in fam_vals.values() if v <= ft)
        per_threshold.append(
            {
                "threshold": str(ft),
                "threshold_float": float(ft),
                "n_families_reach": reach,
                "n_families": n_fam,
                "reach_fraction": float(Fraction(reach, n_fam)),
                "reaches_required_fraction": (
                    Fraction(reach, n_fam) >= reach_fraction
                ),
            }
        )
    for row in per_threshold:
        if row["reaches_required_fraction"]:
            chosen = Fraction(row["threshold"])
            return {
                "status": "IDENTIFIED",
                "track_primary": TRACK_C,
                "endpoint": str(chosen),
                "endpoint_float": float(chosen),
                "reach_fraction": str(reach_fraction),
                "n_families": n_fam,
                "threshold_grid": [str(t) for t in threshold_grid],
                "per_threshold": per_threshold,
                "chosen_threshold": row,
            }
    raise TrackCEndpointNotIdentifiable(
        "no grid threshold reaches " + str(reach_fraction) + " of families; "
        "per-threshold reachability: " + str(per_threshold) + " -> "
        + TRACK_C_ENDPOINT_NOT_IDENTIFIABLE
    )


# ===========================================================================
# 4. strongest comparator determination (development only)
# ===========================================================================


def determine_strongest_comparator(
    candidates: Sequence[dict],
    endpoint: Fraction,
    tie_eps: float = 1e-12,
) -> dict:
    """Select the strongest comparator on DEVELOPMENT only.

    A candidate must pass task reduction, the original paper's toy parity, and
    coverage >= 90%, and must reach the chosen endpoint.  Among those, pick the
    one with the lowest family-cluster mean cost; ties within ``tie_eps`` form a
    frozen co-strongest set.

    ``candidates``: each ``{"method_id", "task_reduction": bool,
    "toy_parity": bool, "coverage": float, "reaches_endpoint": bool,
    "family_cluster_mean_cost": float}``.

    Raises :class:`MatchedComparatorNotIdentified` (status
    ``MATCHED_COMPARATOR_NOT_IDENTIFIED``) if no candidate simultaneously
    satisfies the gates.
    """
    eligible = []
    reasons = []
    for c in candidates:
        fails = []
        if not c.get("task_reduction"):
            fails.append("task_reduction")
        if not c.get("toy_parity"):
            fails.append("toy_parity")
        if (c.get("coverage") or 0.0) < 0.90:
            fails.append("coverage<0.90")
        if not c.get("reaches_endpoint"):
            fails.append("reaches_endpoint")
        if fails:
            reasons.append({"method_id": c["method_id"], "failed": fails})
            continue
        eligible.append(c)
    if not eligible:
        raise MatchedComparatorNotIdentified(
            "no comparator passes task_reduction + toy_parity + coverage>=0.90 "
            "+ reaches_endpoint; rejections: " + str(reasons) + " -> "
            + MATCHED_COMPARATOR_NOT_IDENTIFIED
        )
    eligible.sort(key=lambda c: (c["family_cluster_mean_cost"], c["method_id"]))
    best_cost = eligible[0]["family_cluster_mean_cost"]
    co_strongest = [
        c["method_id"]
        for c in eligible
        if abs(c["family_cluster_mean_cost"] - best_cost) <= tie_eps
    ]
    return {
        "status": "IDENTIFIED",
        "track_primary": TRACK_C,
        "endpoint": str(endpoint),
        "strongest_comparator": eligible[0]["method_id"],
        "co_strongest_set": co_strongest,
        "family_cluster_mean_cost": best_cost,
        "eligible_candidates": [c["method_id"] for c in eligible],
        "rejected_candidates": reasons,
    }


# ===========================================================================
# 5. Track C meaningful success (pre-registered criterion)
# ===========================================================================

MIN_FAMILIES_FOR_CI = 5
TRACK_C_SUCCESS_MEDIAN_REDUCTION = Fraction(10, 100)  # >= 10%
TRACK_C_SUCCESS_CI_ALPHA = 0.05  # one-sided 95% lower bound


def _family_cost_reductions(
    d2t_costs: Sequence[Fraction],
    comparator_costs: Sequence[Fraction],
) -> list[float]:
    """Per-family relative cost reduction ``(comp - d2t)/comp`` (>=0 is better)."""
    out = []
    for dc, cc in zip(d2t_costs, comparator_costs):
        if cc <= 0:
            continue
        out.append(float((Fraction(cc) - Fraction(dc)) / Fraction(cc)))
    return out


def _one_sided_lower_ci_bootstrap(
    reductions: Sequence[float],
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 20260811,
) -> float:
    """One-sided 95% lower confidence bound on the mean relative reduction."""
    rng = random.Random(seed)
    n = len(reductions)
    if n == 0:
        return 0.0
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += reductions[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return means[int(alpha * n_boot)]


def track_c_success(
    d2t_costs: Sequence[Fraction],
    comparator_costs: Sequence[Fraction],
    *,
    n_boot: int = 10000,
) -> dict:
    """Pre-registered Track C success criterion.

    Success requires: family-level median relative cost reduction >= 10% AND a
    pre-registered one-sided 95% lower confidence bound on the reduction > 0.
    If a reasonable CI cannot be defined (too few families), only descriptive
    reporting is allowed (no superiority claim, no GO trigger).
    """
    reductions = _family_cost_reductions(d2t_costs, comparator_costs)
    n = len(reductions)
    if n == 0:
        return {
            "status": "DESCRIPTIVE_ONLY",
            "go": False,
            "n_families": 0,
            "median_reduction": None,
            "mean_reduction": None,
            "ci_defined": False,
            "reason": "no family-level cost pairs",
        }
    reductions_sorted = sorted(reductions)
    median = reductions_sorted[n // 2] if n % 2 else (
        (reductions_sorted[n // 2 - 1] + reductions_sorted[n // 2]) / 2.0
    )
    mean = sum(reductions) / n
    if n < MIN_FAMILIES_FOR_CI:
        return {
            "status": "DESCRIPTIVE_ONLY",
            "go": False,
            "n_families": n,
            "median_reduction": median,
            "mean_reduction": mean,
            "ci_defined": False,
            "reason": (
                "only " + str(n) + " families < " + str(MIN_FAMILIES_FOR_CI)
                + "; a one-sided CI cannot be defined defensibly -> descriptive "
                "only, no superiority claim, no GO"
            ),
        }
    ci_lower = _one_sided_lower_ci_bootstrap(reductions, n_boot=n_boot)
    median_ok = median >= float(TRACK_C_SUCCESS_MEDIAN_REDUCTION)
    ci_ok = ci_lower > 0.0
    go = bool(median_ok and ci_ok)
    return {
        "status": "GO" if go else "NOT_GO",
        "go": go,
        "n_families": n,
        "median_reduction": median,
        "mean_reduction": mean,
        "median_ok_ge_0.10": median_ok,
        "one_sided_95_lower_ci": ci_lower,
        "ci_ok_gt_0": ci_ok,
        "ci_defined": True,
        "n_boot": n_boot,
        "criterion": (
            "median relative cost reduction >= 10% AND one-sided 95% lower CI "
            "on reduction > 0"
        ),
    }
