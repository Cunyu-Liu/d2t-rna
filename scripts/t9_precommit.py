"""t9_precommit.py -- P0-9 true precommit receipt generator (method-repaired).

Reads the frozen Track C decision registry, then writes a PRECOMMIT RECEIPT
(status ``PRECOMMITTED_SYNTHETIC_STRESS_SUITE``) containing the concrete
instance JSON, seeds, generator_commit, generator_tree, and the commitment
hash (sha256 of the canonical precommit payload).

The instance JSON now binds the frozen METHOD-DISTINGUISHING catalog
(``build_distinguishing_catalog``) -- overlapping-support, heterogeneous-cost
cells where the objective-aligned D2T cost-aware deployable reaches the
endpoint at strictly lower cost than the Chernoff proxy-greedy.  The receipt
MUST be produced and recorded BEFORE any confirmation-outcome access; the
confirmation runner refuses to run without this receipt's precommit hash.

Because there is NO external custodian / access isolation, the receipt
explicitly states status ``PRECOMMITTED_SYNTHETIC_STRESS_SUITE`` and is NOT a
'sealed external confirmation'.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess

from d2t_rna.audit import precommit as PC

REPO = "/home/cunyuliu/d2t-rna"
FROZEN_REGISTRY = (
    "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/"
    "track_c_primary_decision.json"
)
DEFAULT_RECEIPT = pathlib.Path(
    REPO, "manifests", "audit", "v7_precommit_receipt_v4.json"
)
MAX_REGISTERED_COST = 12


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", REPO, *args], stderr=subprocess.DEVNULL
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _cell_to_instance(cell: dict) -> dict:
    """Serialize one distinguishing-catalog cell into the instance JSON.

    Channels are encoded as lists of rows of "num/den" strings so the receipt
    binds the exact action literals (deterministic re-materialisation).
    """
    def _f(x):
        from fractions import Fraction
        f = Fraction(x)
        return f"{f.numerator}/{f.denominator}"

    return {
        "cell_id": cell["cell_id"],
        "p0": [_f(x) for x in cell["p0"]],
        "p1": [_f(x) for x in cell["p1"]],
        "actions": [
            [[_f(x) for x in row] for row in channel]
            for channel in cell["actions"]
        ],
        "costs": [_f(x) for x in cell["costs"]],
        "budget": str(cell["budget"]),
        "endpoint": cell["endpoint"],
    }


def _materialize_instance_json() -> dict:
    """Concrete instance JSON for the method-distinguishing stress suite."""
    from d2t_rna.audit.distinguishing_catalog import build_distinguishing_catalog

    cells = [_cell_to_instance(c) for c in build_distinguishing_catalog()]
    return {
        "schema": "d2t_rna.precommit.instance_json.v4",
        "n_cells": len(cells),
        "budget": MAX_REGISTERED_COST,
        "catalog": "method_distinguishing",
        "cells": cells,
    }


def build_receipt(frozen_path: pathlib.Path) -> dict:
    frozen = json.loads(frozen_path.read_text())
    commit, tree = _git_heads()
    instance_json = _materialize_instance_json()
    seeds = {
        "stress_suite_seed": 20260812,
        "instance_generator_seed": 20260812,
        "catalog": "method_distinguishing",
        "allocation_seed": 0,
    }
    exclusion_rules = {
        "oracle_never_ranked": True,
        "withheld_kept_in_denominator": True,
        "paper_eligible_false": True,
        "purpose": PC.PURPOSE,
        "deployable_is_non_oracle_greedy": True,
        "comparator_reports_min_cost_to_endpoint": True,
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
    if not frozen_path.exists():
        print(f"FATAL: frozen registry not found: {frozen_path}")
        return 1

    try:
        receipt = build_receipt(frozen_path)
    except PC.PrecommitError as exc:
        print(f"REFUSED: {exc}")
        return 1

    if args.dry_run:
        print("DRY RUN: receipt not written")
        print("  status:", receipt["status"])
        print("  commitment_hash:", receipt["commitment_hash"])
        print("  strongest_comparator:", receipt["strongest_comparator"])
        print("  endpoint:", receipt["endpoint"])
        print("  n_instances:", receipt["instance_json"]["n_cells"])
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
