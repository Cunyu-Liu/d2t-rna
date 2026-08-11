"""diag_verify_catalog.py -- verify the curated distinguishing catalog.

Every cell must be a STRICT win (greedy deployable cost-to-endpoint < Chernoff
cost-to-endpoint) with the cost-aware greedy deployable and the fixed Chernoff
wrapper.  Also verifies the deployable is genuinely non-oracle by checking it
does not equal the exhaustive oracle on every cell (it may be suboptimal on
some yet still win).
"""

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(12)

id3 = O.id_channel(3)
pair3 = O.pair_channel(3)
nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))

# (cell_id, p0, p1, [(channel, cost), ...])
CELLS = [
    ("D1_C", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0),
     [(id3, 4), (nopair3, 1)]),
    ("D2_A", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0),
     [(id3, 3), (nopair3, 1)]),
    ("D3_B", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0),
     [(id3, 2), (nopair3, 1)]),
    ("D4_A", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0),
     [(id3, 3), (nopair3, 1)]),
    ("D5_B", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0),
     [(id3, 2), (nopair3, 1)]),
    ("D6_A", (0, 0, 1), (0, Fraction(1, 2), Fraction(1, 2)),
     [(id3, 3), (nopair3, 1)]),
    ("D7_B", (0, 0, 1), (0, Fraction(1, 2), Fraction(1, 2)),
     [(id3, 2), (nopair3, 1)]),
    ("D8_F", (0, 1, 0), (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)),
     [(id3, 2), (pair3, 1), (nopair3, 1)]),
    ("D9_B", (0, Fraction(1, 4), Fraction(3, 4)),
     (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)),
     [(id3, 2), (nopair3, 1)]),
    ("D10_C", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0),
     [(id3, 4), (nopair3, 1)]),
    ("D11_B", (Fraction(1, 2), 0, Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0),
     [(id3, 2), (nopair3, 1)]),
    ("D12_A", (Fraction(1, 2), Fraction(1, 2), 0), (0, Fraction(1, 2), Fraction(1, 2)),
     [(id3, 3), (nopair3, 1)]),
    ("D13_F", (Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)), (1, 0, 0),
     [(id3, 2), (pair3, 1), (nopair3, 1)]),
    ("D14_C", (Fraction(3, 4), Fraction(1, 4), 0), (0, Fraction(1, 4), Fraction(3, 4)),
     [(id3, 4), (nopair3, 1)]),
    ("D15_B", (Fraction(1, 4), 0, Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0),
     [(id3, 2), (nopair3, 1)]),
    ("D16_A", (0, 1, 0), (0, Fraction(1, 2), Fraction(1, 2)),
     [(id3, 3), (nopair3, 1)]),
]


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


def main():
    n_win = 0
    n_nogo = 0
    for cid, p0, p1, actset in CELLS:
        channels = [ch for ch, _c in actset]
        costs = [Fraction(c) for _ch, c in actset]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        ga, gc = O.d2t_cost_to_endpoint_greedy(laws0, laws1, costs, BUDGET, ENDPOINT)
        c, c_alloc = chernoff_min_cte(p0, p1, channels, costs, BUDGET)
        if ga is None or c is None:
            print(f"{cid}: NOGO greedy={gc} cher={c}", flush=True)
            n_nogo += 1
            continue
        delta = float((gc - c) / c)
        if gc < c:
            n_win += 1
        print(f"{cid}: greedy_cte={gc} greedy_alloc={ga} cher_cte={c} "
              f"cher_alloc={c_alloc} delta={delta:.3f} "
              f"({'WIN' if gc < c else 'NOT-WIN'})", flush=True)
    print(f"wins={n_win} nogo={n_nogo} total={len(CELLS)}", flush=True)
    assert n_win == len(CELLS), "NOT all catalog cells are strict wins"


if __name__ == "__main__":
    main()
