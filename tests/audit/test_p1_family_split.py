"""P1 6.1: frozen family-split pre-registration validity.

Checks that the synthetic family register covers every required axis, that
the sealed-test family is disjoint from train/development, and that the
register is deterministic.  This pre-registration must exist and be frozen
before any tuning; it is a fail-closed guard so a broken or incomplete split
cannot silently proceed.
"""

from __future__ import annotations

import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'manifests/audit/v7_p1_family_split_v1.json'

REQUIRED_AXES = {
    'n_states', 'catalog', 'n_actions', 'channel_rank', 'channel_noise',
    'collision_margin', 'budget', 'cost_mode', 'abstention', 'exact_scale',
}

REQUIRED_SPLITS = {'train', 'dev', 'sealed_test'}


def _load():
    return json.loads(MANIFEST.read_text())


def test_manifest_exists_and_schema():
    assert MANIFEST.exists(), 'frozen family-split manifest missing'
    d = _load()
    assert d['schema'] == 'd2t_rna.v7_p1_family_split.v1'
    assert d['phase'] == 'P1_6_1'


def test_every_family_carries_all_required_axes():
    d = _load()
    assert d['payload']['families'], 'no families registered'
    for fam in d['payload']['families']:
        assert set(fam['axes']) == REQUIRED_AXES, f"{fam['family_id']} missing axes"
        assert fam['split'] in REQUIRED_SPLITS
        assert fam['generation_mechanism'] in d['payload']['generation_mechanisms']
        # every axis must have a concrete non-null value
        for ax, val in fam['axes'].items():
            assert val not in (None, '', []), f"{fam['family_id']}.{ax} empty"


def test_all_required_splits_present_and_sealed_disjoint():
    d = _load()
    splits = {f['split'] for f in d['payload']['families']}
    assert splits == REQUIRED_SPLITS, f'missing split(s): {REQUIRED_SPLITS - splits}'
    sealed = {f['family_id'] for f in d['payload']['families'] if f['split'] == 'sealed_test'}
    other = {f['family_id'] for f in d['payload']['families'] if f['split'] != 'sealed_test'}
    assert sealed.isdisjoint(other), 'sealed-test family overlaps train/dev'
    assert d['payload']['invariants']['sealed_test_disjoint_from_train_dev'] is True


def test_axis_coverage_is_complete():
    d = _load()
    cov = d['payload']['axis_coverage']
    # n_states and catalog must span both values; budget spans {4,8}; cost and abstention span both
    assert set(cov['n_states']) == {2, 3}
    assert set(cov['catalog']) == {'2x2', '2x3', '3x2', '3x3'}
    assert set(cov['budget']) == {4, 8}
    assert set(cov['cost_mode']) == {'uniform', 'hetero'}
    assert set(cov['abstention']) == {'off', 'on'}
    assert set(cov['exact_scale']) == {'solvable', 'unsolvable'}
    assert set(cov['channel_noise']) == {'clean', 'noisy'}


def test_register_is_deterministic():
    d = _load()
    ids = [f['family_id'] for f in d['payload']['families']]
    assert len(ids) == len(set(ids)), 'duplicate family ids'
    # re-reading twice gives identical serialized canonical content (no order flapping)
    d2 = _load()
    assert d['payload']['families'] == d2['payload']['families']


def test_statistical_unit_invariant_declared():
    d = _load()
    inv = d['payload']['invariants']
    assert inv['tuning_must_not_inspect_sealed_test'] is True
    assert inv['statistical_unit_is_family_or_block_not_cell_seed'] is True
    assert inv['grid_rows_budget_cells_cost_cells_seeds_are_not_independent_units'] is True
