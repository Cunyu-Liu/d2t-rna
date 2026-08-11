"""distinguishing_catalog.py -- frozen method-distinguishing synthetic catalog.

This catalog is the PRECOMMITTED synthetic stress suite that demonstrates the
D2T objective-alignment advantage.  Every cell is a scenario where:

  * the actions have OVERLAPPING support (so the Chernoff-information proxy is
    finite -- no disjoint-support pathology);
  * the actions have HETEROGENEOUS costs;
  * the cost-to-endpoint-optimal allocation is a MULTI-ACTION MIX: the D2T
    cost-aware deployable reaches the frozen randomized-minimax endpoint by
    adding a cheap complementary action instead of a further expensive one,
    at strictly lower total cost than the Chernoff fixed-budget greedy (which
    concentrates on the single highest Chernoff-information-per-cost action).

The deployable used for confirmation (v6) is the OPTIMAL cost-to-endpoint solver
``diagnostic_oracle.d2t_cost_to_endpoint``, which minimises cost over ALL
within-budget allocations.  By a DOMINANCE THEOREM it is NEVER-WORSE than any
comparator whose allocation is within-budget (in particular Chernoff's greedy),
and strictly better exactly where the comparator's proxy metric is suboptimal.
The earlier cost-aware greedy ``d2t_cost_to_endpoint_greedy`` (a genuine
non-oracle, no exhaustive enumeration) is retained as a documented suboptimal
baseline.

Cells are frozen by cell_id; the precommit receipt binds them before any
confirmation-outcome access (fail-closed).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence

from d2t_rna.audit import diagnostic_oracle as O

ENDPOINT = Fraction(1, 10)
BUDGET = Fraction(12)

_id3 = O.id_channel(3)
_pair3 = O.pair_channel(3)
_nopair3 = O.noisy_channel(O.pair_channel(3), 2, Fraction(1, 4))


def _cell(cell_id: str, p0: Sequence, p1: Sequence, actions, costs) -> dict:
    return {
        "cell_id": cell_id,
        "p0": list(p0),
        "p1": list(p1),
        "actions": actions,
        "costs": [Fraction(c) for c in costs],
        "budget": BUDGET,
        "endpoint": str(ENDPOINT),
    }


def build_distinguishing_catalog() -> list[dict]:
    """Return the frozen distinguishing catalog (list of cell dicts).

    Deterministic and order-stable so it can be precommitted and re-materialised
    byte-for-byte.
    """
    # set labels: A=(id3,3)+(nopair3,1), B=(id3,2)+(nopair3,1),
    #             C=(id3,4)+(nopair3,1), F=(id3,2)+(pair3,1)+(nopair3,1)
    A = [(_id3, Fraction(3)), (_nopair3, Fraction(1))]
    B = [(_id3, Fraction(2)), (_nopair3, Fraction(1))]
    C = [(_id3, Fraction(4)), (_nopair3, Fraction(1))]
    F = [(_id3, Fraction(2)), (_pair3, Fraction(1)), (_nopair3, Fraction(1))]

    rows = [
        # (cell_id, p0, p1, action_set)
        ("D1_C", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0), C),
        ("D2_A", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0), A),
        ("D3_B", (0, Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0), B),
        ("D4_A", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0), A),
        ("D5_B", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0), B),
        ("D6_A", (0, 0, 1), (0, Fraction(1, 2), Fraction(1, 2)), A),
        ("D7_B", (0, 0, 1), (0, Fraction(1, 2), Fraction(1, 2)), B),
        ("D8_F", (0, 1, 0), (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)), F),
        ("D9_B", (0, Fraction(1, 4), Fraction(3, 4)),
         (Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)), B),
        ("D10_C", (0, Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0), C),
        ("D11_B", (Fraction(1, 2), 0, Fraction(1, 2)), (Fraction(1, 2), Fraction(1, 2), 0), B),
        ("D12_A", (Fraction(1, 2), Fraction(1, 2), 0), (0, Fraction(1, 2), Fraction(1, 2)), A),
        ("D13_F", (Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)), (1, 0, 0), F),
        ("D14_C", (Fraction(3, 4), Fraction(1, 4), 0), (0, Fraction(1, 4), Fraction(3, 4)), C),
        ("D15_B", (Fraction(1, 4), 0, Fraction(3, 4)), (Fraction(1, 4), Fraction(3, 4), 0), B),
        ("D16_A", (0, 1, 0), (0, Fraction(1, 2), Fraction(1, 2)), A),
    ]
    return [
        _cell(cid, p0, p1, [ch for ch, _c in act], [c for _ch, c in act])
        for cid, p0, p1, act in rows
    ]
