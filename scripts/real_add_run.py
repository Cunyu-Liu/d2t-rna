"""Real-data certificate runner: add riboswitch ON/OFF (T2b+T2c+T2d).

Emits the full decision-theoretic certificate stack over a *registered real
data* finite model: exact separation certificate (T2b), certified finite-sample
decision/budget bounds (T2c), and a costed integer design with no-go status
(T2d).  Converts the previously fail-closed ``add`` case into a
REGISTERED_OBSERVATION_MODEL case.

The observation channel carries a registered measurement-noise coupling
``eps`` (see :mod:`d2t_rna.t2.real_add`).  Because ``eps > 0`` the Hellinger
information per separating position is positive but finite, so the finite-sample
bound is genuine (non-trivial), not a degenerate ``n=1`` certainty.  The runner
sweeps ``eps`` and reports the certified bounds at each level.

Usage:
    PYTHONPATH=src python scripts/real_add_run.py
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from d2t_rna.t2.bounds import (
    correct_decl_lower_interval,
    wrong_prob_upper_interval,
)
from d2t_rna.t2.costed import (
    CostedDesign,
    achievable_integer_design,
    integrality_gap,
    no_go_lower_bound,
    no_go_status,
)
from d2t_rna.t2.decision import exact_bayes_average_error, exact_product_law_tv
from d2t_rna.t2.info import hellinger_info_interval, scale_info_interval
from d2t_rna.t2.real_add import (
    APT_SEQ,
    DEFAULT_EPS,
    build_real_case,
    measurement_channel,
    on_profile,
    off_profile,
    separation_positions,
    shared_positions,
)
from d2t_rna.t2.theorem import collision_or_separation

# Artifact root is env-configurable so the runner is reproducible in a clean
# container (e.g. D2T_RNA_ARTIFACTS_ROOT=/app/artifacts).  The default matches
# the server layout so existing invocations are unchanged.
ARTIFACTS_ROOT = Path(os.environ.get("D2T_RNA_ARTIFACTS_ROOT", "/mnt/cunyuliu/d2t-rna/artifacts"))

KAPPA = Fraction(99, 100)  # correct-declaration target 0.99


def _sufficiency_info_kappa(kappa: Fraction) -> Decimal:
    """Total info needed so the certified bound 1 - (1/2) exp(-I) reaches kappa.

    ``1 - (1/2) exp(-I) >= kappa  <=>  I >= -ln(2 (1 - kappa))``.  This is the
    *achievable/sufficiency* direction (unlike the Le Cam necessity bound).
    Returned as a Decimal (certified upper edge by construction).
    """
    from decimal import Decimal as _D
    return _D.from_float(float(1 / (2 * (1 - kappa)))).ln()


def _dec_to_frac(d: Decimal) -> Fraction:
    """Exact ``Fraction`` equal to a ``Decimal`` (certified endpoint)."""
    sign, digits, exp = d.as_tuple()
    if exp == "n":  # NaN / Infinity handled by caller
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


def _bernoulli_laws(p_on: int, p_off: int, eps: Fraction):
    """Laws of the two states for one position under noise ``eps``.

    outcome 0 = paired(protected), outcome 1 = unpaired.  Column 0 = OFF,
    column 1 = ON.
    """
    ch = measurement_channel(p_on, p_off, eps)
    q_off, q_on = ch[0]  # probabilities of reading *paired*
    law_off = (q_off, Fraction(1) - q_off)
    law_on = (q_on, Fraction(1) - q_on)
    return law_off, law_on


def run_eps(eps: Fraction) -> dict:
    model = build_real_case(eps)
    L = len(APT_SEQ)
    sep = separation_positions()
    shared = shared_positions()

    out: dict = {
        "eps": str(eps),
        "case": "add_riboswitch_on_off",
        "role": "REGISTERED_OBSERVATION_MODEL",
        "sequence": APT_SEQ,
        "length": L,
        "n_states": 2,
        "n_actions": len(model.actions),
        "off_paired": int(sum(off_profile())),
        "on_paired": int(sum(on_profile())),
        "separation_positions": sep,
        "n_separation_positions": len(sep),
        "shared_paired_positions": shared,
        "passive_marginal": "total observation law (1,1); collision fiber non-empty",
    }

    # ---- T2b: exact separation certificate -----------------------------
    full_panel = [a.action_id for a in model.actions]
    cert_full = collision_or_separation(model, full_panel)
    out["t2b_full_panel"] = {
        "gamma": str(cert_full.gamma),
        "status": cert_full.status,
        "enumeration_matches_lp": cert_full.enumeration_matches_lp,
        "lp_strong_duality": cert_full.lp_strong_duality,
        "separation_witness": [str(x) for x in cert_full.separation_witness]
        if cert_full.separation_witness else None,
    }

    # A minimal separating panel: a single separating position.
    single_panel = [f"probe{sep[0]}"]
    cert_single = collision_or_separation(model, single_panel)
    out["t2b_single_probe"] = {
        "probe": single_panel[0],
        "gamma": str(cert_single.gamma),
        "status": cert_single.status,
    }

    # ---- T2c: certified finite-sample bounds per separating probe --------
    # Sufficiency: correct >= 1 - (1/2) exp(-n I).  We find the smallest n
    # whose *certified* lower bound reaches kappa (genuine sample complexity),
    # then report the certified correct/wrong bounds and the exact oracle at
    # that n.  (This is the honest achievability direction; the Le Cam
    # necessity bound is only a lower bound on required info, not a
    # sufficiency certificate, so we do not use `required_repeats` here.)
    t2c = []
    for i in sep:
        law_off, law_on = _bernoulli_laws(on_profile()[i - 1], off_profile()[i - 1], eps)
        info = hellinger_info_interval(law_on, law_off)
        # smallest n with 1 - (1/2) exp(-n I_lo) >= kappa
        #   <=>  n I_lo >= -ln(2 (1 - kappa))  (sufficiency direction)
        n_suff = 1
        while True:
            cl = correct_decl_lower_interval(scale_info_interval(info, n_suff)).lo
            if cl >= Decimal(KAPPA.numerator) / Decimal(KAPPA.denominator):
                break
            n_suff += 1
            if n_suff > 100_000:
                raise RuntimeError("no finite sufficient n")
        total_info = scale_info_interval(info, n_suff)
        t2c.append({
            "probe": i,
            "law_off": [str(x) for x in law_off],
            "law_on": [str(x) for x in law_on],
            "info_lo": str(info.lo),
            "info_hi": str(info.hi),
            "n_sufficient_for_correct_0.99": n_suff,
            "total_info_n": str(total_info.hi),
            "correct_decl_lower_lo": str(correct_decl_lower_interval(total_info).lo),
            "wrong_prob_upper_hi": str(wrong_prob_upper_interval(total_info).hi),
            "exact_bayes_average_error_n": str(exact_bayes_average_error(law_on, law_off, n_suff)),
            "exact_product_tv_n": str(exact_product_law_tv(law_on, law_off, n_suff)),
        })
    out["t2c_per_probe"] = t2c

    # ---- T2d: costed design ---------------------------------------------
    # One pair (v = theta_1 - theta_0); threshold = required info for KAPPA.
    # Each separating probe has identical per-repeat info (all are Bernoulli
    # distractor vs. target), so the optimal design only needs a few probes;
    # we pass a compact representative panel (a few separating + a few shared
    # positions) to keep the integer branch-and-bound tractable.  The LP
    # relaxation and no-go bound are exact on this registered sub-panel.
    sep_prefix = sep[:3]
    shared_prefix = shared[:2]
    panel_idx = sep_prefix + shared_prefix
    U = len(panel_idx)
    info_lower = []
    info_upper = []
    for u_idx in panel_idx:
        law_off, law_on = _bernoulli_laws(on_profile()[u_idx - 1], off_profile()[u_idx - 1], eps)
        iv = hellinger_info_interval(law_on, law_off)
        # Convert the certified Decimal endpoints to exact Fractions.  The
        # interval is already conservative (lo <= true I <= hi), and the
        # Fraction equals the Decimal, so conservativeness is preserved while
        # keeping the LP in exact rational arithmetic.
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
    lb = no_go_lower_bound(cd)
    ub_cost, ub_n = achievable_integer_design(cd)
    gap = integrality_gap(cd)
    nogores = no_go_status(cd, Fraction(1, 1))  # budget == 1 repeat total
    out["t2d_design"] = {
        "n_actions": U,
        "panel": panel_idx,
        "costs": [str(c) for c in cd.costs],
        "threshold_info": str(cd.thresholds[0]),
        "lp_lower_bound": str(lb) if lb is not None else None,
        "achievable_integer_cost": str(ub_cost) if ub_cost is not None else None,
        "achievable_integer_n_nonzero": {
            f"probe{u+1}": int(n)
            for u, n in enumerate(ub_n or ())
            if n > 0
        } if ub_n else None,
        "integrality_gap": str(gap[1]) if gap[1] is not None else None,
        "no_go_status_budget_1": nogores[0],
        "no_go_lower_bound_budget_1": str(nogores[1]) if nogores[1] is not None else None,
    }
    return out


def main() -> int:
    epsilons = [Fraction(1, 20), Fraction(1, 10), Fraction(1, 5)]
    results = [run_eps(e) for e in epsilons]
    summary = []
    for r in results:
        summary.append({
            "eps": r["eps"],
            "gamma_full": r["t2b_full_panel"]["gamma"],
            "n_sep": r["n_separation_positions"],
            "first_probe_repeats": r["t2c_per_probe"][0]["n_sufficient_for_correct_0.99"],
            "first_probe_info_lo": r["t2c_per_probe"][0]["info_lo"],
            "achievable_cost": r["t2d_design"]["achievable_integer_cost"],
            "no_go_budget_1": r["t2d_design"]["no_go_status_budget_1"],
        })
    payload = {
        "name": "add_riboswitch_real_data_certificate",
        "role": "REGISTERED_OBSERVATION_MODEL",
        "kappa": str(KAPPA),
        "eps_default": str(DEFAULT_EPS),
        "summary_table": summary,
        "per_eps": results,
    }

    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    run_dir = ARTIFACTS_ROOT / "runs" / f"real-add-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "certificate.json").write_bytes(
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())