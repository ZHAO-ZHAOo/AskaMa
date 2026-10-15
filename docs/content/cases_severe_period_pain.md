# 合成病例 – severe_period_pain

> status: draft_unreviewed
> version: 0.4.0

---

## Case SP-001：突发剧痛 10分 → EMERGENCY_NOW

**输入：** "突然肚子特别痛，10分痛"

**追问回答：** pain_severity_0_10=10, pain_compared_to_usual=new_kind_of_pain, pain_onset_speed=sudden, pain_interferes_with_activities=cannot_do_usual_things, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=not_related_to_period, pain_location=lower_abdomen_middle

**期望级别：** EMERGENCY_NOW

**期望红旗：** pain_severity_0_10 >= 9

**期望出口：** GO_URGENT_OG_OR_AE

**依据：** 疼痛达到10分触发数值红旗（RF_SP_PAIN_10）

---

## Case SP-002：痛经8分 + 新类型痛 → SEE_DOCTOR_24_48H

**输入：** "痛经很厉害大概8分，和以前不一样的感觉"

**追问回答：** pain_severity_0_10=8, pain_compared_to_usual=new_kind_of_pain, pain_onset_speed=gradual, pain_interferes_with_activities=quite_a_lot, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=during_period, pain_location=lower_abdomen_middle

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 重度且新类型疼痛需尽快评估（DT_SP_002）

---

## Case SP-003：痛经3分 + 和平常一样 → SELF_CARE

**输入：** "痛经3分，和平常差不多"

**追问回答：** pain_severity_0_10=3, pain_compared_to_usual=same_as_usual, pain_onset_speed=gradual, pain_interferes_with_activities=not_at_all, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=during_period, pain_location=lower_abdomen_middle

**期望级别：** SELF_CARE

**依据：** 轻中度疼痛与平常相近，适合居家自我照护（DT_SP_004）

---

## Case SP-004：痛经7分 + 影响日常 → SEE_DOCTOR_24_48H

**输入：** "痛经7分，痛得没法正常做事"

**追问回答：** pain_severity_0_10=7, pain_compared_to_usual=worse_than_usual, pain_onset_speed=gradual, pain_interferes_with_activities=cannot_do_usual_things, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=during_period, pain_location=lower_abdomen_middle

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 重度疼痛影响日常活动需尽快就诊（DT_SP_001；DT_SP_005 保底同命中，取最高级）

---

## Case SP-005：痛经5分 + 和平常一样 → SELF_CARE

**输入：** "痛经5分，和平常一样"

**追问回答：** pain_severity_0_10=5, pain_compared_to_usual=same_as_usual, pain_onset_speed=gradual, pain_interferes_with_activities=a_little, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=during_period, pain_location=lower_abdomen_middle

**期望级别：** SELF_CARE

**依据：** 轻中度疼痛与平常相近，适合居家自我照护（DT_SP_004）

---

## Case SP-006：痛经 + 头晕 → EMERGENCY_NOW

**输入：** "痛经很厉害，头晕差点晕倒"

**追问回答：** pain_severity_0_10=8, pain_compared_to_usual=worse_than_usual, pain_onset_speed=gradual, pain_interferes_with_activities=cannot_do_usual_things, dizziness_or_fainting=nearly_fainted, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false, pain_timing_relative_to_period=during_period, pain_location=lower_abdomen_middle

**期望级别：** EMERGENCY_NOW

**期望红旗：** dizziness_or_fainting=nearly_fainted

**期望出口：** GO_URGENT_OG_OR_AE

**依据：** 头晕接近晕厥触发全球红旗（RF_GLOBAL_NEAR_FAINTING）
