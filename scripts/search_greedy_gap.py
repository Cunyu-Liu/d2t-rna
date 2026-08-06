"""Search for a heterogeneous multi-pair microcase where the certified integer
design (T2d) strictly beats the greedy Test-Cover baseline.

The objective (item 3) asks for a "non-trivial result directly beating the
baseline": on a multi-action instance with heterogeneous pairwise information,
the optimal integer design cost must be strictly less than the greedy Test-Cover
cost.  We search small random exact-rational CostedDesign instances and report
the strongest gap found (with the optimal design and the greedy allocation).
"""
from __future__ import annotations

import random
from fractions import Fraction

from d2t_rna.t2.costed import (
    CostedDesign,
    achievable_integer_design,
    greedy_test_cover_design,
)


def _run(U: int, W: int, seed: int, max_den: int = 3) -> tuple | None:
    rng = random.Random(seed)
    # info entries in {0, 1/max_den, ..., 1}; heterogeneous coverage.
    info_lower: list[tuple[Fraction, ...]] = []
    info_upper: list[tuple[Fraction, ...]] = []
    for _ in range(U):
        row_l = []
        row_h = []
        for _w in range(W):
            v = rng.randint(0, max_den)
            row_l.append(Fraction(v, max_den))
            row_h.append(row_l[-1])  # exact rational microcase
        info_lower.append(tuple(row_l))
        info_upper.append(tuple(row_h))
    thresholds = tuple(Fraction(rng.randint(1, 3), 1) for _ in range(W))
    costs = tuple(Fraction(1) for _ in range(U))
    cd = CostedDesign(
        action_ids=tuple(f"a{u}" for u in range(U)),
        costs=costs,
        pair_ids=tuple(f"p{w}" for w in range(W)),
        thresholds=thresholds,
        info_lower=tuple(info_lower),
        info_upper=tuple(info_upper),
    )
    opt_cost, opt_n = achievable_integer_design(cd)
    gr_cost, gr_n = greedy_test_cover_design(cd)
    if opt_cost is None or gr_cost is None:
        return None
    if gr_cost > opt_cost:
        return {
            "U": U,
            "W": W,
            "seed": seed,
            "info": [[str(v) for v in row] for row in info_lower],
            "thresholds": [str(t) for t in thresholds],
            "optimal_cost": str(opt_cost),
            "optimal_n": list(opt_n),
            "greedy_cost": str(gr_cost),
            "greedy_n": list(gr_n),
            "savings": str(gr_cost - opt_cost),
        }
    return None


def main() -> int:
    best = None
    found = 0
    for U in (3, 4, 5, 6):
        for W in (2, 3, 4):
            for seed in range(4000):
                r = _run(U, W, seed)
                if r is None:
                    continue
                found += 1
                if best is None or Fraction(r["savings"]) > Fraction(best["savings"]):
                    best = r
                    print(f"[found] U={U} W={W} seed={seed} "
                          f"opt={r['optimal_cost']} greedy={r['greedy_cost']} "
                          f"savings={r['savings']}")
    print("\n=== strongest gap ===")
    import json
    print(json.dumps(best, indent=2, sort_keys=True))
    print(f"\ntotal instances with positive gap: {found}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())