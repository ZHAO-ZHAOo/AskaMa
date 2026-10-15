# Examples

本目录存放用于格式演示的示例配置文件（YAML）。

## 重要声明

- 所有示例文件**只用于格式演示**，不含任何临床内容，严禁复制到正式规则里。
- 示例中不包含任何数值阈值、药名、诊断名、真实电话号码或真实机构名。
- 自护卡片示例的 title 和 body 明确标注 "[Format example only – not clinical content]"，不含任何真实自护建议、药名或数值。
- 医疗机构示例使用虚构的占位符名称、地址、电话和坐标，不含真实机构数据。
- 每个示例文件都在文件头部或内容中标注了"仅格式示例"声明。

## 文件列表

| 文件 | 说明 |
| --- | --- |
| `redflag_rules.valid.yaml` | 红旗规则格式演示，合法。 |
| `redflag_rules.invalid.yaml` | 红旗规则格式演示，故意不合法（缺少 followup_slots）。 |
| `redflag_rules.invalid_missing_en.yaml` | 红旗规则格式演示，故意不合法（用户可见文本缺少 en）。 |
| `question_tree.valid.yaml` | 追问树格式演示，合法。 |
| `question_tree.invalid.yaml` | 追问树格式演示，故意不合法（question_id 格式错误、缺少 required_slots）。 |
| `decision_table.valid.yaml` | 决策表格式演示，合法。 |
| `decision_table.invalid.yaml` | 决策表格式演示，故意不合法（level 写成不存在的值）。 |
| `selfcare_card.valid.yaml` | 自护卡片格式演示，合法（2 张卡片，仅格式示例，不含临床内容）。 |
| `selfcare_card.invalid.yaml` | 自护卡片格式演示，故意不合法（content_attestation.contains_diagnostic_statement 设为 true）。 |
| `selfcare_card.invalid_emergency_level.yaml` | 自护卡片格式演示，故意不合法（applicable_levels 包含 EMERGENCY_NOW）。 |
| `facility.valid.yaml` | 医疗机构格式演示，合法（2 个机构，使用虚构占位符，不含真实数据）。 |
| `facility.invalid.yaml` | 医疗机构格式演示，故意不合法（lat 超出新加坡纬度范围）。 |
| `user_profile.valid.yaml` | 用户档案格式演示，合法（仅格式示例，不含真实用户数据）。 |
| `user_profile.invalid.yaml` | 用户档案格式演示，故意不合法（weight_profile.mode 为 preset 但缺少 preset_id）。 |
| `user_profile.invalid_extra_field.yaml` | 用户档案格式演示，故意不合法（含不允许的 date_of_birth 字段）。 |
| `weight_presets.valid.yaml` | 权重预设格式演示，合法（2 个特征、1 个预设，数值仅为格式演示）。 |
| `weight_presets.invalid.yaml` | 权重预设格式演示，故意不合法（ranking_levels 包含不允许的 EMERGENCY_NOW）。 |
| `questionnaire_mapping.valid.yaml` | 问卷映射格式演示，合法（2 个问题，仅格式示例）。 |
| `questionnaire_mapping.invalid.yaml` | 问卷映射格式演示，故意不合法（某个 effect 缺少 type 字段）。 |
| `session_state.valid.yaml` | 会话状态格式演示，合法（仅格式示例，不含真实用户数据）。 |
| `session_state.invalid.yaml` | 会话状态格式演示，故意不合法（含不允许的 raw_text 字段）。 |
| `intake_result.valid.yaml` | Intake 结果格式演示，合法。 |
| `intake_result.invalid.yaml` | Intake 结果格式演示，故意不合法（needs_clarification.needed=true 但缺少 reason）。 |
| `redflag_result.valid.yaml` | L1 红旗结果格式演示，合法。 |
| `redflag_result.invalid.yaml` | L1 红旗结果格式演示，故意不合法（triggered=true 但 exit_type=null）。 |
| `grading_result.valid.yaml` | L2 分级结果格式演示，合法。 |
| `grading_result.invalid.yaml` | L2 分级结果格式演示，故意不合法（status=final 但 level=null）。 |
| `selfcare_output.valid.yaml` | L3.1 自护输出格式演示，合法。 |
| `selfcare_output.invalid.yaml` | L3.1 自护输出格式演示，故意不合法（level=SELF_CARE 但 includes_escalation_criteria=false）。 |
| `recommendation_request.valid.yaml` | L4 推荐请求格式演示，合法（坐标仅为格式示例，不真实）。 |
| `recommendation_request.invalid.yaml` | L4 推荐请求格式演示，故意不合法（含不允许的 home_address 字段）。 |
| `ranked_places.valid.yaml` | L4 排序结果格式演示，合法（机构为虚构占位符）。 |
| `ranked_places.invalid.yaml` | L4 排序结果格式演示，故意不合法（ranked 条目缺少 feature_scores）。 |
| `final_response.valid.yaml` | 最终回复格式演示，合法（text 仅为格式示例）。 |
| `final_response.invalid.yaml` | 最终回复格式演示，故意不合法（response_type=emergency_exit 但 level=SELF_CARE）。 |
| `events_user_message_received.valid.yaml` | 事件日志格式演示，合法（user_message_received 类型）。 |
| `events_l1_evaluated.valid.yaml` | 事件日志格式演示，合法（l1_evaluated 类型）。 |
| `events_l2_decision.valid.yaml` | 事件日志格式演示，合法（l2_decision 类型）。 |
| `events_l4_ranked.valid.yaml` | 事件日志格式演示，合法（l4_ranked 类型）。 |
| `events_outcome_recorded.valid.yaml` | 事件日志格式演示，合法（outcome_recorded 类型）。 |
| `events.invalid_unknown_type.yaml` | 事件日志格式演示，故意不合法（未知的 event_type）。 |
| `events.invalid_raw_text.yaml` | 事件日志格式演示，故意不合法（payload 含禁止的 raw_text 字段）。 |
| `events.invalid_coordinates.yaml` | 事件日志格式演示，故意不合法（payload 含禁止的精确坐标 lat/lng）。 |
