"""Conditional Phase 6: claim-evidence bidirectional graph verification.

Verifies ``scripts/t6_claim_evidence_graph.py`` builds a fail-closed bidirectional
claim<->evidence graph over the frozen synthetic route:

* forward (claim -> evidence) and reverse (evidence -> claim) edges are exactly
  consistent (bidirectional);
* every edge target is a registered evidence id whose path exists and whose
  sha256 matches the recorded value;
* every claim node carries claim_type + claim text + evidence_ids;
* reactflow / external evidence count == 0;
* fail-closed: scientific_claim_authorized=False, no SCIENTIFIC_SUBMISSION_READY;
* registration only.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from scripts.t6_claim_evidence_graph import (
    CLAIM_REGISTER,
    ROOT,
    build_evidence_graph,
    _canonical_sha256,
)


def test_bidirectional_consistency():
    g = build_evidence_graph()
    forward = g["edges_claim_to_evidence"]
    reverse = g["edges_evidence_to_claims"]
    # reverse must be exact inverse of forward
    for cid, ids in forward.items():
        for eid in ids:
            assert cid in reverse[eid], \
                f"reverse missing edge {eid}->{cid}"
    for eid, claims in reverse.items():
        for cid in claims:
            assert eid in forward[cid], \
                f"forward missing edge {cid}->{eid}"
    assert g["bidirectional_consistent"] is True
    assert g["n_forward_edges"] == g["n_reverse_edges"]


def test_all_evidence_nodes_resolve_and_hash():
    g = build_evidence_graph()
    ev = g["evidence"]
    assert ev, "evidence nodes empty"
    for eid, node in ev.items():
        p = pathlib.Path(node["path"])
        if not p.is_absolute():
            p = ROOT / p
        assert p.exists(), f"evidence {eid} missing: {node['path']}"
        assert node["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        assert node["role"]
        # every evidence with claims must have non-empty claim list
        assert node["claims"]


def test_claim_nodes_have_expected_shape():
    g = build_evidence_graph()
    claims = g["claims"]
    assert set(claims.keys()) == {"C1", "S1", "S2", "S3"}
    for cid, c in claims.items():
        assert c["claim_type"] in {"CORE", "SECONDARY"}
        assert c["claim"]
        assert c["evidence_ids"]
    assert g["n_claim_nodes"] == 4
    assert g["n_evidence_nodes"] >= 16


def test_fail_closed_and_no_external_evidence():
    g = build_evidence_graph()
    assert g["reactflow_evidence_count"] == 0
    assert g["external_only_evidence_count"] == 0
    assert g["scientific_claim_authorized"] is False
    assert g["status"] == "CLAIM_EVIDENCE_GRAPH_V2_SYNTHETIC"
    assert "SCIENTIFIC_SUBMISSION_READY" not in g["status"]
    assert "SCIENTIFIC_SUBMISSION_READY" not in g["boundary_note"] or \
        "does not set" in g["boundary_note"]


def test_source_claim_register_locked():
    g = build_evidence_graph()
    src = ROOT / CLAIM_REGISTER
    assert src.exists()
    assert g["source_claim_register_sha256"] == \
        hashlib.sha256(src.read_bytes()).hexdigest()


def test_canonical_sha_deterministic():
    g1 = build_evidence_graph()
    g2 = build_evidence_graph()
    assert _canonical_sha256(g1) == _canonical_sha256(g2)
    assert len(_canonical_sha256(g1)) == 64
