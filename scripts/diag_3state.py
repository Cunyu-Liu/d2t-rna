from fractions import Fraction
from itertools import product
from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def d2t_cost_to_endpoint(p0_laws, p1_laws, costs, budget, endpoint):
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
            best = (tuple(joint), cost, mm, (p0v, p1v))
    return best


def chernoff_cte(p0, p1, channels, budget, endpoint):
    chernoff = ControlledSensingWrapper()
    n = len(channels)
    for b in range(0, int(budget) + 1):
        run = chernoff.run({
            "p0": p0, "p1": p1, "actions": channels,
            "costs": [1] * n, "budget": Fraction(b),
        })
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(run["allocation"]))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return Fraction(b), tuple(run["allocation"])
    return None, None


def d3(den=2):
    out = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((Fraction(a, den), Fraction(b, den),
                        Fraction(den - a - b, den)))
    return out


d3v = d3(2)
id3 = O.id_channel(3)
pair3 = O.pair_channel(3)
# also merge channel (1 output, reads all)
merge3 = O.merge_channel(3)

endpoint = Fraction(1, 10)
budget = Fraction(8)

# all CC/CD-like: p0 in one half, p1 in other half, various action sets
win = 0
tie = 0
no_go = 0
wins_detail = []
rows = []
for i in range(6):
    for j in range(6):
        p0 = d3v[i]
        p1 = d3v[j]
        if p0 == p1:
            continue
        for aname, chans in [
            ("idpair", [id3, pair3]),
            ("idpairmerge", [id3, pair3, merge3]),
        ]:
            channels = chans
            laws0 = tuple(O.action_law(ch, p0) for ch in channels)
            laws1 = tuple(O.action_law(ch, p1) for ch in channels)
            cte = d2t_cost_to_endpoint(laws0, laws1, (Fraction(1),) * len(channels),
                                       budget, endpoint)
            cher_cte, cher_alloc = chernoff_cte(p0, p1, channels, budget, endpoint)
            d_cte = cte[1] if cte else None
            d_alloc = cte[0] if cte else None
            if d_cte is not None and cher_cte is not None:
                delta = float((d_cte - cher_cte) / cher_cte)
                if delta < 0:
                    win += 1
                    wins_detail.append((str(p0), str(p1), aname, d_cte, d_alloc,
                                        cher_cte, cher_alloc, delta))
                elif delta == 0:
                    tie += 1
            else:
                no_go += 1
            rows.append((str(p0), str(p1), aname, d_cte, d_alloc, cher_cte, cher_alloc))

print("3-state exhaustive: win={} tie={} no_go={}".format(win, tie, no_go))
print("--- wins (D2T cheaper than chernoff) ---")
for w in wins_detail:
    print("p0={} p1={} {}: D2T cte={} alloc={}  cher cte={} alloc={}  delta={}".format(*w))
