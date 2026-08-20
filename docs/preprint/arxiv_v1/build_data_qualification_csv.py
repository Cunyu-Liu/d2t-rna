#!/usr/bin/env python3
"""build_data_qualification_csv.py — extract the 7-scope v3 data-qualification
matrix into a public derived CSV (anc/data_qualification.csv).

Source: manifests/data/v7_data_qualification_v3.json (P0-8, fail-closed).
Each row reports ONLY the qualification status per scope (counts, replicate
crosswalk, likelihood, action, cost, license, exposure) — never re-derives
quantitative certificates from normalized reactivity.
"""
from __future__ import annotations

import csv, json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent.parent / "manifests" / "data" / "v7_data_qualification_v3.json"
OUT = Path(__file__).resolve().parent / "anc" / "data_qualification.csv"

FIELDS = ["scope_id", "accession", "raw_counts", "replicate_crosswalk",
          "calibrated_likelihood", "action_executable", "real_marginal_cost",
          "license_receipt", "exposure", "verdict"]


def main() -> int:
    d = json.load(open(SRC, encoding="utf-8"))
    assert d["schema_id"] == "d2t_rna.v7_data_qualification_v3"
    scopes = d["scopes"]
    assert len(scopes) == 7

    rows = []
    for s in scopes:
        cross = s.get("biological_replicate_crosswalk") or "NOT_AVAILABLE"
        if s.get("independent_unit"):
            cross = f"{cross} [independent unit: {s['independent_unit']}]"
        rows.append({
            "scope_id": s["scope_id"],
            "accession": s["accession"],
            "raw_counts": "NOT_AVAILABLE" if not s.get("raw_counts") else s["raw_counts"],
            "replicate_crosswalk": cross,
            "calibrated_likelihood": "NO" if not s.get("calibrated_likelihood") else "YES",
            "action_executable": "NO" if not s.get("action_executable") else "YES",
            "real_marginal_cost": "NO" if not s.get("real_marginal_cost") else "YES",
            "license_receipt": s.get("license_receipt", "UNVERIFIED"),
            "exposure": s.get("historical_exposure", "UNKNOWN"),
            "verdict": s["verdict"],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    all_term = all(r["verdict"] == "TERMINATED_FOR_CURRENT_DATA" for r in rows)
    print(f"n_scopes={len(rows)} all_terminated={all_term}")
    print(f"WROTE -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
