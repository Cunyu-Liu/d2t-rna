#!/usr/bin/env python3
"""Fail-closed verifier for the Task 5 acceptance evidence.

Task 5 deliberately owns a new, dynamic source index.  It never calls the
historical Task 4 ``_source_index`` because that index is frozen to the Task 4
tree and must reject descendants.  The Task 4 isolated launcher and runtime
snapshot implementation are reused only after their accepted bytes are
verified.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
from typing import Any
from xml.etree import ElementTree

from d2t_rna.contracts.base import (
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
)
from d2t_rna.contracts.enums import RorcReason
from d2t_rna.exact.confidence import ExactParameterFamily
from d2t_rna.evaluation.baselines import (
    BaselineComparison,
    replay_baseline_comparison,
)
from d2t_rna.evaluation.milp_check import (
    MilpCheckReceipt,
    replay_bounded_milp_check,
)
from d2t_rna.evaluation.planner import (
    CoverageFeasibilityAssessment,
    replay_coverage_feasibility_assessment,
)
from d2t_rna.evaluation.risk_binding import (
    RiskCertificateReplayBundle,
    replay_risk_certificate_replay_bundle,
)
from d2t_rna.evaluation.scenario import (
    ExactSyntheticScenarioProofArtifact,
    FiniteScenarioCoverageAggregate,
    RegisteredRorcPathAudit,
    RorcObservedDecision,
    RorcStressMetrics,
    ScenarioCoverageDisposition,
    replay_finite_scenario_aggregate,
    replay_rorc_stress_metrics,
)


CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)
COMMIT_TITLE = "feat(evaluation): unify proof manifests and baseline feasibility"
ARTIFACT_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
REPOSITORY = "Cunyu-Liu/d2t-rna"
ORIGIN_URL = "git@github.com:Cunyu-Liu/d2t-rna.git"
PUBLIC_HTTPS_URL = "https://github.com/Cunyu-Liu/d2t-rna.git"

TASK4_ACCEPTANCE_COMMIT = "4793026c1e709b7ca78042b8a10294fe569d7b8c"
TASK4_ACCEPTANCE_MANIFEST_PATH = Path("manifests/task4_acceptance.json")
TASK4_ACCEPTANCE_MANIFEST_SHA256 = (
    "61348d3d00fb96c543e38ffa3b4ab0e15749214ebe54c875024d8efa0a600e96"
)
TASK4_CLOSURE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task4-final-20260730T153100+0800/closure.json"
)
TASK4_CLOSURE_SHA256 = (
    "c023cb1efcfa8cc6d4fe36227d70075bab1a34b7f6cd2939693375016920c068"
)
TASK4_ISOLATED_LAUNCHER_PATH = Path("scripts/task4_isolated_python.py")
TASK4_ISOLATED_LAUNCHER_SHA256 = (
    "01e8ac006837a46faf7208630df8cc362a1e1713c5ecf38229c72c60ec3bbf51"
)
TASK4_RUNTIME_HELPER_PATH = Path(
    "scripts/verify_task4_acceptance_manifest.py"
)
TASK4_RUNTIME_HELPER_SHA256 = (
    "1bb76747e04ebb527c79105b2349bdd648210a30a86498de065330b4e5541b5f"
)

TASK5_ENTRY_GATE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/gates/"
    "task5-entry-gate-open-20260730T165235p0800.json"
)
TASK5_ENTRY_GATE_SHA256 = (
    "01f172eb9d1fa3ee92cb763b995e379a572c5a74c9d3da2678b704192521a725"
)
TASK5_RED_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-red-20260730T165809p0800/red-test.json"
)
TASK5_RED_RECORD_SHA256 = (
    "27fc9fb4ed15dd970d5e75e53a7437440cb797384163f7ca3e060eb67621629e"
)
TASK5_RED_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-red-20260730T165809p0800/pytest-red.log"
)
TASK5_RED_LOG_SHA256 = (
    "1e43f7ab5edbc879f54535ec8f560a4a1f82a52b80ff58d911ed580b8919ff84"
)
TASK5_REJECTED_GREEN_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-green-20260730T172054p0800/evaluation.log"
)
TASK5_REJECTED_GREEN_LOG_SHA256 = (
    "bd835c95635ccfd9c3f719175e45abe526979e622d6176fda303f43680437635"
)
TASK5_ADVERSARIAL_PAUSE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-green-20260730T172054p0800/adversarial-pause.json"
)
TASK5_ADVERSARIAL_PAUSE_SHA256 = (
    "a4dd12f908d856f43340b383dd88b9f0ac0350807560a0e5768b2b84e10bc7f0"
)
TASK5_REPAIR_GREEN_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-repair-green-20260730T180030p0800/evaluation.log"
)
TASK5_REPAIR_GREEN_LOG_SHA256 = (
    "79a108f97f827b5dc5ef10b251d96ba318153c9fefc7afb37cda07e0263dd536"
)
TASK5_REPAIR_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-repair-green-20260730T180030p0800/repair-test.json"
)
TASK5_REPAIR_RECORD_SHA256 = (
    "e982547b0f3bc5de9a10fa0d806b01bdb41c1e6719ab7f4a09f87e2989684733"
)
TASK5_CROSS_AUDIT_PAUSE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-cross-audit-pause-20260730T181604p0800/"
    "cross-audit-pause.json"
)
TASK5_CROSS_AUDIT_PAUSE_SHA256 = (
    "0315494d9dedc60730543773c1503c96df8122a738e8edec7ff309130f8f79e5"
)
TASK5_RISK_WRAPPER_PAUSE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-risk-wrapper-pause-20260730T192413p0800/"
    "risk-wrapper-pause.json"
)
TASK5_RISK_WRAPPER_PAUSE_SHA256 = (
    "5de706de64c39aab350d1679242d62809dad94c48f9f0c656f604d44021a679c"
)
TASK5_RUNTIME_PROVENANCE_PAUSE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-runtime-provenance-pause-20260730T194019p0800/"
    "runtime-provenance-pause.json"
)
TASK5_RUNTIME_PROVENANCE_PAUSE_SHA256 = (
    "9a4cd3aff53140e5cdef1a7a4cda4504d45fc6ed49db3a96288d15badb7ece8c"
)
TASK5_PARENT_BINDING_FAILURE_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/failure-record.json"
)
TASK5_PARENT_BINDING_FAILURE_RECORD_SHA256 = (
    "84dd9e3767511faeb6b15991d3cce78befaba71a4016b5c27d528e6d9105ffce"
)
TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/run.log"
)
TASK5_PARENT_BINDING_FAILURE_RUN_LOG_SHA256 = (
    "9d1a848de575342bbaaf67d530a214fe51ca94b63643688de69235de0186dfd4"
)
TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/junit/evaluation.xml"
)
TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_SHA256 = (
    "14324750b652ff4b686c58664e4d0a4c0a514100d8adc0d9213b32100ccdd82b"
)
TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/junit/combined.xml"
)
TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_SHA256 = (
    "a3c1e3dc175ddeef292c489adc9edece83c28148372ee6ad138592f2e1b9ae48"
)
TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/snapshots/source_index.json"
)
TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_SHA256 = (
    "dcafe80c5a9b8ea250b25c953e334ae837036006545abeacf5a79b7564bb3131"
)
TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260730T201740+0800/snapshots/"
    "runtime_dependency_snapshot.json"
)
TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_SHA256 = (
    "6cb084a2774232bebb12b6f82465b66bbe3b41e20f5580477040dd0abfa7f623"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/failure-record.json"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_SHA256 = (
    "39df71b945f826dcddcfe011c14f68c09f43866c6b1e925dc70d314324217f8d"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/targeted_runner.sh"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_SHA256 = (
    "c786391d062e5b20fe3f72c94d7a23b53f418f6350a3d4840f09430ef869ccce"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/run.log"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_SHA256 = (
    "dda3d80030b66f467aa3f19d15d5c63be5925645591a931b1ea280cc76b39272"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/snapshots/"
    "runtime_dependency_snapshot.json"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_SHA256 = (
    "6cb084a2774232bebb12b6f82465b66bbe3b41e20f5580477040dd0abfa7f623"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/snapshots/"
    "source_index.json"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_SHA256 = (
    "af719c281c5c3f6c0100606899a9961f822afd05a4b599e7983f7f8df9051c52"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T052401+0800/snapshots/"
    "task4_nested_parent_binding.json"
)
TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_SHA256 = (
    "733ad267364c2f9121d61f39ae7cbac69b73060c6ce93cbf8de6620f7b05f19c"
)
TASK5_PARENT_BINDING_REPAIR_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/repair-record.json"
)
TASK5_PARENT_BINDING_REPAIR_RECORD_SHA256 = (
    "801b248a0677a213c921c899be928aa7970c6161619d3c66a5d4066cb0aec643"
)
TASK5_PARENT_BINDING_REPAIR_RUNNER_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/targeted_runner.sh"
)
TASK5_PARENT_BINDING_REPAIR_RUNNER_SHA256 = (
    "ecaadee36e25a7a810f19448493b0a2940d2e8ce12a638b4076083087195b9da"
)
TASK5_PARENT_BINDING_REPAIR_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/run.log"
)
TASK5_PARENT_BINDING_REPAIR_LOG_SHA256 = (
    "2cd045d825b663ad593c9e4ab71d499e7a9e2d66d3e3df2dca996860cd44d3eb"
)
TASK5_PARENT_BINDING_REPAIR_JUNIT_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/junit/targeted.xml"
)
TASK5_PARENT_BINDING_REPAIR_JUNIT_SHA256 = (
    "c4e446c5c6bb88a7d564c75692c36d98990809cfc54c207cb7126094a5171348"
)
TASK5_PARENT_BINDING_REPAIR_RUNTIME_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/snapshots/"
    "runtime_dependency_snapshot.json"
)
TASK5_PARENT_BINDING_REPAIR_RUNTIME_SHA256 = (
    "6cb084a2774232bebb12b6f82465b66bbe3b41e20f5580477040dd0abfa7f623"
)
TASK5_PARENT_BINDING_REPAIR_SOURCE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/snapshots/"
    "source_index.json"
)
TASK5_PARENT_BINDING_REPAIR_SOURCE_SHA256 = (
    "1735169497a0c8988666b6710618c8ab2209f8ee353b7d72dac2ccac0be21605"
)
TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/snapshots/"
    "source_index_post_test.json"
)
TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_SHA256 = (
    "1735169497a0c8988666b6710618c8ab2209f8ee353b7d72dac2ccac0be21605"
)
TASK5_PARENT_BINDING_REPAIR_BINDING_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-parent-binding-repair-20260731T053556+0800/snapshots/"
    "task4_nested_parent_binding.json"
)
TASK5_PARENT_BINDING_REPAIR_BINDING_SHA256 = (
    "733ad267364c2f9121d61f39ae7cbac69b73060c6ce93cbf8de6620f7b05f19c"
)
TASK5_MANIFEST_BUILD_FAILURE_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-manifest-build-20260731T234517+0800/failure-record.json"
)
TASK5_MANIFEST_BUILD_FAILURE_RECORD_SHA256 = (
    "549d722e83d1e9e00ac804097abf12e96e1997505b54dbcc3f474c5b43c3ae63"
)
TASK5_MANIFEST_BUILD_FAILURE_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-manifest-build-20260731T234517+0800/build.log"
)
TASK5_MANIFEST_BUILD_FAILURE_LOG_SHA256 = (
    "f34ab4266d44fa6acb3db5ac48ab9638b8777e0dbc0106f84e3575abbe9b9732"
)
TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-manifest-build-20260731T234517+0800/exit-code.txt"
)
TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_SHA256 = (
    "4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865"
)
TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260731T055458+0800/run.log"
)
TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_SHA256 = (
    "a1d09346b6b38fe9ae7a439c655d1ada551cff08d60771e082d6722338b88327"
)
TASK5_MANIFEST_BUILD_FAILURE_SOURCE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260731T055458+0800/snapshots/source_index.json"
)
TASK5_MANIFEST_BUILD_FAILURE_SOURCE_SHA256 = (
    "10dbf88b480232e1ba3ee71a3b5ae1a12dba43f5eae601970f444ee2734f0fb8"
)
TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260731T055458+0800/snapshots/source_index_post_test.json"
)
TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_SHA256 = (
    "10dbf88b480232e1ba3ee71a3b5ae1a12dba43f5eae601970f444ee2734f0fb8"
)
TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task5-acceptance-20260731T055458+0800/snapshots/"
    "runtime_dependency_snapshot.json"
)
TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_SHA256 = (
    "6cb084a2774232bebb12b6f82465b66bbe3b41e20f5580477040dd0abfa7f623"
)
TASK5_PARENT_BINDING_FAILURE_NODE_IDS = (
    (
        "tests/exact/test_coverage.py::"
        "test_cold_python311_fixture_build_has_stable_engine_hash"
    ),
    (
        "tests/exact/test_coverage.py::"
        "test_fraction_numeric_abc_dispatch_mutation_fails_in_isolated_process"
    ),
    (
        "tests/exact/test_task4_isolated_python.py::"
        "test_real_nested_child_has_exact_isolated_runtime"
    ),
    (
        "tests/exact/test_task4_isolated_python.py::"
        "test_nested_child_cannot_forge_runtime_closure_receipt"
        "[SystemExit-False]"
    ),
    (
        "tests/exact/test_task4_isolated_python.py::"
        "test_nested_child_cannot_forge_runtime_closure_receipt"
        "[os._exit-True]"
    ),
    (
        "tests/contracts/test_canonical.py::"
        "test_hash_is_stable_across_processes_and_hash_seeds"
    ),
)

EXPECTED_HISTORICAL_EVIDENCE = {
    "task4_acceptance_manifest": {
        "path": "manifests/task4_acceptance.json",
        "sha256": TASK4_ACCEPTANCE_MANIFEST_SHA256,
    },
    "task4_post_commit_closure": {
        "path": str(TASK4_CLOSURE_PATH),
        "sha256": TASK4_CLOSURE_SHA256,
    },
    "task5_entry_gate": {
        "path": str(TASK5_ENTRY_GATE_PATH),
        "sha256": TASK5_ENTRY_GATE_SHA256,
    },
    "task5_red_record": {
        "path": str(TASK5_RED_RECORD_PATH),
        "sha256": TASK5_RED_RECORD_SHA256,
    },
    "task5_red_log": {
        "path": str(TASK5_RED_LOG_PATH),
        "sha256": TASK5_RED_LOG_SHA256,
    },
    "task5_rejected_green_log": {
        "path": str(TASK5_REJECTED_GREEN_LOG_PATH),
        "sha256": TASK5_REJECTED_GREEN_LOG_SHA256,
        "status": "NOT_ACCEPTANCE",
    },
    "task5_adversarial_pause": {
        "path": str(TASK5_ADVERSARIAL_PAUSE_PATH),
        "sha256": TASK5_ADVERSARIAL_PAUSE_SHA256,
        "status": "PAUSED_FOR_FAIL_CLOSED_REPAIR",
    },
    "task5_corrected_repair_green_log_not_acceptance": {
        "path": str(TASK5_REPAIR_GREEN_LOG_PATH),
        "sha256": TASK5_REPAIR_GREEN_LOG_SHA256,
        "status": "NOT_ACCEPTANCE",
    },
    "task5_corrected_repair_record_not_acceptance": {
        "path": str(TASK5_REPAIR_RECORD_PATH),
        "sha256": TASK5_REPAIR_RECORD_SHA256,
        "status": "NOT_ACCEPTANCE",
        "record_status": "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE",
    },
    "task5_cross_audit_pause": {
        "path": str(TASK5_CROSS_AUDIT_PAUSE_PATH),
        "sha256": TASK5_CROSS_AUDIT_PAUSE_SHA256,
        "status": "PAUSED_FOR_FORMAL_PROVENANCE_REPAIR",
    },
    "task5_risk_wrapper_pause": {
        "path": str(TASK5_RISK_WRAPPER_PAUSE_PATH),
        "sha256": TASK5_RISK_WRAPPER_PAUSE_SHA256,
        "status": "PAUSED_FOR_RISK_WRAPPER_EXECUTION_CLOSURE_REPAIR",
    },
    "task5_runtime_provenance_pause": {
        "path": str(TASK5_RUNTIME_PROVENANCE_PAUSE_PATH),
        "sha256": TASK5_RUNTIME_PROVENANCE_PAUSE_SHA256,
        "status": "PAUSED_FOR_PLANNER_RORC_CFA_PROVENANCE_REPAIR",
    },
    "task5_parent_binding_candidate_failure": {
        "path": str(TASK5_PARENT_BINDING_FAILURE_RECORD_PATH),
        "sha256": TASK5_PARENT_BINDING_FAILURE_RECORD_SHA256,
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    },
    "task5_targeted_repair_preflight_failure": {
        "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_PATH),
        "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_SHA256,
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    },
    "task5_parent_binding_corrected_targeted_green_not_acceptance": {
        "path": str(TASK5_PARENT_BINDING_REPAIR_RECORD_PATH),
        "sha256": TASK5_PARENT_BINDING_REPAIR_RECORD_SHA256,
        "status": "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE",
    },
    "task5_manifest_build_canonical_equivalence_failure": {
        "path": str(TASK5_MANIFEST_BUILD_FAILURE_RECORD_PATH),
        "sha256": TASK5_MANIFEST_BUILD_FAILURE_RECORD_SHA256,
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    },
}

CLAIM_BOUNDARY = {
    "claim_domain": "TASK5_SYNTHETIC_SOFTWARE_EVALUATION_ONLY",
    "probability_scope": "SYNTHETIC_KNOWN_CHANNEL",
    "finite_registered_scenarios_only": True,
    "risk_certificate_issued": False,
    "formal_scientific_certificate_authorized": False,
    "prospective_claim_authorized": False,
    "new_library_claim_authorized": False,
    "native_t4_claim_authorized": False,
    "population_claim_authorized": False,
    "observed_dataset_qa_completed": False,
    "scientific_conclusion_authorized": False,
    "serialized_bearer_authorization": False,
}

SOURCE_INDEX_SCHEMA = "d2t_rna.task5_source_snapshot.v1"
RUNTIME_SNAPSHOT_SCHEMA = "d2t_rna.task5_runtime_dependency_snapshot.v1"
TASK4_NESTED_PARENT_BINDING_SCHEMA = (
    "d2t_rna.task5_task4_nested_parent_binding.v1"
)
MANIFEST_SCHEMA = "d2t_rna.task5_acceptance_manifest.v1"
FIXTURE_SCHEMA = "d2t_rna.task5_acceptance_fixture_manifest.v1"
CANDIDATE_RUN_ID = re.compile(
    r"^task5-acceptance-(?P<stamp>[0-9]{8}T[0-9]{6})\+0800$"
)
DISALLOWED_CANDIDATE_RUN_IDS = frozenset(
    {
        "task5-acceptance-20260731T055458+0800",
    }
)
PYTEST_SUMMARY = re.compile(
    r"^(\d+) passed(?:, \d+ warnings?)? in [0-9.]+s"
    r"(?: \([0-9:]+\))?$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_INDEXED_FILES = 10_000
MAX_INDEXED_FILE_BYTES = 5 * 1024 * 1024
MINIMUM_TEST_COUNTS = (56, 350, 480)
SELF_REFERENTIAL_PATHS = frozenset(
    {
        "manifests/task5_acceptance.json",
    }
)
FORBIDDEN_ROOT_EXECUTION_INPUTS = (
    "conftest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
)
EXPECTED_FIXTURE_ARTIFACTS = frozenset(
    {
        "available_control_library_check",
        "registered_design_class_check",
        "scenario_aggregate",
        "risk_certificate_replay_bundle",
        "coverage_feasibility_assessment",
        "baseline_comparison",
        "rorc_metrics",
        "registered_rorc_path_audit",
    }
)
EXPECTED_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "task",
        "status",
        "contract_sha256",
        "registered_commit_title",
        "prior_task",
        "historical_evidence",
        "runtime",
        "source_snapshot",
        "task5_delta",
        "test_evidence",
        "fixture_evidence",
        "claim_boundary",
        "github",
        "post_commit_closure_required",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_sha(value: object, *, label: str) -> str:
    if type(value) is not str or SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} is not a canonical SHA-256")
    return value


def _validate_run_id(run_id: object) -> str:
    if type(run_id) is not str:
        raise ValueError("Task 5 candidate run ID is not canonical")
    match = CANDIDATE_RUN_ID.fullmatch(run_id)
    if match is None:
        raise ValueError("Task 5 candidate run ID is not canonical")
    try:
        parsed = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise ValueError(
            "Task 5 candidate run ID does not contain a real calendar time"
        ) from exc
    if parsed.strftime("%Y%m%dT%H%M%S") != match.group("stamp"):
        raise ValueError("Task 5 candidate run ID timestamp is not canonical")
    if run_id in DISALLOWED_CANDIDATE_RUN_IDS:
        raise ValueError(
            "Task 5 candidate run ID is registered failed evidence"
        )
    return run_id


def _canonical_root(project_root: Path) -> Path:
    lexical = Path(os.path.abspath(project_root))
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Task 5 project root is unavailable") from exc
    if lexical != resolved or lexical.is_symlink() or not lexical.is_dir():
        raise ValueError("Task 5 project root is not canonical")
    return lexical


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_symlink_component(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    cursor = root
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            return True
    return False


def _registered_source_paths(project_root: Path) -> tuple[str, ...]:
    root = _canonical_root(project_root)
    required = (
        "README.md",
        "pyproject.toml",
        "contracts/D2T-RNA-v6.1-frozen-plan.md",
    )
    selected: set[str] = set(required)
    root_specs = (
        ("src", None, frozenset()),
        ("tests", None, frozenset()),
        ("scripts", None, frozenset()),
        ("docs/audit", frozenset({".md"}), frozenset()),
        ("manifests", frozenset({".json"}), frozenset()),
    )
    for relative_root, suffixes, names in root_specs:
        directory = root / relative_root
        if relative_root in {"src", "tests", "scripts", "manifests"}:
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or _has_symlink_component(root, directory)
            ):
                raise ValueError(
                    f"Task 5 source-index root is unavailable: {relative_root}"
                )
        elif not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError(
                    "Task 5 source closure contains a symlink: "
                    f"{path.relative_to(root).as_posix()}"
                )
            if "__pycache__" in path.parts:
                if path.is_file() and path.suffix == ".pyc":
                    continue
                if path.is_file():
                    raise ValueError(
                        "Task 5 cache directory contains a non-generated "
                        "regular file: "
                        f"{path.relative_to(root).as_posix()}"
                    )
                continue
            if not path.is_file():
                continue
            if (
                path.suffix == ".pyc"
                or path.name.endswith(
                    tuple(importlib.machinery.EXTENSION_SUFFIXES)
                )
                or path.suffix in {".so", ".pyd", ".dylib"}
            ):
                raise ValueError(
                    "Task 5 source closure contains sourceless bytecode or "
                    "a native extension: "
                    f"{path.relative_to(root).as_posix()}"
                )
            if suffixes is None or path.suffix in suffixes or path.name in names:
                selected.add(path.relative_to(root).as_posix())
    selected.difference_update(SELF_REFERENTIAL_PATHS)
    if len(selected) > MAX_INDEXED_FILES:
        raise ValueError("Task 5 source closure exceeds the registered file cap")
    return tuple(sorted(selected))


def _source_index(project_root: Path) -> dict[str, str]:
    """Hash every Task 5 execution input without a frozen Task 4 path list."""

    root = _canonical_root(project_root)
    index: dict[str, str] = {}
    for relative in _registered_source_paths(root):
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or relative != pure.as_posix()
        ):
            raise ValueError("Task 5 source path is not canonical")
        path = root / relative
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Task 5 indexed source is unavailable: {relative}"
            ) from exc
        if (
            path.is_symlink()
            or not path.is_file()
            or resolved != path
            or _has_symlink_component(root, path)
        ):
            raise ValueError(
                f"Task 5 indexed source is unsafe: {relative}"
            )
        if path.stat().st_size > MAX_INDEXED_FILE_BYTES:
            raise ValueError(
                f"Task 5 indexed source exceeds 5 MiB: {relative}"
            )
        index[relative] = _sha256(path)
    return index


def source_index_sha256(project_root: Path) -> str:
    return canonical_sha256(_source_index(project_root))


def build_source_snapshot(project_root: Path) -> dict[str, object]:
    index = _source_index(project_root)
    return {
        "schema": SOURCE_INDEX_SCHEMA,
        "source_index": index,
        "source_index_sha256": canonical_sha256(index),
        "execution_roots_regular_file_policy": (
            "HASH_ALL_REGULAR_FILES_FAIL_ON_SYMLINK_NATIVE_OR_LEGACY_PYC"
        ),
        "generated_cache_policy": (
            "EXCLUDE_ONLY_PYC_FILES_UNDER___PYCACHE___DIRECTORIES"
        ),
        "self_referential_paths_excluded": tuple(
            sorted(SELF_REFERENTIAL_PATHS)
        ),
        "future_descendant_mutation_policy": "FAIL_CLOSED",
    }


def _verify_reused_task4_helpers(project_root: Path) -> dict[str, str]:
    root = _canonical_root(project_root)
    expected = {
        str(TASK4_ISOLATED_LAUNCHER_PATH): TASK4_ISOLATED_LAUNCHER_SHA256,
        str(TASK4_RUNTIME_HELPER_PATH): TASK4_RUNTIME_HELPER_SHA256,
    }
    for relative, digest in expected.items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise ValueError(
                f"accepted Task 4 helper bytes changed: {relative}"
            )
    return expected


def build_runtime_dependency_snapshot(
    project_root: Path,
) -> dict[str, object]:
    """Wrap the accepted Task 4 full CPython/dependency snapshot."""

    helpers = _verify_reused_task4_helpers(project_root)
    from scripts.verify_task4_acceptance_manifest import (
        _runtime_dependency_snapshot as task4_runtime_snapshot,
    )

    task4_snapshot = task4_runtime_snapshot(project_root)
    return {
        "schema": RUNTIME_SNAPSHOT_SCHEMA,
        "implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "reused_task4_helper_sha256": helpers,
        "task4_runtime_dependency_snapshot": task4_snapshot,
        "task4_runtime_dependency_snapshot_sha256": canonical_sha256(
            task4_snapshot
        ),
    }


def runtime_dependency_snapshot_sha256(project_root: Path) -> str:
    return canonical_sha256(build_runtime_dependency_snapshot(project_root))


def derive_task4_nested_parent_binding(
    project_root: Path,
    *,
    runtime_snapshot: object,
    source_snapshot: object,
) -> dict[str, str]:
    """Derive the live Task 4-subclosure digests frozen for nested tests."""

    _verify_reused_task4_helpers(project_root)
    if (
        type(runtime_snapshot) is not dict
        or set(runtime_snapshot)
        != {
            "schema",
            "implementation",
            "python_version",
            "python_cache_tag",
            "reused_task4_helper_sha256",
            "task4_runtime_dependency_snapshot",
            "task4_runtime_dependency_snapshot_sha256",
        }
        or runtime_snapshot.get("schema") != RUNTIME_SNAPSHOT_SCHEMA
    ):
        raise ValueError(
            "Task 5 runtime snapshot cannot bind the nested Task 4 parent"
        )
    task4_runtime = runtime_snapshot[
        "task4_runtime_dependency_snapshot"
    ]
    task4_dependency_sha256 = canonical_sha256(task4_runtime)
    if (
        runtime_snapshot["task4_runtime_dependency_snapshot_sha256"]
        != task4_dependency_sha256
    ):
        raise ValueError(
            "Task 5 nested Task 4 dependency snapshot hash does not replay"
        )

    if (
        type(source_snapshot) is not dict
        or set(source_snapshot)
        != {
            "schema",
            "source_index",
            "source_index_sha256",
            "execution_roots_regular_file_policy",
            "generated_cache_policy",
            "self_referential_paths_excluded",
            "future_descendant_mutation_policy",
        }
        or source_snapshot.get("schema") != SOURCE_INDEX_SCHEMA
    ):
        raise ValueError(
            "Task 5 source snapshot cannot bind the nested Task 4 parent"
        )
    source_index = source_snapshot["source_index"]
    if (
        type(source_index) is not dict
        or any(type(path) is not str for path in source_index)
        or any(
            type(digest) is not str or SHA256.fullmatch(digest) is None
            for digest in source_index.values()
        )
        or source_snapshot["source_index_sha256"]
        != canonical_sha256(source_index)
    ):
        raise ValueError(
            "Task 5 source snapshot hash does not replay for nested Task 4"
        )

    from scripts.verify_task4_acceptance_manifest import (
        EXPECTED_SOURCE_PATHS as task4_expected_source_paths,
    )

    task4_paths = tuple(sorted(task4_expected_source_paths))
    if (
        len(task4_paths) != len(set(task4_paths))
        or any(path not in source_index for path in task4_paths)
    ):
        raise ValueError(
            "Task 5 source snapshot omits a registered Task 4 parent path"
        )
    task4_source_index = {
        path: source_index[path] for path in task4_paths
    }
    return {
        "schema": TASK4_NESTED_PARENT_BINDING_SCHEMA,
        "dependency_snapshot_sha256": task4_dependency_sha256,
        "source_index_sha256": canonical_sha256(task4_source_index),
    }


def _write_canonical_exclusive(path: Path, value: object) -> str:
    payload = canonical_json_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_equal(left: object, right: object) -> bool:
    """Compare snapshots by their registered canonical JSON semantics."""

    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _reject_duplicate_object_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_canonical_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    try:
        raw = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} is not strict JSON") from exc
    if type(raw) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    if payload != canonical_json_bytes(raw) + b"\n":
        raise ValueError(f"{label} is not canonical JSON")
    return raw


def _path_within(path: Path, root: Path, *, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{label} must be an absolute non-symlink path")
    lexical_root = Path(os.path.abspath(root))
    lexical_path = Path(os.path.abspath(path))
    if (
        lexical_root.is_symlink()
        or not lexical_root.is_dir()
        or lexical_root.resolve() != lexical_root
        or not _is_within(lexical_path, lexical_root)
        or _has_symlink_component(lexical_root, lexical_path)
    ):
        raise ValueError(f"{label} traverses an unsafe path")
    try:
        resolved = lexical_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    if (
        resolved != lexical_path
        or not resolved.is_file()
        or not _is_within(resolved, lexical_root)
    ):
        raise ValueError(f"{label} escaped its registered root")
    return resolved


def _resolve_task4_binding_cli_paths(
    *,
    output_path: Path,
    runtime_snapshot_path: Path,
    source_snapshot_path: Path,
) -> tuple[Path, Path, Path]:
    """Lock the standalone parent-binding action to one canonical snapshot dir."""

    expected_names = {
        output_path: "task4_nested_parent_binding.json",
        runtime_snapshot_path: "runtime_dependency_snapshot.json",
        source_snapshot_path: "source_index.json",
    }
    if any(
        not path.is_absolute() or path.name != expected_name
        for path, expected_name in expected_names.items()
    ):
        raise ValueError(
            "Task 5 parent-binding paths must be absolute registered snapshots"
        )
    snapshot_dir = output_path.parent
    if (
        snapshot_dir.is_symlink()
        or not snapshot_dir.is_dir()
        or snapshot_dir.resolve() != snapshot_dir
        or runtime_snapshot_path.parent != snapshot_dir
        or source_snapshot_path.parent != snapshot_dir
    ):
        raise ValueError(
            "Task 5 parent-binding paths must share one canonical directory"
        )
    expected_output = snapshot_dir / "task4_nested_parent_binding.json"
    if (
        output_path != expected_output
        or output_path.is_symlink()
        or output_path.exists()
    ):
        raise ValueError(
            "Task 5 parent-binding output is not a fresh registered artifact"
        )
    runtime = _path_within(
        runtime_snapshot_path,
        snapshot_dir,
        label="Task 5 runtime snapshot",
    )
    source = _path_within(
        source_snapshot_path,
        snapshot_dir,
        label="Task 5 source snapshot",
    )
    return expected_output, runtime, source


def _verify_external_file(
    record: object,
    *,
    root: Path,
    label: str,
    expected_path: Path | None = None,
    expected_sha256: str | None = None,
) -> Path:
    if type(record) is not dict or set(record) != {"path", "sha256"}:
        raise ValueError(f"{label} record is malformed")
    raw_path = record.get("path")
    digest = _require_sha(record.get("sha256"), label=f"{label} SHA-256")
    if type(raw_path) is not str:
        raise ValueError(f"{label} path is malformed")
    path = _path_within(Path(raw_path), root, label=label)
    if expected_path is not None and path != expected_path.resolve():
        raise ValueError(f"{label} path differs from the registered path")
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"{label} SHA-256 differs from authority")
    if _sha256(path) != digest:
        raise ValueError(f"{label} bytes do not match SHA-256")
    return path


def _validate_manifest_build_failure_record(record: object) -> None:
    expected_evidence = {
        "build_log": {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_LOG_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_LOG_SHA256,
        },
        "candidate_post_source_snapshot": {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_SHA256,
        },
        "candidate_run_log": {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_SHA256,
        },
        "candidate_source_snapshot": {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_SOURCE_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_SOURCE_SHA256,
        },
        "exit_code": {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_SHA256,
        },
    }
    expected = {
        "acceptance_authorized": False,
        "candidate_run_id": "task5-acceptance-20260731T055458+0800",
        "canonical_equality": {
            "runtime_snapshot_sha256": (
                "1a84f1886c2dd66e8f264dd9bd4fa83c"
                "c6a5823c215809b3dc73276c5cf38358"
            ),
            "source_snapshot_object_sha256": (
                "089ce9d1eca459ab753635ca5e5cfcc8"
                "22e0d96a192539b90915e290ca048b7d"
            ),
            "source_snapshot_source_index_sha256": (
                "07451efcb8e5a3eaadea3e192298e415"
                "3adc240772effcaf9644299d587054c7"
            ),
        },
        "cause": (
            "PYTHON_CONTAINER_TYPE_MISMATCH_DESPITE_CANONICAL_BYTE_IDENTITY"
        ),
        "evidence": expected_evidence,
        "exit_code": 1,
        "manifest_created": False,
        "next_action": (
            "PATCH_CANONICAL_EQUIVALENCE_AND_RERUN_FULL_CANDIDATE"
        ),
        "run_id": "task5-manifest-build-20260731T234517+0800",
        "schema": "d2t_rna.task5_manifest_build_failure.v1",
        "scientific_conclusion_authorized": False,
        "stage": "source_snapshot_equivalence",
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
        "type_mismatches": {
            "runtime": [
                (
                    "task4_runtime_dependency_snapshot.conda_python_runtime."
                    "runtime_binding.typing_pathless_aliases:list-vs-tuple"
                ),
                (
                    "task4_runtime_dependency_snapshot.stdlib_roots:"
                    "list-vs-tuple"
                ),
                (
                    "task4_runtime_dependency_snapshot."
                    "typing_pathless_aliases:list-vs-tuple"
                ),
            ],
            "source": [
                "self_referential_paths_excluded:list-vs-tuple",
            ],
        },
    }
    if type(record) is not dict or record != expected:
        raise ValueError(
            "Task 5 manifest-build failure semantics changed"
        )


def _verify_historical_evidence(
    project_root: Path,
    records: object,
) -> None:
    if records != EXPECTED_HISTORICAL_EVIDENCE:
        raise ValueError("Task 5 historical evidence registry changed")
    root = _canonical_root(project_root)
    local_task4 = root / TASK4_ACCEPTANCE_MANIFEST_PATH
    if (
        local_task4.is_symlink()
        or not local_task4.is_file()
        or _sha256(local_task4) != TASK4_ACCEPTANCE_MANIFEST_SHA256
    ):
        raise ValueError("accepted Task 4 manifest bytes changed")
    task4 = _load_canonical_json(
        local_task4,
        label="Task 4 acceptance manifest",
    )
    if (
        task4.get("task") != 4
        or task4.get("status") != "READY_FOR_COMMIT"
        or task4.get("contract_sha256") != CONTRACT_SHA256
        or task4.get("github")
        != {
            "repository": REPOSITORY,
            "visibility": "PUBLIC",
            "branch": "main",
            "push_required_after_commit": True,
        }
    ):
        raise ValueError("Task 4 acceptance manifest semantics changed")
    for label, path, digest in (
        ("Task 4 closure", TASK4_CLOSURE_PATH, TASK4_CLOSURE_SHA256),
        ("Task 5 entry gate", TASK5_ENTRY_GATE_PATH, TASK5_ENTRY_GATE_SHA256),
        ("Task 5 red record", TASK5_RED_RECORD_PATH, TASK5_RED_RECORD_SHA256),
        ("Task 5 red log", TASK5_RED_LOG_PATH, TASK5_RED_LOG_SHA256),
        (
            "Task 5 rejected green log",
            TASK5_REJECTED_GREEN_LOG_PATH,
            TASK5_REJECTED_GREEN_LOG_SHA256,
        ),
        (
            "Task 5 adversarial pause",
            TASK5_ADVERSARIAL_PAUSE_PATH,
            TASK5_ADVERSARIAL_PAUSE_SHA256,
        ),
        (
            "Task 5 corrected repair green log",
            TASK5_REPAIR_GREEN_LOG_PATH,
            TASK5_REPAIR_GREEN_LOG_SHA256,
        ),
        (
            "Task 5 corrected repair record",
            TASK5_REPAIR_RECORD_PATH,
            TASK5_REPAIR_RECORD_SHA256,
        ),
        (
            "Task 5 cross-audit pause",
            TASK5_CROSS_AUDIT_PAUSE_PATH,
            TASK5_CROSS_AUDIT_PAUSE_SHA256,
        ),
        (
            "Task 5 risk-wrapper pause",
            TASK5_RISK_WRAPPER_PAUSE_PATH,
            TASK5_RISK_WRAPPER_PAUSE_SHA256,
        ),
        (
            "Task 5 runtime-provenance pause",
            TASK5_RUNTIME_PROVENANCE_PAUSE_PATH,
            TASK5_RUNTIME_PROVENANCE_PAUSE_SHA256,
        ),
        (
            "Task 5 parent-binding candidate failure",
            TASK5_PARENT_BINDING_FAILURE_RECORD_PATH,
            TASK5_PARENT_BINDING_FAILURE_RECORD_SHA256,
        ),
        (
            "Task 5 targeted-repair preflight failure",
            TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_SHA256,
        ),
        (
            "Task 5 parent-binding targeted repair",
            TASK5_PARENT_BINDING_REPAIR_RECORD_PATH,
            TASK5_PARENT_BINDING_REPAIR_RECORD_SHA256,
        ),
        (
            "Task 5 manifest-build canonical-equivalence failure",
            TASK5_MANIFEST_BUILD_FAILURE_RECORD_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_RECORD_SHA256,
        ),
    ):
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"{label} bytes changed or are unavailable")
    try:
        task4_closure = json.loads(
            TASK4_CLOSURE_PATH.read_bytes(),
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
        adversarial_pause = json.loads(
            TASK5_ADVERSARIAL_PAUSE_PATH.read_bytes(),
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            "Task 5 prior closure/pause evidence is not strict JSON"
        ) from exc
    if (
        type(task4_closure) is not dict
        or task4_closure.get("task") != 4
        or task4_closure.get("status") != "CLOSED_ACCEPTED_PUSHED_PUBLIC"
        or task4_closure.get("contract_sha256") != CONTRACT_SHA256
        or not isinstance(task4_closure.get("commit"), dict)
        or task4_closure["commit"].get("sha") != TASK4_ACCEPTANCE_COMMIT
        or not isinstance(task4_closure.get("github"), dict)
        or task4_closure["github"].get("visibility") != "PUBLIC"
        or task4_closure["github"].get("repository") != REPOSITORY
    ):
        raise ValueError("Task 4 accepted closure semantics changed")
    if (
        type(adversarial_pause) is not dict
        or adversarial_pause.get("status")
        != "PAUSED_FOR_FAIL_CLOSED_REPAIR"
    ):
        raise ValueError("Task 5 adversarial pause status changed")
    try:
        repair_record = json.loads(
            TASK5_REPAIR_RECORD_PATH.read_bytes(),
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            "Task 5 corrected repair record is not strict JSON"
        ) from exc
    _validate_repair_record_status(repair_record)
    try:
        cross_audit = json.loads(
            TASK5_CROSS_AUDIT_PAUSE_PATH.read_bytes(),
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            "Task 5 cross-audit pause is not strict JSON"
        ) from exc
    if (
        type(cross_audit) is not dict
        or cross_audit.get("status")
        != "PAUSED_FOR_FORMAL_PROVENANCE_REPAIR"
    ):
        raise ValueError("Task 5 cross-audit pause status changed")
    for label, path, expected_status in (
        (
            "risk-wrapper",
            TASK5_RISK_WRAPPER_PAUSE_PATH,
            "PAUSED_FOR_RISK_WRAPPER_EXECUTION_CLOSURE_REPAIR",
        ),
        (
            "runtime-provenance",
            TASK5_RUNTIME_PROVENANCE_PAUSE_PATH,
            "PAUSED_FOR_PLANNER_RORC_CFA_PROVENANCE_REPAIR",
        ),
    ):
        try:
            pause = json.loads(
                path.read_bytes(),
                object_pairs_hook=_reject_duplicate_object_pairs,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(
                f"Task 5 {label} pause is not strict JSON"
            ) from exc
        if type(pause) is not dict or pause.get("status") != expected_status:
            raise ValueError(f"Task 5 {label} pause status changed")

    parent_binding_failure = _load_canonical_json(
        TASK5_PARENT_BINDING_FAILURE_RECORD_PATH,
        label="Task 5 parent-binding candidate failure",
    )
    expected_artifacts = {
        "run_log": {
            "path": str(TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH),
            "sha256": TASK5_PARENT_BINDING_FAILURE_RUN_LOG_SHA256,
        },
        "evaluation_junit": {
            "path": str(
                TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_PATH
            ),
            "sha256": TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_SHA256,
            "status": "AVAILABLE_PASSED_NOT_ACCEPTANCE",
        },
        "combined_junit": {
            "path": str(TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_PATH),
            "sha256": TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_SHA256,
            "status": "AVAILABLE_FAILED",
        },
        "full_junit": {"status": "NOT_PRODUCED"},
        "source_index_snapshot": {
            "path": str(TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_PATH),
            "sha256": TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_SHA256,
        },
        "runtime_dependency_snapshot": {
            "path": str(TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_PATH),
            "sha256": TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_SHA256,
        },
        "source_index_post_test": {"status": "NOT_PRODUCED"},
    }
    expected_failure_records = [
        {
            "node_id": node_id,
            "observed_cause": (
                "parent Task 4 dependency digest is unavailable"
            ),
        }
        for node_id in TASK5_PARENT_BINDING_FAILURE_NODE_IDS
    ]
    if (
        parent_binding_failure.get("schema")
        != "d2t_rna.task5_candidate_failure_record.v1"
        or parent_binding_failure.get("task") != 5
        or parent_binding_failure.get("run_id")
        != "task5-acceptance-20260730T201740+0800"
        or parent_binding_failure.get("status")
        != "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE"
        or parent_binding_failure.get("contract_sha256") != CONTRACT_SHA256
        or parent_binding_failure.get("run_terminal") is not True
        or parent_binding_failure.get("task_terminal") is not False
        or parent_binding_failure.get("acceptance_authorized") is not False
        or parent_binding_failure.get("artifacts") != expected_artifacts
        or parent_binding_failure.get("test_results")
        != {
            "evaluation": {
                "status": "PASSED_NOT_ACCEPTANCE",
                "tests": 109,
                "passed": 109,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
            },
            "combined": {
                "status": "FAILED",
                "tests": 422,
                "passed": 416,
                "failures": 6,
                "errors": 0,
                "skipped": 0,
            },
            "full": {"status": "NOT_RUN"},
        }
        or parent_binding_failure.get("failures")
        != expected_failure_records
        or parent_binding_failure.get("failure")
        != {
            "diagnosis": (
                "TASK5_RUNNERS_DID_NOT_EXPORT_PREFROZEN_PARENT_TASK4_DIGESTS"
            ),
            "exit_code": 1,
            "root_cause_status": "DIAGNOSED_REPAIR_REQUIRED",
            "stage": "pytest_combined",
            "terminal_log_marker": (
                "TASK5_CANDIDATE_FAILED_STAGE=pytest_combined EXIT_CODE=1"
            ),
        }
    ):
        raise ValueError(
            "Task 5 parent-binding candidate failure semantics changed"
        )
    for label, path, digest in (
        (
            "parent-binding failure run log",
            TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH,
            TASK5_PARENT_BINDING_FAILURE_RUN_LOG_SHA256,
        ),
        (
            "parent-binding failure evaluation JUnit",
            TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_PATH,
            TASK5_PARENT_BINDING_FAILURE_EVALUATION_JUNIT_SHA256,
        ),
        (
            "parent-binding failure combined JUnit",
            TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_PATH,
            TASK5_PARENT_BINDING_FAILURE_COMBINED_JUNIT_SHA256,
        ),
        (
            "parent-binding failure source snapshot",
            TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_PATH,
            TASK5_PARENT_BINDING_FAILURE_SOURCE_SNAPSHOT_SHA256,
        ),
        (
            "parent-binding failure runtime snapshot",
            TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_PATH,
            TASK5_PARENT_BINDING_FAILURE_RUNTIME_SNAPSHOT_SHA256,
        ),
    ):
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"Task 5 {label} bytes changed or are unavailable")
    run_log = TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH.read_text(
        encoding="utf-8"
    )
    if (
        run_log.count(
            "TASK5_CANDIDATE_FAILED_STAGE=pytest_combined EXIT_CODE=1"
        )
        != 1
        or "6 failed, 416 passed" not in run_log
        or "TASK5_CANDIDATE_PASS" in run_log
        or (
            TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH.parent
            / "junit"
            / "full.xml"
        ).exists()
        or (
            TASK5_PARENT_BINDING_FAILURE_RUN_LOG_PATH.parent
            / "snapshots"
            / "source_index_post_test.json"
        ).exists()
    ):
        raise ValueError(
            "Task 5 parent-binding candidate failure transcript changed"
        )

    targeted_preflight_failure = _load_canonical_json(
        TASK5_TARGETED_PREFLIGHT_FAILURE_RECORD_PATH,
        label="Task 5 targeted-repair preflight failure",
    )
    expected_targeted_evidence = {
        "parent_binding": {
            "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_PATH),
            "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_SHA256,
        },
        "run_log": {
            "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_PATH),
            "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_SHA256,
        },
        "runner": {
            "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_PATH),
            "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_SHA256,
        },
        "runtime_snapshot": {
            "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_PATH),
            "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_SHA256,
        },
        "source_snapshot": {
            "path": str(TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_PATH),
            "sha256": TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_SHA256,
        },
    }
    if (
        targeted_preflight_failure.get("schema")
        != "d2t_rna.task5_targeted_repair_failure.v1"
        or targeted_preflight_failure.get("run_id")
        != "task5-parent-binding-repair-20260731T052401+0800"
        or targeted_preflight_failure.get("status")
        != "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE"
        or targeted_preflight_failure.get("stage")
        != "historical_failure_replay"
        or targeted_preflight_failure.get("exit_code") != 1
        or targeted_preflight_failure.get("tests_executed") is not False
        or targeted_preflight_failure.get("acceptance_authorized") is not False
        or targeted_preflight_failure.get("scientific_conclusion_authorized")
        is not False
        or targeted_preflight_failure.get("cause")
        != "TASK5_RED_LOG_REGISTERED_PATH_MISMATCH"
        or targeted_preflight_failure.get("expected_registered_path")
        != (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-red-20260730T165809p0800/evaluation.log"
        )
        or targeted_preflight_failure.get("actual_path")
        != str(TASK5_RED_LOG_PATH)
        or targeted_preflight_failure.get("expected_sha256")
        != TASK5_RED_LOG_SHA256
        or targeted_preflight_failure.get("actual_sha256")
        != TASK5_RED_LOG_SHA256
        or targeted_preflight_failure.get("next_action")
        != "CORRECT_ONLY_THE_REGISTERED_PATH_THEN_RERUN_IN_A_FRESH_DIRECTORY"
        or targeted_preflight_failure.get("evidence")
        != expected_targeted_evidence
    ):
        raise ValueError(
            "Task 5 targeted-repair preflight failure semantics changed"
        )
    for label, path, digest in (
        (
            "targeted-repair runner",
            TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_RUNNER_SHA256,
        ),
        (
            "targeted-repair failure log",
            TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_SHA256,
        ),
        (
            "targeted-repair runtime snapshot",
            TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_RUNTIME_SHA256,
        ),
        (
            "targeted-repair source snapshot",
            TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_SOURCE_SHA256,
        ),
        (
            "targeted-repair parent binding",
            TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_PATH,
            TASK5_TARGETED_PREFLIGHT_FAILURE_BINDING_SHA256,
        ),
    ):
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise ValueError(f"Task 5 {label} bytes changed or are unavailable")
    targeted_log = TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_PATH.read_text(
        encoding="utf-8"
    )
    if (
        targeted_log.count(
            "TASK5_TARGETED_REPAIR_FAILED_STAGE="
            "historical_failure_replay EXIT_CODE=1"
        )
        != 1
        or "Task 5 red log bytes changed or are unavailable" not in targeted_log
        or "passed in" in targeted_log
        or (
            TASK5_TARGETED_PREFLIGHT_FAILURE_LOG_PATH.parent
            / "junit"
            / "targeted.xml"
        ).exists()
    ):
        raise ValueError(
            "Task 5 targeted-repair preflight failure transcript changed"
        )

    parent_binding_repair = _load_canonical_json(
        TASK5_PARENT_BINDING_REPAIR_RECORD_PATH,
        label="Task 5 parent-binding targeted repair",
    )
    expected_repair_artifacts = {
        "junit": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_JUNIT_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_JUNIT_SHA256,
        },
        "parent_binding": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_BINDING_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_BINDING_SHA256,
        },
        "post_source_snapshot": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_SHA256,
        },
        "run_log": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_LOG_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_LOG_SHA256,
        },
        "runner": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_RUNNER_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_RUNNER_SHA256,
        },
        "runtime_snapshot": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_RUNTIME_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_RUNTIME_SHA256,
        },
        "source_snapshot": {
            "path": str(TASK5_PARENT_BINDING_REPAIR_SOURCE_PATH),
            "sha256": TASK5_PARENT_BINDING_REPAIR_SOURCE_SHA256,
        },
    }
    expected_parent_binding = {
        "dependency_snapshot_sha256": (
            "f7ad6b454f64ce2d3174a01023f5a40e"
            "f88fd3c99e1d0dd38c939a13da18d26e"
        ),
        "source_index_sha256": (
            "355d452bda9fd59cda6e4f88ba138cf"
            "ce14f10097a825a54f9ed70b3f4abd134"
        ),
    }
    if (
        set(parent_binding_repair)
        != {
            "acceptance_authorized",
            "artifacts",
            "historical_failure_replay_passed",
            "parent_binding",
            "run_id",
            "schema",
            "scientific_conclusion_authorized",
            "source_stability",
            "status",
            "terminal_marker",
            "test_results",
        }
        or parent_binding_repair.get("schema")
        != "d2t_rna.task5_targeted_repair_record.v1"
        or parent_binding_repair.get("run_id")
        != "task5-parent-binding-repair-20260731T053556+0800"
        or parent_binding_repair.get("status")
        != "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"
        or parent_binding_repair.get("acceptance_authorized") is not False
        or parent_binding_repair.get("scientific_conclusion_authorized")
        is not False
        or parent_binding_repair.get("historical_failure_replay_passed")
        is not True
        or parent_binding_repair.get("parent_binding")
        != expected_parent_binding
        or parent_binding_repair.get("source_stability")
        != {
            "post_sha256": TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_SHA256,
            "pre_sha256": TASK5_PARENT_BINDING_REPAIR_SOURCE_SHA256,
            "stable": True,
        }
        or parent_binding_repair.get("test_results")
        != {
            "errors": 0,
            "failures": 0,
            "passed": 6,
            "skipped": 0,
            "tests": 6,
        }
        or parent_binding_repair.get("terminal_marker")
        != (
            "TASK5_TARGETED_REPAIR_STATUS="
            "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"
        )
        or parent_binding_repair.get("artifacts")
        != expected_repair_artifacts
    ):
        raise ValueError(
            "Task 5 parent-binding targeted repair semantics changed"
        )
    _validate_repair_record_status(parent_binding_repair)
    for label, artifact_name, expected_path, expected_digest in (
        (
            "parent-binding repair JUnit",
            "junit",
            TASK5_PARENT_BINDING_REPAIR_JUNIT_PATH,
            TASK5_PARENT_BINDING_REPAIR_JUNIT_SHA256,
        ),
        (
            "parent-binding repair binding",
            "parent_binding",
            TASK5_PARENT_BINDING_REPAIR_BINDING_PATH,
            TASK5_PARENT_BINDING_REPAIR_BINDING_SHA256,
        ),
        (
            "parent-binding repair post-source snapshot",
            "post_source_snapshot",
            TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_PATH,
            TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_SHA256,
        ),
        (
            "parent-binding repair log",
            "run_log",
            TASK5_PARENT_BINDING_REPAIR_LOG_PATH,
            TASK5_PARENT_BINDING_REPAIR_LOG_SHA256,
        ),
        (
            "parent-binding repair runner",
            "runner",
            TASK5_PARENT_BINDING_REPAIR_RUNNER_PATH,
            TASK5_PARENT_BINDING_REPAIR_RUNNER_SHA256,
        ),
        (
            "parent-binding repair runtime snapshot",
            "runtime_snapshot",
            TASK5_PARENT_BINDING_REPAIR_RUNTIME_PATH,
            TASK5_PARENT_BINDING_REPAIR_RUNTIME_SHA256,
        ),
        (
            "parent-binding repair source snapshot",
            "source_snapshot",
            TASK5_PARENT_BINDING_REPAIR_SOURCE_PATH,
            TASK5_PARENT_BINDING_REPAIR_SOURCE_SHA256,
        ),
    ):
        _verify_external_file(
            expected_repair_artifacts[artifact_name],
            root=ARTIFACT_ROOT,
            label=label,
            expected_path=expected_path,
            expected_sha256=expected_digest,
        )
    binding_artifact = _load_canonical_json(
        TASK5_PARENT_BINDING_REPAIR_BINDING_PATH,
        label="Task 5 parent-binding repair binding",
    )
    if binding_artifact != {
        "schema": TASK4_NESTED_PARENT_BINDING_SCHEMA,
        **expected_parent_binding,
    }:
        raise ValueError(
            "Task 5 parent-binding repair digest domain changed"
        )
    if (
        TASK5_PARENT_BINDING_REPAIR_SOURCE_PATH.read_bytes()
        != TASK5_PARENT_BINDING_REPAIR_POST_SOURCE_PATH.read_bytes()
    ):
        raise ValueError(
            "Task 5 parent-binding repair source stability changed"
        )
    _verify_junit(
        TASK5_PARENT_BINDING_REPAIR_JUNIT_PATH,
        expected_count=6,
        label="Task 5 parent-binding repair JUnit",
    )
    repair_log = TASK5_PARENT_BINDING_REPAIR_LOG_PATH.read_text(
        encoding="utf-8"
    )
    if (
        repair_log.count("6 passed in 349.36s (0:05:49)") != 1
        or repair_log.count(
            "TASK5_PARENT_BINDING_FAILURE_EVIDENCE_REPLAY_PASS"
        )
        != 1
        or repair_log.count(
            "TASK5_TARGETED_REPAIR_STATUS="
            "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"
        )
        != 1
        or repair_log.count("TASK5_TARGETED_REPAIR_IS_ACCEPTANCE=false") != 1
        or "failed" in repair_log.lower()
    ):
        raise ValueError(
            "Task 5 parent-binding targeted repair transcript changed"
        )

    manifest_build_failure = _load_canonical_json(
        TASK5_MANIFEST_BUILD_FAILURE_RECORD_PATH,
        label="Task 5 manifest-build canonical-equivalence failure",
    )
    _validate_manifest_build_failure_record(manifest_build_failure)
    failure_evidence = manifest_build_failure["evidence"]
    for label, artifact_name, expected_path, expected_digest in (
        (
            "manifest-build failure log",
            "build_log",
            TASK5_MANIFEST_BUILD_FAILURE_LOG_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_LOG_SHA256,
        ),
        (
            "manifest-build failure candidate post-source snapshot",
            "candidate_post_source_snapshot",
            TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_SHA256,
        ),
        (
            "manifest-build failure candidate run log",
            "candidate_run_log",
            TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_SHA256,
        ),
        (
            "manifest-build failure candidate source snapshot",
            "candidate_source_snapshot",
            TASK5_MANIFEST_BUILD_FAILURE_SOURCE_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_SOURCE_SHA256,
        ),
        (
            "manifest-build failure exit code",
            "exit_code",
            TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_PATH,
            TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_SHA256,
        ),
    ):
        _verify_external_file(
            failure_evidence[artifact_name],
            root=ARTIFACT_ROOT,
            label=label,
            expected_path=expected_path,
            expected_sha256=expected_digest,
        )
    _verify_external_file(
        {
            "path": str(TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_PATH),
            "sha256": TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_SHA256,
        },
        root=ARTIFACT_ROOT,
        label="manifest-build failure candidate runtime snapshot",
        expected_path=TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_PATH,
        expected_sha256=TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_SHA256,
    )
    source_snapshot = _load_canonical_json(
        TASK5_MANIFEST_BUILD_FAILURE_SOURCE_PATH,
        label="manifest-build failure candidate source snapshot",
    )
    post_source_snapshot = _load_canonical_json(
        TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_PATH,
        label="manifest-build failure candidate post-source snapshot",
    )
    runtime_snapshot = _load_canonical_json(
        TASK5_MANIFEST_BUILD_FAILURE_RUNTIME_PATH,
        label="manifest-build failure candidate runtime snapshot",
    )
    canonical_equality = manifest_build_failure["canonical_equality"]
    if (
        TASK5_MANIFEST_BUILD_FAILURE_SOURCE_PATH.read_bytes()
        != TASK5_MANIFEST_BUILD_FAILURE_POST_SOURCE_PATH.read_bytes()
        or canonical_sha256(source_snapshot)
        != canonical_equality["source_snapshot_object_sha256"]
        or source_snapshot.get("source_index_sha256")
        != canonical_equality["source_snapshot_source_index_sha256"]
        or canonical_sha256(source_snapshot.get("source_index"))
        != canonical_equality["source_snapshot_source_index_sha256"]
        or canonical_sha256(runtime_snapshot)
        != canonical_equality["runtime_snapshot_sha256"]
    ):
        raise ValueError(
            "Task 5 manifest-build canonical equality evidence changed"
        )
    build_log = TASK5_MANIFEST_BUILD_FAILURE_LOG_PATH.read_text(
        encoding="utf-8"
    )
    candidate_log = (
        TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_PATH.read_text(
            encoding="utf-8"
        )
    )
    if (
        build_log.count(
            "ValueError: Task 5 candidate source snapshot changed"
        )
        != 1
        or "TASK5_ACCEPTANCE_MANIFEST_SHA256=" in build_log
        or TASK5_MANIFEST_BUILD_FAILURE_EXIT_CODE_PATH.read_bytes() != b"1\n"
        or candidate_log.count("TASK5_CANDIDATE_PASS") != 1
        or candidate_log.count(
            "115 passed in 13791.83s (3:49:51)"
        )
        != 1
        or candidate_log.count(
            "428 passed in 15728.38s (4:22:08)"
        )
        != 1
        or candidate_log.count(
            "543 passed in 16379.35s (4:32:59)"
        )
        != 1
        or "TASK5_CANDIDATE_FAILED_STAGE=" in candidate_log
        or (
            TASK5_MANIFEST_BUILD_FAILURE_CANDIDATE_LOG_PATH.parent
            / "task5_acceptance_manifest.draft.json"
        ).exists()
    ):
        raise ValueError(
            "Task 5 manifest-build failure transcript changed"
        )


def _validate_repair_record_status(record: object) -> None:
    """Require the one frozen non-acceptance status, without substring logic."""

    if (
        type(record) is not dict
        or record.get("status")
        != "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"
    ):
        raise ValueError(
            "Task 5 corrected repair evidence was promoted to acceptance"
        )


def _unique_line_position(lines: list[str], marker: str) -> int:
    positions = [index for index, line in enumerate(lines) if line == marker]
    if len(positions) != 1:
        raise ValueError(
            f"Task 5 log requires exactly one {marker!r}"
        )
    return positions[0]


def _summary_between(lines: list[str], begin: str, end: str) -> int:
    begin_index = _unique_line_position(lines, begin)
    end_index = _unique_line_position(lines, end)
    if begin_index >= end_index:
        raise ValueError(f"Task 5 log stage is reversed: {begin}")
    matches = tuple(
        match
        for line in lines[begin_index + 1 : end_index]
        if (match := PYTEST_SUMMARY.fullmatch(line))
    )
    if len(matches) != 1:
        raise ValueError(
            "Task 5 log stage must contain exactly one pytest summary: "
            f"{begin}"
        )
    return int(matches[0].group(1))


def _verify_test_log(
    path: Path,
    *,
    run_id: str,
    runtime: dict[str, object],
    dependency_snapshot_sha256: str,
    source_index_sha256: str,
    task4_parent_dependency_snapshot_sha256: str,
    task4_parent_source_index_sha256: str,
    fixture_manifest_sha256: str,
    expected_counts: tuple[int, int, int],
    artifact_root: Path = ARTIFACT_ROOT,
    final: bool = False,
) -> tuple[int, int, int]:
    _validate_run_id(run_id) if not final else _validate_final_run_id(run_id)
    checked = _path_within(
        path,
        artifact_root,
        label="Task 5 acceptance log",
    )
    expected_log = artifact_root / "runs" / run_id / "run.log"
    if checked != expected_log.resolve():
        raise ValueError("Task 5 acceptance log is not bound to its run ID")
    pycache = artifact_root / "runs" / run_id / "pycache"
    if pycache.is_symlink() or not pycache.is_dir():
        raise ValueError("Task 5 Python isolation directory is unavailable")
    implementation = runtime.get("implementation")
    python_version = runtime.get("python_version")
    if (
        implementation != "CPython"
        or type(python_version) is not str
        or re.fullmatch(r"3\.11\.[0-9]+", python_version) is None
    ):
        raise ValueError("Task 5 runtime must be CPython 3.11")
    dependency = _require_sha(
        dependency_snapshot_sha256,
        label="Task 5 dependency snapshot",
    )
    source = _require_sha(
        source_index_sha256,
        label="Task 5 source index",
    )
    task4_parent_dependency = _require_sha(
        task4_parent_dependency_snapshot_sha256,
        label="Task 5 nested Task 4 parent dependency snapshot",
    )
    task4_parent_source = _require_sha(
        task4_parent_source_index_sha256,
        label="Task 5 nested Task 4 parent source index",
    )
    fixture = _require_sha(
        fixture_manifest_sha256,
        label="Task 5 fixture manifest",
    )
    if (
        type(expected_counts) is not tuple
        or len(expected_counts) != 3
        or any(type(item) is not int for item in expected_counts)
        or any(
            observed < minimum
            for observed, minimum in zip(
                expected_counts,
                MINIMUM_TEST_COUNTS,
                strict=True,
            )
        )
        or expected_counts[0] > expected_counts[1]
        or expected_counts[1] > expected_counts[2]
    ):
        raise ValueError("Task 5 test counts do not satisfy the gate")

    lines = checked.read_text(encoding="utf-8").splitlines()
    header = (
        "TASK5_FINAL_RUNNER_SCHEMA=d2t_rna.task5_final_runner.v1"
        if final
        else "TASK5_CANDIDATE_RUNNER_SCHEMA="
        "d2t_rna.task5_candidate_runner.v1"
    )
    run_marker = (
        f"TASK5_FINAL_RUN_ID={run_id}"
        if final
        else f"TASK5_RUN_ID={run_id}"
    )
    exact_markers = (
        header,
        run_marker,
        f"TASK5_RUNTIME=CPython {python_version}",
        f"TASK5_CONTRACT_SHA256={CONTRACT_SHA256}",
        f"TASK5_TASK4_ACCEPTANCE_COMMIT={TASK4_ACCEPTANCE_COMMIT}",
        (
            "TASK5_TASK4_ACCEPTANCE_MANIFEST_SHA256="
            f"{TASK4_ACCEPTANCE_MANIFEST_SHA256}"
        ),
        f"TASK5_TASK4_CLOSURE_SHA256={TASK4_CLOSURE_SHA256}",
        f"TASK5_DEPENDENCY_SNAPSHOT_SHA256={dependency}",
        (
            "TASK5_TASK4_PARENT_DEPENDENCY_SNAPSHOT_SHA256="
            f"{task4_parent_dependency}"
        ),
        (
            "TASK5_TASK4_PARENT_SOURCE_INDEX_SHA256="
            f"{task4_parent_source}"
        ),
        (
            "TASK5_PYTHON_ISOLATION_PASS="
            f"{artifact_root / 'runs' / run_id / 'pycache'}"
        ),
        f"TASK5_PRE_TEST_SOURCE_INDEX_SHA256={source}",
        "TASK5_COMPILE_PASS",
        "TASK5_EVALUATION_TESTS_BEGIN",
        "TASK5_EVALUATION_TESTS_END",
        "TASK5_COMBINED_TESTS_BEGIN",
        "TASK5_COMBINED_TESTS_END",
        "TASK5_FULL_TESTS_BEGIN",
        "TASK5_FULL_TESTS_END",
        f"TASK5_FIXTURE_MANIFEST_SHA256={fixture}",
        f"TASK5_POST_TEST_SOURCE_INDEX_SHA256={source}",
        "TASK5_GIT_DIFF_CHECK_PASS",
        "TASK5_EXISTING_MANIFEST_JSON_PASS",
    )
    if final:
        exact_markers += (
            "TASK5_MANIFEST_VERIFIED",
            "TASK5_LIVE_MANIFEST_REPLAY_PASS",
        )
    exact_markers += (
        "TASK5_SECRET_AUDIT_PASS",
        "TASK5_LARGE_FILE_AUDIT_PASS",
        "TASK5_ACCEPTANCE_PASS" if final else "TASK5_CANDIDATE_PASS",
    )
    positions = tuple(_unique_line_position(lines, item) for item in exact_markers)
    if positions != tuple(sorted(positions)):
        raise ValueError("Task 5 acceptance transcript is out of order")
    if not lines or lines[0] != header or lines[-1] != exact_markers[-1]:
        raise ValueError("Task 5 acceptance transcript is not terminal")
    failure_fragments = (
        " failed",
        " errors",
        " skipped",
        " xfailed",
        " xpassed",
    )
    if any(
        line.startswith(
            (
                "FAILED ",
                "ERROR ",
                "Traceback ",
                "TASK5_CANDIDATE_FAILED_STAGE=",
            )
        )
        or any(fragment in line for fragment in failure_fragments)
        for line in lines
    ):
        raise ValueError("Task 5 acceptance transcript contains failure marker")
    summaries = (
        _summary_between(
            lines,
            "TASK5_EVALUATION_TESTS_BEGIN",
            "TASK5_EVALUATION_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK5_COMBINED_TESTS_BEGIN",
            "TASK5_COMBINED_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK5_FULL_TESTS_BEGIN",
            "TASK5_FULL_TESTS_END",
        ),
    )
    all_summary_lines = tuple(
        line for line in lines if PYTEST_SUMMARY.fullmatch(line)
    )
    if len(all_summary_lines) != 3:
        raise ValueError(
            "Task 5 acceptance transcript must contain exactly three "
            "pytest summaries"
        )
    if summaries != expected_counts:
        raise ValueError("Task 5 acceptance test counts changed")
    return summaries


def _verify_junit(path: Path, *, expected_count: int, label: str) -> None:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise ValueError(f"{label} is not valid JUnit XML") from exc
    suites = (
        (root,)
        if root.tag == "testsuite"
        else tuple(root.findall("testsuite"))
    )
    if not suites:
        raise ValueError(f"{label} has no testsuite")
    totals = {"tests": 0, "errors": 0, "failures": 0, "skipped": 0}
    for suite in suites:
        for name in totals:
            raw = suite.attrib.get(name, "0")
            if re.fullmatch(r"[0-9]+", raw) is None:
                raise ValueError(f"{label} {name} count is malformed")
            totals[name] += int(raw)
    if totals["tests"] != expected_count:
        raise ValueError(f"{label} test count differs from run log")
    testcases = tuple(root.iter("testcase"))
    if len(testcases) != expected_count:
        raise ValueError(f"{label} testcase count differs from aggregate")
    for name in ("errors", "failures", "skipped"):
        if totals[name]:
            raise ValueError(f"{label} contains {name}")
    if any(
        testcase.find("failure") is not None
        or testcase.find("error") is not None
        or testcase.find("skipped") is not None
        for testcase in testcases
    ):
        raise ValueError(f"{label} contains non-passing testcase evidence")


def _parse_model_json(path: Path, model_type: type, *, label: str):
    _load_canonical_json(path, label=label)
    try:
        return model_type.model_validate_json(
            path.read_bytes(),
            strict=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} failed structural replay: {exc}") from exc


def _parse_rorc_metrics(path: Path) -> RorcStressMetrics:
    """Use an explicit strict decoder for the pre-validated reason enum."""

    raw = _load_canonical_json(path, label="RORC metrics")
    try:
        case_manifest = raw["case_manifest"]
        if type(case_manifest) is not dict:
            raise TypeError("case_manifest must be an object")
        raw_cases = case_manifest["cases"]
        if type(raw_cases) is not list or not raw_cases:
            raise TypeError("cases must be a non-empty array")
        decoded_cases: list[dict[str, object]] = []
        for position, raw_case in enumerate(raw_cases):
            if type(raw_case) is not dict:
                raise TypeError(f"cases[{position}] must be an object")
            decision = raw_case.get("observed_decision")
            reasons = raw_case.get("reasons")
            if type(decision) is not str or type(reasons) is not list:
                raise TypeError(
                    f"cases[{position}] enum fields are malformed"
                )
            if any(type(reason) is not str for reason in reasons):
                raise TypeError(
                    f"cases[{position}] reasons are malformed"
                )
            decoded_cases.append(
                {
                    **raw_case,
                    "observed_decision": RorcObservedDecision(decision),
                    "reasons": tuple(RorcReason(reason) for reason in reasons),
                }
            )
        decoded = {
            **raw,
            "case_manifest": {
                **case_manifest,
                "cases": tuple(decoded_cases),
            },
        }
        return RorcStressMetrics.model_validate(decoded, strict=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"RORC metrics failed registered JSON replay: {exc}"
        ) from exc


def verify_fixture(
    project_root: Path,
    manifest_path: Path,
    *,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    del project_root  # All execution-code binding is carried by source_index.
    checked_path = _path_within(
        manifest_path,
        artifact_root,
        label="Task 5 fixture manifest",
    )
    raw = _load_canonical_json(
        checked_path,
        label="Task 5 fixture manifest",
    )
    expected_fields = {
        "schema",
        "fixture_id",
        "contract_sha256",
        "artifacts",
        "replay",
        "claim_boundary",
    }
    if set(raw) != expected_fields:
        raise ValueError("Task 5 fixture manifest fields changed")
    if (
        raw["schema"] != FIXTURE_SCHEMA
        or raw["fixture_id"] != "task5.registered.synthetic-microcase.v1"
        or raw["contract_sha256"] != CONTRACT_SHA256
        or raw["claim_boundary"] != CLAIM_BOUNDARY
    ):
        raise ValueError("Task 5 fixture authority or claim boundary changed")
    artifacts = raw["artifacts"]
    if type(artifacts) is not dict or set(artifacts) != EXPECTED_FIXTURE_ARTIFACTS:
        raise ValueError("Task 5 fixture artifact registry changed")
    fixture_dir = checked_path.parent
    loaded: dict[str, object] = {}
    for name in sorted(EXPECTED_FIXTURE_ARTIFACTS):
        record = artifacts[name]
        expected_path = fixture_dir / f"{name}.json"
        path = _verify_external_file(
            record,
            root=artifact_root,
            label=f"Task 5 fixture {name}",
            expected_path=expected_path,
        )
        loaded[name] = path

    library = _parse_model_json(
        loaded["available_control_library_check"],
        MilpCheckReceipt,
        label="available-control checker receipt",
    )
    design = _parse_model_json(
        loaded["registered_design_class_check"],
        MilpCheckReceipt,
        label="registered-design checker receipt",
    )
    scenario = _parse_model_json(
        loaded["scenario_aggregate"],
        FiniteScenarioCoverageAggregate,
        label="scenario aggregate",
    )
    replay_finite_scenario_aggregate(scenario)
    if (
        scenario.formal_guarantee is not True
        or scenario.coverage_disposition
        is not ScenarioCoverageDisposition.FORMAL_REGISTERED_SCENARIO_COVERAGE
        or any(
            manifest.formal_guarantee is not True
            or type(manifest.proof_artifact)
            is not ExactSyntheticScenarioProofArtifact
            or manifest.coverage_disposition
            is not (
                ScenarioCoverageDisposition
                .FORMAL_REGISTERED_SCENARIO_COVERAGE
            )
            for manifest in scenario.per_scenario_proof_manifest
        )
    ):
        raise ValueError(
            "Task 5 fixture scenario is not formal raw Task 4 replay"
        )
    risk_bundle = _parse_model_json(
        loaded["risk_certificate_replay_bundle"],
        RiskCertificateReplayBundle,
        label="risk certificate replay bundle",
    )
    replay_risk_certificate_replay_bundle(risk_bundle)
    if (
        risk_bundle.schema_version != "3.0"
        or risk_bundle.task2_semantic_evaluator_replayed is not True
        or risk_bundle.task5_risk_binding_evaluator_replayed is not True
        or re.fullmatch(
            r"[0-9a-f]{64}",
            risk_bundle.task2_semantic_evaluator_execution_sha256,
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            risk_bundle.task5_risk_binding_evaluator_execution_sha256,
        )
        is None
        or risk_bundle.certificate_issued is not False
        or risk_bundle.scientific_claim_authorized is not False
        or risk_bundle.serialized_bearer_authorization is not False
    ):
        raise ValueError(
            "Task 5 risk replay execution or authorization boundary changed"
        )
    assessment = _parse_model_json(
        loaded["coverage_feasibility_assessment"],
        CoverageFeasibilityAssessment,
        label="coverage feasibility assessment",
    )
    replay_bounded_milp_check(assessment.model, library)
    replay_bounded_milp_check(assessment.model, design)
    if assessment.risk_certificate_replay_bundle != risk_bundle:
        raise ValueError(
            "coverage assessment embeds a different risk replay bundle"
        )
    risk_probability_space_sha256 = canonical_sha256(
        risk_bundle.inputs.probability_space
    )
    formal_probability_space_sha256s = tuple(
        canonical_sha256(
            parse_contract_json(
                ExactParameterFamily,
                manifest.proof_artifact.family_json,
            ).probability_space
        )
        for manifest in scenario.per_scenario_proof_manifest
    )
    if (
        assessment.schema_version != "5.0"
        or assessment.cfa_binding_execution_replayed is not True
        or re.fullmatch(
            r"[0-9a-f]{64}",
            assessment.cfa_binding_execution_sha256,
        )
        is None
        or assessment.scenario_formal_guarantee is not True
        or assessment.risk_scenario_probability_space_binding_required
        is not True
        or assessment.risk_scenario_probability_space_binding_verified
        is not True
        or assessment.risk_probability_space_sha256
        != risk_probability_space_sha256
        or assessment.formal_scenario_probability_space_sha256s
        != formal_probability_space_sha256s
        or any(
            digest != risk_probability_space_sha256
            for digest in formal_probability_space_sha256s
        )
        or assessment.serialized_bearer_authorization is not False
        or assessment.formal_scientific_certificate_authorized is not False
        or assessment.scientific_claim_authorized is not False
    ):
        raise ValueError(
            "Task 5 CFA execution, formal source, or probability binding changed"
        )
    replay_coverage_feasibility_assessment(
        assessment,
        assessment.model,
        assessment.planner_result,
        risk_certificate=assessment.risk_certificate,
        risk_certificate_replay_bundle=(
            assessment.risk_certificate_replay_bundle
        ),
        scenario_coverage_aggregate=scenario,
        yield_scope=assessment.yield_scope,
        cost_table=assessment.cost_table,
        expansion_order=assessment.expansion_order,
        available_control_library_check=library,
        registered_design_class_check=design,
    )
    comparison = _parse_model_json(
        loaded["baseline_comparison"],
        BaselineComparison,
        label="baseline comparison",
    )
    replay_baseline_comparison(comparison)
    expected_baseline_ids = tuple(
        specification.baseline_id
        for specification in (
            comparison.method_result.common_binding.required_baseline_registry
        )
    )
    if (
        comparison.schema_version != "3.0"
        or comparison.comparison_scope
        != "STRUCTURAL_HASH_BOUND_DECLARATIONS_ONLY"
        or comparison.baseline_ids != expected_baseline_ids
        or comparison.all_execution_artifacts_replayed is not False
        or comparison.all_outcomes_execution_verified is not False
        or comparison.release_claim_authorized is not False
        or comparison.formal_scientific_certificate_authorized is not False
        or comparison.scientific_claim_authorized is not False
        or comparison.serialized_bearer_authorization is not False
        or comparison.method_result.execution_artifact_replayed is not False
        or comparison.method_result.outcome_execution_verified is not False
        or comparison.method_result.release_claim_authorized is not False
        or comparison.method_result.scientific_claim_authorized is not False
        or comparison.method_result.serialized_bearer_authorization is not False
    ):
        raise ValueError("Task 5 baseline comparison boundary changed")
    for summary in comparison.baseline_summaries:
        batch = summary.batch
        if (
            summary.baseline_id not in expected_baseline_ids
            or summary.seed_count != 100
            or len(batch.results) != 100
            or summary.all_seed_execution_artifacts_replayed is not False
            or summary.all_seed_outcomes_execution_verified is not False
            or summary.release_claim_authorized is not False
            or summary.scientific_claim_authorized is not False
            or summary.serialized_bearer_authorization is not False
            or batch.all_seed_execution_artifacts_replayed is not False
            or batch.all_seed_outcomes_execution_verified is not False
            or batch.release_claim_authorized is not False
            or batch.scientific_claim_authorized is not False
            or batch.serialized_bearer_authorization is not False
            or any(
                result.execution_artifact_replayed is not False
                or result.outcome_execution_verified is not False
                or result.release_claim_authorized is not False
                or result.scientific_claim_authorized is not False
                or result.serialized_bearer_authorization is not False
                for result in batch.results
            )
        ):
            raise ValueError(
                "Task 5 required baseline seed or bearer boundary changed"
            )
    rorc = _parse_rorc_metrics(loaded["rorc_metrics"])
    replay_rorc_stress_metrics(rorc)
    rorc_path_audit = _parse_model_json(
        loaded["registered_rorc_path_audit"],
        RegisteredRorcPathAudit,
        label="registered RORC path audit",
    )
    if (
        rorc_path_audit.expected_path_count != 16
        or len(rorc_path_audit.path_replays) != 16
        or rorc_path_audit.all_registered_paths_abstain is not True
        or rorc_path_audit.registered_path_set_complete is not True
        or rorc_path_audit.paths_executed_via_assess_rorc is not True
        or rorc_path_audit.serialized_bearer_authorization is not False
    ):
        raise ValueError("Task 5 registered RORC path audit changed")
    replay = raw["replay"]
    expected_replay = {
        "all_registered_replays_passed": True,
        "scenario_count": len(scenario.per_scenario_proof_manifest),
        "baseline_seed_count": sum(
            len(summary.batch.results)
            for summary in comparison.baseline_summaries
        ),
        "rorc_observational_case_count": rorc.total_cases,
        "rorc_registered_path_count": rorc_path_audit.expected_path_count,
        "all_registered_rorc_paths_abstain": (
            rorc_path_audit.all_registered_paths_abstain
        ),
        "observed_case_set_all_abstain": (
            rorc.observed_case_set_all_abstain
        ),
        "risk_certificate_issued": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }
    if replay != expected_replay:
        raise ValueError("Task 5 fixture replay summary changed")
    return raw


def _git_environment() -> dict[str, str]:
    return {
        "HOME": "/nonexistent",
        "USER": "cunyuliu",
        "LOGNAME": "cunyuliu",
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def _run_git(project_root: Path, *argv: str) -> str:
    completed = subprocess.run(
        ("/usr/bin/git", *argv),
        cwd=project_root,
        env=_git_environment(),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _run_git_bytes(project_root: Path, *argv: str) -> bytes:
    completed = subprocess.run(
        ("/usr/bin/git", *argv),
        cwd=project_root,
        env=_git_environment(),
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _decode_nul_paths(raw: bytes, *, label: str) -> tuple[str, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise ValueError(f"{label} is not terminal NUL data")
    records = raw[:-1].split(b"\0")
    if any(not record for record in records):
        raise ValueError(f"{label} contains an empty record")
    try:
        paths = tuple(record.decode("utf-8", "strict") for record in records)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    if len(paths) != len(set(paths)):
        raise ValueError(f"{label} contains duplicate paths")
    return paths


def _validate_task5_delta_paths(paths: tuple[str, ...]) -> None:
    if not paths:
        raise ValueError("Task 5 changed-path set is empty")
    mandatory = {
        "src/d2t_rna/evaluation/scenario.py",
        "src/d2t_rna/evaluation/milp_check.py",
        "src/d2t_rna/evaluation/planner.py",
        "src/d2t_rna/evaluation/risk_binding.py",
        "src/d2t_rna/evaluation/baselines.py",
        "docs/audit/task-5-evaluation.md",
        "manifests/task5_acceptance.json",
    }
    missing = sorted(mandatory - set(paths))
    if missing:
        raise ValueError(f"Task 5 commit is missing required paths: {missing}")
    allowed_exact = {
        "README.md",
        "tests/exact/conftest.py",
        "tests/exact/test_acceptance_verifier.py",
        "tests/exact/test_task4_manifest_builder.py",
    }
    for relative in paths:
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or relative != pure.as_posix()
        ):
            raise ValueError("Task 5 changed path is not canonical")
        if relative in allowed_exact:
            continue
        if relative.startswith(
            (
                "src/d2t_rna/evaluation/",
                "tests/evaluation/",
                "scripts/",
            )
        ):
            if relative.startswith("scripts/") and "task5" not in pure.name:
                raise ValueError(
                    f"Task 5 changed unrelated script: {relative}"
                )
            continue
        if relative in {
            "docs/audit/task-5-evaluation.md",
            "manifests/task5_acceptance.json",
        }:
            continue
        raise ValueError(f"Task 5 changed path escaped scope: {relative}")


def task5_delta_snapshot(
    project_root: Path,
    *,
    require_post_commit: bool | None = None,
) -> dict[str, object]:
    root = _canonical_root(project_root)
    head = _run_git(root, "rev-parse", "HEAD")
    if require_post_commit is None:
        require_post_commit = head != TASK4_ACCEPTANCE_COMMIT
    if require_post_commit:
        parents = _run_git(root, "rev-list", "--parents", "-n", "1", head)
        if parents.split() != [head, TASK4_ACCEPTANCE_COMMIT]:
            raise ValueError(
                "Task 5 commit must be the single child of accepted Task 4"
            )
        paths = tuple(sorted(_decode_nul_paths(
            _run_git_bytes(
                root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "--no-renames",
                "-z",
                TASK4_ACCEPTANCE_COMMIT,
                head,
            ),
            label="Task 5 committed changed paths",
        )))
        mode = "POST_COMMIT"
    else:
        if head != TASK4_ACCEPTANCE_COMMIT:
            raise ValueError(
                "Task 5 pre-commit manifest must descend from accepted Task 4"
            )
        status_records = _decode_nul_paths(
            _run_git_bytes(
                root,
                "status",
                "--porcelain=v1",
                "-z",
                "--no-renames",
                "--untracked-files=all",
            ),
            label="Task 5 pre-commit status",
        )
        # Porcelain-v1 -z records are exactly "XY path"; renames are disabled.
        if any(
            len(record) < 4
            or record[2] != " "
            or record[:2] in {"!!", "  "}
            for record in status_records
        ):
            raise ValueError("Task 5 pre-commit status path is malformed")
        paths = tuple(sorted(record[3:] for record in status_records))
        if "manifests/task5_acceptance.json" not in paths:
            paths = tuple(
                sorted((*paths, "manifests/task5_acceptance.json"))
            )
        mode = "PRE_COMMIT"
    _validate_task5_delta_paths(paths)
    return {
        "base_commit": TASK4_ACCEPTANCE_COMMIT,
        "mode_at_verification": mode,
        "changed_paths": paths,
        "changed_paths_sha256": canonical_sha256(paths),
    }


def verify_manifest(
    project_root: Path,
    manifest_path: Path,
    *,
    artifact_root: Path = ARTIFACT_ROOT,
    require_post_commit: bool | None = None,
) -> dict[str, object]:
    root = _canonical_root(project_root)
    expected_manifest_path = root / "manifests" / "task5_acceptance.json"
    checked_manifest = manifest_path.resolve(strict=True)
    draft_allowed = (
        require_post_commit is False
        and manifest_path.name == "task5_acceptance_manifest.draft.json"
        and _is_within(checked_manifest, artifact_root.resolve())
    )
    if manifest_path.is_symlink() or (
        checked_manifest != expected_manifest_path.resolve()
        and not draft_allowed
    ):
        raise ValueError("Task 5 acceptance manifest path changed")
    raw = _load_canonical_json(
        checked_manifest,
        label="Task 5 acceptance manifest",
    )
    if set(raw) != EXPECTED_MANIFEST_FIELDS:
        raise ValueError("Task 5 acceptance manifest fields changed")
    if (
        raw["schema"] != MANIFEST_SCHEMA
        or raw["task"] != 5
        or raw["status"] != "READY_FOR_COMMIT"
        or raw["contract_sha256"] != CONTRACT_SHA256
        or raw["registered_commit_title"] != COMMIT_TITLE
        or raw["claim_boundary"] != CLAIM_BOUNDARY
    ):
        raise ValueError("Task 5 manifest authority or claim boundary changed")
    contract = root / "contracts" / "D2T-RNA-v6.1-frozen-plan.md"
    if contract.is_symlink() or _sha256(contract) != CONTRACT_SHA256:
        raise ValueError("frozen contract bytes changed")
    prior = raw["prior_task"]
    expected_prior = {
        "task": 4,
        "accepted_commit": TASK4_ACCEPTANCE_COMMIT,
        "acceptance_manifest_sha256": TASK4_ACCEPTANCE_MANIFEST_SHA256,
        "post_commit_closure": {
            "path": str(TASK4_CLOSURE_PATH),
            "sha256": TASK4_CLOSURE_SHA256,
        },
    }
    if prior != expected_prior:
        raise ValueError("Task 5 prior-task authority changed")
    _verify_historical_evidence(root, raw["historical_evidence"])

    predeclared_tests = raw["test_evidence"]
    if type(predeclared_tests) is not dict:
        raise ValueError("Task 5 test evidence is malformed")
    predeclared_run_id = _validate_run_id(predeclared_tests.get("run_id"))
    source_record = raw["source_snapshot"]
    if type(source_record) is not dict or set(source_record) != {
        "artifact",
        "post_test_artifact",
        "source_index",
        "source_index_sha256",
        "task4_parent_source_index_sha256",
    }:
        raise ValueError("Task 5 source snapshot record is malformed")
    source_path = _verify_external_file(
        source_record["artifact"],
        root=artifact_root,
        label="Task 5 source snapshot artifact",
        expected_path=(
            artifact_root
            / "runs"
            / predeclared_run_id
            / "snapshots"
            / "source_index.json"
        ),
    )
    post_source_path = _verify_external_file(
        source_record["post_test_artifact"],
        root=artifact_root,
        label="Task 5 post-test source snapshot artifact",
        expected_path=(
            artifact_root
            / "runs"
            / predeclared_run_id
            / "snapshots"
            / "source_index_post_test.json"
        ),
    )
    source_artifact = _load_canonical_json(
        source_path,
        label="Task 5 source snapshot artifact",
    )
    post_source_artifact = _load_canonical_json(
        post_source_path,
        label="Task 5 post-test source snapshot artifact",
    )
    live_source = build_source_snapshot(root)
    if (
        not _canonical_json_equal(source_artifact, live_source)
        or not _canonical_json_equal(
            post_source_artifact, source_artifact
        )
    ):
        raise ValueError("Task 5 source snapshot differs from live source")
    if (
        source_record["source_index"] != live_source["source_index"]
        or source_record["source_index_sha256"]
        != live_source["source_index_sha256"]
    ):
        raise ValueError("Task 5 source index does not replay")

    runtime = raw["runtime"]
    if type(runtime) is not dict or set(runtime) != {
        "implementation",
        "python_version",
        "python_cache_tag",
        "gpu_required",
        "arithmetic",
        "dependency_snapshot",
        "dependency_snapshot_sha256",
        "task4_parent_binding",
        "task4_parent_dependency_snapshot_sha256",
    }:
        raise ValueError("Task 5 runtime record is malformed")
    if (
        runtime["implementation"] != "CPython"
        or type(runtime["python_version"]) is not str
        or re.fullmatch(r"3\.11\.[0-9]+", runtime["python_version"]) is None
        or runtime["gpu_required"] is not False
        or runtime["arithmetic"] != "fractions.Fraction"
    ):
        raise ValueError("Task 5 runtime boundary changed")
    runtime_path = _verify_external_file(
        runtime["dependency_snapshot"],
        root=artifact_root,
        label="Task 5 dependency snapshot artifact",
    )
    runtime_artifact = _load_canonical_json(
        runtime_path,
        label="Task 5 dependency snapshot artifact",
    )
    task4_parent_binding_path = _verify_external_file(
        runtime["task4_parent_binding"],
        root=artifact_root,
        label="Task 5 nested Task 4 parent binding",
        expected_path=(
            artifact_root
            / "runs"
            / predeclared_run_id
            / "snapshots"
            / "task4_nested_parent_binding.json"
        ),
    )
    task4_parent_binding_artifact = _load_canonical_json(
        task4_parent_binding_path,
        label="Task 5 nested Task 4 parent binding",
    )
    live_runtime = build_runtime_dependency_snapshot(root)
    if not _canonical_json_equal(runtime_artifact, live_runtime):
        raise ValueError("Task 5 runtime dependency snapshot changed")
    if runtime["dependency_snapshot_sha256"] != canonical_sha256(live_runtime):
        raise ValueError("Task 5 dependency snapshot hash does not replay")
    task4_parent_binding = derive_task4_nested_parent_binding(
        root,
        runtime_snapshot=runtime_artifact,
        source_snapshot=source_artifact,
    )
    if (
        task4_parent_binding_artifact != task4_parent_binding
        or
        runtime["task4_parent_dependency_snapshot_sha256"]
        != task4_parent_binding["dependency_snapshot_sha256"]
        or source_record["task4_parent_source_index_sha256"]
        != task4_parent_binding["source_index_sha256"]
    ):
        raise ValueError(
            "Task 5 nested Task 4 parent binding does not replay"
        )

    observed_delta = task5_delta_snapshot(
        root,
        require_post_commit=require_post_commit,
    )
    declared_delta = raw["task5_delta"]
    if type(declared_delta) is not dict or set(declared_delta) != {
        "base_commit",
        "changed_paths",
        "changed_paths_sha256",
    }:
        raise ValueError("Task 5 delta record is malformed")
    if (
        declared_delta["base_commit"] != observed_delta["base_commit"]
        or declared_delta["changed_paths"] != list(
            observed_delta["changed_paths"]
        )
        or declared_delta["changed_paths_sha256"]
        != observed_delta["changed_paths_sha256"]
    ):
        raise ValueError("Task 5 Git delta does not match manifest")

    tests = raw["test_evidence"]
    if type(tests) is not dict or set(tests) != {
        "run_id",
        "evaluation_tests_passed",
        "combined_tests_passed",
        "full_tests_passed",
        "run_log",
        "junit",
    }:
        raise ValueError("Task 5 test evidence is malformed")
    run_id = _validate_run_id(tests["run_id"])
    if draft_allowed and checked_manifest != (
        artifact_root
        / "runs"
        / run_id
        / "task5_acceptance_manifest.draft.json"
    ).resolve():
        raise ValueError("Task 5 draft manifest is not bound to its run ID")
    counts = (
        tests["evaluation_tests_passed"],
        tests["combined_tests_passed"],
        tests["full_tests_passed"],
    )
    run_log = _verify_external_file(
        tests["run_log"],
        root=artifact_root,
        label="Task 5 candidate run log",
        expected_path=artifact_root / "runs" / run_id / "run.log",
    )
    fixture_record = raw["fixture_evidence"]
    if type(fixture_record) is not dict or set(fixture_record) != {
        "manifest",
        "all_registered_replays_passed",
        "risk_certificate_issued",
        "scientific_claim_authorized",
        "serialized_bearer_authorization",
    }:
        raise ValueError("Task 5 fixture evidence is malformed")
    fixture_path = _verify_external_file(
        fixture_record["manifest"],
        root=artifact_root,
        label="Task 5 fixture manifest",
        expected_path=(
            artifact_root
            / "runs"
            / run_id
            / "fixture"
            / "fixture_manifest.json"
        ),
    )
    verify_fixture(root, fixture_path, artifact_root=artifact_root)
    if fixture_record != {
        "manifest": fixture_record["manifest"],
        "all_registered_replays_passed": True,
        "risk_certificate_issued": False,
        "scientific_claim_authorized": False,
        "serialized_bearer_authorization": False,
    }:
        raise ValueError("Task 5 fixture authorization changed")
    _verify_test_log(
        run_log,
        run_id=run_id,
        runtime=runtime,
        dependency_snapshot_sha256=runtime[
            "dependency_snapshot_sha256"
        ],
        source_index_sha256=source_record["source_index_sha256"],
        task4_parent_dependency_snapshot_sha256=(
            task4_parent_binding["dependency_snapshot_sha256"]
        ),
        task4_parent_source_index_sha256=(
            task4_parent_binding["source_index_sha256"]
        ),
        fixture_manifest_sha256=fixture_record["manifest"]["sha256"],
        expected_counts=counts,
        artifact_root=artifact_root,
    )
    junit = tests["junit"]
    if type(junit) is not dict or set(junit) != {
        "evaluation",
        "combined",
        "full",
    }:
        raise ValueError("Task 5 JUnit registry changed")
    for name, count in zip(
        ("evaluation", "combined", "full"),
        counts,
        strict=True,
    ):
        junit_path = _verify_external_file(
            junit[name],
            root=artifact_root,
            label=f"Task 5 {name} JUnit",
            expected_path=(
                artifact_root / "runs" / run_id / "junit" / f"{name}.xml"
            ),
        )
        _verify_junit(
            junit_path,
            expected_count=count,
            label=f"Task 5 {name} JUnit",
        )
    if raw["github"] != {
        "repository": REPOSITORY,
        "visibility": "PUBLIC",
        "branch": "main",
        "push_required_after_commit": True,
    }:
        raise ValueError("Task 5 GitHub publication contract changed")
    if raw["post_commit_closure_required"] is not True:
        raise ValueError("Task 5 post-commit closure was disabled")
    return raw


FINAL_RUN_ID = re.compile(
    r"^task5-final-(?P<stamp>[0-9]{8}T[0-9]{6})\+0800$"
)


def _validate_final_run_id(run_id: object) -> str:
    if type(run_id) is not str:
        raise ValueError("Task 5 final run ID is not canonical")
    match = FINAL_RUN_ID.fullmatch(run_id)
    if match is None:
        raise ValueError("Task 5 final run ID is not canonical")
    try:
        parsed = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise ValueError("Task 5 final run ID is not canonical") from exc
    if parsed.strftime("%Y%m%dT%H%M%S") != match.group("stamp"):
        raise ValueError("Task 5 final run ID is not canonical")
    return run_id


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifests/task5_acceptance.json"),
    )
    parser.add_argument("--write-source-snapshot", type=Path)
    parser.add_argument("--write-runtime-snapshot", type=Path)
    parser.add_argument(
        "--write-task4-nested-parent-binding",
        type=Path,
    )
    parser.add_argument("--runtime-snapshot", type=Path)
    parser.add_argument("--source-snapshot", type=Path)
    parser.add_argument("--print-source-index-sha256", action="store_true")
    parser.add_argument(
        "--print-runtime-snapshot-sha256",
        action="store_true",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    selected = sum(
        (
            args.write_source_snapshot is not None,
            args.write_runtime_snapshot is not None,
            args.write_task4_nested_parent_binding is not None,
            args.print_source_index_sha256,
            args.print_runtime_snapshot_sha256,
        )
    )
    if selected > 1:
        parser.error("select at most one snapshot action")
    binding_inputs = (
        args.runtime_snapshot is not None,
        args.source_snapshot is not None,
    )
    if (
        args.write_task4_nested_parent_binding is None
        and any(binding_inputs)
    ) or (
        args.write_task4_nested_parent_binding is not None
        and not all(binding_inputs)
    ):
        parser.error(
            "the Task 4 parent binding action requires both snapshots"
        )
    if args.write_source_snapshot is not None:
        print(
            _write_canonical_exclusive(
                args.write_source_snapshot,
                build_source_snapshot(project_root),
            )
        )
    elif args.write_runtime_snapshot is not None:
        print(
            _write_canonical_exclusive(
                args.write_runtime_snapshot,
                build_runtime_dependency_snapshot(project_root),
            )
        )
    elif args.write_task4_nested_parent_binding is not None:
        (
            binding_output,
            binding_runtime_snapshot,
            binding_source_snapshot,
        ) = _resolve_task4_binding_cli_paths(
            output_path=args.write_task4_nested_parent_binding,
            runtime_snapshot_path=args.runtime_snapshot,
            source_snapshot_path=args.source_snapshot,
        )
        print(
            _write_canonical_exclusive(
                binding_output,
                derive_task4_nested_parent_binding(
                    project_root,
                    runtime_snapshot=_load_canonical_json(
                        binding_runtime_snapshot,
                        label="Task 5 runtime snapshot",
                    ),
                    source_snapshot=_load_canonical_json(
                        binding_source_snapshot,
                        label="Task 5 source snapshot",
                    ),
                ),
            )
        )
    elif args.print_source_index_sha256:
        print(source_index_sha256(project_root))
    elif args.print_runtime_snapshot_sha256:
        print(runtime_dependency_snapshot_sha256(project_root))
    else:
        manifest = args.manifest
        if not manifest.is_absolute():
            manifest = project_root / manifest
        verify_manifest(project_root, manifest)
        print("TASK5_ACCEPTANCE_MANIFEST_VERIFIED")


if __name__ == "__main__":
    _main()
