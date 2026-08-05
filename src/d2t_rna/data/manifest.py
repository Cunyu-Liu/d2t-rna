"""Accession-first, fail-closed metadata manifests for the frozen data stage.

This module deliberately models metadata and hash-only commitments.  It has
no FASTQ reader, no outcome parser, and no native-label constructor.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from d2t_rna.contracts.base import (
    FrozenContractModel,
    canonical_json_bytes,
    canonical_sha256,
)
from d2t_rna.contracts.enums import ExposureStatus, TruthVisibility
from d2t_rna.contracts.primitives import (
    RegisteredId,
    RegistryRef,
    Sha256Hex,
)
from d2t_rna.contracts.truth import TruthAssetCommitment


CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)
SCHEMA_VERSION = "1.0"
RETRIEVAL_DATE = "2026-08-01"
REGISTERED_DATASET_IDS = ("add", "rorc", "sam-iii")


class AccessionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_RESOLVED = "NOT_RESOLVED"


class EvidenceRole(str, Enum):
    PUBLIC_PLANNING_METADATA = "PUBLIC_PLANNING_METADATA"
    SEALED_TRUTH_COMMITMENT = "SEALED_TRUTH_COMMITMENT"
    PRIVATE_PROVENANCE = "PRIVATE_PROVENANCE"
    SANITIZED_ACTION_INPUT = "SANITIZED_ACTION_INPUT"
    RORC_STRESS_ELIGIBILITY = "RORC_STRESS_ELIGIBILITY"


class SourceReference(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.source_reference"] = (
        "d2t_rna.data.source_reference"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    source_id: RegisteredId
    repository: RegisteredId
    accession: StrictStr | None
    locator: StrictStr
    retrieved_at: StrictStr = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    official: StrictBool
    metadata_scope: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def source_is_well_formed(self) -> "SourceReference":
        if not self.metadata_scope:
            raise ValueError("source metadata scope cannot be empty")
        if self.accession is None and self.official:
            raise ValueError("official source without accession is not resolved")
        return self


class MetadataFact(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.metadata_fact"] = (
        "d2t_rna.data.metadata_fact"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    field_path: RegisteredId
    value_status: Literal["REGISTERED", "NOT_AVAILABLE"]
    value: StrictStr
    source_ids: tuple[RegisteredId, ...]
    retrieved_at: StrictStr = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @model_validator(mode="after")
    def fact_has_provenance(self) -> "MetadataFact":
        if not self.source_ids:
            raise ValueError("every metadata fact needs source provenance")
        if self.value_status == "NOT_AVAILABLE" and self.value != "NOT_AVAILABLE":
            raise ValueError("unavailable metadata must use the registered sentinel")
        return self


class AccessionRecord(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.accession_record"] = (
        "d2t_rna.data.accession_record"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    repository: RegisteredId
    accession: StrictStr | None
    status: AccessionStatus
    source_id: RegisteredId

    @model_validator(mode="after")
    def status_matches_accession(self) -> "AccessionRecord":
        if (self.status is AccessionStatus.RESOLVED) != (self.accession is not None):
            raise ValueError("accession status and value disagree")
        return self


class ConstructIdentity(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.construct_identity"] = (
        "d2t_rna.data.construct_identity"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    construct_id: RegisteredId
    identity_status: Literal["HASH_ONLY", "NOT_AVAILABLE"]
    identity_hash: Sha256Hex
    sequence_payload_present: Literal[False] = False
    source_ids: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def construct_is_provenanced(self) -> "ConstructIdentity":
        if not self.source_ids:
            raise ValueError("construct identity needs source provenance")
        return self


class AssayRecord(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.assay_record"] = (
        "d2t_rna.data.assay_record"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    assay_id: RegisteredId
    modality_status: Literal["REGISTERED", "NOT_AVAILABLE"]
    modality: StrictStr
    condition_spec_hash: Sha256Hex
    outcome_payload_present: Literal[False] = False
    source_ids: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def assay_is_provenanced(self) -> "AssayRecord":
        if not self.source_ids:
            raise ValueError("assay record needs source provenance")
        if self.modality_status == "NOT_AVAILABLE" and self.modality != "NOT_AVAILABLE":
            raise ValueError("unavailable assay modality must use the sentinel")
        return self


class ReplicateRecord(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.replicate_record"] = (
        "d2t_rna.data.replicate_record"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    replicate_id: RegisteredId
    replicate_status: Literal["REGISTERED", "NOT_AVAILABLE"]
    replicate_count: StrictInt | None
    dependency_unit_level: RegisteredId
    source_ids: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def replicate_is_provenanced(self) -> "ReplicateRecord":
        if not self.source_ids:
            raise ValueError("replicate record needs source provenance")
        if self.replicate_status == "NOT_AVAILABLE" and self.replicate_count is not None:
            raise ValueError("unavailable replicate count must be null")
        if self.replicate_count is not None and self.replicate_count < 0:
            raise ValueError("replicate count cannot be negative")
        return self


class DependencyEdge(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.dependency_edge"] = (
        "d2t_rna.data.dependency_edge"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    left_id: RegisteredId
    right_id: RegisteredId
    dependency_unit_level: RegisteredId
    relation_status: Literal["REGISTERED", "UNKNOWN"]
    source_ids: tuple[RegisteredId, ...]

    @model_validator(mode="after")
    def edge_is_provenanced(self) -> "DependencyEdge":
        if not self.source_ids:
            raise ValueError("dependency edge needs source provenance")
        return self


class DependencyGraph(FrozenContractModel):
    schema_id: Literal["d2t_rna.data.dependency_graph"] = (
        "d2t_rna.data.dependency_graph"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    nodes: tuple[RegisteredId, ...]
    edges: tuple[DependencyEdge, ...]
    graph_status: Literal["REGISTERED", "PARTIAL_UNKNOWN"]

    @model_validator(mode="after")
    def graph_is_canonical(self) -> "DependencyGraph":
        if not self.nodes:
            raise ValueError("dependency graph needs at least one node")
        if self.nodes != tuple(sorted(set(self.nodes))):
            raise ValueError("dependency graph nodes must be unique and sorted")
        node_set = set(self.nodes)
        if any(edge.left_id not in node_set or edge.right_id not in node_set for edge in self.edges):
            raise ValueError("dependency edge references an unknown node")
        return self


class PublicPlanningStub(FrozenContractModel):
    schema_id: Literal["d2t_rna.public_planning_stub"] = (
        "d2t_rna.public_planning_stub"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_hash: Literal[CONTRACT_SHA256] = CONTRACT_SHA256
    dataset_id: Literal["add", "sam-iii", "rorc"]
    display_name: StrictStr
    retrieved_at: StrictStr = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    accession_status: AccessionStatus
    accessions: tuple[AccessionRecord, ...]
    sources: tuple[SourceReference, ...]
    facts: tuple[MetadataFact, ...]
    constructs: tuple[ConstructIdentity, ...]
    assays: tuple[AssayRecord, ...]
    replicates: tuple[ReplicateRecord, ...]
    dependency_graph: DependencyGraph
    exposure_status: Literal[
        ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
    ]
    evidence_role: Literal[EvidenceRole.PUBLIC_PLANNING_METADATA]
    official_metadata_only: Literal[True] = True
    fastq_outcomes_downloaded: Literal[False] = False
    native_truth_label_generated: Literal[False] = False

    @model_validator(mode="after")
    def source_and_accession_sets_are_consistent(self) -> "PublicPlanningStub":
        source_ids = {source.source_id for source in self.sources}
        if any(source_id not in source_ids for record in self.accessions for source_id in (record.source_id,)):
            raise ValueError("accession references an unknown source")
        if self.accession_status is AccessionStatus.RESOLVED and not any(
            record.status is AccessionStatus.RESOLVED for record in self.accessions
        ):
            raise ValueError("resolved dataset requires a resolved accession")
        if self.accession_status is AccessionStatus.NOT_RESOLVED and any(
            record.status is AccessionStatus.RESOLVED for record in self.accessions
        ):
            raise ValueError("unresolved dataset cannot contain a resolved accession")
        return self


class SealedTruthCommitment(FrozenContractModel):
    schema_id: Literal["d2t_rna.sealed_truth_commitment"] = (
        "d2t_rna.sealed_truth_commitment"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_hash: Literal[CONTRACT_SHA256] = CONTRACT_SHA256
    dataset_id: Literal["add", "sam-iii", "rorc"]
    planning_stub_hash: Sha256Hex
    commitments: tuple[TruthAssetCommitment, ...]
    commitment_set_hash: Sha256Hex
    evidence_role: Literal[EvidenceRole.SEALED_TRUTH_COMMITMENT]
    visibility: Literal[TruthVisibility.HASH_ONLY]
    truth_payload_status: Literal["SEALED_NOT_REVEALED"]
    numeric_truth_revealed: Literal[False] = False
    semantic_truth_revealed: Literal[False] = False
    native_truth_label_generated: Literal[False] = False

    @model_validator(mode="after")
    def commitments_are_hash_only(self) -> "SealedTruthCommitment":
        if not self.commitments:
            raise ValueError("sealed truth commitment set cannot be empty")
        if self.commitment_set_hash != canonical_sha256(self.commitments):
            raise ValueError("sealed truth commitment set hash is stale")
        if any(commitment.visibility is not TruthVisibility.HASH_ONLY for commitment in self.commitments):
            raise ValueError("sealed truth commitment contains non-hash-only data")
        return self


class PrivateProvenanceManifest(FrozenContractModel):
    schema_id: Literal["d2t_rna.private_provenance_manifest"] = (
        "d2t_rna.private_provenance_manifest"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_hash: Literal[CONTRACT_SHA256] = CONTRACT_SHA256
    dataset_id: Literal["add", "sam-iii", "rorc"]
    planning_stub_hash: Sha256Hex
    sealed_commitment_hash: Sha256Hex
    source_ids: tuple[RegisteredId, ...]
    artifact_locator: StrictStr
    evidence_role: Literal[EvidenceRole.PRIVATE_PROVENANCE]
    raw_fastq_downloaded: Literal[False] = False
    outcome_interpretation_performed: Literal[False] = False
    field_provenance_complete: Literal[True] = True
    native_truth_label_generated: Literal[False] = False

    @model_validator(mode="after")
    def locator_is_project_scoped(self) -> "PrivateProvenanceManifest":
        if not self.artifact_locator.startswith("/mnt/cunyuliu/d2t-rna/"):
            raise ValueError("private provenance must remain under the artifact root")
        if not self.source_ids:
            raise ValueError("private provenance needs source IDs")
        return self


class SanitizedActionPackage(FrozenContractModel):
    schema_id: Literal["d2t_rna.sanitized_action_package"] = (
        "d2t_rna.sanitized_action_package"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_hash: Literal[CONTRACT_SHA256] = CONTRACT_SHA256
    dataset_id: Literal["add", "sam-iii", "rorc"]
    planning_stub_hash: Sha256Hex
    sealed_commitment_hash: Sha256Hex
    evidence_role: Literal[EvidenceRole.SANITIZED_ACTION_INPUT]
    allowed_actions: tuple[Literal["READ_OFFICIAL_METADATA", "BUILD_PLAN_ONLY"], ...]
    sequence_payload_present: Literal[False] = False
    outcome_payload_present: Literal[False] = False
    native_truth_label_generated: Literal[False] = False

    @model_validator(mode="after")
    def action_package_is_nonempty(self) -> "SanitizedActionPackage":
        if not self.allowed_actions:
            raise ValueError("sanitized action package cannot be empty")
        return self


class RorcStressEligibilityRecord(FrozenContractModel):
    schema_id: Literal["d2t_rna.rorc_stress_eligibility_record"] = (
        "d2t_rna.rorc_stress_eligibility_record"
    )
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_hash: Literal[CONTRACT_SHA256] = CONTRACT_SHA256
    dataset_id: Literal["rorc"] = "rorc"
    status: Literal["INELIGIBLE_UNRESOLVED_METADATA"]
    reason_code: Literal["NO_PRIMARY_OFFICIAL_ACCESSION_RESOLVED"]
    evidence_role: Literal[EvidenceRole.RORC_STRESS_ELIGIBILITY]
    stress_execution_allowed: Literal[False] = False
    held_out_claim_allowed: Literal[False] = False
    native_truth_label_generated: Literal[False] = False


ManifestModel = (
    PublicPlanningStub
    | SealedTruthCommitment
    | PrivateProvenanceManifest
    | SanitizedActionPackage
    | RorcStressEligibilityRecord
)


def _hash(value: object) -> str:
    return canonical_sha256(value)


def _source_catalog(dataset_id: str) -> tuple[SourceReference, ...]:
    if dataset_id == "add":
        return (
            SourceReference(
                source_id="rmdb.addapo.dcp.0000",
                repository="RMDB",
                accession="ADDAPO_DCP_0000",
                locator="https://rmdb.stanford.edu/detail/ADDAPO_DCP_0000/",
                retrieved_at=RETRIEVAL_DATE,
                official=True,
                metadata_scope=("accession", "construct", "assay"),
            ),
        )
    if dataset_id == "sam-iii":
        return (
            SourceReference(
                source_id="geo.gse278422",
                repository="NCBI_GEO",
                accession="GSE278422",
                locator="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE278422",
                retrieved_at=RETRIEVAL_DATE,
                official=True,
                metadata_scope=("accession", "assay", "replicate"),
            ),
            SourceReference(
                source_id="pdb.6c27",
                repository="RCSB_PDB",
                accession="6C27",
                locator="https://www.rcsb.org/structure/6C27",
                retrieved_at=RETRIEVAL_DATE,
                official=True,
                metadata_scope=("construct", "condition"),
            ),
            SourceReference(
                source_id="rfam.rf01767",
                repository="RFAM",
                accession="RF01767",
                locator="https://rfam.org/family/RF01767",
                retrieved_at=RETRIEVAL_DATE,
                official=True,
                metadata_scope=("construct", "family"),
            ),
        )
    if dataset_id == "rorc":
        return (
            SourceReference(
                source_id="task6.rorc.audit",
                repository="D2T-RNA-INTERNAL-AUDIT",
                accession=None,
                locator="/home/cunyuliu/d2t-rna/docs/audit/task-3-truth-locks.md",
                retrieved_at=RETRIEVAL_DATE,
                official=False,
                metadata_scope=("accession_resolution_status", "exposure"),
            ),
        )
    raise ValueError(f"unknown registered dataset: {dataset_id}")


def _dataset_label(dataset_id: str) -> str:
    return {"add": "ADD", "sam-iii": "SAM-III", "rorc": "RORC"}[dataset_id]


def _source_ids(sources: tuple[SourceReference, ...]) -> tuple[str, ...]:
    return tuple(sorted(source.source_id for source in sources))


def _fact(
    field_path: str,
    value_status: Literal["REGISTERED", "NOT_AVAILABLE"],
    value: str,
    source_ids: tuple[str, ...],
) -> MetadataFact:
    return MetadataFact(
        field_path=field_path,
        value_status=value_status,
        value=value,
        source_ids=source_ids,
        retrieved_at=RETRIEVAL_DATE,
    )


def _build_public(dataset_id: str) -> PublicPlanningStub:
    sources = _source_catalog(dataset_id)
    source_ids = _source_ids(sources)
    resolved = dataset_id in {"add", "sam-iii"}
    accessions = tuple(
        AccessionRecord(
            repository=source.repository,
            accession=source.accession,
            status=(AccessionStatus.RESOLVED if source.accession else AccessionStatus.NOT_RESOLVED),
            source_id=source.source_id,
        )
        for source in sources
    )
    facts = (
        _fact("accession", "REGISTERED" if resolved else "NOT_AVAILABLE", "REGISTERED" if resolved else "NOT_AVAILABLE", source_ids),
        _fact("construct_identity", "REGISTERED" if dataset_id != "rorc" else "NOT_AVAILABLE", "HASH_ONLY" if dataset_id != "rorc" else "NOT_AVAILABLE", source_ids),
        _fact("assay", "REGISTERED" if dataset_id != "rorc" else "NOT_AVAILABLE", "STRUCTURE_PROBING_OR_STRUCTURE_RECORD" if dataset_id != "rorc" else "NOT_AVAILABLE", source_ids),
        _fact("replicate", "REGISTERED" if dataset_id == "sam-iii" else "NOT_AVAILABLE", "REGISTERED" if dataset_id == "sam-iii" else "NOT_AVAILABLE", source_ids),
        _fact("dependency_graph", "REGISTERED" if dataset_id == "sam-iii" else "NOT_AVAILABLE", "REGISTERED" if dataset_id == "sam-iii" else "NOT_AVAILABLE", source_ids),
        _fact("exposure_status", "REGISTERED", ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE.value, source_ids),
        _fact("evidence_role", "REGISTERED", EvidenceRole.PUBLIC_PLANNING_METADATA.value, source_ids),
    )
    construct_source_ids = source_ids
    construct = ConstructIdentity(
        construct_id=f"{dataset_id}.construct.0001",
        identity_status="HASH_ONLY" if dataset_id != "rorc" else "NOT_AVAILABLE",
        identity_hash=_hash({"dataset_id": dataset_id, "construct": "NOT_REVEALED"}),
        source_ids=construct_source_ids,
    )
    assay = AssayRecord(
        assay_id=f"{dataset_id}.assay.0001",
        modality_status="REGISTERED" if dataset_id != "rorc" else "NOT_AVAILABLE",
        modality="STRUCTURE_PROBING_OR_STRUCTURE_RECORD" if dataset_id != "rorc" else "NOT_AVAILABLE",
        condition_spec_hash=_hash({"dataset_id": dataset_id, "condition": "NOT_REVEALED"}),
        source_ids=source_ids,
    )
    replicate = ReplicateRecord(
        replicate_id=f"{dataset_id}.replicate.0001",
        replicate_status="REGISTERED" if dataset_id == "sam-iii" else "NOT_AVAILABLE",
        replicate_count=None,
        dependency_unit_level="UNKNOWN",
        source_ids=source_ids,
    )
    graph = DependencyGraph(
        nodes=(assay.assay_id, construct.construct_id, replicate.replicate_id),
        edges=(
            DependencyEdge(
                left_id=assay.assay_id,
                right_id=replicate.replicate_id,
                dependency_unit_level="UNKNOWN",
                relation_status="UNKNOWN" if dataset_id != "sam-iii" else "REGISTERED",
                source_ids=source_ids,
            ),
        ),
        graph_status="PARTIAL_UNKNOWN" if dataset_id != "sam-iii" else "REGISTERED",
    )
    return PublicPlanningStub(
        dataset_id=dataset_id,  # type: ignore[arg-type]
        display_name=_dataset_label(dataset_id),
        retrieved_at=RETRIEVAL_DATE,
        accession_status=AccessionStatus.RESOLVED if resolved else AccessionStatus.NOT_RESOLVED,
        accessions=accessions,
        sources=sources,
        facts=facts,
        constructs=(construct,),
        assays=(assay,),
        replicates=(replicate,),
        dependency_graph=graph,
        exposure_status=ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE,
        evidence_role=EvidenceRole.PUBLIC_PLANNING_METADATA,
    )


def _build_sealed(dataset_id: str, public: PublicPlanningStub) -> SealedTruthCommitment:
    source_ids = _source_ids(public.sources)
    official_hash = _hash(public.sources)
    asset_id = f"{dataset_id}.truth.0001"
    commitment = TruthAssetCommitment(
        truth_asset_id=asset_id,
        asset_hash=_hash({"asset_id": asset_id, "status": "SEALED_NOT_REVEALED", "official_metadata_hash": official_hash}),
        sequence_identity_hash=_hash({"asset_id": asset_id, "sequence": "NOT_REVEALED"}),
        condition_spec_hash=_hash({"asset_id": asset_id, "condition": "NOT_REVEALED"}),
        measurement_modality=RegistryRef(
            registry_id="metadata-only",
            registry_hash=_hash({"dataset_id": dataset_id, "modality": "metadata-only"}),
        ),
        eligibility_status_without_direction=RegistryRef(
            registry_id="eligibility-unresolved",
            registry_hash=_hash({"dataset_id": dataset_id, "eligibility": "WITHOUT_DIRECTION"}),
        ),
        numeric_payload_hash=_hash({"asset_id": asset_id, "numeric": "SEALED_NOT_REVEALED"}),
        semantic_payload_hash=_hash({"asset_id": asset_id, "semantic": "SEALED_NOT_REVEALED"}),
        visibility=TruthVisibility.HASH_ONLY,
    )
    return SealedTruthCommitment(
        dataset_id=dataset_id,  # type: ignore[arg-type]
        planning_stub_hash=canonical_sha256(public),
        commitments=(commitment,),
        commitment_set_hash=canonical_sha256((commitment,)),
        evidence_role=EvidenceRole.SEALED_TRUTH_COMMITMENT,
        visibility=TruthVisibility.HASH_ONLY,
        truth_payload_status="SEALED_NOT_REVEALED",
    )


def build_registered_bundle(dataset_id: str) -> tuple[ManifestModel, ...]:
    """Build one deterministic, metadata-only registered manifest bundle."""

    if dataset_id not in REGISTERED_DATASET_IDS:
        raise ValueError(f"unknown registered dataset: {dataset_id}")
    public = _build_public(dataset_id)
    sealed = _build_sealed(dataset_id, public)
    private = PrivateProvenanceManifest(
        dataset_id=dataset_id,  # type: ignore[arg-type]
        planning_stub_hash=canonical_sha256(public),
        sealed_commitment_hash=canonical_sha256(sealed),
        source_ids=_source_ids(public.sources),
        artifact_locator=f"/mnt/cunyuliu/d2t-rna/data/task6/{dataset_id}",
        evidence_role=EvidenceRole.PRIVATE_PROVENANCE,
    )
    action = SanitizedActionPackage(
        dataset_id=dataset_id,  # type: ignore[arg-type]
        planning_stub_hash=canonical_sha256(public),
        sealed_commitment_hash=canonical_sha256(sealed),
        evidence_role=EvidenceRole.SANITIZED_ACTION_INPUT,
        allowed_actions=("BUILD_PLAN_ONLY", "READ_OFFICIAL_METADATA"),
    )
    if dataset_id == "rorc":
        return (
            public,
            sealed,
            private,
            action,
            RorcStressEligibilityRecord(
                status="INELIGIBLE_UNRESOLVED_METADATA",
                reason_code="NO_PRIMARY_OFFICIAL_ACCESSION_RESOLVED",
                evidence_role=EvidenceRole.RORC_STRESS_ELIGIBILITY,
            ),
        )
    return public, sealed, private, action


def serialize_bundle(bundle: tuple[ManifestModel, ...]) -> dict[str, str]:
    """Serialize models using the project canonical JSON representation."""

    result: dict[str, str] = {}
    for model in bundle:
        name = {
            "d2t_rna.public_planning_stub": "public_planning_stub.json",
            "d2t_rna.sealed_truth_commitment": "sealed_truth_commitment.json",
            "d2t_rna.private_provenance_manifest": "private_provenance_manifest.json",
            "d2t_rna.sanitized_action_package": "sanitized_action_package.json",
            "d2t_rna.rorc_stress_eligibility_record": "stress_eligibility_record.json",
        }[model.schema_id]
        result[name] = canonical_json_bytes(model).decode("utf-8") + "\n"
    return result


def write_registered_bundle(output_root: Path) -> None:
    """Write all registered bundles under an existing or new manifest root."""

    for dataset_id in REGISTERED_DATASET_IDS:
        dataset_root = output_root / dataset_id.replace("-", "_")
        dataset_root.mkdir(parents=True, exist_ok=True)
        for name, payload in serialize_bundle(build_registered_bundle(dataset_id)).items():
            path = dataset_root / name
            if path.exists() or path.is_symlink():
                raise FileExistsError(f"manifest output already exists: {path}")
            path.write_text(payload, encoding="utf-8")
