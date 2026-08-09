# D2T-RNA v7 — 证据链修复执行计划（Evidence-Repair Execution Plan）

- 计划落地日期：2026-08-09（Asia/Shanghai）
- 执行仓库：远端 `/home/cunyuliu/d2t-rna`，branch `main`
- 审计基线：`D2T-RNA_v7_严格科研与工程审计_2026-08-07.md`
- **当前冻结 HEAD**：`12f6e2defb46c6062951d73bb7bf8e8b608c3c10`
- **origin/main**：`12f6e2defb46c6062951d73bb7bf8e8b608c3c10`（与 HEAD 一致）
- 工作树：clean
- Python：`/home/cunyuliu/d2t-rna/.venv/bin/python3.11` → Python 3.11.15
- import origin：`/home/cunyuliu/d2t-rna/src/d2t_rna/__init__.py`
- 包版本：numpy 2.4.6, scipy 1.17.1, pydantic 2.13.4, pytest 9.1.1, hypothesis 6.163.0

## 权威基线说明（deviation record）

计划原文要求阅读 `D2T-RNA_v7_严格科研与工程审计_2026-08-09.md`（SHA `7d6576f8...`）。
该文件在当前本地与远端均不存在。可获得的最高权威审计材料为：

- `提示词/归档/D2T-RNA_v7_严格科研与工程审计_2026-08-07.md`（已完整阅读）
- `提示词/归档/D2T-RNA_v7_交接文档_承上启下.md`（已完整阅读）
- 远端 `manifests/audit/v7_decision_tree_resolution.json`

依据计划 §2.2「若旧合同、旧审计……与 2026-08-09 审计冲突，以 2026-08-09 审计为准」，
因 08-09 审计缺失，本计划以 **08-07 审计 + 交接文档 + 当前冻结代码** 为执行基线，并在此显式记录该 deviation。
本计划自身即为后续批次的可追踪权威。

## 执行批次总览

1. **Batch 1** — Snapshot、claim freeze 与 provisional terminalization（4 个 authority 文件）
2. **Batch 2** — Typed theorem/metric/certificate 与独立 oracle 修复（K1–K8）
3. **Batch 3** — 真实数据资格、数据身份与 statistical unit contract
4. **Batch 4** — Closest prior art、baseline reduction、claim/evidence 与 readiness gate
5. **Batch 5** — P0 current-HEAD 重放、final terminalization 与里程碑判定

## 状态机（任何修复完成前固定）

```
CURRENT_STAGE = A
SCIENTIFIC_SUBMISSION_BLOCKED
SOTA_NOT_ADJUDICATED
scientific_claim_authorized = false
```

成功状态必须分开记录：
`SEMANTIC_SOFTWARE_SUCCESS` / `COMPARATIVE_SYNTHETIC_SUCCESS` / `REAL_RNA_CONFIRMATION_SUCCESS`。

## 纪律

- 不 push；不做破坏性 git 命令；不覆盖旧 `/mnt` artifacts（tombstone 化而非删除）。
- 只用 `.venv/bin/python3.11`；不生成 Python 3.12 receipt。
- 每个高内聚批次做 focused commit。
- claim 用四个结论标签；artifact 状态用五个权威标签（见计划 §四）。
