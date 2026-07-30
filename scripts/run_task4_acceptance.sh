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

if [[ ! -x "${python_bin}" ]]; then
  echo "FAIL: project Python 3.11 environment is unavailable" >&2
  exit 1
fi
if [[ ! -f "${isolated_launcher}" || -L "${isolated_launcher}" ]]; then
  echo "FAIL: Task 4 isolated Python launcher is unavailable" >&2
  exit 1
fi
if [[ -z "${TASK4_FINAL_RUN_ID:-}" ]]; then
  echo "FAIL: TASK4_FINAL_RUN_ID is required" >&2
  exit 1
fi
if [[ ! "${TASK4_FINAL_RUN_ID}" =~ ^task4-final-[0-9]{8}T[0-9]{6}\+0800$ ]]; then
  echo "FAIL: TASK4_FINAL_RUN_ID is not canonical" >&2
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

final_run_dir="${artifact_root}/runs/${TASK4_FINAL_RUN_ID}"
pycache_dir="${final_run_dir}/pycache"
if [[ -L "${final_run_dir}" ]]; then
  echo "FAIL: final Task 4 run directory is a symlink" >&2
  exit 1
fi
if [[ -e "${final_run_dir}" && ! -d "${final_run_dir}" ]]; then
  echo "FAIL: final Task 4 run path is not a directory" >&2
  exit 1
fi
mkdir -p "${final_run_dir}"
if [[ -e "${pycache_dir}" || -L "${pycache_dir}" ]]; then
  echo "FAIL: final Task 4 Python cache directory already exists" >&2
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

printf "TASK4_FINAL_RUNNER_SCHEMA=d2t_rna.task4_final_runner.v1\n"
printf "TASK4_FINAL_RUN_ID=%s\n" "${TASK4_FINAL_RUN_ID}"
printf "TASK4_RUNTIME=%s\n" "${runtime}"
printf "TASK4_CONTRACT_SHA256=%s\n" "${actual_contract_sha}"
printf "TASK4_DEPENDENCY_SNAPSHOT_SHA256=%s\n" \
  "${dependency_snapshot_sha}"
printf "TASK4_PYTHON_ISOLATION_PASS=%s\n" "${pycache_dir}"
printf "TASK4_PRE_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${pre_test_source_index_sha}"

printf "TASK4_EXACT_TESTS_BEGIN\n"
task4_python -m pytest -q tests/exact
printf "TASK4_EXACT_TESTS_END\n"
printf "TASK4_COMBINED_TESTS_BEGIN\n"
task4_python -m pytest -q \
  tests/exact tests/probability tests/contracts
printf "TASK4_COMBINED_TESTS_END\n"
printf "TASK4_FULL_TESTS_BEGIN\n"
task4_python -m pytest -q
printf "TASK4_FULL_TESTS_END\n"
post_test_source_index_sha="$(task4_python -c \
  'from pathlib import Path
from scripts.verify_task4_acceptance_manifest import source_index_sha256
print(source_index_sha256(Path.cwd()))')"
printf "TASK4_POST_TEST_SOURCE_INDEX_SHA256=%s\n" \
  "${post_test_source_index_sha}"
if [[ "${post_test_source_index_sha}" != "${pre_test_source_index_sha}" ]]; then
  echo "FAIL: Task 4 source index changed during final tests" >&2
  exit 1
fi
task4_python -m compileall -q src tests scripts
printf "TASK4_COMPILE_PASS\n"

/usr/bin/git diff --check
/usr/bin/git diff --cached --check
printf "TASK4_GIT_DIFF_CHECK_PASS\n"

task4_python -c \
  'import json
import pathlib
for path in pathlib.Path("manifests").glob("*.json"):
    json.loads(path.read_text())'
printf "TASK4_EXISTING_MANIFEST_JSON_PASS\n"
task4_python scripts/verify_task4_acceptance_manifest.py
printf "TASK4_LIVE_MANIFEST_REPLAY_PASS\n"

committable_path_index="${final_run_dir}/committable-paths.nul"
if [[ -e "${committable_path_index}" \
  || -L "${committable_path_index}" ]]; then
  echo "FAIL: committable path index already exists" >&2
  exit 1
fi
if ! /usr/bin/git ls-files -z --cached --others \
  --exclude-standard > "${committable_path_index}"; then
  echo "FAIL: could not enumerate committable repository files" >&2
  exit 1
fi

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
      printf "FAIL: secret-pattern audit could not read: %q\n" \
        "${path}" >&2
      exit 1
    fi
  fi
done < "${committable_path_index}"
if [[ "${secret_findings}" -ne 0 ]]; then
  echo "FAIL: secret-pattern audit found a candidate" >&2
  exit 1
fi
printf "TASK4_SECRET_AUDIT_PASS\n"

large_file_findings=0
while IFS= read -r -d '' path; do
  if [[ ! -f "${path}" ]]; then
    continue
  fi
  byte_count="$(wc -c < "${path}")"
  if (( byte_count > 5242880 )); then
    printf "FAIL: committable file exceeds 5 MiB: %q\n" \
      "${path}" >&2
    large_file_findings=1
  fi
done < "${committable_path_index}"
if [[ "${large_file_findings}" -ne 0 ]]; then
  exit 1
fi
printf "TASK4_LARGE_FILE_AUDIT_PASS\n"

printf "TASK4_ACCEPTANCE_PASS\n"
