"""diag_costaware.py -- test the cost-aware cost-to-endpoint greedy deployable.

The deployable is a myopic minimax-reduction greedy that is COST-AWARE:
at each step it adds one unit to the action that most reduces randomized
minimax, but if an addition REACHES the frozen endpoint it immediately takes
the CHEAPEST such addition and stops (cost-to-endpoint semantics).  This is a
genuine non-oracle algorithm: O(budget*U*LP) myopic steps, no exhaustive
enumeration, no access to the comparator.  We test whether it reproduces the
exact solver's wins over Chernoff on the heterogeneous-cost cells.
"""

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(10)


def minimax_of(p0_laws, p1_laws, alloc):
    p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
    return O.randomized_minimax_error_from_laws(p0v, p1v)


def costaware_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
    U = len(costs)
    alloc = [0] * U
    spent = Fraction(0)
    steps = 0
    while True:
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent, steps
        candidates = []
        for u in range(U):
            if spent + costs[u] > budget:
                continue
            alloc[u] += 1
            mm_u = minimax_of(p0_laws, p1_laws, alloc)
            alloc[u] -= 1
            if mm_u is not None:
                candidates.append((u, mm_u))
        if not candidates:
            return None, None, steps
        # if any addition reaches the endpoint, take the cheapest such addition
        reaching = [(u, mm) for u, mm in candidates if mm <= endpoint]
        if reaching:
            u = min(reaching, key=lambda x: spent + costs[x[0]])[0]
            alloc[u] += 1
            spent += costs[u]
            steps += 1
            return tuple(alloc), spent, steps
        # else myopic: add the action minimizing resulting minimax
        u = min(candidates, key=lambda x: x[1])[0]
        alloc[u] += 1
        spent += costs[u]
        steps += 1


def exact_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
    from itertools import product
    max_n = [int(budget // c) if c > 0 else 0 for c in costs]
    best = None
    for joint in product(*(range(m + 1) for m in max_n)):
        cost = sum(c * nu for c, nu in zip(costs, joint))
        if cost > budget:
            continue
        p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, joint)
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is None or mm > endpoint:
            continue
        if best is None or cost < best[1] or (cost == best[1] and mm < best[2]):
            best = (tuple(joint), cost, mm)
    return best


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
    ("c5_mix", (Fraction(1, 2), Fraction(1, 2), Fraction(0)),
     (Fraction(0), Fraction(1, 2), Fraction(1, 2)), [id3, nopair3],
     [Fraction(2), Fraction(1)]),
    ("c7_cheap", (Fraction(3, 4), Fraction(1, 4), Fraction(0)),
     (Fraction(0), Fraction(1, 4), Fraction(3, 4)), [id3, nopair3],
     [Fraction(4), Fraction(1)]),
]

for name, p0, p1, channels, costs in cells:
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    ca, cc, csteps = costaware_cte(laws0, laws1, costs, BUDGET)
    ex = exact_cte(laws0, laws1, costs, BUDGET)
    ec = ex[1] if ex else None
    c, c_alloc = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
    delta = float((cc - c) / c) if (cc is not None and c) else None
    dstr = str(round(delta, 3)) if delta is not None else "None"
    print(f"{name}: costaware_cte={cc} alloc={ca} (steps={csteps}) "
          f"exact_cte={ec} cher_cte={c} cher_alloc={c_alloc} delta={dstr}",
          flush=True)
