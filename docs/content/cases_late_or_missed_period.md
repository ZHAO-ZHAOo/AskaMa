# 合成病例 – late_or_missed_period

> status: draft_unreviewed
> version: 0.4.0

---

## Case LM-001：停经90天 + 可能怀孕 → SEE_DOCTOR_24_48H

**输入：** "三个月没来月经了，有可能怀孕，还有点肚子痛"

**追问回答：** days_since_last_period_start=90, usual_cycle_length_days=28, pregnancy_status=possibly_pregnant, periods_stopped_over_12_months=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 可能怀孕需尽快就诊确认（DT_LM_005）。MVP 运行契约暂无"停经+腹痛+可能怀孕→急诊"红旗，异位妊娠急诊指征列为待临床确认建议。

---

## Case LM-002：停经45天 + 可能怀孕 → SEE_DOCTOR_24_48H

**输入：** "大概45天没来月经了，有可能怀孕"

**追问回答：** days_since_last_period_start=45, usual_cycle_length_days=28, pregnancy_status=possibly_pregnant, periods_stopped_over_12_months=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 可能怀孕需尽快确认（DT_LM_005）

---

## Case LM-003：推迟7天 → SELF_CARE

**输入：** "月经推迟了几天，大概35天了"

**追问回答：** days_since_last_period_start=35, usual_cycle_length_days=28, pregnancy_status=not_pregnant, periods_stopped_over_12_months=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SELF_CARE

**依据：** 推迟一周以内（35天及以内）在正常波动范围（DT_LM_004）

---

## Case LM-004：推迟超过60天 → BOOK_SOON

**输入：** "两个多月没来月经了"

**追问回答：** days_since_last_period_start=60, usual_cycle_length_days=28, pregnancy_status=not_pregnant, periods_stopped_over_12_months=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** BOOK_SOON

**依据：** 推迟超过60天建议就医检查（DT_LM_002）

---

## Case LM-005：连续停经12个月 → BOOK_SOON

**输入：** "快一年没来月经了"

**追问回答：** days_since_last_period_start=90, usual_cycle_length_days=28, pregnancy_status=not_pregnant, periods_stopped_over_12_months=true, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** BOOK_SOON

**依据：** 长期停经需就医评估（DT_LM_001）
