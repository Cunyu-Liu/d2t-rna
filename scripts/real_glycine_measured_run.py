"""Measured-data certificate runner: gcvT glycine riboswitch ON/OFF from DMS.

Second *real-data* case. Emits the full decision-theoretic certificate stack
(T2b exact separation certificate, T2c certified finite-sample bounds, T2d
costed integer design with no-go status) over a *measured* real-data finite
model using registered RMDB accessions BSUGLY_DMS_0013 (apo, 0 mM glycine) /
BSUGLY_DMS_0014 (bound, 1 mM glycine), TECprobe-VL DMS reactivity.

This demonstrates that the measured observation-channel upgrade is
*transferable*: a different chemistry (DMS vs 1M7), a different ligand
(glycine vs adenine), and a different organism/construct still yield an
IFF separation certificate with respect to the real measurements.

Usage:
    PYTHONPATH=src python scripts/real_glycine_measured_run.py
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from d2t_rna.data.measured_glycine import (
    APO_ACCESSION,
    BOUND_ACCESSION,
    SOURCE,
    build_measured_case,
    measured_separation_positions,
    measured_shared_positions,
    q_paired_apo,
    q_paired_bound,
    registered_sequence,
    reactivity_apo,
    reactivity_bound,
)
from d2t_rna.t2.bounds import (
    correct_decl_lower_interval,
    wrong_prob_upper_interval,
)
from d2t_rna.t2.costed import (
    CostedDesign,
    achievable_integer_design,
    integrality_gap,
    no_go_status,
)
from d2t_rna.t2.decision import exact_minimax_error, exact_product_law_tv
from d2t_rna.t2.info import hellinger_info_interval, scale_info_interval
from d2t_rna.t2.theorem import collision_or_separation

ARTIFACTS_ROOT = Path(os.environ.get("D2T_RNA_ARTIFACTS_ROOT", "/mnt/cunyuliu/d2t-rna/artifacts"))

KAPPA = Fraction(99, 100)  # correct-declaration target 0.99


def _sufficiency_info_kappa(kappa: Fraction) -> Decimal:
    """Total info so the certified bound 1 - (1/2) exp(-I) reaches kappa."""
    from decimal import Decimal as _D
    return _D.from_float(float(1 / (2 * (1 - kappa)))).ln()


def _dec_to_frac(d: Decimal) -> Fraction:
    """Exact ``Fraction`` equal to a ``Decimal`` (certified endpoint)."""
    sign, digits, exp = d.as_tuple()
    if exp == "n":
        raise ValueError(f"non-finite Decimal: {d}")
    if exp == "F":
        return Fraction(0)
    num = 0
    for x in digits:
        num = num * 10 + x
    if sign:
        num = -num
    e = int(exp)
    if e >= 0:
        return Fraction(num) * Fraction(10) ** e
    return Fraction(num) / Fraction(10) ** (-e)


def _law(i: int) -> tuple:
    """(law_off, law_on) for 0-based position ``i`` (rows: paired, unpaired)."""
    qa = Fraction(q_paired_apo(i))
    qb = Fraction(q_paired_bound(i))
    return (qa, Fraction(1) - qa), (qb, Fraction(1) - qb)


def main() -> int:
    import sys as _sys
    def log(msg: str) -> None:
        print(msg, file=_sys.stderr, flush=True)

    seq = registered_sequence()
    L = len(seq)
    model = build_measured_case()
    sep = measured_separation_positions()
    shared = measured_shared_positions()
    log(f"[probe0] model built: L={L} n_sep={len(sep)}")

    out: dict = {
        "name": "gcvT_glycine_riboswitch_measured_DMS_certificate",
        "role": "REGISTERED_OBSERVATION_MODEL",
        "observation_channel": "measured_DMS_reactivity",
        "apo_accession": APO_ACCESSION,
        "bound_accession": BOUND_ACCESSION,
        "source": SOURCE,
        "provenance": {
            "construct": "B. subtilis gcvT glycine riboswitch, delta P0 variant, cotranscriptionally folded",
            "reagent": "DMS (methylates unpaired A/C)",
            "apo_condition": "0 mM glycine (BSUGLY_DMS_0013)",
            "bound_condition": "1 mM glycine (BSUGLY_DMS_0014)",
            "normalization": "Low & Weeks 2010 (Methods 10.1016/j.ymeth.2010.06.007)",
            "analysis_tool": "ShapeMapper2 (Busan & Weeks, RNA 10.1261/rna.061945.117)",
            "readout_floor": 0.01,
            "full_length_transcript": True,
            "quality_caveat": "transcripts 223-250 and after 254 may be poor quality per RMDB comment",
        },
        "sequence": seq,
        "length": L,
        "n_states": 2,
        "n_actions": len(model.actions),
        "n_measured_separating_positions": len(sep),
        "n_measured_shared_positions": len(shared),
        "passive_marginal_collision": True,
    }

    # ---- T2b: exact separation certificate (compact strong-separator panel) --
    t2c_infos = []
    for i in sep:
        law_off, law_on = _law(i - 1)
        info = hellinger_info_interval(law_on, law_off)
        if info.lo <= 0:
            continue
        t2c_infos.append((float(info.lo), i))
    t2c_infos.sort(reverse=True)
    strong_panel = [f"probe{i}" for _, i in t2c_infos[:8]]
    log(f"[probe1] t2b full panel (n={len(strong_panel)}): {strong_panel}")
    cert_full = collision_or_separation(model, strong_panel)
    log(f"[probe2] t2b full done gamma={cert_full.gamma} status={cert_full.status}")
    out["t2b_full_panel"] = {
        "panel": strong_panel,
        "gamma": str(cert_full.gamma),
        "status": cert_full.status,
        "enumeration_matches_lp": cert_full.enumeration_matches_lp,
        "lp_strong_duality": cert_full.lp_strong_duality,
        "separation_witness": [str(x) for x in cert_full.separation_witness]
        if cert_full.separation_witness else None,
    }

    single_panel = [f"probe{t2c_infos[0][1]}"]
    cert_single = collision_or_separation(model, single_panel)
    log(f"[probe3] t2b single done gamma={cert_single.gamma}")
    out["t2b_single_best_probe"] = {
        "probe": single_panel[0],
        "gamma": str(cert_single.gamma),
        "status": cert_single.status,
    }

    # ---- T2c: certified finite-sample bounds per measured-separating probe --
    target = Decimal(KAPPA.numerator) / Decimal(KAPPA.denominator)
    need = Decimal(1 / (2 * (1 - float(KAPPA)))).ln()
    t2c = []
    for i in sep:
        law_off, law_on = _law(i - 1)
        info = hellinger_info_interval(law_on, law_off)
        if info.lo <= 0:
            continue
        n_suff = max(1, int((need / info.lo).to_integral_value(rounding="ROUND_CEILING")))
        while True:
            cl = correct_decl_lower_interval(scale_info_interval(info, n_suff)).lo
            if cl >= target:
                break
            n_suff += 1
            if n_suff > 1_000_000:
                raise RuntimeError("no finite sufficient n")
        total_info = scale_info_interval(info, n_suff)
        if n_suff <= 200:
            exact_minimax = str(exact_minimax_error(law_on, law_off, n_suff))
            exact_tv = str(exact_product_law_tv(law_on, law_off, n_suff))
        else:
            exact_minimax = None
            exact_tv = None
        t2c.append({
            "probe": i,
            "nucleotide": seq[i - 1],
            "reactivity_apo": reactivity_apo()[i - 1],
            "reactivity_bound": reactivity_bound()[i - 1],
            "q_paired_apo": str(Fraction(q_paired_apo(i - 1))),
            "q_paired_bound": str(Fraction(q_paired_bound(i - 1))),
            "info_lo": str(info.lo),
            "info_hi": str(info.hi),
            "n_sufficient_for_correct_0.99": n_suff,
            "correct_decl_lower_lo": str(correct_decl_lower_interval(total_info).lo),
            "wrong_prob_upper_hi": str(wrong_prob_upper_interval(total_info).hi),
            "exact_minimax_error_n": exact_minimax,
            "exact_product_tv_n": exact_tv,
        })
    out["t2c_per_probe"] = t2c
    log(f"[probe4] t2c done: n_probes={len(t2c)}")

    # ---- T2d: costed design on a compact panel of strong measured separators
    t2c_infos = sorted(t2c_infos, reverse=True)
    panel_idx = [i for _, i in t2c_infos[:4]]
    U = len(panel_idx)
    info_lower = []
    info_upper = []
    for u_idx in panel_idx:
        law_off, law_on = _law(u_idx - 1)
        iv = hellinger_info_interval(law_on, law_off)
        info_lower.append((_dec_to_frac(iv.lo),))
        info_upper.append((_dec_to_frac(iv.hi),))
    cd = CostedDesign(
        action_ids=tuple(f"probe{u_idx}" for u_idx in panel_idx),
        costs=tuple(Fraction(1) for _ in range(U)),
        pair_ids=("v_theta1_minus_theta0",),
        thresholds=(_dec_to_frac(_sufficiency_info_kappa(KAPPA)),),
        info_lower=tuple(info_lower),
        info_upper=tuple(info_upper),
    )
    ub_cost, ub_n = achievable_integer_design(cd)
    gap = integrality_gap(cd)
    nogores_b1 = no_go_status(cd, Fraction(1, 1))
    out["t2d_design"] = {
        "n_actions": U,
        "panel": panel_idx,
        "threshold_info": str(cd.thresholds[0]),
        "achievable_integer_cost": str(ub_cost) if ub_cost is not None else None,
        "achievable_integer_n_nonzero": {
            f"probe{u+1}": int(n)
            for u, n in enumerate(ub_n or ())
            if n > 0
        } if ub_n else None,
        "integrality_gap": str(gap[1]) if gap[1] is not None else None,
        "no_go_status_budget_1": nogores_b1[0],
        "no_go_lower_bound_budget_1": str(nogores_b1[1]) if nogores_b1[1] is not None else None,
    }
    log(f"[probe5] t2d done: cost={ub_cost} no_go={nogores_b1[0]}")

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"real-glycine-measured-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "certificate.json").write_bytes(
        json.dumps(out, indent=2, sort_keys=True).encode("utf-8"))

    t2c_sorted = sorted(t2c, key=lambda r: int(r["n_sufficient_for_correct_0.99"]))
    print(json.dumps({
        "apo_accession": APO_ACCESSION,
        "bound_accession": BOUND_ACCESSION,
        "n_sep": out["n_measured_separating_positions"],
        "gamma_full": out["t2b_full_panel"]["gamma"],
        "best_probe": t2c_sorted[0]["probe"],
        "best_n_suff": t2c_sorted[0]["n_sufficient_for_correct_0.99"],
        "n_probes_with_finite_bound": len(t2c),
        "achievable_design_cost": out["t2d_design"]["achievable_integer_cost"],
        "no_go_budget_1": out["t2d_design"]["no_go_status_budget_1"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())