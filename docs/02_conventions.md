# 约定文档

本文档规定 AI Grandma 项目的命名、版本、多语言、修改流程等约定，所有贡献者必须遵守。

## 1. 命名规则

| 内容类型 | id 前缀 | 格式 | 示例 |
|---------|--------|------|------|
| 红旗规则 | `RF_` | `RF_[A-Z0-9_]+` | `RF_HEAVY_BLEEDING_CLOTHES` |
| 追问问题 | `Q_` | `Q_[A-Z0-9_]+` | `Q_FLOW_COMPARED` |
| 决策表行 | `DT_` | `DT_[A-Z0-9_]+` | `DT_HEAVY_001` |
| 自护卡片 | `SC_` | `SC_[A-Z0-9_]+` | `SC_RELIEF_EXAMPLE` |
| 医疗机构 | `FAC_` | `FAC_[A-Z0-9_]+` | `FAC_KKH_URGENT` |
| 槽位 | 无前缀 | `^[a-z][a-z0-9_]*$` | `age_band` |
| 级别 | 全大写 | 枚举 | `SELF_CARE`, `BOOK_SOON`, `SEE_DOCTOR_24_48H`, `EMERGENCY_NOW` |
| 模块 | 小写蛇形 | 枚举 | `heavy_bleeding`, `severe_period_pain` |

## 2. 版本与状态规则

### 版本
- 每次修改配置文件（YAML 或 JSON Schema）必须升 `meta.version`（语义化版本：major.minor.patch）。
- 每次修改必须在 `docs/CHANGELOG.md` 记录。

### 状态（status）
| 值 | 含义 |
|----|------|
| `draft_unreviewed` | 草稿，未经临床审核。MVP 阶段所有医学内容保持此状态。 |
| `clinician_reviewed` | 临床医生已审核。要求：reviewer 非空、last_verified 非空、sources 至少 1 项、needs_clinician_review 为 false。 |
| `approved` | 正式批准。同 clinician_reviewed 要求。 |

状态流转：`draft_unreviewed` → `clinician_reviewed` → `approved`。MVP 阶段不进行流转，所有内容保持 `draft_unreviewed`。

> **MVP 说明**：本项目为黑客松原型，没有临床医生审核。MVP 阶段以"权威来源引用"替代医生审核（每条医学内容必须引用公开权威来源），正式上线前仍需临床审核。

## 3. 多语言规则

- 英文（en）是源文本，必填且非空。
- 中文（zh）、马来语（ms）、泰米尔语（ta）可选。
- 缺失翻译时回退显示英文。
- 所有用户可见文本使用 `i18n_text` 对象：`{en: string, zh?: string, ms?: string, ta?: string}`。
- 翻译不得改变原意。
- ms/ta 的医学文本需由母语者或临床医生审核后才可靠。

## 4. 修改流程

1. **新增槽位**：走 `contracts/slot_change_requests/` 流程，填写提案模板。
2. **修改内容文件**（规则、问题、决策表、卡片、机构）：
   - 升 `meta.version`
   - 运行 `python tools/validate_contracts.py`，确保无 ERROR
   - 在 `docs/CHANGELOG.md` 记录
3. **修改 Schema**：记录到 `docs/open_questions.md`（如发现缺陷），不要自行大改。

## 5. 术语表

| 英文 | 中文 | 说明 |
|------|------|------|
| level | 级别 | 四级分诊：EMERGENCY_NOW / SEE_DOCTOR_24_48H / BOOK_SOON / SELF_CARE |
| module | 模块 | 症状模块：heavy_bleeding / severe_period_pain / late_or_missed_period / irregular_or_intermenstrual_bleeding |
| slot | 槽位 | 结构化信息字段，由 LLM 从用户输入抽取 |
| red flag | 红旗 | 急症信号，命中即输出"立即就医" |
| near miss | 险情 | 接近阈值但未触发的规则，用于记录和未来优化 |
| self-care card | 自护卡片 | L3.1 层输出给用户的内容单元 |
| facility | 机构 | L4 层推荐的医疗机构 |
| escalation | 升级 | 从低级别向高级别转变 |
| i18n_text | 多语言文本 | `{en, zh?, ms?, ta?}` 对象 |

## 6. 禁止事项

- **不得诊断**：不说"你可能得了某某病"，只做分级和就医/自护指引。
- **不得写药名和剂量**：用户可见文本中不得出现具体药物名称和数字剂量；允许使用泛称如"可咨询药师"。
- **不得存精确坐标**：机构坐标范围限制在新加坡大致区域内，不得存精确家庭住址。
- **不得使用真实用户数据**：开发和测试只用虚构的合成病例。
- **不得提交密钥**：API key、token 等不得提交到代码仓库。
- **不得使用 `_zh`/`_en` 后缀的键**：已迁移为 `i18n_text` 对象。

## 7. 如何运行校验与测试

### 校验脚本
```bash
python tools/validate_contracts.py
# --strict 将 WARNING 也视为失败
python tools/validate_contracts.py --strict
```

### 测试
```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## 8. 内容目录

| 目录 | schema | 用途 |
|------|--------|------|
| `contracts/rules/` | `redflag_rules` | 红旗（急症）规则 |
| `contracts/questions/` | `question_tree` | 追问树（按模块） |
| `contracts/decision_tables/` | `decision_table` | 决策表（按模块） |
| `contracts/selfcare/` | `selfcare_card` | 自护卡片 |
| `contracts/facilities/` | `facility` | 医疗机构数据 |
| `contracts/weights/` | `weight_presets` | L4 排序权重配置 |
| `contracts/questionnaire/` | `questionnaire_mapping` | 设置页问卷到权重的映射 |

`contracts/examples/` 放格式演示示例，不参与 MVP source 检查和内容完整性 WARNING。

## 9. 校验脚本检查项一览

### 格式校验（JSON Schema）
所有 YAML 文件用 `yaml.safe_load` 读成 Python 对象后，按对应 schema 校验（含 `$ref` 解析和 `format` 检查）。

### 字典检查
- `levels.yaml`：4 个级别、severity_rank 唯一、escalation_rule.order 覆盖全部级别。
- `modules.yaml`：4 个模块、id 匹配。
- `slots.yaml`：id 唯一且匹配 `^[a-z][a-z0-9_]*$`、enum 有 allowed_values 且 label.en 非空、非 enum 无 allowed_values、module_tags 引用有效模块、used_by 非空且值合法、derived=true 需要 derivation_note、int/float 的 range min ≤ max。

### 语义交叉检查
- **红旗规则**：condition/near_miss_condition 引用的 slot 存在且操作符与类型兼容、枚举取值在 allowed_values 内、on_unknown=ask_followup 时 followup_slots 非空、scope 引用有效模块、reviewed/approved 状态的规则 sources 非空且 needs_clinician_review=false。
- **追问树**：question_id 唯一、slot/also_fills 引用有效 slot、answer_options 的 value 在 slot allowed_values 内、precondition 条件合法、required_slots 被某问题填充或为 derived、entry_condition 和 stopping.stop_when 条件合法。
- **决策表**：row_id 唯一、when 条件合法、module 引用有效、conflict_resolution=first_match_by_priority 时每行有 priority、default_row 存在、**WARNING**：某级别从未被任何行产生（示例文件豁免此 WARNING）。
- **自护卡片**：card_id 唯一、module 引用有效、applies_when 条件合法、SELF_CARE 级别必须有 escalation_criteria 卡片、reviewed/approved 状态的卡片 sources 非空。
- **机构表**：facility_id 唯一（含跨文件）、type=urgent_og/a_e 时建议 walk_in_available=true（WARNING）、meta.last_verified 过期 WARNING（>180 天）、reviewed/approved 状态的机构 sources 非空。
- **权重预设**：feature id 唯一、default_weights_by_level/presets[].weights_by_level 的键属于 ranking_levels、权重总和 1 ± 0.001（ERROR）、每个权重落在 bounds_by_level 的 [min,max] 内（ERROR）、bounds_by_level 覆盖所有 features（ERROR）、preset_id 唯一（ERROR）、ranking_levels 不含 EMERGENCY_NOW 或 SELF_CARE（ERROR）、bounds 的 min ≤ max。
- **问卷映射**：question_id 唯一（ERROR）、option_id 唯一（ERROR）、effects 引用的 feature 存在于 weight_presets.features（ERROR，跨文件）、set_base_preset 引用的 preset_id 存在于 weight_presets.presets（ERROR，跨文件）、levels 属于 ranking_levels（ERROR）、set_profile_field 的 value 是合法枚举值（ERROR）、multi_select=false 时多个选项对同一特征用相同 factor 的 multiply（WARNING）、问卷 meta.version 与 weight_presets meta.version 不一致（WARNING）。

### MVP source 检查
`contracts/rules/`、`contracts/decision_tables/`、`contracts/selfcare/` 下的内容文件（非示例），每条 rule/row/card 的 sources 必须非空（ERROR）。

### 内容安全 lint
扫描 `rules`、`questions`、`decision_tables`、`selfcare` 下的内容文件（非示例）的 i18n_text 文本（en 和 zh）：
- 药名匹配 → ERROR
- 剂量模式匹配 → ERROR
- 诊断式表述匹配 → WARNING
- 自护卡片的 content_attestation 与 lint 结果不一致 → ERROR（attestation mismatch）
- ms/ta 文本不自动扫描，记录 INFO 提醒人工审核。

## 10. 提交信息规范

格式：`<步骤编号>: <简述>`

示例：
- `0d-2a: selfcare_card and facility JSON schemas with format examples`
- `0f-lite: contract validator, lint, tests, conventions`
