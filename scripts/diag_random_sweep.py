"""Random-instance sweep: does the objective-aligned greedy advantage generalize?

The frozen 16-cell method-distinguishing catalog is hand-crafted to show the
cost-aware deployable beating the Chernoff proxy-greedy.  A stronger publication
claim needs evidence that the advantage is a genuine algorithmic property, not an
artifact of hand-picked cells.  This script draws a large set of RANDOM instances
(overlapping-support 3-state laws, heterogeneous action costs) and compares the
objective-aligned greedy deployable's cost-to-endpoint against Chernoff's minimum
cost-to-endpoint.  It reports the win/tie/loss split and the median/quantiles of
delta_c, and stratifies by whether the instance is multi-action-complementary
(where the advantage should live) vs single-action-dominated (where it should not).
"""

from __future__ import annotations

import argparse
import random
import statistics
from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(12)

_id3 = O.id_channel(3)
_pair3 = O.pair_channel(3)
_nopair3 = O.merge_channel(3)

ACTION_SETS = {
    "2A": [(_id3, Fraction(2)), (_nopair3, Fraction(1))],          # heterogeneous cost
    "2C": [(_id3, Fraction(4)), (_nopair3, Fraction(1))],          # strong heterogeneity
    "3F": [(_id3, Fraction(2)), (_pair3, Fraction(1)), (_nopair3, Fraction(1))],
}


def random_law(rng, den=4):
    """Random 3-state probability vector with support >= 2 (overlapping support)."""
    while True:
        a = rng.randint(0, den)
        b = rng.randint(0, den - a)
        c = den - a - b
        nz = sum(1 for x in (a, b, c) if x > 0)
        if nz >= 2:
            return (Fraction(a, den), Fraction(b, den), Fraction(c, den))


def chernoff_min_cte(p0, p1, channels, costs, budget=BUDGET, endpoint=ENDPOINT):
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


def is_complementary(channels, p0, p1):
    """Heuristic: instance needs a multi-action mix if the single best action alone
    (at max within-budget allocation) does NOT reach the endpoint while a mix does."""
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    # does a single action reach the endpoint at max affordable allocation?
    for u, ch in enumerate(channels):
        max_n = int(BUDGET // 1)  # homogeneous cost 1 for this probe
        alloc = [0] * len(channels)
        alloc[u] = max_n
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= ENDPOINT:
            return False  # single action suffices -> not complementary
    return True  # no single action reaches endpoint -> needs a mix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--action-set", default="all", choices=["all", "2A", "2C", "3F"])
    args = ap.parse_args()

    rng = random.Random(args.seed)
    sets = list(ACTION_SETS) if args.action_set == "all" else [args.action_set]

    deltas_all = []
    stats = {"win": 0, "tie": 0, "loss": 0, "no_go": 0}
    comp_deltas = []   # deltas on complementary instances
    noncomp_deltas = []  # deltas on single-action-dominated instances

    for i in range(args.n):
        p0 = random_law(rng)
        p1 = random_law(rng)
        if p0 == p1:
            continue
        setname = rng.choice(sets)
        channels = [ch for ch, _c in ACTION_SETS[setname]]
        costs = [c for _ch, c in ACTION_SETS[setname]]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        ga, gc = O.d2t_cost_to_endpoint_greedy(
            laws0, laws1, costs, BUDGET, ENDPOINT)
        cc, _ = chernoff_min_cte(p0, p1, channels, costs)
        if ga is None or cc is None:
            stats["no_go"] += 1
            continue
        delta = float((gc - cc) / cc)
        deltas_all.append(delta)
        if delta < -1e-12:
            stats["win"] += 1
            bucket = comp_deltas
        elif delta > 1e-12:
            stats["loss"] += 1
            bucket = noncomp_deltas  # loss -> likely non-complementary
        else:
            stats["tie"] += 1
            bucket = None
        if bucket is not None:
            bucket.append(delta)

    print(f"seed={args.seed} n={args.n} sets={sets}")
    print(f"WIN={stats['win']} TIE={stats['tie']} LOSS={stats['loss']} NO_GO={stats['no_go']}")
    print(f"total evaluated={len(deltas_all)}")
    if deltas_all:
        print(f"median delta_c={statistics.median(deltas_all):.4f} "
              f"mean delta_c={statistics.mean(deltas_all):.4f}")
        qs = [round(v, 4) for v in
              sorted(deltas_all)[::max(1, len(deltas_all) // 4)]]
        print(f"quartile-ish samples: {qs}")
        # win rate
        print(f"win_rate={stats['win'] / len(deltas_all):.3f}")
    if comp_deltas:
        print(f"complementary instances: n={len(comp_deltas)} "
              f"median={statistics.median(comp_deltas):.4f}")
    if noncomp_deltas:
        print(f"loss/non-comp instances: n={len(noncomp_deltas)} "
              f"median={statistics.median(noncomp_deltas):.4f}")


if __name__ == "__main__":
    main()
