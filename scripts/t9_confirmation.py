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
    REPO, "manifests", "audit", "v7_precommit_receipt.json"
)
ARTIFACT_ROOT = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts")
CONFIRMATION_ROOT = ARTIFACT_ROOT / "phase4v3-confirmation"
MAX_REGISTERED_COST = 8


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", REPO, *args], stderr=subprocess.DEVNULL
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _materialize_cells(instance_json: dict, diag80: pathlib.Path) -> list[dict]:
    """Rebuild concrete confirmation cells from the precommitted instances.

    Reconstructs p0/p1 + action channels deterministically (the same catalog
    generator as the P0-6 diagnostic) and derives a deployable allocation and
    the frozen comparator (chernoff) allocation for each cell.
    """
    from fractions import Fraction

    from d2t_rna.audit import diagnostic_oracle as O

    # ---- catalog generator (mirrors t6) ----
    def _d2(den=4):
        return [(_F(i, den), _F(den - i, den)) for i in range(den + 1)]

    def _d3(den=2):
        out = []
        for a in range(den + 1):
            for b in range(den - a + 1):
                out.append((_F(a, den), _F(b, den), _F(den - a - b, den)))
        return out

    _F = Fraction
    d2 = _d2(4)
    d3 = _d3(2)
    id2 = [("id_a", O.id_channel(2)), ("id_b", O.id_channel(2))]
    id3 = [("id", O.id_channel(3)), ("pair", O.pair_channel(3))]
    pools = [
        ("CA", 2, [d2[1], d2[3]], [d2[0], d2[2], d2[4]], id2, ["id_a", "id_b"]),
        ("CB", 2, [d2[0], d2[2], d2[4]], [d2[1], d2[3]], id2, ["id_a", "id_b"]),
        ("CC", 3, [d3[0], d3[1], d3[2]], [d3[3], d3[4]], id3, ["id", "pair"]),
        ("CD", 3, [d3[1], d3[3], d3[4]], [d3[0], d3[2], d3[5]], id3, ["id", "pair"]),
    ]
    pair_idx = {
        "CA": [(0, 0), (1, 0), (0, 1), (1, 1), (1, 2)],
        "CB": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
        "CC": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
        "CD": [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)],
    }

    # precommitted instance cells keyed by block id
    pre_cells = {c["cell_id"]: c for c in instance_json["cells"]}
    budget = Fraction(instance_json.get("budget", MAX_REGISTERED_COST))
    cost = Fraction(instance_json.get("cost_per_action", 1))

    from d2t_rna.evaluation.wrappers.controlled_sensing import (
        ControlledSensingWrapper,
    )

    chernoff = ControlledSensingWrapper()
    cells_out = []
    for cid, n, t0, t1, actions, panel in pools:
        for k, (i, j) in enumerate(pair_idx[cid], start=1):
            p0 = tuple(t0[i])
            p1 = tuple(t1[j])
            block = f"{cid}_p{k}::b{budget}::x_uniform"
            if block not in pre_cells:
                continue
            n_actions = len(actions)
            costs = tuple(cost for _ in range(n_actions))
            channels = [ch for _name, ch in actions]
            # deployable allocation: exact min-Bayes within budget (the D2T
            # fixed-budget solver is a deployable whose allocation is chosen by
            # the exact oracle semantics); comparator: chernoff faithful wrapper
            depl_alloc, _, _, _ = O.min_bayes_allocation(
                tuple(O.action_law(ch, p0) for ch in channels),
                tuple(O.action_law(ch, p1) for ch in channels),
                costs, budget,
            )
            cmp_run = chernoff.run({
                "p0": p0, "p1": p1, "actions": channels,
                "costs": costs, "budget": budget,
            })
            cells_out.append({
                "cell_id": block,
                "p0": list(p0),
                "p1": list(p1),
                "actions": channels,
                "costs": list(costs),
                "budget": budget,
                "deployable_alloc": list(depl_alloc),
                "comparator_alloc": cmp_run["allocation"],
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
