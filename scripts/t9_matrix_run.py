"""D2T-RNA v7 §9 evaluation-matrix acceptance runner.

Executes the §9.1 microcase fixtures, the §9.1 exhaustive-oracle vs certified
T2c-bounds cross-validation, and the §9.3 actual execution of every baseline
under one common experiment spec, then writes an auditable JSON report.

Contract §9.1 / §9.2 / §9.3.  Every baseline is *actually executed* (never a
bare wrapper); a baseline whose allocation was not produced is flagged
``BASELINE_NOT_EXECUTION_VERIFIED``.  This is model-conditional synthetic
evaluation only; it authorizes no scientific claim.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from fractions import Fraction

from d2t_rna.evaluation.matrix import (
    ExperimentSpec,
    build_matrix_report,
    cross_validate_single_pair,
    microcase_fixtures,
)

# One common, auditable experiment spec reused across microcases: unit action
# costs, a positive budget, and the no-abstention minimax decision rule.
_BUDGET = Fraction(8)
_COST = Fraction(1)


def _frac_to_str(x) -> str:
    if isinstance(x, Fraction):
        return str(x)
    return repr(x)


def _serialize_report(report) -> dict:
    return {
        "model_name": report.model_name,
        "spec_p0": [_frac_to_str(x) for x in report.spec.p0],
        "spec_p1": [_frac_to_str(x) for x in report.spec.p1],
        "budget": _frac_to_str(report.spec.budget),
        "replay_sha256": report.replay_sha256(),
        "baselines": {
            method: {
                "allocation": list(run.allocation),
                "cost": _frac_to_str(run.cost),
                "spent_exceeds_budget": run.spent_exceeds_budget,
                "runtime_s": round(run.runtime_s, 6),
                "memory_peak_bytes": run.memory,
                "executed": run.executed,
                "verification_flag": (
                    "EXECUTED" if run.executed else "BASELINE_NOT_EXECUTION_VERIFIED"
                ),
                "oracle": {
                    "cost": _frac_to_str(run.oracle.cost) if run.oracle else None,
                    "minimax_error": (
                        _frac_to_str(run.oracle.minimax_error) if run.oracle else None
                    ),
                    "correct_decl": (
                        _frac_to_str(run.oracle.correct_decl) if run.oracle else None
                    ),
                    "abstain": _frac_to_str(run.oracle.abstain) if run.oracle else None,
                    "product_tv": (
                        _frac_to_str(run.oracle.product_tv) if run.oracle else None
                    ),
                    "outcome_count": run.oracle.outcome_count if run.oracle else None,
                },
                "lp_lower_bound": _frac_to_str(run.lp_lower_bound) if run.lp_lower_bound is not None else None,
                "integer_upper_cost": _frac_to_str(run.integer_upper) if run.integer_upper is not None else None,
                "optimality_gap": _frac_to_str(run.optimality_gap) if run.optimality_gap is not None else None,
                "certified_omitted_mass": (
                    {
                        "lo": str(run.certified_omitted_mass.lo),
                        "hi": str(run.certified_omitted_mass.hi),
                    }
                    if run.certified_omitted_mass is not None
                    else None
                ),
            }
            for method, run in sorted(report.baselines.items())
        },
    }


def main() -> int:
    fixtures = microcase_fixtures()
    reports: dict[str, dict] = {}
    crossvals: dict[str, dict] = {}
    start = time.time()
    for name, model in sorted(fixtures.items()):
        p0 = model.theta_0[0]
        p1 = model.theta_1[0]
        U = len(model.actions)
        spec = ExperimentSpec(
            model_name=name,
            p0=p0,
            p1=p1,
            costs=tuple(_COST for _ in range(U)),
            budget=_BUDGET,
        )
        report = build_matrix_report(model, spec)
        reports[name] = _serialize_report(report)
        # cross-validation with one repeat per action (n=1 each)
        cv = cross_validate_single_pair(
            model, p0, p1, tuple(1 for _ in range(U)), spec.costs
        )
        crossvals[name] = {
            "oracle_minimax_error": _frac_to_str(cv.oracle.minimax_error),
            "oracle_in_interval": cv.oracle_in_interval,
            "crosscheck": {k: bool(v) for k, v in cv.crosscheck.items()},
        }
    elapsed = time.time() - start

    payload = {
        "contract_section": "9",
        "kind": "EVALUATION_MATRIX_MODEL_CONDITIONAL",
        "run_started": start,
        "run_elapsed_s": round(elapsed, 6),
        "budget": _frac_to_str(_BUDGET),
        "microcase_count": len(reports),
        "microcases": sorted(fixtures.keys()),
        "reports": reports,
        "cross_validation": crossvals,
        "scientific_claim_authorized": False,
        "boundary_note": (
            "model-conditional synthetic evaluation matrix only; "
            "no prospective/blinded/held-out validation and no real-data or "
            "population claim (contract sections 1, 9)"
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())