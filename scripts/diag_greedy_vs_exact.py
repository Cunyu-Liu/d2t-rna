from fractions import Fraction
from itertools import product
from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def minimax_of(p0_laws, p1_laws, alloc):
    p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
    return O.randomized_minimax_error_from_laws(p0v, p1v)


def d2t_greedy_cte(p0_laws, p1_laws, costs, budget, endpoint):
    from fractions import Fraction as F
    U = len(costs)
    alloc = [0] * U
    spent = F(0)
    while True:
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            return tuple(alloc), spent
        best_u = None
        best_mm = None
        for u in range(U):
            if spent + costs[u] > budget:
                continue
            alloc[u] += 1
            mm_u = minimax_of(p0_laws, p1_laws, alloc)
            alloc[u] -= 1
            if mm_u is None:
                continue
            if best_mm is None or mm_u < best_mm:
                best_mm = mm_u
                best_u = u
        if best_u is None:
            return None, None
        alloc[best_u] += 1
        spent += costs[best_u]


def d2t_exact_cte(p0_laws, p1_laws, costs, budget, endpoint):
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
merge3 = O.merge_channel(3)
endpoint = Fraction(1, 10)
budget = Fraction(8)

# compare greedy vs exact: does greedy ever differ (suboptimal)?
subopt = 0
match = 0
gnot = 0
for i in range(6):
    for j in range(6):
        p0 = d3v[i]
        p1 = d3v[j]
        if p0 == p1:
            continue
        for aname, chans in [("idpair", [id3, pair3]),
                             ("idpairmerge", [id3, pair3, merge3])]:
            laws0 = tuple(O.action_law(ch, p0) for ch in chans)
            laws1 = tuple(O.action_law(ch, p1) for ch in chans)
            ga, gc = d2t_greedy_cte(laws0, laws1, (Fraction(1),) * len(chans),
                                    budget, endpoint)
            ex = d2t_exact_cte(laws0, laws1, (Fraction(1),) * len(chans),
                               budget, endpoint)
            ec = ex[1] if ex else None
            if gc is not None and ec is not None:
                if gc > ec:
                    subopt += 1
                else:
                    match += 1
            elif gc is None and ex is None:
                gnot += 1
print("greedy==exact:", match, " greedy suboptimal (> exact):", subopt,
      " both no-go:", gnot)
print("=> greedy is a genuine non-oracle algorithm:", subopt > 0)
