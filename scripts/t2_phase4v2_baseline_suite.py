"""P1 6.4: Phase4-v2 comparable-only baseline suite.

The 8 protocol baseline labels are already implemented and executed inside
``run_baselines`` (exhaustive_oracle, full_matrix, random, greedy_test_cover,
eig, chernoff, lm2r_heuristic, t2_integer_lp).  This module turns per-cell
baseline results into a *comparable-only headline*:

* ``exhaustive_oracle`` is a correctness reference (cap-free global minimizer);
  it is never ranked as a competing baseline.
* Only the same-task comparable labels (all run under one matched
  ``ExperimentSpec`` per cell: same hypothesis/action/observation/cost/budget/
  fixed non-adaptive horizon/stopping/information access/decision loss/split/
  evaluator) enter the ranked headline.
* External prior-art candidates that are NOT_COMPARABLE under the frozen metric/
  schema are listed separately and never enter a leaderboard.

Model-conditional synthetic evaluation only; no formal scientific claim.
"""

from __future__ import annotations

import json
import pathlib
from fractions import Fraction

from scripts.t2_phase4v2_run import run_all

# The correctness reference is never ranked as a competing baseline.
CORRECTNESS_REFERENCE = "exhaustive_oracle"

# Comparable labels executed under one matched ExperimentSpec per cell.
# (protocol §6 internal baselines; oracle excluded from ranking)
COMPARABLE_LABELS = (
    "full_matrix",        # uniform / full-matrix round-robin
    "random",             # fixed-seed budget-feasible random allocation
    "greedy_test_cover",  # per-action TV separation (Moret & Shapiro 1991)
    "eig",                # Hellinger information / Bayesian EIG (Lindley 1956)
    "chernoff",           # true Chernoff information (Chernoff 1952)
    "lm2r_heuristic",     # project-defined TV x Hellinger heuristic
    "t2_integer_lp",      # costed integer design + LP dual lower bound
)

# External candidates from baseline_comparability_registry that are
# NOT_COMPARABLE as-is: different estimand / observation law / no replayable
# certificate over a complete registered difference set.
NOT_COMPARABLE_CANDIDATES = (
    ("controlled_sensing", "adaptive/sequential multihypothesis active sensing; no complete registered D, no replayable exact certificate"),
    ("active_sequential_hypothesis_testing", "sequential ASHT; no complete registered D, no replayable certificate"),
    ("m2_seq_m2r", "RNA structure inference; different observation law/estimand; no decision certificate over complete D"),
    ("markov_basis_fiber", "fiber connectivity criterion only; no decision/budget/no-go consequence"),
    ("bayesian_t_optimal", "EIG/optimality design without exact collision-or-separation certificate over complete D"),
)


def comparable_headline(cells: list[dict]) -> dict:
    """Build the comparable-only headline from per-cell baseline results.

    For each cell, rank only the comparable labels by minimax error (lower is
    better).  The oracle error is recorded as ``correctness_reference`` and is
    never ranked.  A cell is 'headline-eligible' only when every comparable
    label actually executed within budget.
    """
    assert CORRECTNESS_REFERENCE not in COMPARABLE_LABELS, \
        "oracle must never be ranked as a competing baseline"

    # per-cell, per-label minimax error (Fraction from string) and rank
    cells_out = []
    wins = {lab: 0 for lab in COMPARABLE_LABELS}
    n_ranked_cells = 0
    for cell in cells:
        oracle_err = Fraction(cell['oracle_minimax_error'])
        baselines = cell['baselines']

        comparable = {}
        skip_reason = None
        for lab in COMPARABLE_LABELS:
            run = baselines.get(lab)
            if run is None or not run['executed'] or run['spent_exceeds_budget']:
                skip_reason = f'{lab} not executed / exceeds budget'
                break
            if run.get('minimax_error') is None:
                skip_reason = f'{lab} missing oracle evaluation'
                break
            comparable[lab] = Fraction(run['minimax_error'])
        if skip_reason is not None:
            cells_out.append({
                'pair_id': cell['pair_id'], 'budget': cell['budget'],
                'cost_mode': cell['cost_mode'],
                'headline_eligible': False,
                'skip_reason': skip_reason,
                'correctness_reference_error': str(oracle_err),
            })
            continue

        # rank comparable labels by minimax error (lower better); stable tie-break
        ranked = sorted(comparable.items(), key=lambda kv: (kv[1], kv[0]))
        n_ranked_cells += 1
        for rank, (lab, err) in enumerate(ranked, start=1):
            if rank == 1 and err == ranked[0][1]:
                wins[lab] += 1
        cells_out.append({
            'pair_id': cell['pair_id'], 'budget': cell['budget'],
            'cost_mode': cell['cost_mode'],
            'headline_eligible': True,
            'correctness_reference_error': str(oracle_err),
            'oracle_beaten_by': cell.get('oracle_beaten_by', []),
            'ranked': [{'label': lab, 'minimax_error': str(err)}
                       for lab, err in ranked],
            'best_comparable': ranked[0][0],
        })

    return {
        'correctness_reference': CORRECTNESS_REFERENCE,
        'comparable_labels': list(COMPARABLE_LABELS),
        'headline': {
            'n_ranked_cells': n_ranked_cells,
            'ranked_cells': cells_out,
        },
        'aggregate_wins': wins,
        'not_comparable_candidates': [
            {'id': cid, 'reason': reason}
            for cid, reason in NOT_COMPARABLE_CANDIDATES
        ],
        'superiority_claim': False,
        'superiority_note': (
            'ranked headline only shows same-task allocation quality among '
            'comparable internal baselines; no SOTA / superiority claim is made '
            '(SOTA_NOT_ADJUDICATED); external candidates are listed separately.'
        ),
    }


def build_suite(cells: list[dict] | None = None) -> dict:
    """Build the full Phase4-v2 baseline suite (default: run all 80 cells)."""
    if cells is None:
        data = run_all()
        cells = data['cells']
    headline = comparable_headline(cells)
    return {
        'schema': 'd2t_rna.v7_p1_baseline_suite.v1',
        'phase': 'P1_6_4',
        'authority_role': 'BASELINE_COMPARABLE_ONLY_HEADLINE',
        'n_cells': len(cells),
        **headline,
    }


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',
                    default='/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/baseline_suite.json')
    ap.add_argument('--cells-json', default=None,
                    help='optional precomputed phase4v2 cells JSON (to avoid recompute)')
    args = ap.parse_args(argv)

    if args.cells_json:
        cells = json.loads(pathlib.Path(args.cells_json).read_text())['cells']
        suite = build_suite(cells)
    else:
        suite = build_suite()

    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(suite, indent=2))
    print(f'wrote {path}: n_cells={suite["n_cells"]} '
          f'ranked={suite["headline"]["n_ranked_cells"]} '
          f'wins={suite["aggregate_wins"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
