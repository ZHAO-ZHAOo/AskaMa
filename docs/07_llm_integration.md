# 07 · LLM 接入文档（阿里云千问 / 百炼 · 新加坡地域）

> 状态：已接入并完成真实 API 端到端验证（2026-10-11）
> 涉及代码：`src/llm/`（client.py / intake.py / __init__.py）、`src/orchestrator.py`、`src/api/app.py`

## 1. 架构定位

LLM 只承担 **Intake 层的信息抽取**（模块识别 + 槽位抽取），分诊裁决全部由确定性引擎完成：

```
用户文本 ──> LLM intake（模块+槽位）──> L1 红旗（确定性）──> L2 决策表（确定性）
                                              │                    │
                                              └──> L3 自护 / L4 机构推荐（确定性）
```

- **红牌 = 安全底座，可追责**：LLM 永不参与紧急度判断。
- **生成式只增强、不裁决**：LLM 输出经白名单校验后才进入槽位；校验不合法即丢弃（不猜）。
- **失败不阻塞**：LLM 调用异常 / 超时 / 输出不可用时，自动回退关键词规则（原 orchestrator 逻辑）。

## 2. 接入配置（新加坡地域）

环境变量（复制 `.env.example` 为 `.env`）：

| 变量 | 必填 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 是 | **新加坡地域**创建的百炼 API Key（Key 按地域绑定，用北京 Key 调新加坡 endpoint 会返回 401 invalid_api_key） |
| `DASHSCOPE_WORKSPACE_ID` | 否 | 业务空间 ID（控制台"业务空间详情"查看），如 `ws-xxxxx.ap-southeast-1.maas.aliyuncs.com` 域名中的 `ws-xxxxx` |
| `LLM_MODEL` | 否 | 默认 `qwen-plus`；本项目实测 `qwen3.8-max` |
| `LLM_BASE_URL` | 否 | 显式覆盖 base_url，优先级最高，一般不用填 |
| `LLM_INTAKE_ENABLED` | 否 | `0` 关闭 LLM intake（只走关键词）；默认开启 |
| `LLM_DISABLED` | 否 | `1` 强制使用 DummyLLM（离线调试） |

### base_url 自动构造逻辑（`resolve_base_url()`）

1. `LLM_BASE_URL` 显式配置 → 直接用
2. `DASHSCOPE_WORKSPACE_ID` → `https://{workspace_id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`（业务空间专属域名，官方推荐）
3. 都未配置 → `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`（国际站旧域名回退）

> 注意：`.env` 由 `client.py` 内的轻量加载器读取（模块导入时执行，只填充未设置的环境变量，不覆盖已有值），无需安装 python-dotenv。

## 3. 代码结构

| 文件 | 职责 |
|---|---|
| `src/llm/client.py` | `LLMClient` 抽象、`DashScopeClient`（OpenAI 兼容协议 + 超时）、`DummyLLM`（无 Key 演示）、`get_llm_client()` 工厂、`.env` 加载 |
| `src/llm/intake.py` | `build_intake_prompt`（模块+槽位清单渲染）、`llm_intake`、`keyword_intake`（原关键词逻辑，已从 orchestrator 迁入）、`run_intake` 统一入口、`validate_slots` 白名单校验 |
| `src/orchestrator.py` | `run_pipeline` 新增 `llm` / `llm_intake_enabled` 参数，intake 段调用 `run_intake` |
| `src/api/app.py` | 启动时 `get_llm_client()`；`/api/health` 返回 LLM 状态（provider/model/base_url/intake_enabled） |

### 槽位校验规则（`validate_slots`）

- **enum**：值必须在 `allowed_values` 的 id 内
- **bool**：接受 `true/false` 及常见中英文同义表述，规范化为布尔
- **int / float**：类型检查 + `range.min/max` 边界
- **duration**：`{"value": 数字, "unit": "hours|days|weeks"}`
- **date**：`YYYY-MM-DD`
- 未知槽位 / 不合法值一律丢弃，并保留 `confidence`（默认 1.0，夹取 0–1）

## 4. 回退机制

```
run_intake(text, config, llm, enabled)
  ├─ 未启用 或 llm=None         → keyword_intake
  ├─ LLM 调用异常/超时           → keyword_intake
  ├─ 输出无法解析为 JSON         → keyword_intake
  ├─ module 非法 且 slots 为空   → keyword_intake
  └─ 成功                        → 使用 LLM 结果（已校验）
```

模块识别失败时 pipeline 沿用原有兜底（默认 `heavy_bleeding`），流程永不被 LLM 阻断。

## 5. 真实 API 验证记录（2026-10-11，qwen3.8-max）

### 5.1 连通性

```
provider=dashscope  model=qwen3.8-max
base_url=https://ws-teqzyu1e1m9hziaq.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
```

### 5.2 端到端五场景

| 场景 | 输入（摘） | 模块 | 出口 | 结果 |
|---|---|---|---|---|
| 红旗紧急 | "月经出血特别多，刚才站起来直接晕倒了" | heavy_bleeding | EMERGENCY_NOW + 机构推荐 | ✅ |
| 门诊建议 | "出血比平时多，已经三天了，有点头晕" | heavy_bleeding | L2 追问（流量比较） | ✅ |
| 自护场景 | "来月经肚子有点疼，和平常差不多" | severe_period_pain | L2 追问（疼痛 0–10） | ✅ |
| 多轮追问 | 主诉 → 回答 much_more | heavy_bleeding | 正确推进到浸透频率问题 | ✅ |
| 英文场景 | "My period is two weeks late..." | late_or_missed_period | L2 英文追问 | ✅ |

### 5.3 Intake 抽取质量（真实模型）

- 中文经量过多：抽取 6 个槽位（主诉/经期进行中/流量比较/自述量级/浸透/发热状态），全部通过校验
- 英文月经推迟：`period_delay_days=14`、`pregnancy_status=possibly_pregnant`
- 中文痛经：疼痛时机/与平常比较/活动影响 3 槽位
- 已知问题与修复：初版 prompt 下"来月经肚子有点疼，和平常差不多"被误归 heavy_bleeding；已强化模块选择规则（疼痛表述优先），复测归位 severe_period_pain。

### 5.4 测试

- `pytest tests/`：**46/46 通过**（含 19 个 LLM 相关用例：base_url 解析 / 值校验 / 回退 / pipeline 集成）
- 无 Key 环境（DummyLLM）：demo、CI、现场演示可无网络跑通

## 6. 安全与运维

- **Key 地域绑定**：新加坡 endpoint 必须配新加坡地域 Key；跨地域调用返回 `401 invalid_api_key`（错误信息与 Key 失效相同，先核对地域再重置）。
- **Key 泄露处置**：控制台重置即可；`.env` 已被 `.gitignore` 忽略，不会进 git。
- **模型成本**：intake 单轮约 1 次调用（prompt 含全量 65 槽位定义，约 7k token）；`qwen3.8-max` 成本高于 `qwen-turbo`，可按预算切换。
- **部署（Render）**：`render.yaml` 已预留 `DASHSCOPE_API_KEY` / `DASHSCOPE_WORKSPACE_ID` 环境变量（sync: false，面板填写）；生产环境 Key 由平台注入，代码同样自动读取。

## 7. 已知边界

- 当前仅 Intake 使用 LLM；最终话术（persona）仍为模板渲染，未接入 LLM（如需个性化摘要可沿用同一 `LLMClient` 扩展）。
- 槽位全量入 prompt（65 个），单次调用 token 偏大；若需优化可按"模块相关槽位 + context 槽位"裁剪 prompt。
- 多轮上下文：当前每轮独立调用 LLM intake，未传历史；槽位由 Session 累积，不影响正确性。
