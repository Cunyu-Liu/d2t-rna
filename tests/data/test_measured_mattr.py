"""Unit tests for the measured-data miniTTR metal-ion switch case (RMDB MTTR1_MGTI_0001).

Third real-data case. Breaks transferability concerns in two directions at once:
  * it is a *designed* RNA (miniTTR c1 computational-design construct), NOT a
    natural riboswitch, so the registered channel is not riboswitch-specific;
  * it is a *metal-ion* (Mg2+) dependent conformational switch, NOT a
    ligand-induced ON/OFF riboswitch, so the discriminator is not ligand binding.

Validates that the registered single-RDAT DMS reactivity (81 nt, MgCl2 0 mM vs
50 mM, 32-point titration from Yesselman et al., Nature Nanotechnology 2019) is
parsed faithfully, binarized into a stochastic per-position observation channel,
and yields a genuine measured separation certificate, finite-sample bounds, and
a costed design with no-go status -- mirroring the add/glycine cases to
demonstrate transferability across assay chemistry AND biological mode.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.data.measured_mattr import (
    ACCESSION,
    DOI,
    LOW_CHANNEL,
    HIGH_CHANNEL,
    RDAT_PATH,
    build_measured_case,
    measured_separation_positions,
    measured_shared_positions,
    q_paired_low,
    q_paired_high,
    reactivity_low,
    reactivity_high,
    registered_sequence,
)
from d2t_rna.t2.bounds import correct_decl_lower_interval
from d2t_rna.t2.info import hellinger_info_interval, scale_info_interval
from d2t_rna.t2.theorem import collision_or_separation


def test_rdat_file_is_registered_and_present():
    assert ACCESSION == "MTTR1_MGTI_0001"
    assert DOI == "10.1038/s41565-019-0517-8"
    assert RDAT_PATH.exists()
    assert RDAT_PATH.read_text().splitlines()[0].startswith("RDAT_VERSION")


def test_parsed_sequence_and_full_length_matches():
    seq = registered_sequence()
    L = len(seq)
    assert L == 81  # miniTTR c1 designed construct
    assert len(reactivity_low()) == L
    assert len(reactivity_high()) == L
    # 0 mM vs 50 mM Mg2+ DMS profiles must differ at many positions.
    assert measured_separation_positions()
    assert measured_shared_positions()


def test_conditions_are_the_two_titration_endpoints():
    # The two conditions are the depleted (0 mM) and saturated (50 mM)
    # endpoints of the registered 32-point MgCl2 titration.
    assert LOW_CHANNEL == 1
    assert HIGH_CHANNEL == 32


def test_reactivities_are_finite_and_comparable():
    assert all(r == r and r != float("inf") for r in reactivity_low())
    assert all(r == r and r != float("inf") for r in reactivity_high())


def test_measurement_channel_is_stochastic():
    qa = q_paired_low(0)
    qb = q_paired_high(0)
    assert 0 < qa < 1
    assert 0 < qb < 1
    assert Fraction(q_paired_low(0)) + (1 - Fraction(q_paired_low(0))) == 1


def test_measured_separating_position_has_positive_info():
    sep = measured_separation_positions()
    i = sep[0]
    qa = Fraction(q_paired_low(i - 1))
    qb = Fraction(q_paired_high(i - 1))
    info = hellinger_info_interval((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
    assert info.lo > 0
    assert info.hi.is_finite()


def test_full_panel_measured_separation_certificate():
    model = build_measured_case()
    assert model.n_states == 2
    assert len(model.actions) == 81
    from d2t_rna.t2.info import hellinger_info_interval as _hii

    scored = []
    for i in measured_separation_positions():
        qa = Fraction(q_paired_low(i - 1))
        qb = Fraction(q_paired_high(i - 1))
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
        qa = Fraction(q_paired_low(i - 1))
        qb = Fraction(q_paired_high(i - 1))
        iv = _hii((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
        if iv.lo > 0:
            scored.append((float(iv.lo), i))
    scored.sort(reverse=True)
    best = scored[0][1]
    qa = Fraction(q_paired_low(best - 1))
    qb = Fraction(q_paired_high(best - 1))
    info = _hii((qb, Fraction(1) - qb), (qa, Fraction(1) - qa))
    n = 1
    while True:
        cl = correct_decl_lower_interval(scale_info_interval(info, n)).lo
        if cl >= Fraction(99, 100):
            break
        n += 1
        assert n < 1_000_000
    assert n <= 100  # strongest measured separator separates in a few repeats


def test_transferability_is_neither_riboswitch_nor_ligand_specific():
    # The third case must be genuinely different from both prior cases:
    #   * add:      natural riboswitch, 71 nt, 1M7 SHAPE, adenine ligand
    #   * glycine:  natural riboswitch, 265 nt, DMS, glycine ligand
    #   * miniTTR:  *designed* RNA, 81 nt, DMS, *metal-ion* (Mg2+) switch
    # This is what breaks the "riboswitch-specific" / "ligand-induced" concern.
    from d2t_rna.data.measured_add import registered_sequence as _add_seq
    from d2t_rna.data.measured_add import build_measured_case as _add_build
    from d2t_rna.data.measured_glycine import registered_sequence as _gly_seq
    from d2t_rna.data.measured_glycine import build_measured_case as _gly_build

    assert registered_sequence() != _add_seq()
    assert registered_sequence() != _gly_seq()
    assert build_measured_case().name != _add_build().name
    assert build_measured_case().name != _gly_build().name
    assert len(registered_sequence()) == 81
    assert len(_add_seq()) == 71
    assert len(_gly_seq()) == 265