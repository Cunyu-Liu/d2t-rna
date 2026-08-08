"""D2T-RNA v7 §12 Phase 5 mechanism-analysis unit tests.

Validates the mechanism report built from the *frozen* Phase 4 scale grid:
worst-case ordering, action-contribution cost-sensitivity, the
necessary/sufficient gap, the abstention/error partition, and the
claim--evidence map.  Model-conditional synthetic only; no scientific claim.
"""

from __future__ import annotations

from fractions import Fraction

from scripts.t2_mechanism_run import (
    _analyze,
    _build_claim_evidence_map,
    _F,
)


def _sample_rows() -> list[dict]:
    """A minimal frozen-grid-like fixture exercising every analysis branch."""
    base = {
        "name": "s2_2x2",
        "panel": ["id_a", "id_b"],
        "budget": "4",
        "cost_mode": "uniform",
        "oracle_minimax_error": "5/32",
        "min_cost_at_oracle_error": "3",
        "oracle_beaten_by": [],
        "baseline_over_cost_vs_min": {
            "chernoff": "1",
            "eig": "1",
            "full_matrix": "1",
            "greedy_test_cover": "1",
            "lm2r_heuristic": "1",
            "random": "1",
            "t2_integer_lp": "1",
        },
        "baselines": {
            "exhaustive_oracle": {
                "executed": True,
                "spent_exceeds_budget": False,
                "correct_decl": "27/32",
                "abstain": "0",
            },
            "t2_integer_lp": {
                "executed": True,
                "spent_exceeds_budget": False,
                "correct_decl": "27/32",
                "abstain": "0",
                "integer_upper_cost": "4",
                "lp_lower_bound": "3",
            },
        },
    }
    uni = dict(base)
    uni["cost_mode"] = "uniform"
    uni["min_cost_allocation"] = [3, 0]
    het = dict(base)
    het["cost_mode"] = "hetero"
    het["min_cost_allocation"] = [0, 3]
    return [uni, het]


def test_worst_case_ordering_sorts_by_oracle_error():
    rows = _sample_rows()
    a = _analyze(rows)
    errs = [
        _F(x["oracle_minimax_error"])
        for x in a["worst_case_by_oracle_error"]
    ]
    assert errs == sorted(errs, reverse=True)


def test_action_contribution_detects_cost_sensitivity():
    rows = _sample_rows()
    a = _analyze(rows)
    # both rows are the same 2-action cell under different cost modes
    entries = list(a["action_contribution_by_cell"].values())[0]
    allocs = {tuple(e["min_cost_allocation"]) for e in entries}
    assert len(allocs) == 2, "uniform vs hetero should give different allocations"


def test_necessary_sufficient_gap_is_non_negative():
    rows = _sample_rows()
    a = _analyze(rows)
    for g in a["necessary_sufficient_gap"]:
        assert g["gap"] is not None
        assert _F(g["gap"]) >= 0


def test_error_decomposition_is_partition():
    rows = _sample_rows()
    a = _analyze(rows)
    # every decomposition record satisfies correct + wrong + abstain = 1
    for rec in a["abstention_error_decomposition"]:
        correct = _F(rec["correct_decl"])
        wrong = _F(rec["wrong_decl"])
        abstain = _F(rec["abstain"])
        assert correct + wrong + abstain == _F(1)
        assert rec["minimax_error"] == str((wrong + abstain) / 2)


def test_claim_evidence_map_links_each_claim_to_evidence():
    rows = _sample_rows()
    a = _analyze(rows)
    m = _build_claim_evidence_map(rows, a)
    assert len(m) == 4
    for claim in m.values():
        assert "claim" in claim and "evidence" in claim
        assert claim["known_public_mechanism"] is False
    assert m["oracle_never_beaten_over_frozen_grid"]["evidence"][
        "oracle_never_beaten"
    ] is True
    assert m["necessary_sufficient_gap_certified"]["evidence"][
        "gap_non_negative"
    ] is True