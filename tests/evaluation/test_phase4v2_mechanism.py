"""P1 6.6: Phase5-v2 mechanism-analysis semantics tests.

Verifies the Phase5-v2 mechanism report over the corrected Phase4-v2 grid
using an injected synthetic artifact (no heavy oracle recompute):

* primary metric copied verbatim from the evaluator (no re-scaling);
* oracle never beaten over the whole grid;
* cost-sensitivity interpretation lock
  (``PRICE_SUBSTITUTION_OR_TIE_CONTROL`` when allocation shifts but error is
  identical);
* necessary/sufficient gap from the T2 integer design (LP lower bound vs
  achievable integer upper cost);
* claim-evidence map binding every claim to pair/cell/source SHA;
* legacy Phase 5 explicitly marked ``INVALID_SUPERSEDED``.
"""

from __future__ import annotations

import json
import pathlib

from scripts.t2_phase4v2_mechanism import (
    _analyze,
    _build_claim_evidence_map,
    main,
)


def _baseline(minimax='1/4', allocation=None, lp_lb=None, int_cost=None):
    b = {'minimax_error': minimax}
    if allocation is not None:
        b['allocation'] = allocation
    if lp_lb is not None:
        b['lp_lower_bound'] = lp_lb
    if int_cost is not None:
        b['integer_upper_cost'] = int_cost
    return b


def _cell(pair, budget, cost_mode, oracle_err='1/4',
          alloc_u=None, alloc_h=None):
    # oracle allocation depends on cost mode; default: uniform/hetero differ
    alloc = alloc_h if cost_mode == 'hetero' else alloc_u
    return {
        'pair_id': pair,
        'budget': budget,
        'cost_mode': cost_mode,
        'oracle_minimax_error': oracle_err,
        'oracle_beaten_by': [],
        'baselines': {
            'exhaustive_oracle': _baseline(oracle_err, allocation=alloc),
            'full_matrix': _baseline('1/4'),
            'random': _baseline('1/2'),
            'greedy_test_cover': _baseline('1/3'),
            'eig': _baseline('1/3'),
            'chernoff': _baseline('1/3'),
            'lm2r_heuristic': _baseline('1/3'),
            't2_integer_lp': _baseline('1/4', lp_lb='1', int_cost='3'),
        },
    }


def _make_artifact(tmp_path: pathlib.Path) -> pathlib.Path:
    cells = [
        # CA_p1: uniform vs hetero allocation shift at same error -> tie control
        _cell('CA_p1', '4', 'uniform', alloc_u=['1', '3'], alloc_h=['2', '2']),
        _cell('CA_p1', '4', 'hetero', alloc_u=['1', '3'], alloc_h=['2', '2']),
        # CB_p1: allocation identical across cost modes -> no shift
        _cell('CB_p1', '8', 'uniform', alloc_u=['2', '6'], alloc_h=['2', '6']),
        _cell('CB_p1', '8', 'hetero', alloc_u=['2', '6'], alloc_h=['2', '6']),
    ]
    artifact = {
        'schema': 'd2t_rna.v7_phase4v2.v1',
        'n_cells': len(cells),
        'cells': cells,
    }
    p = tmp_path / 'phase4v2.json'
    p.write_text(json.dumps(artifact))
    return p


def test_oracle_never_beaten(tmp_path):
    a = _analyze(_make_artifact(tmp_path))
    assert a['oracle_never_beaten'] is True
    assert a['oracle_beaten_cells'] == []


def test_cost_sensitivity_price_substitution_tie_control(tmp_path):
    a = _analyze(_make_artifact(tmp_path))
    sens = a['cost_sensitivity']
    by_pair = {s['pair_id']: s for s in sens}
    s = by_pair['CA_p1']
    assert s['alloc_shift'] is True
    assert s['error_identical'] is True
    assert s['interpretation'] == 'PRICE_SUBSTITUTION_OR_TIE_CONTROL'
    # CB_p1 does not shift -> no tie-control lock
    s2 = by_pair['CB_p1']
    assert s2['alloc_shift'] is False


def test_necessary_sufficient_gap_present(tmp_path):
    a = _analyze(_make_artifact(tmp_path))
    gaps = a['necessary_sufficient_gap']
    assert len(gaps) == 4
    g = gaps[0]
    # lp_lower_bound=1, integer_upper_cost=3 -> gap = 2 > 0
    assert g['lp_lower_bound'] == '1'
    assert g['integer_upper_cost'] == '3'
    assert g['gap'] == '2'
    cm = _build_claim_evidence_map(a)
    assert cm['necessary_sufficient_gap_exists']['status'] == 'CONFIRMED_FACT'


def test_primary_metric_copied_verbatim(tmp_path):
    a = _analyze(_make_artifact(tmp_path))
    # every cell's oracle error is copied verbatim (no re-scaling)
    for entry in a['primary_metric_verbatim']:
        assert entry['oracle_minimax_error'] in ('1/4',)
        # per-baseline minimax errors copied verbatim too
        assert entry['per_baseline_minimax_error']['chernoff'] == '1/3'


def test_claim_evidence_map_binds_to_source(tmp_path):
    a = _analyze(_make_artifact(tmp_path))
    cm = _build_claim_evidence_map(a)
    for claim in cm.values():
        assert claim['evidence']['source'] == a['source_phase4v2_sha256']


def test_legacy_phase5_marked_invalid_superseded(tmp_path):
    p = _make_artifact(tmp_path)
    out = tmp_path / 'report.json'
    assert main(['--in', str(p), '--out', str(out)]) == 0
    report = json.loads(out.read_text())
    assert report['legacy_phase5_status'] == 'INVALID_SUPERSEDED'
    assert report['scientific_claim_authorized'] is False
