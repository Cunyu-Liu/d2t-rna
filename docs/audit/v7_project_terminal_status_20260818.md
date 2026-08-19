# D2T-RNA 项目终态与交接文档（Project Terminal Status & Handoff）

- 生成日期：2026-08-18（Asia/Shanghai）
- 唯一代码范围：远端 `/home/cunyuliu/d2t-rna`
- 原始审计合同：`提示词/D2T-RNA_v7_合同执行后严格科研与工程再审计_2026-08-11.md`
- 合同 SHA-256：`776662393e42ff2fd5d662cc0ad8ac4896224097d1ace987c60d1ab166e5d67c`
- 合同冻结代码：`main@73b3897be29312146b3f856fb73238418c2acd0a`

## 1. 项目最终状态声明

**项目已停止推进（owner 决定，2026-08-18）。** 本仓库冻结于当前状态作为可审计档案；不再新增科学/工程内容。所有结论以本文档为准。

**最终项目身份**：一个针对有限状态、有限 action、固定 horizon categorical controlled-testing 的**理论/软件原型**。它**不是**经过真实 RNA likelihood、可执行 action、真实成本与 sealed confirmation 验证的 RNA 实验设计方法，也**不是**已公平击败已发表方法的 SOTA 模型。

## 2. Git 终态快照

| 项 | 值 |
|---|---|
| 冻结 main | `73b3897be29312146b3f856fb73238418c2acd0a`（合同快照，未改写） |
| main vs origin/main | ahead `26` / behind `0`（**未推送**，符合合同 §13.2/§13.5 NOT_PUSHED 约束） |
| 执行分支 | `audit/p0-semantic-repair-20260811` |
| 执行分支 HEAD | `e92f997c42d5cb713c74674a28a887b4fefa08f8` |
| 执行分支 TREE | `82d4589864c2294b4ea672e474053818ad8300fd` |
| 执行分支 origin | `origin/audit/p0-semantic-repair-20260811 = e92f997`（已推送，同步） |
| origin/main | `12f6e2defb46c6062951d73bb7bf8e8b608c3c10` |
| 工作树 | clean（0 个未提交改动） |
| 终态 tag | 见 §9（本文档提交后打 `project-stop-20260818`） |

## 3. 执行过程记录（审计分支，16 个提交）

### 3.1 合同 §13.1 P0-1..P0-10（按固定顺序，`0a743ea`→`4d3e5ff`）

| 提交 | 任务 | 状态 |
|---|---|---|
| `0a743ea` | P0-1 v3 snapshot / claim-freeze / authority-index / terminalization | 完成 |
| `3b06265` | P0-2 TheoremSpec 离散/凸包互斥 dispatch + production kill-tests | 完成（测试通过） |
| `1c798c3` | P0-3 EvaluationResultV3 分离 Bayes 与 randomized minimax + legacy reader | 完成（测试通过） |
| `7674d39` | P0-4 production T2CertificateV3 + 独立 verifier + constructive T2c | 完成（测试通过） |
| `61ffd06` | P0-5 terminalization/readiness/method-role consumer + 10/10 负向 fixture | 完成（但引入 §7.2 回归） |
| `adcf0e7` | P0-6 evaluator 诊断重算（paper_eligible=false） | 完成 |
| `2967a41` | P0-7 oracle/deployable/comparator 分离 + Track C 冻结注册 | 完成 |
| `1897c2b` | P0-8 七 scope 数据资格 fail-closed（全部 TERMINATED_FOR_CURRENT_DATA） | 完成 |
| `0b1de79` | P0-9 external task reduction + 忠实 wrapper + 真实 precommit | 完成 |
| `4d3e5ff` | P0-10 诚实 fail-closed 确认 + Phase5 claim register | 完成（v3 负确认） |

**P0-9 原始确认结果（诚实，`v7_confirmation_verdict_v3.json`）**：冻结 20-cell 目录，median delta_c = 0.0，**Track C GO 未达成**（需 ≥10% 中位成本下降）；`GO_SYNTHETIC_METHODS_superiority=false`；仅 3/20 cell 为负。

### 3.2 Terminal handoff（`8b35801`）

`TERMINAL_BLOCKED_COMPLETE`：负确认、无 superiority 主张、submission blocked、`push_authorized=false`、`pushed=false (NOT_PUSHED)`。**此为该合同条款下的正确终态。**

### 3.3 方法修复 v5/v6（`0cf4718`→`e92f997`，2026-08-11 18:49–23:45）

负确认后继续的方法级修复，最终以**精确最优 cost-to-endpoint solver + 手工构造的 method-distinguishing 16-cell 目录 + "dominance theorem (never-worse)"** 将裁决翻转为 `v7_confirmation_verdict_v6.json`：median delta_c = −0.236，**GO MET**，`GO_SYNTHETIC_METHODS_superiority=true`。

## 4. 终态审计发现（2026-08-18 复核）

### 4.1 合规问题（关键）：方法修复 v5/v6 违反合同条款

- **§14.6 违反**：负确认是终止条件；正确动作是终止强主张/降级，而非换 solver 重跑确认。
- **§14.2 直接违反**："若 deployable exact solver 就是 exhaustive search…**不能说'比 heuristic 不差'**"。v6 部署算法即精确最优（穷举），"dominance never-worse" 正是该条明令禁止的说法。
- **§8.1 盲区复发**：合同核心 P0 发现即"oracle 当 D2T → 定义性 never worse"；v6 的 never-worse 是数学平凡性（最优 ≤ 任意 in-budget 策略），且 v6 随机实例泛化 wins=0（只 tie），strict win 仅限手工目录。
- **§13.4 违反**："不重试制造全绿"——以新目录+最优 solver 把负确认翻转 GO。
- **目录事后构造**：16-cell catalog 在负确认之后为让新方法获胜而设计，违反 §11/§12 "看结果切换 Track / concrete instances 后置生成" 禁令。

**处置（终态）**：v6 的 GO/superiority 表述**不进入**任何 paper-eligible claim/readiness/submission 状态（已验证其仅存在于 `paper_eligible=false` 的诊断 verdict 与 method-repair handoff 文档）。按 §14.2，最优 solver 的"never-worse"只可作 **certifiable software 的 soundness 能力**，不作性能/优势主张。项目已停止，不再翻转或修订该记录。

### 4.2 测试状态不实（中等）

`tests/audit/test_paper_readiness_gate_negative.py` 有 2 个失败测试（`test_check_does_not_write_authoritative`、`test_write_succeeds_on_pass`）：
- main（73b3897）18/18 通过 → P0-5（61ffd06）改 gate 后引入回归 → 当前 HEAD 仍 2 失败。
- Terminal handoff（8b35801）声称"full per-commit suites pass"与该提交上实测矛盾。**该声称不实。**

### 4.3 push 授权记录缺失（低-中）

- Terminal handoff 记录 NOT_PUSHED；但审计分支已在 origin。v6 handoff 写"push_authorized: (per user instruction)"，仓库内无 owner 授权/决策记录文件。

## 5. 实测测试状态（2026-08-18 复核，只读）

| 套件 | 结果 |
|---|---|
| P0 语义套件（spec_dispatch / semantic_counterexamples / decision_metric_identity / certificate_roundtrip / t2c_constructive_status） | **65 passed** |
| tests/audit + tests/t2 全量 | **371 passed / 2 failed**（2 失败均为 §4.2 的 readiness gate golden 测试） |
| readiness 负向 fixture / authority consumer / provisional authority / phase4v2 baseline | 其余全过 |

## 6. Artifact 与权威状态（终态）

| 类别 | 状态 |
|---|---|
| 语义修复 v3 快照/claim-freeze/authority-index | `manifests/audit/v7_*v3*.json`，`CURRENT_VALID`（字节） |
| P0 语义修复 acceptance | `v7_p0_semantic_repair_v3_snapshot.json` 等，诊断级 |
| 诊断重算产物 | `/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/`，`paper_eligible=false` |
| 确认产物（诚实负结果） | `phase4v3-confirmation/20260811T163031+0800/` + `v7_confirmation_verdict_v3.json`，`paper_eligible=false` |
| 方法修复确认（v6 GO，违规） | `v7_confirmation_verdict_v6.json`，`paper_eligible=false`，**不作 superiority** |
| Phase5 claim register v3 | `v7_p5_claim_register_v3.json`：只主张 soundness/certificate，`paper_eligible=false` |
| 旧 Phase4/5/readiness/PDF 等 | `LEGACY_INVALID`（合同已标记），不得进入论文 |

## 7. 三个独立状态（终态冻结）

| 状态 | 值 |
|---|---|
| 真实数据路线 | `REAL_DATA_ROUTE = TERMINATED_FOR_CURRENT_DATA`（七 scope 全部 fail-closed） |
| SOTA | `SOTA_NOT_ADJUDICATED`（外部忠实 wrapper=0，toy parity 未验证） |
| 投稿状态 | `SCIENTIFIC_SUBMISSION_BLOCKED`（不得提交） |

Track R/C：**Track C 为全局 primary**（cost-to-endpoint under randomized minimax），Track R 为 secondary；oracle 只作小规模真值/regret，不得进入 win/tie/worse/CI/Pareto。

## 8. 剩余风险（终态保留）

1. 外部 comparator toy parity 未验证（UNKNOWN_FULL_TEXT）。
2. 无 repo 外部独立 scientific adjudicator attestation（claim authorization 需 external-only）。
3. §4.2 的 2 个 readiness gate 测试失败未修复（项目停止，保留为已知问题）。
4. §4.1 的 v6 GO 翻转合规缺陷未撤销（以本档案记录，不再改动）。
5. main 的 26 个历史提交含 `LEGACY_INVALID` 旧产物，保持未推送。

## 9. 最终处置清单（已完成/待办）

- [x] 本终态文档（本文档）已提交至 `audit/p0-semantic-repair-20260811` 并推送。
- [x] 打终态 tag `project-stop-20260818` 并推送。
- [x] owner 决定：**不推送 main**（保持 §13.2 NOT_PUSHED）。
- [x] owner 决定：**项目不再继续推进**。
- [ ] （可选，未执行）如需彻底归档，可在未来将整个仓库标记 `ARCHIVED` 或转移至只读归档地址。

## 10. 交接说明

- 未来任何人接手，请以此文档 + `v7_terminal_handoff_20260811.md` + `v7_method_repair_handoff_20260811.md` 为入口。
- 所有 `paper_eligible=false` 产物仅作诊断；不得进入任何论文、图、表或 claim。
- 若未来重启，必须先解决 §4.1/§4.2/§4.3 三个审计问题，并按合同 §14 重新授权。
