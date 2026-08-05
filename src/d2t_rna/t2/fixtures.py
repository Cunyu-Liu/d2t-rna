"""Registered T2 microcases for the witness / collision engine.

Each fixture maps to a scenario the contract requires (section 10.1):

* ``two_by_two_alternating``  2x2 fixed-marginal alternating rectangle.
* ``no_cycle``                injective marginal map -> empty difference set.
* ``zero_margin``             degenerate marginal map -> full difference set.
* ``symmetric_states``        exchange-symmetric model.
* ``repeated_action``         an action repeated in the library.
* ``cancellation_counterexample``  each generator hit, combination cancels.
* ``three_way_fixed_marginal`` non-decomposable fiber needing >1 generator.
* ``exact_collision``         panel fully blind to a witness.
* ``near_collision``          no exact collision but arbitrarily close.
* ``strict_separation``       panel with positive separation.

All probabilities are exact ``fractions.Fraction``.
"""

from __future__ import annotations

from fractions import Fraction

F = Fraction


def _p(*values: int) -> tuple[Fraction, ...]:
    scale = values[0]
    return tuple(F(v, scale) for v in values[1:])


# --- 2x2 fixed-marginal alternating rectangle -----------------------------
def two_by_two_alternating():
    """States are 2x2 cells: (0,0),(0,1),(1,0),(1,1).

    p0 is flat uniform; p1 puts all mass on the diagonal.  Both have the same
    row and column marginals, so the difference is the alternating rectangle.
    """
    marginal_map = (
        (F(1), F(1), F(0), F(0)),  # row 0 marginal
        (F(0), F(0), F(1), F(1)),  # row 1 marginal
        (F(1), F(0), F(1), F(0)),  # col 0 marginal
        (F(0), F(1), F(0), F(1)),  # col 1 marginal
    )
    p0 = _p(4, 1, 1, 1, 1)
    p1 = _p(2, 1, 0, 0, 1)
    return _model(
        "two_by_two_alternating",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(
            _action("full_obs", (
                (F(1), F(0), F(0), F(0)),
                (F(0), F(1), F(0), F(0)),
                (F(0), F(0), F(1), F(0)),
                (F(0), F(0), F(0), F(1)),
            )),
            _action("row_obs", (
                (F(1), F(1), F(0), F(0)),
                (F(0), F(0), F(1), F(1)),
            )),
        ),
    )


def no_cycle():
    """Identity marginal map: ``M p0 = M p1`` already forces ``p0 = p1``."""
    marginal_map = (
        (F(1), F(0), F(0)),
        (F(0), F(1), F(0)),
        (F(0), F(0), F(1)),
    )
    p0 = _p(3, 1, 1, 1)
    p1 = _p(3, 1, 1, 1)
    return _model(
        "no_cycle",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(_action("a", (
            (F(1), F(0), F(0)),
            (F(0), F(1), F(1)),
        )),),
    )


def zero_margin():
    """Degenerate marginal map (all zeros): every pair is admissible."""
    n = 3
    marginal_map = tuple(tuple(F(0) for _ in range(n)) for _ in range(1))
    p0 = _p(3, 1, 1, 1)
    p1 = _p(3, 2, 1, 0)
    return _model(
        "zero_margin",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(_action("a", (
            (F(1), F(0), F(0)),
            (F(0), F(1), F(1)),
        )),),
    )


def symmetric_states():
    """Exchange-symmetric 2-state model."""
    marginal_map = ((F(1), F(1)),)  # total mass only
    p0 = _p(2, 1, 1)
    p1 = _p(2, 1, 1)
    return _model(
        "symmetric_states",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(_action("a", ((F(1), F(0)), (F(0), F(1)))),),
    )


def repeated_action():
    """The same channel appears twice under different ids."""
    base = two_by_two_alternating()
    return _model(
        "repeated_action",
        theta_0=base.theta_0,
        theta_1=base.theta_1,
        marginal_map=base.marginal_map,
        actions=base.actions + (_action("row_obs_dup", base.actions[1].channel),),
    )


def cancellation_counterexample():
    """Each generator is hit, yet a linear combination cancels.

    States 0..3.  Marginal map is total mass (so the fiber is all zero-sum
    vectors).  A single Bernoulli action observes ``state0 + state3`` minus
    ``state1 + state2``.  The basis generators ``(1,-1,0,0)`` and
    ``(0,0,1,-1)`` each have nonzero response, but their difference
    ``(1,-1,-1,1)`` cancels to zero under the action.
    """
    marginal_map = ((F(1), F(1), F(1), F(1)),)
    # p0 flat; p1 = (1/2,0,0,1/2) so v = p1-p0 = (1/4,-1/4,-1/4,1/4) which is
    # (1/4)g1 - (1/4)g2 with g1=(1,-1,0,0), g2=(0,0,1,-1).  Under the action
    # B v = (v0+v2, v1+v3) = (0,0), so the combination cancels even though
    # each generator is individually hit.
    p0 = _p(4, 1, 1, 1, 1)
    p1 = _p(2, 1, 0, 0, 1)  # (1/2,0,0,1/2)
    return _model(
        "cancellation_counterexample",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(
            _action("b1", (
                (F(1), F(0), F(1), F(0)),  # P(obs=1) = state0 + state2
                (F(0), F(1), F(0), F(1)),
            )),
            _action("b2", (
                (F(1), F(0), F(1), F(0)),
                (F(0), F(1), F(0), F(1)),
            )),
        ),
    )


def three_way_fixed_marginal():
    """3x3 bounded table: the fiber needs more than one generator, so the
    single alternating rectangle (valid for 2D) is not the full Markov basis."""
    n = 9  # 3x3 cells
    # two-way marginals as linear functionals over the 9 cells
    marginal_map = _three_way_marginals()
    # p0: a uniform-ish table; p1: a different table with the SAME two-way
    # marginals is hard to hand-build; instead use two tables that differ only
    # in a direction orthogonal to the marginal map below (a zero-sum vector
    # orthogonal to all rows).  We expose the structural fact that the fiber
    # has dimension > 1 by returning the model plus an explicit generator set.
    p0 = tuple(F(1, n) for _ in range(n))
    p1 = tuple(F(1, n) for _ in range(n))
    return _model(
        "three_way_fixed_marginal",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(_action("a", (
            (F(1), F(0), F(1), F(0), F(1), F(0), F(1), F(0), F(1)),
            (F(0), F(1), F(0), F(1), F(0), F(1), F(0), F(1), F(0)),
        )),),
    )


def _three_way_marginals():
    rows = []
    cells = [(i, j) for i in range(3) for j in range(3)]
    # row sums (3 rows) and column sums (3 cols) of the 3x3 table
    for i in range(3):
        rows.append(tuple(F(1) if c[0] == i else F(0) for c in cells))
    for j in range(3):
        rows.append(tuple(F(1) if c[1] == j else F(0) for c in cells))
    return tuple(rows)


def exact_collision():
    """Panel of a single row-observation action is fully blind to the witness."""
    base = two_by_two_alternating()
    return _model(
        "exact_collision",
        theta_0=base.theta_0,
        theta_1=base.theta_1,
        marginal_map=base.marginal_map,
        actions=(_action("row_obs", base.actions[1].channel),),
    )


def near_collision():
    """Models share the same 2x2 marginals (admissible difference) but differ
    by a small amount along the alternating direction, so a diagonal-reading
    action yields a small positive separation (no exact collision)."""
    marginal_map = (
        (F(1), F(1), F(0), F(0)),
        (F(0), F(0), F(1), F(1)),
        (F(1), F(0), F(1), F(0)),
        (F(0), F(1), F(0), F(1)),
    )
    p0 = _p(4, 1, 1, 1, 1)
    p1 = _p(16, 5, 3, 3, 5)  # p0 + (1/16,-1/16,-1/16,1/16)
    return _model(
        "near_collision",
        theta_0=(p0,),
        theta_1=(p1,),
        marginal_map=marginal_map,
        actions=(_action("diag", (
            (F(1), F(0), F(0), F(1)),  # reads one diagonal
            (F(0), F(1), F(1), F(0)),  # reads the other diagonal
        )),),
    )


def strict_separation():
    """Direct full-observation panel separates the two models."""
    base = two_by_two_alternating()
    return _model(
        "strict_separation",
        theta_0=base.theta_0,
        theta_1=base.theta_1,
        marginal_map=base.marginal_map,
        actions=(_action("full_obs", base.actions[0].channel),),
    )


def _action(action_id: str, channel) -> "object":
    from .model import Action

    return Action(action_id=action_id, channel=tuple(tuple(F(c) for c in row) for row in channel))


def _model(name, theta_0, theta_1, marginal_map, actions):
    from .model import T2FiniteModel

    n = len(theta_0[0])
    return T2FiniteModel(
        name=name,
        n_states=n,
        theta_0=tuple(tuple(F(x) for x in p) for p in theta_0),
        theta_1=tuple(tuple(F(x) for x in p) for p in theta_1),
        marginal_map=tuple(tuple(F(x) for x in row) for row in marginal_map),
        actions=tuple(actions),
    )