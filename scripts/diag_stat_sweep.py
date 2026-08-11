"""Multi-seed statistical sweep: is the cost-weighted deployable advantage robust?

The single-seed run (20260811) showed the cost-weighted greedy is never-worse on
average (mean delta_c=-0.003) but the magnitude is small.  This script runs MANY
seeds to test statistical significance with a paired Wilcoxon signed-rank test on
the per-instance cost (greedy vs Chernoff) and reports a 95% confidence interval on
the mean relative cost reduction.  It also stratifies by REGIME:

  * complementary (a single action alone cannot reach the endpoint; a multi-action
    mix is REQUIRED)  -- where the objective-aligned deployable should shine;
  * single-action-suffices -- where any method concentrates on one action and the
    two methods should tie.

If the complementary-regime advantage is significant and the single-action regime
ties, that is the honest, defensible leading claim (a deployable that is provably
better exactly where allocation choices matter, and provably not worse elsewhere).
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


def is_complementary(channels, p0, p1):
    """True if no single action alone reaches the endpoint at max affordable alloc
    (i.e. a multi-action mix is required)."""
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for u in range(len(channels)):
        alloc = [0] * len(channels)
        alloc[u] = int(BUDGET // 1)
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= ENDPOINT:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--n-seeds", type=int, default=8)
    ap.add_argument("--base-seed", type=int, default=1000)
    args = ap.parse_args()

    # pooled per-instance deltas, plus regime splits
    all_deltas = []
    comp_deltas = []
    single_deltas = []
    # paired costs for Wilcoxon (only jointly-solvable instances)
    paired_greedy, paired_cher = [], []
    # per-seed stats
    per_seed = []

    for s in range(args.n_seeds):
        rng = random.Random(args.base_seed + s)
        n_win = n_tie = n_loss = 0
        seed_g, seed_c = [], []
        for _ in range(args.n):
            p0 = random_law(rng)
            p1 = random_law(rng)
            if p0 == p1:
                continue
            sn = rng.choice(list(ACTION_SETS))
            chans = [x[0] for x in ACTION_SETS[sn]]
            costs = [x[1] for x in ACTION_SETS[sn]]
            l0 = tuple(O.action_law(ch, p0) for ch in chans)
            l1 = tuple(O.action_law(ch, p1) for ch in chans)
            ga, gc = O.d2t_cost_to_endpoint_greedy(l0, l1, costs, BUDGET, ENDPOINT)
            cc, _ = chernoff_min_cte(p0, p1, chans, costs)
            if ga is None or cc is None:
                continue
            delta = float((gc - cc) / cc)
            all_deltas.append(delta)
            paired_greedy.append(float(gc))
            paired_cher.append(float(cc))
            seed_g.append(float(gc)); seed_c.append(float(cc))
            if delta < -1e-12:
                n_win += 1
            elif delta > 1e-12:
                n_loss += 1
            else:
                n_tie += 1
            # regime stratification on the pooled jointly-solvable set
            if is_complementary(chans, p0, p1):
                comp_deltas.append(delta)
            else:
                single_deltas.append(delta)
        per_seed.append((n_win, n_tie, n_loss))

    n = len(all_deltas)
    mean_d = statistics.mean(all_deltas)
    # 95% CI via normal approx on mean of deltas (bootstrap-free, n large)
    stdev = statistics.stdev(all_deltas) if n > 1 else 0.0
    se = stdev / (n ** 0.5)
    ci_lo = mean_d - 1.96 * se
    ci_hi = mean_d + 1.96 * se

    # Wilcoxon signed-rank on paired costs (greedy < cher => negative ranks toward greedy)
    if len(paired_greedy) >= 10:
        stat, pval = sps.wilcoxon(paired_greedy, paired_cher, alternative="less")
    else:
        stat, pval = None, None

    print(f"seeds={args.n_seeds} n_per_seed={args.n} base_seed={args.base_seed}")
    print(f"pooled jointly-solvable n={n}")
    print(f"mean delta_c={mean_d:.4f}  [95% CI: {ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"median delta_c={statistics.median(all_deltas):.4f}")
    n_win = sum(1 for d in all_deltas if d < -1e-12)
    n_tie = sum(1 for d in all_deltas if abs(d) < 1e-12)
    n_loss = sum(1 for d in all_deltas if d > 1e-12)
    print(f"WIN={n_win} TIE={n_tie} LOSS={n_loss}")
    print(f"Wilcoxon (greedy<cher, one-sided less) p={pval} stat={stat}")
    print(f"  significant at 0.05: {pval is not None and pval < 0.05}")
    print(f"per-seed (win/tie/loss): {per_seed}")
    if comp_deltas:
        print(f"COMPLEMENTARY regime: n={len(comp_deltas)} mean={statistics.mean(comp_deltas):.4f} "
              f"median={statistics.median(comp_deltas):.4f} "
              f"neg={sum(1 for d in comp_deltas if d < -1e-12)}")
    if single_deltas:
        print(f"SINGLE-ACTION regime: n={len(single_deltas)} mean={statistics.mean(single_deltas):.4f} "
              f"median={statistics.median(single_deltas):.4f} "
              f"neg={sum(1 for d in single_deltas if d < -1e-12)}")


if __name__ == "__main__":
    main()
