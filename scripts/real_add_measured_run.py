"""Measured-data certificate runner: add ON/OFF from registered 1M7 SHAPE.

Emits the full decision-theoretic certificate stack over a *measured* real-data
finite model (T2b exact separation certificate, T2c certified finite-sample
decision/budget bounds, T2d costed integer design with no-go status) using the
registered RMDB accession ADD71_STD_0001 (Tian/Kladwang/Das, eLife 2018).

The observation channel is *measured*: for each position the probability of
reading unpaired/reactive is the published normalized 1M7 SHAPE reactivity
(apo vs 5 mM adenine), clamped to a registered 1% measurement-resolution floor.
This upgrades the ``add`` case from a model-conditional pairing-status + noise
coupling to a certificate that is separable with respect to real measurements.

Usage:
    PYTHONPATH=src python scripts/real_add_measured_run.py
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from d2t_rna.data.measured_add import (
    ACCESSION,
    DOI,
    PMID,
    build_measured_case,
    measured_separation_positions,
    measured_shared_positions,
    q_paired_apo,
    q_paired_bound,
    registered_sequence,
    reactivity_apo,
    reactivity_bound,
    error_apo,
    error_bound,
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
        "name": "add_riboswitch_measured_1M7_certificate",
        "role": "REGISTERED_OBSERVATION_MODEL",
        "observation_channel": "measured_1M7_SHAPE_reactivity",
        "accession": ACCESSION,
        "doi": DOI,
        "pmid": PMID,
        "provenance": {
            "construct": "add riboswitch residues 13-83, V. vulnificus",
            "reagent": "1M7 (SHAPE)",
            "apo_condition": "no ligand (RDAT REACTIVITY:1)",
            "bound_condition": "5 mM adenine (RDAT REACTIVITY:2)",
            "normalization": "reactive loop residues normalized to mean 1.0",
            "readout_floor": 0.01,
            "per_position_error_used": True,
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
    # The exact rational LP is rapid over a compact panel of the strongest
    # measured separators; a panel of strong probes already certifies IFF
    # separation (gamma > 0).  We rank by certified per-position info.
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

    # A minimal separating panel: the single strongest probe.
    single_panel = [f"probe{t2c_infos[0][1]}"]
    cert_single = collision_or_separation(model, single_panel)
    log(f"[probe3] t2b single done gamma={cert_single.gamma}")
    out["t2b_single_best_probe"] = {
        "probe": single_panel[0],
        "gamma": str(cert_single.gamma),
        "status": cert_single.status,
    }

    # ---- T2c: certified finite-sample bounds per measured-separating probe --
    # The certified achievability bound correct >= 1 - (1/2) exp(-I_total)
    # reaches kappa as soon as I_total >= -ln(2(1-kappa)), so a certified
    # sufficient n is n_suff = ceil(need / info.lo) (since I_total = n*I >=
    # n*info.lo).  We seed from that closed form and verify narrowly, instead
    # of scanning from n=1 (which is O(n_suff) Decimal exp per position).
    target = Decimal(KAPPA.numerator) / Decimal(KAPPA.denominator)
    need = Decimal(1 / (2 * (1 - float(KAPPA)))).ln()  # certified need
    t2c = []
    for i in sep:
        law_off, law_on = _law(i - 1)
        info = hellinger_info_interval(law_on, law_off)
        if info.lo <= 0:
            continue  # not finitely certifiable
        n_suff = max(1, int((need / info.lo).to_integral_value(rounding="ROUND_CEILING")))
        # verify upward from the certified seed (a few Decimal exps at most).
        while True:
            cl = correct_decl_lower_interval(scale_info_interval(info, n_suff)).lo
            if cl >= target:
                break
            n_suff += 1
            if n_suff > 1_000_000:
                raise RuntimeError("no finite sufficient n")
        total_info = scale_info_interval(info, n_suff)
        # The exact minimax/TV microcase crosscheck enumerates all count
        # vectors (O(n) distinct outcomes) and is only practical for tiny n;
        # for larger n the certified T2c interval is the rigorous claim.
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
            "error_apo": error_apo()[i - 1],
            "error_bound": error_bound()[i - 1],
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
    # Branch-and-bound over integer repeats is only tractable when every panel
    # action has strictly positive info.  Shared/scaffold positions have
    # info ~ 0 (their ub[u] = ceil(tau/info) explodes), so we use only the
    # strongest measured separators ranked by certified per-position info.
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
    run_dir = ARTIFACTS_ROOT / "runs" / f"real-add-measured-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "certificate.json").write_bytes(
        json.dumps(out, indent=2, sort_keys=True).encode("utf-8"))

    t2c_sorted = sorted(t2c, key=lambda r: int(r["n_sufficient_for_correct_0.99"]))
    print(json.dumps({
        "accession": ACCESSION,
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