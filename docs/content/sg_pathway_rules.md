# 新加坡就医路径与费用规则

> status: draft_unreviewed
> version: 0.3.0
> last_verified: 2026-10-01
> 来源：新加坡卫生部（MOH）、HealthHub、CHAS 官网

本文档记录新加坡就医路径、费用规则、转介要求和未成年人就诊要求，供 L4 推荐引擎参考。

---

## 1. 就医路径

### 1.1 急症路径（EMERGENCY_NOW）

| 出口类型 | 目标机构 | 说明 |
|---------|---------|------|
| CALL_AMBULANCE | SCDF 995 | 拨打救护车 |
| GO_URGENT_OG_OR_AE | KKH Urgent O&G Centre / 公立医院 A&E | 直接前往，无需预约 |

- 急症不涉及费用差异——所有公立 A&E 对所有人开放，费用后付
- 救护车 995 免费调用（SCDF 提供）
- 非紧急救护车 1777 收费

### 1.2 当天就医路径（SEE_DOCTOR_24_48H）

| 路径 | 机构类型 | 说明 |
|------|---------|------|
| A | polyclinic | 综合诊所，walk-in，费用低，但排队长 |
| B | CHAS GP | 参与 CHAS 计划的全科诊所，补贴后费用低 |
| C | private GP | 私人全科诊所，费用较高但等候短 |
| D | urgent_og / A&E | 如果症状较重也可直接去 |

### 1.3 近期预约路径（BOOK_SOON）

| 路径 | 机构类型 | 说明 |
|------|---------|------|
| A | polyclinic → SOC（专科门诊）转介 | 公立专科需 polyclinic 转介才能享补贴 |
| B | CHAS GP → 转介 | CHAS GP 可转介至公立 SOC |
| C | private GP → 转介 | 私人 GP 可转介但不享 CHAS 补贴 |
| D | private_gynae | 直接看私人妇科，无需转介，费用高 |

**关键规则：** 公立 SOC 的补贴**必须通过转介**才能享受。直接去 SOC 不走补贴。

---

## 2. 费用规则

### 2.1 身份差异

| 身份 | polyclinic | CHAS GP | 公立 SOC（有转介） | 公立 A&E | private GP |
|------|-----------|---------|-------------------|---------|-----------|
| Citizen | ~$5-15 | CHAS 补贴后 ~$0-5 | 补贴后 ~$20-40 | ~$120+ | ~$30-60 |
| PR | ~$15-30 | CHAS 补贴后 ~$0-5 | 补贴后 ~$40-80 | ~$120+ | ~$30-60 |
| Student Pass / Other | ~$40-60 | 不享 CHAS | 无补贴 ~$100+ | ~$150+ | ~$30-60 |

> 注：以上为约数，实际费用随时变化，仅供参考。

### 2.2 CHAS 补贴

CHAS（Community Health Assist Scheme）是新加坡的社区医疗补贴计划：

- **CHAS Blue**：补贴最多（低收入家庭）
- **CHAS Orange**：中等补贴
- **CHAS Green**：补贴较少
- 适用条件：公民或 PR，按家庭人均收入审核
- 申请：通过 HealthHub 或 CHAS 官网

### 2.3 fee_tier 映射

| fee_tier | 含义 | 对应机构 |
|----------|------|---------|
| free | 免费 | 无（新加坡医疗基本都收费） |
| low | 低费用 | polyclinic（公民/PR）、CHAS GP（有补贴） |
| moderate | 中等费用 | private GP、polyclinic（非公民） |
| high | 高费用 | private_gynae、A&E |

---

## 3. 转介规则

| 场景 | 是否需要转介 | 说明 |
|------|------------|------|
| 去 polyclinic | 否 | walk-in |
| 去 CHAS GP | 否 | walk-in，但需 CHAS 资格 |
| 去 private GP | 否 | walk-in |
| 去公立 SOC（享补贴） | 是 | 需从 polyclinic / A&E / CHAS GP 转介 |
| 去公立 SOC（不享补贴） | 否 | 可直接约，但全额自费 |
| 去 private_gynae | 否 | 直接预约 |
| 去 A&E | 否 | walk-in |

---

## 4. 未成年人就诊要求

- **新加坡法定成年年龄**：21 岁
- **医疗同意**：18 岁以下通常需要监护人同意，但紧急情况例外
- **polyclinic**：未成年人可就诊，建议监护人陪同
- **GP / CHAS GP**：通常接受未成年人，建议监护人陪同
- **A&E / KKH Urgent O&G**：接诊所有年龄段，紧急情况优先处理

> 注：具体政策以各机构最新公告为准。

---

## 5. 来源

- 新加坡卫生部 MOH：https://www.moh.gov.sg
- HealthHub：https://www.healthhub.sg
- CHAS 官网：https://www.chas.sg
- KKH Urgent O&G Centre：https://www.kkh.com.sg/pts-educational-info/Pages/Urgent-OG-Centre.aspx
- SCDF 急救电话：https://www.scdf.gov.sg
