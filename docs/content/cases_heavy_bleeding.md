# 合成病例 – heavy_bleeding

> status: draft_unreviewed
> version: 0.4.0
> 用途：评测集，运行 `python -m src.eval.run_eval` 时加载

---

## Case HB-001：经量过多 + 浸透衣物 + 晕厥 → EMERGENCY_NOW

**输入：** "这个月经量特别大，一小时就浸透了卫生巾，裤子都弄脏了，还差点晕倒"

**追问回答：** flow_compared_to_usual=much_more, soak_through_interval=hourly_or_more_often, clots_present=false, bleeding_through_clothes_or_bedding=true, dizziness_or_fainting=nearly_fainted, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** EMERGENCY_NOW

**期望红旗：** bleeding_through_clothes_or_bedding=true, dizziness_or_fainting=nearly_fainted

**期望出口：** GO_URGENT_OG_OR_AE

**依据：** 大量出血伴晕厥为红旗症状（NICE CKS Menorrhagia）

---

## Case HB-002：经量多 + 发烧 → EMERGENCY_NOW

**输入：** "这次出血量很大，还有点发烧，量了一下38.5度"

**追问回答：** flow_compared_to_usual=much_more, soak_through_interval=every_2_to_3_hours, clots_present=false, bleeding_through_clothes_or_bedding=false, dizziness_or_fainting=none, fever_status=measured_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** EMERGENCY_NOW

**期望红旗：** fever_status=measured_fever (≥38°C)

**期望出口：** GO_URGENT_OG_OR_AE

**依据：** 发热伴盆腔出血提示感染可能（NICE CKS）

---

## Case HB-003：经量比平时多但稳定 → SEE_DOCTOR_24_48H

**输入：** "这次经量比平时多很多，大概2小时换一次卫生巾"

**追问回答：** flow_compared_to_usual=much_more, soak_through_interval=every_2_to_3_hours, clots_present=false, bleeding_through_clothes_or_bedding=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 出血量大但无红旗症状，建议 24-48h 就医（DT_HB_001）

---

## Case HB-004：经量稍多 → SELF_CARE

**输入：** "这个月好像量多了一点"

**追问回答：** flow_compared_to_usual=a_bit_more, soak_through_interval=a_few_times_a_day, clots_present=false, bleeding_through_clothes_or_bedding=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SELF_CARE

**依据：** 轻度增多无红旗，可居家观察（DT_HB_003）

---

## Case HB-005：经期中等血块 → BOOK_SOON

**输入：** "这次月经有血块"

**追问回答：** flow_compared_to_usual=much_more, soak_through_interval=a_few_times_a_day, clots_present=true, clot_size=medium, bleeding_through_clothes_or_bedding=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** BOOK_SOON

**依据：** 小/中等血块伴经量多建议近期预约（DT_HB_005；大血块才触发急诊红旗 RF_HB_LARGE_CLOTS）

---

## Case HB-006：不确定是否浸透 → SEE_DOCTOR_24_48H

**输入：** "量很多，我不确定有没有浸透"

**追问回答：** flow_compared_to_usual=much_more, soak_through_interval=not_sure, clots_present=false, bleeding_through_clothes_or_bedding=false, dizziness_or_fainting=none, fever_status=no_fever, heart_racing_or_short_of_breath=false, vomiting_or_cannot_keep_fluids_down=false

**期望级别：** SEE_DOCTOR_24_48H

**依据：** 浸透程度不确定时按不确定升级一级（uncertainty escalate：BOOK_SOON → SEE_DOCTOR_24_48H）
