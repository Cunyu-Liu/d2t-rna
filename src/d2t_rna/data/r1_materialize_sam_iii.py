"""R1 materialization for the SAM-III/GSE278422 DANCE-MaP dataset (contract 8.3).

SAM-III (adenosylmethionine-sensing SAM-III riboswitch, RF01767 / PDB 6C27 /
GSE278422) is a DANCE-MaP (DMS accessibility) mutate-and-probe dataset.  The
raw supplement on NCBI GEO provides, per construct x ligand condition:

  * ``dancemap_reactivities/<construct>_<SAM|noSAM>-reactivities.txt``  -- the
    two-component DMS reactivity table (per-nucleotide mutation counts and
    rates in the modified and untreated channels);
  * ``shapemap_profiles/<construct>_<SAM|noSAM>_profile.txt``             -- the
    normalized reactivity profile table;
  * ``fasta_references/<construct>.fa``                                    -- the
    reference sequence.

R1 materializes this raw evidence and freezes the §8.3 items: raw checksums,
download time, version and license, construct/assay/condition mapping,
dependency units, observed-dataset hash, and the raw/processed/author-truth/
derived layering.  This is a *materialization*, not a scientific claim; any
later R2 evaluation is gated by the fail-closed framework (contract 8.4).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

# Contract §8.5 role for SAM-III/GSE278422.
SAM_III_ROLE = "RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC"

CONSTRUCTS = ("native", "MutON1", "MutON2", "MutOFF1", "MutOFF2")
CONDITIONS = ("SAM", "noSAM")

# reactivity table columns (space-separated within the fixed-width table)
_REACT_HDR = re.compile(r"^Nt\s+Seq\s+")
_REACT_ROW = re.compile(
    r"^\s*(\d+)\s+([A-Za-z])\s+([\d.]+|nan)\s+([-0-9.+eEMan]+|\s+)\s*"
)

# profile table header names that we freeze as column order.
_PROFILE_HDR = re.compile(
    r"^Nucleotide\s+Sequence\s+Modified_mutations\s+"
)


@dataclass(frozen=True)
class SamIIICondition:
    """One construct x ligand condition reactivity table."""

    construct: str
    condition: str
    positions: tuple[int, ...]
    sequence: tuple[str, ...]
    # [position] -> (comp1_count, comp1_raw, comp2_count, comp2_raw, background)
    rows: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class SamIIIReactivity:
    """Canonical in-memory parse of one SAM-III reactivity table."""

    source_file_sha256: str
    construct: str
    condition: str
    n_components: int
    bic: float | None
    mixture: tuple[float, ...]
    positions: tuple[int, ...]
    sequence: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]  # [position][0..4]

    @property
    def n_positions(self) -> int:
        return len(self.positions)

    def canonical_bytes(self) -> bytes:
        payload = {
            "construct": self.construct,
            "condition": self.condition,
            "n_components": self.n_components,
            "bic": self.bic,
            "mixture": [round(x, 6) for x in self.mixture],
            "positions": list(self.positions),
            "sequence": list(self.sequence),
            "rows": [[round(x, 6) for x in row] for row in self.rows],
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def observed_table_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def _to_float(tok: str) -> float:
    tok = tok.strip()
    if not tok or tok.lower() == "nan" or tok == "\u2212nan":
        return float("nan")
    return float(tok)


def parse_reactivity_table(raw: bytes, source_sha256: str) -> SamIIIReactivity:
    """Parse one DANCE-MaP ``-reactivities.txt`` table.

    The table has ``Nt Seq (nReact Raw) x n_components Background`` columns.
    The number of components is read from the header line (``N components``)
    and varies per construct (native = 2, single-mutant = 1).
    """
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    n_components = 2
    bic = None
    mixture: list[float] = []
    positions: list[int] = []
    sequence: list[str] = []
    rows: list[tuple[float, ...]] = []

    m = re.match(r"^(\d+)\s+components", lines[0]) if lines else None
    if m:
        n_components = int(m.group(1))
    for line in lines[1:]:
        if line.lstrip().startswith("p "):
            mixture = [float(x) for x in line.split()[1:]]
            continue
        if _REACT_HDR.match(line):
            continue
        parts = line.split()
        # columns: Nt Seq (nReact Raw) x n_components Background
        need = 2 + 2 * n_components + 1
        if len(parts) < need:
            continue
        try:
            pos = int(parts[0])
        except ValueError:
            continue
        seq = parts[1]
        vals = [_to_float(x) for x in parts[2 : 2 + 2 * n_components + 1]]
        positions.append(pos)
        sequence.append(seq)
        rows.append(tuple(vals))

    return SamIIIReactivity(
        source_file_sha256=source_sha256,
        construct="__unknown__",
        condition="__unknown__",
        n_components=n_components,
        bic=bic,
        mixture=tuple(mixture),
        positions=tuple(positions),
        sequence=tuple(sequence),
        rows=tuple(rows),
    )


def _parse_fasta(raw: bytes) -> tuple[str, str]:
    """Parse a one-record fasta, returning ``(header, sequence)``."""
    text = raw.decode("utf-8", errors="replace")
    lines = text.strip().splitlines()
    header = ""
    seq = ""
    for line in lines:
        if line.startswith(">"):
            header = line[1:].strip()
        else:
            seq += line.strip()
    return header, seq


@dataclass(frozen=True)
class SamIIIMaterialization:
    """Aggregated materialization over all constructs x conditions."""

    accession: str
    role: str
    raw_dir: str
    raw_archive_shas: dict[str, str]
    construct_sequences: dict[str, str]
    construct_sequence_hashes: dict[str, str]
    conditions: tuple[SamIIICondition, ...]
    dependency_units: tuple[str, ...]

    def canonical_bytes(self) -> bytes:
        payload = {
            "accession": self.accession,
            "role": self.role,
            "construct_sequences": {
                k: v for k, v in sorted(self.construct_sequences.items())
            },
            "conditions": [
                {
                    "construct": c.construct,
                    "condition": c.condition,
                    "positions": list(c.positions),
                    "sequence": list(c.sequence),
                    "rows": [[round(x, 6) for x in row] for row in c.rows],
                }
                for c in self.conditions
            ],
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def observed_dataset_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def materialize_sam_iii(
    raw_dir: Path | str,
    *,
    accession: str = "GSE278422",
    role: str = SAM_III_ROLE,
    downloaded_at: str | None = None,
    dependency_units: Sequence[str] = ("construct", "condition", "nucleotide"),
) -> dict:
    """Materialize the SAM-III DANCE-MaP raw supplement and freeze §8.3 evidence.

    Returns a dict report (JSON-serializable) with raw archive checksums,
    construct sequences and hashes, per-condition reactivity, and the complete
    observed-dataset hash.  Writes ``sam-iii.canonical.json`` and
    ``sam-iii.sha256`` next to the raw directory.
    """
    raw = Path(raw_dir)
    react_dir = raw / "dancemap_reactivities"
    fasta_dir = raw / "fasta_references"

    # raw archive checksums (the downloaded .tar.gz files)
    archive_shas: dict[str, str] = {}
    for f in sorted(raw.glob("*.tar.gz")):
        archive_shas[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()

    # construct reference sequences
    construct_sequences: dict[str, str] = {}
    construct_seq_shas: dict[str, str] = {}
    for fa in sorted(fasta_dir.glob("*.fa")):
        header, seq = _parse_fasta(fa.read_bytes())
        construct_sequences[header] = seq
        construct_seq_shas[header] = hashlib.sha256(
            seq.encode("utf-8")
        ).hexdigest()

    # per-condition reactivity
    conditions: list[SamIIICondition] = []
    for construct in CONSTRUCTS:
        for cond in CONDITIONS:
            fname = react_dir / f"SAMIII_{construct}_{cond}-reactivities.txt"
            if not fname.exists():
                continue
            raw_bytes = fname.read_bytes()
            tab = parse_reactivity_table(
                raw_bytes, hashlib.sha256(raw_bytes).hexdigest()
            )
            table = SamIIICondition(
                construct=construct,
                condition=cond,
                positions=tab.positions,
                sequence=tab.sequence,
                rows=tab.rows,
            )
            conditions.append(table)

    mat = SamIIIMaterialization(
        accession=accession,
        role=role,
        raw_dir=str(raw),
        raw_archive_shas=archive_shas,
        construct_sequences=construct_sequences,
        construct_sequence_hashes=construct_seq_shas,
        conditions=tuple(conditions),
        dependency_units=tuple(dependency_units),
    )
    obs_hash = mat.observed_dataset_hash()

    canonical_json = raw.parent / "sam-iii.canonical.json"
    canonical_json.write_bytes(mat.canonical_bytes())
    sha_sidecar = raw.parent / "sam-iii.sha256"
    sha_sidecar.write_text(f"{obs_hash}  {accession}\n")

    now = downloaded_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "dataset_id": "sam-iii",
        "accession": accession,
        "role": role,
        "raw_dir": str(raw),
        "raw_archive_shas": archive_shas,
        "construct_sequences": construct_sequences,
        "construct_sequence_hashes": construct_seq_shas,
        "condition_count": len(conditions),
        "condition_constructs": [c.construct for c in conditions],
        "condition_names": [f"{c.construct}_{c.condition}" for c in conditions],
        "observed_dataset_hash": obs_hash,
        "dependency_units": list(dependency_units),
        "downloaded_at": now,
        "source_version": "GSE278422_suppl (DANCE-MaP)",
        "license": "NCBI GEO public; authors' supplementary data",
        "layering": {
            "raw": str(raw),
            "processed": str(canonical_json),
            "author_truth": "DMS reactivity / SHAPE profile (native_truth_label_generated=false)",
            "derived": "task6 sam-iii modality-transfer diagnostic (R2, gated)",
        },
        "status": "MATERIALIZED",
    }