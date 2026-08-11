"""Method-repair tests: distinguishing catalog + cost-aware greedy deployable.

Covers:
  (a) ``build_distinguishing_catalog`` is deterministic and has the expected
      number of frozen cells (16), each with overlapping-support heterogeneous-cost
      actions reaching the frozen endpoint;
  (b) the cost-aware greedy deployable is a GENUINE NON-ORACLE: on the catalog it
      differs from the exhaustive exact cost-to-endpoint solver on at least one
      cell (i.e. it is not just the oracle relabelled), yet it is well-defined and
      non-empty;
  (c) on the catalog the greedy deployable's cost-to-endpoint NEVER exceeds the
      Chernoff fixed-budget greedy's minimum cost-to-endpoint (delta_c <= 0),
      strictly wins on a majority, and the median relative reduction clears the
      pre-registered GO threshold (>= 10%) -- i.e. the catalog distinguishes the
      objective-aligned, cost-weighted deployable;
  (d) on a random general family of instances the deployable is NEVER-WORSE than
      Chernoff on average and never fails where Chernoff succeeds, i.e. the
      advantage is not confined to the hand-crafted catalog (generalization).

The deployable uses COST-WEIGHTED marginal minimax reduction: at each myopic step
it adds a unit to the action with the greatest minimax reduction PER UNIT COST,
which avoids overspending on expensive actions that the raw-minimax greedy would
dump budget onto.
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


def test_catalog_cells_reach_endpoint_with_greedy():
    for cell in build_distinguishing_catalog():
        p0 = tuple(cell["p0"])
        p1 = tuple(cell["p1"])
        laws0 = tuple(O.action_law(ch, p0) for ch in cell["actions"])
        laws1 = tuple(O.action_law(ch, p1) for ch in cell["actions"])
        alloc, cost = O.d2t_cost_to_endpoint_greedy(
            laws0, laws1, tuple(Fraction(c) for c in cell["costs"]),
            BUDGET, ENDPOINT,
        )
        assert alloc is not None, f"{cell['cell_id']}: greedy no-go"


def test_greedy_is_genuinely_non_oracle():
    """The deployable must differ from the exhaustive exact solver on >=1 cell.

    The exact cost-to-endpoint solver enumerates every within-budget allocation,
    which is combinatorial on the 3-action (F) cells; to keep the unit test fast
    we check the 2-action cells, where the known greedy/exact divergences live
    (e.g. D1_C, D6_A, D10_C, D14_C, D16_A).
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
        ea = exact[0]
        if ga != ea:
            n_diff += 1
    assert n_diff >= 1, "greedy equals exact oracle on every cell -> not non-oracle"


def test_catalog_distinguishes_deployable_over_chernoff():
    """Cost-to-endpoint advantage on the catalog: NEVER loses (gc <= cc) on any
    cell, strictly wins on a majority, and the median relative reduction meets the
    pre-registered GO threshold (>= 10%).  The cost-weighted greedy can TIE on
    some cells (it also exploits the cheap complementary action, as Chernoff
    does), but it must never be strictly worse and must clear the GO bar.
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
        ga, gc = O.d2t_cost_to_endpoint_greedy(laws0, laws1, costs, BUDGET, ENDPOINT)
        cc, _ = _chernoff_min_cte(p0, p1, channels, list(costs))
        assert ga is not None, f"{cell['cell_id']}: greedy no-go"
        assert cc is not None, f"{cell['cell_id']}: chernoff no-go"
        # never strictly worse than the comparator
        assert gc <= cc, f"{cell['cell_id']}: deployable worse (greedy={gc}, cher={cc})"
        deltas.append((float(gc) - float(cc)) / float(cc))
    n_win = sum(1 for d in deltas if d < 0)
    assert n_win > len(deltas) / 2, (
        f"catalog does not distinguish: wins={n_win}/{len(deltas)}")
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
    "3F": [O.id_channel(3), O.pair_channel(3), O.merge_channel(3)],
}
_COSTS = {
    "2A": (Fraction(2), Fraction(1)),
    "2C": (Fraction(4), Fraction(1)),
    "3F": (Fraction(2), Fraction(1), Fraction(1)),
}


def test_deployable_never_worse_than_chernoff_on_random_instances():
    """Generalization: on a random family the cost-weighted deployable is
    never-worse on average (mean delta_c <= 0) and never fails where Chernoff
    succeeds (no deployable-only no-go).  This shows the advantage is not an
    artifact confined to the hand-crafted catalog.
    """
    import random
    from statistics import mean

    rng = random.Random(20260811)
    deltas = []
    dep_no_go_where_cher_succeeds = 0
    evaluated = 0
    for _ in range(300):
        p0 = _random_law(rng)
        p1 = _random_law(rng)
        if p0 == p1:
            continue
        sn = rng.choice(list(_ACTION_SETS))
        channels = _ACTION_SETS[sn]
        costs = _COSTS[sn]
        laws0 = tuple(O.action_law(ch, p0) for ch in channels)
        laws1 = tuple(O.action_law(ch, p1) for ch in channels)
        ga, gc = O.d2t_cost_to_endpoint_greedy(laws0, laws1, costs, BUDGET, ENDPOINT)
        cc, _ = _chernoff_min_cte(p0, p1, channels, list(costs))
        if cc is not None and ga is None:
            dep_no_go_where_cher_succeeds += 1
        if ga is not None and cc is not None:
            evaluated += 1
            deltas.append((float(gc) - float(cc)) / float(cc))
    assert evaluated >= 100, f"too few jointly-solvable instances: {evaluated}"
    assert dep_no_go_where_cher_succeeds == 0, (
        f"deployable fails where Chernoff succeeds on {dep_no_go_where_cher_succeeds}")
    assert mean(deltas) <= 0.0, (
        f"deployable is WORSE on average on random instances: mean {mean(deltas):.3f}")
