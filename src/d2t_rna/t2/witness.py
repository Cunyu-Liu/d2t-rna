"""T2 witness / collision engine: difference set, action-image, separation.

Core objects (contract section 3.1):

* Cross-class difference set
  ``D = { p_1 - p_0 : p_i in theta_i, M p_0 = M p_1 }``.
* Action-image of ``v`` under ``u``: ``(B_u v)[y] = sum_w Q_u[y][w] v[w]``.
* Robust action-image separation ``gamma(S) = inf_{v in D} max_{u in S} ||B_u v||``.
* Exact collision witness: nonzero ``v in D`` with ``B_u v = 0`` for all ``u in S``.

A key contract warning (3.1) is that ``gamma(S)`` must be optimized over the
full ``D``, not over a hand-listed set of cycle generators: a difference that
is a linear combination of generators can cancel under every selected action
even when each generator is individually hit.  ``separate_by_generators``
exposes exactly that failure mode for testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator, Sequence, TypeAlias

from .model import Action, T2FiniteModel, marginal_apply

Vec: TypeAlias = tuple[Fraction, ...]


def _zero_vec(n: int) -> Vec:
    return tuple(Fraction(0) for _ in range(n))


def _is_zero(v: Vec) -> bool:
    return all(x == 0 for x in v)


def norm_l1(v: Vec) -> Fraction:
    """L1 norm (sum of absolute values).  For a zero-sum vector this equals
    2 x total-variation distance of the two distributions it separates."""
    return sum((abs(x) for x in v), Fraction(0))


def iter_differences(model: T2FiniteModel) -> Iterator[tuple[Vec, Vec, Vec]]:
    """Yield ``(p_0, p_1, v=p_1-p_0)`` for every admissible cross-class pair.

    Admissibility means ``M p_0 == M p_1``.  Zero differences are skipped.
    """
    seen: set[bytes] = set()
    for p0 in model.theta_0:
        m0 = marginal_apply(model, p0)
        for p1 in model.theta_1:
            if marginal_apply(model, p1) != m0:
                continue
            v = tuple(p1[w] - p0[w] for w in range(model.n_states))
            if _is_zero(v):
                continue
            key = repr(v).encode("utf-8")
            if key in seen:
                continue
            seen.add(key)
            yield p0, p1, v


def action_image(action: Action, v: Vec) -> Vec:
    """Compute ``B_u v``, the observation-law difference vector for ``v``."""
    m = action.alphabet_size()
    return tuple(
        sum(action.channel[y][w] * v[w] for w in range(len(v)))
        for y in range(m)
    )


@dataclass(frozen=True)
class SeparationResult:
    gamma: Fraction | None  # None <=> no admissible cross-class difference
    witness_v: Vec
    witness_p0: Vec
    witness_p1: Vec
    panel: tuple[str, ...]


def panel_separation(
    model: T2FiniteModel, panel: Sequence[str]
) -> SeparationResult:
    """Return ``gamma(S) = inf_{v in D} max_{u in S} ||B_u v||_1``.

    The norm is L1; for action-image vectors that are zero-sum this equals
    ``2 x TV`` of the resulting observation laws.  The result is exact and
    carries the attaining witness ``v = p_1 - p_0``.  When the difference set
    ``D`` is empty (no admissible cross-class pair), ``gamma`` is ``None``.
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    if len(selected) != len(set(panel)):
        raise ValueError("panel refers to an unknown or duplicate action")
    best: SeparationResult | None = None
    for p0, p1, v in iter_differences(model):
        worst = max(norm_l1(action_image(u, v)) for u in selected)
        if best is None or worst < best.gamma:
            best = SeparationResult(
                gamma=worst,
                witness_v=v,
                witness_p0=p0,
                witness_p1=p1,
                panel=tuple(panel),
            )
    if best is None:
        # no admissible difference: separation is vacuous (empty D)
        return SeparationResult(
            gamma=None, witness_v=_zero_vec(model.n_states),
            witness_p0=model.theta_0[0], witness_p1=model.theta_1[0],
            panel=tuple(panel),
        )
    return best


def collision_witness(
    model: T2FiniteModel, panel: Sequence[str]
) -> Vec | None:
    """Return a nonzero ``v in D`` with ``B_u v = 0`` for all ``u in S``.

    Returns ``None`` when no such collision exists (strict separation).
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    for _p0, _p1, v in iter_differences(model):
        if all(_is_zero(action_image(u, v)) for u in selected):
            return v
    return None


def _rref_basis(constraint_rows: list[Vec]) -> list[Vec]:
    """Return a vector basis of the nullspace of the exact matrix spanned by
    ``constraint_rows`` (rational row-reduced echelon kernel computation)."""
    from fractions import Fraction as F

    if not constraint_rows:
        return []
    n = len(constraint_rows[0])
    rows = [list(r) for r in constraint_rows]
    pivot_cols: list[int] = []
    r = 0
    for c in range(n):
        # find a pivot
        piv = None
        for i in range(r, len(rows)):
            if rows[i][c] != 0:
                piv = i
                break
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        pivot = rows[r][c]
        rows[r] = [x / pivot for x in rows[r]]
        for i in range(len(rows)):
            if i != r and rows[i][c] != 0:
                factor = rows[i][c]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[r])]
        pivot_cols.append(c)
        r += 1
        if r == len(rows):
            break
    pivot_set = set(pivot_cols)
    free_cols = [c for c in range(n) if c not in pivot_set]
    basis: list[Vec] = []
    for free in free_cols:
        vec = [F(0)] * n
        vec[free] = F(1)
        for idx, pc in enumerate(pivot_cols):
            vec[pc] = -rows[idx][free]
        basis.append(tuple(vec))
    return basis


def fiber_basis(model: T2FiniteModel) -> list[Vec]:
    """A basis of the difference directions admissible under the marginal map.

    These are the vectors spanning the fiber of equal marginals (the
    ``alternating`` directions).  For a 2D fixed-marginal model this is a
    single alternating rectangle; for larger state spaces it can be larger,
    which is where cancellation counterexamples live.
    """
    constraints: list[Vec] = []
    # marginal rows must be preserved: M v = 0
    for row in model.marginal_map:
        constraints.append(row)
    # distributions impose zero total mass: sum v = 0
    constraints.append(tuple(Fraction(1) for _ in range(model.n_states)))
    basis = _rref_basis(constraints)
    return [vec for vec in basis if not _is_zero(vec)]


@dataclass(frozen=True)
class SingleActionResidual:
    action_id: str
    residual: Fraction


def separate_by_generators(
    model: T2FiniteModel, panel: Sequence[str]
) -> tuple[list[SingleActionResidual], ...] | None:
    """Generator-level hit audit.

    For each basis generator ``g`` of the fiber, record the residual of its
    action-image under every panel action.  This exposes the contract warning:
    inspecting only per-generator hits is *not* sufficient to conclude
    separation, because a combination can cancel.  Returns per-generator
    residual lists, or ``None`` if there are no basis generators.
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    basis = fiber_basis(model)
    if not basis:
        return None
    out: list[tuple[SingleActionResidual, ...]] = []
    for g in basis:
        residuals = tuple(
            SingleActionResidual(
                action_id=u.action_id,
                residual=norm_l1(action_image(u, g)),
            )
            for u in selected
        )
        out.append(residuals)
    return out