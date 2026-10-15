# 技术栈提案

## 背景约束

- 这是**黑客松原型**，时间紧（具体截止日期待项目负责人确认）。
- 没有临床医生审核；医学内容以"权威来源引用"替代，所有内容保持 `draft_unreviewed`。
- 要求**能在本地一条命令启动演示**，同时可以部署成可访问的网页。
- 界面需包含：**对话页**、**就医推荐结果页（含地图）**、**设置页（权重预设与问卷）**。
- 支持英文（默认）、中文、马来语、泰米尔语切换。
- 使用新加坡 **OneMap**（免费，需注册获取 token）做地址搜索与路线。
- **LLM 只用于两件事**：把用户的话抽取成槽位（Intake）、把确定的结论用"老奶奶"口吻说出来（含输出校验）。所有决策由配置驱动的规则完成。
- 所有配置数据在 `contracts/` 下，带版本号，启动时加载并校验。

---

## 1. 候选方案对比

### 方案 A：Python 后端 + HTMX/Alpine 前端（推荐）

| 维度 | 选择 |
|------|------|
| 后端框架 | **FastAPI**（Python 3.10+，异步，自带 OpenAPI 文档） |
| 前端方案 | **Jinja2 模板 + Alpine.js + Tailwind CSS**；地图用 **Leaflet**（免费，不依赖 Google Maps API key） |
| 数据存储 | SQLite（会话状态、事件日志）+ 本地 JSON 文件（用户档案） |
| LLM 调用 | 通过自定义抽象层调用（见第 2 节） |

**优点**：
- FastAPI 启动快、文档自动生成、异步支持好。
- Jinja2 + Alpine.js 无需前端构建工具链，一条命令启动。
- Tailwind CSS 快速出样式，无需写大量 CSS。
- Leaflet 开源免费，支持瓦片图层（OneMap 瓦片可直接接入）。
- SQLite 零配置，文件级存储，本地开发简单。
- Python 生态丰富，jsonschema / pyyaml 已在用。
- 与现有 `tools/validate_contracts.py` 同语言，配置加载器可直接复用。

**缺点**：
- 前端交互复杂度受限（但本项目前端需求简单：对话、地图、设置页，足够）。
- 多语言需要模板层处理（但 Jinja2 支持简单的 i18n 插件或自建过滤器）。

**搭建难度**：低。已有 Python 环境和校验脚本，FastAPI + Jinja2 + Leaflet 可在一个下午搭好。

**适合本项目的程度**：★★★★★

---

### 方案 B：Python 后端 + React/Next.js 前端

| 维度 | 选择 |
|------|------|
| 后端框架 | FastAPI |
| 前端方案 | React（Next.js 或 Vite）+ Tailwind CSS + react-leaflet |
| 数据存储 | SQLite + JSON 文件 |
| LLM 调用 | 同上 |

**优点**：
- React 生态成熟，组件化程度高。
- 前端交互体验更好（SPA、状态管理）。
- 适合后续扩展为更复杂的产品。

**缺点**：
- 需要前端构建工具链（Node.js / npm / Vite），搭建时间长。
- 黑客松时间紧，前端+后端双栈维护负担大。
- 需要处理 CORS、前后端 API 对齐等问题。

**搭建难度**：中高。

**适合本项目的程度**：★★★☆☆（原型阶段过度设计）

---

### 方案 C：全栈 JavaScript（Node.js + React）

| 维度 | 选择 |
|------|------|
| 后端框架 | Express.js 或 Hono |
| 前端方案 | React + Tailwind + react-leaflet |
| 数据存储 | SQLite（better-sqlite3）+ JSON 文件 |
| LLM 调用 | 通过 fetch 调用 LLM API |

**优点**：
- 单语言全栈，前后端共享类型。
- npm 生态丰富。

**缺点**：
- 现有校验脚本和契约文件都是 Python（jsonschema、pyyaml），改用 Node.js 需要重写校验和配置加载。
- 配置加载器需要重新实现。
- jsonschema 在 Node.js 中不如 Python 成熟。

**搭建难度**：高（需重写已有工具链）。

**适合本项目的程度**：★★☆☆☆（不推荐，丢弃已有 Python 投资）

---

### 明确推荐：方案 A

理由：
1. 复用已有的 Python 校验脚本和 YAML 加载逻辑。
2. 无前端构建工具链，`uvicorn main:app` 一条命令启动。
3. Jinja2 + Alpine.js 足以实现对话页、地图页、设置页。
4. Leaflet + OneMap 瓦片图层可满足新加坡地图需求，无需额外付费。
5. 部署简单：FastAPI + uvicorn + 任意云平台（Fly.io / Railway / Vercel）。

---

## 2. LLM 抽象层设计

### 目标

LLM 调用必须做到**供应商无关**，可以随时更换模型而不改动业务代码。

### 接口定义

```python
# contracts/interfaces/ — 通过 JSON Schema 定义 LLM 输入输出

class LLMClient(ABC):
    """供应商无关的 LLM 客户端接口。"""

    @abstractmethod
    async def extract_slots(
        self,
        messages: list[dict],
        output_schema: dict,  # JSON Schema describing the slot structure
        ui_language: str,
    ) -> dict:
        """Intake: 把用户消息抽取成结构化槽位。
        - messages: 对话历史（role + content）
        - output_schema: 描述期望输出的 JSON Schema（槽位结构）
        - 返回：符合 output_schema 的 dict
        - 失败时抛出 LLMExtractionError
        """

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict],
        context: dict,  # 包含 level, module, refs, language 等决策结果
        constraints: dict,  # 输出校验规则（不含药名、不含诊断措辞等）
    ) -> str:
        """Persona: 用"老奶奶"口吻生成回复文本。
        - 返回：纯文本字符串
        - 输出须经 output_validation 校验后才能展示给用户
        """
```

### 供应商选项（留给项目负责人决定）

| 选项 | 优点 | 缺点 | 备注 |
|------|------|------|------|
| OpenAI (GPT-4o / GPT-4o-mini) | 支持结构化输出（Structured Output / JSON mode）、文档完善 | 需要付费 API key、数据出境 | mini 版便宜，适合原型 |
| Anthropic (Claude 3.5 Sonnet) | 表达能力强、"老奶奶"口吻可能更自然 | 结构化输出支持不如 OpenAI 直接 | 需要额外解析逻辑 |
| Google (Gemini 1.5 Flash) | 免费额度较大、多语言能力好 | API 文档不如 OpenAI 完善 | 原型阶段免费额度可能够用 |
| 本地模型 (Ollama / vLLM) | 完全离线、无数据出境、零成本 | 需要 GPU 或较强 CPU、质量可能不如商业模型 | 演示时本地部署可避免网络依赖 |

**取舍**：
- 如果演示环境网络稳定且预算允许 → 推荐 OpenAI（结构化输出最可靠）。
- 如果需要完全离线演示 → 推荐本地模型（Ollama + 小型模型）。
- 如果预算为零但允许联网 → 推荐 Gemini Flash（免费额度大）。
- **最终选择由项目负责人决定**，LLM 抽象层设计保证切换只改配置不改代码。

### 超时与重试

- Intake 抽取：超时 15 秒，最多重试 2 次（指数退避）。
- Persona 生成：超时 20 秒，最多重试 1 次。
- 所有 LLM 调用失败时：Intake 回退为"无法理解，请重新描述"；Persona 回退为固定模板文案。
- 超时和重试参数记录在事件日志的 `error` 事件中。

### 输出校验保证

- Intake 输出必须通过 `IntakeResult` schema 校验（jsonschema），不通过则重试（最多 2 次），仍不通过则回退。
- Persona 输出必须通过 `FinalResponse.output_validation` 的全部 5 项检查，不通过则回退为固定模板文案。
- 校验失败时记录 `output_validation` 事件（passed=false），不展示未通过的内容。

---

## 3. 代码目录结构提案

```
ai-grandma/
├── contracts/                    # 配置数据（已有，内容阶段填充）
│   ├── rules/                    # → L1 红旗规则引擎读取
│   ├── questions/                # → L2 追问控制器读取
│   ├── decision_tables/          # → L2 追问控制器读取
│   ├── selfcare/                 # → L3 自护检索读取
│   ├── facilities/               # → L4 过滤与排序引擎读取
│   ├── weights/                  # → L4 过滤与排序引擎读取
│   ├── questionnaire/            # → 设置页读取
│   ├── schemas/                  # JSON Schema（已有）
│   ├── levels.yaml               # → 配置加载器读取
│   ├── modules.yaml              # → 配置加载器读取
│   └── slots.yaml                # → 配置加载器读取
├── src/
│   ├── config_loader.py          # 启动时加载并校验 contracts/，生成 versions 字典
│   ├── llm/
│   │   ├── client.py             # LLM 抽象层（见第 2 节）
│   │   └── retry.py              # 超时与重试逻辑
│   ├── engine/
│   │   ├── l1_redflag.py         # L1 红旗规则引擎 → 读取 rules/*.yaml
│   │   │                         # 输入: SessionState.slots → 输出: RedFlagResult
│   │   ├── l2_grading.py         # L2 追问控制器 → 读取 questions/*.yaml + decision_tables/*.yaml
│   │   │                         # 输入: SessionState.slots → 输出: GradingResult
│   │   ├── l3_selfcare.py        # L3 自护检索 → 读取 selfcare/*.yaml
│   │   │                         # 输入: GradingResult.level, module → 输出: SelfCareOutput
│   │   └── l4_recommend.py       # L4 过滤与排序引擎 → 读取 facilities/*.yaml + weights/*.yaml
│   │                             # 输入: RecommendationRequest → 输出: RankedPlaces
│   ├── onemap/
│   │   └── adapter.py            # OneMap 适配器（地址搜索、路线计算）
│   ├── orchestrator.py           # 编排器（纯函数式流水线）
│   │                             # 输入: 用户消息 + SessionState + Config → 输出: FinalResponse + 事件列表
│   ├── persona.py                # 人设层 + 输出校验
│   │                             # 输入: 决策结果 + LLM 客户端 → 输出: FinalResponse
│   ├── logger.py                 # 日志写入器（事件日志，脱敏后写入）
│   ├── api/
│   │   ├── app.py                # FastAPI 应用
│   │   ├── routes.py             # API 路由（/chat, /settings, /facilities）
│   │   └── ws.py                 # WebSocket（对话实时推送）
│   └── templates/                # Jinja2 模板
│       ├── chat.html             # 对话页
│       ├── recommendation.html   # 就医推荐结果页（含 Leaflet 地图）
│       └── settings.html         # 设置页（权重预设与问卷）
├── tools/
│   ├── validate_contracts.py     # 校验脚本（已有）
│   └── lint_denylist.yaml        # lint 词表（已有）
├── tests/
│   ├── test_validate_contracts.py # 契约测试（已有）
│   ├── test_l1_redflag.py         # L1 单元测试（工程阶段）
│   ├── test_l2_grading.py         # L2 单元测试（工程阶段）
│   ├── test_l4_recommend.py       # L4 单元测试（工程阶段）
│   ├── test_orchestrator.py       # 端到端流水线测试（工程阶段）
│   └── eval/                      # 评测集运行器（工程阶段）
│       └── run_eval.py            # 读取 docs/content/cases_*.md，运行流水线，对比期望级别
├── docs/
└── requirements.txt
```

### 各模块读取的 contracts 文件与输入输出接口

| 模块 | 读取的 contracts 文件 | 输入接口 | 输出接口 |
|------|----------------------|---------|---------|
| config_loader | 全部 contracts/ | — | `ConfigBundle`（含 versions 字典） |
| l1_redflag | rules/*.yaml | SessionState.slots | RedFlagResult |
| l2_grading | questions/*.yaml, decision_tables/*.yaml | SessionState.slots | GradingResult |
| l3_selfcare | selfcare/*.yaml | GradingResult.level, module | SelfCareOutput |
| l4_recommend | facilities/*.yaml, weights/*.yaml | RecommendationRequest | RankedPlaces |
| onemap/adapter | — (OneMap API) | 地址/坐标 | 距离、路线 |
| orchestrator | — (调用上述模块) | 用户消息 + SessionState | FinalResponse + 事件列表 |
| persona | — (调用 LLM) | 决策结果 + context | FinalResponse |
| logger | — (写入日志) | 事件列表 | 事件日志文件 |

---

## 4. 配置加载与版本戳

### 启动时加载

```python
# config_loader.py 伪代码
def load_config(contracts_dir: Path) -> ConfigBundle:
    """启动时加载并校验全部 contracts/ 文件。"""
    # 1. 运行 validate_contracts.py 的校验逻辑（schema + 语义 + lint）
    # 2. 如有 ERROR，拒绝启动
    # 3. 提取每个文件的 meta.version 和 meta.id，组成 versions 字典
    # 4. 返回 ConfigBundle(configs=..., versions=...)
```

### 版本戳

- `ConfigBundle.versions` 是一个 `dict[str, str]`，键为配置名（`redflag_rules`、`question_tree`、`decision_table`、`selfcare_kb`、`facility_table`、`weight_presets`、`questionnaire`、`prompt`、`model_id`、`contracts_bundle`），值为版本号字符串。
- 每条事件日志记录时，从 `ConfigBundle.versions` 复制当前 versions 到事件的 `versions` 字段。
- `contracts_bundle` 版本是整个契约包的汇总版本号，每次修改任何 contracts 文件时更新。

---

## 5. 隐私与日志的实现要点

### 脱敏位置

- 用户消息进入系统后**立即脱敏**：只保留 `text_redacted`（截断 + 关键词替换）、`char_count`、`input_language`。原始文本只在内存中用于 LLM 抽取，不落盘。
- `ephemeral_coordinates`（lat/lng）只在内存中用于 L4 距离计算，**不写入日志、不持久化**。
- 日志只记录区域级别位置（`planning_area`），不记录精确坐标。

### 日志只存脱敏摘要

- `FinalResponse.text` 不写入日志。日志只存 `output_validation` 结果和 `refs`（question_id / card_ids / facility_ids / rule_ids）。
- 问卷答案不记录到日志。`settings_changed` 事件只记录 mode 和是否裁剪。
- `feedback_given` 的 `comment_redacted` 经过脱敏后存储。

### 同意开关的处理

- `user_profile.consent.followup_contact` = false 时，不发起回访，不记录 `outcome_recorded` 事件。
- `user_profile.consent.visit_history` = false 时，不记录就诊历史。
- `user_profile.consent.research_use` = false 时，日志数据不用于研究分析。
- `user_profile.consent.service` = false 时，拒绝使用系统（必须同意才能使用核心服务）。
- 每次同意状态变更，记录 `consent_changed` 事件。

---

## 6. 测试策略

### 单元测试
- 每个引擎模块（L1/L2/L3/L4）独立单元测试，使用 fixtures 中的配置数据。
- LLM 抽象层使用 mock 客户端测试（不调用真实 LLM）。
- OneMap 适配器使用 mock 响应测试。

### 基于契约的测试
- 已有的 `test_validate_contracts.py` 覆盖所有 schema 和语义检查。
- 每个接口 schema（`SessionState`、`IntakeResult`、`RedFlagResult` 等）都有 valid/invalid 示例，在测试中被校验。

### 评测集运行器（工程阶段实现）
- 读取 `docs/content/cases_<module>.md` 中的合成病例。
- 每个病例包含：模拟对话历史、期望级别。
- 运行流水线（纯函数式：(状态, 配置) → 决策），对比输出级别与期望级别。
- 输出评测报告：通过率、失败案例分析。

### 端到端演示脚本
- 一条命令启动完整对话流程，模拟用户输入，展示分诊结果和就医推荐。
- 可用于黑客松演示。

---

## 7. 本地运行与部署

### 一条命令启动

```bash
# .env 文件中配置必要的环境变量
cp .env.example .env  # 复制模板，填入 LLM API key 和 OneMap token
python src/api/app.py  # 启动 FastAPI，默认 http://localhost:8000
```

### 环境变量与密钥管理

| 变量名 | 用途 | 必需 |
|--------|------|------|
| `LLM_PROVIDER` | LLM 供应商（openai / anthropic / google / local） | 是 |
| `LLM_API_KEY` | LLM API key | 视供应商而定 |
| `LLM_MODEL` | 模型名称 | 是 |
| `ONEMAP_TOKEN` | OneMap API token | 是 |
| `DATABASE_PATH` | SQLite 数据库路径 | 否（默认 `data/app.db`） |
| `UI_DEFAULT_LANGUAGE` | 默认界面语言 | 否（默认 `en`） |

- `.env` 已在 `.gitignore` 中，不会提交到仓库。
- `.env.example` 提供模板（不含真实 key），提交到仓库。

### OneMap token 的获取与刷新

- 在 [OneMap 注册页面](https://portal.onemap.gov.sg/) 注册账号（免费）。
- 获取 API token，填入 `.env` 的 `ONEMAP_TOKEN`。
- OneMap token 有有效期，需要定期刷新。适配器中实现 token 刷新逻辑。
- OneMap API 限流：如遇 429 错误，回退为基于 `planning_area` 的静态距离估算（降级方案）。

### 需要项目负责人提前注册或申请的账号清单

| 账号 | 用途 | 是否免费 | 备注 |
|------|------|---------|------|
| OneMap API | 地址搜索、路线计算、地图瓦片 | 免费 | 需在 portal.onemap.gov.sg 注册 |
| LLM 供应商账号 | Intake 槽位抽取 + Persona 回复生成 | 视供应商而定 | 见第 2 节选项 |
| 部署平台（如 Fly.io / Railway） | 部署网页版 | 有免费额度 | 如果需要在线演示 |

---

## 8. 风险清单

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **LLM 输出不稳定** | Intake 抽取错误槽位、Persona 输出不合规范 | (1) 结构化输出 + JSON Schema 校验 + 重试；(2) output_validation 自动拦截；(3) 不合规范时回退为固定模板文案；(4) 评测集持续监控 |
| **OneMap 限流或不可用** | L4 排序无法计算距离 | (1) 适配器实现降级：回退为 `planning_area` 级别静态距离估算；(2) 缓存常用地址的路线结果；(3) 记录 error 事件 |
| **机构数据过期** | 推荐的机构已关闭或不提供服务 | (1) 机构表每条标注 `last_verified`，超过 180 天给 WARNING；(2) MVP 阶段数据少，人工核实；(3) 正式上线前定期更新 |
| **翻译质量（ms/ta）** | 马来语/泰米尔语翻译不准确 | (1) en 为源文本并作为回退；(2) ms/ta 未经审核时界面提示"英文为准"；(3) 至少急症出口文案必须有经审核的各语言版本（正式上线前） |
| **没有医生审核** | 医学内容可能不准确 | (1) 每条内容引用权威来源；(2) 来源分歧时取更保守；(3) 界面显著标注"原型，未经临床审核"；(4) 评测只衡量与指南的一致性 |
| **未成年人数据保护** | PDPA 合规风险 | (1) MVP 使用匿名本地档案，不设账号体系；(2) 不收集个人信息（姓名、联系方式、精确位置）；(3) 同意开关默认最严格；(4) 具体合规要求待项目负责人确认（Q-014） |
| **LLM 供应商变更** | 模型行为变化影响质量 | (1) LLM 抽象层保证供应商无关；(2) 评测集覆盖回归测试；(3) 配置化切换供应商，不改代码 |
