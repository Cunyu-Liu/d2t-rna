"""R1 materialization for the add/RMDB full-matrix dataset (contract 8.3).

R1 materializes a registered public dataset and freezes the evidence required
by §8.3: raw checksums, download time, version and license, construct/assay
mapping, dependency units, outcome-access timestamp, theorem/method-freeze
hash, and the complete observed-dataset hash; and the layering of raw /
processed / author-truth payload and derived results.

The add/RMDB accession ``ADDRSW_SHP_0003`` is an SHAPE mutate-and-map dataset
for the adenine riboswitch (Kladwang et al. 2011, Nat. Chem.).  The raw file is
the ``.rdat`` RMDB exchange format.  This module parses it into a canonical,
hash-bound structured form and produces the observed-dataset hash.

This is a *materialization*, not a scientific claim: it freezes evidence.  Any
later retrospective evaluation (R2) of the materialized matrix is gated by
the fail-closed framework (contract 8.4) and authorizes no formal claim on its
own.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

# Contract §8.5 role for add/RMDB.
ADD_ROLE = "COUNTERFACTUAL_RETROSPECTIVE_FULL_MATRIX_COMPRESSION"

_REACTIVITY_RE = re.compile(r"^REACTIVITY:(\d+)\s+(.+)$")
_ANNOTATION_DATA_RE = re.compile(r"^ANNOTATION_DATA:(\d+)\s+(.+)$")


@dataclass(frozen=True)
class AddConstruct:
    """One construct (assayed molecule) in the add mutate-and-map panel."""

    index: int           # REACTIVITY row index (1-based)
    mutation: str        # e.g. "WT", "C13G", "G14C", ...


@dataclass(frozen=True)
class AddMutateMapData:
    """Canonical in-memory parse of an add/RMDB .rdat file."""

    source_file_sha256: str
    name: str
    sequence: str
    structure: str
    offset: int
    seqpos: tuple[int, ...]
    mutpos: tuple[int, ...]
    mutation_observed: tuple[str, ...]   # per seqpos, "WT" or the mutating nt
    constructs: tuple[AddConstruct, ...]
    reactivity: tuple[tuple[float, ...], ...]  # [construct][seqpos]

    @property
    def n_constructs(self) -> int:
        return len(self.constructs)

    @property
    def n_seqpos(self) -> int:
        return len(self.seqpos)

    @property
    def n_data_points(self) -> int:
        return self.n_constructs * self.n_seqpos

    def canonical_bytes(self) -> bytes:
        """Stable serialization used for the observed-dataset hash."""
        payload = {
            "name": self.name,
            "sequence": self.sequence,
            "structure": self.structure,
            "offset": self.offset,
            "seqpos": list(self.seqpos),
            "mutpos": list(self.mutpos),
            "mutation_observed": list(self.mutation_observed),
            "constructs": [
                {"index": c.index, "mutation": c.mutation} for c in self.constructs
            ],
            "reactivity": [
                [round(v, 6) for v in row] for row in self.reactivity
            ],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def observed_dataset_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def parse_rdat_bytes(raw: bytes, source_sha256: str) -> AddMutateMapData:
    """Parse an add/RMDB .rdat file (RMDB v0.24) into canonical data."""
    text = raw.decode("utf-8")
    lines = text.splitlines()

    name = ""
    sequence = ""
    structure = ""
    offset = 0
    seqpos: tuple[int, ...] = ()
    mutpos: tuple[int, ...] = ()
    mutation_observed: tuple[str, ...] = ()
    annotations: dict[int, str] = {}
    reactivity: dict[int, list[float]] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("NAME "):
            name = line[len("NAME "):].strip()
        elif line.startswith("SEQUENCE "):
            sequence = line[len("SEQUENCE "):].strip()
        elif line.startswith("STRUCTURE "):
            structure = line[len("STRUCTURE "):].strip()
        elif line.startswith("OFFSET "):
            offset = int(line[len("OFFSET "):].strip())
        elif line.startswith("SEQPOS "):
            seqpos = tuple(int(x) for x in line[len("SEQPOS "):].split())
        elif line.startswith("MUTPOS "):
            mutpos = tuple(
                int(x) if x != "WT" else 0 for x in line[len("MUTPOS "):].split()
            )
        elif line.startswith("MUTATION_OBSERVED "):
            mutation_observed = tuple(
                line[len("MUTATION_OBSERVED "):].split()
            )
        else:
            m_ann = _ANNOTATION_DATA_RE.match(line)
            if m_ann:
                annotations[int(m_ann.group(1))] = m_ann.group(2).strip()
                continue
            m_re = _REACTIVITY_RE.match(line)
            if m_re:
                idx = int(m_re.group(1))
                reactivity[idx] = [float(x) for x in m_re.group(2).split()]
                continue

    if not sequence or not seqpos:
        raise ValueError("rdat parse failed: missing SEQUENCE/SEQPOS")

    # Default mutation_observed = all WT if the header does not give it.
    if not mutation_observed:
        mutation_observed = tuple("WT" for _ in seqpos)

    constructs: list[AddConstruct] = sorted(
        (AddConstruct(index=i, mutation=annotations.get(i, "UNKNOWN"))
         for i in reactivity),
        key=lambda c: c.index,
    )
    if not constructs:
        raise ValueError("rdat parse failed: no REACTIVITY rows")

    # Build reactivity rows in construct order.
    rows: list[tuple[float, ...]] = []
    for c in constructs:
        row = reactivity[c.index]
        if len(row) != len(seqpos):
            raise ValueError(
                f"construct {c.index} has {len(row)} values but {len(seqpos)} positions"
            )
        rows.append(tuple(row))

    return AddMutateMapData(
        source_file_sha256=source_sha256,
        name=name,
        sequence=sequence,
        structure=structure,
        offset=offset,
        seqpos=seqpos,
        mutpos=mutpos,
        mutation_observed=mutation_observed,
        constructs=tuple(constructs),
        reactivity=tuple(rows),
    )


def sha256_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class R1MaterializationReport:
    """§8.3 evidence freeze for one materialized dataset."""

    dataset_id: str
    accession: str
    role: str
    raw_path: str
    raw_sha256: str
    raw_bytes: int
    downloaded_at: str            # ISO-8601 UTC
    source_version: str           # RDAT_VERSION
    license: str
    construct_count: int
    seqpos_count: int
    data_point_count: int
    observed_dataset_hash: str
    dependency_units: tuple[str, ...]
    layering: dict[str, str]      # raw / processed / author-truth / derived
    status: str = "MATERIALIZED"

    def as_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "accession": self.accession,
            "role": self.role,
            "raw_path": self.raw_path,
            "raw_sha256": self.raw_sha256,
            "raw_bytes": self.raw_bytes,
            "downloaded_at": self.downloaded_at,
            "source_version": self.source_version,
            "license": self.license,
            "construct_count": self.construct_count,
            "seqpos_count": self.seqpos_count,
            "data_point_count": self.data_point_count,
            "observed_dataset_hash": self.observed_dataset_hash,
            "dependency_units": list(self.dependency_units),
            "layering": self.layering,
            "status": self.status,
        }


def materialize_add(
    raw_path: Path | str,
    *,
    accession: str = "ADDRSW_SHP_0003",
    role: str = ADD_ROLE,
    downloaded_at: str | None = None,
    license: str = "add/RMDB terms (Kladwang et al. 2011); see accession page",
    dependency_units: Sequence[str] = (
        "construct",
        "seqpos",
        "mutation",
    ),
) -> R1MaterializationReport:
    """Materialize the add/RMDB .rdat file and freeze the §8.3 evidence.

    Writes the canonical JSON next to the raw file as ``<base>.canonical.json``
    and the observed-dataset hash as ``<base>.sha256``.
    """
    raw = Path(raw_path)
    raw_bytes = raw.read_bytes()
    raw_sha = sha256_of(raw_bytes)
    data = parse_rdat_bytes(raw_bytes, raw_sha)
    if data.n_data_points != data.n_constructs * data.n_seqpos:
        raise ValueError("data point count is inconsistent")

    now = downloaded_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs_hash = data.observed_dataset_hash()

    # Persist canonical JSON + hash sidecar next to the raw file.
    canonical_json = raw.with_name(raw.stem + ".canonical.json")
    canonical_json.write_bytes(data.canonical_bytes())
    sha_sidecar = raw.with_name(raw.stem + ".sha256")
    sha_sidecar.write_text(f"{obs_hash}  {raw.name}\n")

    report = R1MaterializationReport(
        dataset_id="add",
        accession=accession,
        role=role,
        raw_path=str(raw),
        raw_sha256=raw_sha,
        raw_bytes=len(raw_bytes),
        downloaded_at=now,
        source_version="RMDB_RDAT_0.24",
        license=license,
        construct_count=data.n_constructs,
        seqpos_count=data.n_seqpos,
        data_point_count=data.n_data_points,
        observed_dataset_hash=obs_hash,
        dependency_units=tuple(dependency_units),
        layering={
            "raw": str(raw),
            "processed": str(canonical_json),
            "author_truth": "STRUCTURE dot-bracket in raw (native_truth_label_generated=false)",
            "derived": "task6 add full-matrix replay (R2, gated)",
        },
    )
    return report