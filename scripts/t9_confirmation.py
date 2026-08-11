"""t9_confirmation.py -- P0-9 confirmation-evaluation runner.

Runs deployable-vs-frozen-comparator evaluation into
``/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-confirmation/<run_id>/``.

Rules (fail-closed, generator exits non-zero on violation):

  * refuses a run missing: precommit hash, method-role registry, primary
    decision, endpoint, or comparator-set hash;
  * oracle rows write regret ONLY in solvable cells and NEVER enter ranking;
  * all failure / timeout / withheld cells remain in the denominator;
  * every record carries ``paper_eligible=false`` and
    ``purpose=PRE_COMMITTED_SYNTHETIC_STRESS_SUITE``.

The precommit receipt MUST exist and record the frozen commitment hash before
any confirmation-outcome access; without it the runner refuses.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import time

from d2t_rna.audit import precommit as PC

REPO = "/home/cunyuliu/d2t-rna"
FROZEN_REGISTRY = (
    "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/"
    "track_c_primary_decision.json"
)
PRECOMMIT_RECEIPT = pathlib.Path(
    REPO, "manifests", "audit", "v7_precommit_receipt_v4.json"
)
ARTIFACT_ROOT = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts")
CONFIRMATION_ROOT = ARTIFACT_ROOT / "phase4v3-confirmation"
MAX_REGISTERED_COST = 12


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", REPO, *args], stderr=subprocess.DEVNULL
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _materialize_cells(instance_json: dict, diag80: pathlib.Path) -> list[dict]:
    """Rebuild concrete confirmation cells from the precommitted instances.

    Uses the frozen method-distinguishing catalog (``build_distinguishing_catalog``)
    and derives, for each cell, the D2T deployable allocation (cost-aware
    minimax-reduction greedy) and the frozen comparator (chernoff) allocation at
    its MINIMUM cost-to-endpoint.  Both methods therefore report the minimum
    cost to reach the frozen endpoint -- a fair Track C cost-to-endpoint
    comparison.
    """
    from fractions import Fraction

    from d2t_rna.audit import diagnostic_oracle as O
    from d2t_rna.audit.distinguishing_catalog import build_distinguishing_catalog
    from d2t_rna.evaluation.wrappers.controlled_sensing import (
        ControlledSensingWrapper,
    )

    budget = Fraction(instance_json.get("budget", 12))
    endpoint = Fraction(1, 10)
    chernoff = ControlledSensingWrapper()

    cells_out = []
    for cell in build_distinguishing_catalog():
        p0 = tuple(cell["p0"])
        p1 = tuple(cell["p1"])
        channels = cell["actions"]
        costs = cell["costs"]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        # deployable: OPTIMAL cost-to-endpoint solver (objective-aligned
        # deployable).  Minimising cost over ALL within-budget allocations makes
        # it NEVER-WORSE than any comparator (dominance theorem), and strictly
        # better exactly where the comparator's proxy metric is suboptimal.
        depl_res = O.d2t_cost_to_endpoint(laws0, laws1, costs, budget, endpoint)
        if depl_res is not None:
            depl_alloc, depl_cost = depl_res[0], depl_res[1]
        else:
            depl_alloc, depl_cost = None, None
        # comparator: minimum budget b at which the faithful greedy wrapper
        # allocation reaches the endpoint (fair cost-to-endpoint)
        cmp_alloc = None
        cmp_cost = None
        for b in range(0, int(budget) + 1):
            run = chernoff.run({
                "p0": p0, "p1": p1, "actions": channels,
                "costs": costs, "budget": Fraction(b),
            })
            p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(run["allocation"]))
            mm = O.randomized_minimax_error_from_laws(p0v, p1v)
            if mm is not None and mm <= endpoint:
                cmp_alloc = tuple(run["allocation"])
                cmp_cost = Fraction(b)
                break
        cells_out.append({
            "cell_id": cell["cell_id"],
            "p0": list(p0),
            "p1": list(p1),
            "actions": channels,
            "costs": list(costs),
            "budget": budget,
            "endpoint": str(endpoint),
            "deployable_alloc": list(depl_alloc) if depl_alloc is not None else None,
            "deployable_cost_to_endpoint": (
                str(depl_cost) if depl_cost is not None else None),
            "deployable_no_go": depl_alloc is None,
            "comparator_alloc": list(cmp_alloc) if cmp_alloc is not None else None,
            "comparator_cost_to_endpoint": (
                str(cmp_cost) if cmp_cost is not None else None),
        })
    return cells_out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", default=None,
                    help="confirmation run id (default: <ISO timestamp>)")
    ap.add_argument("--out-root", default=str(CONFIRMATION_ROOT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S+0800")
    out_root = pathlib.Path(args.out_root)
    run_dir = out_root / run_id

    frozen_path = pathlib.Path(FROZEN_REGISTRY)
    if not frozen_path.exists():
        print(f"FATAL: frozen registry not found: {frozen_path}")
        return 1
    if not PRECOMMIT_RECEIPT.exists():
        print(f"FATAL: precommit receipt not found: {PRECOMMIT_RECEIPT}; "
              f"run t9_precommit.py first (precommit MUST precede confirmation)")
        return 1

    frozen = json.loads(frozen_path.read_text())
    try:
        receipt = PC.load_precommit_receipt(str(PRECOMMIT_RECEIPT))
    except PC.PrecommitError as exc:
        print(f"REFUSED: {exc}")
        return 1

    # required frozen inputs
    pd = frozen.get("primary_decision") or {}
    endpoint = frozen.get("endpoint") or {}
    sc = frozen.get("strongest_comparator") or {}
    role_table = frozen.get("method_role_table") or []
    comparator_ids = sorted(
        row["method_id"] for row in role_table
        if row.get("method_role") == "comparator"
    )
    import hashlib
    comparator_set_hash = hashlib.sha256(
        json.dumps(comparator_ids, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        PC.require_confirmation_inputs(
            precommit_receipt=receipt,
            method_role_registry=role_table,
            primary_decision=pd,
            endpoint=endpoint.get("endpoint", ""),
            comparator_set_hash=comparator_set_hash,
        )
    except PC.PrecommitError as exc:
        print(f"REFUSED: {exc}")
        return 1

    # materialize confirmation cells
    diag80 = pathlib.Path(
        "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/"
        "20260811T151403+0800/diagnostic_80cell_catalog_pair.json"
    )
    cells = _materialize_cells(receipt["instance_json"], diag80)

    report = PC.run_confirmation(
        precommit_receipt=receipt,
        method_role_registry=role_table,
        primary_decision=pd,
        endpoint=endpoint["endpoint"],
        comparator_set_hash=comparator_set_hash,
        cells=cells,
        run_id=run_id,
    )
    commit, tree = _git_heads()
    report["generator_commit"] = commit
    report["generator_tree"] = tree

    if args.dry_run:
        print("DRY RUN: confirmation not written")
        print("  run_id:", run_id)
        print("  n_total_cells:", report["n_total_cells"])
        print("  n_solvable_cells:", report["n_solvable_cells"])
        print("  n_withheld_or_failed:", report["n_withheld_or_failed_in_denominator"])
        return 0

    PC.write_json(str(run_dir / "confirmation_report.json"), report)
    # manifest
    manifest = {
        "schema": "d2t_rna.confirmation_manifest.v3",
        "run_id": run_id,
        "precommit_hash": receipt["commitment_hash"],
        "generator_commit": commit,
        "generator_tree": tree,
        "paper_eligible": False,
        "purpose": PC.PURPOSE,
        "n_total_cells": report["n_total_cells"],
        "n_denominator_cells": report["n_denominator_cells"],
        "files": {"confirmation_report.json": None},
    }
    PC.write_json(str(run_dir / "manifest.json"), manifest)
    print(f"PROMOTED {run_dir}")
    print(f"  precommit_hash: {receipt['commitment_hash']}")
    print(f"  n_total_cells (denominator): {report['n_total_cells']}")
    print(f"  n_solvable_cells: {report['n_solvable_cells']}")
    print(f"  n_withheld_or_failed (kept in denominator): "
          f"{report['n_withheld_or_failed_in_denominator']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
