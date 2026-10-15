# 合成病例 – irregular_or_intermenstrual_bleeding

> status: draft_unreviewed
> version: 0.4.0

---

## Case IB-001：经间出血 + 发热 → EMERGENCY_NOW

**输入：** "两次月经之间出血了，还发烧38度"

**追问回答：** bleeding_between_periods=true, cycle_regularity=somewhat_irregular, unusual_discharge_or_odor=false, current_bleeding_days_so_far=3, dizziness_or_fainting=none, fever_status=measured_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** EMERGENCY_NOW

**期望红旗：** fever_status=measured_fever

**期望出口：** GO_URGENT_OG_OR_AE

**依据：** 发热伴异常出血提示感染（RF_GLOBAL_FEVER）

---

## Case IB-002：经间出血 + 异味分泌物 → SEE_DOCTOR_24_48H

**输入：** "非经期出血了，还有异味"

**追问回答：** bleeding_between_periods=true, cycle_regularity=somewhat_irregular, unusual_discharge_or_odor=true, current_bleeding_days_so_far=3, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 异常分泌物伴经间出血需尽快就医（DT_IB_001）

---

## Case IB-003：偶尔经间点滴 → BOOK_SOON

**输入：** "这次月经不太规律，中间有几天点滴出血"

**追问回答：** bleeding_between_periods=true, cycle_regularity=somewhat_irregular, unusual_discharge_or_odor=false, current_bleeding_days_so_far=1, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** BOOK_SOON

**依据：** 经间出血为保守评估信号（DT_IB_003；MVP 保守策略，是否放宽为居家观察待临床确认）

---

## Case IB-004：出血持续2周 → SEE_DOCTOR_24_48H

**输入：** "这次月经出血持续了两周还没停"

**追问回答：** bleeding_between_periods=false, cycle_regularity=somewhat_irregular, unusual_discharge_or_odor=false, current_bleeding_days_so_far=14, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 出血超过14天需就医（DT_IB_002）

---

## Case IB-005：周期非常不规律 → BOOK_SOON

**输入：** "最近几个月月经很不规律"

**追问回答：** bleeding_between_periods=false, cycle_regularity=very_irregular, unusual_discharge_or_odor=false, current_bleeding_days_so_far=7, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** BOOK_SOON

**依据：** 持续不规律建议近期就医检查（DT_IB_004）
