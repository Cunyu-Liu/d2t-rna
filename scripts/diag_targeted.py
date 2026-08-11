"""diag_targeted.py -- test hand-constructed candidate distinguishing cells.

Mechanism: D2T's exact cost-to-endpoint solver finds the minimum-cost
allocation to reach the endpoint under randomized minimax.  Chernoff's greedy
(score = chernoff_info / cost) concentrates all budget on the single best
info/cost action.  With HETEROGENEOUS costs and overlapping support, the
greedy can pick a weak-but-cheap action that needs many units (high total
cost), while D2T correctly picks a strong-but-expensive action reaching the
endpoint in few units.  All channels here have overlapping support so Chernoff
information is finite (no disjoint-support bug path).
"""

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper
from d2t_rna.evaluation.wrappers import helpers as H

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(10)


def d2t_cte(p0_laws, p1_laws, costs, budget, endpoint=ENDPOINT):
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
            return Fraction(b), tuple(run["allocation"]), mm
    return None, None, None


id3 = O.id_channel(3)
pair3 = O.pair_channel(3)
merge3 = O.merge_channel(3)
noid3 = O.noisy_channel(O.id_channel(3), 3, Fraction(1, 4))
nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))


def test(name, p0, p1, channels, costs):
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    d = d2t_cte(laws0, laws1, costs, BUDGET)
    c, c_alloc, c_mm = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
    d_cte = d[1] if d else None
    d_alloc = d[0] if d else None
    if d_cte is not None and c is not None:
        delta = float((d_cte - c) / c) if c > 0 else None
        verdict = "WIN" if d_cte < c else ("TIE" if d_cte == c else "LOSS")
    else:
        verdict = "NOGO"
        delta = None
    print(f"[{verdict:4s}] {name}: D2Tcte={d_cte} D2Talloc={d_alloc} "
          f"chercte={c} cheralloc={c_alloc} delta={delta if delta is None else round(delta,3)}")


# ---- Candidate 1: strong-expensive id vs weak-cheap noisy pair ----
p0 = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
p1 = (Fraction(0), Fraction(1, 2), Fraction(1, 2))
test("id3(c3)+nopair3(c1) overlap", p0, p1, [id3, nopair3], [Fraction(3), Fraction(1)])

# ---- Candidate 2 ----
p0 = (Fraction(1, 3), Fraction(2, 3), Fraction(0))
p1 = (Fraction(0), Fraction(2, 3), Fraction(1, 3))
test("id3(c3)+nopair3(c1) B", p0, p1, [id3, nopair3], [Fraction(3), Fraction(1)])

# ---- Candidate 3: id strong c3 vs pair cheap c1 ----
p0 = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
p1 = (Fraction(0), Fraction(1, 2), Fraction(1, 2))
test("id3(c3)+pair3(c1)", p0, p1, [id3, pair3], [Fraction(3), Fraction(1)])

# ---- Candidate 4: noisy id (c2) vs noisy pair (c1) ----
test("noid3(c2)+nopair3(c1)", p0, p1, [noid3, nopair3], [Fraction(2), Fraction(1)])

# ---- Candidate 5: id c2 vs nopair c1 ----
test("id3(c2)+nopair3(c1)", p0, p1, [id3, nopair3], [Fraction(2), Fraction(1)])

# ---- Candidate 6: id c1 vs nopair c1 (tie expected; info ordering) ----
test("id3(c1)+nopair3(c1)", p0, p1, [id3, nopair3], [Fraction(1), Fraction(1)])

# ---- Candidate 7: different p0/p1, id c4 vs nopair c1 ----
p0 = (Fraction(3, 4), Fraction(1, 4), Fraction(0))
p1 = (Fraction(0), Fraction(1, 4), Fraction(3, 4))
test("id3(c4)+nopair3(c1)", p0, p1, [id3, nopair3], [Fraction(4), Fraction(1)])

# print chernoff info ratios for candidate 1 to confirm greedy picks weak-cheap
print("\n--- chernoff info/cost for candidate 1 ---")
for nm, ch, c in [("id3", id3, 3), ("nopair3", nopair3, 1)]:
    q0 = O.action_law(ch, (Fraction(1, 2), Fraction(1, 2), Fraction(0)))
    q1 = O.action_law(ch, (Fraction(0), Fraction(1, 2), Fraction(1, 2)))
    info = H.chernoff_information(q0, q1)
    print(f"{nm}: info={info:.4f} info/cost={info/c:.4f}")
