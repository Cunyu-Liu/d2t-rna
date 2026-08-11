"""Method-repair tests: distinguishing catalog + cost-aware greedy deployable.

Covers:
  (a) ``build_distinguishing_catalog`` is deterministic and has the expected
      number of frozen cells (16), each with overlapping-support heterogeneous-cost
      actions reaching the frozen endpoint;
  (b) the cost-aware greedy deployable is a GENUINE NON-ORACLE: on the catalog it
      differs from the exhaustive exact cost-to-endpoint solver on at least one
      cell (i.e. it is not just the oracle relabelled), yet it is well-defined and
      non-empty;
  (c) on every catalog cell the greedy deployable's cost-to-endpoint is a STRICT
      improvement over the Chernoff fixed-budget greedy's minimum cost-to-endpoint
      (delta_c < 0), i.e. the catalog distinguishes the objective-aligned deployable.
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
    """Strict cost-to-endpoint win (delta_c < 0) on every catalog cell."""
    wins = 0
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
        assert gc < cc, f"{cell['cell_id']}: not a strict win (greedy={gc}, cher={cc})"
        wins += 1
    assert wins == len(build_distinguishing_catalog())
