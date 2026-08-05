# D2T-RNA v7 — Reviewer-aware Audit (PAPER-1)

> 覆盖三个审稿视角：Methods/Reproducibility、Contribution/Novelty、Clarity/Editorial-fit。
> 项目无现成 structured_review 运行器，故按本 prompt §7 执行等价结构化 objection 登记。
> 每个 objection 记录 severity / trigger / preemptive fix / evidence locus / status。

## 视角 1：Methods / Reproducibility

| # | Objection | Severity | Trigger | Preemptive fix | Evidence locus | Status |
|---|---|---|---|---|---|---|
| T1 | cross-class nuisance coupling 与 quantifier order 是否正确 | High | §2.3/§4.3 未显式 | 显式注册 coupling=CARTESIAN/EQUAL_REALIZED_VALUE，quantifier 顺序书面化 | §10 manifest | RESOLVED |
| T2 | 完整差集 D 是否真的被使用（非 cycle 子集） | High | §3.1 | 明确 DLL：完整 D，禁止用手工子集替代 | t2_2 manifest + theorem.py | RESOLVED |
| T3 | product-law 假设是否显式 | Medium | §2.3 | 注册独立性条件后才有 product law | §10 + §4.5 | RESOLVED |
| T4 | rational certificate 是否独立检查 | Medium | §4.4 | independent checker 聚合 | t2_2/t2_4 + verify.py | RESOLVED |
| T5 | continuous nuisance / high-dim tables 是否诚实排除 | High | §2.2 | 明确不覆盖清单 | section_blueprint §4.3 | RESOLVED |

## 视角 2：Contribution / Novelty

| # | Objection | Severity | Trigger | Preemptive fix | Evidence locus | Status |
|---|---|---|---|---|---|---|
| N1 | T2 是否只是 Markov-basis/kernel/rank 重述 | High | §4.4 | 强调 composite certificate + complete D + 可重放，非新通用定理 | prior_art_novelty_matrix | RESOLVED |
| N2 | finite-sample 定理是否已被标准 binary testing 蕴含 | High | §4.5 | 绑定 registered pair catalog + abstention + exact crosscheck | t2_3 manifest | RESOLVED |
| N3 | costed design 是否只是 Test-Cover / 通用信息源选择 | Medium | §4.6 | 突出 integer design + LP dual + integrality gap + no-go | t2_4 manifest | RESOLVED |

## 视角 3：Clarity / Editorial-fit

| # | Objection | Severity | Trigger | Preemptive fix | Evidence locus | Status |
|---|---|---|---|---|---|---|
| C1 | 摘要是否意外暗示 prospective validation | High | §8 | 摘要 strict 五句，禁用词清单 | manuscript abstract | RESOLVED |
| C2 | "RNA experiment design" 是否暗示 future wet-lab cost saving | High | 标题/摘要 | 用 model-conditional / registered 限定 | claim_register P5 | RESOLVED |
| C3 | "robust" 是否暗示 population-level robustness | Medium | 正文 | 限定为 action-level / registered model | claim_register | RESOLVED |
| C4 | "third-state stress" 是否暗示生物学发现 | High | §4.8 | rorc=NOT_APPLICABLE，only terminal audit | task6r_r2 | RESOLVED |

## Evidence objections（cross-cutting）

| # | Objection | Severity | Preemptive fix | Status |
|---|---|---|---|---|
| E1 | 无 qualified retrospective quantitative instance | High | 诚实写入 Evidence Missing | RESOLVED |
| E2 | 为何 add/SAM-III not comparable | High | modality/action-space 不可比，fail-closed | RESOLVED |
| E3 | 为何 RORC NOT_APPLICABLE | High | 无正式 public accession，不替换 | RESOLVED |
| E4 | 无新 library 为何仍算 RNA methods 论文 | Medium | methods/theory 定位 + 明确边界 | RESOLVED |

## Provenance objections

| # | Objection | Severity | Preemptive fix | Status |
|---|---|---|---|---|
| PR1 | t9_4 说 Task6-R pending 而 S12 说 complete fail-closed | Medium | 登记为 HISTORICAL_SYNTHESIS_RECORD，precedence=7 | RESOLVED |
| PR2 | S14 source=728dec6 而 HEAD=f50e251 | Medium | 显式记录两 commit 差异 | RESOLVED |

## 结论

```text
PAPER_REVIEWER_AUDIT:
  methods_review_objects_resolved: true
  contribution_review_objects_resolved: true
  clarity_review_objects_resolved: true
  evidence_objects_resolved: true
  provenance_objects_resolved: true
```
Gate 判定：**PASS**（所有 objection 已登记并给出 preemptive textual fix；无 reviewer approval 伪造）。
