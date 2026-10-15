# Schemas

## 概述

本目录存放 AI Grandma 项目中规则类配置文件的 JSON Schema（draft 2020-12）。所有实际配置内容用 YAML 书写，校验时先用 `yaml.safe_load` 读成 Python 对象，再用 `jsonschema` 库校验。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `common.schema.json` | 共享定义（$defs）：meta、i18n_text、language_code、slot_id、level_id、module_id、redflag_exit_type、duration_value、condition（三值逻辑条件表达式）、versions、slot_value、session_id、outcome_link_key。本身不校验任何配置文件，只供其他 schema 引用。 |
| `redflag_rules.schema.json` | 红旗（急症）规则文件格式。红旗规则每一轮对话都要评估；红旗规则永远不进入自动优化，只能由医生手动修改。 |
| `question_tree.schema.json` | 追问树文件格式。按症状模块定义追问问题、优先级和停止条件。 |
| `decision_table.schema.json` | 决策表文件格式。按症状模块定义条件到级别的映射，含冲突解决和不确定性策略。 |
| `selfcare_card.schema.json` | 自护卡片文件格式。L3.1 层输出的内容单元（缓解办法、常见虚惊情形、需留意的信号、升级就医的条件），只做缓解、解释和升级提示，不做诊断。 |
| `facility.schema.json` | 医疗机构数据表格式。L4 就医推荐层使用，包含机构类型、服务能力、费用档位、补贴与转介要求、是否接诊未成年人等属性。 |
| `user_profile.schema.json` | 用户档案对象格式（非 meta 包装）。存储 L4 排序所需的用户身份、出行方式、区域位置、权重档案、就诊记录和同意信息。档案不含年龄、出生日期、姓名、联系方式、精确位置。 |
| `weight_presets.schema.json` | L4 机构排序权重配置格式。定义排序特征、参与权重排序的级别、默认权重、用户可选预设、安全边界和急症排序策略。硬过滤和红旗规则不受权重影响。 |
| `questionnaire_mapping.schema.json` | 设置页问卷映射格式。定义问卷问题、选项及其对权重的效应（set_base_preset / add_delta / multiply / set_profile_field），以及组合计算流程（裁剪到边界、归一化为总和 1）。 |
| `interfaces/session_state.schema.json` | 会话状态接口。流水线各层之间传递的共享状态，含槽位、已问问题、候选级别、版本号等。不含原始文本、精确坐标、姓名。 |
| `interfaces/intake_result.schema.json` | Intake 结果接口。LLM 槽位抽取的输出，含提取的槽位、是否需要澄清、检测到的语言。槽位 id 与取值与语言无关。 |
| `interfaces/redflag_result.schema.json` | L1 红旗结果接口。红旗规则评估结果，含命中规则、出口类型、险情记录。多条命中时取更紧急的出口。 |
| `interfaces/grading_result.schema.json` | L2 分级结果接口。追问和决策表的输出，含级别、轨迹、停止原因、不确定性升级标记。 |
| `interfaces/selfcare_output.schema.json` | L3.1 自护输出接口。选中的卡片列表，含是否包含升级就医条件。SELF_CARE 级别必须包含升级条件。 |
| `interfaces/recommendation_request.schema.json` | L4 推荐请求接口。L4 的输入，含级别、权重、用户身份字段、位置（坐标仅内存使用）。 |
| `interfaces/ranked_places.schema.json` | L4 排序结果接口。含硬过滤排除列表和按特征得分排序的候选机构。急症模式按通勤时间排序。 |
| `interfaces/final_response.schema.json` | 最终回复接口。人设层输出，含展示文本（不入日志）、级别、输出校验结果。emergency_exit 必须对应 EMERGENCY_NOW。 |
| `events.schema.json` | 事件日志格式。单条事件，用 oneOf 按 event_type 区分 payload。不含原始文本、精确坐标、姓名、联系方式、问卷答案、FinalResponse.text。 |

## 跨文件 $ref 解析方式

各 schema 通过 `$ref` 引用 `common.schema.json` 中的 `$defs`。解析使用 Python `referencing` 库的 `Registry`：

```python
import json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

with open('contracts/schemas/common.schema.json') as f:
    common = json.load(f)
with open('contracts/schemas/redflag_rules.schema.json') as f:
    schema = json.load(f)

registry = Registry().with_resource(
    'https://ai-grandma/schemas/common.schema.json',
    Resource.from_contents(common)
)

validator = Draft202012Validator(schema, registry=registry)
```

每个 schema 文件的 `$id` 与 `$ref` 中的 URI 保持一致。`common.schema.json` 的 `$id` 为 `https://ai-grandma/schemas/common.schema.json`，其他 schema 通过 `common.schema.json#/$defs/xxx` 引用。

## 多语言文本（i18n_text）与语言代码（language_code）

`i18n_text`（定义在 `common.schema.json` 中）是所有用户可见文本的标准结构：

- `en`（英文字符串，必填，非空）：源文本。
- `zh` / `ms` / `ta`（可选字符串）：简体中文 / 马来语 / 泰米尔语翻译。
- `additionalProperties: false`：不允许 `en` / `zh` / `ms` / `ta` 以外的键。
- **语言回退规则**：某种语言缺少翻译时，回退显示英文。
- **医学文本审核要求**：非英文的医学类文本须经母语者或临床医生审核后才能视为可靠；机器翻译只能算草稿。

`language_code`（定义在 `common.schema.json` 中）是支持的语言代码枚举：`en` / `zh` / `ms` / `ta`。后续用户档案和事件日志会引用此定义。

## 条件表达式的三值逻辑语义

`condition`（定义在 `common.schema.json` 中）采用三值（Kleene）逻辑：

- 每个谓词的求值结果为 **true / false / unknown**。
- 当涉及的槽位状态为 `unknown`、`declined` 或 `not_asked` 时，该谓词结果为 **unknown**——除非操作符本身是 `is_unknown` / `is_answered` / `is_declined`（这三个操作符始终返回 true 或 false）。
- `all_of`（逻辑与）按 Kleene 逻辑组合：unknown AND false = false；unknown AND true = unknown。
- `any_of`（逻辑或）按 Kleene 逻辑组合：unknown OR true = true；unknown OR false = unknown。
- `not`（逻辑非）：NOT unknown = unknown。
- 各规则文件自行声明遇到 unknown 时怎么处理（例如红旗规则的 `on_unknown` 字段、决策表的 `uncertainty_policy`）。

## format 检查

校验时需要启用 `format` 检查（`date`、`uri` 等），通过传入 `FormatChecker()` 实现：

```python
from jsonschema import FormatChecker
validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
```

`facility.schema.json` 的 `website` 字段使用 `format: uri`，`meta.sources` 的 `url` 和 `accessed` 字段分别使用 `format: uri` 和 `format: date`。不启用 format 检查时这些约束不会被校验。

## 校验命令

临时校验示例：

```bash
python3 -c "
import json, yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

with open('contracts/schemas/common.schema.json') as f:
    common = json.load(f)
with open('contracts/schemas/redflag_rules.schema.json') as f:
    schema = json.load(f)

registry = Registry().with_resource(
    'https://ai-grandma/schemas/common.schema.json',
    Resource.from_contents(common)
)
from jsonschema import FormatChecker

validator = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())

with open('contracts/examples/redflag_rules.valid.yaml') as f:
    data = yaml.safe_load(f)
errors = list(validator.iter_errors(data))
print('PASS' if not errors else 'FAIL: ' + str(errors))
"
```

## 语义检查说明

本步只校验 JSON Schema 层面的格式（字段是否齐全、类型是否正确、enum 取值是否合法等）。**语义检查**（例如 slot id 是否真实存在于 `slots.yaml`、enum 取值是否与槽位定义一致、condition 中引用的 slot 是否合法等）不在本步范围内，将由后续步骤的 `validate_contracts.py` 完成。

## 跨字段 / 跨文件约束清单（由后续校验脚本检查）

以下约束无法用 JSON Schema 表达，在各自 schema 的 description 里已写明，由 `validate_contracts.py` 负责检查：

### weight_presets
1. `default_weights_by_level` 和 `presets[].weights_by_level` 中每个级别的权重总和必须为 1。
2. 权重对象中的每个 feature id 必须在 `features` 数组中定义。
3. `default_weights_by_level` 和 `presets[].weights_by_level` 的键必须与 `ranking_levels` 一致。
4. `bounds_by_level` 必须覆盖 `features` 中定义的所有特征。
5. `bounds_by_level` 的键必须与 `ranking_levels` 一致。
6. `bounds_by_level` 中每个 bound 的 `min` ≤ `max`。

### questionnaire_mapping
7. `effects` 中引用的 `feature` 必须在 `weight_presets.features` 中定义（跨文件检查）。
8. `effects` 中 `set_base_preset` 引用的 `preset_id` 必须在 `weight_presets.presets` 中存在（跨文件检查）。
9. `combination.start_from` 为 `base_preset` 时，至少一个 effect 应包含 `set_base_preset`（否则起点无效）。

### user_profile
10. `weight_profile.computed_weights` 中每个级别的权重总和必须为 1。
11. `weight_profile.computed_weights` 中的 feature id 必须在 `weight_presets.features` 中定义（跨文件检查）。
12. `weight_profile.computed_weights` 的键必须只包含 `weight_presets.ranking_levels` 中的级别（跨文件检查）。
13. `visit_history` 中的 `facility_id` 必须在 `facilities` 配置中存在（跨文件检查）。
14. `visit_history` 仅在 `consent.visit_history` 为 true 时才应存在。
15. `questionnaire_answers` 中的 question id 必须在 `questionnaire_mapping.questions` 中定义（跨文件检查）。

### 接口 schema（interfaces/）
16. `SessionState.slots` 中的 slot id 必须存在于 `slots.yaml`（跨文件检查）。
17. `SessionState.user_profile_ref` 必须引用一个存在的用户档案（运行时检查）。
18. `IntakeResult.extracted_slots` 中的 slot id 必须存在于 `slots.yaml`。
19. `RedFlagResult.triggered_rules` 中的 rule_id 必须存在于红旗规则配置中（跨文件检查）。
20. `GradingResult.module` 和 `GradingResult.matched_row_ids` 引用的决策表行必须存在（跨文件检查）。
21. `SelfCareOutput.card_ids` 必须存在于自护卡片配置中（跨文件检查）。
22. `RecommendationRequest.weights` 中的 feature id 必须在 `weight_presets.features` 中定义（跨文件检查）。
23. `RankedPlaces.ranked[].facility_id` 必须存在于机构配置中（跨文件检查）。
24. `FinalResponse.refs` 中的 question_id、card_ids、facility_ids、rule_ids 必须引用各自配置中存在的条目（跨文件检查）。
25. `FinalResponse.output_validation.checks` 必须包含全部 5 项检查（运行时检查）。

### 事件日志（events.schema.json）
26. `payload` 中的 slot_id、rule_id、question_id、facility_id 引用必须有效（跨文件检查）。
27. `payload` 不得包含原始用户文本、精确坐标、姓名、联系方式、FinalResponse.text 或问卷具体答案。
28. `session_id` 和 `outcome_link_key` 不得由任何个人信息派生。
