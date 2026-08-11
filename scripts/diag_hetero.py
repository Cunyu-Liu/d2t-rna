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


def chernoff_cte(p0, p1, channels, costs, budget, endpoint):
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


# ---- build a heterogeneous catalog with mixed channels + costs ----
def d2(den=4):
    return [(Fraction(i, den), Fraction(den - i, den)) for i in range(den + 1)]


def d3(den=2):
    out = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((Fraction(a, den), Fraction(b, den),
                        Fraction(den - a - b, den)))
    return out


d2v = d2(4)
d3v = d3(2)

# heterogeneous channels
id2a = O.id_channel(2)
id2b = O.id_channel(2)
pair3 = O.pair_channel(3)
id3 = O.id_channel(3)
merge2 = O.merge_channel(2)
noisy_id = O.noisy_channel(O.id_channel(2), 2, Fraction(1, 4))
# generic 2x2 channels
gen1 = O.generic_channel(((1, 0), (Fraction(1, 3), Fraction(2, 3))))
gen2 = O.generic_channel(((0, 1), (Fraction(2, 3), Fraction(1, 3))))

endpoint = Fraction(1, 10)
budget = Fraction(8)

# candidate cell configs: (name, p0, p1, [(channel, cost), ...])
configs = []
d2list = d2v
# CA-like but with heterogeneous channels and mixed costs
configs += [
    ("CA_het_mix", d2list[1], d2list[3], [(id2a, 1), (noisy_id, 1)]),
    ("CA_merge_id", d2list[1], d2list[3], [(merge2, 1), (id2a, 1)]),
    ("CA_genmix", d2list[0], d2list[3], [(gen1, 1), (gen2, 1)]),
    ("CA_genmix_c", d2list[1], d2list[3], [(gen1, 1), (gen2, 2)]),
    ("CA_1_3", d2list[1], d2list[3], [(id2a, 1)]),
]
# CC-like heterogeneous
for (i, j) in [(0, 3), (0, 4), (1, 3), (2, 4), (1, 4)]:
    p0 = d3v[i]
    p1 = d3v[j]
    configs.append((f"CC_{i}{j}_idpair", p0, p1, [(id3, 1), (pair3, 1)]))
    configs.append((f"CC_{i}{j}_idpair_c", p0, p1, [(id3, 2), (pair3, 1)]))
    configs.append((f"CC_{i}{j}_idpair_c2", p0, p1, [(id3, 1), (pair3, 2)]))

print("{:>18} {:>7} {:>14} {:>7} {:>14} {:>8}".format(
    "cell", "D2Tcte", "D2Talloc", "chercte", "cheralloc", "delta"))
wins = 0
tot = 0
for name, p0, p1, actcost in configs:
    channels = [ch for ch, c in actcost]
    costs = [Fraction(c) for ch, c in actcost]
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    cte = d2t_cost_to_endpoint(laws0, laws1, costs, budget, endpoint)
    cher_cte, cher_alloc = chernoff_cte(p0, p1, channels, costs, budget, endpoint)
    d_cte = cte[1] if cte else None
    d_alloc = cte[0] if cte else None
    delta = None
    if d_cte is not None and cher_cte is not None and cher_cte > 0:
        delta = float((d_cte - cher_cte) / cher_cte)
    if d_cte is not None and cher_cte is not None:
        tot += 1
        if delta < 0:
            wins += 1
    print("{:>18} {:>7} {:>14} {:>7} {:>14} {:>8}".format(
        name,
        str(d_cte) if d_cte is not None else "N/A",
        str(d_alloc),
        str(cher_cte) if cher_cte is not None else "N/A",
        str(cher_alloc),
        str(delta) if delta is not None else "N/A"))
print("wins:", wins, "/", tot)
