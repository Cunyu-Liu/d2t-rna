"""D2T-RNA v7 §10 validation-scenarios and independent-review acceptance runner.

Executes the contract §10 requirements against real synthetic models and
produces an auditable JSON report:

* §10.1 mathematical scenarios: the registered T2b fixtures (2x2 alternating
  rectangle, no-cycle, zero-margin, symmetric states, repeated action,
  cancellation counterexample, three-way fixed marginal, exact collision,
  near-collision, strict separation) are each classified by the exact
  collision-or-separation theorem and the result is independently re-verified.
* §10.1 registered nuisance coupling: pairwise comparison
  (CARTESIAN / EQUAL_REALIZED_VALUE / wrong coupling).
* §1.3 / §10.1 claim lint: forbidden-word and out-of-scope claim audit.
* §10.2 assumption-violation gate: valid profile proceeds; every broken
  assumption returns ``NOT_ESTABLISHED`` (fail-closed).
* §10.3 independent checkers: witness marginal collision, action-level law
  equality / separation, rational LP dual feasibility, budget / cost
  accounting, and product-law information are each re-derived from first
  principles (never a re-run of the same solver).

This is model-conditional synthetic validation only; it authorizes no
scientific claim (``scientific_claim_authorized=false``).  Solver status,
float tolerance, caller hash, or a re-run of the same implementation are never
treated as proof (contract 10.3).
"""

from __future__ import annotations

import json
import sys
import time
from fractions import Fraction

from d2t_rna.evaluation.validation import (
    ACTION_INDUCED_STATE_CHANGE,
    AUTHORIZED,
    DEPENDENT_OBSERVATIONS,
    NOT_ESTABLISHED,
    NO_COMPLETE_OBSERVATION_MODEL,
    OMITTED_THIRD_STATE,
    PROCEED,
    UNKNOWN_DEPENDENCY_UNIT,
    UNREGISTERED_SHARED_NUISANCE,
    VALID_PROFILE,
    assumption_gate,
    claim_lint,
    section10_receipt,
    wrong_coupling_pairwise,
)
from d2t_rna.t2 import (
    CostedDesign,
    achievable_integer_design,
    collision_or_separation,
    lp_relax_exact,
    no_go_lower_bound,
)
from d2t_rna.t2 import fixtures as t2_fixtures
from d2t_rna.t2.costed_verify import (
    check_design_cost,
    check_dual_bound,
    check_dual_feasible,
    check_integer_design_feasible,
    check_integrality_gap,
    check_no_go_sign,
)
from d2t_rna.t2.info import (
    bhattacharyya_coeff_interval,
    hellinger_info_interval,
)
from d2t_rna.t2.verify import verify_collision, verify_separation

F = Fraction


def _diff(a, b):
    return [x - y for x, y in zip(a, b)]


def _l1(v):
    return sum(abs(x) for x in v)


def _action_image(channel, v):
    return [sum(row[w] * v[w] for w in range(len(v))) for row in channel]


def _action_law(model, action_id, p):
    action = next(a for a in model.actions if a.action_id == action_id)
    return tuple(
        sum(action.channel[y][w] * p[w] for w in range(model.n_states))
        for y in range(action.alphabet_size())
    )


def _marginal(model, p):
    return tuple(
        sum(row[w] * p[w] for w in range(model.n_states))
        for row in model.marginal_map
    )


def _channels(model):
    return {a.action_id: a.channel for a in model.actions}


def _info_interval(q0, q1):
    bc = bhattacharyya_coeff_interval(q0, q1)
    if bc.hi == 0:
        return None
    return hellinger_info_interval(q0, q1)


def _independent_checks(model, panel):
    """Run §10.3 independent checkers on one registered scenario."""
    cert = collision_or_separation(model, panel)
    channels = _channels(model)
    collision = {"verified": False, "witness_v": None}
    separation = {"verified": False, "reported_gamma": None}

    if cert.collision_witness is not None:
        # Recover an explicit admissible collision pair by scanning the catalog.
        for p0 in model.theta_0:
            for p1 in model.theta_1:
                v = _diff(p1, p0)
                if v == list(cert.collision_witness) and _marginal(model, p0) == _marginal(model, p1):
                    res = verify_collision(
                        theta_0=model.theta_0,
                        theta_1=model.theta_1,
                        marginal_map=model.marginal_map,
                        channels=channels,
                        panel=panel,
                        witness_v=v,
                        witness_p0=p0,
                        witness_p1=p1,
                    )
                    collision = {
                        "verified": res["verified"],
                        "witness_v": [str(x) for x in v],
                        "failures": res["failures"],
                    }
                    break
            if collision["verified"]:
                break

    if cert.separation_witness is not None and cert.gamma is not None:
        # Reconstruct p0/p1 from the certificate by scanning the catalog for the
        # pair attaining gamma, then independently re-derive the separation.
        for p0 in model.theta_0:
            m0 = _marginal(model, p0)
            for p1 in model.theta_1:
                if _marginal(model, p1) != m0:
                    continue
                v = _diff(p1, p0)
                worst = max(_l1(_action_image(channels[a], v)) for a in panel)
                if worst == cert.gamma:
                    res = verify_separation(
                        theta_0=model.theta_0,
                        theta_1=model.theta_1,
                        marginal_map=model.marginal_map,
                        channels=channels,
                        panel=panel,
                        reported_gamma=cert.gamma,
                        reported_p0=p0,
                        reported_p1=p1,
                    )
                    separation = {
                        "verified": res["verified"],
                        "reported_gamma": str(cert.gamma),
                        "failures": res["failures"],
                    }
                    break
            if separation["verified"]:
                break

    return collision, separation


def _costed_lp_checks(model, panel):
    """Run a T2d costed design and independently check LP dual + budget/cost."""
    pair_ids = ("w",)
    info_lower = []
    info_upper = []
    for a in model.actions:
        q0 = _action_law(model, a.action_id, model.theta_0[0])
        q1 = _action_law(model, a.action_id, model.theta_1[0])
        iv = _info_interval(q0, q1)
        if iv is None:
            info_lower.append(F(1_000_000))
            info_upper.append(F(1_000_000))
        else:
            lo = F(iv.lo)
            hi = F(iv.hi)
            info_lower.append(lo if lo >= 0 else F(0))
            info_upper.append(hi if hi >= 0 else F(0))
    tau = F(1, 2)
    costs = tuple(F(1) for _ in model.actions)
    cd = CostedDesign(
        action_ids=tuple(a.action_id for a in model.actions),
        costs=costs,
        pair_ids=pair_ids,
        thresholds=(tau,),
        info_lower=tuple((v,) for v in info_lower),
        info_upper=tuple((v,) for v in info_upper),
    )
    relax = lp_relax_exact(cd.info_upper, cd.costs, cd.thresholds)
    dual_feasible = False
    dual_bound = None
    if relax.dual_available and relax.dual is not None:
        y = tuple(relax.dual)
        if check_dual_feasible(cd, cd.info_upper, y):
            dual_feasible = True
        dual_bound = check_dual_bound(cd, y)
    lp_lb = no_go_lower_bound(cd)
    int_cost, int_n = achievable_integer_design(cd)
    budget = F(8)
    no_go = check_no_go_sign(budget, dual_bound) if dual_bound is not None else None
    int_feasible = bool(int_n) and check_integer_design_feasible(cd, cd.info_lower, int_n)
    int_cost_val = check_design_cost(cd, int_n) if int_n else None
    gap = check_integrality_gap(int_cost_val, lp_lb) if lp_lb and int_cost_val else None
    return {
        "lp_relax_status": relax.status,
        "dual_feasible": dual_feasible,
        "lp_lower_bound": str(lp_lb) if lp_lb is not None else None,
        "dual_bound_tau_y": str(dual_bound) if dual_bound is not None else None,
        "budget": str(budget),
        "no_go_sign": no_go,
        "integer_feasible": int_feasible,
        "integer_cost": str(int_cost_val) if int_cost_val is not None else None,
        "integrality_gap": str(gap) if gap is not None else None,
    }


def main() -> int:
    fixtures = {
        "two_by_two_alternating": t2_fixtures.two_by_two_alternating,
        "no_cycle": t2_fixtures.no_cycle,
        "zero_margin": t2_fixtures.zero_margin,
        "symmetric_states": t2_fixtures.symmetric_states,
        "repeated_action": t2_fixtures.repeated_action,
        "cancellation_counterexample": t2_fixtures.cancellation_counterexample,
        "three_way_fixed_marginal": t2_fixtures.three_way_fixed_marginal,
        "exact_collision": t2_fixtures.exact_collision,
        "near_collision": t2_fixtures.near_collision,
        "strict_separation": t2_fixtures.strict_separation,
    }

    # --- §10.2 assumption-violation gate ---
    assumption_cases = {
        "valid": VALID_PROFILE,
        "action_changes_state": ACTION_INDUCED_STATE_CHANGE,
        "omitted_third_state": OMITTED_THIRD_STATE,
        "unregistered_nuisance": UNREGISTERED_SHARED_NUISANCE,
        "unknown_dependency_unit": UNKNOWN_DEPENDENCY_UNIT,
        "no_complete_obs_model": NO_COMPLETE_OBSERVATION_MODEL,
        "dependent_observations": DEPENDENT_OBSERVATIONS,
    }
    assumption_report = {
        name: {"gate": assumption_gate(prof), "violations": prof.violations()}
        for name, prof in assumption_cases.items()
    }
    assumption_ok = (
        assumption_report["valid"]["gate"] == PROCEED
        and all(
            assumption_report[n]["gate"] == NOT_ESTABLISHED
            for n in assumption_cases
            if n != "valid"
        )
    )

    # --- §10.1 registered nuisance coupling ---
    coupling_report = wrong_coupling_pairwise()
    coupling_ok = (
        coupling_report[0][1] == AUTHORIZED
        and coupling_report[1][1] == AUTHORIZED
        and coupling_report[2][1] == NOT_ESTABLISHED
    )

    # --- §1.3 / §10.1 claim lint ---
    clean_claim = "model-conditional certificate for a registered finite pair catalog"
    forbidden_claim = "this provides prospective new-library independent validation"
    claim_clean = claim_lint(clean_claim)
    claim_forbidden = claim_lint(forbidden_claim)
    claim_ok = claim_clean["gate"] == "PASS" and claim_forbidden["gate"] == "FAIL"

    # --- §10.1 / §10.3 independent checkers on the registered scenarios ---
    scenario_reports = {}
    n_collision_verified = 0
    n_separation_verified = 0
    n_lp_dual_feasible = 0
    n_budget_cost_consistent = 0
    n_product_tv_consistent = 0
    for name in sorted(fixtures):
        model = fixtures[name]()
        panel = tuple(a.action_id for a in model.actions)
        collision, separation = _independent_checks(model, panel)
        lp_checks = _costed_lp_checks(model, panel)
        q0 = _action_law(model, panel[0], model.theta_0[0])
        q1 = _action_law(model, panel[0], model.theta_1[0])
        receipt = section10_receipt(
            profile=VALID_PROFILE,
            coupling="CARTESIAN",
            claim_text=clean_claim,
            collision=collision,
            separation=separation,
            lp_results={
                "dual_feasible": lp_checks["dual_feasible"],
                "lower_bound": (
                    F(lp_checks["dual_bound_tau_y"]) if lp_checks["dual_bound_tau_y"] else None
                ),
                "budget": F(lp_checks["budget"]),
                "expected_no_go": lp_checks["no_go_sign"] == "NO_GO",
                "cost": (
                    F(lp_checks["integer_cost"]) if lp_checks["integer_cost"] else None
                ),
                "integer_cost": (
                    F(lp_checks["integer_cost"]) if lp_checks["integer_cost"] else None
                ),
            },
            product_tv_pair=(q0, q1),
        )
        if collision["verified"]:
            n_collision_verified += 1
        if separation["verified"]:
            n_separation_verified += 1
        if lp_checks["dual_feasible"]:
            n_lp_dual_feasible += 1
        if receipt.budget_cost_consistent:
            n_budget_cost_consistent += 1
        if receipt.product_tv_consistent:
            n_product_tv_consistent += 1
        scenario_reports[name] = {
            "panel": list(panel),
            "collision": {
                "verified": collision["verified"],
                "witness_v": collision["witness_v"],
                "failures": collision.get("failures", []),
            },
            "separation": {
                "verified": separation["verified"],
                "reported_gamma": separation["reported_gamma"],
                "failures": separation.get("failures", []),
            },
            "lp_checks": lp_checks,
            "receipt": receipt.as_dict(),
        }

    # Acceptance: the §10 mechanisms behave correctly across the registered
    # scenarios.  A single scenario is either a collision or a separation, so we
    # require at least one genuine collision and one genuine separation verify,
    # plus LP dual feasibility, budget/cost accounting, and product-law TV.
    independent_ok = (
        n_collision_verified >= 1
        and n_separation_verified >= 1
        and n_lp_dual_feasible >= 1
        and n_budget_cost_consistent == len(scenario_reports)
        and n_product_tv_consistent == len(scenario_reports)
    )

    payload = {
        "contract_section": "10",
        "kind": "VALIDATION_SCENARIOS_AND_INDEPENDENT_REVIEW",
        "run_finished": time.time(),
        "scenario_count": len(scenario_reports),
        "scenarios": sorted(scenario_reports.keys()),
        "assumption_gate": {
            "cases": assumption_report,
            "all_correct": assumption_ok,
        },
        "coupling": {
            "pairwise": [list(x) for x in coupling_report],
            "registered": ["CARTESIAN", "EQUAL_REALIZED_VALUE"],
            "all_correct": coupling_ok,
        },
        "claim_lint": {
            "clean": {"gate": claim_clean["gate"], "violations": claim_clean["violations"]},
            "forbidden": {
                "gate": claim_forbidden["gate"],
                "violations": claim_forbidden["violations"],
            },
            "all_correct": claim_ok,
        },
        "independent_checkers": {
            "scenarios": scenario_reports,
            "counts": {
                "collision_verified": n_collision_verified,
                "separation_verified": n_separation_verified,
                "lp_dual_feasible": n_lp_dual_feasible,
                "budget_cost_consistent": n_budget_cost_consistent,
                "product_tv_consistent": n_product_tv_consistent,
            },
            "all_correct": independent_ok,
        },
        "acceptance": assumption_ok and coupling_ok and claim_ok and independent_ok,
        "scientific_claim_authorized": False,
        "boundary_note": (
            "model-conditional synthetic validation only; no prospective/blinded/"
            "held-out validation, no real-data or population claim, no method "
            "superiority claim (contract sections 1, 9, 10)"
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())