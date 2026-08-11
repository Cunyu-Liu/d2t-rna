"""diag_catalog.py -- build the method-distinguishing catalog.

Scans overlapping-support 3-state cells with heterogeneous-cost action sets
and keeps cells where the cost-aware greedy deployable strictly beats the
Chernoff comparator at cost-to-endpoint.  Every cell is recorded with the
exact solver's cost (to prove the deployable is a genuine non-oracle that can
be suboptimal yet still win) and the mechanism (mix vs single-action).
"""

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(12)


def minimax_of(p0_laws, p1_laws, alloc):
    p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
    return O.randomized_minimax_error_from_laws(p0v, p1v)


def costaware_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
    U = len(costs)
    alloc = [0] * U
    spent = Fraction(0)
    while True:
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent
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
            return None, None
        reaching = [(u, mm) for u, mm in candidates if mm <= endpoint]
        if reaching:
            u = min(reaching, key=lambda x: spent + costs[x[0]])[0]
            alloc[u] += 1
            return tuple(alloc), spent + costs[u]
        u = min(candidates, key=lambda x: x[1])[0]
        alloc[u] += 1
        spent += costs[u]


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


def simplex(den):
    out = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((Fraction(a, den), Fraction(b, den),
                        Fraction(den - a - b, den)))
    return out


def overlapping(p0, p1):
    return any(a > 0 and b > 0 for a, b in zip(p0, p1))


def main():
    d3 = simplex(4)
    id3 = O.id_channel(3)
    pair3 = O.pair_channel(3)
    noid3 = O.noisy_channel(O.id_channel(3), 3, Fraction(1, 4))
    nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))

    # action sets: (name, [(channel, cost), ...])
    sets = [
        ("A", [(id3, 3), (nopair3, 1)]),
        ("B", [(id3, 2), (nopair3, 1)]),
        ("C", [(id3, 4), (nopair3, 1)]),
        ("D", [(noid3, 3), (nopair3, 1)]),
        ("E", [(id3, 3), (pair3, 1)]),
        ("F", [(id3, 2), (pair3, 1), (nopair3, 1)]),
    ]

    wins = []
    seen = set()
    for i in range(len(d3)):
        for j in range(len(d3)):
            p0, p1 = d3[i], d3[j]
            if p0 == p1 or not overlapping(p0, p1):
                continue
            for sname, actset in sets:
                channels = [ch for ch, _c in actset]
                costs = [Fraction(c) for _ch, c in actset]
                laws0 = tuple(O.action_law(ch, p0) for ch in channels)
                laws1 = tuple(O.action_law(ch, p1) for ch in channels)
                ca, cc = costaware_cte(laws0, laws1, costs, BUDGET)
                if ca is None:
                    continue
                c, c_alloc = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
                if c is None:
                    continue
                if cc < c:
                    mech = "mix" if sum(1 for n in ca if n > 0) > 1 else "single"
                    key = (str(p0), str(p1), sname)
                    if key in seen:
                        continue
                    seen.add(key)
                    wins.append({
                        "p0": list(map(str, p0)), "p1": list(map(str, p1)),
                        "set": sname, "channels": [ch for ch, _c in actset],
                        "costs": [str(x) for x in costs],
                        "greedy_cte": str(cc), "greedy_alloc": list(map(str, ca)),
                        "cher_cte": str(c), "cher_alloc": list(map(str, c_alloc)),
                        "delta": float((cc - c) / c), "mechanism": mech,
                    })

    wins.sort(key=lambda w: w["delta"])
    print(f"TOTAL WINS: {len(wins)}")
    for w in wins:
        print(f"p0={w['p0']} p1={w['p1']} set={w['set']} "
              f"greedy={w['greedy_cte']}{w['greedy_alloc']} "
              f"cher={w['cher_cte']}{w['cher_alloc']} "
              f"delta={w['delta']:.3f} mech={w['mechanism']}", flush=True)


if __name__ == "__main__":
    main()
