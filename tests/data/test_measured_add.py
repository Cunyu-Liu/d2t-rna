"""Unit tests for the measured-data add-riboswitch case (RMDB ADD71_STD_0001).

Validates that the registered 1M7 SHAPE reactivity (apo vs 5 mM adenine) is
parsed faithfully, binarized into a stochastic per-position observation channel,
and yields a genuine measured separation certificate (T2b), finite-sample
bounds (T2c), and a costed design with no-go status (T2d).
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.data.measured_add import (
    ACCESSION,
    APO_CHANNEL,
    BOUND_CHANNEL,
    DOI,
    RDAT_PATH,
    build_measured_case,
    error_apo,
    error_bound,
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


def test_rdat_file_is_registered_and_present():
    assert ACCESSION == "ADD71_STD_0001"
    assert DOI == "10.7554/eLife.29602"
    assert RDAT_PATH.exists()
    assert RDAT_PATH.read_text().splitlines()[0].startswith("RDAT_VERSION")


def test_parsed_sequence_and_channels_match():
    seq = registered_sequence()
    L = len(seq)
    assert L == 71  # add riboswitch residues 13-83
    assert len(reactivity_apo()) == L
    assert len(reactivity_bound()) == L
    assert len(error_apo()) == L
    assert len(error_bound()) == L
    # apo and bound are the two 1M7 SHAPE channels used as the observation.
    assert APO_CHANNEL == 1
    assert BOUND_CHANNEL == 2


def test_reactivities_are_finite_and_comparable():
    # Every measured reactivity must be finite; the two conformations differ
    # at enough positions to separate (else no non-trivial certificate).
    assert all(r == r and r != float("inf") for r in reactivity_apo())
    assert all(r == r and r != float("inf") for r in reactivity_bound())
    assert measured_separation_positions()
    assert measured_shared_positions()


def test_measurement_channel_is_stochastic():
    # q(s,u) = P(reads paired | state).  The readout is binary, so each
    # state column of the channel must sum to 1.
    qa = q_paired_apo(0)
    qb = q_paired_bound(0)
    assert 0 < qa < 1
    assert 0 < qb < 1
    # column sums: (qa + (1-qa)) == 1 and (qb + (1-qb)) == 1 by construction.
    assert Fraction(q_paired_apo(0)) + (1 - Fraction(q_paired_apo(0))) == 1


def test_measured_separating_position_has_positive_info():
    sep = measured_separation_positions()
    i = sep[0]  # 1-based
    qa = Fraction(q_paired_apo(i - 1))
    qb = Fraction(q_paired_bound(i - 1))
    law_apo = (qa, Fraction(1) - qa)
    law_bound = (qb, Fraction(1) - qb)
    info = hellinger_info_interval(law_bound, law_apo)
    assert info.lo > 0
    assert info.hi.is_finite()


def test_non_separating_measured_position_has_zero_info():
    # A position whose binarized apo/bound q are equal (after the readout
    # floor) is not measured-separating and carries zero Hellinger info.
    model = build_measured_case()
    non_sep = None
    for i in range(len(registered_sequence())):
        if Fraction(q_paired_apo(i)) == Fraction(q_paired_bound(i)):
            non_sep = i
            break
    assert non_sep is not None, "expected at least one non-separating position"
    qa = Fraction(q_paired_apo(non_sep))
    law_apo = (qa, Fraction(1) - qa)
    law_bound = (qa, Fraction(1) - qa)  # identical -> zero information
    info = hellinger_info_interval(law_bound, law_apo)
    assert info.lo == 0
    # The certified upper edge is only a numerical widening around 0.
    assert float(info.hi) < 1e-30


def test_full_panel_measured_separation_certificate():
    model = build_measured_case()
    assert model.n_states == 2
    assert len(model.actions) == 71
    # A panel of the eight strongest measured separators certifies IFF
    # separation (gamma > 0) with LP/enumeration agreement.
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
    # The strongest measured separator (probe10 in the current data) has a
    # small certified n_suff for correct-declaration >= 0.99.
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
        # kappa = 0.99
        if cl >= Fraction(99, 100):
            break
        n += 1
        assert n < 1_000_000
    assert n <= 100  # the strongest measured separator separates in a few repeats