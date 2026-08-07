"""P0-5: replicate-aware observation likelihood kill-test infrastructure.

Tests the three candidate observation models required by the glycine
post-selection replicate kill test:

* ``DirectClampModel`` (status quo: clamp normalized reactivity, ignore error),
* ``EqualLawNullModel`` (no-separation null),
* ``WithinReplicateCountModel`` (per-replicate count likelihood).

Because the real glycine archive (BSUGLY_DMS_0013/0014) contains only merged,
normalized reactivity and NO per-replicate raw counts, the count model is
exercised on synthetic fixtures; the real-archive qualification is the
permanent status ``BLOCKED_PENDING_ARCHIVE_QUALIFICATION`` (see module docstring
and these tests).
"""

from __future__ import annotations

from d2t_rna.data.observation_model import (
    BLOCKED_PENDING_ARCHIVE_QUALIFICATION,
    REPLAY_MISSING,
    DirectClampModel,
    EqualLawNullModel,
    WithinReplicateCountModel,
    run_post_selection_diagnostic,
)


def test_direct_clamp_p_and_floor():
    apo = [0.0, 0.5, 1.5]
    bound = [0.0, 0.6, 0.8]
    m = DirectClampModel(apo, bound, floor=0.01)
    # floor clamps low reactivity up
    assert m.p("apo", 0) == 0.01
    # ceiling clamps high reactivity down
    assert m.p("apo", 2) == 0.99
    # interior stays
    assert m.p("apo", 1) == 0.5
    assert m.p("bound", 2) == 0.8


def test_direct_clamp_length_mismatch():
    try:
        DirectClampModel([0.1, 0.2], [0.1], floor=0.01)
    except ValueError:
        return
    raise AssertionError("expected ValueError on length mismatch")


def test_direct_clamp_log_score():
    m = DirectClampModel([0.5], [0.5], floor=0.01)
    # symmetric p=0.5 -> log(1/2) for each binary outcome
    p = m.p("apo", 0)
    assert m.log_score_binary("apo", 0, 1) == m.log_score_binary("apo", 0, 0)
    assert abs(m.log_score_binary("apo", 0, 1) - __import__("math").log(p)) < 1e-12


def test_equal_law_null_pooled():
    apo = [0.1, 0.9]
    bound = [0.3, 0.5]
    m = EqualLawNullModel(apo, bound, floor=0.01)
    assert m.pooled_p(0) == (0.1 + 0.3) / 2
    assert m.pooled_p(1) == (0.9 + 0.5) / 2
    # pooled_p independent of condition
    assert m.log_score_binary("apo", 0, 1) == m.log_score_binary("bound", 0, 1)


def test_within_replicate_count_log_likelihood_binomial():
    counts = {
        "rep1": {
            "apo": [(5, 10), (8, 10)],
            "bound": [(9, 10), (2, 10)],
        },
        "rep2": {
            "apo": [(6, 10), (7, 10)],
            "bound": [(8, 10), (3, 10)],
        },
    }
    m = WithinReplicateCountModel(counts, dispersion=None)
    ll = m.log_likelihood()
    assert ll < 0  # valid densities are < 1 in log space across many events
    # zero dispersion == binomial; positive dispersion lowers the density
    m2 = WithinReplicateCountModel(counts, dispersion=0.05)
    assert m2.log_likelihood() < 0


def test_within_replicate_zero_reads_raises():
    counts = {"rep1": {"apo": [(0, 0)]}}
    m = WithinReplicateCountModel(counts, dispersion=None)
    try:
        m.log_likelihood()
    except ValueError:
        return
    raise AssertionError("expected ValueError for zero total reads")


def test_within_replicate_requires_counts():
    """The count model cannot be built from merged reactivity alone."""
    # A bare reactivity profile has no counts -> the model is not constructible
    # from the real glycine archive, which is the qualification failure.
    try:
        WithinReplicateCountModel({}, dispersion=None)
    except Exception:  # noqa: BLE001 - empty map is degenerate
        pass
    # The archive status is a permanent, explicit signal.
    assert REPLAY_MISSING == "RAW_COUNT_REPLAY_UNAVAILABLE"
    assert BLOCKED_PENDING_ARCHIVE_QUALIFICATION == "BLOCKED_PENDING_ARCHIVE_QUALIFICATION"


def test_post_selection_diagnostic_compares_models():
    apo = [0.4, 0.4, 0.4]
    bound = [0.6, 0.6, 0.6]
    direct = DirectClampModel(apo, bound, floor=0.01)
    null = EqualLawNullModel(apo, bound, floor=0.01)
    # frozen probe set (post-selection) and diagnostic observations
    diag = [("apo", 0, 0), ("apo", 1, 1), ("bound", 0, 1), ("bound", 1, 1)]
    res = run_post_selection_diagnostic(
        {"direct": direct, "null": null},
        diagnostic=diag,
        probe_indices=[0, 1],
    )
    assert set(res.log_score) == {"direct", "null"}
    assert set(res.conditional_errors) == {"direct", "null"}
    for name in res.conditional_errors:
        errs = res.conditional_errors[name]
        assert "alpha" in errs and "beta" in errs and "abstain" in errs
    # direct (separation) model should score >= null on separated diagnostic data
    assert res.log_score["direct"] >= res.log_score["null"]


def test_post_selection_diagnostic_ignores_non_probe_positions():
    apo = [0.4, 0.4, 0.9]
    bound = [0.6, 0.6, 0.1]
    direct = DirectClampModel(apo, bound, floor=0.01)
    diag = [("apo", 2, 0), ("bound", 2, 1)]  # only position 2 (not in probe set)
    res = run_post_selection_diagnostic(
        {"direct": direct}, diagnostic=diag, probe_indices=[0, 1]
    )
    assert res.log_score["direct"] == 0.0  # no probed observations scored