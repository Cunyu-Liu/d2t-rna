"""diag_deployable2.py -- verify greedy deployable wins on candidate cells.

Confirms the greedy (non-oracle) deployable reproduces the D2T wins over
Chernoff on the heterogeneous-cost catalog cells, and that it is a genuine
heuristic: runs in O(budget * U * LP) myopic steps (no exhaustive enumeration,
no access to the comparator), so it is structurally NOT the exhaustive oracle
that the audit flagged.
"""

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(10)


def minimax_of(p0_laws, p1_laws, alloc):
    p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
    return O.randomized_minimax_error_from_laws(p0v, p1v)


def greedy_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
    """Myopic minimax-reduction greedy. Non-exhaustive; never touches Chernoff."""
    U = len(costs)
    alloc = [0] * U
    spent = Fraction(0)
    steps = 0
    while True:
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent, steps
        best_u, best_mm = None, None
        for u in range(U):
            if spent + costs[u] > budget:
                continue
            alloc[u] += 1
            mm_u = minimax_of(p0_laws, p1_laws, alloc)
            alloc[u] -= 1
            if mm_u is None:
                continue
            if best_mm is None or mm_u < best_mm:
                best_mm, best_u = mm_u, u
        if best_u is None:
            return None, None, steps
        alloc[best_u] += 1
        spent += costs[best_u]
        steps += 1
    return None, None, steps


def chernoff_min_cte(p0, p1, channels, costs, budget, endpoint=ENDPOINT):
    chernoff = ControlledSensingWrapper()
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for b in range(0, int(budget) + 1):
        run = chernoff.run({
            "p0": p0, "p1": p1, "actions": channels,
            "costs": costs, "budget": Fraction(b),
        })
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(run["allocation"]))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return Fraction(b), tuple(run["allocation"])
    return None, None


id3 = O.id_channel(3)
nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))

cells = [
    ("c1_mix", (Fraction(1, 2), Fraction(1, 2), Fraction(0)),
     (Fraction(0), Fraction(1, 2), Fraction(1, 2)), [id3, nopair3],
     [Fraction(3), Fraction(1)]),
    ("c7_cheap", (Fraction(3, 4), Fraction(1, 4), Fraction(0)),
     (Fraction(0), Fraction(1, 4), Fraction(3, 4)), [id3, nopair3],
     [Fraction(4), Fraction(1)]),
    ("c5_mix", (Fraction(1, 2), Fraction(1, 2), Fraction(0)),
     (Fraction(0), Fraction(1, 2), Fraction(1, 2)), [id3, nopair3],
     [Fraction(2), Fraction(1)]),
]

for name, p0, p1, channels, costs in cells:
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    ga, gc, steps = greedy_cte(laws0, laws1, costs, BUDGET)
    c, c_alloc = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
    delta = float((gc - c) / c) if (gc is not None and c) else None
    dstr = str(round(delta, 3)) if delta is not None else "None"
    print(f"{name}: greedy_cte={gc} greedy_alloc={ga} (steps={steps}) "
          f"cher_cte={c} cher_alloc={c_alloc} delta={dstr}", flush=True)
