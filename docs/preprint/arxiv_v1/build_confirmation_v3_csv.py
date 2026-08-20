#!/usr/bin/env python3
"""build_confirmation_v3_csv.py — extract the 20-cell v3 confirmation into a
public derived CSV (anc/confirmation_v3.csv) and verify the headline numbers
(3 lower / 17 tie / median ΔC = 0 / GO=false) directly from the artifact.

Source: /mnt/cunyuliu/d2t-rna/artifacts/phase4v3-confirmation/20260811T163031+0800/confirmation_report.json
All numbers are exact Fractions from the artifact (no rounding of semantics).
"""
from __future__ import annotations

import csv, json
from fractions import Fraction
from pathlib import Path

SRC = "/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-confirmation/20260811T163031+0800/confirmation_report.json"
OUT = Path(__file__).resolve().parent / "anc" / "confirmation_v3.csv"


def main() -> int:
    d = json.load(open(SRC, encoding="utf-8"))
    assert d["schema"] == "d2t_rna.confirmation_run.v3"
    assert d["n_total_cells"] == 20 and d["n_solvable_cells"] == 20
    recs = d["records"]
    assert len(recs) == 20

    rows = []
    for r in recs:
        cid = r["cell_id"]
        d_cost = int(r["deployable"]["cost"])
        c_cost = int(r["comparator"]["cost"])
        d_mm = Fraction(r["deployable"]["randomized_minimax_error"])
        c_mm = Fraction(r["comparator"]["randomized_minimax_error"])
        delta_c = (d_cost - c_cost) / c_cost if c_cost > 0 else Fraction(0, 1)
        out = "LOWER" if d_cost < c_cost else ("TIE" if d_cost == c_cost else "HIGHER")
        rows.append({
            "cell_id": cid,
            "deployable_cost": d_cost,
            "comparator_cost": c_cost,
            "deployable_mm_error": str(d_mm),
            "comparator_mm_error": str(c_mm),
            "delta_c": str(delta_c),
            "outcome": out,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n_lower = sum(1 for r in rows if r["outcome"] == "LOWER")
    n_tie = sum(1 for r in rows if r["outcome"] == "TIE")
    n_higher = sum(1 for r in rows if r["outcome"] == "HIGHER")
    deltas = sorted(Fraction(r["delta_c"]) for r in rows)
    median = deltas[len(deltas) // 2]
    go = median <= Fraction(-1, 10)

    print(f"n_cells={len(rows)} lower={n_lower} tie={n_tie} higher={n_higher}")
    print(f"median_delta_c={float(median):.4f} go_median_reduction_ge_10pct={go}")
    print(f"GO_MET={go}  (GO requires median relative cost reduction >= 10%)")
    print(f"WROTE -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
