# 药食同源多智能体研发协同平台

本项目是一个基于知识图谱的药食同源多智能体平台，当前包含两类核心工作台：

- `知识问答工作台`
  基于 Neo4j 图谱做实体识别、证据检索、图谱问答和证据子图展示。
- `研发协同工作台`
  面向药食同源产品研发，围绕需求解析、方剂生成、功效预测、风味预测、替代映射进行顺序编排。

当前前端基于 `Vue 3 + Element Plus + Pinia`，后端基于 `FastAPI + SQLAlchemy`，业务数据存储在 `PostgreSQL`，知识图谱存储在 `Neo4j`，并接入 `DeepSeek` 做结构化生成。

## 项目结构

```text
neo4j_muti_agents/
├─ backend/                     # FastAPI 后端
│  ├─ app/
│  │  ├─ api/                   # 路由
│  │  ├─ core/                  # 配置
│  │  ├─ db/                    # 模型、初始化、种子数据
│  │  ├─ repositories/          # PostgreSQL / Neo4j 访问层
│  │  ├─ schemas/               # Pydantic Schema
│  │  └─ services/              # QA、R&D 工作流、LLM 编排
│  ├─ scripts/
│  │  ├─ run_backend.ps1
│  │  └─ stop_backend.ps1
│  ├─ _vendor/                  # 项目内置 Python 依赖
│  └─ .env.example
├─ frontend/                    # Vue 前端
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ layouts/
│  │  ├─ router/
│  │  ├─ stores/
│  │  └─ views/
│  ├─ scripts/
│  │  ├─ run_frontend.ps1
│  │  └─ stop_frontend.ps1
│  └─ package.json
├─ origin_data/                 # 原始数据与补充目录
├─ scripts/
│  └─ import_agent_kg_0604.py   # 0604 KB1-KB8 + CDB1 全量重建脚本
├─ requirements.txt
└─ README.md
```

## 当前能力

### 1. 知识问答

- 基于图谱的实体识别与问题类型识别
- 问答结果与证据子图联动展示
- 参考来源详情弹窗
- Prompt / Cypher 模板管理
- DeepSeek 失败时自动降级到本地图谱回答

### 2. 研发协同

- 双工作台首页切换
- 研发需求结构化处理
- 五类 Agent 顺序编排
  - `master_control`
  - `formula_generation`
  - `efficacy_prediction`
  - `flavor_prediction`
  - `replacement_mapping`
- 工作流会话、运行记录、步骤日志持久化
- 每步图谱快照与右侧证据面板联动
- 管理后台查看工作流日志、Prompt、数据概览

## 图谱建模说明

当前正式图谱按 2026-06-04 最新数据全量重建，数据源为：

- `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\药食同源Agent_8类知识库-0531`
- `D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目\0512-消费者_体质`

新图谱以 KB1-KB8 与 CDB1 消费者画像/评论偏好库为权威源，不导入旧 `Compound` / 成分网络；旧 `neo4j_graph_v3` 和 dump 仅作为备份参考。

### 8 类知识库

| 编号 | 知识库 | 图谱用途 |
|------|--------|----------|
| KB1 | 药食同源原料合法性库 | 原料合法性、毒性、孕妇禁忌、使用注意 |
| KB2 | 功效-病症-性味归经库 | 功效、病症、性味、归经、禁忌 |
| KB3 | 风味评价库 | 苦味/涩感/药味风险、香气、风味接受度 |
| KB4 | 单味药替代评分库 | `CAN_REPLACE` 单味药替代评分 |
| KB5 | 名方/方剂知识库 | 方剂、来源、组成、君臣佐使、功效、主治 |
| KB6 | 产品与市场库 | 产品、品牌、剂型、卖点、场景、竞品功效标签 |
| KB7 | 食品标准合规库 | 药食同源目录、GB2760、GB7718、宣传边界、禁用慎用表述 |
| KB8 | 9 种体质辨识与食养规则库 | 体质问卷、评分规则、食养方向、慎用原料 |
| CDB1 | 消费者画像与评论偏好库 | 产品、消费者画像、人群场景功效分组、京东/淘宝评论、风味偏好、剂型偏好、投诉点 |

合规字段说明：

- `food_homology` 只表示原料是否属于食药物质目录，不能单独代表全部食品使用资格。
- 条件使用的新食品原料和保健食品原料分别通过 `ordinary_food_*`、`health_food_*` 与关联 `ComplianceRule` 表达。
- 人参仍保留 `food_homology=否`；5 年及以下人工种植人参可按公告条件进入普通食品路径，5 年以上不得据此直接作为普通食品原料；保健食品路径需单独核验注册备案与复配要求。

### 图谱节点

| 标签 | 唯一键 | 说明 |
|------|--------|------|
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

说明：`Flavor` 表示食品/感官风味，`NatureFlavor` 表示中医性味，二者不可合并。

### 图谱关系

| 关系 | 起点 → 终点 | 说明 |
|------|-------------|------|
| `HAS_EFFECT` | Herb/Formula → Effect | 原料或方剂功效 |
| `BELONGS_TO_EFFECT_CATEGORY` | Herb → EffectCategory | 原料功效分类 |
| `TREATS` | Herb → Symptom | 原料主治/适配病症 |
| `TARGETS_SYMPTOM` | Formula → Symptom | 方剂主治/适配病症 |
| `HAS_NATURE_FLAVOR` | Herb → NatureFlavor | 中医性味 |
| `ENTERS_MERIDIAN` | Herb → Meridian | 归经 |
| `HAS_FLAVOR` | Herb → Flavor | 食品感官风味 |
| `HAS_TABOO` | Herb/Formula → Taboo | 禁忌或慎用 |
| `CAN_REPLACE` | Herb → Herb | 单味药替代评分；含 KB4 Top10、`consumer_aware` 消费者感知分、禁忌排除候选 |
| `INCOMPATIBLE_WITH` | Herb → Herb | 十八反/十九畏配伍禁忌（双向） |
| `IN_FORMULA` | Herb → Formula | 方剂组成，属性含 `role` |
| `MONARCH_HERB` / `MINISTER_HERB` / `ASSISTANT_HERB` / `GUIDE_HERB` | Formula → Herb | 君臣佐使 |
| `FROM_SOURCE` | Formula → Source | 方剂出处 |
| `USES_HERB` | Product → Herb | 产品配料中的原料；KB6 配料缺失时按商品名匹配已知 Herb，并在边属性记录 `match_source` |
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

### 全量重建导入

```powershell
python .\scripts\import_agent_kg_0604.py --dry-run --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
python .\scripts\import_agent_kg_0604.py --clear --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
```

`--dry-run` 只解析 KB1-KB8 与 CDB1 并输出计划统计，不连接 Neo4j。正式 `--clear` 导入会先把旧 Neo4j 图谱导出为 JSON 备份到 `neo4j_backups/`，再清空并重建；如确需跳过备份，可显式传入 `--skip-backup`。

回退示例：

```powershell
python .\scripts\restore_neo4j_backup.py --backup neo4j_backups\neo4j_backup_before_0604_rebuild_YYYYMMDD_HHMMSS.json --yes
```

本次优化 additionally 导入：KB4 十八反十九畏、评分/风味规则、禁忌排除候选；KB7 分拆合规文件；`consumer_aware_substitute_results.csv`；`0524/meandqi` 方剂补充。

### 0604 dry-run 计划统计

以下统计来自 2026-06-25 11:19 对 6-4 KB1-KB8 + CDB1 与增强补充源执行 `--dry-run` 的解析结果，作为正式导入后的验收基线。CDB1 同时服务企业端（人群定位、风味/剂型、市场差异化）和个人端（产品适配、口味偏好、风险边界辅助判断）。

| 节点类型 | 计划数量 | 节点类型 | 计划数量 |
|----------|----------|----------|----------|
| ConsumerReview | 63,522 | Symptom | 11,125 |
| Formula | 3,155 | ConsumerSegment | 3,033 |
| Source | 2,063 | Effect | 1,570 |
| Herb | 865 | Taboo | 419 |
| ComplianceRule | 226 | Product | 192 |
| ConsumerProfile | 106 | EffectCategory | 51 |
| RiskExpression | 46 | Flavor | 34 |
| ConstitutionQuestion | 30 | NatureFlavor | 22 |
| Meridian | 14 | ConstitutionType | 9 |

| 关系类型 | 计划数量 | 关系类型 | 计划数量 |
|----------|----------|----------|----------|
| REVIEWS_PRODUCT | 63,522 | MENTIONS_EFFECT | 27,002 |
| BELONGS_TO_CONSUMER_SEGMENT | 25,737 | IN_FORMULA | 20,664 |
| MENTIONS_FLAVOR | 19,904 | TARGETS_SYMPTOM | 11,519 |
| CAN_REPLACE | 9,338 | TREATS | 4,620 |
| FROM_SOURCE | 3,760 | HAS_EFFECT | 3,328 |
| MATCHES_CONSUMER_SEGMENT | 2,817 | TOP_PRODUCT | 2,817 |
| SEGMENT_PREFERS_FLAVOR | 2,497 | HAS_NATURE_FLAVOR | 1,505 |
| ENTERS_MERIDIAN | 1,383 | HAS_FLAVOR | 988 |
| CLAIMS_EFFECT | 893 | BELONGS_TO_EFFECT_CATEGORY | 892 |
| ASSISTANT_HERB | 690 | HAS_TABOO | 690 |
| MINISTER_HERB | 669 | MONARCH_HERB | 431 |
| USES_HERB | 431 | DISLIKES_FLAVOR | 334 |
| PREFERS_FLAVOR | 318 | GUIDE_HERB | 144 |
| LISTED_IN_COMPLIANCE_RULE | 110 | HAS_CONSUMER_PROFILE | 106 |
| INCOMPATIBLE_WITH | 76 | RECOMMENDS_HERB | 60 |
| DERIVED_FROM_RULE | 46 | CAUTIONS_HERB | 33 |
| ASSESSES_CONSTITUTION | 30 |  |  |

计划总量：86,482 个节点、207,354 条关系；`Compound` / 成分网络计划导入数量为 0。

## 环境准备

### 1. Python

推荐使用本机 Python 运行后端入口。

项目依赖有两种方式：

- 直接使用 `requirements.txt` 安装到你的 Python 环境
- 使用项目自带的 `backend/_vendor` 依赖目录

当前后端启动脚本采用第二种方式，不依赖你先手动 `pip install`。

### 2. Node.js

前端脚本默认会把 `E:\nodejs` 加到 `PATH`，因此本机建议存在：

```text
E:\nodejs
```

### 3. PostgreSQL

默认连接配置：

```text
host: localhost
port: 5432
database: postgres
username: postgres
password: <your-postgres-password>
```

### 4. Neo4j

默认连接配置：

```text
uri: neo4j://localhost:7687
username: neo4j
password: <your-neo4j-password>
```

### 5. DeepSeek

后端通过环境变量读取：

- `DEEPSEEK_API_BASE`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`

## 配置文件

首次使用时先复制后端环境文件：

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

然后检查 `backend\.env`：

```env
POSTGRES_DSN=postgresql+psycopg://postgres:1234@localhost:5432/postgres
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_API_KEY=你的Key
DEEPSEEK_MODEL=deepseek-v4-pro
```

## 启动方式

### 方式一：使用脚本启动

后端：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\run_backend.ps1
```

前端：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\scripts\run_frontend.ps1
```

说明：

- 某些 Windows 环境默认禁用 `.ps1` 执行，需要加 `-ExecutionPolicy Bypass`。
- 后端脚本内部会自动设置 `PYTHONPATH=backend\_vendor;backend`。
- 前端脚本会默认使用 `npm run dev -- --host 0.0.0.0 --port 5173`。

### 方式二：手动启动

后端：

```powershell
$env:PYTHONPATH="D:\python_workspace\neo4j_muti_agents\backend\_vendor;D:\python_workspace\neo4j_muti_agents\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端：

```powershell
Set-Location .\frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## 访问地址

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/api/health`

## 停止服务

后端：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\stop_backend.ps1
```

前端：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\scripts\stop_frontend.ps1
```

## 2026-06 全量重建说明

### 0604 数据导入

`scripts/import_agent_kg_0604.py` 用于把 6-4 最新 KB1-KB8 与 CDB1 消费者画像/评论偏好数据全量重建到 Neo4j。该脚本不导入旧 `Compound` / 成分网络。

```powershell
python .\scripts\import_agent_kg_0604.py --dry-run --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
python .\scripts\import_agent_kg_0604.py --clear --data-root "D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
```

可选参数：

- `--data-root`：指定 6-4 数据根目录。
- `--dry-run`：只解析并输出统计，不连接 Neo4j。
- `--clear`：正式导入前清空目标 Neo4j。
- `--backup-dir`：正式 `--clear` 前旧图谱 JSON 备份目录。
- `--skip-backup`：显式跳过旧图谱备份。

业务规则来自：

- `思考逻辑流程.html`
- `药食同源Agent_企业个人分流_名方方剂知识库流程图.html`

关键约束：KB5 名方/方剂知识库单独保留；KB4 只存单味药替代评分，方剂药食同源化时动态组合 KB5 + KB1 + KB2 + KB3 + KB4 + KB7。

### 知识问答升级

重点问题类型：

- `constitution_recommendation`：体质/症状导向的个人端食养推荐。
- `product_recommendation`：产品、风味、市场、剂型、合规类企业端问答。

回答规则集中放在 `backend/app/prompts/knowledge_qa_answer_rules.md`，由 `QAOrchestrator` 拼入系统提示词。推荐类回答按“核心结论、体质/产品判断依据、推荐方案、图谱证据、风险与禁忌、证据边界、追问建议”组织；体质推荐不做医学诊断，产品推荐优先使用产品、原料、功效、风味、市场和 KB7 合规证据。

问答业务路由以 `backend/app/prompts/qa_route_rules.json` 为机器可读主规则，`backend/app/prompts/qa_reasoning_flow.md` 维护可展示的五步过程摘要，`backend/app/prompts/knowledge_qa_answer_rules.md` 维护安全边界、回答风格、禁止项和评分展示规则。企业端覆盖产品研发、方剂食品化、单味替代、风味剂型、市场、合规；个人端覆盖体质辨识、食养推荐、产品适配、成品选购和风险边界。可用 `python scripts\validate_qa_routing.py` 回归校验典型问题的 `qa_route/question_type/audience`。

产品研发类回答会联查 KB5 名方与 KB4 单味替代关系，并通过 `graph_grounded` 通道按小标题直接流式输出，不等待大模型改写图谱事实。系统优先展示与核心原料存在直接图谱关系的名方及出处；没有直接关系时，只能标注为按功效、人群和风味筛选的“参考原型”。最终配方相对原方逐味归入“保留、替换、新增、删除”，其中“替换”必须有 `CAN_REPLACE` 关系；KB4 原始分与系统综合可信度按 100 分制分列，均表示研发证据强度，不表示临床有效率。

正式回答和“图谱检索与证据整理摘要”统一使用业务判断与行动建议表达。待验证项写成核验原料身份、补充原方剂量、开展感官小试、目标人群验证或专业复核，不向用户展示“图谱未提供”“知识库尚不支持”“知识库未提供”“未命中”等系统视角措辞。

### 登录与权限

后端新增真实登录：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

默认管理员由 `backend/.env` 配置：

```env
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<change-me>
AUTH_SESSION_TTL_HOURS=24
```

除 `/api/health` 和 `/api/auth/*` 外，主要业务接口均需要 Bearer Token。前端新增登录页、Pinia auth store、axios token 拦截器、路由守卫和退出登录。

### Remotion 登录背景

登录页背景视频由 `frontend/remotion/` 下的 Remotion composition 生成，产物放在：

- `frontend/public/login-bg.mp4`
- `frontend/public/login-bg-still.png`
- `frontend/public/login-bg-poster.svg`

常用命令：

```powershell
cd frontend
npm run render:login-still
npm run render:login-bg
npm run build
```

如果你是在前台直接运行，也可以使用：

```powershell
Ctrl + C
```

## 数据导入

重建 0604 KB1-KB8 + CDB1 知识图谱：

```powershell
python .\scripts\import_agent_kg_0604.py --dry-run
python .\scripts\import_agent_kg_0604.py --clear
```

脚本执行内容：

1. 解析 KB1-KB8 与 CDB1 并输出计划统计
2. 正式导入时先备份旧图谱
3. 清空业务图谱
4. 重建所有节点唯一约束
5. 导入 18 种节点类型和 KB1-KB8/CDB1 关系
6. 确认不导入 `Compound` / 成分网络

## 研发工作流接口

当前新增接口：

- `POST /api/rnd/sessions`
- `GET /api/rnd/sessions`
- `POST /api/rnd/sessions/{session_id}/runs`
- `GET /api/rnd/runs/{run_id}`
- `GET /api/rnd/runs/{run_id}/steps/{step_id}`

研发结果对象核心字段：

- `brief`
- `final_report`
- `steps`
- `summary_metrics`
- `related_graph_snapshots`

## 管理后台

当前后台支持：

- 数据概览
- Chat 日志
- Workflow 日志
- Prompt 模板管理
- Cypher 模板管理

Prompt 模板已按：

- `knowledge_qa`
- `rnd_workflow`

两个场景拆分，并支持 `agent_key` 与 `output_schema`。

## 常见问题

### 1. PowerShell 提示脚本被禁用

使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\run_backend.ps1
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\scripts\run_frontend.ps1
```

### 2. 前端启动时报 npm cache 权限错误

如果 `E:\nodejs\node_cache` 没有写权限，可以先切到项目本地 cache：

```powershell
Set-Location .\frontend
npm config set cache ..\.npm-cache --location=user
npm run dev -- --host 0.0.0.0 --port 5173
```

### 3. DeepSeek 返回了错误结构

后端已经加入结构化输出兜底：

- 如果 LLM 没按当前 Agent schema 返回
- 会自动回退到本地结构化 fallback
- 不会中断整条研发工作流

### 4. 替代映射结果为空

这通常不是错误，而是当前候选药材在正式 `CAN_REPLACE` 替代结果中没有对应边。此时工作流仍会继续，只是 `replacement_mapping` 模块返回空推荐。

## 常用命令速查

启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\run_backend.ps1
```

停止后端：

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\stop_backend.ps1
```

启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\scripts\run_frontend.ps1
```

停止前端：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\scripts\stop_frontend.ps1
```
