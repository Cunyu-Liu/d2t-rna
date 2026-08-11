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


# ---- Test 1: complementary coverage on a JOINT latent state ----
# Latent state w in {00,01,10,11} (2 binary coordinates).
# H0: w = 00 or 11 (coordinates EQUAL). H1: w = 01 or 10 (coordinates DIFFERENT).
# Action A reads only coordinate 1. Action B reads only coordinate 2.
# Neither single action can separate {equal} vs {different} by itself;
# only the JOINT observation separates them => multi-action is REQUIRED.
endpoint = Fraction(1, 10)
budget = Fraction(8)

# Under equal prior over the 4 states, H0 mass on {00,11}, H1 mass on {01,10}
# Marginals: P(coord1=0)=P(coord1=1)=1/2 for both H0 and H1 (identical marginal!)
# => single coordinate is completely uninformative (bayes err 1/2).
p0 = (Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4))  # equal mass on all
p1 = (Fraction(1, 4), Fraction(1, 4), Fraction(1, 4), Fraction(1, 4))  # same -> degenerate

# Instead: H0 concentrated on 00 & 11; H1 concentrated on 01 & 10.
p0 = (Fraction(1, 2), Fraction(0), Fraction(0), Fraction(1, 2))
p1 = (Fraction(0), Fraction(1, 2), Fraction(1, 2), Fraction(0))
# action A: reads coord1. channel rows = output over coord1 given state
# state 00->c1=0, 01->c1=0, 10->c1=1, 11->c1=1
chA = O.generic_channel(((1, 0), (0, 1)))  # this is 2x2 identity? no
# Need channel mapping 4 latent states -> 2 outputs
chA4 = O.generic_channel((
    (1, 1, 0, 0),  # output coord1=0 given states 00,01 (coord1=0), not 10,11
    (0, 0, 1, 1),  # output coord1=1 given states 10,11 (coord1=1)
))
# state index w in {0,1,2,3} = {00,01,10,11} (c1,c2)
# chB4 row0 = P(c2=0|w): c2=0 for 00(w0),10(w2) -> (1,0,1,0)
# chB4 row1 = P(c2=1|w): c2=1 for 01(w1),11(w3) -> (0,1,0,1)
chB4 = O.generic_channel((
    (1, 0, 1, 0),  # output coord2=0 given states 00,10 (coord2=0)
    (0, 1, 0, 1),  # output coord2=1 given states 01,11 (coord2=1)
))

def run_case(name, p0, p1, channels, costs):
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    cte = d2t_cost_to_endpoint(laws0, laws1, costs, budget, endpoint)
    cher_cte, cher_alloc = chernoff_cte(p0, p1, channels, costs, budget, endpoint)
    d_cte = cte[1] if cte else None
    d_alloc = cte[0] if cte else None
    delta = None
    if d_cte is not None and cher_cte is not None and cher_cte > 0:
        delta = float((d_cte - cher_cte) / cher_cte)
    print("{:>20} D2Tcte={} D2Talloc={} chercte={} cheralloc={} delta={}".format(
        name, d_cte, d_alloc, cher_cte, cher_alloc, delta))


# single action A only: expected to be no-go (can't separate)
print("== complementary coverage (joint latent state) ==")
run_case("joint_A_only", p0, p1, [chA4], [Fraction(1)])
run_case("joint_B_only", p0, p1, [chB4], [Fraction(1)])
run_case("joint_A_and_B", p0, p1, [chA4, chB4], [Fraction(1), Fraction(1)])
run_case("joint_A_and_B_c", p0, p1, [chA4, chB4], [Fraction(1), Fraction(3)])
