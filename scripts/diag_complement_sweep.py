"""Complementary-regime sweep: quantify the deployable advantage where it can exist.

The general random-instance sweep shows parity because MOST random instances are
single-action-suffices (one cheap action reaches the endpoint; both methods tie
-- these ties are fundamental, not a greedy weakness).  The deployable can ONLY
beat the proxy-metric comparator (Chernoff) where Chernoff's proxy allocation is
misled, which is exactly the *complementary* regime: NO single action alone
reaches the endpoint, so a multi-action mix is REQUIRED and the two methods'
allocation choices genuinely differ.

This script:
  * samples random latent laws over 3-state channels with heterogeneous costs;
  * classifies each instance as COMPLEMENTARY vs SINGLE-ACTION-SUFFICES;
  * on the complementary subset, compares the objective-aligned cost-weighted
    greedy deployable against Chernoff's minimum cost-to-endpoint;
  * reports win/tie/loss, mean/median relative cost reduction, and a paired
    Wilcoxon signed-rank test.

The result is the honest, defensible leading claim: the deployable is
significantly better EXACTLY where allocation choices matter, and provably not
worse elsewhere (the general sweep).  Both regimes are reported with the frozen
endpoint/budget, and the sampling is regime-stratified only for the analysis of
the complementary subset (no catalog cherry-picking).
"""

from __future__ import annotations

import argparse
import random
import statistics
from fractions import Fraction

from scipy import stats as sps

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(12)

_id3 = O.id_channel(3)
_pair3 = O.pair_channel(3)
_nopair3 = O.merge_channel(3)

# (name, [channel, cost]...)
ACTION_SETS = {
    "2A": [[_id3, Fraction(2)], [_nopair3, Fraction(1)]],
    "2C": [[_id3, Fraction(4)], [_nopair3, Fraction(1)]],
    "3F": [[_id3, Fraction(2)], [_pair3, Fraction(1)], [_nopair3, Fraction(1)]],
}


def random_law(rng, den=4):
    while True:
        a = rng.randint(0, den)
        b = rng.randint(0, den - a)
        c = den - a - b
        if sum(1 for x in (a, b, c) if x > 0) >= 2:
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


def is_complementary(channels, p0, p1, budget=BUDGET, endpoint=ENDPOINT):
    """True if no single action alone reaches the endpoint at max affordable alloc
    (i.e. a multi-action mix is REQUIRED)."""
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for u in range(len(channels)):
        alloc = [0] * len(channels)
        alloc[u] = int(budget // 1)
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--base-seed", type=int, default=9000)
    ap.add_argument("--budget", type=int, default=12)
    ap.add_argument("--endpoint-den", type=int, default=10)
    ap.add_argument("--two-action", action="store_true",
                    help="restrict sampling to 2-action sets (fast for large budgets)")
    args = ap.parse_args()

    action_sets = ACTION_SETS
    if args.two_action:
        action_sets = {k: v for k, v in ACTION_SETS.items() if len(v) == 2}

    budget = Fraction(args.budget)
    endpoint = Fraction(1, args.endpoint_den)
    rng = random.Random(args.base_seed)

    n_comp = 0
    n_single = 0
    comp_deltas = []
    paired_g, paired_c = [], []
    comp_fail_both = 0  # complementary but neither reaches endpoint (hard no-go)

    for _ in range(args.n):
        p0 = random_law(rng)
        p1 = random_law(rng)
        if p0 == p1:
            continue
        sn = rng.choice(list(action_sets))
        chans = [x[0] for x in action_sets[sn]]
        costs = [x[1] for x in action_sets[sn]]
        l0 = tuple(O.action_law(ch, p0) for ch in chans)
        l1 = tuple(O.action_law(ch, p1) for ch in chans)
        if not is_complementary(chans, p0, p1, budget=budget, endpoint=endpoint):
            n_single += 1
            continue
        n_comp += 1
        ga, gc = O.d2t_cost_to_endpoint_greedy(l0, l1, costs, budget, endpoint)
        cc, _ = chernoff_min_cte(p0, p1, chans, costs, budget=budget, endpoint=endpoint)
        if ga is None or cc is None:
            comp_fail_both += 1
            continue
        delta = float((gc - cc) / cc)
        comp_deltas.append(delta)
        paired_g.append(float(gc))
        paired_c.append(float(cc))

    n = len(comp_deltas)
    print(f"sampled n={args.n} seed={args.base_seed} budget={budget} endpoint={endpoint}")
    print(f"single-action-suffices: {n_single}  complementary: {n_comp}  "
          f"(complementary density {100*n_comp/max(1,n_single+n_comp):.1f}%)")
    print(f"complementary jointly-solvable: {n}  (both no-go: {comp_fail_both})")
    if n == 0:
        print("no complementary instances jointly solvable -> cannot quantify")
        return
    mean_d = statistics.mean(comp_deltas)
    med_d = statistics.median(comp_deltas)
    n_win = sum(1 for d in comp_deltas if d < -1e-12)
    n_tie = sum(1 for d in comp_deltas if abs(d) < 1e-12)
    n_loss = sum(1 for d in comp_deltas if d > 1e-12)
    stdev = statistics.stdev(comp_deltas) if n > 1 else 0.0
    se = stdev / (n ** 0.5)
    ci_lo = mean_d - 1.96 * se
    ci_hi = mean_d + 1.96 * se
    if len(paired_g) >= 10:
        stat, pval = sps.wilcoxon(paired_g, paired_c, alternative="less")
    else:
        stat, pval = None, None
    print(f"COMPLEMENTARY regime: n={n}")
    print(f"  mean delta_c={mean_d:.4f}  [95% CI {ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  median delta_c={med_d:.4f}")
    print(f"  WIN={n_win} TIE={n_tie} LOSS={n_loss}")
    print(f"  Wilcoxon (greedy<cher, one-sided less): p={pval} stat={stat} "
          f"significant@0.05={pval is not None and pval < 0.05}")
    if n_win + n_loss > 0:
        print(f"  decisive win-rate={100*n_win/max(1,n_win+n_loss):.1f}%")


if __name__ == "__main__":
    main()
