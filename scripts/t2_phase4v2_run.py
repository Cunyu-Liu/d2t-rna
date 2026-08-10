"""P1 6.2: Phase4-v2 full-catalog pair benchmark (80 pair-cells).

Four catalog classes x 5 explicit pairs = 20 pairs; each pair x 2 budgets x
2 cost modes = 80 cells.  Every pair is an explicit (p0, p1) selection --
never the theta_0[0]/theta_1[0] shorthand that the old Phase 4 used.
Runs the 8 protocol labels under one matched ExperimentSpec per cell,
reports per-pair, computes the catalog worst-case, and binds results to the
corrected metric/schema.  Produces a Phase4-v2 artifact that does not overwrite
the legacy Phase 4 scale-grid.

Model-conditional synthetic evaluation only; no formal scientific claim.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from fractions import Fraction

from d2t_rna.evaluation.matrix import ExperimentSpec, run_baselines
from d2t_rna.t2.model import Action, T2FiniteModel

from scripts.t2_scale_grid_run import _allocate_costs, _channel, _id_channel, _merge_channel, _pair_channel, _unit_marg


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


def _d2(den=4):
    """2-state distributions (i/den, (den-i)/den)."""
    return [(_F(i, den), _F(den - i, den)) for i in range(den + 1)]


def _d3(den=2):
    """3-state distributions with common denominator den."""
    out = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((_F(a, den), _F(b, den), _F(den - a - b, den)))
    return out


def _pools():
    """Four catalog classes: (class_id, n_states, theta0_pool, theta1_pool, actions).\n\n    Pools are explicit lists of distributions (Fractions); pairs are drawn\n    deterministically from them by index.\n    """
    d2 = _d2(4)
    d3 = _d3(2)
    id2 = [Action('id_a', _id_channel(2)), Action('id_b', _id_channel(2)), Action('merge', _merge_channel(2))]
    id3 = [Action('id', _id_channel(3)), Action('pair', _pair_channel(3))]
    return [
        ('CA', 2, [d2[1], d2[3]], [d2[0], d2[2], d2[4]], id2, ['id_a', 'id_b']),
        ('CB', 2, [d2[0], d2[2], d2[4]], [d2[1], d2[3]], id2, ['id_a', 'id_b']),
        ('CC', 3, [d3[0], d3[1], d3[2]], [d3[3], d3[4]], id3, ['id', 'pair']),
        ('CD', 3, [d3[1], d3[3], d3[4]], [d3[0], d3[2], d3[5]], id3, ['id', 'pair']),
    ]


# explicit (theta0_idx, theta1_idx) pairs per class -> 5 pairs x 4 classes = 20
# Local (theta0_pool_idx, theta1_pool_idx) selections -> 5 pairs x 4 classes = 20.
# Pools are sublists, so indices are LOCAL within each pool (not absolute).
_PAIR_IDX = {
    'CA': [(0, 0), (1, 0), (0, 1), (1, 1), (1, 2)],
    'CB': [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    'CC': [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    'CD': [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)],
}


def build_p4v2_registry():
    """Return deterministic list of 20 pair dicts (explicit p0/p1 as Fractions)."""
    pairs = []
    for cid, n, t0, t1, actions, panel in _pools():
        for k, (i, j) in enumerate(_PAIR_IDX[cid], start=1):
            p0 = t0[i]
            p1 = t1[j]
            assert tuple(p0) != tuple(p1), f'{cid} p{k}: degenerate pair'
            pairs.append({
                'pair_id': f'{cid}_p{k}',
                'catalog_class': cid,
                'n_states': n,
                'p0': tuple(tuple(Fraction(x) for x in p0)),
                'p1': tuple(tuple(Fraction(x) for x in p1)),
                'panel': list(panel),
                'actions': actions,
                'marginal_map': (_unit_marg(n),),
            })
    return pairs


def _model_for(pair):
    return T2FiniteModel(
        name=pair['pair_id'],
        n_states=pair['n_states'],
        theta_0=(pair['p0'],),
        theta_1=(pair['p1'],),
        marginal_map=pair['marginal_map'],
        actions=pair['actions'],
    )


def run_cell(pair, budget: Fraction, cost_mode: str) -> dict:
    """Run the 8-label matched suite on one pair-cell (explicit p0/p1)."""
    panel = pair['panel']
    model = _model_for(pair)
    sub = T2FiniteModel(
        name=pair['pair_id'],
        n_states=model.n_states,
        theta_0=(pair['p0'],),
        theta_1=(pair['p1'],),
        marginal_map=model.marginal_map,
        actions=tuple(a for a in model.actions if a.action_id in panel),
    )
    costs = _allocate_costs(panel, cost_mode)
    spec = ExperimentSpec(model_name=pair['pair_id'], p0=pair['p0'], p1=pair['p1'],
                          costs=costs, budget=budget)
    t0 = time.time()
    runs = run_baselines(sub, spec)
    elapsed = time.time() - t0

    baseline = {}
    for method, run in sorted(runs.items()):
        baseline[method] = {
            'allocation': [int(x) for x in run.allocation],
            'cost': str(run.cost),
            'spent_exceeds_budget': run.spent_exceeds_budget,
            'runtime_s': round(run.runtime_s, 6),
            'memory_peak_bytes': int(run.memory) if run.memory is not None else None,
            'executed': run.executed,
            'minimax_error': str(run.oracle.minimax_error) if run.oracle else None,
            'lp_lower_bound': str(run.lp_lower_bound) if run.lp_lower_bound is not None else None,
            'integer_upper_cost': str(run.integer_upper) if run.integer_upper is not None else None,
        }

    oracle_err = runs['exhaustive_oracle'].oracle.minimax_error
    feasible = [m for m, r in runs.items()
                if m != 'exhaustive_oracle' and r.executed and not r.spent_exceeds_budget
                and r.oracle is not None]
    beaten = [m for m in feasible if runs[m].oracle.minimax_error < oracle_err]

    return {
        'pair_id': pair['pair_id'],
        'catalog_class': pair['catalog_class'],
        'budget': str(budget),
        'cost_mode': cost_mode,
        'oracle_minimax_error': str(oracle_err),
        'oracle_beaten_by': beaten,
        'baselines': baseline,
        'cell_elapsed_s': round(elapsed, 6),
    }


def run_all() -> dict:
    """Run all 80 cells and aggregate per-pair + catalog worst-case."""
    pairs = build_p4v2_registry()
    cells = []
    for pair in pairs:
        for budget in (_F(4), _F(8)):
            for cm in ('uniform', 'hetero'):
                cells.append(run_cell(pair, budget, cm))
    # catalog worst-case: per class, the pair with the largest oracle minimax error
    worst = {}
    for cid in sorted({c['catalog_class'] for c in cells}):
        sub = [c for c in cells if c['catalog_class'] == cid]
        worst[cid] = max(sub, key=lambda c: Fraction(c['oracle_minimax_error']))['pair_id']
    return {'n_pairs': len(pairs), 'n_cells': len(cells), 'cells': cells,
            'catalog_worst_case': worst}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/phase4v2.json')
    args = ap.parse_args(argv)
    data = run_all()
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f'wrote {path}: {data["n_cells"]} cells, worst-case={data["catalog_worst_case"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
