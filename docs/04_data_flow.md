# 数据流说明

本文档说明一次对话中数据如何在各层之间流动，每一步的输入和输出接口名称、会写入哪些事件，以及"决策与表达分离"体现在哪里。

## 1. 对话流程（文字流程图）

```
用户消息
  │
  ├─ 事件: user_message_received (脱敏后存储)
  │
  ▼
Intake（LLM 槽位抽取）
  │ 输入: 原始用户消息
  │ 输出: IntakeResult (extracted_slots, needs_clarification, detected_language, out_of_scope)
  │ 更新: SessionState.slots, detected_input_languages, stage="intake"
  ├─ 事件: intake_extracted
  │
  ▼
L1 红旗层（每一轮评估所有红旗规则）
  │ 输入: SessionState.slots
  │ 输出: RedFlagResult (triggered, triggered_rules, exit_type, near_misses)
  │ 更新: SessionState.stage="l1"
  ├─ 事件: l1_evaluated
  │
  ├─ 命中红旗 → 直接走"立即就医"出口
  │   输出: FinalResponse (response_type=emergency_exit, level=EMERGENCY_NOW)
  │   事件: output_validation
  │   → 结束
  │
  ▼
L2 分级层（追问 + 决策表）
  │ 输入: SessionState.slots, active_modules, 配置版本
  │ 输出: GradingResult (status, level, next_question_id, level_trajectory, stop_reason)
  │ 更新: SessionState.asked_question_ids, candidate_levels, stage="l2"
  │
  │  循环 (status=in_progress):
  │    事件: l2_question_asked
  │    → 用户回答
  │    事件: l2_question_answered
  │    → 重新评估
  │
  │  status=final 时:
  ├─ 事件: l2_decision
  │
  ├─ level=SELF_CARE → L3.1 自护层
  │   输入: GradingResult.level, GradingResult.module
  │   输出: SelfCareOutput (card_ids, includes_escalation_criteria, fallback_used)
  │   事件: l3_selfcare_rendered
  │   → 人设层组装回复 (response_type=selfcare)
  │
  └─ level=需就医 → L4 就医推荐层
      输入: RecommendationRequest (level, module, weights, profile_fields, location, age_band)
      │   硬过滤 → 排除不符合条件的机构
      │   事件: l4_candidates_filtered
      │   加权排序 → 按特征得分排序
      │   事件: l4_ranked (含 feature_scores 明细)
      │   若用户偏好被裁剪到安全边界:
      │   事件: preference_clipped
      输出: RankedPlaces (ranked[], excluded[], weights_used, preferences_clipped)
      → 人设层组装回复 (response_type=recommendation)

人设层（最终回复 + 输出校验）
  │ 输入: 上游结果 + 配置版本
  │ 输出: FinalResponse (text, response_type, level, output_validation, refs)
  │ 校验: no_diagnostic_wording, level_consistent_with_grading,
  │        no_drug_or_dosage, disclaimer_present, language_matches
  ├─ 事件: output_validation
  │
  ▼
用户看到回复
  │ 可能的操作:
  ├─ 事件: l4_user_action (view_map, click_navigate, etc.)
  ├─ 事件: feedback_given
  ├─ 事件: language_switched
  └─ 事件: session_end (reason, last_stage, final_level)

后续回访（仅当用户同意 followup_contact）:
  事件: outcome_recorded (went_to_care, facility_type, symptom_change)
```

## 2. 决策与表达分离

- **决策**（确定级别）：由 L1 红旗规则、L2 追问树和决策表完成。规则是确定性的，带版本号的配置数据，不涉及 LLM 自主判断。
- **表达**（生成回复文本）：由人设层（Persona）完成。LLM 用"老奶奶"的口吻把决策结果变成用户可读的文字，但不能自行改变级别。
- **Intake 的 LLM 只负责抽取槽位和检测语言**，不参与分级判断。
- **FinalResponse.output_validation** 自动检查：回复中不含诊断式措辞、级别与 L2 结论一致、不含药名/剂量、包含免责声明、语言与 UI 一致。

## 3. 绝不能出现在事件日志中的数据

以下数据**严禁**写入事件日志：

| 数据类型 | 原因 |
|---------|------|
| 原始用户文本 | 高度敏感的月经健康信息；只存脱敏后的 `text_redacted` |
| `FinalResponse.text` | 这是展示给用户的最终文字，可能含医学指引；日志只存 `output_validation` 结果和 `refs` |
| 精确坐标（lat/lng） | 位置隐私；`ephemeral_coordinates` 只在内存中用于计算，不落盘 |
| 姓名、联系方式 | 身份信息；`session_id` 和 `outcome_link_key` 均为随机生成，不派生自个人信息 |
| 问卷具体答案 | 偏好选择可能泄露健康状态；`settings_changed` 只记录 mode 和是否裁剪 |
| 出生日期、年龄 | 用户档案不存储；`age_band` 只在会话中通过槽位收集 |

**允许记录的位置信息**：仅区域级别（planning_area），不包含精确地址或坐标。
**所有时间戳**：使用 UTC。
