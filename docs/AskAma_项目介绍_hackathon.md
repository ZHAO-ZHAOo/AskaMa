# AskAma（问问阿嫲）· Hackathon Project Introduction / 黑客松项目介绍

> **One-line positioning:** AskAma is an evidence-based menstrual & pelvic health triage assistant for women in Singapore — it never diagnoses; it listens, screens for red flags, and tells you exactly *where and how soon* to seek care.
>
> **一句话定位：** AskAma（问问阿嫲）是面向新加坡女性的循证经期与盆腔健康分诊助手——它不做诊断，只负责倾听、红旗筛查，并告诉用户"该去哪一级医疗、多快必须去"。

---

## 1. Project Overview: Target Scenarios, Users, and Value Proposition

**Target scenarios (when a woman opens AskAma):**
- Heavy, alarming menstrual bleeding (soaking through hourly, large clots)
- Severe period pain, including sudden-onset pain
- Late or missed period, with uncertainty about next steps
- Irregular or intermenstrual bleeding
- Fever, fainting, near-fainting, racing heart, or vomiting accompanying any menstrual/pelvic symptom — signs that may indicate serious conditions (e.g., ectopic pregnancy, ovarian torsion, severe pelvic infection)

**Target users:**
- Women and adolescent girls in Singapore (no minimum age gate; teens are an explicit target persona)
- Users who are unsure whether a symptom warrants A&E, a clinic, or home care
- Multilingual users: English, 简体中文, Bahasa Melayu, தமிழ் (en/zh/ms/ta)

**Value proposition:**
- **For the user:** a non-judgmental "grandmother" who listens without shame, screens for danger signs, and converts health anxiety into a concrete, tiered action plan — self-care guidance, a clinic visit, an urgent O&G assessment, or calling an ambulance.
- **For the system:** right-care, right-place, right-time — diverting low-acuity cases away from crowded A&E while catching high-risk cases early.
- **For the ecosystem:** an AI-for-social-good tool built on traceable clinical guidelines, not on LLM guesswork.

---

## 2. Real World Scenario Insights: Source of Pain Points, Target Audience and Core Problem Solved

**Where the pain points come from:**
- **Health literacy gap:** most women cannot distinguish "normal period discomfort" from red-flag symptoms (e.g., soaking through pads hourly, fainting, sudden severe pain). General online information is either alarmist or contradictory, producing both panic and dangerous delay.
- **Stigma & shame:** menstrual and pelvic complaints carry social taboo; many women endure pain silently rather than seek advice, especially adolescents.
- **Complex local care landscape:** Singapore has no "tier-3 hospital" shortcut. Care paths differ across A&E, 24-hour Urgent O&G Centres (e.g., KKH), polyclinics, CHAS GPs, private gynaecologists, and public specialist outpatient clinics (SOC) — with cost heavily dependent on user identity (citizen/PR/foreigner) and referral path. Choosing wrong = wasted time, money, or a missed emergency.

**Core problem solved:**
> "I don't know if this is serious, where I should go, and I'm too embarrassed to ask."

AskAma answers all three in one conversation: **is this an emergency → what level of care → which type of facility fits me** — while never saying "you have disease X".

---

## 3. Comprehensive Solution Design: Business & Technical Architecture, and How Prompts Drive the AI

### 3.1 Business architecture (user journey)

```
User speaks (en/zh/ms/ta)
   │
   ▼
AskAma triage conversation (multi-turn, empathetic, non-judgmental)
   │
   ▼
Tiered outcome ──► SELF_CARE (home care + escalation criteria)
              ├──► BOOK_SOON (outpatient booking, ~1–2 weeks)
              ├──► SEE_DOCTOR_24_48H (care setting chosen by system)
              └──► EMERGENCY_NOW (CALL_AMBULANCE | GO_URGENT_OG_OR_AE)
   │
   ▼
Facility recommendation (hard-filter by eligibility → weighted ranking by user profile)
   │
   ▼
Post-visit follow-up (optional, anonymous outcome_link_key)
```

### 3.2 Technical architecture (the safety-first pipeline)

The system enforces a hard rule — **decision and expression are separated**: the *level* is always decided by deterministic engines, never by the LLM.

| Layer | Role | Determinism |
|---|---|---|
| **Intake** | LLM extracts structured "slots" (symptom facts) from free-form speech; detects language; falls back to keyword rules on LLM failure | LLM-assisted, rule fallback |
| **L1 Red-Flag Engine** | Evaluates **every turn** against a versioned red-flag rule base (e.g., RF_GLOBAL_FEVER, RF_GLOBAL_FAINING, RF_HB_SOAK_HOURLY, RF_SP_SUDDEN_PAIN) → immediate emergency exit | 100% deterministic |
| **L2 Grading** | Drives multi-turn follow-up via question tree + decision table → assigns one of 4 levels; **uncertainty escalates one level up** | 100% deterministic |
| **L3 Self-care / L4 Recommendation** | Self-care cards (with escalation criteria) or facility ranking: hard filter (eligibility) → weighted scoring (user profile from settings quiz) | 100% deterministic |
| **Persona Layer** | LLM renders the decision in a warm "grandmother" voice + automated output validation | LLM expression only |

**Knowledge layer:** all medical content lives in versioned YAML contracts — red-flag rules, question trees, decision tables, self-care cards, facility data — validated by JSON Schema + semantic cross-checks, each citing public authoritative sources (NICE Clinical Knowledge Summaries – Menorrhagia/Dysmenorrhoea; KKH Urgent O&G Centre). Red-flag rules can only be changed by clinicians, never auto-optimized.

**Privacy-by-design:** raw user text is redacted before logging; location is region-level only; sessions use anonymous IDs; no name/contact/DOB is stored; age band collected in-session only.

### 3.3 How prompts drive the AI generation

Three prompt contracts, each tightly scoped:

1. **Intake prompt** — "You are a clinical information extractor, not a doctor. Extract the following slots into JSON: {slot schema}. Do NOT assess severity. Do NOT infer a level. If a slot is unknown, return needs_clarification." → LLM produces only structured facts; it cannot influence triage.

2. **Persona (expression) prompt** — "You are Ama, a warm, experienced grandmother. Explain the given triage decision to a woman in simple, kind, non-judgmental words. Never diagnose. Never mention drug names or dosages. If the user is young, keep it simple and non-scary. Always keep the mandatory disclaimer. Reply in the user's language (en/zh/ms/ta)." → LLM owns tone, never content.

3. **Output validation (rule layer, not prompt)** — every FinalResponse is machine-checked for: no diagnostic wording, level consistent with L2 conclusion, no drug/dosage, disclaimer present, language matches UI. Violations are blocked.

The result: the LLM contributes **understanding + warmth**, while **safety and correctness come from deterministic, source-cited rules** — an architecture that directly answers the "how do you prevent hallucination in healthcare AI" question judges ask.

---

## 4. Business Value: Quantifiable Metrics or Clearly Defined Impact

### 4.1 Built-in, verifiable product metrics (already true in the MVP)
- **100% deterministic decision layer** — triage level is never LLM-inferred; every decision is reproducible from versioned config
- **0 diagnostic claims** — enforced by automated output validation on every response
- **10+ red-flag rules** covering fever, fainting, near-fainting, tachycardia/SOB, vomiting, hourly soak-through, bleeding through clothes, large clots, pain ≥9/10, sudden severe pain — each traceable to NICE CKS / KKH sources
- **4 triage levels + 2 emergency exits** (CALL_AMBULANCE / GO_URGENT_OG_OR_AE) mapped to Singapore's real care network (A&E, Urgent O&G Centre, polyclinic, CHAS GP, private gynae, SOC)
- **4 official languages** (en/zh/ms/ta) with English as source text
- **Full audit trail** — session events, slot states, level trajectories, and near-miss red flags logged anonymously for later clinical review

### 4.2 Target impact metrics (goals to measure in pilot)
| Metric | Target | Rationale |
|---|---|---|
| Red-flag detection latency | 1st conversational turn | Global red flags are evaluated every turn; high-risk users get an emergency exit immediately |
| Reduction in avoidable A&E visits for low-acuity menstrual complaints | ≥20–30% of diverted users | Public hospital A&E in SG is crowded & costly; self-care + clinic routing absorbs low-acuity demand |
| Time-to-appropriate-care for high-risk users | Minutes (vs. days of self-doubt) | Immediate EMERGENCY_NOW exit with facility + ambulance guidance |
| User trust & stigma reduction | ≥4.5/5 satisfaction; % of users who "would have delayed seeking help without AskAma" | Core pain point is shame-driven delay |
| Multilingual accessibility | 100% of core emergency-exit copy reviewed in all 4 languages | Equal access for SG's multilingual population |

### 4.3 Clearly defined impact
- **Social:** lowers the threshold for women and adolescent girls to engage with their menstrual/pelvic health; destigmatizes a taboo topic; fills a public-health education gap in SG.
- **System:** reduces unnecessary emergency-department load and out-of-pocket cost from wrong care-path choices (cost depends on user identity & referral path — AskAma surfaces the *cheapest eligible* correct path).
- **Platform potential:** API embeddable into polyclinic/KKH portals, insurer wellness programs, and employer health benefits; the audit-log design makes clinician-reviewed iterations and regulatory alignment (e.g., PDPA) feasible.

---

## 中文对照版

**一句话定位：** AskAma（问问阿嫲）是面向新加坡女性的循证经期与盆腔健康分诊助手——它不做诊断，只负责倾听、红旗筛查，并告诉用户"该去哪一级医疗、多快必须去"。

### 1. 项目概览：目标场景、用户与价值主张
- **目标场景：** 经量过多（每小时浸透、大血块）、严重痛经（含突发剧痛）、月经推迟/未来潮、不规则/经间期出血，以及伴随发热、晕倒、近晕厥、心悸气促、呕吐等红旗症状（可能提示异位妊娠、卵巢扭转、严重盆腔感染等急症）。
- **目标用户：** 新加坡女性与青春期少女（不设最低年龄门槛）；不确定是否需要就医的用户；多语言用户（英/简中/马来语/泰米尔语）。
- **价值主张：** 对用户——一位不评判、愿意倾听的"阿嫲"，筛查危险信号，把健康焦虑转化为具体分级行动；对系统——对的人在对的地方在对的时间获得照护，分流低危用户、早抓高危用户；对生态——基于可溯源临床指南的 AI 向善工具。

### 2. 现实场景洞察：痛点来源、目标人群与解决的核心问题
- **健康素养缺口：** 多数女性无法区分正常经期不适与红旗症状；线上信息非恐即乱，既造成恐慌也造成延误。
- **病耻感：** 月经与盆腔话题自带社会禁忌，尤其是青少年，常选择隐忍拖延。
- **本地医疗体系复杂：** A&E、24小时妇科急症中心（如 KKH）、综合诊所、CHAS 全科、私立妇科、公立专科门诊（SOC）路径各异，费用取决于身份（公民/PR/外籍）与转诊路径；选错=浪费钱和时间，或错过急症。
- **核心问题：** "我不知道严不严重、该去哪、又不好意思问"——AskAma 用一次对话解决三者：是否急症→哪级照护→哪类机构，且从不说"你得了某种病"。

### 3. 方案设计：业务与技术架构、Prompt 如何驱动 AI
- **业务架构：** 用户多语言对话 → 多轮分诊 → 四级结论（SELF_CARE 居家自护+升级条件 / BOOK_SOON 近期门诊 / SEE_DOCTOR_24_48H 系统指定去处 / EMERGENCY_NOW 立即就医：呼叫救护车或妇科急症/A&E）→ 机构推荐（硬过滤→按用户档案加权排序）→ 可选匿名回访。
- **技术架构（安全优先管线，硬规则：决策与表达分离）：**
  - Intake：LLM 从口语抽取结构化槽位、检测语言；失败回退关键词规则；不做风险判断
  - L1 红旗层：每一轮确定性评估全部红旗规则（RF_GLOBAL_FEVER、RF_GLOBAL_FAINING、RF_HB_SOAK_HOURLY、RF_SP_SUDDEN_PAIN 等 10+ 条），命中即急诊出口
  - L2 分级层：追问树 + 决策表定级；信息不确定时向上升一级
  - L3/L4：自护卡片（必附升级就医条件）或机构加权推荐，全确定性
  - 人设层：LLM 以"阿嫲"口吻组织回复 + 自动化输出校验（无诊断措辞/级别一致/无药名剂量/必含免责声明/语言匹配）
  - 知识层：带版本 YAML 合约（红旗/追问/决策/自护/机构），JSON Schema+语义校验，每条引用公开权威来源（NICE CKS、KKH）；红旗规则仅医生可改
  - 隐私：原始文本脱敏、仅区域级位置、匿名会话、不存身份信息
- **Prompt 驱动：** 三份严格职责的 prompt——抽取 prompt 只产出结构化槽位（禁止评估严重度/推断级别）；人设 prompt 只管语气与边界（禁止诊断、禁止药名剂量、青少年更简单不吓人、必含免责声明、按用户语言回复）；输出校验是规则层而非 prompt，机器检查每一条回复。LLM 贡献"理解+温度"，安全与正确性来自确定性、可溯源的规则——从架构上回答评委最关心的"医疗 AI 如何防幻觉"。

### 4. 商业价值：可量化指标与明确影响
- **内建可验证指标（MVP 已成立）：** 100% 确定性决策层；0 诊断式表述（自动校验）；10+ 条可溯源红旗规则；4 级 + 2 个急救出口映射新加坡真实医疗网络；4 种官方语言；全审计轨迹（会话事件/槽位状态/级别轨迹/险情规则匿名留档）。
- **试点目标指标：** 红旗首轮检出；低危用户不必要急诊分流 ≥20–30%；高危到诊时间由"数天自我怀疑"缩至"分钟级"；满意度 ≥4.5/5，并度量"没有 AskAma 会延迟就医"的用户占比；4 语言急症出口文案 100% 审核。
- **明确影响：** 社会——降低女性与少女接触自身经期/盆腔健康的门槛、消解禁忌、填补新加坡公共卫生科普缺口；系统——减轻急诊负荷与选错路径的额外花费（AskAma 给出资格内最便宜的合规路径）；平台——可嵌入综合诊所/KKH 门户、保险健康计划、企业健康福利，审计日志设计使临床审核迭代与 PDPA 合规演进可行。

---

*Generated for Tencent Hackathon submission. Prototype — not clinically reviewed, not medical advice.*
