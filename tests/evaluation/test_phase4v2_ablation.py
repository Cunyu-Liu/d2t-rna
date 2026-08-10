"""P1 6.3: non-equivalent action ablation (12 cells) tests."""

from __future__ import annotations

import json
import pathlib
from fractions import Fraction

from scripts.t2_phase4v2_ablation import build_ablation_registry, run_all

REPO = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = REPO / 'manifests/audit/v7_p1_ablation_registry_v1.json'


def test_registry_has_12_cells_three_panels():
    d = json.loads(REGISTRY.read_text())
    assert d['schema'] == 'd2t_rna.v7_p1_ablation_registry.v1'
    assert d['payload']['n_cells'] == 12
    cells = d['payload']['cells']
    assert len(cells) == 12
    from collections import Counter
    per = Counter(c['panel_id'] for c in cells)
    assert set(per) == {'A_identical_control', 'B_crossing_informativeness', 'C_3state_identity_pair'}
    assert all(v == 4 for v in per.values())


def test_builder_deterministic():
    a = build_ablation_registry()
    b = build_ablation_registry()
    assert [c['cell_id'] for c in a] == [c['cell_id'] for c in b]


def test_identical_channel_control_is_price_substitution_only():
    data = run_all()
    cells = {c['cell_id']: c for c in data['cells']}
    # identical channels -> error identical under uniform vs hetero (cost only substitutes)
    u = cells['A_identical_control__b4_x_uniform']['oracle_minimax_error']
    h = cells['A_identical_control__b4_x_hetero']['oracle_minimax_error']
    assert u == h
    for c in data['cells']:
        if c['panel_id'] == 'A_identical_control':
            assert c['interpretation'] == 'PRICE_SUBSTITUTION_OR_TIE_CONTROL'
            assert c['oracle_beaten_by'] == []


def test_crossing_panel_risk_cost_tradeoff():
    data = run_all()
    cells = {c['cell_id']: c for c in data['cells']}
    # hetero cost (3,1) makes cheap low-info action favored -> error >= uniform
    u = Fraction(cells['B_crossing_informativeness__b4_x_uniform']['oracle_minimax_error'])
    h = Fraction(cells['B_crossing_informativeness__b4_x_hetero']['oracle_minimax_error'])
    assert h > u, 'expected hetero cost to raise error via risk-cost tradeoff'
    for c in data['cells']:
        if c['panel_id'] == 'B_crossing_informativeness':
            assert c['interpretation'] == 'NON_EQUIVALENT_ACTION_RISK_COST_TRADEOFF'
            assert c['oracle_beaten_by'] == []


def test_3state_identity_pair_non_isomorphic():
    data = run_all()
    for c in data['cells']:
        if c['panel_id'] == 'C_3state_identity_pair':
            assert c['interpretation'] == 'NON_EQUIVALENT_ACTION_CHANNEL_RANK'
            assert c['oracle_beaten_by'] == []


def test_oracle_never_beaten_all_12():
    data = run_all()
    assert data['n_cells'] == 12
    assert all(c['oracle_beaten_by'] == [] for c in data['cells'])
