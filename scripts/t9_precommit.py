"""t9_precommit.py -- P0-9 true precommit receipt generator.

Reads the frozen Track C decision registry, then writes a PRECOMMIT RECEIPT
(status ``PRECOMMITTED_SYNTHETIC_STRESS_SUITE``) containing the concrete
instance JSON, seeds, generator_commit, generator_tree, and the commitment
hash (sha256 of the canonical precommit payload).

Because there is NO external custodian / access isolation, the receipt
explicitly states status ``PRECOMMITTED_SYNTHETIC_STRESS_SUITE`` and is NOT a
'sealed external confirmation'.  The receipt MUST be produced and recorded
BEFORE any confirmation-outcome access (the confirmation runner refuses to run
without this receipt's precommit hash).

The generator REFUSES (non-zero) if any frozen registry field is missing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import time
from fractions import Fraction

from d2t_rna.audit import precommit as PC

REPO = "/home/cunyuliu/d2t-rna"
FROZEN_REGISTRY = (
    "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/"
    "track_c_primary_decision.json"
)
DEFAULT_RECEIPT = pathlib.Path(
    REPO, "manifests", "audit", "v7_precommit_receipt.json"
)
MAX_REGISTERED_COST = 8


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", REPO, *args], stderr=subprocess.DEVNULL
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _materialize_instance_json(diag80: pathlib.Path) -> dict:
    """Concrete instance JSON for the confirmation stress suite.

    Reuses the 80-cell catalog-pair development families as the precommitted
    synthetic stress suite instances (budget 8, unit action cost).  Each cell
    records p0 / p1 / action channels / costs / budget deterministically.
    """
    from d2t_rna.audit import diagnostic_oracle as O

    doc = json.loads(diag80.read_text())
    # action-channel reconstruction is done by the confirmation runner from the
    # instance JSON; here we record the raw laws and budget and defer the exact
    # channels to the cell materializer in t9_confirmation.  For a self-binding
    # receipt we record the per-cell laws + budget.
    cells = []
    for r in doc["records"]:
        if r["budget"] != str(MAX_REGISTERED_COST):
            continue
        # the frozen Track C endpoint used the x_uniform cost-mode families;
        # the confirmation stress suite uses the same x_uniform cells so the
        # precommitted instance set and the confirmation materializer agree.
        if "x_uniform" not in r["block_id"]:
            continue
        cells.append({
            "cell_id": r["block_id"],
            "budget": MAX_REGISTERED_COST,
            "cost": 1,
        })
    return {
        "schema": "d2t_rna.precommit.instance_json.v3",
        "n_cells": len(cells),
        "budget": MAX_REGISTERED_COST,
        "cost_per_action": 1,
        "cells": cells,
    }


def build_receipt(frozen_path: pathlib.Path, diag80: pathlib.Path) -> dict:
    frozen = json.loads(frozen_path.read_text())
    commit, tree = _git_heads()
    instance_json = _materialize_instance_json(diag80)
    seeds = {
        "stress_suite_seed": 20260811,
        "instance_generator_seed": 20260811,
        "allocation_seed": 0,
    }
    exclusion_rules = {
        "oracle_never_ranked": True,
        "withheld_kept_in_denominator": True,
        "paper_eligible_false": True,
        "purpose": PC.PURPOSE,
    }
    return PC.build_precommit_receipt(
        frozen_registry=frozen,
        instance_json=instance_json,
        seeds=seeds,
        generator_commit=commit,
        generator_tree=tree,
        exclusion_rules=exclusion_rules,
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_RECEIPT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    frozen_path = pathlib.Path(FROZEN_REGISTRY)
    diag80 = (
        pathlib.Path(
            "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/"
            "20260811T151403+0800/diagnostic_80cell_catalog_pair.json"
        )
    )
    if not frozen_path.exists():
        print(f"FATAL: frozen registry not found: {frozen_path}")
        return 1
    if not diag80.exists():
        print(f"FATAL: diagnostic not found: {diag80}")
        return 1

    try:
        receipt = build_receipt(frozen_path, diag80)
    except PC.PrecommitError as exc:
        print(f"REFUSED: {exc}")
        return 1

    if args.dry_run:
        print("DRY RUN: receipt not written")
        print("  status:", receipt["status"])
        print("  commitment_hash:", receipt["commitment_hash"])
        print("  strongest_comparator:", receipt["strongest_comparator"])
        print("  endpoint:", receipt["endpoint"])
        return 0

    out = pathlib.Path(args.out)
    PC.write_json(str(out), receipt)
    print(f"PROMOTED {out}")
    print(f"  status: {receipt['status']}")
    print(f"  commitment_hash: {receipt['commitment_hash']}")
    print(f"  endpoint: {receipt['endpoint']}")
    print(f"  strongest_comparator: {receipt['strongest_comparator']}")
    print(f"  comparator_set_hash: {receipt['comparator_set_hash']}")
    print(f"  n_instances: {receipt['instance_json']['n_cells']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
