"""Tests for D2T-RNA v7 §8.3 R1 materialization of the SAM-III/GSE278422 dataset."""

from __future__ import annotations

import hashlib
import json

from d2t_rna.data.r1_materialize_sam_iii import (
    CONSTRUCTS,
    CONDITIONS,
    SAM_III_ROLE,
    materialize_sam_iii,
    parse_reactivity_table,
)

FIXTURE_REACT = (
    "2 components; BIC=10749806.8\n"
    "p 0.516 0.484\n"
    "Nt      Seq     nReact  Raw             nReact  Raw             Background\n"
    "1       G       nan     nan             nan     nan             nan\n"
    "15      G       -0.0392 0.0025          -0.0603 0.0018          0.0037 i\n"
    "16      U       0.0615  0.0113          0.1294  0.0134          0.0094 i\n"
    "17      U       0.1454  0.0060          0.2705  0.0099          0.0015\n"
)

FIXTURE_FASTA = ">SAMIII_native\nGGAAACUCGGU\n"

FIXTURE_ARCHIVE = b"dummy tar.gz payload"

# Single-mutant reactivity tables report 1 component (5 columns:
# Nt Seq nReact Raw Background).  The parser must not apply the
# 2-component minimum-column rule to them (contract 8.3 materialization).
FIXTURE_REACT_1COMP = (
    "1 components; BIC=20956395.8\n"
    "p 1.000\n"
    "Nt      Seq     nReact  Raw             Background\n"
    "1       G       nan     nan             nan\n"
    "15      G       -0.0296 0.0019          0.0029 i\n"
    "16      U       0.2060  0.0136          0.0065\n"
    "17      U       0.2874  0.0113          0.0014\n"
)


def test_parse_reactivity_table_1component() -> None:
    """1-component (single-mutant) tables must parse fully, not as 0 positions."""
    raw = FIXTURE_REACT_1COMP.encode("utf-8")
    tab = parse_reactivity_table(raw, "abc")
    assert tab.n_components == 1
    assert tab.mixture == (1.0,)
    assert tab.n_positions == 4
    assert tab.positions == (1, 15, 16, 17)
    # row = [nReact, Raw, Background], so row[1] is the modified-channel rate.
    assert tab.rows[1][0] == -0.0296
    assert tab.rows[1][1] == 0.0019
    assert tab.rows[1][2] == 0.0029


def test_parse_reactivity_table_basic() -> None:
    raw = FIXTURE_REACT.encode("utf-8")
    sha = "abc"
    tab = parse_reactivity_table(raw, sha)
    assert tab.n_components == 2
    assert tab.mixture == (0.516, 0.484)
    assert tab.n_positions == 4
    assert tab.positions == (1, 15, 16, 17)
    # row 15: comp1_count, comp1_raw, comp2_count, comp2_raw, background
    assert tab.rows[1][0] == -0.0392
    assert tab.rows[1][1] == 0.0025
    assert tab.rows[1][4] == 0.0037


def test_parse_reactivity_nan_handling() -> None:
    raw = FIXTURE_REACT.encode("utf-8")
    tab = parse_reactivity_table(raw, "abc")
    assert tab.rows[0][0] != tab.rows[0][0]  # nan


def test_observed_table_hash_stable() -> None:
    raw = FIXTURE_REACT.encode("utf-8")
    tab = parse_reactivity_table(raw, "abc")
    h1 = tab.observed_table_hash()
    h2 = tab.observed_table_hash()
    assert h1 == h2
    assert len(h1) == 64
    assert h1 == hashlib.sha256(tab.canonical_bytes()).hexdigest()


def test_materialize_sam_iii(tmp_path) -> None:
    react = tmp_path / "dancemap_reactivities"
    fasta = tmp_path / "fasta_references"
    react.mkdir()
    fasta.mkdir()
    # one construct x one condition fixture
    (react / "SAMIII_native_noSAM-reactivities.txt").write_text(FIXTURE_REACT)
    (fasta / "SAMIII_native.fa").write_text(FIXTURE_FASTA)
    # one dummy archive
    (tmp_path / "GSE278422_dancemap_reactivities.tar.gz").write_bytes(FIXTURE_ARCHIVE)

    report = materialize_sam_iii(
        tmp_path,
        downloaded_at="2026-08-05T00:00:00Z",
    )
    assert report["dataset_id"] == "sam-iii"
    assert report["role"] == SAM_III_ROLE
    assert report["status"] == "MATERIALIZED"
    assert report["condition_count"] == 1
    assert report["condition_names"] == ["native_noSAM"]
    assert report["observed_dataset_hash"]
    assert len(report["observed_dataset_hash"]) == 64
    assert report["raw_archive_shas"]["GSE278422_dancemap_reactivities.tar.gz"] == (
        hashlib.sha256(FIXTURE_ARCHIVE).hexdigest()
    )
    assert report["construct_sequence_hashes"]["SAMIII_native"]
    # sidecars written next to the raw dir
    assert (tmp_path.parent / "sam-iii.canonical.json").exists()
    assert (tmp_path.parent / "sam-iii.sha256").exists()
    # report is JSON-serializable
    json.dumps(report)


def test_materialize_sam_iii_constructs_conditions() -> None:
    assert set(CONSTRUCTS) == {
        "native",
        "MutON1",
        "MutON2",
        "MutOFF1",
        "MutOFF2",
    }
    assert set(CONDITIONS) == {"SAM", "noSAM"}