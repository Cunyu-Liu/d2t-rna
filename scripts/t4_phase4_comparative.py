"""Conditional Phase 4 (synthetic route): comparative, generalization & sealed
confirmation for D2T.

Evaluates D2T -- the exact decision-theoretic framework -- against the matched
*strongest comparable baseline* (``chernoff``, the Phase4-v2 headline winner:
60/64 ranked cells) on the five pre-registered sealed problem families from
``manifests/audit/v7_p1_family_split_v1.json``.

The sealed families use the pre-registered SEALED generation mechanism
``dgrid_den5_pairmerge_narrow_noisy``: distributions on the denominator-5 grid,
low-rank pair/merge (plus identity) channels that carry measurement noise, and
narrow (near-collision) margins.  They are genuinely held out from
train/development -- the D2T solver was never tuned on them.

Statistical unit (contract §6.1 / §3.6): the *block* (a concrete problem
instance), not grid cells / seeds / budget cells.  Per block,

    D_i = L_i(D2T) - L_i(strongest comparable method)

which is ``<= 0`` by D2T optimality (the exact solver never reaches a *worse*
error than a heuristic at the same task); strictly negative blocks are the
blocks where the heuristic comparator fails to reach the certified optimum.

Deliverables (plan §Conditional Phase 4 / §6.7):
  * sealed problem families (concrete, reproducible, genuinely held out)
  * matched strongest comparator
  * Pareto (error vs cost) per block + dominance
  * family/block-level CI on Delta (block bootstrap)
  * domain / family failure accounting
  * runtime / gap / coverage + full timeout / failure accounting
  * the unsolvable sealed family handled fail-closed via the Scheme C provable
    bound (``BOUND_ONLY`` / certified interval, no exact point claim)

Fail-closed: no SOTA / superiority claim; ``scientific_claim_authorized=false``;
``status = COMPARATIVE_SYNTHETIC_RECORD``.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import time
from fractions import Fraction
from itertools import product

from d2t_rna.architecture.provable_bound import provable_minimax_interval
from d2t_rna.evaluation.matrix import ExperimentSpec, MultiActionOracle, action_law, run_baselines
from d2t_rna.t2.model import Action, T2FiniteModel

_F = Fraction

# ---------------------------------------------------------------------------
# channel construction (SEALED mechanism: den-5 grid, pair/merge + identity,
# low-rank, noisy, narrow margin)
# ---------------------------------------------------------------------------


def _channel(rows):
    return tuple(tuple(Fraction(x) for x in row) for row in rows)


def _noisy_channel(base_rows, n_out, eps):
    """Column-stochastic channel ``Q' = (1-eps)*Q + eps*uniform``.

    ``base_rows`` is the row-major base channel (row = outcome, col = state).
    ``eps`` is the measurement-noise level; ``n_out`` the number of outcomes.
    Each column of ``Q'`` still sums to 1 and every entry stays in ``[0,1]``.
    For ``n_out == 1`` (merge) the channel stays information-free.
    """
    N = len(base_rows[0])
    out = []
    for y in range(n_out):
        row = tuple(
            (1 - eps) * base_rows[y][w] + eps * Fraction(1, n_out)
            for w in range(N)
        )
        out.append(row)
    return _channel(out)


def _id_rows(n):
    return tuple(tuple(1 if w == y else 0 for w in range(n)) for y in range(n))


def _pair_rows(n):
    rows = []
    w = 0
    while w < n:
        row = [0] * n
        row[w] = 1
        if w + 1 < n:
            row[w + 1] = 1
        rows.append(tuple(row))
        w += 2
    return rows


def _merge_rows(n):
    return ((1,) * n,)


def _dgrid(n, den):
    """All distributions over ``n`` states with common denominator ``den``."""
    if n == 2:
        return [(Fraction(a, den), Fraction(den - a, den)) for a in range(den + 1)]
    if n == 3:
        out = []
        for a in range(den + 1):
            for b in range(den - a + 1):
                out.append((Fraction(a, den), Fraction(b, den),
                            Fraction(den - a - b, den)))
        return out
    raise ValueError("dgrid supports n_states in {2,3}")


def _unit_marg(n):
    return tuple((Fraction(1) if w == 0 else Fraction(0)) for w in range(n))


# Sealed measurement-noise levels (distinct from train/dev clean channels).
EPS_CHEAP = Fraction(3, 10)
EPS_CLEAN = Fraction(1, 10)

# ---------------------------------------------------------------------------
# sealed-family concrete construction
# ---------------------------------------------------------------------------


def _three_state_pairs():
    """Deterministic narrow-margin 3-state pairs from the den-5 grid."""
    table = [
        ((2, 2, 1), (2, 3, 0)),
        ((1, 2, 2), (2, 2, 1)),
        ((1, 2, 2), (1, 3, 1)),
        ((3, 1, 1), (3, 2, 0)),
        ((2, 1, 2), (2, 2, 1)),
        ((1, 3, 1), (2, 2, 1)),
    ]
    seen = {}
    for a, b in table:
        seen.setdefault(a, b)

    def dist(t):
        return tuple(Fraction(v, 5) for v in t)

    return [(dist(a), dist(b)) for a, b in seen.items()]


def _two_state_actions(n_actions, include_merge, eps_cheap, eps_clean):
    acts = [
        Action("a_cheap", _noisy_channel(_id_rows(2), 2, eps_cheap)),
        Action("a_clean", _noisy_channel(_id_rows(2), 2, eps_clean)),
    ]
    if include_merge:
        acts.append(Action("merge", _noisy_channel(_merge_rows(2), 1, eps_cheap)))
    assert len(acts) == n_actions
    return tuple(acts)


def _three_state_actions(n_actions, eps_pair, eps_id):
    acts = [
        Action("pair", _noisy_channel(_pair_rows(3), 2, eps_pair)),
        Action("id", _noisy_channel(_id_rows(3), 3, eps_id)),
    ]
    if n_actions == 3:
        acts.append(Action("merge", _noisy_channel(_merge_rows(3), 1, eps_pair)))
    assert len(acts) == n_actions
    return tuple(acts)


def _costs(panel_len, mode):
    if mode == "uniform":
        return tuple(Fraction(1) for _ in range(panel_len))
    if mode == "hetero":
        return tuple(Fraction(i + 1) for i in range(panel_len))
    raise ValueError(mode)


def build_sealed_families() -> list[dict]:
    """Return the 5 pre-registered sealed families with concrete blocks.

    Each returned family dict has the frozen axes from the family-split manifest
    plus a deterministic list of concrete ``blocks`` (independent problem
    instances = statistical units).
    """
    # Build blocks explicitly per family.
    families = []

    # ---- q_s2_2x2_noisy: n=2, 2x2, 2 actions, budget 4, uniform, abstain off
    d2 = _dgrid(2, 5)
    s2_2x2 = [
        (d2[1], d2[2]),
        (d2[2], d2[3]),
        (d2[0], d2[1]),
        (d2[3], d2[4]),
    ]
    blocks = [
        {"block_id": f"q_s2_2x2_b{k}", "p0": p0, "p1": p1}
        for k, (p0, p1) in enumerate(s2_2x2, start=1)
    ]
    families.append(_family(
        "q_s2_2x2_noisy", 2, "2x2", 2, Fraction(4), "uniform", Fraction(1),
        "solvable", blocks, _two_state_actions(2, False, EPS_CHEAP, EPS_CLEAN),
    ))

    # ---- q_s2_3x3_noisy: n=2, 3x3, 3 actions, budget 8, uniform, abstain on
    s2_3x3 = [
        (d2[0], d2[1]),
        (d2[1], d2[2]),
        (d2[2], d2[3]),
        (d2[3], d2[4]),
        (d2[4], d2[5]),
    ]
    blocks = [
        {"block_id": f"q_s2_3x3_b{k}", "p0": p0, "p1": p1}
        for k, (p0, p1) in enumerate(s2_3x3, start=1)
    ]
    families.append(_family(
        "q_s2_3x3_noisy", 2, "3x3", 3, Fraction(8), "uniform", Fraction(2),
        "solvable", blocks, _two_state_actions(3, True, EPS_CHEAP, EPS_CLEAN),
    ))

    # ---- q_s3_2x2_noisy: n=3, 2x2, 2 actions, budget 4, uniform, abstain off
    tri = _three_state_pairs()
    blocks = [
        {"block_id": f"q_s3_2x2_b{k}", "p0": p0, "p1": p1}
        for k, (p0, p1) in enumerate(tri, start=1)
    ]
    families.append(_family(
        "q_s3_2x2_noisy", 3, "2x2", 2, Fraction(4), "uniform", Fraction(1),
        "solvable", blocks, _three_state_actions(2, EPS_CHEAP, EPS_CLEAN),
    ))

    # ---- q_s3_3x3_noisy: n=3, 3x3, 2 actions, budget 8, hetero, abstain on
    blocks = [
        {"block_id": f"q_s3_3x3_b{k}", "p0": p0, "p1": p1}
        for k, (p0, p1) in enumerate(tri, start=1)
    ]
    families.append(_family(
        "q_s3_3x3_noisy", 3, "3x3", 2, Fraction(8), "hetero", Fraction(2),
        "solvable", blocks, _three_state_actions(2, EPS_CHEAP, EPS_CLEAN),
    ))

    # ---- q_s3_3x2_noisy_unsolv: n=3, 3x2, 3 actions, budget 8, hetero, abstain off, unsolvable
    blocks = [
        {"block_id": f"q_s3_3x2_b{k}", "p0": p0, "p1": p1}
        for k, (p0, p1) in enumerate(tri, start=1)
    ]
    families.append(_family(
        "q_s3_3x2_noisy_unsolv", 3, "3x2", 3, Fraction(8), "hetero", Fraction(1),
        "unsolvable", blocks, _three_state_actions(3, EPS_CHEAP, EPS_CLEAN),
    ))

    return families


def _family(fid, n, catalog, n_actions, budget, cost_mode, abstain_ratio,
            exact_scale, blocks, actions):
    return {
        "family_id": fid,
        "n_states": n,
        "catalog": catalog,
        "n_actions": n_actions,
        "budget": str(budget),
        "cost_mode": cost_mode,
        "abstain_ratio": str(abstain_ratio),
        "exact_scale": exact_scale,
        "generation_mechanism": "dgrid_den5_pairmerge_narrow_noisy",
        "actions": [a.action_id for a in actions],
        "costs": [str(c) for c in _costs(len(actions), cost_mode)],
        "panel": [a.action_id for a in actions],
        "blocks": blocks,
        "action_objects": actions,
    }


# ---------------------------------------------------------------------------
# Pareto frontier + block evaluation
# ---------------------------------------------------------------------------


def _pareto_frontier(model, spec):
    """Enumerate within-budget allocations and return the non-dominated
    (cost, error) Pareto frontier plus the min-error (D2T) point."""
    U = len(spec.costs)
    p0_laws = tuple(action_law(model, a, spec.p0) for a in model.actions)
    p1_laws = tuple(action_law(model, a, spec.p1) for a in model.actions)
    max_n = [int(spec.budget // c) if c > 0 else 0 for c in spec.costs]
    points = []  # (cost, error, alloc)
    for joint in product(*(range(m + 1) for m in max_n)):
        cost = sum(c * nu for c, nu in zip(spec.costs, joint))
        if cost > spec.budget:
            continue
        res = MultiActionOracle(p0_laws, p1_laws, spec.costs, joint,
                                spec.abstain_ratio).evaluate()
        points.append((cost, res.minimax_error, tuple(joint)))
    if not points:
        return {"frontier": [], "min_error_point": None, "all_points": []}
    # non-dominated: a point is Pareto if no other feasible point has
    # (cost, error) <= (cost', error') with at least one strict.
    frontier = []
    for p in points:
        dominated = False
        for q in points:
            if q is p:
                continue
            if q[0] <= p[0] and q[1] <= p[1] and (q[0] < p[0] or q[1] < p[1]):
                dominated = True
                break
        if not dominated:
            frontier.append(p)
    # deterministic sort
    frontier.sort(key=lambda p: (p[0], p[1], p[2]))
    min_err = min(p[1] for p in points)
    min_err_point = min((p for p in points if p[1] == min_err), key=lambda p: p[0])
    return {
        "frontier": [[str(c), str(e), [int(x) for x in a]] for c, e, a in frontier],
        "min_error_point": [str(min_err_point[0]), str(min_err_point[1]),
                            [int(x) for x in min_err_point[2]]],
        "all_points": [[str(c), str(e)] for c, e, a in points],
    }


def _run_solvable_block(fam, block):
    model = T2FiniteModel(
        name=block["block_id"], n_states=fam["n_states"],
        theta_0=(block["p0"],), theta_1=(block["p1"],),
        marginal_map=(_unit_marg(fam["n_states"]),),
        actions=fam["action_objects"],
    )
    costs = _costs(len(fam["action_objects"]), fam["cost_mode"])
    spec = ExperimentSpec(model_name=block["block_id"], p0=block["p0"],
                          p1=block["p1"], costs=costs,
                          budget=Fraction(fam["budget"]),
                          abstain_ratio=Fraction(fam["abstain_ratio"]))
    t0 = time.time()
    runs = run_baselines(model, spec)
    elapsed = time.time() - t0

    d2t = runs["exhaustive_oracle"]  # D2T certified optimum (== correctness ref)
    comp = runs["chernoff"]          # matched strongest comparator

    d2t_err = d2t.oracle.minimax_error
    comp_err = comp.oracle.minimax_error
    d_i = d2t_err - comp_err  # <= 0 by D2T optimality
    strict_improvement = d_i < 0

    pareto = _pareto_frontier(model, spec)
    # dominance: is comparator Pareto-dominated by D2T's min-error point?
    dominated = _is_dominated(
        (comp.cost, comp_err), pareto["all_points"], pareto["min_error_point"]
    )

    return {
        "block_id": block["block_id"],
        "family_id": fam["family_id"],
        "exact_status": "RUN",
        "d2t_error": str(d2t_err),
        "d2t_cost": str(d2t.cost),
        "d2t_allocation": [int(x) for x in d2t.allocation],
        "comparator": "chernoff",
        "comparator_error": str(comp_err),
        "comparator_cost": str(comp.cost),
        "comparator_allocation": [int(x) for x in comp.allocation],
        "d_i": str(d_i),
        "strict_improvement": strict_improvement,
        "comparator_pareto_dominated": dominated,
        "oracle_beaten_by": runs["exhaustive_oracle"].oracle.minimax_error < d2t_err,
        "t2_integer_lp_gap": (str(runs["t2_integer_lp"].optimality_gap)
                              if runs["t2_integer_lp"].optimality_gap is not None else None),
        "runtime_s": round(elapsed, 6),
        "pareto_frontier": pareto["frontier"],
        "pareto_min_error_point": pareto["min_error_point"],
        "timeout": False,
        "failure": None,
    }


def _is_dominated(comp_pt, all_points, min_err_pt):
    c_cost, c_err = comp_pt
    if min_err_pt is None:
        return False
    m_cost = Fraction(min_err_pt[0])
    m_err = Fraction(min_err_pt[1])
    # D2T point (min error at its cost) dominates comparator if cost <= and err <= with strict
    if m_cost <= c_cost and m_err <= c_err and (m_cost < c_cost or m_err < c_err):
        return True
    # check any frontier point dominating comparator
    for row in all_points:
        pc = Fraction(row[0]); pe = Fraction(row[1])
        if pc <= c_cost and pe <= c_err and (pc < c_cost or pe < c_err):
            return True
    return False


def _run_unsolvable_block(fam, block):
    """Fail-closed bound-only handling for the unsolvable sealed family."""
    model = T2FiniteModel(
        name=block["block_id"], n_states=fam["n_states"],
        theta_0=(block["p0"],), theta_1=(block["p1"],),
        marginal_map=(_unit_marg(fam["n_states"]),),
        actions=fam["action_objects"],
    )
    costs = _costs(len(fam["action_objects"]), fam["cost_mode"])
    spec = ExperimentSpec(model_name=block["block_id"], p0=block["p0"],
                          p1=block["p1"], costs=costs,
                          budget=Fraction(fam["budget"]),
                          abstain_ratio=Fraction(fam["abstain_ratio"]))
    t0 = time.time()
    # comparator (heuristics are polynomial and feasible)
    runs = run_baselines(model, spec)
    elapsed = time.time() - t0
    comp = runs["chernoff"]
    comp_err = comp.oracle.minimax_error

    # D2T certified interval via Scheme C provable bound (no exact point claim)
    p0_laws = tuple(action_law(model, a, spec.p0) for a in model.actions)
    p1_laws = tuple(action_law(model, a, spec.p1) for a in model.actions)
    bound = provable_minimax_interval(p0_laws, p1_laws, costs, Fraction(fam["budget"]))
    lower = Fraction(bound["lower_bound"])
    upper = Fraction(bound["upper_bound"])
    # comparator relation to the certified interval (fail-closed)
    if comp_err > upper:
        comp_relation = "CERTIFIED_WORSE_THAN_D2T_UPPER"
    elif comp_err < lower:
        comp_relation = "CERTIFIED_BELOW_D2T_LOWER"  # would contradict bound
    else:
        comp_relation = "WITHIN_D2T_CERTIFIED_INTERVAL"

    return {
        "block_id": block["block_id"],
        "family_id": fam["family_id"],
        "exact_status": "BOUND_ONLY",
        "d2t_error_lower": str(lower),
        "d2t_error_upper": str(upper),
        "d2t_gap": str(upper - lower),
        "d2t_allocation": bound["allocation"],
        "d2t_allocation_cost": bound["allocation_cost"],
        "within_budget": bound["within_budget"],
        "bound": bound["bound"],
        "comparator": "chernoff",
        "comparator_error": str(comp_err),
        "comparator_cost": str(comp.cost),
        "comparator_relation_to_certified": comp_relation,
        "runtime_s": round(elapsed, 6),
        "timeout": False,
        "failure": None,
    }


def _block_bootstrap_ci(d_list, n_boot=10000, alpha=0.05, seed=17):
    """Block-bootstrap 95% CI on the mean of block-level ``D_i``."""
    if not d_list:
        return None
    rng = random.Random(seed)
    n = len(d_list)
    means = []
    for _ in range(n_boot):
        s = 0
        for _ in range(n):
            s += d_list[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return {
        "n_blocks": n,
        "mean": float(sum(d_list) / n),
        "bootstrap_n": n_boot,
        "ci_lower": lo,
        "ci_upper": hi,
        "seed": seed,
        "strictly_below_zero": hi < 0,
    }


# ---------------------------------------------------------------------------
# report assembly
# ---------------------------------------------------------------------------


def build_phase4_report() -> dict:
    families = build_sealed_families()
    fam_records = []
    all_d_i = []
    n_exact = 0
    n_bound_only = 0
    n_strict = 0
    n_dominated = 0
    n_timeout = 0
    n_failure = 0
    total_runtime = 0.0
    max_runtime = 0.0

    for fam in families:
        cells = []
        for block in fam["blocks"]:
            if fam["exact_scale"] == "unsolvable":
                res = _run_unsolvable_block(fam, block)
                n_bound_only += 1
            else:
                res = _run_solvable_block(fam, block)
                n_exact += 1
                d = Fraction(res["d_i"])
                all_d_i.append(d)
                if res["strict_improvement"]:
                    n_strict += 1
                if res["comparator_pareto_dominated"]:
                    n_dominated += 1
            if res["timeout"]:
                n_timeout += 1
            if res["failure"]:
                n_failure += 1
            total_runtime += res["runtime_s"]
            max_runtime = max(max_runtime, res["runtime_s"])
            cells.append(res)
        fam_records.append({
            "family_id": fam["family_id"],
            "n_states": fam["n_states"],
            "catalog": fam["catalog"],
            "n_actions": fam["n_actions"],
            "budget": fam["budget"],
            "cost_mode": fam["cost_mode"],
            "abstain_ratio": fam["abstain_ratio"],
            "exact_scale": fam["exact_scale"],
            "generation_mechanism": fam["generation_mechanism"],
            "actions": fam["actions"],
            "costs": fam["costs"],
            "n_blocks": len(cells),
            "cells": cells,
        })

    pooled_ci = _block_bootstrap_ci([float(d) for d in all_d_i]) if all_d_i else None
    n_blocks = n_exact + n_bound_only

    return {
        "schema": "d2t_rna.v7_p4_comparative.v1",
        "phase": "P4_CONDITIONAL_SYNTHETIC",
        "authority_role": "COMPARATIVE_GENERALIZATION_SEALED_CONFIRMATION",
        "status": "COMPARATIVE_SYNTHETIC_RECORD",
        "scientific_claim_authorized": False,
        "comparator": "chernoff",
        "comparator_basis": "Phase4-v2 comparable-only headline winner (60/64 ranked cells)",
        "correctness_reference": "exhaustive_oracle (D2T exact decision; never ranked as competitor)",
        "statistical_unit": "block (independent problem instance); grid cells/seeds/budget cells are not independent units",
        "sealed": {
            "generation_mechanism": "dgrid_den5_pairmerge_narrow_noisy",
            "genuinely_held_out_from_train_dev": True,
            "solver_not_tuned_on_sealed": True,
        },
        "summary": {
            "n_families": len(fam_records),
            "n_blocks": n_blocks,
            "n_exact": n_exact,
            "n_bound_only": n_bound_only,
            "n_strict_improvement": n_strict,
            "n_comparator_pareto_dominated": n_dominated,
            "n_timeout": n_timeout,
            "n_failure": n_failure,
            "n_withheld_certificate": n_bound_only,
            "coverage_exact": (n_exact / n_blocks) if n_blocks else 0.0,
            "total_runtime_s": round(total_runtime, 6),
            "max_block_runtime_s": round(max_runtime, 6),
            "pooled_delta_mean": (pooled_ci["mean"] if pooled_ci else None),
            "pooled_delta_ci": pooled_ci,
            "d2t_never_worse_than_comparator": bool(all_d_i) and all(d <= 0 for d in all_d_i),
        },
        "families": fam_records,
        "fail_closed_note": (
            "model-conditional synthetic sealed evaluation only; no SOTA / "
            "superiority claim; scientific_claim_authorized=false; "
            "COMPARATIVE_SYNTHETIC_SUCCESS is NOT claimed here -- this is a "
            "comparative-synthetic record."
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/mnt/cunyuliu/d2t-rna/artifacts/phase4/p4_comparative.json")
    ap.add_argument("--manifest", default="manifests/audit/v7_p4_comparative_v1.json")
    args = ap.parse_args(argv)

    report = build_phase4_report()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    man = pathlib.Path(args.manifest)
    man.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "d2t_rna.v7_p4_comparative_manifest.v1",
        "phase": "P4_CONDITIONAL_SYNTHETIC",
        "status": "COMPARATIVE_SYNTHETIC_RECORD",
        "scientific_claim_authorized": False,
        "payload": report,
        "artifact": {"path": str(out), "sha256": _sha256(out)},
    }
    man.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print(f"wrote {out}")
    print(f"wrote {man}")
    return 0


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    h.update(pathlib.Path(path).read_bytes())
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
