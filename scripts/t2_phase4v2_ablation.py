"""P1 6.3: non-equivalent action ablation (12 cells).

Three panels (identical-channel control, crossing-informativeness 2-action,
3-state identity/pair) x 2 cost modes x 2 budgets = 12 cells.

Tie-break is fixed (the same deterministic rational cost-minimizing tie-break
used throughout the evaluation matrix).  The identical-channel panel (A) must
only ever be interpreted as PRICE_SUBSTITUTION_OR_TIE_CONTROL -- never as
evidence of a mechanism.

Model-conditional synthetic only; no scientific claim.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from fractions import Fraction

from d2t_rna.evaluation.matrix import ExperimentSpec, run_baselines
from d2t_rna.t2.model import Action, T2FiniteModel

from scripts.t2_scale_grid_run import _channel, _id_channel, _pair_channel


def _F(n, d=1) -> Fraction:
    return Fraction(n, d)


# Panels: (panel_id, n_states, p0, p1, actions, usable_panel,
#          cost{uniform,hetero}, interpretation)
def _panels():
    id2 = [Action('id_a', _id_channel(2)), Action('id_b', _id_channel(2))]
    b_cheap = Action('b_cheap', _channel(((Fraction(3, 4), Fraction(1, 4)),
                                                 (Fraction(1, 4), Fraction(3, 4)))))
    b_panel = [Action('a_info', _id_channel(2)), b_cheap]
    id3 = [Action('id', _id_channel(3)), Action('pair', _pair_channel(3))]
    return [
        {
            'panel_id': 'A_identical_control',
            'n_states': 2,
            'p0': (_F(1, 4), _F(3, 4)),
            'p1': (_F(3, 4), _F(1, 4)),
            'actions': id2,
            'panel': ['id_a', 'id_b'],
            'costs': {'uniform': (_F(1), _F(1)), 'hetero': (_F(1), _F(2))},
            'interpretation': 'PRICE_SUBSTITUTION_OR_TIE_CONTROL',
        },
        {
            'panel_id': 'B_crossing_informativeness',
            'n_states': 2,
            'p0': (_F(1, 10), _F(9, 10)),
            'p1': (_F(9, 10), _F(1, 10)),
            'actions': b_panel,
            'panel': ['a_info', 'b_cheap'],
            # cost ranking OPPOSES informativeness ranking (a_info most informative but costly)
            'costs': {'uniform': (_F(1), _F(1)), 'hetero': (_F(3), _F(1))},
            'interpretation': 'NON_EQUIVALENT_ACTION_RISK_COST_TRADEOFF',
        },
        {
            'panel_id': 'C_3state_identity_pair',
            'n_states': 3,
            'p0': (_F(0), _F(1, 2), _F(1, 2)),
            'p1': (_F(1, 2), _F(0), _F(1, 2)),
            'actions': id3,
            'panel': ['id', 'pair'],
            'costs': {'uniform': (_F(1), _F(1)), 'hetero': (_F(1), _F(2))},
            'interpretation': 'NON_EQUIVALENT_ACTION_CHANNEL_RANK',
        },
    ]


def build_ablation_registry():
    """Return deterministic list of 12 cell dicts."""
    cells = []
    for pan in _panels():
        for budget in (_F(4), _F(8)):
            for cm in ('uniform', 'hetero'):
                cells.append({
                    'cell_id': f"{pan['panel_id']}__b{budget.numerator if budget.denominator==1 else budget}_x_{cm}",
                    'panel_id': pan['panel_id'],
                    'n_states': pan['n_states'],
                    'p0': pan['p0'],
                    'p1': pan['p1'],
                    'actions': pan['actions'],
                    'panel': pan['panel'],
                    'costs': pan['costs'][cm],
                    'budget': budget,
                    'cost_mode': cm,
                    'interpretation': pan['interpretation'],
                })
    return cells


def run_cell(cell) -> dict:
    pan_actions = cell['actions']
    panel = cell['panel']
    model = T2FiniteModel(
        name=cell['cell_id'], n_states=cell['n_states'],
        theta_0=(cell['p0'],), theta_1=(cell['p1'],),
        marginal_map=(tuple(_F(1) if w == 0 else _F(0) for w in range(cell['n_states'])),),
        actions=pan_actions,
    )
    sub = T2FiniteModel(
        name=cell['cell_id'], n_states=model.n_states,
        theta_0=(cell['p0'],), theta_1=(cell['p1'],),
        marginal_map=model.marginal_map,
        actions=tuple(a for a in pan_actions if a.action_id in panel),
    )
    spec = ExperimentSpec(model_name=cell['cell_id'], p0=cell['p0'], p1=cell['p1'],
                          costs=cell['costs'], budget=cell['budget'])
    t0 = time.time()
    runs = run_baselines(sub, spec)
    elapsed = time.time() - t0
    baseline = {}
    for method, run in sorted(runs.items()):
        baseline[method] = {
            'allocation': [int(x) for x in run.allocation],
            'cost': str(run.cost),
            'spent_exceeds_budget': run.spent_exceeds_budget,
            'executed': run.executed,
            'minimax_error': str(run.oracle.minimax_error) if run.oracle else None,
            'lp_lower_bound': str(run.lp_lower_bound) if run.lp_lower_bound is not None else None,
            'runtime_s': round(run.runtime_s, 6),
        }
    oracle_err = runs['exhaustive_oracle'].oracle.minimax_error
    beaten = [m for m, r in runs.items()
              if m != 'exhaustive_oracle' and r.executed and not r.spent_exceeds_budget
              and r.oracle is not None and r.oracle.minimax_error < oracle_err]
    return {
        'cell_id': cell['cell_id'],
        'panel_id': cell['panel_id'],
        'budget': str(cell['budget']),
        'cost_mode': cell['cost_mode'],
        'interpretation': cell['interpretation'],
        'oracle_minimax_error': str(oracle_err),
        'oracle_beaten_by': beaten,
        'baselines': baseline,
        'cell_elapsed_s': round(elapsed, 6),
    }


def run_all() -> dict:
    cells = [run_cell(c) for c in build_ablation_registry()]
    return {'n_cells': len(cells), 'cells': cells}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='/mnt/cunyuliu/d2t-rna/artifacts/phase4v2/ablation.json')
    args = ap.parse_args(argv)
    data = run_all()
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f'wrote {path}: {data["n_cells"]} cells')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
