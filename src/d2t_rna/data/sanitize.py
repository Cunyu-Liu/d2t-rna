"""Fail-closed scanner for exact pre-Lock-D planning-package directories."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import unicodedata
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import unquote

from pydantic import StrictBool, StrictInt, StrictStr, model_validator

from ..contracts.base import (
    FrozenContractModel,
    canonical_sha256,
    strict_revalidate_contract_model,
    validate_contract_json_syntax,
)
from ..contracts.enums import ExposureStatus, LockStage
from ..contracts.primitives import RegisteredId, Sha256Hex


CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)
SANITIZER_RULESET_ID = "d2t_rna.pre_d_semantic_sanitizer.v1"
MAX_PARSED_FILE_BYTES = 16 * 1024 * 1024

_REGISTERED_SEMANTIC_TOKENS = ("on", "off", "rescue")
_FORBIDDEN_PRE_D_FIELDS = (
    "population_estimate",
    "confidence_region",
    "directional_evidence",
    "state_preservation_result",
    "projected_state_proportions",
    "h0_h1_core_binding",
    "action_effect_labels",
    "native_t4_eligible",
)
_CONFUSABLE_ASCII = str.maketrans(
    {
        "Ο": "o",
        "ο": "o",
        "О": "o",
        "о": "o",
        "ᴏ": "o",
        "Ν": "n",
        "ν": "n",
        "Н": "n",
        "н": "n",
        "ɴ": "n",
        "Ϝ": "f",
        "ϝ": "f",
        "Ғ": "f",
        "ғ": "f",
        "Ρ": "p",
        "ρ": "p",
        "Р": "p",
        "р": "p",
        "Ε": "e",
        "ε": "e",
        "Е": "e",
        "е": "e",
        "Ѕ": "s",
        "ѕ": "s",
        "С": "c",
        "с": "c",
        "Ս": "u",
        "ս": "u",
    }
)
_UNICODE_ESCAPE = re.compile(
    r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})|\\x([0-9a-fA-F]{2})"
)
_ARCHIVE_MAGICS = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
    b"\x1f\x8b",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07",
)
_TEXT_SUFFIXES = {
    ".csv": ("text/csv", "parser.csv_utf8.v1"),
    ".fa": ("application/fasta", "parser.fasta_utf8.v1"),
    ".fasta": ("application/fasta", "parser.fasta_utf8.v1"),
    ".fastq": ("application/fastq", "parser.fastq_utf8.v1"),
    ".fq": ("application/fastq", "parser.fastq_utf8.v1"),
    ".tsv": ("text/tab-separated-values", "parser.tsv_utf8.v1"),
    ".txt": ("text/plain", "parser.text_utf8.v1"),
}


class LeakSurface(str, Enum):
    FILE_NAME = "FILE_NAME"
    HEADER_NAME = "HEADER_NAME"
    HEADER_VALUE = "HEADER_VALUE"
    METADATA_KEY = "METADATA_KEY"
    METADATA_VALUE = "METADATA_VALUE"
    PUBLIC_LOCATOR = "PUBLIC_LOCATOR"
    PACKAGE_STRUCTURE = "PACKAGE_STRUCTURE"


class PreRevealDisposition(str, Enum):
    NO_REGISTERED_LEAKAGE_DETECTED = "NO_REGISTERED_LEAKAGE_DETECTED"
    EVALUATION_INVALIDATED_PRE_LOCK_D = (
        "EVALUATION_INVALIDATED_PRE_LOCK_D"
    )
    AUDIT_INCOMPLETE_FAIL_CLOSED = "AUDIT_INCOMPLETE_FAIL_CLOSED"


class HeaderField(FrozenContractModel):
    schema_id: Literal["d2t_rna.planning_header_field"] = (
        "d2t_rna.planning_header_field"
    )
    schema_version: Literal["1.0"] = "1.0"
    locator: StrictStr
    name: StrictStr
    value: StrictStr


class MetadataField(FrozenContractModel):
    schema_id: Literal["d2t_rna.planning_metadata_field"] = (
        "d2t_rna.planning_metadata_field"
    )
    schema_version: Literal["1.0"] = "1.0"
    locator: StrictStr
    key: StrictStr
    value: StrictStr


class PlanningPackageEntry(FrozenContractModel):
    """Scanner-derived inventory record; callers cannot authorize it directly."""

    schema_id: Literal["d2t_rna.planning_package_entry"] = (
        "d2t_rna.planning_package_entry"
    )
    schema_version: Literal["1.0"] = "1.0"
    entry_index: StrictInt
    relative_path: StrictStr
    entry_kind: Literal[
        "REGULAR_FILE",
        "SYMLINK",
        "HARDLINK",
        "ARCHIVE",
        "DEVICE",
        "OPAQUE",
    ]
    media_type: StrictStr
    parser_id: RegisteredId
    content_sha256: Sha256Hex
    byte_size: StrictInt
    complete_parse: StrictBool
    headers: tuple[HeaderField, ...] = ()
    metadata: tuple[MetadataField, ...] = ()

    @model_validator(mode="after")
    def counts_are_nonnegative(self) -> "PlanningPackageEntry":
        if self.entry_index < 0:
            raise ValueError("planning entry index must be nonnegative")
        if self.byte_size < 0:
            raise ValueError("planning entry byte size must be nonnegative")
        return self


class PublicLeakLocation(FrozenContractModel):
    """Redacted finding with no path, source value, number, or snippet."""

    schema_id: Literal["d2t_rna.public_leak_location"] = (
        "d2t_rna.public_leak_location"
    )
    schema_version: Literal["1.0"] = "1.0"
    entry_index: StrictInt
    path_hash: Sha256Hex
    surface: LeakSurface
    locator_hash: Sha256Hex
    rule_id: RegisteredId


class PreRevealAuditReport(FrozenContractModel):
    schema_id: Literal["d2t_rna.pre_reveal_audit_report"] = (
        "d2t_rna.pre_reveal_audit_report"
    )
    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: RegisteredId
    stage: LockStage
    source_package_hash: Sha256Hex
    ruleset_hash: Sha256Hex
    scanner_release_hash: Sha256Hex
    scanned_entry_count: StrictInt
    disposition: PreRevealDisposition
    public_findings: tuple[PublicLeakLocation, ...]
    private_evidence_hash: Sha256Hex

    @model_validator(mode="after")
    def disposition_matches_evidence(self) -> "PreRevealAuditReport":
        if self.stage is LockStage.D:
            raise ValueError("pre-reveal audit stage must be A, B, or C")
        if self.scanned_entry_count < 0:
            raise ValueError("scanned entry count cannot be negative")
        leak_rules = {
            "REGISTERED_SEMANTIC_TOKEN",
            "FORBIDDEN_PRE_D_TRUTH_FIELD",
        }
        has_leak = any(
            finding.rule_id in leak_rules
            for finding in self.public_findings
        )
        if (
            self.disposition
            is PreRevealDisposition.NO_REGISTERED_LEAKAGE_DETECTED
            and (
                self.scanned_entry_count == 0
                or self.public_findings
            )
        ):
            raise ValueError(
                "clean report requires nonempty scan and zero findings"
            )
        if (
            self.disposition
            is PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
            and not has_leak
        ):
            raise ValueError("invalidated report requires a registered leak")
        if (
            self.disposition
            is PreRevealDisposition.AUDIT_INCOMPLETE_FAIL_CLOSED
            and (has_leak or not self.public_findings)
        ):
            raise ValueError(
                "incomplete report requires non-leak failure findings"
            )
        return self


class HistoricalExposureRecord(FrozenContractModel):
    schema_id: Literal["d2t_rna.historical_exposure_record"] = (
        "d2t_rna.historical_exposure_record"
    )
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: RegisteredId
    display_name: StrictStr
    exposure_status: Literal[
        ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
    ]
    held_out_claim_allowed: Literal[False]
    prospective_claim_allowed: Literal[False]
    basis_contract_hash: Sha256Hex
    basis_section_id: RegisteredId


def _raw_sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _raw_sha256_text(value: str) -> str:
    return _raw_sha256_bytes(value.encode("utf-8"))


def _decode_unicode_escape(match: re.Match[str]) -> str:
    codepoint = next(group for group in match.groups() if group is not None)
    return chr(int(codepoint, 16))


def _normalize_for_detection(value: str) -> tuple[str, bool]:
    decoded = value
    converged = False
    for _ in range(12):
        changed = html.unescape(unquote(decoded))
        changed = _UNICODE_ESCAPE.sub(_decode_unicode_escape, changed)
        if changed == decoded:
            converged = True
            break
        decoded = changed

    decoded = unicodedata.normalize("NFKD", decoded).casefold()
    decoded = decoded.translate(_CONFUSABLE_ASCII)
    suspicious_control = not converged
    retained: list[str] = []
    for character in decoded:
        category = unicodedata.category(character)
        if category in {"Cf", "Cc", "Cs", "Co"}:
            suspicious_control = True
            continue
        if category.startswith("M"):
            continue
        retained.append(character)
    return "".join(retained), suspicious_control


def _bounded_obfuscated_pattern(token: str) -> re.Pattern[str]:
    separated = r"[^a-z0-9]*".join(
        re.escape(character) for character in token
    )
    return re.compile(rf"(?<![a-z0-9]){separated}(?![a-z0-9])")


_REGISTERED_PATTERNS = tuple(
    _bounded_obfuscated_pattern(token)
    for token in _REGISTERED_SEMANTIC_TOKENS
)
_FORBIDDEN_COMPACT = tuple(
    field.replace("_", "") for field in _FORBIDDEN_PRE_D_FIELDS
)


def _rule_for_text(value: str) -> tuple[str | None, bool]:
    normalized, suspicious_control = _normalize_for_detection(value)
    if any(pattern.search(normalized) for pattern in _REGISTERED_PATTERNS):
        return "REGISTERED_SEMANTIC_TOKEN", suspicious_control
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    if any(token in compact for token in _FORBIDDEN_COMPACT):
        return "FORBIDDEN_PRE_D_TRUTH_FIELD", suspicious_control
    return None, suspicious_control


def pre_d_public_text_rule(value: str) -> str | None:
    """Return a generic rule ID for an unsafe public pre-D string."""

    if type(value) is not str:
        raise TypeError("pre-D public text must be exactly str")
    rule_id, suspicious_control = _rule_for_text(value)
    if rule_id is not None:
        return rule_id
    if suspicious_control:
        return "AMBIGUOUS_UNICODE_CONTROL"
    return None


def _read_regular_file_once(
    path: Path,
    expected: os.stat_result,
) -> tuple[bytes | None, str, int, bool]:
    """Read one no-follow descriptor once; hash and parser share those bytes."""

    if not hasattr(os, "O_NOFOLLOW"):
        return None, _raw_sha256_bytes(b""), 0, False
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None, _raw_sha256_bytes(b""), 0, False

    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    size = 0
    stable = True
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or opened.st_nlink != 1
        ):
            stable = False
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
            if size <= MAX_PARSED_FILE_BYTES:
                chunks.append(chunk)
        after = os.fstat(descriptor)
        try:
            path_after = path.lstat()
        except OSError:
            stable = False
        else:
            stable = stable and (
                stat.S_ISREG(path_after.st_mode)
                and path_after.st_dev == opened.st_dev
                and path_after.st_ino == opened.st_ino
            )
        stable = stable and (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        stable = stable and size == after.st_size
    finally:
        os.close(descriptor)

    raw = b"".join(chunks) if size <= MAX_PARSED_FILE_BYTES else None
    return raw, hasher.hexdigest(), size, stable


def _json_metadata(value: object) -> tuple[MetadataField, ...]:
    fields: list[MetadataField] = []

    def visit(item: object, locator: str) -> None:
        if isinstance(item, dict):
            for index, (key, child) in enumerate(item.items()):
                child_locator = f"{locator}.object.{index}"
                fields.append(
                    MetadataField(
                        locator=child_locator,
                        key=key,
                        value=child if type(child) is str else "",
                    )
                )
                visit(child, child_locator)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{locator}.array.{index}")
        elif type(item) is str:
            fields.append(
                MetadataField(
                    locator=locator,
                    key="value",
                    value=item,
                )
            )

    visit(value, "json")
    return tuple(fields)


def _regular_file_entry(
    *,
    path: Path,
    relative_path: str,
    entry_index: int,
    expected_metadata: os.stat_result,
) -> PlanningPackageEntry:
    raw, content_hash, byte_size, stable_identity = _read_regular_file_once(
        path,
        expected_metadata,
    )
    if not stable_identity:
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="OPAQUE",
            media_type="application/octet-stream",
            parser_id="parser.concurrent_change_rejected.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=False,
        )
    if raw is None:
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="OPAQUE",
            media_type="application/octet-stream",
            parser_id="parser.size_limit.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=False,
        )
    if any(raw.startswith(magic) for magic in _ARCHIVE_MAGICS) or (
        len(raw) > 262 and raw[257:262] == b"ustar"
    ):
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="ARCHIVE",
            media_type="application/archive",
            parser_id="parser.archive_rejected.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=False,
        )

    suffix = path.suffix.casefold()
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="OPAQUE",
            media_type="application/octet-stream",
            parser_id="parser.invalid_utf8.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=False,
        )

    if suffix == ".json":
        try:
            validate_contract_json_syntax(text)
            loaded = json.loads(text)
        except (TypeError, ValueError):
            return PlanningPackageEntry(
                entry_index=entry_index,
                relative_path=relative_path,
                entry_kind="OPAQUE",
                media_type="application/json",
                parser_id="parser.json_invalid.v1",
                content_sha256=content_hash,
                byte_size=byte_size,
                complete_parse=False,
            )
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="REGULAR_FILE",
            media_type="application/json",
            parser_id="parser.json_duplicate_safe.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=True,
            metadata=_json_metadata(loaded),
        )

    media_and_parser = _TEXT_SUFFIXES.get(suffix)
    if media_and_parser is None:
        return PlanningPackageEntry(
            entry_index=entry_index,
            relative_path=relative_path,
            entry_kind="OPAQUE",
            media_type="text/unknown",
            parser_id="parser.unsupported_suffix.v1",
            content_sha256=content_hash,
            byte_size=byte_size,
            complete_parse=False,
        )
    media_type, parser_id = media_and_parser
    headers = tuple(
        HeaderField(
            locator=f"line.{line_index}",
            name="line",
            value=line,
        )
        for line_index, line in enumerate(text.splitlines())
        if line
    )
    return PlanningPackageEntry(
        entry_index=entry_index,
        relative_path=relative_path,
        entry_kind="REGULAR_FILE",
        media_type=media_type,
        parser_id=parser_id,
        content_sha256=content_hash,
        byte_size=byte_size,
        complete_parse=True,
        headers=headers,
    )


def _scan_directory(package_root: Path) -> tuple[PlanningPackageEntry, ...]:
    if package_root.is_symlink():
        raise ValueError("planning package root cannot be a symlink")
    if not package_root.is_dir():
        raise ValueError("planning package root must be an existing directory")

    inventory: list[tuple[str, Path, os.stat_result]] = []
    for current_root, directory_names, file_names in os.walk(
        package_root,
        topdown=True,
        followlinks=False,
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        retained_directories: list[str] = []
        for name in directory_names:
            candidate = current / name
            metadata = candidate.lstat()
            relative = candidate.relative_to(package_root).as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                inventory.append((relative, candidate, metadata))
            else:
                retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            candidate = current / name
            inventory.append(
                (
                    candidate.relative_to(package_root).as_posix(),
                    candidate,
                    candidate.lstat(),
                )
            )

    entries: list[PlanningPackageEntry] = []
    for entry_index, (relative, path, metadata) in enumerate(
        sorted(inventory, key=lambda item: item[0])
    ):
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1:
            content_hash = _raw_sha256_bytes(b"")
            byte_size = metadata.st_size
            entries.append(
                PlanningPackageEntry(
                    entry_index=entry_index,
                    relative_path=relative,
                    entry_kind="HARDLINK",
                    media_type="inode/hardlink",
                    parser_id="parser.hardlink_rejected.v1",
                    content_sha256=content_hash,
                    byte_size=byte_size,
                    complete_parse=False,
                )
            )
            continue
        if stat.S_ISREG(metadata.st_mode):
            entries.append(
                _regular_file_entry(
                    path=path,
                    relative_path=relative,
                    entry_index=entry_index,
                    expected_metadata=metadata,
                )
            )
            continue
        if stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(path).encode("utf-8", errors="strict")
            entries.append(
                PlanningPackageEntry(
                    entry_index=entry_index,
                    relative_path=relative,
                    entry_kind="SYMLINK",
                    media_type="inode/symlink",
                    parser_id="parser.symlink_rejected.v1",
                    content_sha256=_raw_sha256_bytes(target),
                    byte_size=len(target),
                    complete_parse=False,
                )
            )
            continue
        entries.append(
            PlanningPackageEntry(
                entry_index=entry_index,
                relative_path=relative,
                entry_kind="DEVICE",
                media_type="inode/special",
                parser_id="parser.special_rejected.v1",
                content_sha256=_raw_sha256_bytes(b""),
                byte_size=0,
                complete_parse=False,
            )
        )
    return tuple(entries)


def _finding(
    *,
    entry_index: int,
    relative_path: str,
    surface: LeakSurface,
    locator: str,
    rule_id: str,
) -> PublicLeakLocation:
    return PublicLeakLocation(
        entry_index=entry_index,
        path_hash=_raw_sha256_text(relative_path),
        surface=surface,
        locator_hash=_raw_sha256_text(locator),
        rule_id=rule_id,
    )


def _entry_structural_failure(entry: PlanningPackageEntry) -> str | None:
    path = entry.relative_path.replace("\\", "/")
    pure_path = PurePosixPath(path)
    if (
        not path
        or path.startswith("/")
        or any(part in {"", ".", ".."} for part in pure_path.parts)
        or "\x00" in path
    ):
        return "UNSAFE_PACKAGE_PATH"
    if entry.entry_kind != "REGULAR_FILE":
        return "UNSUPPORTED_ENTRY_KIND"
    if not entry.complete_parse:
        return "INCOMPLETE_PARSE"
    return None


def audit_planning_package(
    *,
    evaluation_id: str,
    stage: LockStage,
    package_root: str | Path,
) -> PreRevealAuditReport:
    """Enumerate, read, hash, parse, and audit one exact package directory."""

    if type(evaluation_id) is not str:
        raise TypeError("evaluation_id must be exactly str")
    if stage not in (LockStage.A, LockStage.B, LockStage.C):
        raise ValueError("planning-package audit stage must be A, B, or C")
    root = Path(package_root)
    entries = _scan_directory(root)

    source_package_hash = canonical_sha256(
        {
            "entries": entries,
            "schema_id": "d2t_rna.planning_package_content_manifest",
            "schema_version": "1.0",
        }
    )
    ruleset_hash = canonical_sha256(
        {
            "forbidden_pre_d_fields": _FORBIDDEN_PRE_D_FIELDS,
            "registered_semantic_tokens": _REGISTERED_SEMANTIC_TOKENS,
            "ruleset_id": SANITIZER_RULESET_ID,
        }
    )
    scanner_release_hash = canonical_sha256(
        {
            "content_binding": "sha256-and-byte-size",
            "enumeration": "owned-directory-walk-no-symlink-follow",
            "normalization": (
                "recursive-percent-html-jsonescape-nfkd-casefold-confusable-v1"
            ),
            "ruleset_hash": ruleset_hash,
            "scanner_id": "d2t_rna.planning_directory_scanner.v1",
        }
    )

    findings: list[PublicLeakLocation] = []
    private_findings: list[dict[str, object]] = []
    incomplete = False
    if not entries:
        incomplete = True
        findings.append(
            _finding(
                entry_index=0,
                relative_path="",
                surface=LeakSurface.PACKAGE_STRUCTURE,
                locator="package",
                rule_id="EMPTY_PACKAGE",
            )
        )

    evaluation_rule = pre_d_public_text_rule(evaluation_id)
    if evaluation_rule is not None:
        findings.append(
            _finding(
                entry_index=0,
                relative_path="",
                surface=LeakSurface.PUBLIC_LOCATOR,
                locator="evaluation_id",
                rule_id=evaluation_rule,
            )
        )
        incomplete = evaluation_rule == "AMBIGUOUS_UNICODE_CONTROL"

    normalized_paths: set[str] = set()
    for entry in entries:
        path_key = unicodedata.normalize(
            "NFKD", entry.relative_path.replace("\\", "/")
        ).casefold()
        if path_key in normalized_paths:
            incomplete = True
            findings.append(
                _finding(
                    entry_index=entry.entry_index,
                    relative_path=entry.relative_path,
                    surface=LeakSurface.PACKAGE_STRUCTURE,
                    locator=f"entry.{entry.entry_index}",
                    rule_id="NORMALIZED_PATH_COLLISION",
                )
            )
        normalized_paths.add(path_key)

        structural_rule = _entry_structural_failure(entry)
        if structural_rule is not None:
            incomplete = True
            findings.append(
                _finding(
                    entry_index=entry.entry_index,
                    relative_path=entry.relative_path,
                    surface=LeakSurface.PACKAGE_STRUCTURE,
                    locator=f"entry.{entry.entry_index}",
                    rule_id=structural_rule,
                )
            )

        surfaces: list[tuple[LeakSurface, str, str]] = [
            (
                LeakSurface.FILE_NAME,
                f"entry.{entry.entry_index}.path",
                entry.relative_path,
            )
        ]
        for header_index, header in enumerate(entry.headers):
            surfaces.extend(
                (
                    (
                        LeakSurface.PUBLIC_LOCATOR,
                        f"header.{header_index}.locator",
                        header.locator,
                    ),
                    (
                        LeakSurface.HEADER_NAME,
                        f"header.{header_index}.name",
                        header.name,
                    ),
                    (
                        LeakSurface.HEADER_VALUE,
                        f"header.{header_index}.value",
                        header.value,
                    ),
                )
            )
        for metadata_index, metadata in enumerate(entry.metadata):
            surfaces.extend(
                (
                    (
                        LeakSurface.PUBLIC_LOCATOR,
                        f"metadata.{metadata_index}.locator",
                        metadata.locator,
                    ),
                    (
                        LeakSurface.METADATA_KEY,
                        f"metadata.{metadata_index}.key",
                        metadata.key,
                    ),
                    (
                        LeakSurface.METADATA_VALUE,
                        f"metadata.{metadata_index}.value",
                        metadata.value,
                    ),
                )
            )

        for surface, locator, value in surfaces:
            rule_id, suspicious_control = _rule_for_text(value)
            if rule_id is not None:
                findings.append(
                    _finding(
                        entry_index=entry.entry_index,
                        relative_path=entry.relative_path,
                        surface=surface,
                        locator=locator,
                        rule_id=rule_id,
                    )
                )
                private_findings.append(
                    {
                        "content_sha256": entry.content_sha256,
                        "entry_index": entry.entry_index,
                        "locator_hash": _raw_sha256_text(locator),
                        "rule_id": rule_id,
                        "surface": surface.value,
                        "value_hash": _raw_sha256_text(value),
                    }
                )
            elif suspicious_control:
                incomplete = True
                findings.append(
                    _finding(
                        entry_index=entry.entry_index,
                        relative_path=entry.relative_path,
                        surface=surface,
                        locator=locator,
                        rule_id="AMBIGUOUS_UNICODE_CONTROL",
                    )
                )

    deduplicated = {
        canonical_sha256(finding): finding for finding in findings
    }
    ordered_findings = tuple(
        deduplicated[key] for key in sorted(deduplicated)
    )
    leak_rules = {
        "REGISTERED_SEMANTIC_TOKEN",
        "FORBIDDEN_PRE_D_TRUTH_FIELD",
    }
    if any(
        finding.rule_id in leak_rules for finding in ordered_findings
    ):
        disposition = (
            PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
        )
    elif incomplete:
        disposition = PreRevealDisposition.AUDIT_INCOMPLETE_FAIL_CLOSED
    else:
        disposition = (
            PreRevealDisposition.NO_REGISTERED_LEAKAGE_DETECTED
        )

    return PreRevealAuditReport(
        evaluation_id=evaluation_id,
        stage=stage,
        source_package_hash=source_package_hash,
        ruleset_hash=ruleset_hash,
        scanner_release_hash=scanner_release_hash,
        scanned_entry_count=len(entries),
        disposition=disposition,
        public_findings=ordered_findings,
        private_evidence_hash=canonical_sha256(
            {
                "domain": "d2t-rna:v1:sealed-sanitizer-evidence",
                "findings": tuple(private_findings),
                "source_package_hash": source_package_hash,
            }
        ),
    )


def assert_pre_reveal_audit_clean(report: PreRevealAuditReport) -> None:
    """Fail unless a strict, internally consistent report is narrowly clean."""

    if type(report) is not PreRevealAuditReport:
        raise TypeError("pre-reveal audit requires exactly PreRevealAuditReport")
    report = strict_revalidate_contract_model(report)
    if (
        report.disposition
        is not PreRevealDisposition.NO_REGISTERED_LEAKAGE_DETECTED
    ):
        raise ValueError("pre-reveal audit is invalidated or incomplete")


def sanitizer_report_hash(report: PreRevealAuditReport) -> str:
    """Hash clean or failed reports so failures can remain auditable."""

    if type(report) is not PreRevealAuditReport:
        raise TypeError("sanitizer report hash requires exact report type")
    return canonical_sha256(strict_revalidate_contract_model(report))


HISTORICAL_EXPOSURE_REGISTRY = (
    HistoricalExposureRecord(
        dataset_id="add",
        display_name="add",
        exposure_status=(
            ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
        ),
        held_out_claim_allowed=False,
        prospective_claim_allowed=False,
        basis_contract_hash=CONTRACT_SHA256,
        basis_section_id="task3.historical_exposure",
    ),
    HistoricalExposureRecord(
        dataset_id="rorc",
        display_name="RORC",
        exposure_status=(
            ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
        ),
        held_out_claim_allowed=False,
        prospective_claim_allowed=False,
        basis_contract_hash=CONTRACT_SHA256,
        basis_section_id="task3.historical_exposure",
    ),
    HistoricalExposureRecord(
        dataset_id="sam-iii",
        display_name="SAM-III",
        exposure_status=(
            ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
        ),
        held_out_claim_allowed=False,
        prospective_claim_allowed=False,
        basis_contract_hash=CONTRACT_SHA256,
        basis_section_id="task3.historical_exposure",
    ),
)


def validate_historical_exposure_registry(
    records: tuple[HistoricalExposureRecord, ...],
) -> tuple[HistoricalExposureRecord, ...]:
    """Require the exact three frozen retrospective-only records."""

    if type(records) is not tuple:
        raise TypeError("historical exposure registry must be a tuple")
    validated: list[HistoricalExposureRecord] = []
    for record in records:
        if type(record) is not HistoricalExposureRecord:
            raise TypeError(
                "historical exposure records require the exact registered type"
            )
        validated.append(strict_revalidate_contract_model(record))
    result = tuple(validated)
    if canonical_sha256(result) != canonical_sha256(
        HISTORICAL_EXPOSURE_REGISTRY
    ):
        raise ValueError(
            "historical exposure registry must equal the frozen exact records"
        )
    return result


validate_historical_exposure_registry(HISTORICAL_EXPOSURE_REGISTRY)
