"""Conditional Phase 2 (plan §P2): real-data route protocol & terminal decision.

The v7 audit (2026-08-09) and the per-domain data-qualification v2 manifests
establish that no candidate measured domain (add / glycine / miniTTR / SAM-III
/ RORC) is QUALIFIED: the archives carry only merged, normalized reactivity;
no per-replicate raw counts, independent-unit crosswalk, calibrated count
likelihood, executable action, or real marginal cost exist; and every measured
profile is selection-exposed (the same outcome profile selected the probe and
determined ``n``).

Per plan §P2 we therefore pre-register the *protocol* that would be required
for a future qualified archive (independent-unit DAG, count likelihood,
calibration, action registry, cost receipt, delta_min, power/precision,
multiplicity, QC/exclusion, sealed confirmation) and record the honest
terminal decision for the current data holdings:

    REAL_DATA_ROUTE = TERMINATED_FOR_CURRENT_DATA

No new data is acquired here (plan rule 11 requires separate authorization).
No normalized-clamp-as-Bernoulli bypass is permitted.

The output manifest is deterministic: it binds the SHA-256 of every input
per-domain qualification manifest and computes deterministic analytic
power / delta_min values (no Monte-Carlo noise, fixed formulas).  Timestamps /
hostname live only in the receipt outer layer, never in the canonical payload.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

from scipy.stats import norm

from d2t_rna.data.qualification import (
    DataQualification,
    REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA,
    aggregate_real_data_route,
)

# ---------------------------------------------------------------------------
# vocabulary / status vocabulary (fail-closed)
# ---------------------------------------------------------------------------

PROTOCOL_SPEC = "PRE_REGISTERED_SPEC"
PROTOCOL_NOT_FITTABLE = "PRE_REGISTERED_SPEC_NOT_FITTABLE_ON_CURRENT_DATA"
PROTOCOL_NOT_EXECUTABLE = "PRE_REGISTERED_SPEC_NOT_EXECUTABLE"
PROTOCOL_EMPTY_UNTIL_QUALIFIED = "PRE_REGISTERED_SPEC_EMPTY_UNTIL_QUALIFIED_ARCHIVE"
PROTOCOL_REAL_COST_UNAVAILABLE = "PRE_REGISTERED_SPEC_REAL_COST_UNAVAILABLE"

ACQUISITION_NO_GO = "NO_GO_FOR_CURRENT_DATA"

PIVOT_SYNTHETIC_SOFTWARE = "SYNTHETIC_SOFTWARE_PAPER"

# The plan requires: REAL_DATA_ROUTE = TERMINATED_FOR_CURRENT_DATA when the
# archive still (仍) lacks raw counts / independent units / real action / cost.
TERMINAL_ROUTE = REAL_DATA_ROUTE_TERMINATED_FOR_CURRENT_DATA

# ---------------------------------------------------------------------------
# deterministic analytic power (two independent proportions, pooled H0 var.)
# ---------------------------------------------------------------------------


def _z(quantile: float) -> float:
    return float(norm.ppf(quantile))


def required_n_per_condition(
    delta: float,
    p0: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Replicates per condition (n) to detect ``delta = p1 - p0`` with the
    registered within-replicate count likelihood, using a two-sample
    independent-proportion normal approximation (pooled variance under H0).

    Returns the smallest integer n achieving the target power.
    """
    if not (0.0 < delta < 1.0 - p0):
        raise ValueError(f"delta={delta!r} outside (0, 1-p0)")
    p1 = p0 + delta
    pbar = (p0 + p1) / 2.0
    z_alpha = _z(1.0 - alpha / 2.0)
    z_beta = _z(power)
    num = z_alpha * math.sqrt(2.0 * pbar * (1.0 - pbar)) + z_beta * math.sqrt(
        p1 * (1.0 - p1) + p0 * (1.0 - p0)
    )
    return int(math.ceil(num * num / (delta * delta)))


def delta_min_at_n(
    n: int,
    p0: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Smallest |p1-p0| resolvable with ``n`` replicates per condition, by
    bisecting the (monotone) required-n power curve.

    Evaluated at ``p0 = 0.5`` (max variance) so the value is a conservative
    upper bound on the true delta_min for interior probabilities.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    lo, hi = 1e-9, 1.0 - p0 - 1e-9
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if required_n_per_condition(mid, p0, alpha, power) <= n:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


# ---------------------------------------------------------------------------
# manifest loading
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text())


def load_qualification_v2_manifests(manifests_dir: Path) -> list[DataQualification]:
    """Load every ``*_qualification_v2.json`` manifest into fail-closed
    :class:`DataQualification` records, recording each manifest's SHA-256."""
    if not manifests_dir.is_dir():
        raise FileNotFoundError(f"no qualification manifests dir: {manifests_dir}")
    out: list[DataQualification] = []
    for p in sorted(manifests_dir.glob("*_qualification_v2.json")):
        m = _load_manifest(p)
        out.append(
            DataQualification(
                dataset_id=m["dataset_id"],
                accessions=tuple(m.get("accessions", ())),
                verdict=m["verdict"],
                raw_per_replicate_counts_available=bool(
                    m.get("raw_per_replicate_counts_available", False)
                ),
                independent_unit_crosswalk=bool(
                    m.get("independent_unit_crosswalk", False)
                ),
                calibrated_likelihood=bool(m.get("calibrated_likelihood", False)),
                executable_action=bool(m.get("executable_action", False)),
                real_marginal_cost=bool(m.get("real_marginal_cost", False)),
                per_position_error_used=bool(m.get("per_position_error_used", False)),
                exposure_role=m.get("exposure_role", ""),
                reasons=tuple(m.get("reasons", ())),
                forbidden_claims=tuple(m.get("forbidden_claims", ())),
                sources=tuple(m.get("sources", ())),
            )
        )
    if not out:
        raise ValueError("no *_qualification_v2.json manifests found")
    return out


# ---------------------------------------------------------------------------
# protocol elements
# ---------------------------------------------------------------------------


def _independent_unit_dag() -> dict:
    return {
        "element": "independent_unit_dag",
        "statistical_unit": "independent biological block (construct-library-assay replicate)",
        "nodes": [
            "construct_library",
            "biological_replicate",
            "assay_condition",
            "count_measurement",
            "action",
            "cost",
        ],
        "edges": [
            "construct_library -> biological_replicate",
            "biological_replicate -> assay_condition",
            "assay_condition -> count_measurement",
            "count_measurement -> action",
            "action -> cost",
        ],
        "not_independent_units": [
            "position",
            "read",
            "seed",
            "budget_cell",
            "cost_cell",
            "technical_repeat",
            "action_draw",
        ],
        "status": f"{PROTOCOL_SPEC}_NEEDS_QUALIFIED_ARCHIVE",
    }


def _count_likelihood() -> dict:
    return {
        "element": "count_likelihood",
        "model": (
            "WithinReplicateCountModel: per-replicate binomial (k,n) reactive "
            "reads per position/condition; optional beta-binomial for "
            "overdispersion"
        ),
        "requires": ["per_replicate_raw_counts"],
        "current_availability": "NO_CANDIDATE_ARCHIVE_STORES_PER_REPLICATE_RAW_COUNTS",
        "status": PROTOCOL_NOT_FITTABLE,
    }


def _calibration_protocol() -> dict:
    return {
        "element": "calibration_protocol",
        "approach": (
            "per-position, over-replicate calibration of the count likelihood "
            "on a cold diagnostic replicate that was NOT used for probe "
            "selection or n determination"
        ),
        "requires": ["cold_diagnostic_replicate"],
        "current_availability": (
            "NO_COLD_REPLICATE_ALL_MEASURED_PROFILES_ARE_SELECTION_EXPOSED"
        ),
        "status": PROTOCOL_NOT_EXECUTABLE,
    }


def _action_registry() -> dict:
    return {
        "element": "action_registry",
        "registered_real_actions": [],
        "note": (
            "no executable real (wet-lab) action is registered; all current "
            "actions are synthetic-catalog objects, model-conditional only"
        ),
        "status": PROTOCOL_EMPTY_UNTIL_QUALIFIED,
    }


def _cost_receipt() -> dict:
    return {
        "element": "cost_receipt",
        "registered_real_marginal_cost": False,
        "note": (
            "no real wet-lab marginal cost receipt exists; synthetic "
            "costed-design costs are model-conditional only"
        ),
        "status": PROTOCOL_REAL_COST_UNAVAILABLE,
    }


def _power_precision(historical_n: Sequence[tuple[str, int]]) -> dict:
    """Deterministic analytic power table + historical-n delta_min report."""
    alpha, power = 0.05, 0.8
    deltas = [0.02, 0.05, 0.10, 0.20, 0.30]
    table = [
        {"delta": d, "n_per_condition": required_n_per_condition(d, alpha=alpha, power=power)}
        for d in deltas
    ]
    historical = [
        {
            "case": cid,
            "n_claimed": n,
            "delta_min_at_n": round(delta_min_at_n(n, alpha=alpha, power=power), 4),
        }
        for cid, n in historical_n
    ]
    return {
        "element": "power_precision_simulation",
        "alpha": alpha,
        "target_power": power,
        "reference_p0": 0.5,
        "method": (
            "two-sample independent-proportion normal approximation, pooled "
            "H0 variance, at max-variance p0=0.5 (conservative)"
        ),
        "required_n_by_delta": table,
        "historical_n_delta_min": historical,
        "note": (
            "analytic/deterministic; no Monte-Carlo noise. At the historical "
            "claimed sample sizes the resolvable delta_min is very large, "
            "consistent with the audit finding that the n=3/15/3 real-repeat "
            "claims are unsupported and not independently confirmable."
        ),
        "status": "DETERMINISTIC_ANALYTIC",
    }


def _multiplicity() -> dict:
    return {
        "element": "multiplicity_control",
        "control": (
            "pre-register the finite probe/rule set; family-wise control over "
            "the registered action set; do not cherry-pick post hoc"
        ),
        "sealed_confirmation": "sealed test families pre-registered (see P1-6.1)",
        "status": "PRE_REGISTERED_SPEC",
    }


def _qc_exclusion() -> dict:
    return {
        "element": "qc_exclusion",
        "criteria": (
            "pre-registered read-depth floor per replicate, contamination/QC "
            "flags, and exclusion criteria fixed BEFORE sealed confirmation; "
            "no post hoc removal of disagreeing replicates"
        ),
        "status": "PRE_REGISTERED_SPEC",
    }


def _sealed_confirmation() -> dict:
    return {
        "element": "sealed_confirmation_protocol",
        "protocol": (
            "acquire fresh biological replicates on a sealed, pre-registered "
            "probe/rule set that was never exposed to selection or n "
            "determination; frozen likelihood, action, cost, and decision "
            "rule; only then fit the count likelihood and confirm"
        ),
        "requires": ["fresh_unexposed_replicates", "sealed_protocol", "separate_authorization"],
        "current_availability": "NO_FRESH_DATA_ACQUISITION_AUTHORIZED",
        "status": PROTOCOL_NOT_EXECUTABLE,
    }


# ---------------------------------------------------------------------------
# top-level build
# ---------------------------------------------------------------------------


def build_phase2_protocol(
    manifests_dir: Path,
    *,
    head: str = "",
    historical_n: Sequence[tuple[str, int]] | None = None,
) -> dict:
    """Build the deterministic Phase 2 protocol manifest.

    ``historical_n`` lists ``(case, n_claimed)`` pairs used to report the
    resolvable delta_min at the historical claimed sample sizes.
    """
    quals = load_qualification_v2_manifests(manifests_dir)

    # input SHAs (bound to the canonical payload so the manifest is traceable)
    input_shas = {
        p.name: _file_sha256(p) for p in sorted(manifests_dir.glob("*_qualification_v2.json"))
    }

    route = aggregate_real_data_route(quals)

    domains = [
        {
            "dataset_id": q.dataset_id,
            "verdict": q.verdict,
            "exposure_role": q.exposure_role,
            "raw_per_replicate_counts_available": q.raw_per_replicate_counts_available,
            "independent_unit_crosswalk": q.independent_unit_crosswalk,
            "calibrated_likelihood": q.calibrated_likelihood,
            "executable_action": q.executable_action,
            "real_marginal_cost": q.real_marginal_cost,
            "real_route_requirements_met": q.real_route_requirements_met,
        }
        for q in quals
    ]

    if historical_n is None:
        historical_n = [("add/miniTTR", 3), ("glycine", 15), ("SAM-III", 3)]

    protocol = {
        "independent_unit_dag": _independent_unit_dag(),
        "count_likelihood": _count_likelihood(),
        "calibration_protocol": _calibration_protocol(),
        "action_registry": _action_registry(),
        "cost_receipt": _cost_receipt(),
        "delta_min": {
            "element": "delta_min",
            "definition": (
                "minimum |p1-p0| (between-condition reactive-read probability "
                "difference) detectable by the registered count likelihood at "
                "target alpha/power"
            ),
            "power_precision": _power_precision(historical_n),
        },
        "power_precision_simulation": _power_precision(historical_n),
        "multiplicity_control": _multiplicity(),
        "qc_exclusion": _qc_exclusion(),
        "sealed_confirmation_protocol": _sealed_confirmation(),
    }

    return {
        "schema": "d2t_rna.v7_phase2_protocol.v1",
        "phase": "P2",
        "head": head,
        "real_data_route_for_current_data": TERMINAL_ROUTE,
        "aggregate_route_from_qualification_layer": route.route,
        "route_detail": (
            "No candidate domain is QUALIFIED; all current archives lack "
            "per-replicate raw counts, independent-unit crosswalk, calibrated "
            "count likelihood, executable action, and real marginal cost, and "
            "all measured profiles are selection-exposed. Per plan §P2 the "
            "current-data route is TERMINATED_FOR_CURRENT_DATA; the paper "
            "pivots to a synthetic/software methods paper. No "
            "normalized-clamp-as-Bernoulli bypass is permitted."
        ),
        "qualified_domains": list(route.qualified_domains),
        "blocked_domains": list(route.blocked_domains),
        "domains": domains,
        "protocol": protocol,
        "acquisition": {
            "decision": ACQUISITION_NO_GO,
            "real_data_route_for_current_data": TERMINAL_ROUTE,
            "go_conditions": [
                "a candidate archive carrying per-replicate raw counts arrives",
                "independent biological-block crosswalk is registered",
                "calibrated count likelihood is fittable on a cold replicate",
                "an executable real action and real marginal cost receipt are registered",
                "separate acquisition authorization is granted (plan rule 11)",
            ],
            "authorization_required": True,
        },
        "pivot": PIVOT_SYNTHETIC_SOFTWARE,
        "forbidden_practices": [
            "clamp(normalized_reactivity) treated as an independent Bernoulli parameter",
            "per_position_error_used=True without the model consuming per-position error",
            "n=3/15/3 real-repeat or independent-validation claims",
            "real gamma / wet-lab-cost-saving / cross-system-transfer claims",
        ],
        "input_manifests_sha256": input_shas,
    }
