"""P1 6.4: Phase4-v2 comparable-only baseline suite tests.

Verifies the comparable-only headline semantics:
* exhaustive_oracle is a correctness reference and is never ranked as a
  competing baseline;
* only the same-task comparable labels enter the ranked headline;
* NOT_COMPARABLE external candidates are listed separately, never in a
  leaderboard;
* per-cell ranking uses minimax error (lower better) and cells where any
  comparable label fails to execute/budget are marked not headline-eligible.
"""

from __future__ import annotations

from fractions import Fraction

from scripts.t2_phase4v2_baseline_suite import (
    COMPARABLE_LABELS,
    CORRECTNESS_REFERENCE,
    NOT_COMPARABLE_CANDIDATES,
    comparable_headline,
)


def _cell(pair_id, budget, cost_mode, oracle_err, baselines, beaten=None):
    """Build a synthetic per-cell result in the run_cell output shape."""
    return {
        'pair_id': pair_id,
        'budget': budget,
        'cost_mode': cost_mode,
        'oracle_minimax_error': str(Fraction(oracle_err)),
        'oracle_beaten_by': beaten or [],
        'baselines': baselines,
    }


def _run(label, err, executed=True, over_budget=False):
    return {
        'executed': executed,
        'spent_exceeds_budget': over_budget,
        'minimax_error': str(Fraction(err)),
    }


def test_oracle_is_correctness_reference_not_ranked():
    assert CORRECTNESS_REFERENCE == 'exhaustive_oracle'
    assert CORRECTNESS_REFERENCE not in COMPARABLE_LABELS


def test_all_eight_protocol_labels_registered():
    # protocol §6 internal baselines (oracle reference + 7 comparable)
    assert 'exhaustive_oracle' in COMPARABLE_LABELS or CORRECTNESS_REFERENCE == 'exhaustive_oracle'
    for lab in ('full_matrix', 'random', 'greedy_test_cover', 'eig',
                'chernoff', 'lm2r_heuristic', 't2_integer_lp'):
        assert lab in COMPARABLE_LABELS
    assert len(COMPARABLE_LABELS) == 7


def test_not_comparable_candidates_listed_separately():
    ids = {c[0] for c in NOT_COMPARABLE_CANDIDATES}
    assert {'controlled_sensing', 'active_sequential_hypothesis_testing',
            'm2_seq_m2r', 'markov_basis_fiber', 'bayesian_t_optimal'} <= ids


def test_comparable_only_ranking_excludes_oracle():
    cells = [
        _cell('CA_p1', '4', 'uniform', '3/10', {
            'full_matrix': _run('full_matrix', '1/2'),
            'random': _run('random', '2/5'),
            'greedy_test_cover': _run('greedy_test_cover', '1/3'),
            'eig': _run('eig', '1/4'),
            'chernoff': _run('chernoff', '1/4'),
            'lm2r_heuristic': _run('lm2r_heuristic', '1/5'),
            't2_integer_lp': _run('t2_integer_lp', '1/5'),
        }),
    ]
    h = comparable_headline(cells)
    # oracle error is preserved as correctness reference but is not ranked
    ranked_cell = h['headline']['ranked_cells'][0]
    assert ranked_cell['headline_eligible'] is True
    labels_ranked = {r['label'] for r in ranked_cell['ranked']}
    assert 'exhaustive_oracle' not in labels_ranked
    assert labels_ranked == set(COMPARABLE_LABELS)
    assert ranked_cell['correctness_reference_error'] == '3/10'
    # best comparable by minimax error: lm2r_heuristic / t2_integer_lp both 1/5
    assert ranked_cell['best_comparable'] in ('lm2r_heuristic', 't2_integer_lp')


def test_cell_not_eligible_when_comparable_label_fails():
    cells = [
        _cell('CA_p1', '8', 'hetero', '1/2', {
            'full_matrix': _run('full_matrix', '1/2'),
            'random': _run('random', '1/2', executed=False),  # fails to execute
            'greedy_test_cover': _run('greedy_test_cover', '1/2'),
            'eig': _run('eig', '1/2'),
            'chernoff': _run('chernoff', '1/2'),
            'lm2r_heuristic': _run('lm2r_heuristic', '1/2'),
            't2_integer_lp': _run('t2_integer_lp', '1/2'),
        }),
    ]
    h = comparable_headline(cells)
    cell = h['headline']['ranked_cells'][0]
    assert cell['headline_eligible'] is False
    assert h['headline']['n_ranked_cells'] == 0


def test_aggregate_wins_only_over_comparable():
    cells = [
        _cell('CA_p1', '4', 'uniform', '1/2', {
            'full_matrix': _run('full_matrix', '1/3'),
            'random': _run('random', '1/2'),
            'greedy_test_cover': _run('greedy_test_cover', '1/2'),
            'eig': _run('eig', '1/2'),
            'chernoff': _run('chernoff', '1/2'),
            'lm2r_heuristic': _run('lm2r_heuristic', '1/2'),
            't2_integer_lp': _run('t2_integer_lp', '1/2'),
        }),
        _cell('CA_p2', '8', 'uniform', '1/2', {
            'full_matrix': _run('full_matrix', '1/2'),
            'random': _run('random', '1/3'),
            'greedy_test_cover': _run('greedy_test_cover', '1/2'),
            'eig': _run('eig', '1/2'),
            'chernoff': _run('chernoff', '1/2'),
            'lm2r_heuristic': _run('lm2r_heuristic', '1/2'),
            't2_integer_lp': _run('t2_integer_lp', '1/2'),
        }),
    ]
    h = comparable_headline(cells)
    assert h['headline']['n_ranked_cells'] == 2
    assert h['aggregate_wins']['full_matrix'] == 1
    assert h['aggregate_wins']['random'] == 1
    # no oracle win counter exists
    assert 'exhaustive_oracle' not in h['aggregate_wins']
    assert h['superiority_claim'] is False


def test_no_superiority_claim_emitted():
    h = comparable_headline([])
    assert h['superiority_claim'] is False
    assert h['not_comparable_candidates']
