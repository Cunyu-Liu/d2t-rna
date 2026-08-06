"""Fail-closed negative control on measured data (A3).

This module is the *honesty / fail-closed* counterpart to
:mod:`d2t_rna.data.measured_add` and :mod:`d2t_rna.data.measured_glycine`.
Those two cases certify a *separation* (gamma > 0) on real measured 1M7 SHAPE
and DMS reactivity.  A reviewer can rightly ask: *does the method ever refuse
to certify?*  This module answers that question with an executed, real-data
negative control.

What it does
------------
It registers a panel drawn *only* from the measured-shared positions of the
real add riboswitch dataset (RMDB ADD71_STD_0001, Tian/Kladwang/Das, eLife
2018) --- positions whose binarized apo/bound reactivity read identical after
the registered 1% readout floor.  Because these positions carry zero measured
Hellinger information between the two classes, the T2b collision-or-separation
theorem must certify *collision* (gamma = 0, a non-trivial collision witness),
not a forced separation.  The same executable that emits the add/glycine
separation certificates therefore *honestly refuses* to emit a separation
certificate on a panel that cannot separate.

Why this is a real negative control (not a synthetic one)
----------------------------------------------------------
* The observation channels are the *measured* 1M7 SHAPE reactivities of the
  published add assay, identical to the positive case.
* The object being tested is the *certificate logic* (fail-closedness), not a
  fabricated counterexample: given a real panel with no separating signal, the
  executable must return collision rather than a fabricated gamma > 0.
* Every certificate is cross-checked by exact enumeration and LP strong duality,
  exactly as in the positive cases.

Terminal verdict
----------------
The negative control does not degrade the two positive certificates; it
confirms the framework is fail-closed (contract 8.4 / 10.2): no input condition
is force-fit into a separation it cannot support.
"""
from __future__ import annotations

from fractions import Fraction

from ..t2.model import Action, T2FiniteModel
from ..t2.theorem import T2bCertificate, collision_or_separation
from .measured_add import (
    build_measured_case,
    q_paired_apo,
    q_paired_bound,
    registered_sequence,
)

# Panel label used throughout the paper and the negative-control record.
NEGATIVE_CONTROL_ROLE = "FALSE_POSITIVE_PROBE_TAIL_HONEST_COLLISION"
NEGATIVE_CONTROL_LABEL = "measured_shared_panel_negative_control"


def strictly_non_separating_positions() -> list[int]:
    """1-based positions whose binarized apo/bound q are identical (zero info)."""
    seq = registered_sequence()
    return [
        i + 1
        for i in range(len(seq))
        if Fraction(q_paired_apo(i)) == Fraction(q_paired_bound(i))
    ]


def build_negative_control_model(shared_panel: list[int] | None = None) -> T2FiniteModel:
    """A registered model whose action panel is restricted to non-separating
    positions of the measured add assay.

    The latent states, marginal, and per-action channels are identical to the
    positive add case (``build_measured_case()``); only the *panel* is reduced
    to the measured-shared positions.  This is the natural fail-closed probe:
    the exact same executable, evaluated on a panel with no separating signal.
    """
    if shared_panel is None:
        shared_panel = strictly_non_separating_positions()
    if not shared_panel:
        raise ValueError("no strictly non-separating positions in the measured add assay")

    full = build_measured_case()
    seq = registered_sequence()
    positions = set(shared_panel)
    actions = []
    for u in range(len(seq)):
        if (u + 1) not in positions:
            continue
        # Match the positive add case's rationalization exactly
        # (measured_add.build_measured_case uses limit_denominator(100000)).
        qa = Fraction(q_paired_apo(u)).limit_denominator(100000)
        qb = Fraction(q_paired_bound(u)).limit_denominator(100000)
        channel = (
            (qa, qb),
            (Fraction(1 - q_paired_apo(u)).limit_denominator(100000),
             Fraction(1 - q_paired_bound(u)).limit_denominator(100000)),
        )
        actions.append(Action(action_id=f"probe{u + 1}", channel=channel))

    return T2FiniteModel(
        name="add_measured_shared_panel_negative_control",
        n_states=full.n_states,
        theta_0=full.theta_0,
        theta_1=full.theta_1,
        marginal_map=full.marginal_map,
        actions=tuple(actions),
    )


def certify_negative_control(
    shared_panel: list[int] | None = None,
) -> T2bCertificate:
    """Run the T2b collision-or-separation theorem on the negative-control panel.

    Expected: ``gamma == 0`` with a non-trivial ``collision_witness`` and no
    separation witness, cross-checked by enumeration and LP strong duality.
    """
    model = build_negative_control_model(shared_panel)
    panel = [a.action_id for a in model.actions]
    cert = collision_or_separation(model, panel)
    return cert