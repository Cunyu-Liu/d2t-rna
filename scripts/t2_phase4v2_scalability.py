"""P1 6.5: Phase4-v2 scalability reporting.

Aggregates the Phase4-v2 80-cell benchmark into an engineering scaling record.
For every cell and every baseline label it reports:

* runtime (s)
* peak traced memory (bytes)
* executed / spent_exceeds_budget (fail-closed flags)
* for ``t2_integer_lp``: LP/MIP dimensions (U actions x W pairs decision
  variables and thresholds constraints), the LP lower bound, the integer
  achievable cost, and the resulting optimality gap
* withheld certificate / timeout accounting and per-label coverage
  (fraction of cells where the label executed within budget)
* the exact-oracle solvable boundary: the size of the cap-free within-budget
  allocation space (= product over actions of floor(budget / cost_u) + 1)

Any cell that is not exactly solvable (oracle timeout / failure) is reported
with ``UNKNOWN_NOT_ASSERTED`` rather than a fabricated number.  Engineering
scaling record only; no formal scientific claim.
"""

from __future__ import annotations

import json
import math
import pathlib
from fractions import Fraction

from scripts.t2_phase4v2_run import _allocate_costs, build_p4v2_registry

ARTIFACT = pathlib.Path('/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase4v2.json')

BASELINE_LABELS = (
    'exhaustive_oracle', 'full_matrix', 'random', 'greedy_test_cover',
    'eig', 'chernoff', 'lm2r_heuristic', 't2_integer_lp',
)


def _frac(x):
    return Fraction(x)


def exact_boundary(pair, budget: Fraction, cost_mode: str) -> int:
    """Size of the cap-free within-budget allocation space for a pair-cell."""
    panel = pair['panel']
    costs = _allocate_costs(panel, cost_mode)
    space = 1
    for c in costs:
        space *= int(budget // _frac(c)) + 1
    return int(space)


def _lp_dims(pair) -> dict:
    """LP/MIP dimensions for the costed integer design on this pair."""
    U = len(pair['panel'])
    W = 1  # single registered candidate-vs-rival pair (pair_ids=("w",))
    return {'n_decision_variables': U, 'n_threshold_constraints': W}


def cell_scalability(cell: dict, pair) -> dict:
    """Aggregate scalability facts for one cell."""
    budget = _frac(cell['budget'])
    rows = {}
    timeout = 0
    failure = 0
    withheld = 0
    for lab in BASELINE_LABELS:
        run = cell['baselines'].get(lab)
        if run is None:
            rows[lab] = {'executed': False, 'status': 'NOT_RUN',
                         'runtime_s': None, 'memory_peak_bytes': None}
            failure += 1
            continue
        executed = run.get('executed', True)
        over = run.get('spent_exceeds_budget', False)
        entry = {
            'executed': executed,
            'spent_exceeds_budget': over,
            'runtime_s': run.get('runtime_s'),
            'memory_peak_bytes': run.get('memory_peak_bytes'),
            'minimax_error': run.get('minimax_error'),
            'status': 'EXECUTED_OK' if executed and not over else 'FAIL_CLOSED',
        }
        if lab == 't2_integer_lp':
            lp_lb = run.get('lp_lower_bound')
            int_cost = run.get('integer_upper_cost')
            dims = _lp_dims(pair)
            entry['lp_dims'] = dims
            entry['lp_lower_bound'] = lp_lb
            entry['integer_upper_cost'] = int_cost
            gap = None
            if lp_lb is not None and int_cost is not None and _frac(lp_lb) > 0:
                gap = (_frac(int_cost) - _frac(lp_lb)) / _frac(lp_lb)
                entry['optimality_gap'] = str(gap)
            elif int_cost is not None and lp_lb is None:
                # integer achieved but no LP lower bound -> cannot assert gap
                entry['optimality_gap'] = 'UNKNOWN_NOT_ASSERTED'
                withheld += 1
            else:
                entry['optimality_gap'] = None
        if not executed:
            failure += 1
        if over:
            withheld += 1
        if run.get('runtime_s') is not None and run['runtime_s'] > 60.0:
            timeout += 1
        rows[lab] = entry

    return {
        'pair_id': cell['pair_id'],
        'catalog_class': cell['catalog_class'],
        'budget': cell['budget'],
        'cost_mode': cell['cost_mode'],
        'oracle_minimax_error': cell['oracle_minimax_error'],
        'exact_boundary_allocation_space': exact_boundary(pair, budget, cell['cost_mode']),
        'baselines': rows,
        'n_timeouts': timeout,
        'n_failures': failure,
        'n_withheld_certificates': withheld,
        'cell_elapsed_s': cell.get('cell_elapsed_s'),
    }


def build_scalability_report(data: dict | None = None) -> dict:
    if data is None:
        data = json.loads(ARTIFACT.read_text())
    pairs = {p['pair_id']: p for p in build_p4v2_registry()}
    cells = [cell_scalability(c, pairs[c['pair_id']]) for c in data['cells']]

    # per-label coverage: fraction of cells where the label executed within budget
    coverage = {}
    for lab in BASELINE_LABELS:
        ok = sum(1 for c in cells
                 if c['baselines'][lab]['status'] == 'EXECUTED_OK')
        coverage[lab] = {'executed_ok_cells': ok, 'coverage': ok / len(cells)}

    # runtime / memory aggregate per label
    runtime = {}
    memory = {}
    for lab in BASELINE_LABELS:
        rs = [c['baselines'][lab]['runtime_s'] for c in cells
              if c['baselines'][lab].get('runtime_s') is not None]
        ms = [c['baselines'][lab]['memory_peak_bytes'] for c in cells
              if c['baselines'][lab].get('memory_peak_bytes') is not None]
        runtime[lab] = {'max_s': round(max(rs), 4) if rs else None,
                        'mean_s': round(sum(rs) / len(rs), 4) if rs else None,
                        'total_s': round(sum(rs), 4) if rs else None}
        memory[lab] = {'max_bytes': max(ms) if ms else None,
                       'mean_bytes': round(sum(ms) / len(ms), 1) if ms else None}

    # global LP dims (uniform across cells of same class size; report per class)
    lp_dims_by_class = {}
    for cid in sorted({c['catalog_class'] for c in cells}):
        sample = next(c for c in cells if c['catalog_class'] == cid)
        lp_dims_by_class[cid] = sample['baselines']['t2_integer_lp'].get('lp_dims')

    max_boundary = max(c['exact_boundary_allocation_space'] for c in cells)
    total_timeouts = sum(c['n_timeouts'] for c in cells)
    total_failures = sum(c['n_failures'] for c in cells)
    total_withheld = sum(c['n_withheld_certificates'] for c in cells)

    return {
        'schema': 'd2t_rna.v7_p1_scalability_report.v1',
        'phase': 'P1_6_5',
        'authority_role': 'SCALABILITY_RECORD',
        'n_cells': len(cells),
        'cells': cells,
        'coverage': coverage,
        'runtime': runtime,
        'memory': memory,
        'lp_dims_by_catalog_class': lp_dims_by_class,
        'exact_oracle_boundary': {
            'max_allocation_space': max_boundary,
            'exact_solvable_boundary': (
                f'cap-free within-budget allocation space <= {max_boundary} '
                f'for all 80 cells'
            ),
            'beyond_exact_scale': 'UNKNOWN_NOT_ASSERTED',
        },
        'timeout_failure_withheld': {
            'n_timeouts': total_timeouts,
            'n_failures': total_failures,
            'n_withheld_certificates': total_withheld,
            'note': (
                'withheld certificates only for cells where a label failed '
                'closed (not executed or exceeded budget); no number is '
                'fabricated for beyond-exact-scale instances.'
            ),
        },
        'scientific_claim_authorized': False,
    }


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/scalability.json')
    args = ap.parse_args(argv)
    report = build_scalability_report()
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(f'wrote {path}: n_cells={report["n_cells"]} '
          f'timeouts={report["timeout_failure_withheld"]["n_timeouts"]} '
          f'failures={report["timeout_failure_withheld"]["n_failures"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
