# 固定文案

> status: draft_unreviewed
> version: 0.3.0
> last_verified: 2026-10-01
> 来源：新加坡卫生部、HealthHub、KKH 公开指引

本文档定义所有固定文案（急症出口、免责声明、同意文案），供 persona 层和前端界面引用。所有文案 en 必填，zh 尽量提供，ms/ta 后续补充。

---

## 1. 急症出口文案

### 1.1 CALL_AMBULANCE（拨打急救）

**en:**
> Dear, based on what you've told me, this sounds like an emergency. Please call for an ambulance right away — don't wait. The emergency hotline in Singapore is **995** for ambulance. If it's not life-threatening but you still need urgent transport, call **1777** for non-emergency ambulance. Stay safe and stay on the line.

**zh:**
> 亲爱的，根据你描述的情况，这看起来是急症。请马上拨打急救电话，不要等。新加坡急救电话是 **995**（救护车）。如果不是危及生命但仍然需要紧急送医，可以拨打 **1777**（非紧急救护车）。注意安全，保持电话畅通。

**ms:**
> (待翻译审核)

**ta:**
> (待翻译审核)

### 1.2 GO_URGENT_OG_OR_AE（前往 24 小时妇科急症或 A&E）

**en:**
> Dear, from what you've shared, this needs urgent attention. Please go to the nearest 24-hour women's emergency centre or hospital emergency department right away. In Singapore, **KK Hospital (KKH)** has a 24-hour Urgent O&G Centre, and all public hospitals have 24-hour A&E departments. Don't drive yourself if you feel faint — ask someone to take you or call 995 for an ambulance.

**zh:**
> 亲爱的，根据你说的情况，这需要紧急处理。请马上前往最近的 24 小时妇科急症中心或医院急诊。新加坡 **KK 医院（KKH）** 设有 24 小时妇产科急症中心（Urgent O&G Centre），所有公立医院都有 24 小时急诊。如果你觉得头晕，不要自己开车——请别人送你去，或者打 995 叫救护车。

**ms:**
> (待翻译审核)

**ta:**
> (待翻译审核)

### 1.3 急症出口后的附加信息（机构列表前缀）

**en:**
> Here are the nearest 24-hour emergency facilities I can find for you:

**zh:**
> 这是我能找到的最近的 24 小时急症机构：

---

## 2. 免责声明

### 2.1 界面免责声明（页面顶部 + 对话末尾）

**en:**
> ⚠️ This is a prototype for a hackathon, not clinically reviewed, and is not medical advice. When in doubt, always seek care from a qualified healthcare professional.

**zh:**
> ⚠️ 这是黑客松原型，未经临床审核，不是医疗建议。如有疑虑，请咨询合格的医疗专业人员。

**ms:**
> ⚠️ Ini adalah prototaip, belum dikaji semula secara klinikal, dan bukan nasihat perubatan. Jika ragu-ragu, sentiasa dapatkan rawatan daripada profesional penjagaan kesihatan.

**ta:**
> ⚠️ இது ஒரு முன்மாதிரி, மருத்துவ ரீதியாக மதிப்பாய்வு செய்யப்படவில்லை, மருத்துவ ஆலோசனை அல்ல. சந்தேகம் இருந்தால், எப்போதும் தகுதியான சுகாதார நிபுணரை அணுகவும்.

### 2.2 文档免责声明（README / docs）

**en:**
> AI Grandma is a hackathon prototype and is NOT a medical device, NOT a diagnostic tool, and NOT a substitute for professional medical advice, diagnosis, or treatment. All medical content is marked as draft_unreviewed and must be reviewed by a qualified clinician before any real-world use. Always seek the advice of a qualified healthcare provider with any questions about a medical condition.

**zh:**
> AI Grandma 是黑客松原型，不是医疗器械，不是诊断工具，不能替代专业医疗建议、诊断或治疗。所有医学内容标注为 draft_unreviewed，在任何实际使用前必须由合格的临床医生审核。如有任何健康问题，请咨询合格的医疗专业人员。

---

## 3. 同意文案

### 3.1 数据使用同意（首次使用时展示）

**consent_text_version:** "0.3.0"

**en:**
> **Before we begin, I want to be clear about how your information is used:**
>
> - I only collect what's needed to help figure out how urgent your situation is — things like your symptoms, cycle details, and general area.
> - I don't ask for your name, phone number, or any way to identify you. Each conversation uses a random, anonymous session ID.
> - Your original messages are not stored. Only the structured information I extract (like "pain level: 7") is kept for the duration of the conversation.
> - Your location is only recorded at the region level (e.g., "Bukit Merah"), never your exact address or coordinates.
> - I do not share your data with anyone.
>
> Do you agree to proceed?

**zh:**
> **在开始之前，我想说明一下你的信息如何被使用：**
>
> - 我只收集帮助判断你情况紧急程度所需的信息——比如症状、周期详情和大概区域。
> - 我不会问你的姓名、电话或任何可以识别你的信息。每次对话使用随机的匿名 session ID。
> - 你的原始消息不会被存储。我只保留对话期间抽取的结构化信息（比如"疼痛等级：7"）。
> - 你的位置只记录到区域级别（如"红山"），不会记录精确地址或坐标。
> - 我不会与任何人分享你的数据。
>
> 你同意继续吗？

### 3.2 就诊记录同意（设置页，可选）

**en:**
> May I keep a note of which clinics you've visited through me? This helps me recommend places you're familiar with. You can turn this off anytime, and I'll forget those records.

**zh:**
> 我可以记录你通过我去过哪些诊所吗？这有助于我推荐你熟悉的机构。你可以随时关闭，我会删除这些记录。

---

## 4. 界面固定文案

### 4.1 欢迎语

**en:**
> Hello dear, I'm AI Grandma. Tell me what's bothering you about your period — how you're feeling, what's different, and I'll help you figure out what to do. Don't worry, I'm here to help.

**zh:**
> 亲爱的你好，我是 AI Grandma。跟我说说月经方面有什么不舒服——你的感受、有什么变化，我来帮你看该怎么办。别担心，我在这里帮你。

### 4.2 设置页标题

**en:**
> "Your preferences — so I can suggest the right places for you"

**zh:**
> "你的偏好——这样我才能推荐最合适的机构给你"

### 4.3 语言切换提示

**en:**
> "Language"

**zh:**
> "语言"

---

## 5. 来源

- 新加坡急救电话 995：新加坡民防部队（SCDF）官网 https://www.scdf.gov.sg/
- 非紧急救护车 1777：SCDF 官网
- KKH Urgent O&G Centre：https://www.kkh.com.sg/pts-educational-info/Pages/Urgent-OG-Centre.aspx
- HealthHub（新加坡卫生部健康资讯）：https://www.healthhub.sg
- PDPA（个人数据保护法）：新加坡个人数据保护委员会 https://www.pdpc.gov.sg
