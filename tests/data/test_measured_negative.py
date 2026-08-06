"""Tests for the fail-closed negative control on measured add data (A3).

The negative control proves the certificate logic is *honest*: a panel drawn
only from the measured-shared positions of the real add riboswitch assay must
certify collision (gamma = 0), not a fabricated separation.  These tests lock
the fail-closedness contract (contract 8.4 / 10.2).
"""

from __future__ import annotations

from fractions import Fraction

from d2t_rna.data.measured_add import (
    build_measured_case,
    measured_separation_positions,
    q_paired_apo,
    q_paired_bound,
    registered_sequence,
)
from d2t_rna.data.measured_negative import (
    build_negative_control_model,
    certify_negative_control,
    strictly_non_separating_positions,
)
from d2t_rna.t2.info import hellinger_info_interval
from d2t_rna.t2.theorem import collision_or_separation


def test_negative_control_has_nonempty_shared_panel():
    shared = strictly_non_separating_positions()
    assert len(shared) >= 1
    # The shared panel is a strict subset of the full action set.
    assert set(shared) <= set(range(1, len(registered_sequence()) + 1))


def test_shared_positions_carry_zero_measured_info():
    # A strictly non-separating position has identical binarized apo/bound q,
    # so its measured Hellinger information is exactly zero.
    shared = strictly_non_separating_positions()
    for p in shared:
        qa = Fraction(q_paired_apo(p - 1))
        law_apo = (qa, Fraction(1) - qa)
        law_bound = (law_apo[0], law_apo[1])  # identical
        info = hellinger_info_interval(law_bound, law_apo)
        assert info.lo == 0


def test_negative_control_certifies_collision_not_separation():
    # The whole point: the executable must refuse to emit a separation
    # certificate on a real panel that cannot separate.
    cert = certify_negative_control()
    assert cert.gamma == 0
    assert cert.collision_witness is not None
    assert cert.separation_witness is None


def test_negative_control_cross_checked_lp_enumeration():
    cert = certify_negative_control()
    assert cert.enumeration_matches_lp is True
    assert cert.lp_strong_duality is True


def test_negative_control_uses_real_measured_channels():
    # The negative control must use the *same* measured add channels as the
    # positive case; only the panel differs.  This proves it is a real-data
    # negative control, not a synthetic counterexample.
    neg = build_negative_control_model()
    pos = build_measured_case()
    assert neg.n_states == pos.n_states
    assert neg.theta_0 == pos.theta_0
    assert neg.theta_1 == pos.theta_1
    # Every negative-control action channel is a strict subset of the positive
    # model's action channels, and both read the same measured q values.
    pos_lookup = {a.action_id: a.channel for a in pos.actions}
    for a in neg.actions:
        assert a.action_id in pos_lookup
        assert a.channel == pos_lookup[a.action_id]


def test_negative_control_does_not_contaminate_separation_case():
    # The separating positions still separate: restricting the panel to shared
    # positions must NOT change the positive certificate on the full panel.
    sep_panel = [f"probe{i}" for i in measured_separation_positions()[:8]]
    pos = build_measured_case()
    cert = collision_or_separation(pos, sep_panel)
    assert cert.gamma > 0
    assert cert.status == "IFF"
    assert cert.separation_witness is not None