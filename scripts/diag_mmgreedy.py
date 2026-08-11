from fractions import Fraction
from itertools import product
from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def minimax_of(p0_laws, p1_laws, alloc):
    p0v, p1v = O.multi_product_laws(p0_laws, p1_laws, tuple(alloc))
    return O.randomized_minimax_error_from_laws(p0v, p1v)


def d2t_greedy_cost_to_endpoint(p0_laws, p1_laws, costs, budget, endpoint):
    """Deployable: myopic minimax-reduction greedy.

    Start at zero allocation. Repeatedly add ONE unit to the action whose
    marginal addition most reduces the current randomized-minimax error
    (cost-weighted). Stop when minimax <= endpoint. Returns allocation, cost.
    This is objective-aligned (minimizes minimax, not Chernoff proxy), is
    NOT exhaustive enumeration, and is O(budget*U*LP). If it cannot reach the
    endpoint within budget, returns None (no-go).
    """
    from fractions import Fraction as F
    U = len(costs)
    alloc = [0] * U
    cur = F(1)  # start at minimax 1 (no information)
    best_cost = None
    best_alloc = None
    spent = F(0)
    while True:
        # evaluate current
        mm = minimax_of(p0_laws, p1_laws, alloc)
        if mm is not None and mm <= endpoint:
            best_cost = spent
            best_alloc = tuple(alloc)
            break
        # pick action with best cost-weighted marginal minimax reduction
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
            # choose the action minimizing resulting minimax (lower is better)
            if best_mm is None or mm_u < best_mm:
                best_mm = mm_u
                best_u = u
        if best_u is None:
            break  # cannot add anything
        alloc[best_u] += 1
        spent += costs[best_u]
    return best_alloc, best_cost


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

endpoint = Fraction(1, 10)
budget = Fraction(8)

win = 0
tie = 0
loss = 0
no_go = 0
details = []
for i in range(6):
    for j in range(6):
        p0 = d3v[i]
        p1 = d3v[j]
        if p0 == p1:
            continue
        channels = [id3, pair3]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        d_alloc, d_cte = d2t_greedy_cost_to_endpoint(
            laws0, laws1, (Fraction(1), Fraction(1)), budget, endpoint)
        cher_cte, cher_alloc = chernoff_cte(p0, p1, channels, budget, endpoint)
        if d_cte is not None and cher_cte is not None:
            delta = float((d_cte - cher_cte) / cher_cte)
            if delta < 0:
                win += 1
                details.append((str(p0), str(p1), d_cte, d_alloc, cher_cte, cher_alloc, delta))
            elif delta == 0:
                tie += 1
            else:
                loss += 1
                details.append((str(p0), str(p1), d_cte, d_alloc, cher_cte, cher_alloc, delta))
        else:
            no_go += 1

print("D2T minimax-greedy vs Chernoff: win={} tie={} loss={} no_go={}".format(
    win, tie, loss, no_go))
print("--- non-tie cells ---")
for d in details:
    print("p0={} p1={}: D2T cte={} alloc={}  cher cte={} alloc={}  delta={:.3f}".format(*d))
