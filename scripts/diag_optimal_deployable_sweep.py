"""Optimal-deployable vs Chernoff: the new deployable principle.

The myopic greedy had 49 LOSSES vs Chernoff on the general family -- it is
suboptimal in cases where Chernoff is optimal.  The NEW deployable principle is
to make the deployable the EXACT OPTIMAL cost-to-endpoint solver
(``d2t_cost_to_endpoint``): the minimum-cost within-budget allocation whose
induced product laws reach the randomized-minimax endpoint.

THEOREM (provable): the optimal cost-to-endpoint deployable is NEVER worse than
any comparator.  Chernoff's allocation is a valid within-budget allocation that
reaches the endpoint (by definition of its min-CTE), so the optimal deployable's
cost is <= Chernoff's cost on every jointly-solvable instance.  It strictly beats
Chernoff exactly when Chernoff's proxy allocation is suboptimal.

This turns the claim from an empirical "never-worse-on-average" into a PROVABLE
dominance, and QUANTIFIES how much the standard proxy-metric method (Chernoff)
loses -- i.e. how often and how much objective-alignment matters.

We also report deployable-only no-go (optimal deployable fails where Chernoff
succeeds) -- the only way the theorem could be violated is the MAX_OUTCOMES LP
withholding, which we must surface honestly (fail-closed).
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--n-seeds", type=int, default=3)
    ap.add_argument("--base-seed", type=int, default=1500)
    ap.add_argument("--two-action", action="store_true",
                    help="restrict to 2-action sets (fast; validates the dominance theorem)")
    args = ap.parse_args()

    action_sets = ACTION_SETS
    if args.two_action:
        action_sets = {k: v for k, v in ACTION_SETS.items() if len(v) == 2}

    deltas = []
    paired_g, paired_c = [], []
    n_win = n_tie = n_loss = 0
    n_dep_only_nogo = 0
    n_joint = 0
    per_seed = []

    for s in range(args.n_seeds):
        rng = random.Random(args.base_seed + s)
        seed_deltas = []
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
            exact = O.d2t_cost_to_endpoint(l0, l1, costs, BUDGET, ENDPOINT)
            cc, _ = chernoff_min_cte(p0, p1, chans, costs)
            if cc is not None and exact is None:
                n_dep_only_nogo += 1
            if exact is None or cc is None:
                continue
            gc = exact[1]
            delta = float((gc - cc) / cc)
            deltas.append(delta)
            seed_deltas.append(delta)
            paired_g.append(float(gc))
            paired_c.append(float(cc))
            if delta < -1e-12:
                n_win += 1
            elif delta > 1e-12:
                n_loss += 1
            else:
                n_tie += 1
            n_joint += 1
        per_seed.append((sum(1 for d in seed_deltas if d < -1e-12),
                         sum(1 for d in seed_deltas if abs(d) < 1e-12),
                         sum(1 for d in seed_deltas if d > 1e-12)))

    n = len(deltas)
    print(f"seeds={args.n_seeds} n_per_seed={args.n} base_seed={args.base_seed}")
    print(f"pooled jointly-solvable n={n}  dep-only-no-go-where-cher-succeeds={n_dep_only_nogo}")
    if n == 0:
        print("no jointly-solvable instances")
        return
    mean_d = statistics.mean(deltas)
    med_d = statistics.median(deltas)
    stdev = statistics.stdev(deltas) if n > 1 else 0.0
    se = stdev / (n ** 0.5)
    ci_lo = mean_d - 1.96 * se
    ci_hi = mean_d + 1.96 * se
    if len(paired_g) >= 10:
        stat, pval = sps.wilcoxon(paired_g, paired_c, alternative="less")
    else:
        stat, pval = None, None
    print(f"mean delta_c={mean_d:.4f}  [95% CI {ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"median delta_c={med_d:.4f}")
    print(f"WIN={n_win} TIE={n_tie} LOSS={n_loss}")
    print(f"  theorem violated (deployable worse than Chernoff): {n_loss}")
    print(f"  Wilcoxon (opt<cher, one-sided less): p={pval} stat={stat} "
          f"significant@0.05={pval is not None and pval < 0.05}")
    print(f"  per-seed (win/tie/loss): {per_seed}")
    if n_win > 0:
        print(f"  decisive win-rate on wins+losses: "
              f"{100*n_win/max(1,n_win+n_loss):.1f}%  (proxy suboptimal on "
              f"{100*n_win/max(1,n):.1f}% of all jointly-solvable)")
        # distribution of winning deltas
        wins = [d for d in deltas if d < -1e-12]
        print(f"  winning delta: min={min(wins):.3f} median={statistics.median(wins):.3f}")


if __name__ == "__main__":
    main()
