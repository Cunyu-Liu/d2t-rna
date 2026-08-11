"""precommit.py -- P0-9 true precommit + confirmation evaluation core.

Two responsibilities:

1. **Precommit receipt** (:func:`build_precommit_receipt`).  Once the
   algorithm / hyperparameters / primary-track / endpoint /
   strongest-comparator / exclusion-rules are FROZEN, the receipt records a
   concrete instance JSON, seeds, generator_commit, generator_tree, and a
   commitment hash ``sha256(canonical precommit payload)``.  Because there is
   no external custodian / access isolation, the receipt status is
   ``PRECOMMITTED_SYNTHETIC_STRESS_SUITE`` (NOT ``sealed external
   confirmation``).  The receipt MUST be produced and recorded BEFORE any
   confirmation-outcome access -- enforced by the confirmation runner refusing
   to run without the receipt's precommit hash.

2. **Confirmation runner** (:func:`run_confirmation`).  Runs
   deployable-vs-frozen-comparator evaluation into a run dir.  Guards:

   * refuses (raises, caller exits non-zero) any run missing: precommit hash,
     method-role registry, primary decision, endpoint, or comparator-set hash;
   * oracle rows write regret ONLY in solvable cells and never enter ranking
     (fail-closed via ``method_role.assert_no_oracle_ranking``);
   * all failure / timeout / withheld cells REMAIN in the denominator (they are
     never dropped);
   * every record carries ``paper_eligible=false`` and
     ``purpose=PRE_COMMITTED_SYNTHETIC_STRESS_SUITE``.
"""

from __future__ import annotations

import hashlib
import json
import os
from fractions import Fraction
from typing import Optional

from d2t_rna.evaluation.method_role import (
    MethodRole,
    assert_no_oracle_ranking,
    classify_method_role,
)

PRECOMMIT_STATUS = "PRECOMMITTED_SYNTHETIC_STRESS_SUITE"
PURPOSE = "PRE_COMMITTED_SYNTHETIC_STRESS_SUITE"
PAPER_ELIGIBLE = False
SCHEMA_PRECOMMIT = "d2t_rna.precommit_receipt.v3"
SCHEMA_CONFIRMATION = "d2t_rna.confirmation_run.v3"

# frozen registry field keys required by the receipt / confirmation runner
_REQUIRED_REGISTRY_FIELDS = (
    "cost_cap_hash",       # from primary_decision
    "endpoint",            # frozen Track C endpoint (status IDENTIFIED)
    "strongest_comparator",
    "method_role_table",
)


class PrecommitError(RuntimeError):
    """Fail-closed error for a missing / inconsistent precommit input."""


# ---------------------------------------------------------------------------
# 1. precommit receipt
# ---------------------------------------------------------------------------


def _canonical_field(d, key) -> str:
    val = d.get(key)
    if val is None:
        raise PrecommitError(f"precommit field missing: {key!r}")
    if isinstance(val, bool) or isinstance(val, (int, float)):
        return json.dumps(val, sort_keys=True)
    if isinstance(val, (list, dict)):
        return json.dumps(val, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    return str(val)


def build_precommit_receipt(
    *,
    frozen_registry: dict,
    instance_json: dict,
    seeds: dict,
    generator_commit: str,
    generator_tree: str,
    exclusion_rules: Optional[dict] = None,
) -> dict:
    """Build a precommit receipt, refusing if any frozen registry field is
    missing.  The receipt is produced BEFORE any confirmation-outcome access.

    ``frozen_registry`` must carry ``primary_decision.cost_cap_hash``,
    ``endpoint`` (IDENTIFIED), ``strongest_comparator.strongest_comparator``
    and ``method_role_table``.
    """
    # --- guard: require the frozen registry fields ------------------------
    pd = frozen_registry.get("primary_decision") or {}
    endpoint = frozen_registry.get("endpoint") or {}
    sc = frozen_registry.get("strongest_comparator") or {}
    role_table = frozen_registry.get("method_role_table")

    cost_cap_hash = pd.get("cost_cap_hash")
    if not cost_cap_hash:
        raise PrecommitError("frozen registry missing primary_decision.cost_cap_hash")
    if endpoint.get("status") != "IDENTIFIED":
        raise PrecommitError(
            "frozen registry endpoint is not IDENTIFIED; cannot precommit -> "
            "refusing to precommit before endpoint is frozen"
        )
    strongest = sc.get("strongest_comparator")
    if not strongest:
        raise PrecommitError(
            "frozen registry missing strongest_comparator.strongest_comparator"
        )
    if not role_table:
        raise PrecommitError("frozen registry missing method_role_table")

    # comparator-set hash over the rankable comparator method ids
    comparator_ids = sorted(
        row["method_id"] for row in role_table
        if row.get("method_role") == MethodRole.COMPARATOR.value
    )
    comparator_set_hash = hashlib.sha256(
        json.dumps(comparator_ids, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schema": SCHEMA_PRECOMMIT,
        "status": PRECOMMIT_STATUS,
        "purpose": PURPOSE,
        "paper_eligible": PAPER_ELIGIBLE,
        "cost_cap_hash": cost_cap_hash,
        "endpoint": endpoint.get("endpoint"),
        "endpoint_float": endpoint.get("endpoint_float"),
        "strongest_comparator": strongest,
        "comparator_set": comparator_ids,
        "comparator_set_hash": comparator_set_hash,
        "method_role_registry_hash": hashlib.sha256(
            json.dumps(role_table, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "instance_json": instance_json,
        "seeds": seeds,
        "exclusion_rules": exclusion_rules or {},
        "generator_commit": generator_commit,
        "generator_tree": generator_tree,
        "note": (
            "PRECOMMITTED_SYNTHETIC_STRESS_SUITE -- no external custodian / "
            "access isolation exists, so this is NOT a 'sealed external "
            "confirmation'; the commitment hash binds the precommit payload "
            "before any confirmation-outcome access."
        ),
    }
    canonical = canonical_precommit_payload(payload)
    payload["commitment_hash"] = precommit_hash(canonical)
    payload["canonical_payload"] = canonical
    return payload


def canonical_precommit_payload(payload: dict) -> str:
    """Deterministic canonical JSON of the precommit payload (excluding the
    commitment hash and canonical payload itself)."""
    keys = [
        "schema", "status", "purpose", "paper_eligible", "cost_cap_hash",
        "endpoint", "endpoint_float", "strongest_comparator",
        "comparator_set", "comparator_set_hash",
        "method_role_registry_hash", "instance_json", "seeds",
        "exclusion_rules", "generator_commit", "generator_tree",
    ]
    canonical = {}
    for k in keys:
        canonical[k] = payload.get(k)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def precommit_hash(canonical_payload: str) -> str:
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def load_precommit_receipt(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        receipt = json.load(fh)
    if receipt.get("status") != PRECOMMIT_STATUS:
        raise PrecommitError(
            "precommit receipt status is not "
            f"{PRECOMMIT_STATUS!r}; refusing confirmation"
        )
    return receipt


def write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 2. confirmation-runner guards
# ---------------------------------------------------------------------------


def require_confirmation_inputs(
    *,
    precommit_receipt: dict,
    method_role_registry: dict,
    primary_decision: dict,
    endpoint: str,
    comparator_set_hash: str,
) -> None:
    """Refuse (raise) any confirmation run missing a required frozen input.

    The generator must exit non-zero on any of these being absent / mismatched.
    """
    if not precommit_receipt:
        raise PrecommitError("missing precommit receipt (precommit hash)")
    if not precommit_receipt.get("commitment_hash"):
        raise PrecommitError("missing precommit hash")
    if not method_role_registry:
        raise PrecommitError("missing method-role registry")
    if not primary_decision:
        raise PrecommitError("missing primary decision")
    if not endpoint:
        raise PrecommitError("missing endpoint")
    if not comparator_set_hash:
        raise PrecommitError("missing comparator-set hash")
    # cross-check: precommit must bind the same endpoint / comparator hash
    if precommit_receipt.get("endpoint") != endpoint:
        raise PrecommitError(
            f"precommit endpoint {precommit_receipt.get('endpoint')!r} "
            f"!= confirmation endpoint {endpoint!r}"
        )
    if precommit_receipt.get("comparator_set_hash") != comparator_set_hash:
        raise PrecommitError(
            "precommit comparator-set hash does not match the confirmation "
            "comparator-set hash"
        )


# ---------------------------------------------------------------------------
# 3. per-cell confirmation evaluation
# ---------------------------------------------------------------------------

WITHHELD = "WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE"
TIMEOUT = "TIMEOUT"
FAILURE = "FAILURE"


def evaluate_confirmation_cell(
    *,
    cell_id: str,
    p0,
    p1,
    actions,
    costs,
    budget,
    deployable_alloc,
    comparator_alloc,
    endpoint: Fraction,
    run_id: str,
) -> dict:
    """Evaluate one confirmation cell.

    The deployable and the frozen comparator each produce an allocation; the
    independent oracle evaluates both.  Oracle-derived regret is written only
    in *solvable* cells (where the minimax LP is available), and an oracle row
    is NEVER ranked (fail-closed guard).  Every returned record carries
    ``paper_eligible=false`` and ``purpose=PRE_COMMITTED_SYNTHETIC_STRESS_SUITE``.
    """
    from d2t_rna.audit import diagnostic_oracle as O

    p0_laws = tuple(O.action_law(a, tuple(Fraction(x) for x in p0)) for a in actions)
    p1_laws = tuple(O.action_law(a, tuple(Fraction(x) for x in p1)) for a in actions)

    def _eval(alloc):
        p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        cost = sum(Fraction(c) * Fraction(n) for c, n in zip(costs, alloc))
        return {"cost": cost, "randomized_minimax_error": mm, "n_outcomes": len(p0v)}

    def _record(method_id, alloc):
        try:
            res = _eval(alloc)
            role = classify_method_role(method_id)
            row = {
                "task_id": "P0-9-CONFIRMATION",
                "run_id": run_id,
                "cell_id": cell_id,
                "method_id": method_id,
                "method_role": role.value,
                "allocation": list(alloc),
                "cost": str(res["cost"]),
                "randomized_minimax_error": (
                    str(res["randomized_minimax_error"])
                    if res["randomized_minimax_error"] is not None else None
                ),
                "n_outcomes": res["n_outcomes"],
                "status": (
                    WITHHELD if res["randomized_minimax_error"] is None
                    else "COMPUTED"
                ),
                "paper_eligible": PAPER_ELIGIBLE,
                "purpose": PURPOSE,
            }
            return row, res
        except Exception as exc:  # noqa: BLE001
            return {
                "task_id": "P0-9-CONFIRMATION",
                "run_id": run_id,
                "cell_id": cell_id,
                "method_id": method_id,
                "method_role": classify_method_role(method_id).value,
                "allocation": list(alloc),
                "status": FAILURE,
                "failure_reason": str(exc),
                "paper_eligible": PAPER_ELIGIBLE,
                "purpose": PURPOSE,
            }, None

    dep_row, dep = _record("D2T_FIXED_BUDGET_SOLVER", deployable_alloc)
    comp_row, comp = _record("chernoff", comparator_alloc)

    # oracle row: regret written ONLY in solvable cells, never ranked
    oracle_rows = []
    regret = None
    solvable = False
    if dep is not None and dep["randomized_minimax_error"] is not None \
            and comp is not None and comp["randomized_minimax_error"] is not None:
        solvable = True
        # oracle = minimum-cost allocation that reaches the endpoint (Track C)
        oracle_alloc, oracle_cost, _, _ = O.min_bayes_allocation(
            p0_laws, p1_laws, tuple(Fraction(c) for c in costs), Fraction(budget)
        )
        # regret is only a reference value; never ranked
        assert_no_oracle_ranking(
            MethodRole.ORACLE, "regret", method_id="INDEPENDENT_ORACLE_EXACT"
        )
        regret = float(dep["cost"] - oracle_cost)
        oracle_rows.append({
            "task_id": "P0-9-CONFIRMATION",
            "run_id": run_id,
            "cell_id": cell_id,
            "method_id": "INDEPENDENT_ORACLE_EXACT",
            "method_role": "oracle",
            "allocation": list(oracle_alloc),
            "cost": str(oracle_cost),
            "regret_solvable_only": str(regret),
            "solvable": True,
            "paper_eligible": PAPER_ELIGIBLE,
            "purpose": PURPOSE,
        })

    cell = {
        "cell_id": cell_id,
        "budget": str(budget),
        "endpoint": str(endpoint),
        "solvable": solvable,
        "deployable": dep_row,
        "comparator": comp_row,
        "oracle_regret_solvable_only": oracle_rows,
    }
    return cell


def run_confirmation(
    *,
    precommit_receipt: dict,
    method_role_registry: dict,
    primary_decision: dict,
    endpoint: str,
    comparator_set_hash: str,
    cells: list[dict],
    run_id: str,
) -> dict:
    """Run deployable-vs-frozen-comparator confirmation into ``run_id``.

    Returns the confirmation report.  Guards refuse a run missing any required
    input.  All failure/timeout/withheld cells remain in the denominator.
    """
    require_confirmation_inputs(
        precommit_receipt=precommit_receipt,
        method_role_registry=method_role_registry,
        primary_decision=primary_decision,
        endpoint=endpoint,
        comparator_set_hash=comparator_set_hash,
    )

    endpoint_f = Fraction(endpoint)
    records = []
    for cell_in in cells:
        try:
            result = evaluate_confirmation_cell(
                cell_id=cell_in["cell_id"],
                p0=cell_in["p0"],
                p1=cell_in["p1"],
                actions=cell_in["actions"],
                costs=cell_in["costs"],
                budget=cell_in["budget"],
                deployable_alloc=cell_in["deployable_alloc"],
                comparator_alloc=cell_in["comparator_alloc"],
                endpoint=endpoint_f,
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            # failure/timeout/withheld stays in the denominator
            result = {
                "cell_id": cell_in["cell_id"],
                "budget": str(cell_in.get("budget")),
                "endpoint": str(endpoint_f),
                "solvable": False,
                "status": FAILURE,
                "failure_reason": str(exc),
                "deployable": None,
                "comparator": None,
                "oracle_regret_solvable_only": [],
            }
        records.append(result)

    n_total = len(records)
    n_solvable = sum(1 for r in records if r.get("solvable"))
    n_withheld_or_failed = sum(
        1 for r in records if not r.get("solvable")
    )
    return {
        "schema": SCHEMA_CONFIRMATION,
        "run_id": run_id,
        "status": "CONFIRMATION_EVALUATION",
        "precommit_hash": precommit_receipt["commitment_hash"],
        "purpose": PURPOSE,
        "paper_eligible": PAPER_ELIGIBLE,
        "n_total_cells": n_total,
        "n_denominator_cells": n_total,  # nothing dropped
        "n_solvable_cells": n_solvable,
        "n_withheld_or_failed_in_denominator": n_withheld_or_failed,
        "records": records,
        "note": (
            "All failure/timeout/withheld cells remain in the denominator. "
            "Oracle rows write regret only in solvable cells and never enter "
            "ranking (fail-closed). This is a PRECOMMITTED SYNTHETIC STRESS "
            "SUITE; it authorizes no scientific superiority claim."
        ),
    }
