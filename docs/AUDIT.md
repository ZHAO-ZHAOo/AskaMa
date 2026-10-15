# 仓库审计（2026-10-11，基于 commit 3e17bfd）

## 1. 现状：能跑，但没有 LLM
- `tools/validate_contracts.py`：0 ERROR / 1 WARNING。`pytest`：27 passed（只测校验器，**没有引擎测试**）。`run_demo.py`：能跑通。自带评测：22 例，准确率 59%，under-triage 27%。（需 Python ≥3.10；本机 3.9 跑不了，已建 `.venv` 用 3.12。）
- **`src/llm/` 是空目录。** Intake 是 `orchestrator.py` 里的关键词匹配（如文本里出现"38"就算发烧）；回复是 `persona.py` 里写死的几段话。这就是"回答差"的根本原因。
- `persona.py` 的 `output_validation` 全部硬编码为 `True`，**没有做任何校验**。
- 没有医生摘要，没有"判断依据"展示，没有回显确认，没有范围判断（第 8 节）。

## 2. 目录用途与运行时是否用到
| 目录/文件 | 用途 | 运行时用到？ |
|---|---|---|
| `contracts/rules/redflag_rules.yaml` | 10 条红旗 | 是 |
| `contracts/questions/`、`decision_tables/` | 4 个模块的追问树与决策表 | 是 |
| `contracts/selfcare/` | 自护卡片（均为非药物，合规） | 是 |
| `contracts/slots.yaml`、`levels.yaml`、`modules.yaml` | 槽位/级别/模块字典 | 是 |
| `contracts/facilities/` | 6 家具体机构 + 电话 | 是（结果里直接列出） |
| `contracts/weights/`、`questionnaire/` | 机构排序权重 + 设置页问卷 | 是（L4 排序、`/settings`） |
| `contracts/schemas/`、`examples/` | JSON Schema 与正反例 | 仅校验器 |
| `src/onemap/` | OneMap 适配器 | **否，死代码** |
| `src/templates/settings.html` | 权重偏好设置页 | 是，但规格不需要 |
| `docs/content/cases_*.md` | 22 例合成评测病例 | 评测脚本 |
| `docs/content/fixed_copy.md` | 固定文案，被 `persona.py` 用正则解析 | 是（脆弱） |

## 3. 与说明书的冲突（严重程度从高到低）
1. **第 4.2 节描述的红旗规则文件不在本仓库。** `RF_HEMO_001 / RF_HEAVY_001 / RF_PREG_001 / RF_ANTICOAG_001 / RF_POSTMENO_001 / RF_SHOULDER_001`、槽位 `bleeding_currently / palpitations_or_breathless / pallor_or_weakness` 均不存在。→ 见第 5 节问题 1。
2. **没有任何妊娠相关红旗**，痛经模块也不问怀孕。违反"第一道安全闸门"。抗凝药、节育环、绝经后出血、棉条+发热也都没有规则（`on_blood_thinner` 槽位存在但无人使用）。
3. **红旗里有无出处的数值阈值**：疼痛 ≥9 → 急诊、突发 + ≥7 → 急诊、每小时浸透 → 急诊，引用的 NICE 页面并无这些分界。决策表也有 ≥7 / ≥6 / <6 的分界。违反硬约束 5。
4. `RF_GLOBAL_NEAR_FAINTING`："差点晕倒" 无任何出血/疼痛限定即触发急诊——与你在 4.2-1 指出的过度触发问题同类。
5. **用户可见文本里有病名**：`RF_SP_SUDDEN_PAIN` 写"卵巢扭转或破裂"，其他规则有"感染""贫血"。lint 漏检，因为 denylist 没有这些词，且病名只报 WARNING。
6. 机构：推荐具体诊所并排名，带电话、`fee_tier`；包含占位的 "Ang Mo Kio GP Clinic (Example)"、电话 `6xxx-xxxx`，会直接显示给用户。KKH 来源 URL 是旧地址。违反 3.3 "只推类型和区域，不排名"。
7. 评测标签由 CodeBuddy 生成，未经临床核对（违反第 10 节）。
8. 三值逻辑：`evaluator.py` 的 `all_of / any_of` **已是 Kleene 语义**，4.2-9 无需改，但要补单测。
9. 级别规则结构是"每模块一张表 + `rows`"，不是说明书写的单一 `decision_table.yaml` + `tier_rules`。建议沿用现结构，不改名。

## 4. 建议砍掉（等你确认，我不会动）
- `contracts/weights/` + `contracts/questionnaire/` + `settings.html` + `src/engine/l4_recommend.py`：205 行无出处的数值权重，用于给机构打分排序，而规格要求不排名。
- `src/onemap/`：死代码，且第 13 节明确不做 OneMap。
- `contracts/schemas/interfaces/` 和 `examples/` 中 L4 排序、问卷、权重相关的 schema/示例（随上一条一起删）。
- `facilities/` 改为"机构类型 + 区域"清单，具体机构只保留已核实的 KKH Urgent O&G 和公立 A&E。

## 5. 需要你决定的问题
1. 4.2 节的红旗规则：你手上是否有另一版文件？若有，请放进 `contracts/rules/`（红旗规则只能由你改）。若没有，我按 4.2 起草一份**新文件**给你审，不覆盖现有文件。
2. 用哪个 LLM？（腾讯赛道是否要求混元？需要 API key 放 `.env`。）
