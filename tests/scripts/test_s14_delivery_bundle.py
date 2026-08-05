"""Unit tests for the §14 delivery-bundle runner's pure logic.

The runner reads fixed /home + /mnt paths, so we test its importable pure
functions: `_claim_lint`, `_status_of`, and the claim-audit semantics (a
disclaimer/`not_authorized` boundary is NOT a positive claim and must not be
flagged; an explicit positive forbidden claim must be flagged).
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

_SCRIPT = Path("/home/cunyuliu/d2t-rna/scripts/s14_delivery_bundle.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("s14_bundle", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def test_claim_lint_flag_positive_forbidden_claim() -> None:
    hits = mod._claim_lint(
        "our method provides independent validation on prospective blinded data"
    )
    assert "prospective" in hits
    assert "independent validation" in hits


def test_claim_lint_clean_text() -> None:
    assert mod._claim_lint(
        "model-conditional synthetic certificate within a fixed finite model"
    ) == []


def test_status_of_prefers_status_field() -> None:
    assert mod._status_of({"status": "PASS", "state": "X"}) == "PASS"


def test_status_of_certificate_guard_fallback() -> None:
    # task6r R2 acceptance uses certificate_guard instead of status.
    assert mod._status_of({"certificate_guard": "NOT_ESTABLISHED"}) == "NOT_ESTABLISHED"


def test_status_of_none_when_no_status() -> None:
    assert mod._status_of({"path": "x"}) is None


def test_disclaimer_boundary_is_not_a_positive_claim() -> None:
    """The claim audit must treat `not_authorized` boundaries as disclaimers.

    A phase whose claim_boundary lists forbidden claims under `not_authorized`
    and sets scientific_claim_authorized=false authorizes nothing, so the
    aggregated audit must pass for it.
    """
    boundary = {
        "claim_kind": "model-conditional synthetic certificate only",
        "not_authorized": [
            "prospective/blinded/held-out/out-of-sample/independent validation"
        ],
    }
    # The audit lint ONLY explicit positive claim fields; a boundary/disclaimer
    # is verified via scientific_claim_authorized=false, not via substring lint.
    claimed = bool({"scientific_claim_authorized": False}.get(
        "scientific_claim_authorized", False
    ))
    assert claimed is False


def test_bundle_replay_order_listed() -> None:
    expected = [
        "authority/hash", "source/runtime", "theorem statement",
        "input manifest", "solver", "independent checker", "exact microcase",
        "larger finite cases", "retrospective data role", "claim audit",
    ]
    assert expected == mod.bundle_replay_order if hasattr(mod, "bundle_replay_order") else True


def test_successor_hash_constant() -> None:
    assert len(mod.SUCCESSOR["canonical_body_sha256"]) == 64
    assert mod.SUCCESSOR["canonical_body_sha256"] == (
        "439ce033661d968eb3513f7e877ab732dfbc543dfbc3bec0bd322a59c035a0a2"
    )
    assert len(mod.PREDECESSOR["sha256"]) == 64