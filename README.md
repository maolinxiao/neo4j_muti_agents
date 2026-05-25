# 药食同源多智能体研发协同平台

本项目是一个基于知识图谱的药食同源多智能体平台，当前包含两类核心工作台：

- `知识问答工作台`
  基于 Neo4j 图谱做实体识别、证据检索、图谱问答和证据子图展示。
- `研发协同工作台`
  面向药食同源产品研发，围绕需求解析、方剂生成、功效预测、风味预测、替代映射进行顺序编排。

当前前端基于 `Vue 3 + Element Plus + Pinia`，后端基于 `FastAPI + SQLAlchemy`，业务数据存储在 `PostgreSQL`，知识图谱存储在 `Neo4j`，并接入 `MiniMax` 做结构化生成。

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
│  └─ import_neo4j_graph_v3.py  # v3 图谱导入脚本
├─ requirements.txt
└─ README.md
```

## 当前能力

### 1. 知识问答

- 基于图谱的实体识别与问题类型识别
- 问答结果与证据子图联动展示
- 参考来源详情弹窗
- Prompt / Cypher 模板管理
- MiniMax 失败时自动降级到本地图谱回答

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

当前正式图谱（v3）采用以下数据源：

- `D:\工作\多智能体-宋\最新数据\0508汇总\neo4j_graph_v3\` 目录下所有 CSV

### 图谱节点

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
| `NatureFlavor` | `nature_flavor_name` | 中医性味（辛、甘、苦、温、寒等） |
| `Meridian` | `meridian_name` | 归经 |

说明：Flavor 表示食品/感官风味，NatureFlavor 表示中医性味，二者不可合并。

### 图谱关系

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

## 当前正式导入结果

最近一次导入后的图谱统计：

| 节点/关系 | 数量 |
|-----------|------|
| Herb | 659 |
| Compound | 1613 |
| Effect | 49 |
| Flavor | 9 |
| Formula | 100 |
| EffectCategory | 21 |
| Symptom | 1260 |
| Taboo | 387 |
| Source | 30 |
| NatureFlavor | 28 |
| Meridian | 23 |
| CONTAINS | 4034 |
| HAS_EFFECT (Herb) | 965 |
| HAS_FLAVOR | 520 |
| CAN_REPLACE | ~378 |
| 其他关系 | ~16,000+ |
| **总节点** | **~4,179** |
| **总关系** | **~22,830** |

注：`food_homology = '是'` 的药材约 114 种，便于研发场景检索与候选召回。

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
password: 1234
```

### 4. Neo4j

默认连接配置：

```text
uri: neo4j://localhost:7687
username: neo4j
password: 3217858658
```

### 5. MiniMax

后端通过环境变量读取：

- `MINIMAX_API_BASE`
- `MINIMAX_API_KEY`
- `MINIMAX_MODEL`

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
NEO4J_PASSWORD=3217858658
MINIMAX_API_BASE=https://api.minimaxi.com/v1
MINIMAX_API_KEY=你的Key
MINIMAX_MODEL=MiniMax-M2.7
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

## 2026-05 增量升级说明

### 增量数据导入

本次新增 `scripts/import_agent_project_data.py`，用于把 `D:\工作\多智能体-宋\最新数据\药食同源agent项目` 中的新数据增量合并到 Neo4j，不清空现有图谱。

```powershell
python .\scripts\import_agent_project_data.py --dry-run
python .\scripts\import_agent_project_data.py
```

可选参数：

- `--data-root`：指定数据根目录。
- `--limit`：限制每类数据处理行数，便于抽样验证。
- `--dry-run`：只解析并输出统计，不写入 Neo4j。

新增节点标签：

| 标签 | 唯一键 | 说明 |
|------|--------|------|
| `Product` | `product_id` | 药食同源产品/成药商品 |
| `ConsumerProfile` | `profile_id` | 产品级消费者聚合画像 |
| `ConsumerSegment` | `segment_key` | 消费者人群/场景/功效分组 |
| `ConstitutionType` | `constitution_type_name` | 中医体质类型 |
| `ConstitutionQuestion` | `question_code` | 体质评估题目 |

新增关系：

| 关系 | 起点 → 终点 | 说明 |
|------|-------------|------|
| `USES_HERB` | Product → Herb | 产品使用的药食同源原料 |
| `HAS_CONSUMER_PROFILE` | Product → ConsumerProfile | 产品对应消费者聚合画像 |
| `MATCHES_CONSUMER_SEGMENT` | ConsumerProfile → ConsumerSegment | 画像匹配的人群/场景分组 |
| `TOP_PRODUCT` | ConsumerSegment → Product | 分组下推荐/高频产品 |
| `PREFERS_FLAVOR` | ConsumerProfile → Flavor | 消费者偏好风味 |
| `DISLIKES_FLAVOR` | ConsumerProfile → Flavor | 消费者排斥风味 |
| `ASSESSES_CONSTITUTION` | ConstitutionQuestion → ConstitutionType | 体质题目指向体质类型 |

消费者评论只导入画像、分组、风味偏好、好评率、评论量等聚合字段，不导入用户名和评论原文。

### 知识问答升级

新增问题类型：

- `constitution_recommendation`：体质/症状导向的药食同源方剂推荐。
- `product_recommendation`：消费者画像/成药产品推荐。

回答规则集中放在 `backend/app/prompts/knowledge_qa_answer_rules.md`，由 `QAOrchestrator` 拼入系统提示词。推荐类回答按“核心结论、用户画像/体质判断依据、推荐方案、图谱证据、风险与禁忌、证据边界、追问建议”组织；体质推荐不做医学诊断，产品推荐优先使用人群、功效需求、剂型、风味偏好、价格敏感度、好评率和评论量等图谱证据。

### 登录与权限

后端新增真实登录：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

默认管理员由 `backend/.env` 配置：

```env
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123456
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

重建 v3 知识图谱：

```powershell
python .\scripts\import_neo4j_graph_v3.py
```

脚本执行内容：

1. 清空业务图谱
2. 重建所有节点的唯一约束
3. 导入 11 种节点类型
4. 导入 19 种关系类型
5. 导入 consumer-aware 替代结果
6. 输出导入统计

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

### 3. MiniMax 返回了错误结构

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
