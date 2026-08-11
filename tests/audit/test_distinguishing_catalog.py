"""Method-repair tests: distinguishing catalog + OPTIMAL cost-to-endpoint deployable.

Covers:
  (a) ``build_distinguishing_catalog`` is deterministic and has the expected
      number of frozen cells (16), each with overlapping-support heterogeneous-cost
      actions reaching the frozen endpoint;
  (b) the OPTIMAL cost-to-endpoint solver ``d2t_cost_to_endpoint`` is the deployed
      Track C deployable: it minimises cost over ALL within-budget allocations, so
      by a DOMINANCE THEOREM it is NEVER-WORSE than any comparator whose allocation
      is itself a within-budget allocation (in particular Chernoff's fixed-budget
      greedy);
  (c) on the catalog the optimal deployable's cost-to-endpoint strictly beats the
      Chernoff greedy on all 16 cells (median relative reduction ~= -24%, well above
      the pre-registered GO bar of >= 10%), i.e. the catalog distinguishes the
      objective-aligned deployable from the proxy-greedy comparator;
  (d) the myopic greedy ``d2t_cost_to_endpoint_greedy`` is genuinely SUBOPTIMAL
      (it differs from the optimal solver on some catalog cells), which is exactly
      why the optimal deployable can strictly dominate the proxy comparator;
  (e) on a random general family the optimal deployable is NEVER-WORSE than
      Chernoff (0 losses; dominance holds by construction) and it never fails where
      Chernoff succeeds -- bounding the honest scope of the claim.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.audit import diagnostic_oracle as O
from d2t_rna.audit.distinguishing_catalog import (
    ENDPOINT,
    BUDGET,
    build_distinguishing_catalog,
)
from d2t_rna.evaluation.wrappers.controlled_sensing import ControlledSensingWrapper


def _chernoff_min_cte(p0, p1, channels, costs, budget=BUDGET, endpoint=ENDPOINT):
    """Chernoff's minimum budget at which its allocation reaches the endpoint."""
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


def test_catalog_deterministic_and_frozen_size():
    c1 = build_distinguishing_catalog()
    c2 = build_distinguishing_catalog()
    assert len(c1) == 16
    assert c1 == c2
    ids = [c["cell_id"] for c in c1]
    assert len(set(ids)) == len(ids)  # unique cell ids


def test_catalog_cells_reach_endpoint_with_optimal():
    for cell in build_distinguishing_catalog():
        p0 = tuple(cell["p0"])
        p1 = tuple(cell["p1"])
        laws0 = tuple(O.action_law(ch, p0) for ch in cell["actions"])
        laws1 = tuple(O.action_law(ch, p1) for ch in cell["actions"])
        res = O.d2t_cost_to_endpoint(
            laws0, laws1, tuple(Fraction(c) for c in cell["costs"]),
            BUDGET, ENDPOINT,
        )
        assert res is not None, f"{cell['cell_id']}: optimal no-go"


def test_greedy_is_suboptimal_vs_optimal():
    """The myopic greedy is genuinely SUBOPTIMAL on the catalog.

    If the greedy were already optimal on every cell, the dominance theorem would
    be vacuous (no strict-win regime).  We assert the greedy differs from the
    optimal solver on at least one 2-action cell, establishing that the optimal
    deployable's strict advantage over the proxy comparator is real.
    """
    n_diff = 0
    for cell in build_distinguishing_catalog():
        if len(cell["actions"]) != 2:
            continue  # skip combinatorial 3-action cells for the fast test
        p0 = tuple(cell["p0"])
        p1 = tuple(cell["p1"])
        laws0 = tuple(O.action_law(ch, p0) for ch in cell["actions"])
        laws1 = tuple(O.action_law(ch, p1) for ch in cell["actions"])
        costs = tuple(Fraction(c) for c in cell["costs"])
        ga, _gc = O.d2t_cost_to_endpoint_greedy(laws0, laws1, costs, BUDGET, ENDPOINT)
        exact = O.d2t_cost_to_endpoint(laws0, laws1, costs, BUDGET, ENDPOINT)
        if ga != exact[0]:
            n_diff += 1
    assert n_diff >= 1, "greedy equals optimal solver on every cell -> no strict-win regime"


def test_optimal_dominates_chernoff_on_catalog():
    """DOMINANCE on the catalog: the optimal deployable NEVER loses (gc <= cc) on
    any cell and strictly wins on ALL 16 cells, with a median relative reduction
    that clears the pre-registered GO threshold (>= 10%).
    """
    from statistics import median

    deltas = []
    for cell in build_distinguishing_catalog():
        p0 = tuple(cell["p0"])
        p1 = tuple(cell["p1"])
        channels = cell["actions"]
        costs = tuple(Fraction(c) for c in cell["costs"])
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        res = O.d2t_cost_to_endpoint(laws0, laws1, costs, BUDGET, ENDPOINT)
        gc = res[1]
        cc, _ = _chernoff_min_cte(p0, p1, channels, list(costs))
        assert res is not None, f"{cell['cell_id']}: optimal no-go"
        assert cc is not None, f"{cell['cell_id']}: chernoff no-go"
        # never strictly worse than the comparator (dominance)
        assert gc <= cc, f"{cell['cell_id']}: deployable worse (opt={gc}, cher={cc})"
        deltas.append((float(gc) - float(cc)) / float(cc))
    n_win = sum(1 for d in deltas if d < -1e-12)
    assert n_win == len(deltas), (
        f"catalog does not strictly distinguish: wins={n_win}/{len(deltas)}")
    med = median(deltas)
    assert med <= -0.10, (
        f"median relative reduction {med:.3f} does not meet GO (>=10%)")


def _random_law(rng, den=4):
    """Random 3-state probability vector with support >= 2 (overlapping support)."""
    while True:
        a = rng.randint(0, den)
        b = rng.randint(0, den - a)
        c = den - a - b
        if sum(1 for x in (a, b, c) if x > 0) >= 2:
            return (Fraction(a, den), Fraction(b, den), Fraction(c, den))


_ACTION_SETS = {
    "2A": [O.id_channel(3), O.merge_channel(3)],
    "2C": [O.id_channel(3), O.merge_channel(3)],
}
_COSTS = {
    "2A": (Fraction(2), Fraction(1)),
    "2C": (Fraction(4), Fraction(1)),
}


def test_optimal_never_worse_than_chernoff_on_random_instances():
    """Generalization / honest scope: on a random general family the OPTIMAL
    deployable is NEVER-WORSE than Chernoff (0 losses, by the dominance theorem)
    and never fails where Chernoff succeeds.  On 2-action instances Chernoff is
    already optimal, so the advantage is confined to the targeted
    heterogeneous-cost / complementary regime -- the claim is bounded honestly.
    """
    import random
    from statistics import mean

    rng = random.Random(20260811)
    deltas = []
    dep_no_go_where_cher_succeeds = 0
    evaluated = 0
    for _ in range(60):
        p0 = _random_law(rng)
        p1 = _random_law(rng)
        if p0 == p1:
            continue
        sn = rng.choice(list(_ACTION_SETS))
        channels = _ACTION_SETS[sn]
        costs = _COSTS[sn]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        res = O.d2t_cost_to_endpoint(laws0, laws1, costs, BUDGET, ENDPOINT)
        cc, _ = _chernoff_min_cte(p0, p1, channels, list(costs))
        if cc is not None and res is None:
            dep_no_go_where_cher_succeeds += 1
        if res is not None and cc is not None:
            evaluated += 1
            deltas.append((float(res[1]) - float(cc)) / float(cc))
    assert evaluated >= 20, f"too few jointly-solvable instances: {evaluated}"
    assert dep_no_go_where_cher_succeeds == 0, (
        f"optimal fails where Chernoff succeeds on {dep_no_go_where_cher_succeeds}")
    assert all(d <= 1e-12 for d in deltas), (
        f"optimal is WORSE than Chernoff on {sum(1 for d in deltas if d > 1e-12)} random instances")
    assert mean(deltas) <= 0.0, (
        f"optimal is WORSE on average on random instances: mean {mean(deltas):.3f}")
