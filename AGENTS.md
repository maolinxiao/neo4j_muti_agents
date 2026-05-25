# 药食同源多智能体研发协同平台 — Agent 开发规则

> 本文件是项目的**开发约束手册**，所有后续开发（包括人工编码和 AI 辅助编码）都必须遵守以下规则，确保项目的完整性、可扩展性和可维护性。

---

## 1. 项目技术栈

| 层 | 技术 | 版本约束 |
|---|---|---|
| 后端框架 | FastAPI | Python 3.10+ |
| ORM | SQLAlchemy 2.x (mapped_column 声明式) | `DeclarativeBase` + `Mapped` |
| 数据库 | PostgreSQL (JSONB) | psycopg 驱动 |
| 图数据库 | Neo4j 5.x | python-neo4j 官方驱动 |
| LLM | MiniMax API (`MiniMax-M2.7`) | httpx 同步客户端 |
| 前端框架 | Vue 3 Composition API | `<script setup>` |
| UI 库 | Element Plus | el-* 组件 |
| 状态管理 | Pinia | defineStore |
| 构建工具 | Vite 5.x | |
| 前后端通信 | axios (REST JSON) | vite proxy → localhost:8000 |

---

## 2. 后端架构分层

```
backend/app/
├── api/            # 路由层：只做参数校验、调用 Service、返回 Schema
│   ├── routes.py   # 所有路由（按 Router 对象分组）
│   └── deps.py     # FastAPI 依赖注入工厂
├── core/           # 配置
│   └── config.py   # Settings dataclass + dotenv
├── db/             # 数据层
│   ├── models.py   # SQLAlchemy ORM 模型（所有模型在同一文件）
│   ├── sqlalchemy.py  # engine, SessionLocal, Base
│   ├── init_db.py  # 建表 + 种子数据
│   └── seed_data.py   # 默认 Prompt/Cypher/SystemConfig 种子
├── repositories/   # 数据访问层（封装 SQL/Cypher 细节）
│   ├── postgres_repository.py
│   └── neo4j_repository.py
├── schemas/        # Pydantic v2 请求/响应 Schema
│   ├── chat.py
│   ├── entity.py
│   ├── rnd.py
│   ├── admin.py
│   └── common.py
└── services/       # 业务编排层（核心逻辑）
    ├── qa_orchestrator.py
    ├── rnd_workflow_orchestrator.py
    ├── graph_retriever.py
    ├── entity_resolver.py
    ├── question_classifier.py
    └── minimax_client.py
```

### 2.1 分层职责

| 层 | 职责 | 禁止 |
|---|---|---|
| **api/routes** | HTTP 参数解析、Schema 校验、调用 Service、返回 Schema | 禁止直接写 SQL / Cypher / 业务逻辑 |
| **services** | 业务编排、流程控制、Fallback 逻辑 | 禁止直接操作 HTTP Request/Response |
| **repositories** | 数据 CRUD、Cypher 查询、SQL 查询 | 禁止包含业务判断逻辑 |
| **schemas** | 请求/响应数据结构定义（Pydantic BaseModel） | 禁止包含业务方法 |
| **models** | ORM 映射（表结构定义） | 禁止包含业务方法 |
| **core/config** | 环境变量读取、Settings 定义 | 禁止依赖业务模块 |

### 2.2 依赖注入规则

- 路由层通过 `Depends()` 获取依赖，不在路由内 `import` 具体实现
- 工厂函数统一放在 `api/deps.py`
- `Neo4jRepository` 实例用完后必须调用 `.close()`
- `PostgresRepository` 的 `session.commit()` 由调用方（通常是路由层）负责

### 2.3 新增路由规则

- 新增功能模块时，在 `routes.py` 中创建新的 `APIRouter`，按前缀分组注册
- 路由前缀约定：
  - 知识问答：`/chat/...`
  - 研发协同：`/rnd/...`
  - 管理后台：`/admin/...`
  - 通用实体：`/entities/...`
  - 健康检查：`/health`

### 2.4 异步与同步

- 当前后端为**同步模式**（`uvicorn` + 同步 handler）
- 长耗时任务（如研发工作流）使用 `BackgroundTasks` 异步执行
- 禁止在同步 handler 中使用 `await`
- `MiniMaxClient` 使用 `httpx.Client`（同步），不使用 `httpx.AsyncClient`

---

## 3. 数据库建模规则

### 3.1 PostgreSQL ORM 约定

- 所有 Model 继承 `Base` 和 `TimestampMixin`
- 主键使用 `String(36)` + `uuid.uuid4()` 字符串
- `created_at` / `updated_at` 使用 `datetime.utcnow`
- 复杂结构使用 `JSONB` 类型
- Model 统一放在 `db/models.py`
- 新增 Model 后必须在 `init_db.py` 的 `Base.metadata.create_all()` 范围内自动建表

### 3.2 种子数据约定

- `PromptTemplate` 按 `scenario` + `agent_key` 组织
- 当前 scenario：`knowledge_qa`、`rnd_workflow`
- `CypherTemplate` 按 `question_type` 组织
- 种子数据使用 `INSERT ... ON CONFLICT DO NOTHING` 模式（幂等）
- 新增种子数据时，同步更新 `seed_data.py` 中的对应列表

---

## 4. Neo4j 图谱建模规则

### 4.1 核心约束

- **每种节点有独立的唯一约束**，不使用统一的 `Entity` 标签
- **唯一约束示例**：`herb_name IS UNIQUE`（Herb）、`canonical_smiles IS UNIQUE`（Compound）、`formula_name IS UNIQUE`（Formula）
- 写入方式：`MERGE (n:{Label} {{unique_key}: $value}) SET n += $props`
- 禁止使用 `CREATE` 创建节点，必须用 `MERGE` 防止重复

### 4.2 当前节点类型

| 标签 | 唯一键 | 说明 |
|------|--------|------|
| `Herb` | `herb_name` | 药材 |
| `Compound` | `canonical_smiles` | 化合物 |
| `Effect` | `effect_name` | 功效 |
| `Flavor` | `flavor_name` | 食品/感官风味 |
| `Formula` | `formula_name` | 方剂 |
| `EffectCategory` | `effect_category_name` | 功效分类 |
| `Symptom` | `symptom_name` | 症状/主治 |
| `Taboo` | `taboo_name` | 禁忌 |
| `Source` | `source_name` | 方剂出处 |
| `NatureFlavor` | `nature_flavor_name` | 中医性味 |
| `Meridian` | `meridian_name` | 归经 |

说明：Flavor 与 NatureFlavor 是不同的概念，不可合并。

### 4.3 当前关系类型

| 关系 | 起点 → 终点 | 属性 |
|------|-------------|------|
| `CONTAINS` | Herb → Compound | `ob`, `dl` |
| `HAS_EFFECT` | Herb → Effect | — |
| `HAS_FLAVOR` | Herb → Flavor | `intensity` |
| `HAS_COMPOUND_EFFECT` | Compound → Effect | — |
| `PRODUCES_FLAVOR` | Compound → Flavor | `intensity` |
| `IN_FORMULA` | Herb → Formula | `role`, `dosage` |
| `BELONGS_TO_EFFECT_CATEGORY` | Herb → EffectCategory | — |
| `TREATS` | Herb → Symptom | — |
| `HAS_TABOO` | Herb → Taboo | — |
| `HAS_NATURE_FLAVOR` | Herb → NatureFlavor | — |
| `ENTERS_MERIDIAN` | Herb → Meridian | — |
| `FROM_SOURCE` | Formula → Source | — |
| `HAS_EFFECT` | Formula → Effect | — |
| `TARGETS_SYMPTOM` | Formula → Symptom | — |
| `HAS_TABOO` | Formula → Taboo | — |
| `MONARCH_HERB` | Formula → Herb | — |
| `MINISTER_HERB` | Formula → Herb | — |
| `ASSISTANT_HERB` | Formula → Herb | — |
| `GUIDE_HERB` | Formula → Herb | — |
| `CAN_REPLACE` | Herb → Herb | `model`, `rank`, `final_score`, `flavor_acceptance`, `effect_similarity`, `source_type` |

### 4.4 新增节点类型规则

新增图谱节点类型时，**必须同步完成以下所有步骤**：

1. **数据导入脚本**：在 `scripts/` 下新建或更新导入脚本
2. **约束创建**：在导入脚本中 `CREATE CONSTRAINT ... IF NOT EXISTS`
3. **搜索支持**：在 `neo4j_repository.py` 的 `search_entities` UNION 查询中添加新标签分支
4. **实体详情**：在 `neo4j_repository.py` 的 `get_entity` UNION 查询中添加新标签分支
5. **图谱检索**：在 `neo4j_repository.py` 的 `retrieve_graph_for_entity` 中添加专用查询条件
6. **节点ID解析**：在 `_node_id` 和 `_node_label` 中添加新标签的 ID/标签解析逻辑
7. **优先级注册**：在 `_node_priority` 中注册新类型的优先级
8. **问题分类**：在 `question_classifier.py` 中按需添加新问题类型的关键词匹配
9. **属性映射**：在 `qa_orchestrator.py` 的 `_build_llm_context` 中为新类型添加属性映射
10. **Cypher 模板**：在 `seed_data.py` 中添加新问题类型的 Cypher 查询模板
11. **Graph Retriever**：在 `graph_retriever.py` 的 `select_entities` 中注册新类型
12. **前端颜色**：在 `GraphCanvas.vue` 的 `colorByType` 和 `zoneKeyByType` 中注册新类型
13. **README 更新**：更新图谱节点、关系列表和统计数据

### 4.5 新增关系类型规则

1. 在 `neo4j_repository.py` 的 `_edge_priority` 中注册新关系优先级
2. 在 `graph_retriever.py` 的 `_edge_priority` 中注册新关系优先级
3. 在导入脚本中使用 `MERGE` 创建关系
4. 更新 README 图谱关系列表

---

## 5. 前端架构规则

### 5.1 目录结构

```
frontend/src/
├── api/
│   └── client.js      # axios 封装（所有 API 调用入口）
├── components/         # 可复用组件
│   ├── GraphCanvas.vue # 知识图谱可视化
│   └── EntityDrawer.vue # 实体详情抽屉
├── layouts/
│   └── MainLayout.vue  # 全局布局（侧边栏 + 顶栏 + 内容区）
├── router/
│   └── index.js        # 路由定义
├── stores/
│   ├── chat.js         # 知识问答 Pinia Store
│   └── rnd.js          # 研发协同 Pinia Store
└── views/
    ├── portal/         # 用户侧页面
    │   ├── HomeView.vue
    │   ├── ChatView.vue
    │   ├── RndWorkspaceView.vue
    │   └── HistoryView.vue
    └── admin/          # 管理后台页面
        ├── OverviewView.vue
        ├── LogsView.vue
        ├── PromptView.vue
        └── TemplateView.vue
```

### 5.2 命名约定

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 页面组件 | `{Feature}View.vue` | `ChatView.vue` |
| 可复用组件 | `{Feature}{Type}.vue` | `GraphCanvas.vue`、`EntityDrawer.vue` |
| Store | `use{Feature}Store` | `useChatStore` |
| API 方法 | `{verb}{Resource}` | `createSession`、`listMessages` |
| 路由 name | `kebab-case` | `admin-overview`、`chat` |

### 5.3 组件规则

- 使用 `<script setup>` + Composition API
- 状态优先使用 Pinia Store，组件本地状态用 `ref` / `computed`
- 组件内样式使用 `<style scoped>`
- Element Plus 组件按需导入（已配置自动导入）
- 表格统一使用 `el-table` + `border` + `stripe`
- 分页统一使用 `el-pagination` + `background` + `layout="total, sizes, prev, pager, next, jumper"`
- 弹窗/抽屉统一使用 `el-drawer` 或 `el-dialog`

### 5.4 API 层规则

- 所有 HTTP 请求统一通过 `api/client.js` 的 `api` 对象调用
- 禁止在组件中直接使用 `axios`
- 新增接口时，先在 `client.js` 中添加方法，再在 Store/组件中调用
- API 方法名与后端路由保持语义一致

### 5.5 路由规则

- 所有路由嵌套在 `MainLayout` 下
- 用户侧路由无前缀：`/chat`、`/rnd`、`/history`
- 管理后台路由统一 `/admin/` 前缀
- 新增页面时同步更新 `MainLayout.vue` 的侧边栏菜单和 `routeNameMap`

### 5.6 样式规则

- 全局风格遵循 RuoYi 框架审美：
  - 侧边栏：`#304156` 深色背景
  - 内容区：`#f3f3f4` 浅灰背景
  - 卡片：`shadow="hover"`、`border-radius: 4px`
  - 表头：`font-weight: 600`、`background-color: #f5f7fa`
  - 表格字号：`14px`、单元格 padding `10px 8px`
- 颜色变量使用 Element Plus 语义色（`primary`、`success`、`warning`、`danger`）
- 图谱节点颜色在 `GraphCanvas.vue` 的 `colorByType` 中统一管理

---

## 6. 数据导入脚本规则

### 6.1 脚本位置

- 正式导入脚本放在 `scripts/` 目录
- 脚本命名：`import_{功能}.py`
- 临时调试脚本禁止提交到仓库

### 6.2 导入脚本必须遵循

- 使用独立 Python 环境，不依赖项目 `_vendor`
- 增量导入脚本**不能清空已有数据**
- 全量重建脚本会先清空所有节点再重建
- 输出导入统计

### 6.3 数据源文件

- 正式数据在 `D:\工作\多智能体-宋\最新数据\0508汇总\`
- 补充数据在 `origin_data/`
- 数据源路径变更时同步更新脚本中的常量和 README

---

## 7. LLM 集成规则

### 7.1 MiniMax Client

- 统一通过 `MiniMaxClient` 类调用 LLM API
- 禁止在 Service 层直接使用 `httpx` 调用 LLM
- 所有 LLM 调用必须有 **fallback 逻辑**（本地兜底）
- Fallback 函数命名：`_fallback_{功能}` 或 `_{模块}_fallback`

### 7.2 结构化输出

- LLM 返回值必须通过 `_matches_expected_shape()` 校验
- 校验失败时使用本地 fallback 数据，不中断工作流
- 新增 Agent 时必须在 `seed_data.py` 中定义 `output_schema`

### 7.3 Prompt 管理

- Prompt 模板存储在 PostgreSQL `prompt_template` 表
- 种子 Prompt 在 `seed_data.py` 中定义
- 按 `scenario`（`knowledge_qa`、`rnd_workflow`）+ `agent_key` 组织
- 可通过管理后台在线编辑 Prompt

---

## 8. 研发协同工作流规则

### 8.1 Agent 编排

- Agent 按固定顺序执行（`AGENT_SEQUENCE`）：方剂生成 → 功效预测 → 风味预测 → 替代映射
- 每步生成一个 `WorkflowStepRun` 记录
- 每步可生成一个 `GraphSnapshot` 供前端展示
- 工作流在后台执行（`BackgroundTasks`），前端轮询状态

### 8.2 Agent 详细规范

本系统包含 5 个研发协同 Agent，规格依据《规则词》定义：

| Agent Key | 角色 | 核心职责 |
|-----------|------|---------|
| `master_control` | 药食同源智研系统主控Agent | 需求拆解、模块调度、逻辑校验、方案整合、合规校验 |
| `formula_generation` | 药食同源方剂生成专家 | 组方设计、君臣佐使配伍、剂量建模、方解撰写、合规校验 |
| `efficacy_prediction` | 药食同源功效预测专家 | 成分-功效建模、药理分析、人群分层（适用/不适宜/禁忌）、风险评估 |
| `flavor_prediction` | 药食同源风味预测专家 | 风味数据库应用、感官分析（味觉/嗅觉/口感）、协调性分析、消费者接受度 |
| `replacement_mapping` | 药食同源替代映射专家 | 功效等效性评估、多维度对比（功效/风味/成本/合规/工艺/供应链）、替代方案设计 |

#### 8.2.1 主控Agent (`master_control` / `master_control_final`)

- **Role**: 统筹全流程任务，按研发逻辑顺序调度子模块（方剂生成→功效预测→风味预测→替代映射），整合输出结构化完整研发方案
- **Constraints**: 
  - 严格基于用户需求分配任务，禁止超出需求范围的冗余输出
  - 所有子模块输出须符合中医药理论、药食同源国家标准与食品科学规范
  - 必须校验各模块数据一致性（方剂配伍与功效预测、风味预测与工艺适配的逻辑匹配）
  - 所有输出标注数据来源（如《中国药典》、GB标准、FlavorDB等）
- **Workflow**: 需求接收与拆解 → 任务调度与流转 → 逻辑校验与修正 → 方案整合与输出 → 需求迭代与优化
- **Output Schema**: `brief_summary`, `task_plan`, `consistency_checks`, `final_recommendation`, `next_actions`, `data_sources`

#### 8.2.2 方剂生成Agent (`formula_generation`)

- **Role**: 基于中医药经典名方、君臣佐使理论与药食同源目录，生成符合用户需求的药食同源方剂
- **Constraints**: 
  - 所有药材须来自《药食同源物品目录》（`food_homology='是'`）
  - 严格遵循君臣佐使配伍原则，符合经典名方配伍逻辑
  - 剂量区间须符合食品安全标准，标注成人每日推荐用量与最大安全用量
  - 须标注方剂的理论依据（经典名方来源、中医药理论支撑）
  - 禁止使用非药食同源、有毒性或超剂量的药材
- **Workflow**: 接收需求 → 组方设计（基于目标功效筛选药材+经典名方参考） → 剂量建模（安全有效剂量区间） → 方解撰写（配伍逻辑与各药作用） → 合规校验 → 结果输出
- **Output Schema**: `formulas`, `selection_rationale`, `fang_jie`, `classic_references`, `compliance_notes`, `risks`

#### 8.2.3 功效预测Agent (`efficacy_prediction`)

- **Role**: 基于方剂组方、成分-功效关联模型与中医药理论，预测核心功效、作用机制、适用人群与潜在风险
- **Constraints**: 
  - 功效预测须基于药理研究、中医药理论与临床应用数据
  - 须区分传统中医药功效与现代药理功效，标注依据来源
  - 须区分三类人群：适用人群、不适宜人群、禁忌人群
  - 禁止夸大功效，符合《保健食品注册与备案管理办法》等法规
- **Workflow**: 接收方剂 → 成分-功效分析（构建关联模型、量化功效强度） → 功效预测（中医药+现代药理+作用机制） → 人群与风险评估 → 结果输出
- **Output Schema**: `core_tcm_efficacy`, `core_modern_efficacy`, `mechanisms`, `target_population`, `avoid_population`, `contraindicated_population`, `risks`, `literature_basis`

#### 8.2.4 风味预测Agent (`flavor_prediction`)

- **Role**: 基于FlavorDB等风味数据库与食品感官科学，预测方剂风味特征，分析协调性并提供优化方案
- **Constraints**: 
  - 风味预测须基于FlavorDB、BungentDB等权威风味数据库的成分-风味标签
  - 须区分三维度：味觉（酸/甜/苦/咸/鲜）、嗅觉（香气类型）、口感
  - 须分析风味协调性，标注潜在风味缺陷
  - 禁止无依据的风味描述
- **Workflow**: 接收方剂 → 风味数据提取（FlavorDB/BungentDB风味标签量化） → 风味整合与预测（主导/辅助风味+协调性+缺陷） → 消费者接受度分析 → 优化方案输出（矫味成分/比例/辅料/工艺） → 结果输出
- **Output Schema**: `flavor_profile`（含 `taste`/`aroma`/`mouthfeel`）, `coordination_summary`, `defects`, `optimization_suggestions`, `consumer_acceptance`, `data_sources`

#### 8.2.5 替代映射Agent (`replacement_mapping`)

- **Role**: 基于功效、风味、成本、合规性等维度，为方剂药材提供可替代的药食同源品种，优化产品可及性与成本
- **Constraints**: 
  - 替代品种须来自药食同源目录
  - 替代须保障核心功效一致，标注功效等效性依据
  - 须对比替代前后的功效、风味、成本、工艺适配性差异
  - 禁止使用功效/安全性不可靠的替代品种
- **Workflow**: 接收方剂 → 替代筛选（功效等效品种+供应稳定/成本低/风味优优先） → 多维度对比（功效/风味/成本/合规/工艺/供应链） → 方案验证 → 结果输出
- **Output Schema**: `recommended_replacements`, `baseline_comparison`, `impact_summary`, `compliance_notes`, `applicable_scenarios`

### 8.3 新增 Agent 步骤

1. 在 `AGENT_SEQUENCE` 中添加新 Agent key
2. 在 `seed_data.py` 中定义对应的 PromptTemplate（含 `output_schema`）
3. 在 `rnd_workflow_orchestrator.py` 中实现 `_run_step` 的分支逻辑和 fallback
4. 在前端 `RndWorkspaceView.vue` 中处理新步骤的展示

### 8.4 Brief 结构

- Brief 由 `_build_brief()` 生成，包含结构化需求信息
- Brief 通过 `workflow_session.last_brief` 持久化
- 支持 `reuse_last_brief` 复用上次 Brief

### 8.5 待扩展模块

根据《规则词》定义，以下两个模块尚未实现：

- **工艺适配 (`process_adaptation`)**: 待补充
- **市场预测 (`market_prediction`)**: 待补充

---

## 9. 错误处理规则

### 9.1 后端

- 路由层：使用 `HTTPException` 返回标准 HTTP 错误码
  - 404：资源不存在
  - 422：参数校验失败（Pydantic 自动处理）
  - 500：服务端错误
- Service 层：使用 `ValueError` 表示业务错误，由路由层转换为 `HTTPException`
- Repository 层：不捕获异常，向上传播
- LLM 调用：所有 LLM 失败都走 fallback，不抛异常到路由层

### 9.2 前端

- API 调用统一 try-catch
- 错误提示使用 `ElMessage.error()`
- 加载状态使用 `loading` ref + `v-loading` 指令
- 禁止 `console.error` 残留在生产代码中

---

## 10. 环境与配置

### 10.1 环境变量

- 所有配置通过 `backend/.env` 管理
- 配置项在 `core/config.py` 的 `Settings` dataclass 中声明默认值
- 敏感信息（API Key）禁止硬编码，必须通过环境变量
- `.env` 文件不提交到版本控制

### 10.2 Python 依赖

- 项目使用 `backend/_vendor` 内置依赖（不依赖系统 pip install）
- 启动脚本通过 `PYTHONPATH` 引入 `_vendor`
- 新增依赖时同时更新 `_vendor` 和 `requirements.txt`

### 10.3 Node.js 依赖

- 前端依赖通过 `npm install` 安装到 `node_modules`
- 构建命令：`npm run build`（输出到 `dist/`）
- 开发命令：`npm run dev -- --host 0.0.0.0 --port 5173`

---

## 11. 构建与验证

### 11.1 后端验证

```powershell
python -m py_compile backend/app/services/{文件}.py
python -m py_compile backend/app/repositories/{文件}.py
python -m py_compile backend/app/db/{文件}.py
```

### 11.2 前端验证

```powershell
cd frontend ; npm run build
```

### 11.3 图谱验证

导入数据后执行验证查询：

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC
MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC
```

---

## 12. Git 提交规则

- 提交信息格式：`{类型}: {简要描述}`
- 类型：`feat`（新功能）、`fix`（修复）、`refactor`（重构）、`docs`（文档）、`chore`（杂项）
- 禁止提交：`.env`、`node_modules/`、`__pycache__/`、`*.pyc`、临时调试脚本
- 每次提交前确认后端 `py_compile` 和前端 `npm run build` 均通过

---

## 13. 关键文件索引

| 文件 | 作用 | 修改频率 |
|------|------|---------|
| `backend/app/api/routes.py` | 所有 HTTP 路由 | 高 |
| `backend/app/services/qa_orchestrator.py` | 知识问答编排 | 高 |
| `backend/app/services/rnd_workflow_orchestrator.py` | 研发工作流编排 | 高 |
| `backend/app/repositories/neo4j_repository.py` | 图谱查询与检索 | 高 |
| `backend/app/repositories/postgres_repository.py` | PostgreSQL CRUD | 中 |
| `backend/app/db/models.py` | ORM 模型定义 | 低 |
| `backend/app/db/seed_data.py` | 种子数据 | 中 |
| `backend/app/core/config.py` | 配置 | 低 |
| `backend/app/services/question_classifier.py` | 问题类型分类 | 中 |
| `backend/app/services/graph_retriever.py` | 图谱检索与实体选择 | 中 |
| `backend/app/services/entity_resolver.py` | 实体识别与消歧 | 中 |
| `backend/app/services/minimax_client.py` | LLM 调用封装 | 中 |
| `frontend/src/api/client.js` | API 调用封装 | 中 |
| `frontend/src/stores/chat.js` | 知识问答 Store | 中 |
| `frontend/src/stores/rnd.js` | 研发协同 Store | 中 |
| `frontend/src/components/GraphCanvas.vue` | 图谱可视化 | 中 |
| `frontend/src/layouts/MainLayout.vue` | 全局布局 | 低 |
| `scripts/import_neo4j_graph_v3.py` | v3 图谱导入 | 低 |
| `README.md` | 项目说明 | 中 |

---

## 14. 新增功能开发 Checklist

新增一个完整功能模块时，按以下清单逐项确认：

- [ ] **后端 Model**：如需新表，在 `models.py` 添加 Model
- [ ] **后端 Schema**：在 `schemas/` 添加 Pydantic 请求/响应 Schema
- [ ] **后端 Repository**：在 `postgres_repository.py` 或 `neo4j_repository.py` 添加数据访问方法
- [ ] **后端 Service**：在 `services/` 添加业务编排逻辑（含 fallback）
- [ ] **后端 Route**：在 `routes.py` 添加 API 端点
- [ ] **种子数据**：如需 Prompt/Cypher 模板，更新 `seed_data.py`
- [ ] **图谱建模**：如涉及新节点/关系类型，遵循 4.4/4.5 节完整步骤
- [ ] **前端 API**：在 `client.js` 添加新接口方法
- [ ] **前端 Store**：如需全局状态，在 `stores/` 添加或更新 Store
- [ ] **前端页面**：在 `views/` 添加页面组件
- [ ] **前端路由**：在 `router/index.js` 注册路由
- [ ] **前端布局**：在 `MainLayout.vue` 添加侧边栏菜单项
- [ ] **数据导入脚本**：如需导入新数据，在 `scripts/` 添加脚本
- [ ] **README 更新**：更新相关说明
- [ ] **编译验证**：`py_compile` + `npm run build` 均通过
