# 内容阶段计划

本文档规划 Step 0（契约阶段）完成后进入的**内容阶段**的具体任务。项目负责人明确要求：**先把所有规则内容写完，再进入工程阶段统一搭建框架并串联。不要边搭框架边写规则。**

## 核心原则

1. **内容阶段不写应用代码。** 所有工程代码（规则引擎、前端、API、日志等）在内容全部完成后的工程阶段统一实现。
2. **工程阶段不改内容含义。** 如果工程阶段发现内容问题，只能提交修改请求给内容负责人，不能自行修改规则。
3. **统一完成标准**：每个内容任务完成时，`python tools/validate_contracts.py` 无 ERROR；每条内容 sources 非空；来源已人工抽查。

---

## C1 红旗规则

### 输出文件
- `contracts/rules/redflag_rules.yaml`：全局红旗规则 + 4 个模块的专属规则。
- `docs/content/redflag_evidence.md`：证据表，每条规则记录来源、概括、分歧、取舍。

### 需要引用的 schema 与槽位
- schema: `contracts/schemas/redflag_rules.schema.json`
- 槽位: `contracts/slots.yaml` 中 `used_by` 含 `l1_redflag` 的槽位
- 级别: `EMERGENCY_NOW`，红旗出口类型: `CALL_AMBULANCE` / `GO_URGENT_OG_OR_AE`

### 内容范围
- 全局规则：适用于所有模块的红旗条件（如发烧、晕厥等）。
- 模块专属规则：`heavy_bleeding`、`severe_period_pain`、`late_or_missed_period`、`irregular_or_intermenstrual_bleeding` 各自的急症条件。
- 每条规则包含：rule_id、scope、condition（三值逻辑）、exit_type、on_unknown、rationale、user_note、near_miss_condition（如有）、followup_slots（如有）、sources。

### 完成标准
- `python tools/validate_contracts.py` 无 ERROR。
- 每条规则 sources 非空（至少含 title 和 url）。
- 来源已人工抽查：每条规则的 condition 能追溯到来源文档的具体表述。
- 来源有分歧时取更保守的方案，在 `redflag_evidence.md` 中记录分歧和取舍理由。

---

## C2 追问逻辑与决策表

### 输出文件
- `contracts/questions/<module>.yaml`：每个模块一份追问树。
- `contracts/decision_tables/<module>.yaml`：每个模块一份决策表。
- `docs/content/cases_<module>.md`：每个模块一批用于评测的合成病例草稿（按所引用指南构造，标注期望级别）。

### 需要引用的 schema 与槽位
- schema: `contracts/schemas/question_tree.schema.json`、`contracts/schemas/decision_table.schema.json`
- 槽位: `contracts/slots.yaml` 中对应模块的 `module_tags` 槽位
- 级别: `SELF_CARE` / `BOOK_SOON` / `SEE_DOCTOR_24_48H`

### 内容范围
- **优先 `heavy_bleeding` 和 `severe_period_pain`**，其余两个模块（`late_or_missed_period`、`irregular_or_intermenstrual_bleeding`）视时间决定。
- 追问树：question_id、slot、text（i18n）、answer_options、priority、precondition、stopping 条件、required_slots、max_questions。
- 决策表：row_id、when（条件）、level、priority、rationale、sources、default_row、conflict_resolution、uncertainty_policy。
- 合成病例：模拟对话历史、期望级别、参考来源。

### 完成标准
- `python tools/validate_contracts.py` 无 ERROR。
- 每行决策表 sources 非空。
- required_slots 均被某问题填充或为 derived。
- 合成病例的期望级别与所引用指南一致。
- 来源已人工抽查。

---

## C3 自护指南

### 输出文件
- `contracts/selfcare/<module>.yaml`：每个模块的自护卡片。

### 需要引用的 schema 与槽位
- schema: `contracts/schemas/selfcare_card.schema.json`
- 槽位: `contracts/slots.yaml` 中对应模块的 `module_tags` 槽位
- 级别: `SELF_CARE`（自护卡片）+ 升级就医卡片

### 内容范围
- 每个模块的自护卡片：relief_measure（缓解办法）、common_reassurance（常见虚惊情形）、warning_signs（需留意的信号）、escalation_criteria（升级就医的条件）。
- **只写非药物措施**，不含药名和剂量。
- 每个模块必须含至少一张 escalation_criteria 卡片（SELF_CARE 级别必须包含）。
- content_attestation: mentions_specific_drug=false, gives_dosage=false, contains_diagnostic_statement=false。

### 完成标准
- `python tools/validate_contracts.py` 无 ERROR。
- 每张卡片 sources 非空。
- 不含药名和剂量（lint 检查通过）。
- 不含诊断式表述（lint 检查通过）。
- 来源已人工抽查。

---

## C4 就医推荐规则

### 输出文件
- `contracts/facilities/` 下的新加坡机构表（逐条对照官方来源核实，标注核实日期）。
- `contracts/weights/weight_presets.yaml`：默认权重、四个预设与安全边界。
- `contracts/questionnaire/questionnaire.yaml`：设置页问卷到权重的映射。
- `docs/content/sg_pathway_rules.md`：新加坡就医路径与费用规则文档（含转介、补贴、身份差异、未成年人就诊要求，均附来源）。

### 需要引用的 schema 与槽位
- schema: `contracts/schemas/facility.schema.json`、`contracts/schemas/weight_presets.schema.json`、`contracts/schemas/questionnaire_mapping.schema.json`
- 槽位: `contracts/slots.yaml` 中 `used_by` 含 `l4_recommend` 的槽位
- 用户档案字段: `residency_status`、`has_chas`、`insurance`、`travel_mode`（来自 `user_profile.schema.json`）

### 内容范围
- 机构表：新加坡真实医疗机构，逐条核实名称、地址、邮编、坐标（新加坡范围内）、类型、妇科能力、是否 walk-in、费用档位、补贴要求、是否接诊未成年人、营业时间、电话、网站、语言。标注 `last_verified`。
- 权重预设：排序特征（travel_time、cost、accessibility 等）、ranking_levels（SEE_DOCTOR_24_48H + BOOK_SOON）、default_weights_by_level、4 个预设（如 nearest、budget_friendly、accessibility_focused、balanced）、bounds_by_level、emergency_ranking。
- 问卷映射：设置页问题（PQ_ 前缀）、选项及 effects（set_base_preset / add_delta / multiply / set_profile_field）、combination 计算流程。
- 就医路径文档：新加坡就医路径（polyclinic → SOC 转介链、A&E 直接就诊、CHAS GP → 补贴、private GP、private gynae）、费用规则（公民/PR/留学生差异、CHAS 补贴、保险）、转介要求、未成年人就诊要求。

### 完成标准
- `python tools/validate_contracts.py` 无 ERROR。
- 每个机构 sources 非空（引用官方来源 URL）。
- 权重总和为 1 ± 0.001，每个权重在 bounds 范围内。
- 问卷 effects 引用的 feature 和 preset_id 存在于 weight_presets。
- 来源已人工抽查。

---

## C5 固定文案与语气规范

### 输出文件
- `docs/content/fixed_copy.md`：急症出口文案、免责声明、同意文案。
- `docs/content/persona_guide.md`："老奶奶"人设语气指南（含面向青少年的表达）。

### 需要引用的 schema 与槽位
- schema: 无（文案内容，但格式参照 `i18n_text` 结构）
- 级别: `EMERGENCY_NOW`（急症出口文案）

### 内容范围
- 急症出口文案：CALL_AMBULANCE 和 GO_URGENT_OG_OR_AE 两种出口的固定引导文本，多语言（en 必填，zh/ms/ta 尽量提供）。
- 免责声明：界面和文档中的免责声明文本，多语言。
- 同意文案：数据使用同意的说明文本，多语言，带版本号（consent_text_version）。
- 人设语气指南：对话风格、用词难度、对青少年的表达规范（更简单、不吓人、不评判、鼓励告知信任成年人）、怀孕相关措辞中性、不收集性生活史。

### 完成标准
- 所有文案 en 必填且非空。
- 不含药名、剂量、诊断式表述。
- 人设语气指南覆盖面向青少年的表达规范。
- 来源已人工抽查（急症出口文案参考新加坡急救指引）。

---

## 工程阶段（内容全部完成后）

### 前提条件
C1–C5 全部完成，`python tools/validate_contracts.py` 无 ERROR。

### 任务清单
1. **校验脚本升级为运行时配置加载**：`config_loader.py` 在启动时加载并校验全部 `contracts/` 文件，生成 `ConfigBundle`（含 versions 字典）。
2. **L1 红旗规则引擎**：`src/engine/l1_redflag.py`，读取 `contracts/rules/`，输入 `SessionState.slots`，输出 `RedFlagResult`。三值逻辑条件求值。
3. **L2 追问控制器**：`src/engine/l2_grading.py`，读取 `contracts/questions/` 和 `contracts/decision_tables/`，输入 `SessionState.slots`，输出 `GradingResult`。追问循环管理。
4. **L3 自护检索**：`src/engine/l3_selfcare.py`，读取 `contracts/selfcare/`，输入 `GradingResult.level` 和 `module`，输出 `SelfCareOutput`。
5. **L4 过滤与排序引擎**：`src/engine/l4_recommend.py`，读取 `contracts/facilities/` 和 `contracts/weights/`，输入 `RecommendationRequest`，输出 `RankedPlaces`。硬过滤 + 加权排序。
6. **OneMap 适配器**：`src/onemap/adapter.py`，调用 OneMap API 做地址搜索和路线计算。含 token 刷新和限流降级。
7. **编排器**：`src/orchestrator.py`，纯函数式流水线：`(SessionState, Config) → (FinalResponse, Events)`。串联 L1→L2→L3/L4→Persona。
8. **人设与输出校验**：`src/persona.py`，调用 LLM 生成"老奶奶"口吻回复，运行 output_validation 5 项检查，不通过则回退固定模板。
9. **前端**：`src/templates/`（对话页、就医推荐结果页含 Leaflet 地图、设置页）。Jinja2 + Alpine.js + Tailwind CSS。
10. **日志写入器**：`src/logger.py`，事件日志脱敏后写入，不含原始文本、精确坐标、FinalResponse.text、问卷答案。
11. **评测集运行器**：`src/eval/run_eval.py`，读取 `docs/content/cases_*.md`，运行流水线，对比期望级别，输出评测报告。
12. **端到端演示脚本**：一条命令启动完整对话流程，模拟用户输入，展示分诊结果和就医推荐。

### 原则重申
- **工程阶段不改内容含义。** 发现内容问题只能提交修改请求给内容负责人。
- 所有引擎模块是纯函数：`(状态, 配置) → 决策`，便于影子模式重跑。
- 红旗规则引擎永远不进入自动优化。
