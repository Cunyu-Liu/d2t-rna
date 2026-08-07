"""Measured-data case engine: add adenine riboswitch ON/OFF from registered 1M7 SHAPE.

This upgrades the ``add`` observation channel from a *model-conditional* pairing
status + synthetic noise coupling (see :mod:`d2t_rna.t2.real_add`) to a
*measured* observation channel read directly off published nucleotide-resolution
SHAPE reactivity.

Dataset (registered, CC0, RMDB accession ADD71_STD_0001)
  * paper:    Tian S, Kladwang W, Das R. "Allosteric mechanism of the V.
               vulnificus adenine riboswitch resolved by four-dimensional
               chemical mapping." eLife (2018) 7:e29602.
  * doi:      10.7554/eLife.29602      PMID: 29446752
  * construct: add riboswitch residues 13-83, V. vulnificus (71 nt).
  * reagent:   1M7 (SHAPE); normalized so reactive loop residues have mean
               reactivity 1.0.
  * two conformations used here:
      REACTIVITY:1  apo  (no ligand)
      REACTIVITY:2  bound (5 mM adenine)
  * per-position reactivity AND per-position measurement standard error
    (REACTIVITY_ERROR:1 / :2) are parsed but NOT used in the clamp likelihood (P0-5).

Observation channel (binarized measured reactivity)
  For each probed position ``u`` and conformation ``s`` the readout is binary
  ``{paired/protected, unpaired/reactive}``.  The probability of reading
  *unpaired/reactive* is the measured normalized reactivity ``r[s,u]``
  (relative modification propensity), clamped to a registered measurement
  floor ``1/100``:

      p_reactive(s,u) = max(1/100, min(99/100, r[s,u]))

  so the probability of reading *paired* is ``q(s,u) = 1 - p_reactive(s,u)``.
  The ``1/100`` floor encodes the repeats/resolution of the measurement (the
  reported SEs show class call is not sub-1% precise); it keeps the Hellinger
  information per separating position *finite*, so the finite-sample bound is
  genuine (non-trivial) rather than a degenerate ``n=1`` certainty.

  Position ``u`` is *measured-separating* iff ``q(apo,u) != q(bound,u)``, i.e.
  iff the measured apo and bound reactivities differ after the floor.  The
  separation coefficient for a single probe is ``gamma = 2|q(bound)-q(apo)|``.

Registration mirrors contract 8.5 (role REGISTERED_OBSERVATION_MODEL):
  * states            2 conformations: OFF (apo), ON (5 mM adenine)
  * theta_0 (target)  e_OFF = (1,0)
  * theta_1 (rival)   e_ON  = (0,1)
  * passive marginal  M = (1,1)  total law; M theta_0 = M theta_1 = 1 (collision)
  * actions           one per measured position with the measured channel above.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from ..t2.model import Action, T2FiniteModel

# --- provenance -----------------------------------------------------------
ACCESSION = "ADD71_STD_0001"
DOI = "10.7554/eLife.29602"
PMID = "29446752"
RDAT_PATH = Path(__file__).parent / "raw" / "ADD71_STD_0001.rdat"

# 1M7 (SHAPE) channels in the RDAT: 1 = apo, 2 = 5 mM adenine (bound).
APO_CHANNEL = 1
BOUND_CHANNEL = 2

# Registered measurement-resolution floor on the binarized readout
# probability (see module docstring).
READOUT_FLOOR = 1 / 100


def _parse_rdat(path: Path) -> dict:
    seq = ""
    reactivity: dict[int, list[float]] = {}
    error: dict[int, list[float]] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        key, val = parts[0], parts[1]
        if key == "SEQUENCE":
            seq = val.strip().upper()
        elif key.startswith("REACTIVITY_ERROR:"):
            ch = int(key.split(":")[1])
            error[ch] = [float(x) for x in val.split()]
        elif key.startswith("REACTIVITY:"):
            ch = int(key.split(":")[1])
            reactivity[ch] = [float(x) for x in val.split()]
    if not seq:
        raise ValueError(f"RDAT {path} missing SEQUENCE")
    L = len(seq)
    for ch in (APO_CHANNEL, BOUND_CHANNEL):
        if ch not in reactivity or len(reactivity[ch]) != L:
            raise ValueError(
                f"RDAT {path} channel {ch} length mismatch (expected {L})"
            )
    return {
        "sequence": seq,
        "reactivity": reactivity,
        "error": error,
    }


_DATA: dict | None = None


def _data() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = _parse_rdat(RDAT_PATH)
    return _DATA


def registered_sequence() -> str:
    """The 71-nt measured construct (add riboswitch residues 13-83)."""
    return _data()["sequence"]


def reactivity_apo() -> list[float]:
    return list(_data()["reactivity"][APO_CHANNEL])


def reactivity_bound() -> list[float]:
    return list(_data()["reactivity"][BOUND_CHANNEL])


def error_apo() -> list[float]:
    return list(_data()["error"][APO_CHANNEL])


def error_bound() -> list[float]:
    return list(_data()["error"][BOUND_CHANNEL])


def _p_reactive(r: float) -> float:
    """Measured reactivity -> probability of reading *unpaired/reactive*."""
    return max(READOUT_FLOOR, min(1 - READOUT_FLOOR, r))


def q_paired_apo(u: int) -> float:
    """P(reads paired | apo) at 0-based position ``u``."""
    return 1 - _p_reactive(reactivity_apo()[u])


def q_paired_bound(u: int) -> float:
    """P(reads paired | bound) at 0-based position ``u``."""
    return 1 - _p_reactive(reactivity_bound()[u])


def measured_separation_positions() -> list[int]:
    """1-based positions where measured apo/bound reactivity differ (after floor)."""
    return [
        i + 1
        for i in range(len(registered_sequence()))
        if q_paired_apo(i) != q_paired_bound(i)
    ]


def measured_shared_positions() -> list[int]:
    """1-based positions that read paired in BOTH conformations (low reactivity)."""
    return [
        i + 1
        for i in range(len(registered_sequence()))
        if q_paired_apo(i) > 0.5 and q_paired_bound(i) > 0.5
    ]


def build_measured_case() -> T2FiniteModel:
    """Build the registered add ON/OFF model using the measured 1M7 channels."""
    seq = registered_sequence()
    L = len(seq)
    q_off = [q_paired_apo(i) for i in range(L)]
    q_on = [q_paired_bound(i) for i in range(L)]

    theta_0 = ((Fraction(1), Fraction(0)),)
    theta_1 = ((Fraction(0), Fraction(1)),)
    marginal_map = ((Fraction(1), Fraction(1)),)

    actions = []
    for u in range(L):
        channel = (
            (Fraction(q_off[u]).limit_denominator(100000), Fraction(q_on[u]).limit_denominator(100000)),
            (Fraction(1 - q_off[u]).limit_denominator(100000), Fraction(1 - q_on[u]).limit_denominator(100000)),
        )
        actions.append(Action(action_id=f"probe{u+1}", channel=channel))

    return T2FiniteModel(
        name="add_riboswitch_on_off_measured_1M7",
        n_states=2,
        theta_0=theta_0,
        theta_1=theta_1,
        marginal_map=marginal_map,
        actions=tuple(actions),
    )