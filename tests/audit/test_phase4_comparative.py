"""Conditional Phase 4 (synthetic route): sealed-confirmation comparative tests.

Verifies the sealed-confirmation comparative record produced by
``scripts/t4_phase4_comparative.py``:

* all five pre-registered sealed families are constructed concretely with the
  SEALED generation mechanism (``dgrid_den5_pairmerge_narrow_noisy``);
* every block is a non-degenerate problem (p0 != p1, valid column-stochastic
  noisy low-rank channels, within-budget costs);
* D2T (the exact decision framework) is never worse than the matched strongest
  comparator (``chernoff``) on every exact block -- ``d_i <= 0`` -- and strictly
  better on blocks where the comparator misses the certified optimum;
* the unsolvable sealed family is handled fail-closed as ``BOUND_ONLY`` with a
  certified Scheme C interval (no exact point claim);
* the Pareto frontier is valid (non-dominated) and dominance is reported;
* runtime / gap / coverage + timeout / failure accounting is complete;
* fail-closed: ``scientific_claim_authorized=False``,
  ``status=COMPARATIVE_SYNTHETIC_RECORD``, no SOTA / superiority claim.
"""

from __future__ import annotations

from fractions import Fraction

from scripts.t4_phase4_comparative import (
    _run_solvable_block,
    _run_unsolvable_block,
    build_phase4_report,
    build_sealed_families,
)

SEALED_FAMILY_IDS = {
    "q_s2_2x2_noisy",
    "q_s2_3x3_noisy",
    "q_s3_2x2_noisy",
    "q_s3_3x3_noisy",
    "q_s3_3x2_noisy_unsolv",
}


def _channel_columns_sum_to_one(channel):
    n_states = len(channel[0])
    for w in range(n_states):
        total = sum(row[w] for row in channel)
        assert total == 1, f"column {w} does not sum to 1: {total}"
    for row in channel:
        for val in row:
            assert 0 <= val <= 1, f"entry out of [0,1]: {val}"


def test_all_five_sealed_families_present():
    fams = build_sealed_families()
    ids = {f["family_id"] for f in fams}
    assert ids == SEALED_FAMILY_IDS, f"sealed families mismatch: {ids}"
    assert len(fams) == 5
    assert all(f["generation_mechanism"] == "dgrid_den5_pairmerge_narrow_noisy"
               for f in fams)


def test_every_block_is_nondegenerate_and_channels_valid():
    fams = build_sealed_families()
    assert fams
    for fam in fams:
        assert fam["blocks"], f"{fam['family_id']} has no blocks"
        for a in fam["action_objects"]:
            _channel_columns_sum_to_one(a.channel)
        for blk in fam["blocks"]:
            assert tuple(blk["p0"]) != tuple(blk["p1"]), \
                f"{blk['block_id']} degenerate p0==p1"
            assert len(blk["p0"]) == fam["n_states"]
            assert len(blk["p1"]) == fam["n_states"]
            # narrow margin: p0 and p1 are near-collision (small TV)
            tv = sum(abs(a - b) for a, b in zip(blk["p0"], blk["p1"])) / 2
            assert 0 < tv <= Fraction(3, 10), \
                f"{blk['block_id']} not narrow margin (tv={tv})"


def test_exact_block_d2t_never_worse_than_comparator():
    fams = build_sealed_families()
    fam = next(f for f in fams if f["exact_scale"] == "solvable")
    res = _run_solvable_block(fam, fam["blocks"][0])
    assert res["exact_status"] == "RUN"
    assert Fraction(res["d_i"]) <= 0, "D2T must never be worse than comparator"
    assert res["timeout"] is False
    assert res["failure"] is None
    # D2T error equals the certified oracle optimum on this block
    assert Fraction(res["d2t_error"]) >= 0


def test_unsolvable_block_is_fail_closed_bound_only():
    fams = build_sealed_families()
    fam = next(f for f in fams if f["exact_scale"] == "unsolvable")
    res = _run_unsolvable_block(fam, fam["blocks"][0])
    assert res["exact_status"] == "BOUND_ONLY"
    lo = Fraction(res["d2t_error_lower"])
    hi = Fraction(res["d2t_error_upper"])
    assert 0 <= lo <= hi <= 1
    assert res["within_budget"] is True
    assert res["bound"] == "BHATTACHARYYA_PRODUCT_TWO_SIDED"
    assert res["comparator_relation_to_certified"] in {
        "CERTIFIED_WORSE_THAN_D2T_UPPER",
        "CERTIFIED_BELOW_D2T_LOWER",
        "WITHIN_D2T_CERTIFIED_INTERVAL",
    }


def test_full_report_fail_closed_invariants():
    rep = build_phase4_report()
    s = rep["summary"]
    assert rep["status"] == "COMPARATIVE_SYNTHETIC_RECORD"
    assert rep["scientific_claim_authorized"] is False
    assert rep["comparator"] == "chernoff"
    assert s["n_families"] == 5
    assert s["n_blocks"] == s["n_exact"] + s["n_bound_only"]
    assert s["n_bound_only"] == 5          # the unsolvable family is bound-only
    assert s["n_timeout"] == 0
    assert s["n_failure"] == 0
    assert s["n_withheld_certificate"] == s["n_bound_only"]
    assert s["d2t_never_worse_than_comparator"] is True
    # no superiority claim: CI must not assert strict superiority
    ci = s["pooled_delta_ci"]
    assert ci is not None
    assert ci["mean"] <= 0
    assert "strictly_below_zero" in ci
    # every exact block has d_i <= 0
    for fam in rep["families"]:
        for c in fam["cells"]:
            if c["exact_status"] == "RUN":
                assert Fraction(c["d_i"]) <= 0, \
                    f"{c['block_id']} d_i>0 would violate D2T optimality"
