"""P1 6.5: Phase4-v2 scalability reporting tests.

Verifies the engineering scaling-record semantics using an injected synthetic
cell dataset (no heavy oracle recompute):

* per-label coverage (fraction of cells executed OK within budget);
* runtime / peak-memory aggregates;
* LP/MIP dimension reporting for ``t2_integer_lp`` (U actions x W constraints);
* optimality gap computed from lp_lower_bound / integer_upper_cost;
* exact-oracle solvable boundary (cap-free within-budget allocation space);
* timeout / failure / withheld-certificate accounting is fail-closed and no
  number is fabricated for beyond-exact-scale instances.
"""

from __future__ import annotations

from fractions import Fraction

from scripts.t2_phase4v2_scalability import (
    BASELINE_LABELS,
    build_scalability_report,
    cell_scalability,
    exact_boundary,
)

from scripts.t2_phase4v2_run import build_p4v2_registry


def _run(lab, runtime=0.01, mem=1000, executed=True, over=False, err='1/4',
         lp_lb='2', int_cost='2'):
    e = {
        'executed': executed,
        'spent_exceeds_budget': over,
        'runtime_s': runtime,
        'memory_peak_bytes': mem,
        'minimax_error': err,
    }
    if lab == 't2_integer_lp':
        e['lp_lower_bound'] = lp_lb
        e['integer_upper_cost'] = int_cost
    return e


def _synthetic_data():
    pair = build_p4v2_registry()[0]  # CA_p1
    cells = []
    for i in range(4):
        over = (i == 3)  # last cell: t2_integer_lp exceeds budget -> fail-closed
        baselines = {lab: _run(lab) for lab in BASELINE_LABELS}
        if over:
            baselines['t2_integer_lp'] = _run(
                't2_integer_lp', over=True, int_cost=None)
        cells.append({
            'pair_id': pair['pair_id'],
            'catalog_class': pair['catalog_class'],
            'budget': '4',
            'cost_mode': 'uniform',
            'oracle_minimax_error': '1/4',
            'oracle_beaten_by': [],
            'baselines': baselines,
            'cell_elapsed_s': 0.1,
        })
    return {'cells': cells, 'n_cells': len(cells)}


def test_coverage_counts_executed_ok_only():
    report = build_scalability_report(_synthetic_data())
    cov = report['coverage']['t2_integer_lp']
    # 3 of 4 cells executed OK; 1 fail-closed (exceeds budget)
    assert cov['executed_ok_cells'] == 3
    assert cov['coverage'] == 3 / 4


def test_other_labels_full_coverage():
    report = build_scalability_report(_synthetic_data())
    for lab in ('exhaustive_oracle', 'full_matrix', 'random',
                'greedy_test_cover', 'eig', 'chernoff', 'lm2r_heuristic'):
        assert report['coverage'][lab]['coverage'] == 1.0


def test_runtime_and_memory_aggregates():
    report = build_scalability_report(_synthetic_data())
    assert report['runtime']['chernoff']['max_s'] == 0.01
    assert report['memory']['chernoff']['mean_bytes'] == 1000.0


def test_lp_dims_reported():
    report = build_scalability_report(_synthetic_data())
    # CA class uses 2-action panel -> 2 decision variables, 1 threshold
    dims = report['lp_dims_by_catalog_class']['CA']
    assert dims['n_decision_variables'] == 2
    assert dims['n_threshold_constraints'] == 1


def test_optimality_gap_zero_when_bounds_match():
    report = build_scalability_report(_synthetic_data())
    cell0 = report['cells'][0]['baselines']['t2_integer_lp']
    assert Fraction(cell0['optimality_gap']) == 0  # lp_lb == int_cost == 2


def test_exact_boundary_cap_free():
    pair = build_p4v2_registry()[0]
    # CA_p1 panel = 2 actions, uniform cost 1, budget 4 -> (4+1)*(4+1) = 25
    b = exact_boundary(pair, Fraction(4), 'uniform')
    assert b == 25


def test_beyond_exact_scale_not_asserted():
    report = build_scalability_report(_synthetic_data())
    assert report['exact_oracle_boundary']['beyond_exact_scale'] == \
        'UNKNOWN_NOT_ASSERTED'


def test_withheld_certificates_fail_closed():
    report = build_scalability_report(_synthetic_data())
    withheld = report['timeout_failure_withheld']['n_withheld_certificates']
    assert withheld == 1  # the fail-closed t2_integer_lp cell
