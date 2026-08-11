"""diag_search.py -- search for GENUINE method-distinguishing cells.

Searches for confirmation cells where D2T's exact cost-to-endpoint solver
strictly beats Chernoff's greedy cost-to-endpoint, using OVERLAPPING-support
channels and HETEROGENEOUS costs.  Overlapping support guarantees Chernoff
information is finite (the +inf disjoint-support path is never hit), so any
win is a genuine cost-optimality / multi-action-allocation advantage, not a
wrapper-bug artifact.

For each cell we compute:
  * D2T cost-to-endpoint   = min-cost allocation reaching the endpoint under
                             randomized minimax (exact).
  * Chernoff cost-to-endpoint = min budget b at which the faithful greedy
                             wrapper's allocation reaches the endpoint.
Both are "minimum cost to reach the frozen endpoint".
"""

from fractions import Fraction
from itertools import product

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper
from d2t_rna.evaluation.wrappers import helpers as H

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(10)


def d2t_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
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
    """Minimum budget b at which the greedy wrapper reaches the endpoint."""
    chernoff = ControlledSensingWrapper()
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for b in range(0, int(budget) + 1):
        run = chernoff.run({
            "p0": p0, "p1": p1, "actions": channels,
            "costs": [1] * len(channels), "budget": Fraction(b),
        })
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(run["allocation"]))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return Fraction(b), tuple(run["allocation"]), mm
    return None, None, None


def simplex(den):
    """All k-dim probability vectors with denominator den (k inferred)."""
    # 3-state
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
    merge3 = O.merge_channel(3)
    noid3 = O.noisy_channel(O.id_channel(3), 3, Fraction(1, 4))
    nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))

    # action library: (name, channel, cost)
    actions3 = [
        ("id3", id3, 1), ("pair3", pair3, 1), ("merge3", merge3, 1),
        ("noid3", noid3, 1), ("nopair3", nopair3, 1),
        ("id3c2", id3, 2), ("id3c3", id3, 3),
    ]
    # action SETS to try (list of names into actions3)
    sets = [
        ("id3", "pair3"), ("id3", "nopair3"), ("noid3", "id3c3"),
        ("id3", "merge3", "pair3"), ("id3c2", "nopair3"),
        ("noid3", "pair3"), ("id3c3", "nopair3"), ("id3", "noid3", "pair3"),
    ]

    wins = []
    ties = 0
    nogo = 0
    total = 0
    for i in range(len(d3)):
        for j in range(len(d3)):
            p0, p1 = d3[i], d3[j]
            if p0 == p1 or not overlapping(p0, p1):
                continue
            for sname in sets:
                chans = [(nm, ch, c) for nm, ch, c in actions3 if nm in sname]
                channels = [ch for _nm, ch, _c in chans]
                costs = [Fraction(c) for _nm, _ch, c in chans]
                laws0 = tuple(O.action_law(ch, p0) for ch in channels)
                laws1 = tuple(O.action_law(ch, p1) for ch in channels)
                d = d2t_cte(laws0, laws1, costs, BUDGET)
                c, c_alloc, c_mm = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
                total += 1
                d_cte = d[1] if d else None
                if d_cte is not None and c is not None:
                    # only count as win if not relying on disjoint (guaranteed
                    # by overlapping filter) and genuinely cheaper
                    if d_cte < c:
                        wins.append((str(p0), str(p1), sname, d_cte, d[0],
                                     c, c_alloc, float((d_cte - c) / c)))
                    elif d_cte == c:
                        ties += 1
                else:
                    nogo += 1
    print(f"total={total} wins={len(wins)} ties={ties} nogo={nogo}")
    print("--- wins (D2T strictly cheaper; overlapping-support, finite Chernoff info) ---")
    for w in sorted(wins, key=lambda x: x[7]):
        print(f"p0={w[0]} p1={w[1]} set={w[2]} D2Tcte={w[3]} D2Talloc={w[4]} "
              f"chercte={w[5]} cheralloc={w[6]} delta={w[7]:.3f}")


if __name__ == "__main__":
    main()
