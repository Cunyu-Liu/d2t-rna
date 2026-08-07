"""Typed T2 semantic spec (P0-3 hard gate).

The audit (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``) found that the
project's central certificate object drifted across four layers (contract,
paper, code, checker): the discrete catalog and the convex-hull relaxation were
silently mixed, and the action-level L1 separation was mislabelled as a
product-law total-variation (which must lie in ``[0,1]``).

This module provides the single, immutable, hash-bound ``TheoremSpec`` that
explicitly declares the two axes that were previously ambiguous:

* ``uncertainty_kind`` -- ``DISCRETE_CATALOG`` (optimize over the finite
  catalogs) or ``CONVEX_HULL`` (optimize over their convex hulls).  These two
  problems are *not* equivalent in general (T2b convexification counterexample).
* ``separation_measure`` -- ``ACTION_L1`` (the raw ``max_u ||B_u v||_1`` the
  engine computes) or ``ACTION_TV`` (the same separation expressed as a
  total-variation distance, equal to ``L1 / 2`` for a zero-sum difference).

A certificate is only a formal certificate when the declared
``uncertainty_kind`` matches the engine actually used *and* any reported value
is expressed in the declared measure.  Wall-clock reuse of the same name
``gamma`` across these objects is exactly the drift the audit flags.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction

UNCERTAINTY_DISCRETE = "DISCRETE_CATALOG"
UNCERTAINTY_CONVEX = "CONVEX_HULL"

MEASURE_ACTION_L1 = "ACTION_L1"
MEASURE_ACTION_TV = "ACTION_TV"
MEASURE_PRODUCT_TV = "PRODUCT_TV"

_UNCERTAINTY_KINDS = frozenset({UNCERTAINTY_DISCRETE, UNCERTAINTY_CONVEX})
_MEASURES = frozenset(
    {MEASURE_ACTION_L1, MEASURE_ACTION_TV, MEASURE_PRODUCT_TV}
)


@dataclass(frozen=True)
class TheoremSpec:
    """Immutable declaration of the object a T2 certificate is about."""

    uncertainty_kind: str = UNCERTAINTY_DISCRETE
    separation_measure: str = MEASURE_ACTION_L1

    def __post_init__(self) -> None:
        if self.uncertainty_kind not in _UNCERTAINTY_KINDS:
            raise ValueError(
                f"unknown uncertainty_kind {self.uncertainty_kind!r}; "
                f"expected one of {sorted(_UNCERTAINTY_KINDS)}"
            )
        if self.separation_measure not in _MEASURES:
            raise ValueError(
                f"unknown separation_measure {self.separation_measure!r}; "
                f"expected one of {sorted(_MEASURES)}"
            )

    def canonical(self) -> str:
        """Deterministic canonical serialization (hash-bound identity)."""
        return repr(
            {
                "uncertainty_kind": self.uncertainty_kind,
                "separation_measure": self.separation_measure,
            }
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


def tv_from_l1(l1: Fraction) -> Fraction:
    """Total-variation of a zero-sum difference equals ``L1 / 2``.

    For ``v = p_1 - p_0`` with ``p_0, p_1`` distributions, the action-image
    ``B_u v`` is zero-sum, so its L1 norm is ``2 * TV``.  Normalising here
    guarantees any value reported as ``ACTION_TV``/``PRODUCT_TV`` lies in
    ``[0, 1]`` (the audit's TV-range hard gate).
    """
    if l1 < 0:
        raise ValueError("L1 separation cannot be negative")
    return l1 / 2