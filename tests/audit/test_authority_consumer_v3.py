"""P0-5: the single production authority resolver (AuthorityV3) consumer tests.

Verifies the resolver is the one source of evidence truth: unknown/invalid and
``paper_eligible=false`` artifacts raise, ReactFlow is EXTERNAL_ONLY, terminalization
is honored, and scientific-claim authorization can only come from an external
(non-self-referential) attestation.
"""
import json
import os

import pytest

from d2t_rna.audit.authority_v3 import (
    ATTESTATION_SCHEMA,
    AuthorityV3,
    EvidenceResolutionError,
    compute_readiness_status,
    scientific_claim_authorization,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))


INDEX = {
    "schema": "d2t_rna.v7_artifact_authority_index.v3",
    "payload": {"index": [
        {"artifact": "manifests/m0/m0_v7_activation.json", "role": "activation",
         "file_integrity": "ok", "scientific_interpretation": "ok",
         "paper_eligible": True, "terminal_status": "CURRENT_VALID",
         "schema": "d2t_rna.m0_activation.v7"},
        {"artifact": "manifests/t2/t2_2_acceptance.json", "role": "certificate",
         "file_integrity": "ok", "scientific_interpretation": "ok",
         "paper_eligible": True, "terminal_status": "CURRENT_VALID",
         "schema": "d2t_rna.t2_2_acceptance"},
        {"artifact": "manifests/phase5/legacy_phase5.json", "role": "legacy",
         "file_integrity": "ok", "scientific_interpretation": "withdrawn",
         "paper_eligible": False, "terminal_status": "TERMINALIZED",
         "schema": "d2t_rna.legacy_phase5"},
        {"artifact": "manifests/reactflow_adapter.json", "role": "external",
         "file_integrity": "ok", "scientific_interpretation": "external",
         "paper_eligible": False, "terminal_status": "EXTERNAL_ONLY",
         "schema": "d2t_rna.reactflow"},
    ]},
}

TERMINALIZATION = {
    "schema": "d2t_rna.v7_artifact_terminalization.v3",
    "payload": {"families": [
        {"artifact_family": "phase5", "status": "TERMINALIZED"},
    ]},
}


@pytest.fixture()
def repo(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(os.path.join(repo, "manifests", "audit"), exist_ok=True)
    with open(os.path.join(repo, "manifests", "audit",
                          "v7_artifact_authority_index_v3.json"), "w") as f:
        json.dump(INDEX, f)
    with open(os.path.join(repo, "manifests", "audit",
                          "v7_artifact_terminalization_v3.json"), "w") as f:
        json.dump(TERMINALIZATION, f)
    return repo


def test_resolve_known_artifact(repo):
    a = AuthorityV3(repo)
    rec = a.resolve("manifests/m0/m0_v7_activation.json")
    assert rec.paper_eligible is True


def test_resolve_unknown_artifact_raises(repo):
    a = AuthorityV3(repo)
    with pytest.raises(EvidenceResolutionError):
        a.resolve("manifests/unknown/not_in_index.json")


def test_require_paper_eligible_rejects_legacy_invalid(repo):
    a = AuthorityV3(repo)
    with pytest.raises(EvidenceResolutionError):
        a.require_paper_eligible("manifests/phase5/legacy_phase5.json")


def test_reactflow_is_external_only(repo):
    a = AuthorityV3(repo)
    assert a.is_reactflow("manifests/reactflow_adapter.json") is True


def test_d2t_paper_eligible_reactflow_count_zero_for_clean(repo):
    """No D2T paper-eligible ReactFlow evidence in a clean index."""
    a = AuthorityV3(repo)
    assert a.d2t_paper_eligible_reactflow_count() == 0


def test_terminalized_includes_phase5(repo):
    a = AuthorityV3(repo)
    arts = {r.artifact for r in a.terminalized()}
    assert "manifests/phase5/legacy_phase5.json" in arts


# --- submission status conjunction -------------------------------------------

def test_submission_blocked_when_not_authorized():
    rs = compute_readiness_status(
        editorial_build_ok=True, scientific_claim_authorized=False,
        authority_lineage_ok=True, reproducibility_ok=True, citation_ok=True,
        pdf_ok=True, visual_qa_ok=True, sota_ok=True, real_data_ok=True,
        comparative_ok=True,
    )
    assert rs.submission_status == "SCIENTIFIC_SUBMISSION_BLOCKED"
    assert "READY_FOR_SUBMISSION" not in rs.submission_status


def test_submission_ready_only_when_authorized_and_all_ok():
    rs = compute_readiness_status(
        editorial_build_ok=True, scientific_claim_authorized=True,
        authority_lineage_ok=True, reproducibility_ok=True, citation_ok=True,
        pdf_ok=True, visual_qa_ok=True, sota_ok=True, real_data_ok=True,
        comparative_ok=True,
    )
    assert rs.submission_status == "SCIENTIFIC_SUBMISSION_READY"


# --- external-only scientific claim authorization ----------------------------

def _write_attestation(repo, head, signer="EXTERNAL_ADJUDICATOR", generator="thirdparty-ci",
                       limitations="real-data route terminated; synthetic-only"):
    p = os.path.join(repo, "attestation.json")
    with open(p, "w") as f:
        json.dump({
            "schema": ATTESTATION_SCHEMA,
            "tree": head,
            "signer": signer,
            "generator": generator,
            "limitations": limitations,
            "allowed_artifacts": "manifests/audit/v7_artifact_authority_index_v3.json",
            "claim_graph": "manifests/paper/paper_claim_register.json",
        }, f)
    return p


def test_authorization_absent_is_false(repo):
    assert scientific_claim_authorization(repo, "abc123") is False


def test_authorization_requires_exact_tree(repo):
    head = "abc123"
    att = _write_attestation(repo, "othertree")
    assert scientific_claim_authorization(repo, head, att) is False


def test_authorization_rejects_self_referential_generator(repo):
    """The repo's own gate/scripts must not be able to authorize itself."""
    head = "abc123"
    att = _write_attestation(repo, head, generator="paper_readiness_gate")
    assert scientific_claim_authorization(repo, head, att) is False


def test_authorization_rejects_in_repo_generator(repo):
    head = "abc123"
    att = _write_attestation(repo, head, generator="d2t_rna.gate")
    assert scientific_claim_authorization(repo, head, att) is False


def test_authorization_accepts_external_signature(repo):
    head = "abc123"
    att = _write_attestation(repo, head)
    assert scientific_claim_authorization(repo, head, att) is True
