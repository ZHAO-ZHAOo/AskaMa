# 槽位变更请求：menarche_stage

## 基本信息

- 提议日期：2026-10-08
- 提议者：项目负责人
- 变更类型：[x] 新增槽位
- 提议的槽位 id：menarche_stage

## 完整字段（按 slots.yaml 格式）

```yaml
- id: menarche_stage
  group: context
  type: enum
  allowed_values:
    - {id: not_yet_started, label: {en: Not yet started, zh: 尚未开始}}
    - {id: started_recently, label: {en: Started recently, zh: 刚开始不久}}
    - {id: started_a_while_ago, label: {en: Started a while ago, zh: 已经开始一段时间}}
  multi: false
  range: null
  unit: null
  description:
    en: The stage of the user's menarche.
    zh: 用户初潮所处的阶段。
  example_phrases:
    en: ["I haven't had my period yet", "It just started not long ago", "It's been a few years"]
    zh: ["还没来过月经", "刚来没多久", "已经来几年了"]
  module_tags: [late_or_missed_period, severe_period_pain, irregular_or_intermenstrual_bleeding]
  used_by: [l2_grading, l1_redflag]
  sensitivity: sensitive
  derived: false
  derivation_note: null
  needs_clinician_review: true
  review_note: started_recently 与 started_a_while_ago 的分界待医生确认
  status: draft_unreviewed
  added_in_version: pending
```

## 为什么需要

区分初潮前后阶段。青春期用户的周期规律性判断可能与成年人不同（例如初潮后一段时间内周期不规律较为常见），这一信息有助于后续步骤中按年龄段区分的追问逻辑和决策表正确运作。分档边界由临床医生确认，工程师不得自行设定。

## 哪一层会用

- l2_grading：周期规律性、出血量等判断可能因初潮阶段不同而有差异。
- l1_redflag：红旗规则可能需要按初潮阶段预留区分空间（由医生决定）。

## 影响评估

新增槽位，不影响现有槽位。合并后 slots.yaml 槽位总数将从 47 增至 48，需升版本号。used_by 列出的层在后续步骤定义规则时引用此槽位 id。
