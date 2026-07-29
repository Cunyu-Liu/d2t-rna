#!/usr/bin/env bash
set -euo pipefail

run_id="${1:?usage: run_task1_acceptance.sh RUN_ID}"
repo_root="/home/cunyuliu/d2t-rna"
artifact_root="/mnt/cunyuliu/d2t-rna/artifacts/runs/${run_id}"
log_path="${artifact_root}/run.log"
snapshot_index="${artifact_root}/source_files.sha256"
large_file_audit="${artifact_root}/out_of_scope_large_files.txt"
pycache_root="/mnt/cunyuliu/d2t-rna/tmp/${run_id}-pycache"
contract_sha256="87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"

mkdir -p "${artifact_root}" "${pycache_root}"
exec > >(tee "${log_path}") 2>&1
set -x

cd "${repo_root}"

.venv/bin/python --version
.venv/bin/python -m pytest -q
PYTHONPYCACHEPREFIX="${pycache_root}" .venv/bin/python -m compileall -q src tests

observed_contract_sha256="$(
  sha256sum contracts/D2T-RNA-v6.1-frozen-plan.md | cut -d' ' -f1
)"
test "${observed_contract_sha256}" = "${contract_sha256}"

git diff --check

find \
  "${repo_root}/.gitignore" \
  "${repo_root}/AGENTS.md" \
  "${repo_root}/README.md" \
  "${repo_root}/contracts" \
  "${repo_root}/docs" \
  "${repo_root}/manifests" \
  "${repo_root}/pyproject.toml" \
  "${repo_root}/scripts" \
  "${repo_root}/src" \
  "${repo_root}/tests" \
  -type f \
  ! -name '*.pyc' \
  ! -path '*.egg-info/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/.pytest_cache/*' \
  ! -path '*/.hypothesis/*' \
  -print0 \
  | sort -z \
  | xargs -0 sha256sum \
  > "${snapshot_index}"

find \
  "${repo_root}/contracts" \
  "${repo_root}/docs" \
  "${repo_root}/manifests" \
  "${repo_root}/scripts" \
  "${repo_root}/src" \
  "${repo_root}/tests" \
  -type f \
  -size +5M \
  -print \
  > "${large_file_audit}"
test ! -s "${large_file_audit}"

if grep -R -n -I -E \
  --exclude='*.pyc' \
  --exclude-dir='__pycache__' \
  --exclude-dir='.pytest_cache' \
  --exclude-dir='.hypothesis' \
  -- \
  '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,}' \
  .gitignore AGENTS.md README.md contracts docs manifests pyproject.toml scripts src tests
then
  exit 1
fi

sha256sum "${snapshot_index}"
