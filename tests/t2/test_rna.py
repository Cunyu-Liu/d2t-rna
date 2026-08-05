"""Tests for the RNA secondary-structure scaffold (T2e candidate).

These tests verify the scaffold's machinery is *correct* (enumeration,
validity, fiber, swap moves, connectivity/diameter).  They deliberately make
NO novelty claim: the structural lemma is a conjecture under investigation.
"""

from __future__ import annotations

import pytest

from d2t_rna.t2.rna import (
    NOT_ESTABLISHED,
    base_pair_count,
    fiber_by_pair_count,
    fiber_by_profile,
    fiber_connected_and_diameter,
    is_valid_structure,
    paired_profile,
    scan_profile_fibers,
    structures,
    swap_neighbors,
)


def test_structures_count_matches_motzkin() -> None:
    # Motzkin numbers M_n (n positions): M_0=M_1=1, M_2=2, M_3=4, M_4=9, M_5=21.
    # We count all noncrossing matchings (allow positions unpaired).
    expected = {0: 1, 1: 1, 2: 2, 3: 4, 4: 9, 5: 21, 6: 51}
    for L, count in expected.items():
        assert len(structures(L)) == count, L


def test_all_structures_are_valid() -> None:
    for L in range(2, 8):
        for s in structures(L):
            assert is_valid_structure(s), (L, s)


def test_paired_profile() -> None:
    s = ((0, 3), (1, 2))
    assert paired_profile(s, 6) == (1, 1, 1, 1, 0, 0)
    assert base_pair_count(s) == 2


def test_fiber_by_profile_consistent() -> None:
    L = 6
    seen = set()
    for s in structures(L):
        prof = paired_profile(s, L)
        seen.add(prof)
    for prof in seen:
        fb = fiber_by_profile(L, prof)
        assert all(paired_profile(x, L) == prof for x in fb)
        assert len(fb) >= 1
        # every structure in the fiber was enumerated
        assert all(x in structures(L) for x in fb)


def test_fiber_by_pair_count_values() -> None:
    L = 6
    for count in range(0, 4):
        fb = fiber_by_pair_count(L, count)
        assert all(base_pair_count(x) == count for x in fb)


def test_swap_moves_stay_valid_and_same_profile() -> None:
    L = 6
    for s in structures(L):
        prof = paired_profile(s, L)
        for t in swap_neighbors(s):
            assert is_valid_structure(t)
            assert paired_profile(t, L) == prof


def test_swap_neighbors_unique() -> None:
    for L in range(4, 7):
        for s in structures(L):
            nbrs = swap_neighbors(s)
            assert len(nbrs) == len(set(nbrs))


def test_scan_profile_fibers_small() -> None:
    for L in [4, 6]:
        evs = scan_profile_fibers(L)
        assert evs
        for ev in evs:
            assert ev.status == NOT_ESTABLISHED
            assert ev.fiber_size >= 1
            # connectivity is computed, whatever it is (no claim yet)
            assert ev.swap_connected in (True, False)


def test_fiber_connected_single_element() -> None:
    # the empty structure (all unpaired) fiber has one element -> connected.
    L = 4
    empty = (0, 0, 0, 0)
    conn, diam, size = fiber_connected_and_diameter(L, empty)
    assert size == 1
    assert conn is True
    assert diam is None


def test_conjecture_evidence_collected_not_asserted() -> None:
    # We do NOT assert the lemma holds; we only ensure evidence is produced so
    # the researcher can decide whether the conjecture is supported.
    L = 6
    evs = scan_profile_fibers(L)
    multi = [e for e in evs if e.fiber_size >= 2]
    # At least one non-trivial fiber must exist at L=6 to be worth studying.
    assert multi, "expected at least one non-trivial fiber at L=6"