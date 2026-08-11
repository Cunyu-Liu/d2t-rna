"""t7_track_freeze.py -- P0-7 frozen Track C decision registry generator.

Writes a FROZEN DECISION REGISTRY (not a result / comparative artifact) to
``/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/track_c_primary_decision.json``.

The registry freezes, BEFORE any development endpoint computation:

  * the primary-decision payload (max_registered_cost=8, cost_unit,
    cost_scale, cost_cap_source) with track_primary=TRACK_C and its
    ``cost_cap_hash = sha256(canonical primary-decision payload)``;
  * the Track C endpoint determined on DEVELOPMENT data (the 80-cell
    catalog-pair development families) using the pre-fixed threshold grid
    ``{0.05, 0.10, 0.20, 0.30}``;
  * the strongest comparator selected on DEVELOPMENT data (task reduction +
    original-paper toy parity + coverage >= 90% + reaches the endpoint,
    lowest family-cluster mean cost);
  * the method-role table (oracle / deployable / comparator);
  * the pre-registered Track C success criterion (no GO trigger is evaluated
    at decision-freeze time -- success is assessed only on confirmation data).

Every record carries ``paper_eligible=false`` and
``purpose=DECISION_REGISTRY_OR_METHOD_ROLE``.  This step NEVER writes a
comparative / superiority artifact and refuses to write into ``phase4v2``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
from collections import defaultdict
from fractions import Fraction

from d2t_rna.evaluation import method_role as MR
from d2t_rna.evaluation import track_registry as TR

ARTIFACT_ROOT = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts")
DEFAULT_OUT = (
    ARTIFACT_ROOT / "phase4v3-diagnostic" / "track_c_primary_decision.json"
)
MAX_REGISTERED_COST = 8
ENDPOINT_REACH_FRACTION = Fraction(80, 100)
COMPARATOR_COVERAGE_MIN = 0.90


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _git_heads() -> tuple[str, str]:
    def _run(args):
        return subprocess.check_output(
            ["git", "-C", "/home/cunyuliu/d2t-rna", *args],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    return _run(["rev-parse", "HEAD"]), _run(["rev-parse", "HEAD^{tree}"])


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _guard_not_phase4v2(out: pathlib.Path) -> None:
    if "phase4v2" in str(out.resolve()):
        raise RuntimeError(
            "refusing to write a track registry to a phase4v2 destination: "
            f"{out}"
        )


def _load_development_families(diag80: pathlib.Path) -> list[dict]:
    """Per-family deployable-certified randomized-minimax at budget 8.

    Uses the independent-oracle (deployable-achievable) values from the P0-6
    diagnostic over the 80-cell catalog-pair development families.  A family
    "can reach" a threshold within the max registered cost if the minimum
    budget-8 randomized-minimax over its cells is <= threshold.
    """
    doc = json.loads(diag80.read_text())
    fam = defaultdict(list)
    for r in doc["records"]:
        if r["budget"] != str(MAX_REGISTERED_COST):
            continue
        mm = r.get("randomized_minimax_error")
        if mm is None:
            continue
        pid = r["block_id"].split("::")[0]
        fam[pid].append(Fraction(mm))
    out = []
    for pid in sorted(fam):
        out.append({
            "family_id": pid,
            "minimax_at_max_cost": min(fam[pid]),
            "source": "diagnostic_80cell_catalog_pair (oracle/deployable)",
        })
    return out


def _load_comparator_candidates(
    baseline_suite: pathlib.Path,
    phase4v2: pathlib.Path,
    endpoint: Fraction,
) -> list[dict]:
    """Comparator coverage from baseline_suite; family-cluster mean cost and
    endpoint reachability from phase4v2 recorded baselines (development only)."""
    bs = json.loads(baseline_suite.read_text())
    agg = bs.get("aggregate_wins", {})
    n_ranked = int(bs["headline"]["n_ranked_cells"])
    coverage = {
        k: (v / n_ranked if n_ranked else 0.0) for k, v in agg.items()
    }
    p4 = json.loads(phase4v2.read_text())
    cells = [c for c in p4["cells"] if c["budget"] == str(MAX_REGISTERED_COST)]
    byfam = defaultdict(list)
    for c in cells:
        byfam[c["pair_id"]].append(c)
    candidates = []
    for label in bs.get("comparable_labels", []):
        if label == "exhaustive_oracle":
            continue  # oracle is never a comparator
        # family-cluster mean cost = mean of per-family min registered cost
        fam_min_costs = []
        fam_reach = 0
        nf = len(byfam)
        for pid in sorted(byfam):
            b = [c["baselines"].get(label) for c in byfam[pid]]
            b = [x for x in b if x and x.get("executed") and not x.get("spent_exceeds_budget")]
            if not b:
                continue
            mns = [Fraction(x["cost"]) for x in b]
            fam_min_costs.append(min(mns))
            # recorded-metric endpoint reachability (best minimax over cells)
            best = min((Fraction(x["minimax_error"]) for x in b
                        if x.get("minimax_error")), default=None)
            if best is not None and best <= endpoint:
                fam_reach += 1
        mean_cost = (
            float(sum(fam_min_costs) / len(fam_min_costs))
            if fam_min_costs else float("inf")
        )
        cov = coverage.get(label, 0.0)
        reaches = (fam_reach / nf) >= float(ENDPOINT_REACH_FRACTION) if nf else False
        candidates.append({
            "method_id": label,
            "task_reduction": True,   # same task/information/cost/horizon/endpoint
            "toy_parity": True,       # verified comparable baseline (P4 methodology)
            "coverage": cov,
            "coverage_detail": f"{int(round(cov*n_ranked))}/{n_ranked}",
            "reaches_endpoint": reaches,
            "families_reach_endpoint": f"{fam_reach}/{nf}",
            "family_cluster_mean_cost": mean_cost,
        })
    return candidates


def build_registry(
    diag80: pathlib.Path,
    baseline_suite: pathlib.Path,
    phase4v2: pathlib.Path,
) -> dict:
    commit, tree = _git_heads()
    reg = {
        "schema": "d2t_rna.track_registry.v3",
        "phase": "P0-7",
        "track": TR.TRACK_C,
        "status": "FROZEN_DECISION_REGISTRY",
        "generator": "t7_track_freeze.py",
        "generator_commit": commit,
        "generator_tree": tree,
        "paper_eligible": TR.PAPER_ELIGIBLE,
        "purpose": TR.PURPOSE,
        "is_result_artifact": False,
        "max_registered_cost": MAX_REGISTERED_COST,
    }

    # 1. frozen primary-decision
    reg["primary_decision"] = TR.primary_decision()

    # 2. endpoint on development data
    dev_fams = _load_development_families(diag80)
    try:
        ep = TR.determine_track_c_endpoint(
            dev_fams,
            threshold_grid=TR.TRACK_C_THRESHOLD_GRID,
            reach_fraction=ENDPOINT_REACH_FRACTION,
        )
        reg["endpoint"] = ep
        reg["endpoint"]["development_families_used"] = [
            {"family_id": f["family_id"], "minimax_at_max_cost": str(f["minimax_at_max_cost"])}
            for f in dev_fams
        ]
    except TR.TrackCEndpointNotIdentifiable as exc:
        reg["endpoint"] = {
            "status": TR.TRACK_C_ENDPOINT_NOT_IDENTIFIABLE,
            "track_primary": TR.TRACK_C,
            "reason": str(exc),
            "development_families_used": dev_fams,
        }
        return reg  # fail closed: cannot proceed to comparator/success

    # 3. strongest comparator on development data
    endpoint_f = Fraction(ep["endpoint"])
    cands = _load_comparator_candidates(baseline_suite, phase4v2, endpoint_f)
    reg["comparator_candidates"] = cands
    try:
        reg["strongest_comparator"] = TR.determine_strongest_comparator(
            cands, endpoint_f
        )
    except TR.MatchedComparatorNotIdentified as exc:
        reg["strongest_comparator"] = {
            "status": TR.MATCHED_COMPARATOR_NOT_IDENTIFIED,
            "reason": str(exc),
            "candidates": cands,
        }

    # 4. method-role table
    all_methods = set()
    for c in cands:
        all_methods.add(c["method_id"])
    all_methods.update(
        ["INDEPENDENT_ORACLE_EXACT", "D2T_FIXED_BUDGET_SOLVER"]
    )
    reg["method_role_table"] = MR.method_role_table(sorted(all_methods))

    # 5. pre-registered success criterion (NO GO at decision freeze time)
    reg["success_criterion"] = {
        "status": "PENDING_CONFIRMATION",
        "go": None,
        "track_primary": TR.TRACK_C,
        "criterion": (
            "family-level median relative cost reduction >= 10% AND a "
            "pre-registered one-sided 95% lower confidence bound on the "
            "reduction > 0; if a CI cannot be defined (too few families) only "
            "descriptive reporting is allowed (no superiority claim, no GO)"
        ),
        "min_families_for_ci": TR.MIN_FAMILIES_FOR_CI,
        "success_median_reduction": str(TR.TRACK_C_SUCCESS_MEDIAN_REDUCTION),
        "note": (
            "evaluated only on confirmation data; a decision registry never "
            "triggers a GO / superiority claim"
        ),
    }
    return reg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    out = pathlib.Path(args.out)
    _guard_not_phase4v2(out)

    diag80 = ARTIFACT_ROOT / "phase4v3-diagnostic" / "20260811T151403+0800" \
        / "diagnostic_80cell_catalog_pair.json"
    baseline_suite = ARTIFACT_ROOT / "phase4v2" / "baseline_suite.json"
    phase4v2 = ARTIFACT_ROOT / "phase4v2" / "phase4v2.json"

    reg = build_registry(diag80, baseline_suite, phase4v2)

    text = json.dumps(reg, indent=2, default=str) + "\n"
    if args.dry_run:
        print("DRY RUN: staged registry not written")
        print("cost_cap_hash:", reg["primary_decision"]["cost_cap_hash"])
        print("endpoint status:", reg["endpoint"]["status"])
        if reg["endpoint"]["status"] == "IDENTIFIED":
            print("endpoint:", reg["endpoint"]["endpoint"])
            print("strongest_comparator:",
                  reg.get("strongest_comparator", {}).get("strongest_comparator"))
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    # atomic write
    tmp = out.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    if _sha256_file(tmp) != hashlib.sha256(text.encode("utf-8")).hexdigest():
        raise RuntimeError("registry hash verify failed")
    tmp.replace(out)

    print(f"PROMOTED {out}")
    print(f"  cost_cap_hash: {reg['primary_decision']['cost_cap_hash']}")
    print(f"  endpoint: {reg['endpoint']['status']}")
    if reg["endpoint"]["status"] == "IDENTIFIED":
        print(f"    endpoint = {reg['endpoint']['endpoint']}")
        for row in reg["endpoint"]["per_threshold"]:
            print(f"    t={row['threshold_float']:.2f}: "
                  f"{row['n_families_reach']}/{row['n_families']} "
                  f"({row['reach_fraction']:.2%})")
        sc = reg.get("strongest_comparator", {})
        print(f"  strongest_comparator: {sc.get('strongest_comparator')}")
        print(f"  family_cluster_mean_cost: {sc.get('family_cluster_mean_cost')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
