"""T2 finite model: state-space, catalogs, marginal map, action channels.

Exact rational arithmetic throughout.  A model is a finite, pre-registered
RNA observation system:

* ``n_states`` latent structural states ``w in {0,...,n_states-1}``;
* two model classes ``theta_0`` (target) and ``theta_1`` (rival), each a
  finite catalog of distributions over the states;
* a passive marginal map ``M`` (rows are linear functionals over the state
  distribution);
* a finite action library ``U``, each action a categorical observation channel
  ``Q[y][w] = q(y|w)`` (column-stochastic, entries rational in ``[0,1]``).

The cross-class difference set is ``D = { p_1 - p_0 : p_i in theta_i,
M p_0 = M p_1 }``.  The action-image of a difference ``v`` under action ``u``
is ``(B_u v)[y] = sum_w Q[y][w] v[w]``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence, TypeAlias

Vec: TypeAlias = tuple[Fraction, ...]
Matrix: TypeAlias = tuple[Vec, ...]


def _check_distribution(p: Vec, label: str) -> None:
    if not p:
        raise ValueError(f"{label} must be non-empty")
    total = Fraction(0)
    for x in p:
        if x < 0 or x > 1:
            raise ValueError(f"{label} entries must lie in [0,1]")
        total += x
    if total != 1:
        raise ValueError(
            f"{label} must sum to 1 (got {total})"
        )


@dataclass(frozen=True)
class Action:
    """One categorical observation channel ``Q[y][w]``."""

    action_id: str
    channel: Matrix  # Q[y][w]; rows are outcomes, columns are latent states

    def alphabet_size(self) -> int:
        return len(self.channel)

    def n_states(self) -> int:
        return len(self.channel[0])

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id must be non-empty")
        if not self.channel:
            raise ValueError("channel must be non-empty")
        m = len(self.channel)
        n = len(self.channel[0])
        for y, row in enumerate(self.channel):
            if len(row) != n:
                raise ValueError(
                    f"action {self.action_id!r} row {y} has wrong length"
                )
            for x in row:
                if x < 0 or x > 1:
                    raise ValueError(
                        f"action {self.action_id!r} channel entry out of [0,1]"
                    )
        for w in range(n):
            col = sum(self.channel[y][w] for y in range(m))
            if col != 1:
                raise ValueError(
                    f"action {self.action_id!r} column {w} not stochastic "
                    f"(sum={col})"
                )


@dataclass(frozen=True)
class T2FiniteModel:
    """A finite registered RNA observation model for the T2 theorem stack."""

    name: str
    n_states: int
    theta_0: tuple[Vec, ...]  # target catalog
    theta_1: tuple[Vec, ...]  # rival catalog
    marginal_map: Matrix       # rows of M
    actions: tuple[Action, ...]

    def __post_init__(self) -> None:
        if self.n_states <= 0:
            raise ValueError("n_states must be positive")
        if not self.theta_0 or not self.theta_1:
            raise ValueError("both catalogs must be non-empty")
        for i, p in enumerate(self.theta_0):
            if len(p) != self.n_states:
                raise ValueError(f"theta_0[{i}] wrong length")
            _check_distribution(p, f"theta_0[{i}]")
        for i, p in enumerate(self.theta_1):
            if len(p) != self.n_states:
                raise ValueError(f"theta_1[{i}] wrong length")
            _check_distribution(p, f"theta_1[{i}]")
        for r, row in enumerate(self.marginal_map):
            if len(row) != self.n_states:
                raise ValueError(f"marginal_map row {r} wrong length")
        for a in self.actions:
            if a.n_states() != self.n_states:
                raise ValueError(
                    f"action {a.action_id!r} has wrong state count"
                )


def marginal_apply(model: T2FiniteModel, p: Vec) -> Vec:
    """Apply the passive marginal map ``M`` to a distribution ``p``."""
    return tuple(
        sum(model.marginal_map[r][w] * p[w] for w in range(model.n_states))
        for r in range(len(model.marginal_map))
    )


def _vec_key(v: Vec) -> bytes:
    return repr(v).encode("utf-8")


def canonicalize_model(model: T2FiniteModel) -> tuple[str, str]:
    """Return ``(canonical_form, canonical_sha256)`` for a T2 finite model.

    The canonical form sorts the two catalogs and the action library by a
    stable serialization so mathematically identical models hash identically.
    """
    sorted_theta0 = tuple(
        sorted(model.theta_0, key=lambda p: _vec_key(p))
    )
    sorted_theta1 = tuple(
        sorted(model.theta_1, key=lambda p: _vec_key(p))
    )
    sorted_actions = tuple(
        sorted(model.actions, key=lambda a: (a.action_id, _vec_key(tuple(a.channel))))
    )
    canonical = {
        "name": model.name,
        "n_states": model.n_states,
        "theta_0": [[str(x) for x in p] for p in sorted_theta0],
        "theta_1": [[str(x) for x in p] for p in sorted_theta1],
        "marginal_map": [[str(x) for x in row] for row in model.marginal_map],
        "actions": [
            {
                "action_id": a.action_id,
                "channel": [[str(x) for x in row] for row in a.channel],
            }
            for a in sorted_actions
        ],
    }
    canonical_str = repr(canonical)
    digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    return canonical_str, digest