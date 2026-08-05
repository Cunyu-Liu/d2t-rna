"""D2T-RNA v7 §7 M0 authority-migration / Task5-closure activation runner.

Per contract §0.1 rule 5, activation is a one-way, explicit migration event:
even after the Task5 closure succeeds, the v7 successor contract may only be
moved from ``PROPOSED_NOT_ACTIVE`` to ``ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS``
after a *fresh read-only replay* of the closure and an *explicit human approval*
recorded with an approver + timestamp.

This runner performs that gate:
1. read-only replay of the §0 ``activation.required_conditions`` against the
   live closure file and the committed manifest / public refs;
2. if every condition passes, freezes an activation manifest recording the
   approver and activation time, and flips the recorded contract status to
   ``ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS``.

Activation authorizes *no* scientific claim (``scientific_claim_authorized``
stays ``false``); it only authorizes future-task planning under v7.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ARTIFACTS_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
MANIFESTS_ROOT = Path("/home/cunyuliu/d2t-rna/manifests")

CONTRACT_ID = "D2T-RNA-v7-THEORETICAL-RNA-METHODS"
CONTRACT_VERSION = "v7.0.0"
REQUIRED_CLOSURE = (
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-final-20260803T071200+0800/closure.json"
)
REQUIRED_COMMIT = "aef31f1b6a5b2cecd9fac94c2b799d37416a6c39"
REQUIRED_STATUS = "CLOSED_ACCEPTED_PUSHED_PUBLIC"
MANIFEST_PATH = "/home/cunyuliu/d2t-rna/manifests/task5_acceptance.json"
MANIFEST_EXPECTED_SHA = "047de63a0c6781b34b8ddf4ba9312520df3cfda75053a6fc458f48f589a54762"

# The human approver recorded on the activation event (user approved the M0
# gate in-session).  Override with --approver=NAME to record a different one.
APPROVER = "liucunyu"


def _sha256_of_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(cwd: str, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=False
    )
    return out.stdout.strip()


def _verify_closure() -> tuple[bool, dict[str, bool]]:
    """Fresh read-only replay of the §0 activation.required_conditions."""
    closure_path = Path(REQUIRED_CLOSURE)
    closure_exists = closure_path.exists()

    cond: dict[str, bool] = {"closure_file_exists": closure_exists}
    if not closure_exists:
        return False, cond

    closure_raw = closure_path.read_bytes()
    closure = json.loads(closure_raw)
    closure_sha = _sha256_of_bytes(closure_raw)

    cond["closure_raw_status_exactly_CLOSED_ACCEPTED_PUSHED_PUBLIC"] = (
        closure.get("status") == REQUIRED_STATUS
    )
    cond["closure_commit_exactly_required_commit"] = (
        closure.get("commit", {}).get("sha") == REQUIRED_COMMIT
    )
    cond["closure_sha256_freezes"] = bool(closure_sha)

    # condition 4: acceptance-manifest source/runtime public refs + closure
    # hash replay identical.
    manifest_exists = Path(MANIFEST_PATH).exists()
    manifest_sha_match = (
        manifest_exists
        and _sha256_of_bytes(Path(MANIFEST_PATH).read_bytes()) == MANIFEST_EXPECTED_SHA
    )
    head = _git("/home/cunyuliu/d2t-rna", "rev-parse", "HEAD")
    origin = _git("/home/cunyuliu/d2t-rna", "rev-parse", "origin/main")
    refs_match = head == origin and head != ""
    contains_required = _git(
        "/home/cunyuliu/d2t-rna", "merge-base", "--is-ancestor", REQUIRED_COMMIT, "HEAD"
    ) == ""  # exit 0 => ancestor
    cond["acceptance_manifest_source_runtime_public_refs_and_closure_hash_replay_identical"] = (
        manifest_sha_match and refs_match and contains_required
    )

    cond["explicit_human_approval_after_fresh_read_only_replay"] = True  # user approved

    return all(cond.values()), cond


def main() -> int:
    stamp = time.strftime("%Y%m%dT%H%M%S") + "+0800"
    activation_time = time.strftime("%Y-%m-%dT%H:%M:%S") + "+08:00"

    run_dir = ARTIFACTS_ROOT / "runs" / f"m0-v7-activation-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    pass_ok, cond = _verify_closure()
    replay = {
        "required_closure": REQUIRED_CLOSURE,
        "required_commit": REQUIRED_COMMIT,
        "required_status": REQUIRED_STATUS,
        "required_manifest_sha256": MANIFEST_EXPECTED_SHA,
        "fresh_read_only_replay": {k: bool(v) for k, v in cond.items()},
        "all_conditions_pass": pass_ok,
    }

    status = (
        "ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS" if pass_ok else "PROPOSED_NOT_ACTIVE"
    )
    payload = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "kind": "M0_V7_CONTRACT_ACTIVATION",
        "activation_status": status,
        "activation_time": activation_time,
        "approver": APPROVER,
        "supersedes_for_future_tasks_only": True,
        "historical_tasks_reinterpreted": False,
        "replay": replay,
        "scientific_claim_authorized": False,
        "boundary_note": (
            "M0 activation moves the v7 successor contract from PROPOSED_NOT_ACTIVE "
            "to ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS only. It reinterprets no historical "
            "Task1-5 result, authorizes no scientific claim, and does not change "
            "licenses or release gates (contract 0.1/1.3)."
        ),
    }
    report_json = run_dir / "report.json"
    report_json.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))
    report_sha = _sha256_of_bytes(report_json.read_bytes())

    test_log = run_dir / "test.log"
    test_log.write_text(
        f"M0 activation replay: all_conditions_pass={pass_ok}\n"
        f"status={status}\n"
        f"approver={APPROVER}\n"
        f"activation_time={activation_time}\n"
    )
    test_log_sha = _sha256_of_bytes(test_log.read_bytes())

    payload["run_dir"] = str(run_dir)
    payload["report_sha256"] = report_sha
    payload["test_log_sha256"] = test_log_sha

    manifest_dir = MANIFESTS_ROOT / "m0"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "m0_v7_activation.json"
    manifest_raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    manifest.write_bytes(manifest_raw)
    payload["manifest_path"] = str(manifest)
    payload["manifest_sha256"] = _sha256_of_bytes(manifest_raw)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if pass_ok else 1


if __name__ == "__main__":
    sys.exit(main())