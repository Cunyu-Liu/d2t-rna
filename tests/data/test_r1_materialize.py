"""Tests for D2T-RNA v7 §8.3 R1 observed-dataset materialization."""

from __future__ import annotations

import hashlib
import json

from d2t_rna.data.r1_materialize import (
    ADD_ROLE,
    R1MaterializationReport,
    materialize_add,
    parse_rdat_bytes,
    sha256_of,
)

# A minimal but structurally faithful add/RMDB-style .rdat fixture.
RDAT_FIXTURE = (
    "NAME test_riboswitch\n"
    "SEQUENCE GGAAACUCGGU\n"
    "STRUCTURE ((((....))))\n"
    "OFFSET 1\n"
    "SEQPOS 1 2 3 4 5 6 7 8 9 10 11\n"
    "MUTPOS 1 2 3 4 5 6 7 8 9 10 11\n"
    "MUTATION_OBSERVED WT WT WT WT C WT WT WT WT WT WT\n"
    "ANNOTATION_DATA:1 WT\n"
    "ANNOTATION_DATA:2 C5G\n"
    "REACTIVITY:1 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1\n"
    "REACTIVITY:2 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 1.2\n"
)


def test_parse_rdat_basic() -> None:
    raw = RDAT_FIXTURE.encode("utf-8")
    sha = sha256_of(raw)
    data = parse_rdat_bytes(raw, sha)
    assert data.name == "test_riboswitch"
    assert data.sequence == "GGAAACUCGGU"
    assert data.structure == "((((....))))"
    assert data.offset == 1
    assert data.n_seqpos == 11
    assert data.n_constructs == 2
    assert data.n_data_points == 22
    assert data.mutation_observed[4] == "C"
    assert data.constructs[0].index == 1
    assert data.constructs[0].mutation == "WT"
    assert data.constructs[1].mutation == "C5G"
    assert data.reactivity[0][0] == 0.1
    assert data.reactivity[1][-1] == 1.2


def test_observed_dataset_hash_is_stable_and_sha256() -> None:
    raw = RDAT_FIXTURE.encode("utf-8")
    data = parse_rdat_bytes(raw, sha256_of(raw))
    h1 = data.observed_dataset_hash()
    h2 = data.observed_dataset_hash()
    assert h1 == h2
    assert len(h1) == 64
    # digest of the canonical serialization
    assert h1 == hashlib.sha256(data.canonical_bytes()).hexdigest()


def test_canonical_bytes_roundtrip_sorted() -> None:
    raw = RDAT_FIXTURE.encode("utf-8")
    data = parse_rdat_bytes(raw, sha256_of(raw))
    payload = json.loads(data.canonical_bytes())
    assert payload["sequence"] == "GGAAACUCGGU"
    assert payload["constructs"][1]["mutation"] == "C5G"
    assert payload["reactivity"][0][0] == 0.1


def test_data_point_count_consistency_validated() -> None:
    raw = RDAT_FIXTURE.encode("utf-8")
    data = parse_rdat_bytes(raw, sha256_of(raw))
    assert data.n_data_points == data.n_constructs * data.n_seqpos


def test_materialize_add_report_fields(tmp_path) -> None:
    raw = tmp_path / "ADDRSW_SHP_0003.rdat"
    raw.write_bytes(RDAT_FIXTURE.encode("utf-8"))
    report = materialize_add(
        raw,
        accession="ADDRSW_SHP_0003",
        downloaded_at="2026-08-05T00:00:00Z",
    )
    assert isinstance(report, R1MaterializationReport)
    assert report.dataset_id == "add"
    assert report.accession == "ADDRSW_SHP_0003"
    assert report.role == ADD_ROLE
    assert report.status == "MATERIALIZED"
    assert report.downloaded_at == "2026-08-05T00:00:00Z"
    assert report.construct_count == 2
    assert report.seqpos_count == 11
    assert report.data_point_count == 22
    assert len(report.raw_sha256) == 64
    assert len(report.observed_dataset_hash) == 64
    assert report.dependency_units == ("construct", "seqpos", "mutation")
    # sidecars written next to the raw file
    assert (tmp_path / "ADDRSW_SHP_0003.canonical.json").exists()
    assert (tmp_path / "ADDRSW_SHP_0003.sha256").exists()


def test_materialize_add_sidecar_hash_matches() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ADDRSW_SHP_0003.rdat"
        p.write_bytes(RDAT_FIXTURE.encode("utf-8"))
        report = materialize_add(p, downloaded_at="2026-08-05T00:00:00Z")
        sidecar = Path(d) / "ADDRSW_SHP_0003.sha256"
        content = sidecar.read_text().strip()
        assert content == f"{report.observed_dataset_hash}  {p.name}"


def test_materialize_add_bytes_is_int() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ADDRSW_SHP_0003.rdat"
        p.write_bytes(RDAT_FIXTURE.encode("utf-8"))
        report = materialize_add(p, downloaded_at="2026-08-05T00:00:00Z")
        assert isinstance(report.raw_bytes, int)
        assert report.raw_bytes == len(RDAT_FIXTURE.encode("utf-8"))
        # as_dict must be JSON-serializable
        json.dumps(report.as_dict())