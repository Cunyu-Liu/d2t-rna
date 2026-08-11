"""Joint-latent-state complementary-family sweep (PRINCIPLED, not cherry-picked).

The 16-cell hand-crafted catalog is the current weakness: its cells are hand-picked
to be feasible AND to make the deployable win, so the advantage looks catalog-bound.
This script replaces that with a NATURAL GENERATIVE FAMILY where the complementary
(multi-action-required) regime is a STRUCTURAL property, not a hand-picked artifact:

  * Latent state w in {00, 01, 10, 11} (2 binary coordinates).
  * H0 = {w: coordinates EQUAL} = {00, 11}; H1 = {w: coordinates DIFFER} = {01, 10}.
  * Action A reads ONLY coordinate 1; Action B reads ONLY coordinate 2.
  * At the symmetric point each single coordinate's marginal is IDENTICAL under
    H0 and H1, so a SINGLE action is (near-)uninformative: it can NOT reach the
    endpoint alone.  A multi-action mix is therefore REQUIRED by construction.
  * Noise (eps) gives overlapping support so the Chernoff-information proxy is
    finite and enough sampling of BOTH coordinates is needed.

Because each channel has only 2 outputs, the joint product support is tiny
((a+1)(b+1)), so this family stays computationally tractable at larger budgets
-- unlike the 3-output channels where random complementary instances were no-go.

Sampling: p0 = (a, 0, 0, 1-a), p1 = (0, b, 1-b, 0) with a,b drawn near 1/2, noise
eps drawn from a set, and heterogeneous costs.  Every instance is structurally
complementary.  We compare the cost-aware greedy deployable against Chernoff's
minimum cost-to-endpoint and report win/tie/loss, mean/median relative cost
reduction, and a paired Wilcoxon test.
"""

from __future__ import annotations

import argparse
import random
import statistics
from fractions import Fraction

from scipy import stats as sps

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper

BUDGET = Fraction(16)
ENDPOINT = Fraction(1, 10)


def _coord_channel(coord: int) -> tuple:
    """2-output channel reading coordinate `coord` (0 or 1) of the 2-bit state.

    state w in {0=00, 1=01, 2=10, 3=11}; bit c1 = (w>>1)&1 ... we define:
      c1 = 0 for w in {00, 01} (index 0,1); c1 = 1 for w in {10, 11} (index 2,3)
      c2 = 0 for w in {00, 10} (index 0,2); c2 = 1 for w in {01, 11} (index 1,3)
    """
    if coord == 0:  # coordinate 1
        rows = ((1, 1, 0, 0), (0, 0, 1, 1))
    else:  # coordinate 2
        rows = ((1, 0, 1, 0), (0, 1, 0, 1))
    return O.generic_channel(rows)


def _noisy(rows, eps: Fraction) -> tuple:
    return O.noisy_channel(rows, 2, eps)


def random_instance(rng):
    """Sample a random structural-complementary instance."""
    # a,b near 1/2 (keep each single action weakly informative)
    a = Fraction(rng.choice([5, 6, 7]), 12)
    b = Fraction(rng.choice([5, 6, 7]), 12)
    p0 = (a, Fraction(0), Fraction(0), Fraction(1) - a)
    p1 = (Fraction(0), b, Fraction(1) - b, Fraction(0))
    eps = rng.choice([Fraction(1, 8), Fraction(1, 6), Fraction(1, 4)])
    chA = _noisy(_coord_channel(0), eps)
    chB = _noisy(_coord_channel(1), eps)
    # heterogeneous costs: which coordinate is cheaper is randomized
    if rng.random() < 0.5:
        channels, costs = [chA, chB], [Fraction(2), Fraction(1)]
    else:
        channels, costs = [chB, chA], [Fraction(2), Fraction(1)]
    return p0, p1, tuple(channels), costs


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


def single_action_can_reach(p0, p1, channels, costs, budget=BUDGET, endpoint=ENDPOINT):
    laws0 = tuple(O.action_law(ch, p0) for ch in channels)
    laws1 = tuple(O.action_law(ch, p1) for ch in channels)
    for u in range(len(channels)):
        alloc = [0] * len(channels)
        alloc[u] = int(budget // costs[u])
        p0v, p1v = O.multi_product_laws(laws0, laws1, tuple(alloc))
        mm = O.randomized_minimax_error_from_laws(p0v, p1v)
        if mm is not None and mm <= endpoint:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--base-seed", type=int, default=20260812)
    ap.add_argument("--budget", type=int, default=16)
    ap.add_argument("--endpoint-den", type=int, default=10)
    args = ap.parse_args()

    budget = Fraction(args.budget)
    endpoint = Fraction(1, args.endpoint_den)
    rng = random.Random(args.base_seed)
    deltas = []
    paired_g, paired_c = [], []
    n_comp = n_single = n_nogo_both = 0
    n_greedy_only = n_cher_only = 0

    for _ in range(args.n):
        p0, p1, channels, costs = random_instance(rng)
        if single_action_can_reach(p0, p1, channels, costs, budget=budget,
                                   endpoint=endpoint):
            n_single += 1
        else:
            n_comp += 1
        l0 = tuple(O.action_law(ch, p0) for ch in channels)
        l1 = tuple(O.action_law(ch, p1) for ch in channels)
        ga, gc = O.d2t_cost_to_endpoint_greedy(l0, l1, costs, budget, endpoint)
        cc, _ = chernoff_min_cte(p0, p1, list(channels), list(costs), budget=budget,
                                 endpoint=endpoint)
        if ga is not None and cc is None:
            n_greedy_only += 1
        if ga is None and cc is not None:
            n_cher_only += 1
        if ga is None or cc is None:
            n_nogo_both += 1
            continue
        delta = float((gc - cc) / cc)
        deltas.append(delta)
        paired_g.append(float(gc))
        paired_c.append(float(cc))

    n = len(deltas)
    print(f"structural-complementary family: sampled n={args.n} seed={args.base_seed} "
          f"budget={budget} endpoint={endpoint}")
    print(f"  complementary: {n_comp}  single-action-suffices: {n_single}")
    print(f"  jointly-solvable: {n}  both-no-go: {n_nogo_both}  "
          f"greedy-only-solve: {n_greedy_only}  cher-only-solve: {n_cher_only}")
    if n == 0:
        print("no jointly-solvable instances -> cannot quantify")
        return
    mean_d = statistics.mean(deltas)
    med_d = statistics.median(deltas)
    n_win = sum(1 for d in deltas if d < -1e-12)
    n_tie = sum(1 for d in deltas if abs(d) < 1e-12)
    n_loss = sum(1 for d in deltas if d > 1e-12)
    stdev = statistics.stdev(deltas) if n > 1 else 0.0
    se = stdev / (n ** 0.5)
    ci_lo = mean_d - 1.96 * se
    ci_hi = mean_d + 1.96 * se
    if len(paired_g) >= 10:
        stat, pval = sps.wilcoxon(paired_g, paired_c, alternative="less")
    else:
        stat, pval = None, None
    print(f"  mean delta_c={mean_d:.4f}  [95% CI {ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"  median delta_c={med_d:.4f}")
    print(f"  WIN={n_win} TIE={n_tie} LOSS={n_loss}")
    print(f"  Wilcoxon (greedy<cher, one-sided less): p={pval} stat={stat} "
          f"significant@0.05={pval is not None and pval < 0.05}")
    if n_win + n_loss > 0:
        print(f"  decisive win-rate={100*n_win/max(1, n_win+n_loss):.1f}%")


if __name__ == "__main__":
    main()
