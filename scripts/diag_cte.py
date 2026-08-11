from fractions import Fraction
from itertools import product
from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def d2t_cost_to_endpoint(p0_laws, p1_laws, costs, budget, endpoint):
    from fractions import Fraction as F
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
id2 = [("id_a", O.id_channel(2)), ("id_b", O.id_channel(2))]
id3 = [("id", O.id_channel(3)), ("pair", O.pair_channel(3))]
pools = [
    ("CA", 2, [d2v[1], d2v[3]], [d2v[0], d2v[2], d2v[4]], id2),
    ("CB", 2, [d2v[0], d2v[2], d2v[4]], [d2v[1], d2v[3]], id2),
    ("CC", 3, [d3v[0], d3v[1], d3v[2]], [d3v[3], d3v[4]], id3),
    ("CD", 3, [d3v[1], d3v[3], d3v[4]], [d3v[0], d3v[2], d3v[5]], id3),
]
pair_idx = {
    "CA": [(0, 0), (1, 0), (0, 1), (1, 1), (1, 2)],
    "CB": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    "CC": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
    "CD": [(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)],
}
budget = Fraction(8)
cost = Fraction(1)
endpoint = Fraction(1, 10)
chernoff = ControlledSensingWrapper()
hdr = "{:>10} {:>7} {:>16} {:>7} {:>16} {:>14} {:>9}".format(
    "cell", "D2Tcte", "D2Talloc", "chercte", "cheralloc", "fullmm", "delta")
print(hdr)
rows = []
for cid, n, t0, t1, actions in pools:
    for k, (i, j) in enumerate(pair_idx[cid], 1):
        p0 = tuple(t0[i])
        p1 = tuple(t1[j])
        channels = [ch for _nm, ch in actions]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        cte = d2t_cost_to_endpoint(laws0, laws1, (cost,) * n, budget, endpoint)
        # chernoff greedy cost-to-endpoint: min budget to reach endpoint
        cher_cte = None
        cher_alloc = None
        for b in range(0, 9):
            run = chernoff.run({
                "p0": p0, "p1": p1, "actions": channels,
                "costs": [1] * n, "budget": Fraction(b),
            })
            p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(run["allocation"]))
            mm = O.randomized_minimax_error_from_laws(p0v, p1v)
            if mm is not None and mm <= endpoint:
                cher_cte = Fraction(b)
                cher_alloc = tuple(run["allocation"])
                break
        d_alloc = cte[0] if cte else None
        d_cte = cte[1] if cte else None
        delta = None
        if d_cte is not None and cher_cte is not None:
            delta = float((d_cte - cher_cte) / cher_cte)
        fullmm = None
        if n == 2:
            f0, f1 = O.multi_product_laws(
                laws0, laws1, tuple(int(budget) for _ in channels))
            fullmm = O.randomized_minimax_error_from_laws(f0, f1)
        rows.append((f"{cid}_p{k}", d_cte, d_alloc, cher_cte, cher_alloc, fullmm, delta))
        print("{:>10} {:>7} {:>16} {:>7} {:>16} {:>14} {:>9}".format(
            f"{cid}_p{k}",
            str(d_cte) if d_cte is not None else "N/A",
            str(d_alloc),
            str(cher_cte) if cher_cte is not None else "N/A",
            str(cher_alloc),
            str(fullmm) if fullmm is not None else "N/A",
            str(delta) if delta is not None else "N/A"))

negs = [r for r in rows if r[6] is not None and r[6] < 0]
ties = [r for r in rows if r[6] is not None and r[6] == 0]
print("n_negative_delta:", len(negs), "n_tie:", len(ties))
print("negative cells:", [r[0] for r in negs])
