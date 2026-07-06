# 药食同源多智能体研发协同平台 — Agent 开发规则

> 本文件是项目的开发约束手册。后续开发，包括人工编码和 AI 辅助编码，都必须以当前真实项目结构为准，避免沿用旧的 v3/Compound/MiniMax 口径。

---

## 1. 当前技术栈

| 层 | 技术 | 当前约定 |
|---|---|---|
| 后端框架 | FastAPI | Python 3.10+，同步 handler 为主 |
| ORM | SQLAlchemy 2.x | `DeclarativeBase` + `Mapped` + `mapped_column` |
| 关系数据库 | PostgreSQL | JSONB，`psycopg` 驱动 |
| 图数据库 | Neo4j 5.x | `python-neo4j` 官方驱动 |
| LLM | DeepSeek API | `DeepSeekClient` + `httpx.Client` 同步客户端 |
| 前端框架 | Vue 3 | Composition API，`<script setup>` |
| UI 库 | Element Plus | `el-*` 组件 |
| 状态管理 | Pinia | `defineStore` |
| 构建工具 | Vite 5.x | `npm run build` |
| 前后端通信 | axios + SSE | REST JSON + `/chat/.../messages/stream` |

说明：

- `backend/app/services/deepseek_client.py` 是当前 LLM 主客户端。
- `backend/app/services/minimax_client.py` 属于历史兼容文件，不再作为新增开发入口。
- `core/config.py` 仍兼容读取旧 `MINIMAX_*` 环境变量，但新增配置应优先使用 `DEEPSEEK_*` / 通用 `llm_*` 字段。

---

## 2. 当前目录结构

### 2.1 后端

```text
backend/app/
├── api/
│   ├── routes.py              # 所有 HTTP 路由，按 APIRouter 分组
│   └── deps.py                # FastAPI 依赖注入工厂
├── core/
│   └── config.py              # Settings dataclass + dotenv
├── db/
│   ├── models.py              # SQLAlchemy ORM 模型
│   ├── sqlalchemy.py          # engine, SessionLocal, Base
│   ├── init_db.py             # 建表 + 种子数据
│   └── seed_data.py           # Prompt / Cypher / SystemConfig 种子
├── domain/                    # 预留领域层目录
├── prompts/
│   └── knowledge_qa_answer_rules.md  # 知识问答回答规则
├── repositories/
│   ├── postgres_repository.py
│   └── neo4j_repository.py
├── schemas/
│   ├── admin.py
│   ├── auth.py
│   ├── chat.py
│   ├── common.py
│   ├── entity.py
│   └── rnd.py
├── services/
│   ├── auth_service.py
│   ├── deepseek_client.py
│   ├── entity_resolver.py
│   ├── graph_retriever.py
│   ├── minimax_client.py      # 历史兼容，新增逻辑不要优先使用
│   ├── qa_answer_templates.py
│   ├── qa_orchestrator.py
│   ├── question_classifier.py
│   └── rnd_workflow_orchestrator.py
└── utils/                     # 预留工具目录
```

### 2.2 前端

```text
frontend/src/
├── api/
│   └── client.js              # axios + SSE 封装
├── components/
│   ├── EntityDrawer.vue
│   └── GraphCanvas.vue
├── layouts/
│   └── MainLayout.vue
├── router/
│   └── index.js
├── stores/
│   ├── auth.js
│   ├── chat.js
│   └── rnd.js
├── utils/
│   └── qaAnswerFormat.js      # QA 回答小标题解析与排序
└── views/
    ├── LoginView.vue
    ├── admin/
    │   ├── LogsView.vue
    │   ├── OverviewView.vue
    │   ├── PromptView.vue
    │   └── TemplateView.vue
    └── portal/
        ├── ChatView.vue
        ├── HistoryView.vue
        ├── HomeView.vue
        └── RndWorkspaceView.vue
```

其他目录：

- `scripts/import_agent_kg_0604.py`：0604 KB1-KB8 + CDB1 Neo4j 全量重建脚本。
- `scripts/import_neo4j_graph_v3.py`、`scripts/import_agent_project_data.py`：历史/参考脚本，非当前主线。
- `frontend/remotion/`：登录背景等视频/视觉生成相关代码。
- `frontend/public/` 与 `frontend/dist/`：登录背景资源和构建产物。

---

## 3. 后端分层职责

| 层 | 职责 | 禁止 |
|---|---|---|
| `api/routes.py` | HTTP 参数解析、Schema 校验、调用 Service、返回 Schema/SSE | 禁止直接写复杂 SQL/Cypher 或业务编排 |
| `api/deps.py` | 依赖注入工厂、Repository/Service 创建 | 禁止堆业务逻辑 |
| `services/` | 业务编排、流程控制、LLM fallback、图谱证据组织 | 禁止直接操作底层 HTTP Request/Response |
| `repositories/` | PostgreSQL CRUD、Neo4j Cypher 查询、图谱转换 | 禁止包含产品业务判断 |
| `schemas/` | Pydantic v2 请求/响应结构 | 禁止写业务方法 |
| `db/models.py` | ORM 映射 | 禁止写业务方法 |
| `core/config.py` | 环境变量和 Settings | 禁止依赖业务模块 |

依赖注入规则：

- 路由层通过 `Depends()` 获取 `Session`、`Neo4jRepository`、当前用户等依赖。
- `Neo4jRepository` 必须通过 `get_neo4j_repository()` 这类 generator 依赖关闭，或在手动创建后 `finally: close()`。
- `PostgresRepository` 的 `session.commit()` 由调用方负责，通常在路由层或 orchestrator 完成业务单元后提交。
- 后台任务中手动创建的 `SessionLocal()` 和 `Neo4jRepository()` 必须在 `finally` 中关闭。

路由前缀：

- 认证：`/auth/...`
- 健康检查：`/health`
- 知识问答：`/chat/...`
- 通用实体：`/entities/...`
- 研发协同：`/rnd/...`
- 管理后台：`/admin/...`

---

## 4. PostgreSQL 建模与种子数据

### 4.1 ORM 规则

- 所有 Model 统一放在 `backend/app/db/models.py`。
- Model 继承 `Base`，需要时间字段时继承 `TimestampMixin`。
- 主键默认使用 `String(36)` + `uuid.uuid4()` 字符串。
- 复杂结构使用 PostgreSQL `JSONB`。
- 新增 Model 后必须确保 `init_db.py` 的 `Base.metadata.create_all()` 能自动建表。

### 4.2 种子数据

- Prompt 模板在 `seed_data.py` 的 `DEFAULT_PROMPTS` 中维护。
- Cypher 模板在 `seed_data.py` 的 `DEFAULT_CYPHER_TEMPLATES` 中维护。
- SystemConfig 在 `seed_data.py` 中维护。
- `PromptTemplate` 按 `scenario` + `agent_key` 组织。
- 当前 `scenario`：`knowledge_qa`、`rnd_workflow`。
- 新增 Prompt / Cypher 模板时必须同步更新 `output_schema` 或 `parameter_schema`。
- 种子逻辑必须保持幂等，使用“存在则跳过/更新”的方式，不写破坏性初始化。

---

## 5. Neo4j 图谱建模规则（0604 KB1-KB8 + CDB1）

### 5.1 当前图谱口径

- 当前正式图谱以 `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\药食同源Agent_8类知识库-0531` 和 `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\0512-消费者_体质` 为权威源。
- 使用 `scripts/import_agent_kg_0604.py` 全量重建。
- 新图谱不导入 `Compound` / 成分网络，不主动检索旧成分-功效网络。
- 旧 `neo4j_graph_v3`、旧 dump 和旧 Compound 数据仅作备份参考，不回灌。
- `ConsumerProfile`、`ConsumerSegment`、`ConsumerReview` 是 CDB1 消费者画像与评论偏好正式节点；新增检索和回答逻辑可以依赖它们。代码不得依赖旧 `Compound`。
- 最新 dry-run 验收基线为 `86,482 nodes / 207,354 relationships`，`Compound=0`；CDB1 同时服务企业端（人群定位、风味/剂型、市场差异化）和个人端（产品适配、口味偏好、风险边界辅助判断）。

### 5.2 8 类知识库

| 编号 | 知识库 | 图谱用途 |
|---|---|---|
| KB1 | 药食同源原料合法性库 | 原料合法性、毒性、孕妇禁忌、使用注意 |
| KB2 | 功效-病症-性味归经库 | 功效、病症、性味、归经、禁忌 |
| KB3 | 风味评价库 | 苦味/涩感/药味风险、香气、风味接受度 |
| KB4 | 单味药替代评分库 | `CAN_REPLACE` 单味药替代评分 |
| KB5 | 名方/方剂知识库 | 方剂、来源、组成、君臣佐使、功效、主治 |
| KB6 | 产品与市场库 | 产品、品牌、剂型、卖点、场景、竞品功效标签 |
| KB7 | 食品标准合规库 | 药食同源目录、GB2760、GB7718、宣传边界、禁用/慎用表述 |
| KB8 | 9 种体质辨识与食养规则库 | 体质问卷、评分规则、食养方向、慎用原料 |
| CDB1 | 消费者画像与评论偏好库 | 产品、消费者画像、人群场景功效分组、京东/淘宝评论、风味偏好、剂型偏好、投诉点 |

### 5.3 当前节点类型

| 标签 | 唯一键 | 说明 |
|---|---|---|
| `Herb` | `herb_name` | 药食同源/非药食同源原料 |
| `EffectCategory` | `effect_category_name` | 功效大类/二级功效分类 |
| `Effect` | `effect_name` | 功效标签 |
| `Symptom` | `symptom_name` | 症状/主治 |
| `NatureFlavor` | `nature_flavor_name` | 中医性味 |
| `Meridian` | `meridian_name` | 归经 |
| `Flavor` | `flavor_name` | 食品/感官风味 |
| `Taboo` | `taboo_name` | 禁忌/慎用描述 |
| `Formula` | `formula_name` | 名方/方剂 |
| `Source` | `source_name` | 方剂出处 |
| `Product` | `product_id` | 产品/竞品 |
| `ComplianceRule` | `rule_id` | 食品合规、标签、宣传、体质评分等规则 |
| `RiskExpression` | `expression` | 禁用/慎用宣传表述 |
| `ConstitutionType` | `constitution_type_name` | 九种体质 |
| `ConstitutionQuestion` | `question_code` | 体质问卷题目 |
| `ConsumerProfile` | `profile_id` | 商品对应消费者画像 |
| `ConsumerSegment` | `segment_key` | 人群-场景-功效分组 |
| `ConsumerReview` | `review_id` | 匿名化消费者评论与标签 |

说明：

- `Flavor` 是食品/感官风味。
- `NatureFlavor` 是中医性味。
- 二者不能合并。

### 5.4 当前关系类型

| 关系 | 起点 → 终点 | 说明 |
|---|---|---|
| `HAS_EFFECT` | Herb/Formula → Effect | 原料或方剂功效 |
| `BELONGS_TO_EFFECT_CATEGORY` | Herb → EffectCategory | 原料功效分类 |
| `TREATS` | Herb → Symptom | 原料主治/适配病症 |
| `TARGETS_SYMPTOM` | Formula → Symptom | 方剂主治/适配病症 |
| `HAS_NATURE_FLAVOR` | Herb → NatureFlavor | 中医性味 |
| `ENTERS_MERIDIAN` | Herb → Meridian | 归经 |
| `HAS_FLAVOR` | Herb → Flavor | 食品感官风味 |
| `HAS_TABOO` | Herb/Formula → Taboo | 禁忌或慎用 |
| `CAN_REPLACE` | Herb → Herb | 单味药替代评分；含 KB4 Top10、consumer_aware 消费者感知分、禁忌排除候选 |
| `INCOMPATIBLE_WITH` | Herb → Herb | 十八反/十九畏配伍禁忌（双向） |
| `IN_FORMULA` | Herb → Formula | 方剂组成，属性可含 `role` / `dosage` |
| `MONARCH_HERB` / `MINISTER_HERB` / `ASSISTANT_HERB` / `GUIDE_HERB` | Formula → Herb | 君臣佐使 |
| `FROM_SOURCE` | Formula → Source | 方剂出处 |
| `USES_HERB` | Product → Herb | 产品配料或商品名推断原料，边属性可含 `match_source` |
| `CLAIMS_EFFECT` | Product → Effect | 产品/竞品功效标签 |
| `LISTED_IN_COMPLIANCE_RULE` | Herb → ComplianceRule | 原料进入药食同源目录或相关规则 |
| `DERIVED_FROM_RULE` | RiskExpression → ComplianceRule | 禁用/慎用表述对应规则 |
| `ASSESSES_CONSTITUTION` | ConstitutionQuestion → ConstitutionType | 体质问卷题目归属 |
| `RECOMMENDS_HERB` | ConstitutionType → Herb | 体质食养适宜原料 |
| `CAUTIONS_HERB` | ConstitutionType → Herb | 体质慎用原料 |
| `HAS_CONSUMER_PROFILE` | Product → ConsumerProfile | 产品对应消费者画像 |
| `PREFERS_FLAVOR` / `DISLIKES_FLAVOR` | ConsumerProfile → Flavor | 画像偏好/不喜欢风味 |
| `SEGMENT_PREFERS_FLAVOR` | ConsumerSegment → Flavor | 人群分组高频风味 |
| `TOP_PRODUCT` | ConsumerSegment → Product | 人群分组高频产品 |
| `MATCHES_CONSUMER_SEGMENT` | ConsumerProfile → ConsumerSegment | 画像匹配的人群场景功效分组 |
| `REVIEWS_PRODUCT` | ConsumerReview → Product | 评论对应产品 |
| `MENTIONS_FLAVOR` / `MENTIONS_EFFECT` | ConsumerReview → Flavor/Effect | 评论标签提到的风味/功效 |
| `BELONGS_TO_CONSUMER_SEGMENT` | ConsumerReview → ConsumerSegment | 评论归属的人群场景功效分组 |

### 5.5 写入约束

- 每种节点必须有独立唯一约束，不使用统一 `Entity` 标签。
- 写入节点必须使用 `MERGE`：`MERGE (n:{Label} {unique_key: $value}) SET n += $props`。
- 导入关系必须使用 `MERGE`，避免重复边。
- 增量脚本不能清空已有数据；全量重建脚本必须显式 `--clear`，且正式清空前备份旧图谱。

### 5.6 新增节点类型 Checklist

新增图谱节点类型时必须同步：

1. 更新 `scripts/import_agent_kg_0604.py` 或新增正式导入脚本。
2. 在导入脚本中创建唯一约束。
3. 更新 `neo4j_repository.py` 的 `search_entities()`。
4. 更新 `neo4j_repository.py` 的 `get_entity()`。
5. 更新 `neo4j_repository.py` 的 `retrieve_graph_for_entity()`。
6. 更新 `_node_id()`、`_node_label()`、`_primary_label()`、`_node_priority()`。
7. 更新 `graph_retriever.py` 的实体选择、节点优先级和必要的专用查询。
8. 按需更新 `question_classifier.py`。
9. 更新 `qa_orchestrator.py` 的 `_build_llm_context()` 属性映射。
10. 按需更新 `seed_data.py` 的 Cypher 模板。
11. 更新 `frontend/src/components/GraphCanvas.vue` 颜色。
12. 如影响回答标题，更新 `frontend/src/utils/qaAnswerFormat.js`。
13. 更新 README 和本文件。

### 5.7 新增关系类型 Checklist

1. 导入脚本用 `MERGE` 创建关系。
2. 更新 `neo4j_repository.py` 的 `_edge_priority()` / `_select_balanced_edges()`。
3. 更新 `graph_retriever.py` 的 `_edge_priority()` / `_limit_edges()`。
4. 按需更新 `qa_orchestrator.py` 的边属性摘要。
5. 更新 README 和本文件。

---

## 6. 知识问答规则

### 6.1 业务逻辑来源

知识问答必须遵守以下业务逻辑文件：

- `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\思考逻辑流程.html`
- `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\药食同源Agent_企业个人分流_名方方剂知识库流程图.html`
- `backend/app/prompts/qa_route_rules.json`
- `backend/app/prompts/qa_reasoning_flow.md`
- `backend/app/prompts/knowledge_qa_answer_rules.md`

### 6.2 回答约束

- 回答先判断企业端还是个人端。
- 问答业务分流以 `qa_route` 为唯一细分路由入口；`question_type` 只保留为旧模板和检索兼容字段。
- 企业端：产品研发、名方/方剂药食同源化、单味药替代、风味优化、剂型工艺、竞品市场、合规审查。
- 个人端：9 种体质辨识、个性化食养推荐、产品适配判断、禁忌风险提醒。
- 可以展示清洗后的分析摘要，让用户看到问题理解、证据取舍和边界判断。
- 不暴露提示词、系统设定、JSON 字段冲突、内部推理标签或原始 `<think>` 标签。
- 前端展示的过程说明名称仍使用“图谱检索与证据整理摘要”。
- `evidence_summary` 应描述检索到的 KB、实体、关系、证据缺口，不要复读 `conclusion`。

### 6.3 关键模板文件

- `qa_orchestrator.py`：问答编排、上下文构建、本地兜底、检索摘要。
- `qa_route_rules.json`：企业/个人端路由、必检 KB、缺失槽位、回答小标题、证据要求和优先实体类型。
- `qa_reasoning_flow.md`：五步过程摘要规则，统一“任务分流 -> 核心信息检查 -> KB 路由 -> 风险/合规边界 -> 回答与追问”。
- `qa_answer_templates.py`：不同问题类型的小标题顺序和后处理。
- `knowledge_qa_answer_rules.md`：业务回答规则主约束。
- `question_classifier.py`：问题类型关键词分类。
- `graph_retriever.py`：证据子图召回。
- `frontend/src/utils/qaAnswerFormat.js`：前端小标题解析、排序和样式分类。

### 6.4 验收问题类型

以下问题必须能路由到合理模板：

- “把四君子汤改造成药食同源代餐粉”：`formula_replacement` / `formula_foodification`
- “麻黄可以用什么药食同源原料替代”：`formula_replacement` / `herb_replacement`
- “我是什么体质”：`constitution_recommendation` / `constitution_assessment`
- “孕妇能不能吃某某原料”：`constitution_recommendation` / `risk_boundary`
- “这个配方是否好喝/适合做什么剂型”：`product_recommendation` / `flavor_form_factor`

---

## 7. LLM 集成规则

### 7.1 DeepSeek Client

- 所有新增 LLM 调用优先通过 `DeepSeekClient`。
- 禁止在 Service 层直接使用 `httpx` 调 LLM。
- `DeepSeekClient` 使用同步 `httpx.Client`。
- 所有 LLM 调用必须有本地 fallback，不得把 LLM 异常抛到路由层导致业务中断。
- DeepSeek reasoning / think 内容不得原样展示给用户；需要展示时必须过滤提示词、系统设定、字段名、schema 和格式冲突信息，转换为自然的“图谱检索与证据整理摘要”。

### 7.2 结构化输出

- QA 输出字段：`conclusion`、`evidence_summary`、`cautions`、`related_entities`、`follow_up_questions`。
- RnD Agent 输出必须通过 `_matches_expected_shape()` 或等价校验。
- 校验失败时使用本地 fallback 数据。
- 新增 Agent 时必须在 `seed_data.py` 中定义 `output_schema`。

### 7.3 Prompt 管理

- Prompt 模板存储在 PostgreSQL `prompt_template` 表。
- 种子 Prompt 在 `seed_data.py` 中定义。
- 按 `scenario`（`knowledge_qa`、`rnd_workflow`）+ `agent_key` 组织。
- 可通过管理后台在线编辑 Prompt。
- 可编辑 Prompt 不能覆盖代码中的安全硬约束。

---

## 8. 研发协同工作流规则

### 8.1 Agent 编排

当前固定顺序在 `RnDWorkflowOrchestrator.AGENT_SEQUENCE` 中：

1. `master_control`
2. `formula_generation`
3. `efficacy_prediction`
4. `flavor_prediction`
5. `replacement_mapping`
6. `master_control_final`

每步规则：

- 每步生成一个 `WorkflowStepRun`。
- 每步可生成一个 `GraphSnapshot` 供前端展示。
- 工作流通过 FastAPI `BackgroundTasks` 后台执行。
- 前端轮询运行状态。
- LLM 失败必须 fallback，不能让整个工作流直接中断。

### 8.2 Agent 职责

| Agent Key | 角色 | 核心职责 |
|---|---|---|
| `master_control` | 药食同源智研系统主控 Agent | 需求拆解、模块调度、逻辑校验、方案整合、合规校验 |
| `formula_generation` | 药食同源方剂生成专家 | 组方设计、君臣佐使配伍、剂量建模、方解撰写、合规校验 |
| `efficacy_prediction` | 药食同源功效预测专家 | 中医功效、现代药理、人群分层、风险评估 |
| `flavor_prediction` | 药食同源风味预测专家 | 风味特征、协调性、缺陷、优化建议 |
| `replacement_mapping` | 药食同源替代映射专家 | 功效/风味/成本/合规/工艺/供应链替代方案 |
| `master_control_final` | 最终主控汇总 | 整合各模块输出，形成最终研发方案 |

### 8.3 新增 Agent 步骤

1. 在 `AGENT_SEQUENCE` 中添加新 Agent key。
2. 在 `seed_data.py` 中定义 PromptTemplate 和 `output_schema`。
3. 在 `rnd_workflow_orchestrator.py` 中实现 `_run_step` 分支和 fallback。
4. 如需图谱展示，补充 GraphSnapshot 构建逻辑。
5. 在 `frontend/src/views/portal/RndWorkspaceView.vue` 中处理新步骤展示。
6. 更新 README 和本文件。

### 8.4 Brief 结构

- Brief 由 `_build_brief()` 生成。
- Brief 通过 `workflow_session.last_brief` 持久化。
- 支持 `reuse_last_brief` 复用上次 Brief。

### 8.5 待扩展模块

- `process_adaptation`：工艺适配，尚未作为独立 Agent 实现。
- `market_prediction`：市场预测，尚未作为独立 Agent 实现。

---

## 9. 前端开发规则

### 9.1 组件与状态

- 页面组件使用 `{Feature}View.vue` 命名。
- 组件使用 `<script setup>` + Composition API。
- 全局/跨页面状态放 Pinia Store：`auth.js`、`chat.js`、`rnd.js`。
- 组件本地状态使用 `ref` / `computed`。
- 组件样式使用 `<style scoped>`。
- 禁止在组件中直接使用 `axios`，所有请求走 `frontend/src/api/client.js`。

### 9.2 路由与页面

- 普通页面嵌套在 `MainLayout` 下。
- 登录页为 `LoginView.vue`。
- 用户侧页面在 `views/portal/`。
- 管理后台页面在 `views/admin/`。
- 新增页面必须同步更新 `router/index.js`、`MainLayout.vue` 菜单和 route name 映射。

### 9.3 知识问答前端

- `ChatView.vue` 展示 QA 流式回答、证据摘要、证据子图、注意事项、追问。
- `chat.js` 负责 SSE 事件处理、消息归一化和图谱快照加载。
- `qaAnswerFormat.js` 负责将 `【】` 小标题解析成结构化 UI。
- 不要把模型原始 `<think>` 标签或提示词相关内容展示给用户；允许展示清洗后的分析摘要，展示名称必须使用“图谱检索与证据整理摘要”。

### 9.4 图谱前端

- 图谱颜色统一在 `GraphCanvas.vue` 中维护。
- 新增节点类型时必须补颜色配置。
- 当前不要为 `Compound` 新增主色配置；`ConsumerProfile`、`ConsumerSegment`、`ConsumerReview` 属于 CDB1 正式节点，图谱 UI 必须配置主色。

### 9.5 样式

- 整体遵循 RuoYi 风格：深色侧边栏、浅灰内容区、Element Plus 表格和卡片。
- 表格优先使用 `el-table` + `border` + `stripe`。
- 分页使用 `el-pagination` + `background`。
- 弹窗/抽屉使用 `el-dialog` 或 `el-drawer`。
- 不要残留 `console.error` 等生产调试输出。

---

## 10. 数据导入脚本规则

### 10.1 脚本位置

- 正式脚本放在 `scripts/`。
- 命名：`import_{功能}.py`。
- 临时调试脚本禁止提交。

### 10.2 当前主导入脚本

```powershell
python .\scripts\import_agent_kg_0604.py --dry-run --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
python .\scripts\import_agent_kg_0604.py --clear --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
```

规则：

- `--dry-run` 只解析数据和输出统计，不连接 Neo4j。
- `--clear` 是破坏性导入，必须由用户明确要求后才运行。
- 正式 `--clear` 前默认备份旧 Neo4j 到 `neo4j_backups/`（JSON）；可用 `scripts/restore_neo4j_backup.py` 回退。
- `neo4j_backups/` 不提交到版本控制。
- KB6 若无配料字段，可从商品名保守匹配已知 Herb，并在 `USES_HERB.match_source` 标注来源。

### 10.3 数据源

- 当前正式数据：`D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\药食同源Agent_8类知识库-0531` 与 `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\0512-消费者_体质`
- 两份业务逻辑 HTML 位于：`D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\`
- `origin_data/` 仅作为补充/历史资料，不是 0604 图谱权威源。

---

## 11. 环境与配置

### 11.1 后端环境变量

所有配置通过 `backend/.env` 管理，敏感信息禁止硬编码。

常用项：

```text
APP_NAME=药食同源知识问答平台
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=8000
POSTGRES_DSN=postgresql+psycopg://postgres:1234@localhost:5432/postgres
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING_ENABLED=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<change-me>
```

### 11.2 Python 依赖

- 项目保留 `backend/_vendor` 机制。
- 启动脚本通过 `PYTHONPATH` 引入 `_vendor`。
- 新增依赖时同步更新 `requirements.txt` 和实际运行环境。

### 11.3 Node 依赖

- 前端依赖通过 `npm install` 安装到 `frontend/node_modules`。
- 开发命令：`npm run dev -- --host 0.0.0.0 --port 5173`。
- 构建命令：`npm run build`，输出到 `frontend/dist/`。

---

## 12. 构建与验证

### 12.1 后端验证

按修改范围运行：

```powershell
python scripts\validate_qa_routing.py
python -m py_compile backend\app\services\qa_routing.py
python -m py_compile backend\app\services\qa_orchestrator.py
python -m py_compile backend\app\services\qa_answer_templates.py
python -m py_compile backend\app\services\deepseek_client.py
python -m py_compile backend\app\services\question_classifier.py
python -m py_compile backend\app\services\graph_retriever.py
python -m py_compile backend\app\repositories\neo4j_repository.py
python -m py_compile backend\app\db\seed_data.py
python -m py_compile scripts\import_agent_kg_0604.py
```

### 12.2 前端验证

```powershell
cd frontend ; npm run build
```

Vite 大 chunk 警告目前不是失败条件。

### 12.3 图谱验证

导入后在 Neo4j 执行：

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC;
MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC;
MATCH (c:Compound) RETURN count(c) AS compound_count;
MATCH (cp:ConsumerProfile) RETURN count(cp) AS consumer_profile_count;
MATCH (cs:ConsumerSegment) RETURN count(cs) AS consumer_segment_count;
MATCH (rv:ConsumerReview) RETURN count(rv) AS consumer_review_count;
```

0604 新图谱验收要求：`compound_count = 0`。

### 12.4 知识问答验证

至少检查：

- 分类器对 5 个业务验收问题的分类。
- `scripts\validate_qa_routing.py` 中典型问题的 `qa_route/question_type/audience` 全部通过。
- 回答正文使用 `【】` 小标题。
- 前端过程区标题为“图谱检索与证据整理摘要”。
- 回答和证据摘要不出现 `<think>`、提示词、系统设定、JSON 字段冲突。

---

## 13. Git 与文件保护

- 不提交 `.env`、`node_modules/`、`__pycache__/`、`*.pyc`、临时调试脚本、`neo4j_backups/`。
- 不随意回滚用户已有修改；工作树可能是 dirty。
- 生成或构建导致 `frontend/dist/` 变化时，要在最终说明中说明。
- 提交信息格式：`{类型}: {简要描述}`，类型包括 `feat`、`fix`、`refactor`、`docs`、`chore`。

---

## 14. 关键文件索引

| 文件 | 作用 | 修改频率 |
|---|---|---|
| `backend/app/api/routes.py` | HTTP 路由、SSE、后台任务入口 | 高 |
| `backend/app/api/deps.py` | 依赖注入工厂 | 中 |
| `backend/app/core/config.py` | 环境变量与 Settings | 中 |
| `backend/app/db/models.py` | ORM 模型 | 中 |
| `backend/app/db/seed_data.py` | Prompt/Cypher/SystemConfig 种子 | 高 |
| `backend/app/repositories/neo4j_repository.py` | Neo4j 查询、图谱转换、节点/边优先级 | 高 |
| `backend/app/repositories/postgres_repository.py` | PostgreSQL CRUD | 中 |
| `backend/app/services/qa_orchestrator.py` | 知识问答编排、上下文、fallback、检索摘要 | 高 |
| `backend/app/services/qa_answer_templates.py` | QA 小标题模板与后处理 | 高 |
| `backend/app/prompts/knowledge_qa_answer_rules.md` | 知识问答回答规则 | 高 |
| `backend/app/services/graph_retriever.py` | 图谱证据召回与裁剪 | 高 |
| `backend/app/services/question_classifier.py` | 问题类型分类 | 中 |
| `backend/app/services/entity_resolver.py` | 实体识别与消歧 | 中 |
| `backend/app/services/deepseek_client.py` | LLM 调用、流式输出、fallback | 高 |
| `backend/app/services/rnd_workflow_orchestrator.py` | 研发协同工作流 | 高 |
| `frontend/src/api/client.js` | REST/SSE API 封装 | 中 |
| `frontend/src/stores/chat.js` | 知识问答状态与流式消息处理 | 高 |
| `frontend/src/utils/qaAnswerFormat.js` | QA 回答结构化渲染 | 高 |
| `frontend/src/views/portal/ChatView.vue` | 知识问答页面 | 高 |
| `frontend/src/views/portal/RndWorkspaceView.vue` | 研发协同页面 | 高 |
| `frontend/src/components/GraphCanvas.vue` | 图谱可视化 | 中 |
| `scripts/import_agent_kg_0604.py` | 0604 图谱全量重建 | 高 |
| `README.md` | 项目说明 | 中 |
| `AGENTS.md` | 开发规则 | 中 |

---

## 15. 新增功能开发 Checklist

- [ ] 后端 Model：如需新表，在 `models.py` 添加 Model。
- [ ] 后端 Schema：在 `schemas/` 添加 Pydantic 请求/响应 Schema。
- [ ] Repository：在 `postgres_repository.py` 或 `neo4j_repository.py` 添加数据访问方法。
- [ ] Service：在 `services/` 添加业务编排逻辑和 fallback。
- [ ] Route：在 `routes.py` 添加 API 端点。
- [ ] 种子数据：如需 Prompt/Cypher/SystemConfig，更新 `seed_data.py`。
- [ ] 图谱建模：涉及新节点/关系时完成第 5 节 Checklist。
- [ ] QA 规则：影响问答框架时更新 `knowledge_qa_answer_rules.md` 和 `qa_answer_templates.py`。
- [ ] 前端 API：在 `client.js` 添加接口方法。
- [ ] 前端 Store：如需全局状态，更新 `stores/`。
- [ ] 前端页面：新增或更新 `views/`。
- [ ] 前端路由/菜单：更新 `router/index.js` 和 `MainLayout.vue`。
- [ ] 图谱 UI：新增节点类型时更新 `GraphCanvas.vue`。
- [ ] 数据导入脚本：如需导入新数据，更新 `scripts/`。
- [ ] 文档：更新 README 和 AGENTS.md。
- [ ] 验证：按修改范围运行 `py_compile`、`npm run build`、dry-run 或 Neo4j 查询。
