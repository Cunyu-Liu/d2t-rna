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
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"
python_bin="${project_root}/.venv/bin/python"
isolated_launcher="${project_root}/scripts/task4_isolated_python.py"
verifier="${project_root}/scripts/verify_task5_acceptance_manifest.py"
contract_path="${project_root}/contracts/D2T-RNA-v6.1-frozen-plan.md"
artifact_root="/mnt/cunyuliu/d2t-rna/artifacts"
expected_contract_sha="87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
task4_commit="4793026c1e709b7ca78042b8a10294fe569d7b8c"
task4_manifest_sha="61348d3d00fb96c543e38ffa3b4ab0e15749214ebe54c875024d8efa0a600e96"
task4_closure_sha="c023cb1efcfa8cc6d4fe36227d70075bab1a34b7f6cd2939693375016920c068"
task4_launcher_sha="01e8ac006837a46faf7208630df8cc362a1e1713c5ecf38229c72c60ec3bbf51"
task4_runtime_helper="${project_root}/scripts/verify_task4_acceptance_manifest.py"
task4_runtime_helper_sha="1bb76747e04ebb527c79105b2349bdd648210a30a86498de065330b4e5541b5f"
current_stage="preflight"

record_failure() {
  exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    printf "TASK5_CANDIDATE_FAILED_STAGE=%s EXIT_CODE=%s\n" \
      "${current_stage}" "${exit_code}"
  fi
}
trap record_failure EXIT

if [[ ! -x "${python_bin}" ]]; then
  echo "FAIL: project Python 3.11 environment is unavailable" >&2
  exit 1
fi
if [[ ! -d "${artifact_root}" || -L "${artifact_root}" ]]; then
  echo "FAIL: Task 5 artifact root is unavailable or a symlink" >&2
  exit 1
fi
if [[ ! -f "${isolated_launcher}" || -L "${isolated_launcher}" ]]; then
  echo "FAIL: accepted isolated Python launcher is unavailable" >&2
  exit 1
fi
if [[ "$(sha256sum "${isolated_launcher}" | cut -d ' ' -f 1)" \
  != "${task4_launcher_sha}" \
  || ! -f "${task4_runtime_helper}" || -L "${task4_runtime_helper}" \
  || "$(sha256sum "${task4_runtime_helper}" | cut -d ' ' -f 1)" \
  != "${task4_runtime_helper_sha}" ]]; then
  echo "FAIL: accepted Task 4 helper bytes changed" >&2
  exit 1
fi
if [[ ! -f "${verifier}" || -L "${verifier}" ]]; then
  echo "FAIL: Task 5 acceptance verifier is unavailable" >&2
  exit 1
fi
if [[ "$(/usr/bin/git rev-parse HEAD)" != "${task4_commit}" \
  || "$(/usr/bin/git branch --show-current)" != "main" \
  || "$(/usr/bin/git remote get-url origin)" \
    != "git@github.com:Cunyu-Liu/d2t-rna.git" ]]; then
  echo "FAIL: Task 5 candidate must start at accepted Task 4 main" >&2
  exit 1
fi
if [[ -z "${TASK5_RUN_ID:-}" ]]; then
  echo "FAIL: TASK5_RUN_ID is required" >&2
  exit 1
fi
if [[ ! "${TASK5_RUN_ID}" =~ ^task5-acceptance-[0-9]{8}T[0-9]{6}\+0800$ ]]; then
  echo "FAIL: TASK5_RUN_ID is not canonical" >&2
  exit 1
fi

run_dir="${artifact_root}/runs/${TASK5_RUN_ID}"
pycache_dir="${run_dir}/pycache"
junit_dir="${run_dir}/junit"
fixture_dir="${run_dir}/fixture"
snapshot_dir="${run_dir}/snapshots"
if [[ ! -d "${run_dir}" || -L "${run_dir}" ]]; then
  echo "FAIL: caller must create one non-symlink Task 5 run directory" >&2
  exit 1
fi
for output in "${pycache_dir}" "${junit_dir}" "${fixture_dir}" "${snapshot_dir}"; do
  if [[ -e "${output}" || -L "${output}" ]]; then
    echo "FAIL: Task 5 candidate output already exists: ${output}" >&2
    exit 1
  fi
done

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
for execution_root in src tests scripts; do
  if [[ ! -d "${execution_root}" || -L "${execution_root}" ]]; then
    echo "FAIL: invalid Task 5 execution root: ${execution_root}" >&2
    exit 1
  fi
done
execution_symlink="$(find src tests scripts -type l -print -quit)"
if [[ -n "${execution_symlink}" ]]; then
  echo "FAIL: execution tree contains a symlink: ${execution_symlink}" >&2
  exit 1
fi
legacy_bytecode="$(
  find src tests scripts -type f -name '*.pyc' \
    ! -path '*/__pycache__/*' -print -quit
)"
if [[ -n "${legacy_bytecode}" ]]; then
  echo "FAIL: legacy or sourceless bytecode: ${legacy_bytecode}" >&2
  exit 1
fi
native_extension="$(
  find src tests scripts -type f \
    \( -name '*.so' -o -name '*.so.*' -o -name '*.pyd' \
    -o -name '*.dylib' \) -print -quit
)"
if [[ -n "${native_extension}" ]]; then
  echo "FAIL: unregistered native extension: ${native_extension}" >&2
  exit 1
fi

mkdir -p "${pycache_dir}" "${junit_dir}" "${snapshot_dir}"
task5_python() {
  "${python_bin}" -I -S -B -X "pycache_prefix=${pycache_dir}" \
    "${isolated_launcher}" \
    --project-root "${project_root}" \
    --pycache-prefix "${pycache_dir}" \
    -- "$@"
}

runtime="$(task5_python -c \
  'import platform
import sys
assert sys.version_info[:2] == (3, 11), sys.version
print(platform.python_implementation(), platform.python_version())')"
actual_contract_sha="$(sha256sum "${contract_path}" | cut -d ' ' -f 1)"
if [[ "${actual_contract_sha}" != "${expected_contract_sha}" ]]; then
  echo "FAIL: frozen contract SHA-256 changed" >&2
  exit 1
fi

current_stage="snapshots"
runtime_snapshot_path="${snapshot_dir}/runtime_dependency_snapshot.json"
source_snapshot_path="${snapshot_dir}/source_index.json"
post_source_snapshot_path="${snapshot_dir}/source_index_post_test.json"
task4_parent_binding_path="${snapshot_dir}/task4_nested_parent_binding.json"
task5_python "${verifier}" \
  --write-runtime-snapshot "${runtime_snapshot_path}" >/dev/null
task5_python "${verifier}" \
  --write-source-snapshot "${source_snapshot_path}" >/dev/null
task5_python "${verifier}" \
  --write-task4-nested-parent-binding "${task4_parent_binding_path}" \
  --runtime-snapshot "${runtime_snapshot_path}" \
  --source-snapshot "${source_snapshot_path}" >/dev/null
dependency_snapshot_sha="$(task5_python -c \
  'import json
from pathlib import Path
from d2t_rna.contracts.base import canonical_sha256
raw=json.loads(Path("'"${runtime_snapshot_path}"'").read_text())
print(canonical_sha256(raw))')"
pre_test_source_index_sha="$(task5_python -c \
  'import json
from pathlib import Path
raw=json.loads(Path("'"${source_snapshot_path}"'").read_text())
print(raw["source_index_sha256"])')"
task4_parent_dependency_sha="$(task5_python -c \
  'import json
from pathlib import Path
raw=json.loads(Path("'"${task4_parent_binding_path}"'").read_text())
print(raw["dependency_snapshot_sha256"])')"
task4_parent_source_sha="$(task5_python -c \
  'import json
from pathlib import Path
raw=json.loads(Path("'"${task4_parent_binding_path}"'").read_text())
print(raw["source_index_sha256"])')"
if [[ ! "${task4_parent_dependency_sha}" =~ ^[0-9a-f]{64}$ \
  || ! "${task4_parent_source_sha}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "FAIL: nested Task 4 parent binding is malformed" >&2
  exit 1
fi
export TASK4_REGISTERED_DEPENDENCY_SNAPSHOT_SHA256="${task4_parent_dependency_sha}"
export TASK4_REGISTERED_SOURCE_INDEX_SHA256="${task4_parent_source_sha}"

printf "TASK5_CANDIDATE_RUNNER_SCHEMA=d2t_rna.task5_candidate_runner.v1\n"
printf "TASK5_RUN_ID=%s\n" "${TASK5_RUN_ID}"
printf "TASK5_RUNTIME=%s\n" "${runtime}"
printf "TASK5_CONTRACT_SHA256=%s\n" "${actual_contract_sha}"
printf "TASK5_TASK4_ACCEPTANCE_COMMIT=%s\n" "${task4_commit}"
printf "TASK5_TASK4_ACCEPTANCE_MANIFEST_SHA256=%s\n" "${task4_manifest_sha}"
printf "TASK5_TASK4_CLOSURE_SHA256=%s\n" "${task4_closure_sha}"
printf "TASK5_DEPENDENCY_SNAPSHOT_SHA256=%s\n" \
  "${dependency_snapshot_sha}"
printf "TASK5_TASK4_PARENT_DEPENDENCY_SNAPSHOT_SHA256=%s\n" \
  "${task4_parent_dependency_sha}"
printf "TASK5_TASK4_PARENT_SOURCE_INDEX_SHA256=%s\n" \
  "${task4_parent_source_sha}"
printf "TASK5_PYTHON_ISOLATION_PASS=%s\n" "${pycache_dir}"
printf "TASK5_PRE_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${pre_test_source_index_sha}"

current_stage="compile"
task5_python -m compileall -q src tests scripts
printf "TASK5_COMPILE_PASS\n"

current_stage="pytest_evaluation"
printf "TASK5_EVALUATION_TESTS_BEGIN\n"
task5_python -m pytest -q tests/evaluation \
  --junitxml="${junit_dir}/evaluation.xml"
printf "TASK5_EVALUATION_TESTS_END\n"

current_stage="pytest_combined"
printf "TASK5_COMBINED_TESTS_BEGIN\n"
task5_python -m pytest -q \
  tests/evaluation tests/exact tests/probability tests/contracts \
  --junitxml="${junit_dir}/combined.xml"
printf "TASK5_COMBINED_TESTS_END\n"

current_stage="pytest_full"
printf "TASK5_FULL_TESTS_BEGIN\n"
task5_python -m pytest -q --junitxml="${junit_dir}/full.xml"
printf "TASK5_FULL_TESTS_END\n"

current_stage="fixture"
task5_python scripts/build_task5_acceptance_fixture.py \
  --output-dir "${fixture_dir}"
fixture_sha="$(sha256sum \
  "${fixture_dir}/fixture_manifest.json" | cut -d ' ' -f 1)"
printf "TASK5_FIXTURE_MANIFEST_SHA256=%s\n" "${fixture_sha}"

current_stage="source_index_post_test"
task5_python "${verifier}" \
  --write-source-snapshot "${post_source_snapshot_path}" >/dev/null
post_test_source_index_sha="$(task5_python -c \
  'import json
from pathlib import Path
raw=json.loads(Path("'"${post_source_snapshot_path}"'").read_text())
print(raw["source_index_sha256"])')"
printf "TASK5_POST_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${post_test_source_index_sha}"
if [[ "${post_test_source_index_sha}" != "${pre_test_source_index_sha}" ]]; then
  echo "FAIL: Task 5 source index changed during candidate run" >&2
  exit 1
fi

current_stage="repository_audit"
/usr/bin/git diff --check
/usr/bin/git diff --cached --check
printf "TASK5_GIT_DIFF_CHECK_PASS\n"
task5_python -c \
  'import json
import pathlib
for path in pathlib.Path("manifests").glob("*.json"):
    json.loads(path.read_text())'
printf "TASK5_EXISTING_MANIFEST_JSON_PASS\n"

committable_path_index="${run_dir}/committable-paths.nul"
if [[ -e "${committable_path_index}" || -L "${committable_path_index}" ]]; then
  echo "FAIL: committable path index already exists" >&2
  exit 1
fi
/usr/bin/git ls-files -z --cached --others \
  --exclude-standard > "${committable_path_index}"
secret_pattern='(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|'
secret_pattern+='github_pat_[A-Za-z0-9_]{20,}|'
secret_pattern+='ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})'
secret_findings=0
while IFS= read -r -d '' path; do
  if [[ ! -f "${path}" ]]; then
    continue
  fi
  if grep -IEn -- "${secret_pattern}" "${path}"; then
    secret_findings=1
  else
    grep_status=$?
    if (( grep_status != 1 )); then
      echo "FAIL: secret audit could not read ${path}" >&2
      exit 1
    fi
  fi
done < "${committable_path_index}"
if [[ "${secret_findings}" -ne 0 ]]; then
  echo "FAIL: secret-pattern audit found a candidate" >&2
  exit 1
fi
printf "TASK5_SECRET_AUDIT_PASS\n"

large_file_findings=0
while IFS= read -r -d '' path; do
  if [[ ! -f "${path}" ]]; then
    continue
  fi
  byte_count="$(wc -c < "${path}")"
  if (( byte_count > 5242880 )); then
    echo "FAIL: committable file exceeds 5 MiB: ${path}" >&2
    large_file_findings=1
  fi
done < "${committable_path_index}"
if [[ "${large_file_findings}" -ne 0 ]]; then
  exit 1
fi
printf "TASK5_LARGE_FILE_AUDIT_PASS\n"
current_stage="complete"
printf "TASK5_CANDIDATE_PASS\n"
