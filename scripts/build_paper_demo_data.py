from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

ART = Path("/mnt/cunyuliu/d2t-rna/artifacts/runs")


def _find(prefix: str) -> Path:
    hits = [p for p in ART.iterdir() if p.name.startswith(prefix)]
    if not hits:
        raise FileNotFoundError(f"no run dir for {prefix} in {ART}")
    return max(hits, key=lambda p: p.stat().st_mtime) / "certificate.json"


def flatten(cert: dict) -> dict:
    rows = []
    for row in cert["t2c_per_probe"]:
        rows.append({
            "pos": row["probe"],
            "nt": row["nucleotide"],
            "ra": row["reactivity_apo"],
            "rb": row["reactivity_bound"],
            "qa": float(Fraction(row["q_paired_apo"])),
            "qb": float(Fraction(row["q_paired_bound"])),
            "info_lo": float(row["info_lo"]),
            "info_hi": float(row["info_hi"]),
            "n": row["n_sufficient_for_correct_0.99"],
        })
    t2b = cert["t2b_full_panel"]
    t2d = cert["t2d_design"]
    return {
        "name": cert["name"],
        "length": cert["length"],
        "sequence": list(cert["sequence"]),
        "n_sep": cert["n_measured_separating_positions"],
        "t2b": {
            "status": t2b["status"],
            "gamma": t2b["gamma"],
            "panel": t2b["panel"],
            "enumeration_matches_lp": t2b["enumeration_matches_lp"],
            "lp_strong_duality": t2b["lp_strong_duality"],
            "separation_witness": t2b.get("separation_witness"),
        },
        "t2d": {
            "cost": t2d["achievable_integer_cost"],
            "n_nonzero": t2d["achievable_integer_n_nonzero"],
            "no_go_status": t2d["no_go_status_budget_1"],
            "design_cost": int(t2d["achievable_integer_cost"]) if t2d["achievable_integer_cost"] else None,
        },
        "rows": rows,
    }


def main() -> int:
    add = flatten(json.loads(_find("real-add-measured-").read_text()))
    add["accession"] = "ADD71_STD_0001"
    add["doi"] = "10.7554/eLife.29602"
    add["pmid"] = "29446752"
    add["reagent"] = "1M7 (SHAPE)"
    add["residues"] = "13-83"
    add["title"] = "Certified collision-or-separation on measured SHAPE reactivity"
    add["subtitle"] = "D2T-RNA | registered observation model | add adenine riboswitch aptamer (PDB 1Y26)"
    add["foot"] = ("Tian et al., eLife 2018 (RMDB ADD71_STD_0001).")

    gly = flatten(json.loads(_find("real-glycine-measured-").read_text()))
    gly["accession"] = "BSUGLY_DMS_0013 / BSUGLY_DMS_0014"
    gly["doi"] = None
    gly["pmid"] = None
    gly["reagent"] = "DMS"
    gly["residues"] = "1-265"
    gly["title"] = "Certified collision-or-separation on measured DMS reactivity"
    gly["subtitle"] = "D2T-RNA | registered observation model | gcvT glycine riboswitch (B. subtilis)"
    gly["foot"] = ("TECprobe-VL, Weeks lab (RMDB BSUGLY_DMS_0013 / BSUGLY_DMS_0014).")

    out = {"cases": {"add": add, "glycine": gly}}
    print(json.dumps(out, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
