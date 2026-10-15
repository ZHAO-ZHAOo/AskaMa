# AI Grandma

新加坡女性月经健康分诊助手，只做分级建议，不做诊断。

> **原型，未经临床审核，不是医疗建议。** 本项目为黑客松 MVP，仅用于演示和合成病例。

**当前阶段：内容阶段（C1-C5）+ 工程阶段均已完成。** 包含完整的红旗规则、追问树、决策表、自护卡片、机构数据、权重预设、固定文案、人设指南，以及可运行的 FastAPI Web 应用。

## 快速启动

```bash
pip install -r requirements.txt
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

然后在浏览器打开 `http://localhost:8000`。

## LLM 接入（阿里云千问 / 百炼，新加坡地域）

Intake 层（模块识别 + 槽位抽取）默认使用 LLM 增强，失败自动回退关键词规则；
分诊（L1 红旗 / L2 决策表）始终由确定性引擎完成。未配置 Key 时自动使用 DummyLLM，
demo / CI 可无网络跑通。

复制 `.env.example` 为 `.env` 并填写（**API Key 按地域绑定，必须使用新加坡地域创建的 Key**）：

```bash
DASHSCOPE_API_KEY=sk-...          # 新加坡地域的百炼 API Key（必填）
DASHSCOPE_WORKSPACE_ID=...        # 业务空间 ID（可选；配置后走专属域名，性能更稳）
LLM_MODEL=qwen-plus               # 默认 qwen-plus，可换 qwen-turbo / qwen-max 等
```

新加坡地域 OpenAI 兼容 base_url（代码自动构造）：
`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
未配置 WorkspaceId 时回退 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`。
`/api/health` 会返回当前 LLM 状态（provider / model / intake_enabled）。
详细设计与验证记录见 `docs/07_llm_integration.md`。

## 端到端演示

```bash
python run_demo.py
```

## 评测

```bash
python -m src.eval.run_eval
```

## 校验

```bash
python tools/validate_contracts.py
python -m pytest tests/ -q
```

## 目录结构

```
ai-grandma/
├── contracts/              # 配置数据与 JSON Schema
│   ├── schemas/            # JSON Schema 定义
│   │   ├── common.schema.json
│   │   ├── levels.schema.json
│   │   ├── modules.schema.json
│   │   ├── slots.schema.json
│   │   ├── redflag_rules.schema.json
│   │   ├── question_tree.schema.json
│   │   ├── decision_table.schema.json
│   │   ├── selfcare_card.schema.json
│   │   ├── facility.schema.json
│   │   ├── weight_presets.schema.json
│   │   ├── questionnaire_mapping.schema.json
│   │   ├── user_profile.schema.json
│   │   ├── events.schema.json
│   │   └── interfaces/     # 层间接口 schema
│   ├── rules/              # 红旗规则（内容阶段 C1）
│   ├── questions/          # 追问树（内容阶段 C2）
│   ├── decision_tables/    # 决策表（内容阶段 C2）
│   ├── selfcare/           # 自护卡片（内容阶段 C3）
│   ├── facilities/         # 医疗机构（内容阶段 C4）
│   ├── weights/            # 权重预设（内容阶段 C4）
│   ├── questionnaire/      # 问卷映射（内容阶段 C4）
│   ├── examples/           # 格式演示示例
│   ├── levels.yaml
│   ├── modules.yaml
│   └── slots.yaml
├── docs/                   # 项目文档
├── tools/                  # 校验工具
│   ├── validate_contracts.py
│   └── lint_denylist.yaml
├── tests/                  # 测试
│   ├── test_validate_contracts.py
│   └── fixtures/
└── requirements-dev.txt
```

## 如何运行校验与测试

```bash
# 安装依赖
pip install -r requirements-dev.txt

# 校验所有 contracts 文件（格式 + 语义 + 内容安全）
python tools/validate_contracts.py

# 严格模式（WARNING 也算失败）
python tools/validate_contracts.py --strict

# 运行测试
python -m pytest tests/ -q
```

校验内容包括：
1. **JSON Schema 格式校验**（含 $ref 解析和 format 检查）
2. **基础字典检查**（levels / modules / slots 完整性和一致性）
3. **语义交叉检查**（槽位引用、操作符兼容性、枚举取值、required 槽位覆盖、决策表 default_row、SELF_CARE 必须含 escalation_criteria、机构 id 唯一、权重总和 = 1、问卷引用一致性等）
4. **内容安全扫描**（药名 ERROR、剂量 ERROR、诊断式表述 WARNING）

详见 [docs/02_conventions.md](docs/02_conventions.md)。

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/00_project_context.md](docs/00_project_context.md) | 项目背景、目标用户、语言决策、MVP 范围、安全措施 |
| [docs/01_levels_and_modules.md](docs/01_levels_and_modules.md) | 分诊级别与症状模块定义 |
| [docs/02_conventions.md](docs/02_conventions.md) | 文件结构、命名规范、校验检查项一览 |
| [docs/03_tech_stack_proposal.md](docs/03_tech_stack_proposal.md) | 技术栈提案（方案对比、LLM 抽象层、目录结构、风险清单） |
| [docs/04_data_flow.md](docs/04_data_flow.md) | 数据流说明（层间接口与事件日志） |
| [docs/05_content_phase_plan.md](docs/05_content_phase_plan.md) | 内容阶段计划（C1–C5 任务清单与工程阶段任务） |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 变更记录 |
| [docs/open_questions.md](docs/open_questions.md) | 未解决问题清单 |
