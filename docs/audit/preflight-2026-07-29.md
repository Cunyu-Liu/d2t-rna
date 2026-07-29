# D2T-RNA remote preflight

## Scope

- Host: `36.137.135.49:22`
- Remote identity: `cunyuliu@bms-18937653-012`
- Snapshot window: 2026-07-29 21:35–21:41 `+08:00`
- Method: read-only SSH checks before any project path was created
- Contract source SHA-256: `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`

This report is a time-stamped snapshot. Process, GPU, disk, and network state must be rechecked immediately before any long or GPU-backed run.

## Path and Git findings

- `/home/cunyuliu/d2t-rna`: absent.
- `/mnt/cunyuliu/d2t-rna`: absent.
- Alternate underscore spellings were also absent.
- A bounded, depth-limited scan found no D2T-RNA, SAM-III, or RORC-named path. This is not a proof that no relevant data exist elsewhere.
- The candidate project had no Git state because the path did not exist.
- Existing Git roots under `/home/cunyuliu` included mRNA-EditFlow, PC-CNG, ReactFlow stages, and LucaOne; they are out of scope and protected.

The existing repository `/home/cunyuliu/mrna_editflow_goal/mrna_editflow` was dirty and was not modified:

```text
branch: phase2-reliable-local-delta-20260727
HEAD: 9f431332a6c922d784d61ae087f253c985ad524f
untracked: benchmark_v21/external_data/LinearDesign
modified: scripts/data/download_ena_reconstruction.py
```

## Active user work that must remain untouched

Observed active work owned by `cunyuliu` included:

- ReactFlow C1.3 training on GPUs 0, 2, and 5, working directory `/home/cunyuliu/reactflow_c1_3_stage_20260722`.
- ReactFlow checkpoint evaluation on GPU 4 in the same working directory.
- ENCSR854RUF repair transfer:
  - shell PID 648365;
  - curl PID 1110442 at the snapshot;
  - output `/mnt/cunyuliu/mrna_editflow_p0/ENCSR854RUF/reconstructed/ENCFF597AIT.fastq.gz.part`;
  - 61 final files plus 1 `.part`;
  - `.part` size 4,496,114,476 bytes at 21:37:52.
- Home-data migration/cutover audit in tmux session `quota_remaining_cutover_20260729`.

No existing task was stopped, reprioritized, or modified.

## GPU snapshot

All devices are NVIDIA A100-PCIE-40GB with driver 580.126.09.

| GPU | Used MiB | Free MiB | GPU util | Protected observations |
|---:|---:|---:|---:|---|
| 0 | 40,342 | 99 | 100% | active multi-user jobs, including user ReactFlow |
| 1 | 40,341 | 101 | 100% | active multi-user jobs |
| 2 | 38,830 | 1,611 | 100% | active multi-user jobs, including user ReactFlow |
| 3 | 39,281 | 1,160 | 0% snapshot | active allocated processes |
| 4 | 33,466 | 6,975 | 100% | active jobs, including user ReactFlow evaluation |
| 5 | 39,438 | 1,003 | 100% | active multi-user jobs, including user ReactFlow |
| 6 | 2,527 | 37,914 | unavailable in query | active GROMACS processes |
| 7 | 23,249 | 17,193 | unavailable in query | many active multi-user processes |

Conclusion:

- CUDA hardware is present.
- No D2T-RNA GPU process exists.
- Task 1 is CPU-only schema work and does not need a GPU.
- A later GPU validation may use a device with sufficient free memory only after a fresh ownership, memory, utilization, and CUDA check.
- The presence of free memory does not authorize terminating or altering existing jobs.
- Any CUDA unavailability or CPU fallback is a hard stop with an evidence bundle.

## Capacity snapshot

```text
CPU threads: 96
load average: approximately 148 / 156 / 159
RAM: 754 GiB total, 467 GiB available
swap: 1.9 GiB total, 1.9 GiB used
/home: 7.0 TiB total, 5.4 TiB available, 19% used
/mnt: 18 TiB total, 13 TiB available, 31% used
/home inode use: 3%
/mnt inode use: 12%
```

The server was heavily loaded. Do not add high-CPU parallel work without a fresh capacity check.

## Runtime snapshot

- System `python3.11`: unavailable.
- Existing Python 3.11 environment: none found in the bounded environment scan.
- Conda: 26.3.2 at `/home/cunyuliu/miniconda3`.
- Existing environments are protected and will not be modified.
- Python 3.11 package cache was not found in the checked Conda caches.
- Git: 2.34.1.
- Git identity:
  - name `liucunyu`;
  - email `tylcy020509@qq.com`.
- GitHub CLI `gh`: unavailable both on the remote host and the local control host.
- Authenticated GitHub connector identity: `Cunyu-Liu`.
- Remote Git SSH authentication: verified as `Cunyu-Liu` by `ssh -T git@github.com` (GitHub's expected success message with exit status 1 because shell access is disabled).
- `Cunyu-Liu/d2t-rna`: not found at preflight time.

The primary Python 3.11 environment attempt targets `/mnt/cunyuliu/d2t-rna/envs/`. If the NFS-backed transaction meets the registered no-progress stop rule, a project-local ignored `.venv` is the authorized software-runtime recovery; datasets, weights, checkpoints, logs, and generated scientific artifacts remain under `/mnt`. The remote host has push credentials, but GitHub repository creation must still be completed before Task 1 can be called fully published.

## Preflight cleanup event

The first related-path scan was too broad for the shared filesystem. The local SSH client was interrupted, but the remote shell and its `find`/`head` children remained.

Before termination, all three were revalidated by exact PID, parent relation, user, and a command signature containing this run's `RELATED_PATH_SCAN` and candidate roots:

```text
parent shell: 1277985
find child: 1277994
head child: 1277995
```

`SIGTERM` was sent only to these three preflight-created processes. A subsequent process check returned no matching PIDs. No pre-existing process was signaled.

## Preflight gate

Result: `PASS_WITH_REGISTERED_CONSTRAINTS`

The project may be initialized because both target roots were absent and capacity is sufficient for lightweight Task 1 work. Constraints:

1. do not modify existing repositories, jobs, downloads, or migration evidence;
2. use an isolated Python 3.11 environment under `/mnt`;
3. keep all generated data, environments, weights, checkpoints, and artifacts under `/mnt/cunyuliu/d2t-rna`;
4. recheck server and GPU state before each long or CUDA-backed run;
5. resolve GitHub repository creation before reporting Task 1 as uploaded.

## Post-preflight execution note

The first isolated Python 3.11 environment attempt followed constraint 2 and targeted `/mnt/cunyuliu/d2t-rna/envs/py311`. Package download completed, but the Conda transaction spent more than eight minutes with no new file writes while its main process remained in `rpc_wait_bit_killable`. It was safely sent `SIGTERM` after exact command/PID verification; the log and incomplete directory were preserved.

The recovery environment was created at the ignored software path `/home/cunyuliu/d2t-rna/.venv`, with package caches also ignored. This does not move datasets, weights, checkpoints, or generated scientific artifacts out of `/mnt`; it avoids pathological NFS small-file transactions for the Python runtime. See `docs/audit/environment-bootstrap-2026-07-29.md`.
