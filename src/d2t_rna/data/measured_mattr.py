"""Measured-data case engine: miniTTR metal-ion conformational switch (Mg2+).

This is the *third* real-data case, breaking transferability concerns in two
directions at once:
  * it is a *designed* RNA (a miniTTR computational-design construct), NOT a
    natural riboswitch, so the registered channel is not riboswitch-specific;
  * it is a *metal-ion* (Mg2+) dependent conformational switch, NOT a
    ligand-induced ON/OFF riboswitch, so the discriminator is not ligand
    binding.

It mirrors :mod:`d2t_rna.data.measured_add` and
:mod:`d2t_rna.data.measured_glycine` (same registered two-state model shape,
same binarized measured-reactivity observation channel, same 1% readout
floor) but reads *two Mg2+ concentrations of a single construct* from one
RDAT file.

Dataset (registered, CC0, RMDB accession MTTR1_MGTI_0001)
  * paper:    Yesselman JD, Eiler D, Carlson ED, Gotrik MR, d'Aquino AE,
               Ooms AN, Kladwang W, Carlson PD, Shi X, Costantino DA,
               Herschlag D, Lucks JB, Jewett MC, Kieft JS, Das R.
               "Computational design of three-dimensional RNA structure and
               function." Nature Nanotechnology (2019).
  * doi:      10.1038/s41565-019-0517-8      PMID: 31427748
  * construct: miniTTR c1, a small designed RNA (81 nt).
  * reagent:   DMS reactivity measured as a function of MgCl2 concentration
               (32-point Mg2+ titration, 0 mM .. 50 mM).
  * two conditions used here:
      ANNOTATION_DATA:1   MgCl2 0 mM     (metal-ion depleted / unfolded)
      ANNOTATION_DATA:32  MgCl2 50 mM    (metal-ion saturated / folded)
  * per-position reactivity AND per-position measurement standard error
    (REACTIVITY_ERROR:1 / :32) are both parsed and used.

Observation channel (binarized measured reactivity)
  Identical to the add/glycine cases.  For each probed position ``u`` and
  condition ``s`` the readout is binary ``{paired/protected, unpaired/reactive}``.
  The probability of reading *unpaired/reactive* is the measured normalized
  reactivity ``r[s,u]`` clamped to the registered measurement floor ``1/100``:

      p_reactive(s,u) = max(1/100, min(99/100, r[s,u]))

  so ``q(s,u) = 1 - p_reactive(s,u)`` is the probability of reading *paired*.
  The ``1/100`` floor keeps the Hellinger information per separating position
  *finite*, so the finite-sample bound is genuine (non-trivial).

Registration mirrors contract 8.5 (role REGISTERED_OBSERVATION_MODEL):
  * states            2 conformations: LOW (0 mM Mg2+), HIGH (50 mM Mg2+)
  * theta_0 (target)  e_LOW  = (1,0)
  * theta_1 (rival)   e_HIGH = (0,1)
  * passive marginal  M = (1,1)  total law; M theta_0 = M theta_1 = 1 (collision)
  * actions           one per measured position with the measured channel above.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from ..t2.model import Action, T2FiniteModel

# --- provenance -----------------------------------------------------------
ACCESSION = "MTTR1_MGTI_0001"
DOI = "10.1038/s41565-019-0517-8"
PMID = "31427748"
RDAT_PATH = Path(__file__).parent / "raw" / "MTTR1_MGTI_0001.rdat"

# MgCl2 channels in the RDAT: 1 = 0 mM (depleted), 32 = 50 mM (saturated).
LOW_CHANNEL = 1
HIGH_CHANNEL = 32

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
    for ch in (LOW_CHANNEL, HIGH_CHANNEL):
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
    """The 81-nt designed miniTTR c1 construct."""
    return _data()["sequence"]


def reactivity_low() -> list[float]:
    """Measured DMS reactivity at 0 mM MgCl2 (metal-ion depleted)."""
    return list(_data()["reactivity"][LOW_CHANNEL])


def reactivity_high() -> list[float]:
    """Measured DMS reactivity at 50 mM MgCl2 (metal-ion saturated)."""
    return list(_data()["reactivity"][HIGH_CHANNEL])


def error_low() -> list[float]:
    return list(_data()["error"][LOW_CHANNEL])


def error_high() -> list[float]:
    return list(_data()["error"][HIGH_CHANNEL])


def _p_reactive(r: float) -> float:
    """Measured reactivity -> probability of reading *unpaired/reactive*."""
    return max(READOUT_FLOOR, min(1 - READOUT_FLOOR, r))


def q_paired_low(u: int) -> float:
    """P(reads paired | 0 mM Mg2+) at 0-based position ``u``."""
    return 1 - _p_reactive(reactivity_low()[u])


def q_paired_high(u: int) -> float:
    """P(reads paired | 50 mM Mg2+) at 0-based position ``u``."""
    return 1 - _p_reactive(reactivity_high()[u])


def measured_separation_positions() -> list[int]:
    """1-based positions where measured 0mM/50mM reactivity differ (after floor)."""
    return [
        i + 1
        for i in range(len(registered_sequence()))
        if q_paired_low(i) != q_paired_high(i)
    ]


def measured_shared_positions() -> list[int]:
    """1-based positions that read paired in BOTH conditions (low reactivity)."""
    return [
        i + 1
        for i in range(len(registered_sequence()))
        if q_paired_low(i) > 0.5 and q_paired_high(i) > 0.5
    ]


def build_measured_case() -> T2FiniteModel:
    """Build the registered miniTTR LOW/HIGH model using measured DMS channels."""
    seq = registered_sequence()
    L = len(seq)
    q_lo = [q_paired_low(i) for i in range(L)]
    q_hi = [q_paired_high(i) for i in range(L)]

    theta_0 = ((Fraction(1), Fraction(0)),)
    theta_1 = ((Fraction(0), Fraction(1)),)
    marginal_map = ((Fraction(1), Fraction(1)),)

    actions = []
    for u in range(L):
        channel = (
            (Fraction(q_lo[u]).limit_denominator(100000), Fraction(q_hi[u]).limit_denominator(100000)),
            (Fraction(1 - q_lo[u]).limit_denominator(100000), Fraction(1 - q_hi[u]).limit_denominator(100000)),
        )
        actions.append(Action(action_id=f"probe{u+1}", channel=channel))

    return T2FiniteModel(
        name="miniTTR_metal_ion_switch_low_high_measured_DMS",
        n_states=2,
        theta_0=theta_0,
        theta_1=theta_1,
        marginal_map=marginal_map,
        actions=tuple(actions),
    )