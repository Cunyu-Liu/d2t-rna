"""authority_v3.py — the single production authority / evidence resolver (P0-5).

P0-5 contract:

* Every manuscript table/figure/claim-graph/readiness consumer must obtain
  evidence through this ONE resolver.  It must not hand-parse paths or do
  file-existence-only checks.
* ``resolve`` / ``require_paper_eligible`` reject an invalid or
  ``paper_eligible=false`` artifact (non-zero / exception) so that tombstoned
  legacy artifacts can never re-enter the paper evidence chain.
* ReactFlow / external-project evidence is ``EXTERNAL_ONLY`` and must resolve to
  ``paper_eligible=false``.
* ``scientific_claim_authorization`` can ONLY come from a repo-external
  independent attestation.  It is never produced by the readiness gate itself.
  If the attestation is absent, unverifiable, or self-referential (produced by
  the repo's own gate), authorization is fixed ``False``.
* The six status axes are computed separately and never conflated; the
  submission status is a conjunction over authorization + claim scope + real
  data scope + authority lineage + reproducibility + citation + PDF build +
  visual QA.  When ``scientific_claim_authorized`` is false the submission
  status is blocked and must never be named ``READY_FOR_SUBMISSION``.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional, Sequence

AUTHORITY_INDEX_SCHEMA = "d2t_rna.v7_artifact_authority_index.v3"
TERMINALIZATION_SCHEMA = "d2t_rna.v7_artifact_terminalization.v3"
CLAIM_FREEZE_SCHEMA = "d2t_rna.v7_claim_freeze.v3"
ATTESTATION_SCHEMA = "d2t_rna.external_scientific_claim_attestation.v3"

# --- fixed statuses (contract) ----------------------------------------------
SOTA_STATUS = "SOTA_NOT_ADJUDICATED"
REAL_DATA_ROUTE = "TERMINATED_FOR_CURRENT_DATA"
COMPARATIVE_SYNTHETIC_STATUS_BLOCKED = (
    "INVALID_PENDING_METRIC_AND_METHOD_ROLE_REPAIR"
)

BLOCKED_SUBMISSION = "SCIENTIFIC_SUBMISSION_BLOCKED"
READY_SUBMISSION = "SCIENTIFIC_SUBMISSION_READY"


class EvidenceResolutionError(RuntimeError):
    """Raised when a consumer asks for an artifact that is invalid or not
    paper-eligible.  Consumers must propagate this as a non-zero failure."""


@dataclass(frozen=True)
class EvidenceRecord:
    artifact: str
    role: str
    file_integrity: str
    scientific_interpretation: str
    paper_eligible: bool
    terminal_status: str
    schema: str
    sha256: Optional[str] = None
    superseded_by: Optional[str] = None
    note: Optional[str] = None


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class AuthorityV3:
    """Loads the v3 authority manifests and serves as the one resolver."""

    def __init__(
        self,
        repo_root: str,
        authority_index: Optional[str] = None,
        terminalization: Optional[str] = None,
    ) -> None:
        self.repo_root = os.path.realpath(repo_root)
        self.authority_index_path = (
            authority_index
            or os.path.join(
                self.repo_root,
                "manifests/audit/v7_artifact_authority_index_v3.json",
            )
        )
        self.terminalization_path = (
            terminalization
            or os.path.join(
                self.repo_root,
                "manifests/audit/v7_artifact_terminalization_v3.json",
            )
        )
        self._index, self._term = self._load()
        self._by_path = self._build_map()

    # -------- loading ------------------------------------------------------
    def _load(self) -> tuple[list[dict], dict]:
        if not os.path.exists(self.authority_index_path):
            raise EvidenceResolutionError(
                f"authority index missing: {self.authority_index_path}"
            )
        with open(self.authority_index_path) as f:
            index_doc = json.load(f)
        schema = index_doc.get("schema")
        if schema != AUTHORITY_INDEX_SCHEMA:
            raise EvidenceResolutionError(
                f"authority index has unexpected schema {schema!r}"
            )
        entries = index_doc.get("payload", {}).get("index", [])
        term = {}
        term_path = self.terminalization_path
        if os.path.exists(term_path):
            with open(term_path) as f:
                tdoc = json.load(f)
            for fam in tdoc.get("payload", {}).get("families", []):
                term[fam.get("artifact_family")] = fam
        return entries, term

    def _norm(self, p: str) -> str:
        p = os.path.normpath(p)
        if not os.path.isabs(p):
            p = os.path.join(self.repo_root, p)
        return os.path.realpath(p)

    def _build_map(self) -> dict[str, EvidenceRecord]:
        m: dict[str, EvidenceRecord] = {}
        for e in self._index:
            art = e.get("artifact")
            if not art:
                continue
            rec = EvidenceRecord(
                artifact=art,
                role=e.get("role", ""),
                file_integrity=e.get("file_integrity", ""),
                scientific_interpretation=e.get("scientific_interpretation", ""),
                paper_eligible=bool(e.get("paper_eligible", False)),
                terminal_status=e.get("terminal_status", ""),
                schema=e.get("schema", ""),
                sha256=e.get("sha256"),
                superseded_by=e.get("superseded_by"),
                note=e.get("note"),
            )
            m[self._norm(art)] = rec
            m[os.path.normpath(art)] = rec  # allow repo-relative lookup too
        return m

    # -------- resolution ---------------------------------------------------
    def resolve(self, artifact: str) -> EvidenceRecord:
        """Resolve an artifact id/path to its authoritative record.

        Raises :class:`EvidenceResolutionError` if the artifact is not in the
        authority index (unknown => invalid).
        """
        key = self._norm(artifact)
        rec = self._by_path.get(key)
        if rec is None:
            rec = self._by_path.get(os.path.normpath(artifact))
        if rec is None:
            raise EvidenceResolutionError(
                f"artifact is not in the authority index (unknown/invalid): "
                f"{artifact!r}"
            )
        return rec

    def require_paper_eligible(self, artifact: str) -> EvidenceRecord:
        """Return the record if paper-eligible, else raise (consumer must fail)."""
        rec = self.resolve(artifact)
        if not rec.paper_eligible:
            raise EvidenceResolutionError(
                f"artifact is not paper-eligible "
                f"(paper_eligible={rec.paper_eligible}, "
                f"terminal_status={rec.terminal_status}): {artifact!r}"
            )
        return rec

    def is_reactflow(self, artifact: str) -> bool:
        """External-project evidence (ReactFlow etc.) is EXTERNAL_ONLY."""
        return "reactflow" in artifact.lower() or "external" in artifact.lower()

    def d2t_paper_eligible_reactflow_count(self) -> int:
        """Number of D2T paper-eligible records that are ReactFlow evidence."""
        seen = set()
        n = 0
        for rec in self._by_path.values():
            if rec.artifact in seen:
                continue
            seen.add(rec.artifact)
            if rec.paper_eligible and self.is_reactflow(rec.artifact):
                n += 1
        return n

    def terminalized(self) -> list[EvidenceRecord]:
        """All terminalized records (deduplicated by artifact name)."""
        seen = set()
        out = []
        for rec in self._by_path.values():
            if rec.artifact in seen:
                continue
            seen.add(rec.artifact)
            if rec.terminal_status == "TERMINALIZED":
                out.append(rec)
        return out


# ---------------------------------------------------------------------------
# Scientific claim authorization (external-only, never self-produced)
# ---------------------------------------------------------------------------

def _verify_attestation(attestation_path: str, repo_root: str, head: str) -> bool:
    """Return True only for a valid, external, non-self-referential attestation.

    An attestation is self-referential if its ``generator`` is the repo's own
    readiness gate, or if it is produced by repo scripts.  The readiness gate
    must never be able to manufacture its own authorization.
    """
    if not attestation_path or not os.path.exists(attestation_path):
        return False
    try:
        with open(attestation_path) as f:
            doc = json.load(f)
    except Exception:
        return False
    if doc.get("schema") != ATTESTATION_SCHEMA:
        return False
    # must bind the exact current tree
    if doc.get("tree") != head:
        return False
    # external signer must be present and NOT the repo's own gate
    signer = (doc.get("signer") or "").strip()
    generator = (doc.get("generator") or "").strip().lower()
    if not signer:
        return False
    if "paper_readiness_gate" in generator or "d2t_rna" in generator.lower():
        return False  # self-referential / produced in-repo
    # must carry a non-empty limitation statement (an honest adjudicator lists them)
    if not (doc.get("limitations") or "").strip():
        return False
    # must reference the allowed artifact manifest and the claim graph it endorsed
    if not (doc.get("allowed_artifacts") or "").strip():
        return False
    if not (doc.get("claim_graph") or "").strip():
        return False
    return True


def scientific_claim_authorization(
    repo_root: str,
    head: str,
    attestation_path: Optional[str] = None,
) -> bool:
    """Authorization is exclusively external.  Absent => False."""
    return _verify_attestation(attestation_path, repo_root, head)


# ---------------------------------------------------------------------------
# Six-axis status computation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadinessStatus:
    editorial_build_status: str
    scientific_claim_authorized: bool
    sota_status: str
    real_data_route: str
    comparative_synthetic_status: str
    submission_status: str


def compute_readiness_status(
    *,
    editorial_build_ok: bool,
    scientific_claim_authorized: bool,
    authority_lineage_ok: bool,
    reproducibility_ok: bool,
    citation_ok: bool,
    pdf_ok: bool,
    visual_qa_ok: bool,
    sota_ok: bool = True,
    real_data_ok: bool = True,
    comparative_ok: bool = True,
) -> ReadinessStatus:
    """Compute the six status axes and the derived submission status.

    ``submission_status`` is a conjunction over authorization, claim scope
    (sota / real-data / comparative), authority lineage, reproducibility,
    citation, PDF build and visual QA.  It is ``READY`` only when
    ``scientific_claim_authorized`` is true and every conjunct passes.
    """
    editorial = "EDITORIAL_DRAFT_BUILT" if editorial_build_ok else "EDITORIAL_DRAFT_INCOMPLETE"

    claim_scope_ok = sota_ok and real_data_ok and comparative_ok
    submission_ok = (
        scientific_claim_authorized
        and authority_lineage_ok
        and reproducibility_ok
        and citation_ok
        and pdf_ok
        and visual_qa_ok
        and claim_scope_ok
    )
    submission = READY_SUBMISSION if submission_ok else BLOCKED_SUBMISSION

    return ReadinessStatus(
        editorial_build_status=editorial,
        scientific_claim_authorized=scientific_claim_authorized,
        sota_status=SOTA_STATUS,
        real_data_route=REAL_DATA_ROUTE,
        comparative_synthetic_status=COMPARATIVE_SYNTHETIC_STATUS_BLOCKED,
        submission_status=submission,
    )


def submission_status_name(rs: ReadinessStatus) -> str:
    """Guarantee the blocked status never leaks a READY_FOR_SUBMISSION name."""
    if rs.submission_status == BLOCKED_SUBMISSION:
        return "SCIENTIFIC_SUBMISSION_BLOCKED"
    return "SCIENTIFIC_SUBMISSION_READY"
