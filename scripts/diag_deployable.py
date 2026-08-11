"""diag_deployable.py -- verify the greedy deployable on candidate catalog cells.

Confirms:
  1. The greedy (non-oracle) deployable reproduces the D2T wins over Chernoff
     on the hand-built heterogeneous-cost cells.
  2. The greedy is a GENUINE non-oracle: it is suboptimal vs the exact solver
     somewhere, so it is not merely re-implementing exhaustive enumeration.
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
    U = len(costs)
    alloc = [0] * U
    spent = Fraction(0)
    while True:
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent
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
            return None, None
        alloc[best_u] += 1
        spent += costs[best_u]
    return None, None


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
pair3 = O.pair_channel(3)
noid3 = O.noisy_channel(O.id_channel(3), 3, Fraction(1, 4))
nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))

# catalog candidate cells: (name, p0, p1, channels, costs)
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

print(f"{'name':10s} {'greedy_cte':>10s} {'greedy_alloc':>14s} "
      f"{'exact_cte':>9s} {'cher_cte':>8s} {'cher_alloc':>10s} {'delta':>7s}")
for name, p0, p1, channels, costs in cells:
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    ga, gc = greedy_cte(laws0, laws1, costs, BUDGET)
    ex = exact_cte(laws0, laws1, costs, BUDGET)
    ec = ex[1] if ex else None
    c, c_alloc = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
    delta = float((gc - c) / c) if (gc is not None and c) else None
    dstr = str(round(delta, 3)) if delta is not None else "None"
    print(f"{name:10s} {str(gc):>10s} {str(ga):>14s} {str(ec):>9s} "
          f"{str(c):>8s} {str(c_alloc):>10s} {dstr:>7s}")

# non-oracle verification: search 3-state grid where greedy != exact
print("\n--- non-oracle check (greedy vs exact over grid) ---")
subopt = 0
match = 0
gno = 0
d3 = [(Fraction(a, 2), Fraction(b, 2), Fraction(2 - a - b, 2))
      for a in range(3) for b in range(3 - a)]
for i in range(len(d3)):
    for j in range(len(d3)):
        p0, p1 = d3[i], d3[j]
        if p0 == p1:
            continue
        for chans, costs in [([id3, nopair3], [Fraction(1), Fraction(1)]),
                             ([id3, pair3, nopair3],
                              [Fraction(1), Fraction(1), Fraction(1)])]:
            laws0 = tuple(O.action_law(ch, p0) for ch in chans)
            laws1 = tuple(O.action_law(ch, p1) for ch in chans)
            ga, gc = greedy_cte(laws0, laws1, costs, Fraction(8))
            ex = exact_cte(laws0, laws1, costs, Fraction(8))
            ec = ex[1] if ex else None
            if gc is not None and ec is not None:
                if gc > ec:
                    subopt += 1
                else:
                    match += 1
            elif gc is None and ex is None:
                gno += 1
print(f"greedy==exact: {match}, greedy suboptimal (>exact): {subopt}, both-no-go: {gno}")
print(f"=> greedy is a genuine non-oracle algorithm: {subopt > 0}")
