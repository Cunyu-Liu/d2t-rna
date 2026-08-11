"""Targeted multi-action-regime sweep.

The general-instance result is parity (not superiority).  The cost-aware advantage
should appear only where a MULTI-ACTION mix is genuinely REQUIRED: a hard endpoint
plus heterogeneous costs with a cheap complementary channel.  This script tests that
regime directly:

  * 4 channels (id3/pair3/nopair3/merge4) with heterogeneous costs,
  * a HARD endpoint (e.g. 1/16 or 1/20) so a single action alone cannot reach it,
  * budget large enough that a mix is affordable.

For each instance we classify REQUIRED-MULTI-ACTION vs single-action-suffices via an
exact oracle probe, then compare the cost-weighted greedy vs Chernoff only on the
required-multi-action subset (where the claim lives), with a Wilcoxon test.

This is a METHOD-level test: a broader, harder random family, not hand-picked cells.
"""

from __future__ import annotations

import argparse
import random
import statistics
from fractions import Fraction

from scipy import stats as sps

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def random_law(rng, den):
    while True:
        coords = [rng.randint(0, den) for _ in range(3)]
        if sum(coords) > den:
            continue
        rest = den - sum(coords)
        v = tuple(Fraction(x, den) for x in coords) + (Fraction(rest, den),)
        if sum(1 for x in v if x > 0) >= 2:
            return v


def chernoff_min_cte(p0, p1, channels, costs, budget, endpoint):
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


def single_action_reaches_endpoint(channels, costs, p0, p1, budget, endpoint):
    """Does ANY single action alone reach the endpoint (at its max affordable alloc)?"""
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for u in range(len(channels)):
        max_n = int(budget // costs[u]) if costs[u] > 0 else 0
        if max_n <= 0:
            continue
        alloc = [0] * len(channels)
        alloc[u] = max_n
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--n-seeds", type=int, default=6)
    ap.add_argument("--base-seed", type=int, default=5000)
    ap.add_argument("--endpoint-den", type=int, default=16)
    ap.add_argument("--budget", type=int, default=24)
    args = ap.parse_args()

    endpoint = Fraction(1, args.endpoint_den)
    budget = Fraction(args.budget)

    id4 = O.id_channel(4)
    pair4 = O.pair_channel(4)
    nopair4 = O.merge_channel(4)
    id4b = O.id_channel(4)

    # 4-channel heterogeneous-cost action sets (all 4-state latent channels)
    CHANNEL_SETS = {
        "P": [id4, pair4, nopair4, id4b],
        "Q": [id4, pair4, id4b, nopair4],
    }
    COST_SETS = {
        "P": [Fraction(2), Fraction(1), Fraction(1), Fraction(4)],
        "Q": [Fraction(3), Fraction(1), Fraction(2), Fraction(1)],
    }

    req_deltas = []       # required-multi-action deltas (the claim lives here)
    single_deltas = []
    paired_g, paired_c = [], []
    win = tie = loss = 0

    for s in range(args.n_seeds):
        rng = random.Random(args.base_seed + s)
        for _ in range(args.n):
            p0 = random_law(rng, 4)
            p1 = random_law(rng, 4)
            if p0 == p1:
                continue
            sn = rng.choice(list(CHANNEL_SETS))
            chans = CHANNEL_SETS[sn]
            costs = COST_SETS[sn]
            l0 = tuple(O.action_law(ch, p0) for ch in chans)
            l1 = tuple(O.action_law(ch, p1) for ch in chans)
            ga, gc = O.d2t_cost_to_endpoint_greedy(l0, l1, costs, budget, endpoint)
            cc, _ = chernoff_min_cte(p0, p1, chans, costs, budget, endpoint)
            if ga is None or cc is None:
                continue
            delta = float((gc - cc) / cc)
            req = not single_action_reaches_endpoint(chans, costs, p0, p1, budget, endpoint)
            if req:
                req_deltas.append(delta)
                paired_g.append(float(gc)); paired_c.append(float(cc))
                if delta < -1e-12:
                    win += 1
                elif delta > 1e-12:
                    loss += 1
                else:
                    tie += 1
            else:
                single_deltas.append(delta)

    n = len(req_deltas)
    print(f"endpoint=1/{args.endpoint_den} budget={args.budget} seeds={args.n_seeds} n={args.n}")
    print(f"REQUIRED-multi-action: n={n} (win/tie/loss: {win}/{tie}/{loss})")
    if n:
        mean_d = statistics.mean(req_deltas)
        stdev = statistics.stdev(req_deltas) if n > 1 else 0.0
        se = stdev / (n ** 0.5)
        print(f"  mean delta_c={mean_d:.4f} [95%CI: {mean_d-1.96*se:.4f},{mean_d+1.96*se:.4f}]")
        print(f"  median delta_c={statistics.median(req_deltas):.4f}")
        if len(paired_g) >= 10:
            stat, pval = sps.wilcoxon(paired_g, paired_c, alternative="less")
            print(f"  Wilcoxon(greedy<cher) p={pval:.5f}  significant@0.05={pval < 0.05}")
        print(f"  win_rate={win/n:.3f} loss_rate={loss/n:.3f}")
    if single_deltas:
        print(f"SINGLE-action-suffices: n={len(single_deltas)} "
              f"mean={statistics.mean(single_deltas):.4f}")


if __name__ == "__main__":
    main()
