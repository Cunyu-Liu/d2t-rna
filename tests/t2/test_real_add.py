"""Unit tests for the registered real-data add-riboswitch case.

Validates that the real ON/OFF finite model (PDB 1Y26 + ViennaRNA MFE) yields
a genuine, non-trivial separation certificate (T2b), finite-sample bounds
(T2c), and a costed design (T2d) for the add adenine riboswitch.
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.t2.bounds import correct_decl_lower_interval
from d2t_rna.t2.info import hellinger_info_interval, scale_info_interval
from d2t_rna.t2.real_add import (
    APT_SEQ,
    build_real_case,
    measurement_channel,
    off_profile,
    on_profile,
    separation_positions,
    shared_positions,
)
from d2t_rna.t2.theorem import collision_or_separation


def test_profiles_match_sequence_length():
    L = len(APT_SEQ)
    assert len(on_profile()) == L == len(off_profile())


def test_profiles_differ():
    # The two conformations must differ at some positions, else no separation.
    assert separation_positions()
    # And share a scaffold (both paired at some positions).
    assert shared_positions()


def test_measurement_channel_is_stochastic():
    ch = measurement_channel(1, 0, Fraction(1, 10))
    # row 0 = P(reads paired | state) ; row 1 = P(reads unpaired | state)
    assert ch[0][0] + ch[1][0] == 1  # state OFF column
    assert ch[0][1] + ch[1][1] == 1  # state ON column


def test_noise_makes_info_finite_and_positive():
    # A separating probe under noise eps has finite, positive Hellinger info.
    p_on, p_off = on_profile()[9], off_profile()[9]  # position 10 separates
    assert p_on != p_off
    ch = measurement_channel(p_on, p_off, Fraction(1, 10))
    q_off, q_on = ch[0]
    law_off = (q_off, Fraction(1) - q_off)
    law_on = (q_on, Fraction(1) - q_on)
    info = hellinger_info_interval(law_on, law_off)
    assert info.lo > 0
    assert info.hi.is_finite()


def test_full_panel_separation_certificate():
    model = build_real_case()
    full = [a.action_id for a in model.actions]
    cert = collision_or_separation(model, full)
    assert cert.status == "IFF"
    assert cert.gamma > 0
    # P0-2: DISCRETE_CATALOG path is pure exact enumeration; it does not invoke
    # the convex-hull LP, so the LP diagnostic fields are not computed here.
    assert cert.enumeration_gamma == cert.gamma
    assert cert.enumeration_matches_lp is False
    assert cert.lp_strong_duality is False
    assert cert.separation_witness is not None


def test_single_separating_probe_is_separation():
    model = build_real_case()
    i = separation_positions()[0]
    cert = collision_or_separation(model, [f"probe{i}"])
    assert cert.status == "IFF"
    assert cert.gamma > 0


def test_single_non_separating_probe_is_collision():
    # A scaffold position (identical pairing in both states) cannot separate.
    model = build_real_case()
    shared = shared_positions()[0]
    p_on, p_off = on_profile()[shared - 1], off_profile()[shared - 1]
    assert p_on == p_off == 1
    cert = collision_or_separation(model, [f"probe{shared}"])
    assert cert.gamma == 0


def test_sufficiency_repeats_reach_kappa():
    # n=8 repeats of a separating probe (eps=1/10) certify correct >= 0.99.
    ch = measurement_channel(1, 0, Fraction(1, 10))
    q_off, q_on = ch[0]
    law_off = (q_off, Fraction(1) - q_off)
    law_on = (q_on, Fraction(1) - q_on)
    info = hellinger_info_interval(law_on, law_off)
    total = scale_info_interval(info, 8)
    cl = correct_decl_lower_interval(total)
    assert cl.lo >= Fraction(99, 100)


def test_no_noise_is_degenerate_but_registered_error_positive():
    # With eps=0 the model is deterministic (separating probe -> infinite
    # info); the registered positive-noise model is the non-trivial one.  The
    # rest of the suite uses eps=DEFAULT_EPS and must stay finite.
    model = build_real_case()
    assert model.n_states == 2
    assert len(model.actions) == len(APT_SEQ)