"""Real-data case engine: add adenine riboswitch ON/OFF discrimination.

This registers the add (adenine) riboswitch as a finite RNA state/action/
observation contract and emits a real separation certificate + finite-sample
bound.  It converts the previously fail-closed ``add`` case
(ADD_ROLE = COUNTERFACTUAL_RETROSPECTIVE_FULL_MATRIX_COMPRESSION,
NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL) into a *registered* case by
providing a legitimate binary classification observation channel (paired /
unpaired, i.e. binarized SHAPE/DMS chemical mapping).

Registration (contract 8.5, role REGISTERED_OBSERVATION_MODEL):
  * states            2 conformations: OFF (apo), ON (adenine-bound)
  * theta_0 (target)  e_OFF = (1,0)   -- the apo/low-ligand ensemble
  * theta_1 (rival)   e_ON  = (0,1)   -- the bound ensemble
  * passive marginal  M = (1,1)  total observation law; M theta_0 = M theta_1
                       so the passive (no-action) observation cannot separate
                       the two classes (genuine collision fiber).
  * actions           one per probed position u: binary channel
                       Q_u = [[q_on_u, q_off_u],[1-q_on_u, 1-q_off_u]]
                       where q_*_u is the *(noisy)* probability that position
                       u reads as paired (protected) in that conformation.

Measurement-noise coupling (registered nuisance coupling C).
  The bare pairing statuses are *deterministic* (a nucleotide is either
  base-paired or not in a given structure).  A deterministic readout would
  give ``BC = 0`` and thereby *infinite* Hellinger information per separating
  position, i.e. a trivially-perfect, non-finite-sample certificate.  Real
  SHAPE/DMS chemical mapping has a non-zero per-position readout error: a
  protected (paired) position occasionally reads as reactive and vice versa.
  We therefore register a symmetric bit-flip observation coupling with error
  rate ``eps in (0, 1/2)``:

      P(observe paired   | truly paired)   = 1 - eps
      P(observe paired   | truly unpaired) = eps

  This is the nuisance coupling ``C`` of the framework (contract 5.3).  It is
  a *registered modelling assumption*, not measured reactivity; ``eps`` is
  swept in the runner so the certificate's dependence on the noise level is
  explicit and auditable.  Because ``eps`` is strictly positive, the
  Bhattacharyya coefficient is non-zero and the Hellinger information per
  separating position is positive but *finite*, so the finite-sample bound is
  genuine (non-trivial), not a degenerate ``n=1`` certainty.

Observation probability separation
  gamma(S) = min_{v in D} max_{u in S} ||B_u v||_1,
  with a single difference vector v = theta_1 - theta_0 = (-1,1) admissible
  because M v = 0.  For a single separating probe u, ||B_u v||_1 = 2|1-2*eps|,
  so gamma(S) = 2|1-2*eps| * [S contains a separating position].
"""
from __future__ import annotations

from fractions import Fraction

from .model import Action, T2FiniteModel

# --- real structures -----------------------------------------------------
# add adenine riboswitch aptamer, 71 nt (PDB 1Y26, residues 13..83).
APT_SEQ = "CGCUUCAUAUAAUCCUAAUGAUAUGGUUUGGGAGUUUCUACCAAGAGCCUUAAACUCUUGAUUAUGAAGUG"

# OFF (apo) structure: ViennaRNA MFE of the real aptamer.
OFF_DOT = "(((((((((...((((((.........))))))........((((((.......))))))..)))))))))"
# ON (adenine-bound) structure: base pairs read from PDB 1Y26 (see real-add
# case provenance).  Dot-bracket with '1'=paired.
ON_PROFILE = "11111111111.1111111.111.11111111111.1111111111111..111111111..111111111"

# Default registered measurement-noise coupling (see module docstring).
DEFAULT_EPS = Fraction(1, 10)


def _dot_to_profile(dot: str) -> tuple[int, ...]:
    return tuple(1 if c in "()" else 0 for c in dot)


def off_profile() -> tuple[int, ...]:
    return _dot_to_profile(OFF_DOT)


def on_profile() -> tuple[int, ...]:
    return tuple(1 if c == "1" else 0 for c in ON_PROFILE)


def measurement_channel(p_on: int, p_off: int, eps: Fraction):
    """Binary noisy readout channel for a position.

    Returns ``(Q_paired, Q_unpaired)`` where ``Q_paired = (q_off, q_on)`` and
    ``Q_unpaired = (1-q_off, 1-q_on)``; column index is the state (0 = OFF,
    1 = ON).  ``q_off``/``q_on`` are the probabilities of reading *paired*
    given that the position is truly paired in OFF/ON respectively.
    """
    q_off = Fraction(1) - eps if p_off == 1 else eps
    q_on = Fraction(1) - eps if p_on == 1 else eps
    return (
        (Fraction(q_off), Fraction(q_on)),
        (Fraction(1) - q_off, Fraction(1) - q_on),
    )


def build_real_case(eps: Fraction = DEFAULT_EPS) -> T2FiniteModel:
    """Build the registered add ON/OFF finite model with readout noise ``eps``."""
    p_off = off_profile()
    p_on = on_profile()
    L = len(APT_SEQ)
    assert len(p_off) == L and len(p_on) == L, "profile length mismatch"

    # theta_0 = target = OFF concentrated; theta_1 = rival = ON concentrated.
    theta_0 = ((Fraction(1), Fraction(0)),)
    theta_1 = ((Fraction(0), Fraction(1)),)
    # passive marginal = total law (1,1); M theta_0 = M theta_1 = 1 -> collision.
    marginal_map = ((Fraction(1), Fraction(1)),)

    actions = []
    for u in range(L):
        channel = measurement_channel(p_on[u], p_off[u], eps)
        actions.append(Action(action_id=f"probe{u+1}", channel=channel))

    return T2FiniteModel(
        name="add_riboswitch_on_off",
        n_states=2,
        theta_0=theta_0,
        theta_1=theta_1,
        marginal_map=marginal_map,
        actions=tuple(actions),
    )


def separation_positions() -> list[int]:
    """1-based positions where ON and OFF bare pairing status differs."""
    return [
        i + 1
        for i, (a, b) in enumerate(zip(off_profile(), on_profile()))
        if a != b
    ]


def shared_positions() -> list[int]:
    """1-based positions paired in BOTH conformations (scaffold)."""
    return [
        i + 1
        for i, (a, b) in enumerate(zip(off_profile(), on_profile()))
        if a == 1 and b == 1
    ]