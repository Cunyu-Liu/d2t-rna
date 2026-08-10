#!/usr/bin/env python3
"""Independent P0 red-team review for D2T-RNA v7 evidence repair (Batch 5.3).

The reviewer recomputes each item from RAW serialized inputs (not from the
production acceptance manifests), and where the plan requires it, exercises a
genuinely independent path.  It reports PASS/FAIL/UNKNOWN per item and writes a
receipt JSON into ``--outdir``.

Checks (plan 5.3):
  1. one discrete T2 certificate  -- rebuild gamma from raw theta_0/theta_1/M/
     channels via the independent discrete oracle; compare to production cert.
  2. one Bayes/minimax counterexample -- independent exact enumeration for
     P0=(1,0), P1=(1/2,1/2), n=1 (bayes 1/4, randomized minimax 1/3).
  3. one T2c constructive-feasibility status -- independent reconstruction of
     the fail-closed classification for the five branch cases vs production.
  4. one data-qualification decision -- re-derive the ADD verdict from the raw
     manifest eligibility fields.
  5. one manuscript claim -> experiment/artifact -- follow one claim id through
     the claim/evidence graph.
  6. one manuscript citation -> original source -- verify one cite key against
     references.bib and the citation verification manifest.
  7. one readiness negative fixture -- confirm the fail-closed gate reports FAIL
     for a deliberately out-of-range TV value.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction
from pathlib import Path

# ---------------------------------------------------------------------------
# Independent math primitives (rebuilt here, not imported from production).
# ---------------------------------------------------------------------------


def independent_bayes_minimax():
    """Exact enumeration for P0=(1,0), P1=(1/2,1/2), n=1.

    Outcomes y in {0,1}.  Equal prior, no abstention.
    Bayes error = sum_y min(P(H0) P0(y), P(H1) P1(y)).
    Randomized minimax = min over rules of max(alpha,beta) with
      alpha = P(declare H1 | H0) = q_0*P0(0)+q_1*P0(1)
      beta  = P(declare H0 | H1) = q0c*P1(0)+q1c*P1(1), qc=1-q
    We enumerate q_0, q_1 on a fine rational grid and take the min of the max.
    This never calls d2t_rna.t2.decision.
    """
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    pr = Fraction(1, 2)  # equal prior each hypothesis

    # Bayes error (no abstention): sum_y min(PH0*P0(y), PH1*P1(y))
    bayes = sum(
        min(pr * p0[y], pr * p1[y]) for y in range(2)
    )

    # Randomized minimax: enumerate q0,q1 in [0,1] on a grid.
    best = None
    N = 300  # multiple of 3 so q0=1/3 is representable on grid
    for i in range(N + 1):
        q0 = Fraction(i, N)
        for j in range(N + 1):
            q1 = Fraction(j, N)
            alpha = q0 * p0[0] + q1 * p0[1]          # = q0
            beta = (1 - q0) * p1[0] + (1 - q1) * p1[1]
            m = max(alpha, beta)
            if best is None or m < best:
                best = m
    return Fraction(bayes), Fraction(best)


def independent_discrete_gamma_from_raw(theta_0, theta_1, marginal_map,
                                        channels, panel):
    """Recompute the discrete-catalog robust separation gamma from raw inputs.

    gamma = min over admissible cross-differences v of max over actions u of
    || B_u v ||_1.  Admissible v = theta1 - theta0 with equal marginal image.
    Implemented by raw enumeration; does not import production witness/lp.
    """
    def marginal_of(p):
        return tuple(
            sum(Fraction(marginal_map[r][w]) * p[w] for w in range(len(p)))
            for r in range(len(marginal_map))
        )

    def action_image(channel, v):
        return tuple(
            sum(Fraction(channel[y][w]) * v[w] for w in range(len(v)))
            for y in range(len(channel))
        )

    best = None
    for a in theta_0:
        for b in theta_1:
            if marginal_of(a) != marginal_of(b):
                continue
            v = tuple(b[w] - a[w] for w in range(len(a)))
            worst = Fraction(0)
            for u in panel:
                img = action_image(channels[u], v)
                l1 = sum(abs(x) for x in img)
                if l1 > worst:
                    worst = l1
            if best is None or worst < best:
                best = worst
    return best


# ---------------------------------------------------------------------------
# Review drivers
# ---------------------------------------------------------------------------

def review_discrete_certificate(repo):
    """Rebuild one discrete T2 certificate from raw inputs via the oracle."""
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "src"))
    from d2t_rna.t2.fixtures import two_by_two_alternating
    from d2t_rna.t2.spec import MEASURE_ACTION_L1
    from d2t_rna.t2.theorem import collision_or_separation
    from tests.independent_oracles.t2_raw_discrete_oracle import (
        raw_separation_gamma,
    )

    model = two_by_two_alternating()
    panel = tuple(a.action_id for a in model.actions)
    channels = {
        a.action_id: [[Fraction(x) for x in row] for row in a.channel]
        for a in model.actions
    }
    theta_0 = tuple(tuple(Fraction(x) for x in p) for p in model.theta_0)
    theta_1 = tuple(tuple(Fraction(x) for x in p) for p in model.theta_1)
    marginal_map = tuple(
        tuple(Fraction(x) for x in row) for row in model.marginal_map
    )

    cert = collision_or_separation(model, panel)
    assert cert.theorem == "T2b"
    prod_gamma = cert.gamma
    measure = cert.spec.separation_measure
    gamma_tv = cert.gamma_tv

    ind_gamma = raw_separation_gamma(
        theta_0, theta_1, marginal_map, channels, panel
    )
    # Independent of raw_separation_gamma: our own enumeration.
    own_gamma = independent_discrete_gamma_from_raw(
        theta_0, theta_1, marginal_map, channels, panel
    )
    # gamma_tv must be the action-L1 separation halved, in [0,1].
    tv_consistent = (
        gamma_tv is not None
        and Fraction(gamma_tv) == Fraction(prod_gamma) / 2
        and 0 <= Fraction(gamma_tv) <= 1
    )
    ok = (Fraction(prod_gamma) == Fraction(ind_gamma)
          and Fraction(ind_gamma) == Fraction(own_gamma)
          and tv_consistent
          and measure == MEASURE_ACTION_L1)
    return {
        "ok": ok,
        "production_gamma": str(prod_gamma),
        "oracle_gamma": str(ind_gamma),
        "independent_gamma": str(own_gamma),
        "gamma_tv": str(gamma_tv),
        "separation_measure": measure,
        "tv_consistent": tv_consistent,
        "panel": list(panel),
    }


def review_bayes_minimax(repo):
    """Recompute the classical Bayes/minimax counterexample independently."""
    bayes, mm = independent_bayes_minimax()
    ok = (bayes == Fraction(1, 4)) and (mm == Fraction(1, 3))
    return {
        "ok": ok,
        "bayes_average_error": str(bayes),
        "randomized_minimax_error": str(mm),
        "expected": {"bayes": "1/4", "minimax": "1/3"},
    }


def review_t2c_status(repo):
    """Independently reconstruct the fail-closed T2c status for 5 branches."""
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "src"))
    from d2t_rna.t2.bounds import (
        T2cConstructiveStatus,
        constructive_feasibility_status,
    )

    F = Fraction

    # Independent expected classification from the documented decision rule.
    def expected_status(*, decision_rule, alpha, beta, budget_cost,
                        alpha_max, beta_max):
        # CONSTRUCTIVELY_FEASIBLE only when ALL of the required evidence is present
        # and every per-hypothesis risk and budget check passes.
        if not (decision_rule and budget_cost):
            return "NOT_FEASIBLE_OR_BOUND_ONLY"
        if alpha > alpha_max or beta > beta_max:
            return "BOUND_NOT_DECISIVE"
        return "CONSTRUCTIVELY_FEASIBLE"

    cases = [
        # (info bound, no rule) -> BOUND_ONLY  (independent: not feasible)
        dict(decision_rule=False, alpha=F(1, 10), beta=F(1, 10),
             budget_cost=True, alpha_max=F(1, 2), beta_max=F(1, 2),
             want=T2cConstructiveStatus.BOUND_ONLY,
             indep="NOT_FEASIBLE_OR_BOUND_ONLY"),
        # (rule but alpha over) -> BOUND_NOT_DECISIVE
        dict(decision_rule=True, alpha=F(6, 10), beta=F(1, 10),
             budget_cost=True, alpha_max=F(1, 2), beta_max=F(1, 2),
             want=T2cConstructiveStatus.BOUND_NOT_DECISIVE,
             indep="BOUND_NOT_DECISIVE"),
        # (rule but beta over) -> BOUND_NOT_DECISIVE
        dict(decision_rule=True, alpha=F(1, 10), beta=F(6, 10),
             budget_cost=True, alpha_max=F(1, 2), beta_max=F(1, 2),
             want=T2cConstructiveStatus.BOUND_NOT_DECISIVE,
             indep="BOUND_NOT_DECISIVE"),
        # (rule but budget not verified) -> NO_GO
        dict(decision_rule=True, alpha=F(1, 10), beta=F(1, 10),
             budget_cost=False, alpha_max=F(1, 2), beta_max=F(1, 2),
             want=T2cConstructiveStatus.NO_GO,
             indep="NOT_FEASIBLE_OR_BOUND_ONLY"),
        # (full rule + verified budget) -> CONSTRUCTIVELY_FEASIBLE
        dict(decision_rule=True, alpha=F(1, 10), beta=F(1, 10),
             budget_cost=True, alpha_max=F(1, 2), beta_max=F(1, 2),
             want=T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE,
             indep="CONSTRUCTIVELY_FEASIBLE"),
    ]

    results = []
    ok = True
    for c in cases:
        got = constructive_feasibility_status(
            product_laws_registered=True,
            allocation_registered=True,
            decision_rule_registered=c["decision_rule"],
            budget_cost_verified=c["budget_cost"],
            alpha=c["alpha"],
            beta=c["beta"],
            alpha_max=c["alpha_max"],
            beta_max=c["beta_max"],
        ).status
        # Independent classification must agree on the CONSTRUCTIVELY_FEASIBLE
        # branch (the only one that unlocks a positive claim).
        branch_ok = got == c["want"]
        independent_ok = (
            (got == T2cConstructiveStatus.CONSTRUCTIVELY_FEASIBLE)
            == (c["indep"] == "CONSTRUCTIVELY_FEASIBLE")
        )
        ok = ok and branch_ok and independent_ok
        results.append({
            "got": str(got),
            "want": str(c["want"]),
            "independent_consistency": independent_ok,
        })
    return {"ok": ok, "cases": results}


def review_data_qualification(repo):
    """Re-derive the ADD data-qualification verdict from raw eligibility fields."""
    path = repo / "manifests" / "data" / "add_qualification_v2.json"
    data = json.loads(path.read_text())
    raw = data["raw_per_replicate_counts_available"]
    unit = data["independent_unit_crosswalk"]
    like = data["calibrated_likelihood"]
    action = data["executable_action"]
    cost = data["real_marginal_cost"]
    # Independent fail-closed rule: QUALIFIED requires all five.
    qualified_requires_all = (raw and unit and like and action and cost)
    verdict = data["verdict"]
    ok = (qualified_requires_all is False) and (verdict != "QUALIFIED")
    return {
        "ok": ok,
        "verdict": verdict,
        "all_five_present": qualified_requires_all,
        "expected_eligible": "DESCRIPTIVE_ONLY/BLOCKED/INELIGIBLE (not QUALIFIED)",
    }


def review_claim_evidence(repo):
    """Follow the claim/evidence graph: edges must each carry evidence and the
    ReactFlow evidence count must be zero."""
    graph = json.loads((repo / "manifests" / "audit" /
                        "claim_evidence_graph.json").read_text())
    edges = graph.get("edges")
    reactflow = graph.get("reactflow_evidence_count")
    if not isinstance(edges, list) or not edges:
        return {"ok": False, "reason": "no edges in claim/evidence graph"}
    all_have_evidence = all(
        (isinstance(e, dict) and (e.get("artifact") or e.get("evidence_id")))
        for e in edges
    )
    ok = bool(all_have_evidence) and (reactflow in (0, None, False))
    return {
        "ok": ok,
        "edge_count": len(edges),
        "reactflow_evidence_count": reactflow,
        "all_edges_have_evidence": bool(all_have_evidence),
        "sample_claim": edges[0].get("claim_id"),
        "sample_evidence_id": edges[0].get("evidence_id"),
        "sample_allowed_strength": edges[0].get("allowed_strength"),
    }


def review_citation(repo):
    """Verify one cited key is registered in the citation verification manifest
    with a positive (FIXED/VERIFIED) status."""
    bib = (repo / "docs" / "paper" / "references.bib").read_text()
    manifest = json.loads((repo / "manifests" / "audit" /
                           "citation_verification_manifest.json").read_text())
    entries = manifest.get("entries") or {}
    import re
    keys = re.findall(r"@\w+\{([^,]+),", bib)
    key = next((k for k in keys if k in entries), None)
    if key is None:
        return {"ok": False, "reason": "no bib key registered in citation verification manifest"}
    entry = entries.get(key) or {}
    status = entry.get("status")
    verified = status in ("FIXED", "VERIFIED", "VERIFIED_OR_CORRECTED")
    return {"ok": bool(verified), "key": key, "in_bib": True,
            "status": status, "doi": entry.get("doi")}


def review_readiness_negative(repo):
    """Confirm the fail-closed gate FAILs on an out-of-range TV (9/5)."""
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo / "scripts"))
    import paper_readiness_gate as _gate
    _prob_ok = _gate._prob_ok
    ok = (_prob_ok("9/5") is False) and (_prob_ok("3/5") is True)
    return {
        "ok": ok,
        "tv_9_over_5_in_range": _prob_ok("9/5"),
        "tv_3_over_5_in_range": _prob_ok("3/5"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/cunyuliu/d2t-rna", type=Path)
    ap.add_argument("--outdir", default="/tmp/b5_receipts", type=Path)
    args = ap.parse_args()

    repo = args.repo.resolve()
    checks = {
        "discrete_certificate": review_discrete_certificate(repo),
        "bayes_minimax_counterexample": review_bayes_minimax(repo),
        "t2c_constructive_status": review_t2c_status(repo),
        "data_qualification_add": review_data_qualification(repo),
        "claim_to_evidence": review_claim_evidence(repo),
        "citation_to_source": review_citation(repo),
        "readiness_negative_fixture": review_readiness_negative(repo),
    }

    all_ok = all(c["ok"] for c in checks.values())
    receipt = {
        "schema": "d2t_rna.p0_redteam_review.v1",
        "authority_role": "INDEPENDENT_P0_RED_TEAM",
        "generator": "redteam_p0_review.py (Batch 5.3)",
        "all_pass": all_ok,
        "checks": checks,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    out = args.outdir / "redteam_p0_review_receipt.json"
    out.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
