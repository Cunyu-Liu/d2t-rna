#!/bin/bash
set -euo pipefail

PATH=/usr/bin:/bin
export PATH
while IFS= read -r environment_name; do
  case "${environment_name}" in
    BASH_ENV|ENV|BASH_FUNC_*|GIT_*|GH_*|PYTHON*|_PYTHON*|PYTEST*)
      if ! builtin unset -v "${environment_name}"; then
        printf "FAIL: could not clear environment input: %s\n" \
          "${environment_name}" >&2
        exit 1
      fi
      ;;
  esac
done < <(builtin compgen -e)
while IFS= read -r function_name; do
  if ! builtin unset -f "${function_name}"; then
    printf "FAIL: could not clear imported function: %s\n" \
      "${function_name}" >&2
    exit 1
  fi
done < <(builtin compgen -A function)
builtin unalias -a 2>/dev/null || true
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_TERMINAL_PROMPT=0

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

python_bin="${project_root}/.venv/bin/python"
isolated_launcher="${project_root}/scripts/task4_isolated_python.py"
contract_path="${project_root}/contracts/D2T-RNA-v6.1-frozen-plan.md"
expected_contract_sha="87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
artifact_root="/mnt/cunyuliu/d2t-rna/artifacts"
current_stage="preflight"

record_failure() {
  exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    printf "TASK4_CANDIDATE_FAILED_STAGE=%s EXIT_CODE=%s\n" \
      "${current_stage}" "${exit_code}"
  fi
}
trap record_failure EXIT

if [[ ! -x "${python_bin}" ]]; then
  echo "FAIL: project Python 3.11 environment is unavailable" >&2
  exit 1
fi
if [[ ! -f "${isolated_launcher}" || -L "${isolated_launcher}" ]]; then
  echo "FAIL: Task 4 isolated Python launcher is unavailable" >&2
  exit 1
fi
if [[ -z "${TASK4_RUN_ID:-}" ]]; then
  echo "FAIL: TASK4_RUN_ID is required" >&2
  exit 1
fi
if [[ ! "${TASK4_RUN_ID}" =~ ^task4-acceptance-[0-9]{8}T[0-9]{6}\+0800$ ]]; then
  echo "FAIL: TASK4_RUN_ID is not canonical" >&2
  exit 1
fi

expected_fixture_dir="${artifact_root}/runs/${TASK4_RUN_ID}/fixture"
junit_dir="${artifact_root}/runs/${TASK4_RUN_ID}/junit"
run_dir="${artifact_root}/runs/${TASK4_RUN_ID}"
if [[ "${TASK4_FIXTURE_OUTPUT_DIR:-}" != "${expected_fixture_dir}" ]]; then
  echo "FAIL: TASK4_FIXTURE_OUTPUT_DIR is not bound to TASK4_RUN_ID" >&2
  exit 1
fi
if [[ -L "${run_dir}" || ( -e "${run_dir}" && ! -d "${run_dir}" ) ]]; then
  echo "FAIL: candidate Task 4 run directory is unsafe" >&2
  exit 1
fi
if [[ -e "${TASK4_FIXTURE_OUTPUT_DIR}" || -L "${TASK4_FIXTURE_OUTPUT_DIR}" ]]; then
  echo "FAIL: candidate fixture output already exists" >&2
  exit 1
fi
if [[ -e "${junit_dir}" || -L "${junit_dir}" ]]; then
  echo "FAIL: candidate JUnit output already exists" >&2
  exit 1
fi

for forbidden_path in \
  conftest.py \
  sitecustomize.py \
  usercustomize.py \
  pytest.ini \
  tox.ini \
  setup.cfg; do
  if [[ -e "${forbidden_path}" || -L "${forbidden_path}" ]]; then
    echo "FAIL: unregistered root execution input: ${forbidden_path}" >&2
    exit 1
  fi
done
for execution_root in src src/d2t_rna tests scripts; do
  if [[ ! -d "${execution_root}" || -L "${execution_root}" ]]; then
    echo "FAIL: invalid Task 4 execution root: ${execution_root}" >&2
    exit 1
  fi
done
execution_symlink="$(
  find src tests scripts -type l -print -quit
)"
if [[ -n "${execution_symlink}" ]]; then
  echo "FAIL: project execution tree contains a symlink: ${execution_symlink}" >&2
  exit 1
fi
legacy_bytecode="$(
  find src tests scripts -type f -name '*.pyc' \
    ! -path '*/__pycache__/*' -print -quit
)"
if [[ -n "${legacy_bytecode}" ]]; then
  echo "FAIL: legacy or sourceless project bytecode: ${legacy_bytecode}" >&2
  exit 1
fi
native_extension="$(
  find src tests scripts -type f \
    \( -name '*.so' -o -name '*.so.*' -o -name '*.pyd' \
    -o -name '*.dylib' \) -print -quit
)"
if [[ -n "${native_extension}" ]]; then
  echo "FAIL: unregistered project native extension: ${native_extension}" >&2
  exit 1
fi

pycache_dir="${artifact_root}/runs/${TASK4_RUN_ID}/pycache"
if [[ -e "${pycache_dir}" || -L "${pycache_dir}" ]]; then
  echo "FAIL: candidate Python cache directory already exists" >&2
  exit 1
fi
mkdir -p "${pycache_dir}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

task4_python() {
  "${python_bin}" -I -S -X "pycache_prefix=${pycache_dir}" \
    "${isolated_launcher}" \
    --project-root "${project_root}" \
    --pycache-prefix "${pycache_dir}" \
    -- "$@"
}

runtime="$(task4_python -c \
  'import platform
import sys
assert sys.version_info[:2] == (3, 11), sys.version
print(platform.python_implementation(), platform.python_version())')"
dependency_snapshot_sha="$(task4_python -c \
  'from pathlib import Path
from scripts.verify_task4_acceptance_manifest import (
    runtime_dependency_snapshot_sha256,
)
print(runtime_dependency_snapshot_sha256(Path.cwd()))')"
pre_test_source_index_sha="$(task4_python -c \
  'from pathlib import Path
from scripts.verify_task4_acceptance_manifest import source_index_sha256
print(source_index_sha256(Path.cwd()))')"
export TASK4_REGISTERED_DEPENDENCY_SNAPSHOT_SHA256="${dependency_snapshot_sha}"
export TASK4_REGISTERED_SOURCE_INDEX_SHA256="${pre_test_source_index_sha}"
actual_contract_sha="$(sha256sum "${contract_path}" | cut -d ' ' -f 1)"
if [[ "${actual_contract_sha}" != "${expected_contract_sha}" ]]; then
  echo "FAIL: frozen contract SHA-256 changed" >&2
  exit 1
fi

printf "TASK4_RUNNER_SCHEMA=d2t_rna.task4_candidate_runner.v1\n"
printf "TASK4_RUN_ID=%s\n" "${TASK4_RUN_ID}"
printf "TASK4_RUNTIME=%s\n" "${runtime}"
printf "TASK4_CONTRACT_SHA256=%s\n" "${actual_contract_sha}"
printf "TASK4_DEPENDENCY_SNAPSHOT_SHA256=%s\n" \
  "${dependency_snapshot_sha}"
printf "TASK4_PYTHON_ISOLATION_PASS=%s\n" "${pycache_dir}"
printf "TASK4_PRE_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${pre_test_source_index_sha}"

mkdir -p "${junit_dir}"
current_stage="pytest_exact"
printf "TASK4_EXACT_TESTS_BEGIN\n"
task4_python -m pytest -q tests/exact \
  --junitxml="${junit_dir}/exact.xml"
printf "TASK4_EXACT_TESTS_END\n"

current_stage="pytest_combined"
printf "TASK4_COMBINED_TESTS_BEGIN\n"
task4_python -m pytest -q \
  tests/exact tests/probability tests/contracts \
  --junitxml="${junit_dir}/combined.xml"
printf "TASK4_COMBINED_TESTS_END\n"

current_stage="pytest_full"
printf "TASK4_FULL_TESTS_BEGIN\n"
task4_python -m pytest -q --junitxml="${junit_dir}/full.xml"
printf "TASK4_FULL_TESTS_END\n"

current_stage="source_index_post_test"
post_test_source_index_sha="$(task4_python -c \
  'from pathlib import Path
from scripts.verify_task4_acceptance_manifest import source_index_sha256
print(source_index_sha256(Path.cwd()))')"
printf "TASK4_POST_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${post_test_source_index_sha}"
if [[ "${post_test_source_index_sha}" != "${pre_test_source_index_sha}" ]]; then
  echo "FAIL: Task 4 source index changed during candidate tests" >&2
  exit 1
fi

current_stage="compile"
task4_python -m compileall -q src tests scripts
printf "TASK4_COMPILE_PASS\n"

current_stage="fixture"
task4_python scripts/build_task4_acceptance_fixture.py \
  --output-dir "${TASK4_FIXTURE_OUTPUT_DIR}"
fixture_sha="$(sha256sum \
  "${TASK4_FIXTURE_OUTPUT_DIR}/fixture_manifest.json" | cut -d ' ' -f 1)"
printf "TASK4_FIXTURE_MANIFEST_SHA256=%s\n" "${fixture_sha}"

current_stage="repository_audit"
/usr/bin/git diff --check
/usr/bin/git diff --cached --check
printf "TASK4_GIT_DIFF_CHECK_PASS\n"

task4_python -c \
  'import json
import pathlib
for path in pathlib.Path("manifests").glob("*.json"):
    json.loads(path.read_text())'
printf "TASK4_EXISTING_MANIFEST_JSON_PASS\n"
current_stage="complete"
printf "TASK4_CANDIDATE_PASS\n"
