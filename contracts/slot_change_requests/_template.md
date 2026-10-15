# 槽位变更请求模板

## 基本信息

- 提议日期：YYYY-MM-DD
- 提议者：
- 变更类型：[ ] 新增槽位 [ ] 修改槽位 [ ] 删除槽位
- 提议的槽位 id：（英文 snake_case）

## 完整字段（按 slots.yaml 格式）

```yaml
- id:
  group:
  type:           # enum / int / float / bool / date / duration / text
  allowed_values: # enum 时列出取值；其他类型为 null
  multi:          # enum 是否允许多选
  range:          # 数值型时填写，否则 null
  unit:
  description:
    en:           # 必填，英文为源文本
    zh:
  example_phrases:
    en: ["", ""]  # 必填，英文示例说法
    zh: ["", ""]
  module_tags:    # 用 modules.yaml 中的模块 id，全局通用用 [global]
  used_by:        # l1_redflag / l2_grading / l3_selfcare / l4_recommend / logging
  sensitivity:    # normal / sensitive / high
  derived:
  derivation_note:
  needs_clinician_review:
  review_note:
  status: draft_unreviewed
  added_in_version:
```

## 为什么需要

（说明该槽位解决什么问题、当前字典中为何缺少）

## 哪一层会用

（列出 used_by 的理由）

## 影响评估

（新增/修改此槽位是否影响现有槽位、追问流程或决策逻辑）
