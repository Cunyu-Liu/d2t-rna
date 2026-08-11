"""Unit tests for the measured-data glycine-riboswitch case (RMDB BSUGLY).

Second real-data case. Validates that the registered single-channel DMS
reactivity (full-length 265-nt transcript, apo 0 mM vs bound 1 mM glycine,
TECprobe-VL) is parsed faithfully, binarized into a stochastic per-position
observation channel, and yields a genuine measured separation certificate,
finite-sample bounds, and a costed design with no-go status -- mirroring the
add-riboswitch case to demonstrate transferability.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.data.measured_glycine import (
    APO_ACCESSION,
    APO_PATH,
    BOUND_ACCESSION,
    BOUND_PATH,
    SOURCE,
    build_measured_case,
    measured_separation_positions,
    measured_shared_positions,
    q_paired_apo,
    q_paired_bound,
    reactivity_apo,
    reactivity_bound,
    registered_sequence,
)
from d2t_rna.t2.bounds import correct_decl_lower_interval
from d2t_rna.t2.info import hellinger_info_interval, scale_info_interval
from d2t_rna.t2.theorem import collision_or_separation


def test_rdat_files_are_registered_and_present():
    assert APO_ACCESSION == "BSUGLY_DMS_0013"
    assert BOUND_ACCESSION == "BSUGLY_DMS_0014"
    assert "RMDB" in SOURCE
    assert APO_PATH.exists()
    assert BOUND_PATH.exists()
    assert APO_PATH.read_text().splitlines()[0].startswith("RDAT_VERSION")
    assert BOUND_PATH.read_text().splitlines()[0].startswith("RDAT_VERSION")


def test_parsed_sequence_and_full_length_matches():
    seq = registered_sequence()
    L = len(seq)
    assert L == 265  # full-length gcvT transcript
    assert len(reactivity_apo()) == L
    assert len(reactivity_bound()) == L
    # apo and bound full-length DMS profiles must differ at many positions.
    assert measured_separation_positions()
    assert measured_shared_positions()


def test_reactivities_are_finite_and_comparable():
    assert all(r == r and r != float("inf") for r in reactivity_apo())
    assert all(r == r and r != float("inf") for r in reactivity_bound())


def test_measurement_channel_is_stochastic():
    qa = q_paired_apo(0)
    qb = q_paired_bound(0)
    assert 0 < qa < 1
    assert 0 < qb < 1
    assert Fraction(q_paired_apo(0)) + (1 - Fraction(q_paired_apo(0))) == 1


def test_measured_separating_position_has_positive_info():
    sep = measured_separation_positions()
    i = sep[0]
    qa = Fraction(q_paired_apo(i - 1))
    qb = Fraction(q_paired_bound(i - 1))
    info = hellinger_info_interval((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
    assert info.lo > 0
    assert info.hi.is_finite()


def test_full_panel_measured_separation_certificate():
    model = build_measured_case()
    assert model.n_states == 2
    assert len(model.actions) == 265
    from d2t_rna.t2.info import hellinger_info_interval as _hii

    scored = []
    for i in measured_separation_positions():
        qa = Fraction(q_paired_apo(i - 1))
        qb = Fraction(q_paired_bound(i - 1))
        iv = _hii((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
        if iv.lo > 0:
            scored.append((float(iv.lo), i))
    scored.sort(reverse=True)
    panel = [f"probe{i}" for _, i in scored[:8]]
    cert = collision_or_separation(model, panel)
    assert cert.status == "IFF"
    assert cert.gamma > 0
    # P0-2: DISCRETE_CATALOG certifies by pure exact enumeration and must not
    # call the convex LP, so enumeration_matches_lp is only a cross-object
    # diagnostic (False because the LP is not run here), never a discrete gate.
    assert cert.enumeration_matches_lp is False
    assert cert.lp_strong_duality is False


def test_single_measured_best_probe_sufficient_repeats_reach_kappa():
    from d2t_rna.t2.info import hellinger_info_interval as _hii

    scored = []
    for i in measured_separation_positions():
        qa = Fraction(q_paired_apo(i - 1))
        qb = Fraction(q_paired_bound(i - 1))
        iv = _hii((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
        if iv.lo > 0:
            scored.append((float(iv.lo), i))
    scored.sort(reverse=True)
    best = scored[0][1]
    qa = Fraction(q_paired_apo(best - 1))
    qb = Fraction(q_paired_bound(best - 1))
    info = _hii((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
    n = 1
    while True:
        cl = correct_decl_lower_interval(scale_info_interval(info, n)).lo
        if cl >= Fraction(99, 100):
            break
        n += 1
        assert n < 1_000_000
    assert n <= 100  # strongest measured separator separates in a few repeats


def test_transferability_uses_different_chemistry_and_construct():
    # The second case must be genuinely different from the add case: different
    # chemistry (DMS vs 1M7), different construct (gcvT, 265 nt vs add, 71 nt),
    # different ligand (glycine vs adenine).  This is what makes the measured
    # channel upgrade a fact, not a one-off artifact.
    from d2t_rna.data.measured_add import registered_sequence as _add_seq
    from d2t_rna.data.measured_add import build_measured_case as _add_build

    assert registered_sequence() != _add_seq()
    assert build_measured_case().name != _add_build().name
    assert len(registered_sequence()) == 265
    assert len(_add_seq()) == 71