"""P1 6.7: Phase-1 success-state acceptance manifest integrity tests.

Verifies that ``v7_phase1_acceptance_v2.json`` records an honest, complete
Phase-1 success state:

* schema is the v2 acceptance schema;
* status is exactly one of the plan's separated success states
  (``SEMANTIC_SOFTWARE_SUCCESS``), and the comparative / real-data success
  states are NOT claimed;
* ``scientific_claim_authorized`` is ``false`` (model-conditional synthetic);
* every Phase-1 subsection (6.1-6.6) is bound to a manifest/artifact with a
  SHA-256;
* the non-trivial-capability claim does not overstate: closest-prior-art
  reduction is recorded PENDING (SOTA_NOT_ADJUDICATED), not asserted as fact.
"""

from __future__ import annotations

import json
import pathlib

REPO = pathlib.Path('/home/cunyuliu/d2t-rna')
MANIFEST = REPO / 'manifests/audit/v7_phase1_acceptance_v2.json'

ALLOWED_SUCCESS_STATES = {
    'SEMANTIC_SOFTWARE_SUCCESS',
    'COMPARATIVE_SYNTHETIC_SUCCESS',
    'REAL_RNA_CONFIRMATION_SUCCESS',
}


def _load() -> dict:
    assert MANIFEST.exists(), f'missing {MANIFEST}'
    return json.loads(MANIFEST.read_text())


def test_schema_and_status():
    d = _load()
    assert d['schema'] == 'd2t_rna.v7_phase1_acceptance.v2'
    assert d['status'] == 'SEMANTIC_SOFTWARE_SUCCESS'


def test_success_states_separated_and_not_overclaimed():
    d = _load()
    ss = d['success_states']
    assert set(ss) == ALLOWED_SUCCESS_STATES
    assert ss['SEMANTIC_SOFTWARE_SUCCESS'] == 'CLAIMED_P1_SYNTHETIC_BENCHMARK'
    assert ss['COMPARATIVE_SYNTHETIC_SUCCESS'].startswith('NOT_CLAIMED')
    assert ss['REAL_RNA_CONFIRMATION_SUCCESS'].startswith('NOT_CLAIMED')


def test_no_scientific_claim_authorized():
    d = _load()
    assert d['scientific_claim_authorized'] is False


def test_all_subsections_bound_with_sha256():
    d = _load()
    for key in ('6.1_family_split', '6.2_full_catalog_pair_benchmark',
                '6.3_non_equivalent_action_ablation',
                '6.4_comparable_only_baseline_suite',
                '6.5_scalability', '6.6_phase5v2_mechanism'):
        assert key in d['acceptance_criteria'], key
        crit = d['acceptance_criteria'][key]
        assert crit['result'] == 'PASS', key
        # each subsection binds at least one manifest or artifact sha256
        ev = crit['evidence']
        assert any(k == 'sha256' or k.endswith('_sha256') for k in ev), key


def test_oracle_never_beaten_bound_across_benchmarks():
    d = _load()
    for key in ('6.2_full_catalog_pair_benchmark',
                '6.3_non_equivalent_action_ablation',
                '6.6_phase5v2_mechanism'):
        assert d['acceptance_criteria'][key]['evidence']['oracle_never_beaten'] \
            is True, key


def test_non_trivial_capability_not_overstated():
    d = _load()
    nt = d['non_trivial_capability']
    assert nt['status'].startswith('CONFIRMED')
    # closest-prior-art reduction must be recorded as PENDING, not asserted
    assert nt['closest_prior_art_reduction']['status'].startswith('PENDING')
    assert 'SOTA_NOT_ADJUDICATED' in nt['closest_prior_art_reduction']['status']


def test_phase4v2_source_sha_consistent_between_6_2_and_6_6():
    d = _load()
    p4 = d['acceptance_criteria']['6.2_full_catalog_pair_benchmark'] \
        ['evidence']['artifact_sha256']
    src = d['acceptance_criteria']['6.6_phase5v2_mechanism'] \
        ['evidence']['source_phase4v2_sha256']
    assert p4 == src
