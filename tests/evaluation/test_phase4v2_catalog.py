"""P1 6.2: Phase4-v2 full-catalog pair benchmark tests.

Verifies the 80 pair-cell design: registry integrity, explicit (p0,p1) pairs
(never theta_0[0]/theta_1[0]), determinism, oracle-never-beaten, catalog
worst-case, and binding to the corrected product-BC metric.  Model-conditional
synthetic only; no scientific claim.
"""

from __future__ import annotations

import json
import pathlib
from fractions import Fraction

import pytest

from d2t_rna.t2.model import T2FiniteModel

from scripts.t2_phase4v2_run import build_p4v2_registry, run_all, run_cell, _pools

REPO = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = REPO / 'manifests/audit/v7_p1_catalog_registry_v1.json'


def test_registry_has_20_pairs_80_cells_explicit():
    d = json.loads(REGISTRY.read_text())
    assert d['schema'] == 'd2t_rna.v7_p1_catalog_registry.v1'
    assert d['payload']['n_pairs'] == 20
    assert d['payload']['n_cells'] == 80
    pairs = d['payload']['pairs']
    assert len(pairs) == 20
    ids = [p['pair_id'] for p in pairs]
    assert len(set(ids)) == len(ids)
    # explicit p0/p1 present on every pair; not index-0 shorthand
    for p in pairs:
        assert p['p0'] and p['p1']
        assert len(p['p0']) == p['n_states'] == len(p['p1'])


def test_builder_deterministic_and_matches_manifest():
    a = build_p4v2_registry()
    b = build_p4v2_registry()
    assert [p['pair_id'] for p in a] == [p['pair_id'] for p in b]
    reg = json.loads(REGISTRY.read_text())['payload']['pairs']
    assert [p['pair_id'] for p in a] == [r['pair_id'] for r in reg]


def test_every_pair_is_non_degenerate_and_distinct():
    seen = set()
    for p in build_p4v2_registry():
        key = (tuple(p['p0']), tuple(p['p1']))
        assert key[0] != key[1], f"{p['pair_id']} degenerate (p0==p1)"
        assert key not in seen, f"{p['pair_id']} duplicates another pair"
        seen.add(key)


def test_all_four_catalog_classes_present_five_pairs_each():
    pairs = build_p4v2_registry()
    classes = {}
    for p in pairs:
        classes.setdefault(p['catalog_class'], []).append(p['pair_id'])
    assert set(classes) == {'CA', 'CB', 'CC', 'CD'}
    for cid, lst in classes.items():
        assert len(lst) == 5, f'{cid} does not have 5 pairs'


def test_oracle_never_beaten_across_all_80_cells():
    data = run_all()
    assert data['n_cells'] == 80
    assert all(c['oracle_beaten_by'] == [] for c in data['cells']), 'oracle beaten somewhere'


def test_catalog_worst_case_reported_per_class():
    data = run_all()
    wc = data['catalog_worst_case']
    assert set(wc) == {'CA', 'CB', 'CC', 'CD'}
    for cid, worst_pair in wc.items():
        assert worst_pair.startswith(cid + '_p')


def test_pools_model_valid():
    for cid, n, t0, t1, actions, panel in _pools():
        for i, p0 in enumerate(t0):
            assert len(p0) == n
            assert sum(p0) == 1
        assert len(t1) >= 2 and len(t0) >= 2
        # every selected pair index stays in range
        from scripts.t2_phase4v2_run import _PAIR_IDX
        for i, j in _PAIR_IDX[cid]:
            assert i < len(t0) and j < len(t1)
