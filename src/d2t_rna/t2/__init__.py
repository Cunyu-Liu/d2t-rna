"""T2 witness / collision engine for the D2T-RNA v7 theoretical methods contract.

This package implements the T2-1 deliverable: finite-model canonicalization,
cross-class difference set enumeration, action-image computation, robust
action-image separation gamma(S), exact collision witnesses, cancellation
counterexample search, and an independent verifier.

All arithmetic is exact (``fractions.Fraction``).  This engine produces
model-conditional synthetic certificates only; it cannot authorize any formal
scientific claim (``scientific_claim_authorized=false``).
"""

from .model import Action, T2FiniteModel, canonicalize_model
from .witness import (
    collision_witness,
    iter_differences,
    norm_l1,
    panel_separation,
    separate_by_generators,
    SingleActionResidual,
)
from .verify import verify_collision, verify_separation

__all__ = [
    "Action",
    "T2FiniteModel",
    "canonicalize_model",
    "collision_witness",
    "iter_differences",
    "norm_l1",
    "panel_separation",
    "separate_by_generators",
    "SingleActionResidual",
    "verify_collision",
    "verify_separation",
]