# LangGraph 研发协同迁移实施计划 v2.2 附录：执行环境改为「服务器侧隔离暂存树」

> 本附录是 v2.1 的**增量修订**（v2.1 正文保持有效，冲突处以本附录为准）。
> 缘起：用户指示「LangGraph 直接在服务器上做，不要在本地搞」。

## 1. 变更结论

| 维度 | v2.1 | **v2.2（本附录）** |
|---|---|---|
| P1 实现自检环境 | 本地开发机 + 本地影子库 `neo4j_agents_parity` | **服务器侧隔离暂存树** `/www/wwwroot/neo4j-migrate/` + 独立库 `neo4j_agents_migrate` |
| P2 隔离真实运行环境 | 本地装 Neo4j 5.26 + 生产 dump 副本（A7） | **服务器暂存树直接跑**（真实 Neo4j 只读 + 真实 DeepSeek + staging 库）；本地不再需要 Neo4j，A7 降级为可选 |
| 本地开发机职责 | 代码 + 运行 + 验证 | **仅**代码编写与语法检查（不承担运行/验证） |
| 生产树/库/nginx | 不碰（A1–A8） | **不变，仍不碰（A1–A8）** |
| 契约冻结、默认 legacy、回滚 R1–R3、幂等与崩溃语义、Checkpointer 独立 schema、脱敏/留存/日志要求 | — | **全部不变** |

## 2. 服务器侧环境布局

```
/www/wwwroot/neo4j-migrate/            # 新增暂存树（与生产树完全分离）
├── backend/                            # 基线 = 复制当前生产 backend，再叠加本次改动
├── venv/                               # 独立虚拟环境（Python 3.11）
├── logs/                               # 暂存运行日志
├── .env                                # 独立配置（0600）
└── run_staging.sh                      # 启动脚本：uvicorn 监听 127.0.0.1:8010
```

- **PostgreSQL**：新建独立库 `neo4j_agents_migrate`（同实例、**独立 database**）；库内由 staging 应用 `initialize_database()` 自建业务表，并另建 `langgraph` schema（`run_engine`/`run_lock` + 4 张 checkpoint 表）。**生产库 `neo4j_agents` 与其 schema 一律不动。**
- **Neo4j**：复用生产实例 `bolt://127.0.0.1:7687`，**只读使用**（本迁移不写图谱；数据导入功能不在范围内）。
- **端口**：`127.0.0.1:8010`，不开放公网、**不改 nginx**。
- **依赖**：只装进 `/www/wwwroot/neo4j-migrate/venv`；生产 venv（`/www/server/pyporject_evn/neo4j-agents-backend`）的安装仍属审批点 A2。
- **资源纪律**：暂存进程按需启停（测试结束即停）；启动前检查 `free -m` 与 PG 连接数；不与生产后端争抢 8000 端口。

## 3. 允许 / 禁止清单（对全体团队成员生效）

**允许（暂存域）**
1. 创建/修改 `/www/wwwroot/neo4j-migrate/**` 下的任何文件；
2. 创建独立 venv 并安装 3 个 `==` 固定依赖（langgraph / langgraph-checkpoint-postgres / psycopg-pool）；
3. 创建并使用 `neo4j_agents_migrate` 库（含其中的 `langgraph` schema）；
4. 启动/停止 8010 上的暂存进程；
5. **只读**查询生产 Neo4j 与生产 PG（用于基线核对与 T1–T4 实体绑定）。

**禁止（生产域，仍需逐项审批 A1–A8）**
1. 修改 `/www/wwwroot/neo4j-agents/**` 任何文件；
2. 重启/停止面板 Python 项目 `neo4j-agents-backend`；
3. 修改 nginx 配置或站点；
4. 写入生产库 `neo4j_agents` 或生产 `langgraph` schema；
5. 修改生产 venv；
6. 执行 `git add/commit/push`（由 captain 统一处理）；
7. 关闭/重启 PostgreSQL、Neo4j 服务。

## 4. 代码来源与同步（为何代码仍在仓库中编写）

- 服务器**没有 git 源**：按 `AGENTS.md` §12.5，`frontend/src` 与版本管理只存在于**本地仓库 + GitHub**；若只在服务器上改代码，将失去版本管理与审查轨迹（无法回溯、无法审阅 diff）。
- 因此采用**仓库为唯一版本来源 + 服务器暂存树为执行环境**：
  1. 在仓库中编写/修改代码（本步骤不依赖本地 PG/Neo4j，不运行任何业务逻辑）；
  2. 通过 **staging 助手**把改动文件同步到 `/www/wwwroot/neo4j-migrate/backend/`（逐文件 sha256 校验 MATCH）；
  3. 在暂存树 venv 中执行全部验证（P1/P2）。
- **本地不承担任何运行/验证职责**：本地 PG 17.9 与本地 Neo4j（未安装）不参与；本地只做"写文件 + `py_compile`"。
- **staging 助手**：`stg_server.py`（未跟踪；**不得含明文凭据**——优先读环境变量 `STG_SSH_HOST/USER/PASSWORD`，回退读取既有未跟踪文件 `deploy_t2_upload.py` 的常量）；
  内置**写路径守卫**：任何以 `/www/wwwroot/neo4j-agents` 开头的目标路径一律拒绝，并记录拒绝日志。

## 5. P1 / P2 的调整

- **P1（Mock 等价 + CFG/FB/FI-1..4）**：在暂存树 venv 中运行 `scripts/accept_rnd_engine_parity.py`；影子库参数改为 `--db-url postgresql+psycopg://postgres@127.0.0.1:5432/neo4j_agents_migrate`（库由脚本自建/重建）。
- **P2（隔离真实运行）**：把暂存后端跑在 `127.0.0.1:8010`（真实 DeepSeek key + 真实 Neo4j 只读 + staging 库），对同一 brief 分别以 legacy / langgraph 各跑一轮，按 v2.1 §D-2/§D-3 口径比对。
- **A7（拉取生产图谱 dump 副本）**：**降级为可选**（本地已无需 Neo4j）；如仍要留档可另行批准。
- T1–T4 灰度用例的实体绑定与预期结果**不变**（v2.1 §E.4）。

## 6. 风险与补偿

| 风险 | 补偿措施 |
|---|---|
| 误改生产树或生产库（同一台机器） | 助手写路径守卫；成员提示词禁止清单；每次同步后核对生产侧行数与校验和；生产树目录 mtime 监控 |
| 2C/8G 资源被暂存进程挤占 | 暂存进程按需启停；仅监听 127.0.0.1:8010；启动前查内存与 PG 连接数 |
| 暂存库与生产库同实例 | 独立 database + 独立 schema；所有 DDL 仅作用于 staging 库 |
| 生产机直接开发的发布风险 | 发布仍走 A4：备份 → 覆盖生产树 → 面板脚本重启 → R1/R2 回滚 |
| 依赖装错环境 | 只装 staging venv；生产 venv 安装仍为 A2 |
| 代码只存在于服务器而丢失 | 仓库为唯一版本来源，改动先落仓库再同步；captain 统一提交 |

## 7. 对已批准 DAG 的影响

| 任务 | 影响 |
|---|---|
| t1 计划副本校对 | 不变（仍校对本 v2.1 正文副本） |
| t2 引擎实现 + 验收工具 | 描述更新：仓库编写 → staging 同步（sha256）→ 暂存树自检 |
| t3 隔离验收 | 执行环境改为服务器暂存树；影子库改为 `neo4j_agents_migrate`（契约同步修订） |
| t4 独立审查 | 审查证据改为服务器暂存树运行记录（仍只读） |
| t5 文档与手册 | 按「仓库 → 服务器暂存树 → 生产发布」三段式改写 |

## 8. 本附录不改变的内容

契约冻结（前端、`/api/rnd/*`、业务库字段、历史数据、Prompt 配置、Fallback、图谱逻辑）· 默认引擎 legacy · Run 创建与引擎 pin 同事务且失败不降级 · 缺 pin 判定规则 · 租约锁禁止自动接管 · 节点重放幂等与四个崩溃窗口 · Checkpointer 独立 schema 与"建表仅 CLI、启动只校验" · 生产失败即 failed 且不承诺自动续跑 · 回滚 R1–R3（不含 DROP SCHEMA）· 禁用明文凭据的新脚本 · 版本固定 · 数据脱敏 / 配置回滚 / 历史留存 / 日志脱敏 · 审批点 A0–A8（A7 可选）。

## 9. 勘误与决策（对 v2.1 的标签口径，v2.1 正文保持冻结不改）

t1 校对发现 4 处标签口径问题，本附录定案如下（**实现与验收以下述口径为准**）：

| # | v2.1 原文 | 定案 |
|---|---|---|
| ① | §B.1 标题"新增（13）"，表内实为 **14** 行 | **以表为准：新增 14 个路径**（8 个 `rnd_graph` 模块 + `rnd_engine.py` + `db/langgraph_schema.py` + `scripts/init_langgraph_checkpoint.py` + `scripts/rnd_engine_switch.py` + `scripts/accept_rnd_engine_parity.py` + `scripts/accept_rnd_api_regression.py`）。t2 按 14 个路径实现 |
| ② | §B.2 标题"修改（7"，表内 8 行 | 口径 = **7 个代码文件 + 1 组文档（DEPLOY.md/AGENTS.md/README.md）** |
| ③ | §A-P0a ③ 写"5 张表行数"，附录 A3 实列 **8** 张表 | 口径 = **8 张表**（workflow_run / workflow_step_run / graph_snapshot / workflow_session / chat_session / app_user / auth_session / import_batch） |
| ④ | §D-1 定义 FI-1…FI-7，而 §A-P1/§F-P1 与验收任务只要求 FI-1…FI-4 | 口径 = **FI-1…FI-4 为门禁**（并发领取 / 崩溃恢复 / checkpoint 写失败 / 状态恢复）；**FI-5…FI-7 为可选**（重复投递、连接中断、schema 缺失），执行到则一并报告，未执行不判失败 |

另注：v2.1 §A-P0a 产出所列 `backups/baseline/` 属**生产只读审计**（不在已批准的本地/staging DAG 内），当前**唯一在库基线来源是附录 A1–A7 的数字与本附录 §5 的隔离环境说明**。

环境变更（§1–§8）与本节勘误共同构成本次执行的**生效口径**：凡 v2.1 正文与本附录冲突处，以本附录为准；其余全部保持有效。

## 10. 实现期发现与口径修正（t2 交付时实测，2026-10-14）

| # | 事项 | 定案 |
|---|---|---|
| ① | 暂存树基线由生产 `backend` 复制而来，会把**生产 `backend/.env`** 一并带入（`core/config.py` 经 `parents[2]/.env` 加载） | 已由 t2 用暂存专用 `.env` 覆盖（root 与 backend 两处），staging 库口令轮换为随机值；**任何重建暂存树的操作必须重复此步骤**，否则会误用生产密钥/口令。t3 须核验：暂存树内**不存在**生产 `.env` 的副本（按 sha256 比对，生产 `.env` = `dc8f334c…`） |
| ② | CFG-1「停用 → `latency_ms=0`」在冻结的 `_run_step` 下**不可达**（`step.latency_ms = latency_ms or elapsed` 会把 0 替换为实测值） | 口径改为**量级断言**（`latency_ms < 100ms`，且与 legacy 同口径），不再要求等于 0；t3/t4/t5 统一按此口径 |
| ③ | v2.1 §E.2 所述"major0/minor<5 兼容告警"在**锁定版本**源码中不存在 | 实测兼容约束为 `langgraph-checkpoint>=4.3.0,<5.0.0`（已写入 `requirements.txt` 注释）；t5 文档按实测约束描述 |
| ④ | v2.1 §C.8 提及的"5 张表" | 实际为 **6 张**：`checkpoint_migrations`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`run_engine`、`run_lock`；校验按 6 张 |
| ⑤ | 恢复前置 4「已提交 step 与 checkpoint 一致」的落地定义 | 定义为：①committed 为**线性前缀**；②checkpoint 覆盖 ⊆ committed；③**至多 1 步**已提交但未落 checkpoint（W1 窗口）。否则 FI-2 的崩溃窗口无法恢复 |
| ⑥ | 故障注入覆盖 | FI-5（重复投递）、FI-6（PG 连接中断）**未执行**（v2.2 §9 判为可选，不判失败）；FI-7 相邻的 **503 注入已实测通过**（pin 表缺失 → 503 且 runs/steps 零新增、不入队） |
| ⑦ | 澄清（captain 只读抽查） | 暂存树实际包含 HEAD 版 `db/models.py`（`c57295db…`）与 `db/init_db.py`（`50a4a375…`），两列已在 staging 库落位（实测列数 = 2）；staging 库 `workflow_step_run` 428 条中 `used_fallback=104`、`skipped=8` → **标志真实持久化**，排除"两引擎均不落库导致等价测试假通过"的风险；t2 报告的"6 个修改文件"指迁移自身改动，不含随最小批次同步的 `models.py`/`init_db.py` |

## 11. t3 验收结论、findings 定案与修正后的 verify 命令（2026-10-14）

**验收结论（t3 已完成）**：acceptance **11/11 passed**；12 门禁用例 × 2 轮 = **24 次执行全通过**；FI-1..4 全绿（重复 `(run_id, agent_key)`=0、悬空快照=0、running 残留=0、run_lock 泄漏=0）；表落位 **6 张**且 staging `public` 无 `checkpoint%`；隔离性通过（暂存树 6702 文件中**生产 `.env` 副本命中 = 0**；staging `.env` 600；库口令随机 24 位；24/24 交付文件仓库↔暂存树 sha256 相同）；**生产未写**（10/56/45 前后一致、生产 `langgraph` schema=NONE、生产两标志列=0、生产树 17 条指纹一致、`:8000` pid 2398177 未重启、8010 已停）；GET-only 回归 2 轮 9/9。

| # | Finding | 定案 |
|---|---|---|
| G1 | FI-2 未覆盖节点级 `reused=true` 分支（整套日志 0 命中）；实测复用机制是 LangGraph 对 pending write 的重放（恢复仅跑 seq 2..6） | **已知机制差异，不判失败**：契约实质（不重复调用 LLM、不重复行）已满足。补"step 已提交且 `put_writes` 未落库"窗口用例列为**可选项**（不影响阶段一放行），由 t4 记录 |
| G2 | verify #1 的 DSN 缺库口令 → 服务器上必然 exit 1（fe_sendauth） | **契约缺陷（captain 撰写问题）**：修正为 `--db-url postgresql+psycopg://neo4j_migrate:<staging口令>@127.0.0.1:5432/neo4j_agents_migrate`；口令见 staging `.env` 或 `~/.stg-t2/staging.json`(0600)。t3 已以等价证据通过，修正后命令供后续复跑使用 |
| G3 | verify #2 用系统 `python3`（无 psycopg）→ exit 1 | **契约缺陷**：改用暂存树 venv python（`/www/wwwroot/neo4j-migrate/venv/bin/python`）或 `sudo -u postgres psql -d neo4j_agents_migrate -tAc "…"` |
| G4 | verify #5 的 `accept_rnd_api_regression.py --dry-run --no-network` 参数不存在 → exit 2 | **契约缺陷**：交付脚本无 dry-run/离线参数；等价证据 = **带 token 实跑 2 轮**（only_get=true / 9 GET / 0 失败 / 历史回放哈希两轮一致）。如需 dry-run 语义，列为后续增强，不作为验收判据 |
| G5 | 503 响应体回显内部异常细节（relation / SQL 片段） | **需修复（生产前硬化）**：503 仅返回通用错误与标识，不回显异常内部信息（§E.9 口径）；已派 repair 任务 t6；t5 文档须写"503 返回通用错误、不回显内部细节" |
| G6/G7 | 影子库不清库，绝对计数含 t2 残留（§10⑦ 的 428/104/8 → 646/156/12）；本轮未用 `--recreate-db`（重建会使 `neo4j_migrate` 失去 `public` 授权） | **口径说明**：等价性以"同库连跑 2 轮全绿"与相对差异为准，不以绝对计数为准；重建暂存库须重新授权 `public`（写入 t5 文档） |

**下游判定口径（务必遵守）**：t4 审查时，**G2–G4 属契约文本缺陷（已定案），不得计为 t2 的实现失败**；t3 的 `commandsRun` 三条字面退出码（1/1/2）仅表示"原命令文本不可直接执行"，其验收结论已由等价证据支撑。G1 记为已知机制差异；G5 由 t6 修复，t5 按修复后口径写文档。

## 12. t4 审查结论与 F1–F7 定案（2026-10-14）

**结论**：**verdict = pass**（无 blocker / high）；10 项清单逐条 pass；审查方**独立复算 48 对 legacy↔langgraph 规范化后 0 差异**；22/22 交付文件（本地↔暂存树）sha256 全 MATCH（被审查代码 = 被验收代码）；只读 SQL 复核 staging 120 个 Run **全部有 pin**（72 langgraph / 48 legacy）、`dup(run_id,agent_key)=0`、`run_lock=0`；生产侧 10/56/45、`langgraph` schema=NONE、生产树 mtime 停在 10-12、生产 Neo4j 86,484/207,356/Compound=0、生产 venv 无新依赖、HEAD 未变。

| # | Finding | 定案 |
|---|---|---|
| **F1**(medium) | §C.5 的 pin 完备性校验 SQL 有**时区缺陷**（`workflow_run.created_at` 是 naive-UTC 列，marker 是 `timestamptz`）→ 实测返回"迁移后 Run 数 = 0"，**恒通过漏报** | **确认为文档缺陷**（实现侧口径正确）。生效版本见下方修正 SQL，并把「**全量 `runs_without_pin = 0`**」作为**强断言**（不依赖 marker 比较）。t5 文档按修正版书写 |
| F2(low) | P1 DoD④ 的 fixture 无产物 | 口径：fixture 产物为**可选增强**（如 `--write-fixture`）；阶段一以"E2E-1 规范化 0 差异 + 审查方独立复算 0 差异"作为等价证据；t5 文档注明 |
| F3(low) | 503 回显内部异常细节 | 已派 **t6** 修复（生产前硬化） |
| F4(low) | §11 G2 所写 `~/.stg-t2/staging.json` 是本地开发机路径，服务器不存在 | 更正：staging 库口令存于**服务器** `/www/wwwroot/neo4j-migrate/.env` 与 `/www/wwwroot/neo4j-migrate/backend/.env`（均 0600）；本地另有 `C:\Users\feife\.stg-t2\staging.json`（0600，仅供 captain 使用） |
| **F5**(low) | **E2E-3 / HIST-1（生产只读历史回放）未执行**；t2/t3 的"回放哈希一致"只是 staging 8010 两轮稳定性 | **明确记为未验证**：任何报告与文档**不得表述为 HIST-1 / E2E-3 通过**；生产只读回放归入 **A4 窗口或另行批准的只读审计**执行 |
| F6(low) | 传递依赖未固定（如 `langgraph-checkpoint==4.3.0`） | **A2 检查项**：安装前后各存 `pip freeze`（含传递依赖），并把关键传递依赖以 `==` 固化进 `requirements.txt`，或归档 `pip-freeze-*.txt` 作为等同证据 |
| F7(low) | G1 定案记录 | 按 §11 G1 执行（已知机制差异；补"step 已提交且 `put_writes` 未落库"窗口用例为可选项） |

**部署顺序硬约束（新增）**：**A3（引导 `langgraph` schema/表 + 写 marker）必须先于 A4（上传代码并重启）**。若先部署代码而 schema 未就绪，按设计每次建 Run 都会返回 503（不降级）——这是预期行为，但会使研发工作台不可用，故顺序不可颠倒。

**修正后的 pin 完备性校验 SQL（生效版本）**

```sql
-- ① 强断言（推荐，作为巡检与 DoD 主判据）：全量 Run 都必须有 pin，不依赖 marker
SELECT count(*) AS runs_without_pin
FROM workflow_run r
WHERE NOT EXISTS (SELECT 1 FROM langgraph.run_engine p WHERE p.run_id = r.id);   -- 必须为 0

-- ② 迁移后分段统计（时区修正：created_at 为 naive-UTC，marker 为 timestamptz）
SELECT count(*) AS migrated_runs,
       count(*) FILTER (WHERE p.run_id IS NULL) AS runs_without_pin
FROM workflow_run r
LEFT JOIN langgraph.run_engine p ON p.run_id = r.id
WHERE r.created_at >= ((SELECT config_value::timestamptz FROM system_config
                        WHERE config_key = 'rnd_engine_migrated_at') AT TIME ZONE 'UTC');
```

> 说明：marker 尚未写入时（迁移前）②无基准，只用①。原 §C.5 的写法作废。

## 13. t6（G5 修复）结果、对外错误口径与第三条命令文本更正（2026-10-14）

**t6 结论**：G5 修复完成并在服务器暂存树回归通过；改动仅 2 个 inScope 文件（`services/rnd_engine.py`、`api/routes.py`；`rnd_graph/checkpointer.py` 审阅后判定无需改动），同步暂存树 sha256 全 MATCH；未 git 提交（HEAD 仍 `7e0abbf1`）。

**对外错误口径（生效，t5 文档须照此书写）**
1. **HTTP 503（引擎固定失败）**：对外只返回通用文案 + 可选 `run_id`，例如
   `{"detail":"研发任务引擎固定失败，请联系管理员（可能原因：LangGraph 存储未初始化）（run_id=…）"}`
   ；异常类名 / relation / SQL / `psycopg` / 连接串一律**不得**出现在响应体（staging 注入实测 `grep -Eic 'psycopg|UndefinedTable|ProgrammingError|relation|SQL|Traceback|postgresql://'` **hits=0**）。
2. **失败骨架（后台执行期）**：读 pin 失败 / pin 取值非法 / 迁移后缺 pin 三种情形的**入库失败骨架与抛出文案**同样改为通用文案，原因只写服务端日志——因为 `workflow_run.final_report` 可经 `GET /api/rnd/runs/{id}` 读出（此前会把 psycopg 原文写进该字段）。
3. **语义未变**：仍为 `run=failed` + 失败骨架 + 不降级；503 场景仍**不入队、不执行**（staging 实测 runs 120→120、steps 646→646、pins 120→120，注入表已还原）。
4. **日志侧保留可排查信息**：`rnd_engine pin 写入失败 run_id=… engine=… stage=pin_write schema=…` + 完整堆栈 + `研发任务引擎固定失败（HTTP 503）run_id=…`。

**第三条命令文本更正（同一类缺陷，captain 撰写问题）**：t6 契约 verify #4 的两条命令在**当前阶段**不可直接执行，正确理解如下——
1. `sha256sum /www/wwwroot/neo4j-agents/backend/app/services/rnd_engine.py` → 生产树**尚无该文件**（未部署），`exit=1` 属**预期**；生产未触碰的证明应改用**生产树现存文件**的 sha256/mtime 指纹前后一致（如 `rnd_workflow_orchestrator.py`、`routes.py`、`config.py`）。
2. `psql -d neo4j_agents` 以 root 直连会 `exit=2`（`role "root" does not exist`）→ 应使用 `sudo -u postgres psql -d neo4j_agents -tAc "…"`。

**未跟踪文件清单（勿 git add）**：`stg_server.py`（同步助手，无明文凭据、含生产路径写守卫）、`.tmp-t2-*.sh/.txt`、`.tmp-t6-*.sh/.py/.txt`、`.tmp-langgraph-verify/`、`.tmp-langgraph-review/`；staging 库口令仅存服务器暂存树两份 0600 `.env`（本地副本 `C:\Users\feife\.stg-t2\staging.json` 0600）。

**交接 t5 的三点**：① 503 与失败骨架均为通用文案（见上）；② 巡检/文档中的命令须按本节更正（`sudo -u postgres psql`、生产未部署文件不要作为指纹对象）；③ 部署顺序仍为 **A3 先于 A4**。

## 14. t7 重验收结论与"注入类验证脚本"约定（2026-10-14）

**结论**：t7 acceptance **7/7 passed**；**28 项用例全通过**（24 = parity 12×2 轮 + 3 = 失败骨架脱敏情形 + 1 = 503 注入），未执行项 0。

**哈希绑定（当前 revision 的权威锚点）**

| 文件 | sha256（前缀/全文） | 大小 |
|---|---|---|
| `backend/app/api/routes.py` | `a53e0da52f51e8424e17afd87e60a09748ffe7878143053afd56cfa1e22f8daf` | 60,502 B |
| `backend/app/services/rnd_engine.py` | `0522f4c2701d9b6b8212a5b2eccb442ff8ca5edaf11f6ae854ce251f6ee7c0c3` | 15,611 B |

staging 与**仓库同文件逐字节相同**，且与 t6 交付一致 → 被测 = 被审查 = 被验收。**t3/t4 对更早字节的 verdict 不适用于当前 revision**；完整哈希链见 §15。

**脱敏实测**：503 响应 162 B，仅通用文案 + `run_id`，`grep -Eic 'psycopg|UndefinedTable|ProgrammingError|relation|SQL|Traceback|postgresql://'` = **0**；`runs 180→180`、`steps 973→973`（不入队、不执行）；失败骨架 3 情形（读 pin 失败 / pin 非法 / 迁移后缺 pin）均 `run=failed`、`leak_hits=0`、骨架 14 键齐备、对外为通用文案，服务端日志保留 psycopg/SQL/堆栈。

**隔离性与生产零触碰**：`langgraph` 6 表齐备、staging `public` `checkpoint%`=0、暂存树内生产 `.env` 命中 = 0；生产 10/56/45 前后各测一次一致、生产 `langgraph`=NONE、生产树 17 条指纹 `before == after == t3-before`、`:8000` pid 2398177 未重启、8010 已停。

**验证侧事故（info，非产品缺陷，已闭环）**：t7 的 503 注入脚本**还原语句方向写反**（应为 `run_engine_t7_bak → run_engine`），注入后表短暂停留在 bak；**1 分钟内**用修正脚本恢复（`bak=0`、6 表、`pins=180`），不影响 503 结论（数据与响应均在注入期间采集）。**由此形成约定**：任何注入类验证脚本必须带 `trap` 还原 + 幂等守卫（参考 `t7-503-fixed.sh`），并在注入前后各留一次表清单与计数快照。

**staging 测试数据说明**：本轮新增 3 个 failed Run + 1 个空 session；`runs_without_pin=0`、`pins=183=runs`、`dup_step_groups=0`、`running_runs=0`（**仅 staging 域**，生产不受影响）。

**沿用口径**：§11 的 G2–G4 修正文本已在 t7 生效（`neo4j_migrate:<口令>` DSN、`sudo -u postgres psql`、生产未部署文件不作指纹对象）——t5 文档与后续巡检一律沿用。

## 15. t8 重新审查结论、哈希链更正与两项决策（2026-10-14）

**结论**：t8 **verdict = pass**，7 项 acceptance 全 passed，**verdict 绑定当前字节**：`routes.py a53e0da52f51e842…`（60,502 B）、`rnd_engine.py 0522f4c2701d9b6b…`（15,611 B）；本地 = 暂存树 = t6 报告 = t7 证据四处同值。

**哈希链（溯源更正，T8-F2）**

| 阶段 | `routes.py` | `rnd_engine.py` |
|---|---|---|
| t2 交付（t3/t4 的审查基线） | `266563a2…` | `c324bb0f…` |
| t6 第一轮改动的中间修订 | `2492554e…` | `6966fa61…` |
| **t6 终稿 = 当前 revision** | **`a53e0da5…`** | **`0522f4c2…`** |

> **更正**：§12/§13 与 t6 报告、t7 SUMMARY 中曾把 `2492554e…`/`6966fa61…` 标注为"t3/t4 旧哈希"，实为 **t6 自己的中间修订**（全仓无副本留存）。该标注错误**不影响失效结论**：t3/t4 的基线是 `266563a2…`/`c324bb0f…`，与当前字节不同，故其 verdict 确实不覆盖当前 revision。

**T8-F1（medium）决策：阶段一接受，A4 窗口同批脱敏**

- 事实：`_apply_run_failure`（`rnd_workflow_orchestrator.py:360`）仍把异常原文写入 `final_report.consistency_checks[0]`，该字段可经 `GET /api/rnd/runs/{id}` 读出；可达路径 `runner.py:292/325/386` 与 legacy `resume_run` 的 except。
- 性质：**迁移前既有 legacy 语义**（v2.1 §C.6 要求复用），**非 t2/t6 引入**；库内实测无 psycopg / relation / SQL / 连接串（全库扫描 **0 行**），仅见库内部错误描述（如 `Invalid checkpointer provided…`）。
- 决策：**(a) 阶段一接受**，并列为 **A4 窗口必做项**——与生产发布同批改为通用文案（原异常只进日志），随后按 §11/§13 口径**重新验收 + 重新审查**。理由：①不构成对现状的回归（生产今天已是该行为）；②现在就改会变动 legacy 可见文本并触发新一轮 verify/review，而 A4 本身就要对最终字节重跑门禁，合并做更经济；③该改动只涉及文案内容，不动字段与 `/api/rnd/*` 结构，不触碰契约冻结的字段层面。
- 若你（用户）希望**立即修复**，我可另派 repair（`orchestrator.py` 失败骨架文案脱敏）并附带 verify + review 闭环——请示意。

**T8-F3（low）**：t7 的注入脚本还原方向事故已闭环（复核 `bak=0`）；「注入脚本必须 `trap` 还原 + 幂等守卫 + 前后快照」已写入 §14 与 `DEPLOY.md` P20.10。

**阶段一闭环声明（本地/服务器暂存树侧）**：t1–t8 全部完成；**t2+t6 的当前字节**经 t7 重验收（28 项全通过）与 t8 重新审查（verdict=pass）双门禁覆盖；**生产域（树/库/schema/venv/nginx/面板项目）自始至终未被写入**，所有生产动作仍待 A0–A8 逐项批准。







