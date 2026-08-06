"""Measured-data case engine: B. subtilis gcvT glycine riboswitch ON/OFF from DMS.

This is the *second* real-data case, demonstrating that the measured
observation-channel upgrade is transferable (not an add-riboswitch artifact).
It mirrors :mod:`d2t_rna.data.measured_add` but reads a *different* chemistry
(DMS rather than 1M7 SHAPE), a *different* ligand (glycine rather than
adenine), and a *different* organism/construct (Bacillus subtilis gcvT
glycine riboswitch, co-transcriptionally folded).

Dataset (registered, RMDB accessions BSUGLY_DMS_0013 / BSUGLY_DMS_0014)
  * experiment: TECprobe-VL of the B. subtilis gcvT glycine riboswitch
    *delta P0* variant, co-transcriptionally folded, DMS reactivity.
  * accessions:  BSUGLY_DMS_0013  apo  (0 mM glycine)
                 BSUGLY_DMS_0014  bound (1 mM glycine)
  * reagent:     DMS (methylates solvent-exposed A/C); analyzed with
                 ShapeMapper2 (Busan & Weeks, RNA 2017, Doi:10.1261/rna.061945.117)
                 and normalized per Low & Weeks (Methods 2010,
                 Doi:10.1016/j.ymeth.2010.06.007).
  * construct:   265-nt full-length transcript (last DATA block, Length265).
  * two conditions used here:
      DATA block of the apo  RDAT  (0 mM)   -> OFF
      DATA block of the bound RDAT (1 mM)   -> ON

Observation channel (binarized measured DMS reactivity)
  For each probed position ``u`` and condition ``s`` the readout is binary
  ``{paired/protected, unpaired/reactive}``.  DMS modifies unpaired A/C, so
  higher normalized reactivity reads as *unpaired/reactive*.  The probability
  of reading *unpaired/reactive* is the measured normalized reactivity
  ``r[s,u]`` clamped to the registered measurement floor ``1/100``:

      p_reactive(s,u) = max(1/100, min(99/100, r[s,u]))

  Position ``u`` is *measured-separating* iff ``q(apo,u) != q(bound,u)``.

Registration mirrors contract 8.5 (role REGISTERED_OBSERVATION_MODEL),
identical to the add case: two conformations, theta_0 = e_OFF, theta_1 = e_ON,
passive marginal M = (1,1) (collision), one action per measured position.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from ..t2.model import Action, T2FiniteModel

# --- provenance -----------------------------------------------------------
APO_ACCESSION = "BSUGLY_DMS_0013"
BOUND_ACCESSION = "BSUGLY_DMS_0014"
# Primary source: RMDB (Stanford RNA Mapping Database / RNA Mapping Center).
# The underlying TECprobe-VL dataset is deposited by the Weeks lab (UNC).
SOURCE = "RMDB (BSUGLY_DMS_0013 / BSUGLY_DMS_0014); TECprobe-VL, Weeks lab"
APO_PATH = Path(__file__).parent / "raw" / "BSUGLY_DMS_0013.rdat"
BOUND_PATH = Path(__file__).parent / "raw" / "BSUGLY_DMS_0014.rdat"

# DMS modifies unpaired A/C: higher normalized reactivity => more unpaired.
READOUT_FLOOR = 1 / 100


def _parse_full_length_reactivity(path: Path) -> list[float]:
    """Return the reactivity profile of the *last* DATA block (full transcript)."""
    data_blocks: dict[int, list[float]] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("DATA:"):
            idx = int(line.split()[0].split(":")[1])
            vals = [float(x) for x in line.split()[1:]]
            data_blocks[idx] = vals
    if not data_blocks:
        raise ValueError(f"RDAT {path} has no DATA blocks")
    last = max(data_blocks)
    return data_blocks[last]


def _sequence(path: Path) -> str:
    for line in path.read_text().splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0] == "SEQUENCE":
            return parts[1].strip().upper()
    raise ValueError(f"RDAT {path} missing SEQUENCE")


_DATA: dict | None = None


def _data() -> dict:
    global _DATA
    if _DATA is None:
        seq = _sequence(APO_PATH)
        apo = _parse_full_length_reactivity(APO_PATH)
        bound = _parse_full_length_reactivity(BOUND_PATH)
        if len(apo) != len(bound):
            raise ValueError("apo/bound reactivity length mismatch")
        if len(apo) != len(seq):
            raise ValueError("reactivity/sequence length mismatch")
        _DATA = {"sequence": seq, "reactivity_apo": apo, "reactivity_bound": bound}
    return _DATA


def registered_sequence() -> str:
    return _data()["sequence"]


def reactivity_apo() -> list[float]:
    return list(_data()["reactivity_apo"])


def reactivity_bound() -> list[float]:
    return list(_data()["reactivity_bound"])


def _p_reactive(r: float) -> float:
    """Measured DMS reactivity -> probability of reading *unpaired/reactive*."""
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
    """1-based positions that read paired in BOTH conditions (low reactivity)."""
    return [
        i + 1
        for i in range(len(registered_sequence()))
        if q_paired_apo(i) > 0.5 and q_paired_bound(i) > 0.5
    ]


def build_measured_case() -> T2FiniteModel:
    """Build the registered glycine ON/OFF model using measured DMS channels."""
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
        name="gcvT_glycine_riboswitch_on_off_measured_DMS",
        n_states=2,
        theta_0=theta_0,
        theta_1=theta_1,
        marginal_map=marginal_map,
        actions=tuple(actions),
    )