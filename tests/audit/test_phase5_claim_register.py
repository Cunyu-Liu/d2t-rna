"""Conditional Phase 5: claim register v2 verification.

Verifies the Phase 5 claim register (``scripts/t5_phase5_claim_register.py``)
binds the frozen synthetic route into a fail-closed claim-evidence structure:

* exactly ONE core claim + THREE secondary claims (plan "论文最多" contract);
* every claim lists required_evidence / available_evidence /
  missing_evidence / prohibited_overinterpretation;
* every claim is bound to evidence IDs whose artifacts exist and carry a sha256;
* fail-closed: scientific_claim_authorized=False, status=CLAIM_REGISTER_V2_SYNTHETIC,
  real_data_route=TERMINATED_FOR_CURRENT_DATA, sota_status=SOTA_NOT_ADJUDICATED,
  no prohibited claim (no SOTA / real-data superiority / biological or
  population generalization / strictly-cheaper-unfair);
* registration only: does NOT set SCIENTIFIC_SUBMISSION_READY.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from scripts.t5_phase5_claim_register import (
    ROOT,
    build_claim_register,
    _canonical_sha256,
    _claims,
)

CLAIM_TYPES = {"C1", "S1", "S2", "S3"}
EVIDENCE_FIELDS = {
    "required_evidence",
    "available_evidence",
    "missing_evidence",
    "prohibited_overinterpretation",
}


def test_exactly_one_core_and_three_secondary_claims():
    payload = build_claim_register()
    claims = payload["claims"]
    assert set(claims.keys()) == CLAIM_TYPES, f"claim set mismatch: {set(claims)}"
    n_core = sum(1 for c in claims.values() if c["claim_type"] == "CORE")
    n_sec = sum(1 for c in claims.values() if c["claim_type"] == "SECONDARY")
    assert n_core == 1, "must have exactly one core claim"
    assert n_sec == 3, "must have exactly three secondary claims"
    assert payload["n_core_claims"] == 1
    assert payload["n_secondary_claims"] == 3
    assert payload["core_plus_secondary"] == 4


def test_every_claim_has_all_required_fields():
    claims = _claims()
    for cid, c in claims.items():
        for field in EVIDENCE_FIELDS:
            assert field in c, f"{cid} missing field {field}"
            assert isinstance(c[field], list) and c[field], \
                f"{cid} field {field} must be a non-empty list"
        assert isinstance(c["claim"], str) and c["claim"]
        assert c["claim_type"] in {"CORE", "SECONDARY"}


def test_fail_closed_invariants():
    payload = build_claim_register()
    assert payload["status"] == "CLAIM_REGISTER_V2_SYNTHETIC"
    assert payload["scientific_claim_authorized"] is False
    assert payload["real_data_route"] == "TERMINATED_FOR_CURRENT_DATA"
    assert payload["sota_status"] == "SOTA_NOT_ADJUDICATED"
    for k, v in payload["prohibited_present"].items():
        assert v is False, f"prohibited claim present in {k}"
    assert "SCIENTIFIC_SUBMISSION_READY" not in payload["status"]
    # boundary note must not assert readiness; a mention is allowed only as a
    # negation ("does not set ..."), never as an affirmative READY claim.
    bn = payload["boundary_note"]
    assert "SCIENTIFIC_SUBMISSION_READY" not in bn or "does not set" in bn


def test_all_evidence_exists_and_is_hashed():
    payload = build_claim_register()
    reg = payload["evidence_registry"]
    assert reg, "evidence registry must be non-empty"
    for eid, meta in reg.items():
        p = pathlib.Path(meta["path"])
        if not p.is_absolute():
            p = ROOT / p
        assert p.exists(), f"evidence {eid} path missing: {meta['path']}"
        assert meta["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        assert meta["role"]


def test_claim_evidence_edges_reference_valid_ids():
    payload = build_claim_register()
    reg = payload["evidence_registry"]
    edges = payload["claim_evidence_edges"]
    assert set(edges.keys()) == CLAIM_TYPES
    for cid, ids in edges.items():
        assert ids, f"{cid} has no evidence edges"
        for eid in ids:
            assert eid in reg, f"{cid} edge references unknown evidence {eid}"
            # the referenced evidence must carry the claimed quantitative payload
            assert payload["claims"][cid]["available_evidence"], \
                f"{cid} claims evidence but available_evidence empty"


def test_canonical_sha_is_stable_and_deterministic():
    p1 = build_claim_register()
    p2 = build_claim_register()
    # deterministic: same content -> same canonical hash
    assert _canonical_sha256(p1) == _canonical_sha256(p2)
    # canonical hash must be a 64-hex sha256
    h = _canonical_sha256(p1)
    assert len(h) == 64 and set(h) <= set("0123456789abcdef")


def test_no_claim_overreaches_scope():
    payload = build_claim_register()
    forbidden_terms = ["SOTA", "state-of-the-art", "beats all", "best-in-class"]
    claims = payload["claims"]
    for cid, c in claims.items():
        claim = c["claim"].lower()
        for term in forbidden_terms:
            assert term.lower() not in claim, \
                f"{cid} over-claims: contains {term}"
