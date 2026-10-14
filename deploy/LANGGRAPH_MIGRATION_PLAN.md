# LangGraph 研发协同迁移实施计划 v2.1

> **阶段一：固定串行六步的等价迁移**

| 项 | 内容 |
|---|---|
| 来源任务书 | `D:\工作\多智能体-宋\思路2026-10-14\LangGraph 研发协同迁移规划任务书.md` |
| 仓库 | `D:\python_workspace\neo4j_muti_agents`（GitHub `maolinxiao/neo4j_muti_agents`，分支 `codex/rnd-fix-2026-08-26`） |
| 网站 | https://mmfh.com.cn/ |
| 制定日期 | 2026-10-14 |
| 版本 | **v2.1**（经两轮评审：11 条 + 9 条修订） |
| 本阶段范围 | 仅迁移**研发协同工作台**；知识问答、体质、个人中心、管理端其他模块一律不动 |
| 零改动声明 | 本文档本身不修改任何代码、数据库、依赖或服务器；文中的生产动作均为**待逐项批准**的操作说明 |

## 修订史

| 版本 | 变更 |
|---|---|
| v1 | 初稿（P0–P5 框架、逐文件清单、验收与回滚） |
| v2 | 落实 11 条审核意见：P0 拆为只读审计 + 最小兼容补丁；Node 只包装既有 `_run_*`；Run 创建与引擎 pin 同事务且失败不降级；新增 Run 级独占锁与节点重放幂等；生产失败即 failed 不承诺自动续跑；State 防覆盖；运行依赖放 runtime.context；Saver 连接参数与 CLI 建表；不硬编码快照数并用真实契约比较；灰度加任务类别门槛、故障注入仅隔离、DROP SCHEMA 移出回滚、部署脚本禁明文凭据；版本固定/数据脱敏/配置回滚/历史留存/日志脱敏 |
| **v2.1** | 落实 9 条最终修订（见 §0.2），并更正两处事实错误（见 §0.1） |

---

## 0. 前提核对与事实更正

### 0.1 任务书前提核对（实测，2026-10-14）

| 任务书陈述 | 实测结果 | 处置 |
|---|---|---|
| "GitHub 与生产代码一致" | **不成立**：生产落后 1 个代码批次；且生产**缺列** `workflow_step_run.used_fallback` / `.skipped`、**缺表** `agent_config_revision` | P0a/P0b 先做基线审计与最小补丁；发布时采用**最小文件集**（实测差异恰 8 个文件，其余 74 个逐字节一致，**不存在"整树同步"的必要**） |
| "现有六步研发 Agent 可稳定运行" | 10 次 run（9 完成 / 1 失败），**最近一次 2026-09-01 17:32**，此后 6 周未跑；唯一失败根因是 2026-09-02 已修但未再验证的 `kb5_formula_context` 类型 bug | P3 部署后先跑 1 次 **legacy 基线运行**，再进 canary |
| "仅有生产 Linux 服务器，没有独立测试环境" | 确认：生产 + 本地开发机；本地 PG 17.9 在跑，**本地 Neo4j 未安装/未运行** | P1 用假依赖做等价测试（不需 Neo4j）；P2 才需真实图谱（本地装 Neo4j + 生产 dump 只读副本） |
| "允许新增独立 Checkpoint 表" | 可行：库内仅 `public` 一个 schema、`checkpoint%` 表 0 张、`psycopg3` 已就位 | 采用同库独立 schema `langgraph`（§C.8） |

**两处事实更正（v1/v2 有误）**

1. **远程 LLM 调用次数**：`build_rnd_brief()` 是**本地规则解析**（`backend/app/services/deepseek_client.py:396-430`，正则 + 关键词表，无任何 HTTP），**不计入远程调用**。正常 Run 的远程生成调用**上限 6 次**（每个 Agent 步 1 次）；**重试单独统计**（见 §D-3）。
2. **快照数量不可硬编码**：库内 45 条 `graph_snapshot` 中，37 条被研发步骤引用，其余 **8 条属知识问答工作台**（研发 session 与影子 `chat_session` 同 id 共用同一张表）。且快照数随图谱命中情况变化（**0 也是合法值**）。等价断言一律改为"与同 brief 的 legacy 实测值逐项相等"。

### 0.2 v2.1 的 9 条修订（差异清单）

| # | 修订点 | 修订后口径 |
|---|---|---|
| 1 | 调用与统计 | `build_rnd_brief()` 本地解析；远程生成调用上限 **6 次/Run**；重试按日志行单独统计，不并入 6 次 |
| 2 | 比较口径 | 不同 Run 的 `run_id`/`step_id`/`graph_snapshot_id`/时间戳**不要求相等**；Mock 比规范化业务数据，真实模型比结构/约束/来源关系 |
| 3 | FI-3 语义 | Checkpoint 写失败：**保留已提交 StepRun**，Run 必须标记 `failed`，不得重复步骤或悬空引用 |
| 4 | invoke 与恢复 | 首次必须 `graph.invoke(initial_state, ..., durability="sync")`；`invoke(None, ...)` 仅用于满足 5 项前置的已有 Checkpoint 恢复 |
| 5 | 租约锁 | 第一阶段**禁止租约过期自动接管**；如需自动接管必须先有 fencing token + 写入权限校验（阶段二） |
| 6 | 测试边界 | 生产只读验收**仅 GET**；`POST /api/chat/.../messages/stream` 会写库，移入隔离环境写入测试 |
| 7 | 真实模型验收 | 不要求文字值一致；Fallback **不一概判定为失败**，改为与 legacy 同场景的**归因比较** |
| 8 | marker 语义 | 固定 `rnd_engine_metrics_started_at` 与 `rnd_engine_migrated_at` 的写入时机与事务边界；校验"迁移后所有 Run 必须有 pin"；历史 `used_fallback/skipped` 属**未测量**，不得当作真实 FALSE |
| 9 | 灰度可验证性 | 四类灰度用例**绑定真实图谱实体**，写明数据版本与具体预期结果 |

---

## A. 实施步骤 P0a–P5

### P0a 只读基线审计（零写入、零重启、无需审批）

| 项 | 内容 |
|---|---|
| ① 版本差异核对 | 存证 8 个差异文件（1 新增 + 7 修改）+ 74 个文件 sha256 MATCH 记录 → 结论"最小补丁集 = 这 8 个文件" |
| ② 结构基线 | `workflow_step_run` 列清单（确认无 `used_fallback`/`skipped`）；`agent_config_revision` 缺失；`checkpoint%` 表 0 张；schema 仅 `public` |
| ③ 数据基线 | 5 张表行数 + 关键列校验和 + 10 条历史 run 的 `GET /api/rnd/runs/{id}` JSON 与 sha256 |
| ④ 环境基线 | 无在跑 run（`status in ('queued','running')` = 0）、磁盘余量、`max_connections`、`pip freeze`、图谱指纹 |
| 产出 | `backups/baseline/` + `deploy/LANGGRAPH_MIGRATION_PLAN.md` 的 P0a 附录（见附录 A1–A7） |
| DoD | 见 §F-P0a |

### P0b 独立最小兼容补丁（**仅 DDL，加法式**；待批准，审批 A1）

```sql
BEGIN;
ALTER TABLE workflow_step_run ADD COLUMN IF NOT EXISTS used_fallback BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE workflow_step_run ADD COLUMN IF NOT EXISTS skipped       BOOLEAN NOT NULL DEFAULT FALSE;
INSERT INTO system_config (id, config_key, config_value, config_type, created_at, updated_at)
VALUES (gen_random_uuid()::text, 'rnd_engine_metrics_started_at', now()::text, 'string', now(), now())
ON CONFLICT (config_key) DO NOTHING;
COMMIT;
```

- 边界：**不部署应用代码、不重启、不改任何既有列/约束/数据**；`agent_config_revision` 表由 P3 发布时 `create_all()` 加法创建。
- 语义：`created_at < rnd_engine_metrics_started_at` 的 step 行，其 `used_fallback/skipped` 属**未测量**，不得解释为真实 FALSE；所有统计查询必须带该时间过滤。
- DoD：见 §F-P0b。

### P1 本地实现 + Mock 等价（隔离环境，含故障注入）

- 实现 §B 清单；影子库 `neo4j_agents_parity`（脚本自建 + `initialize_database()`）。
- 命令：`python scripts/accept_rnd_engine_parity.py --mock --offline --db-url postgresql+psycopg://postgres@127.0.0.1:5432/neo4j_agents_parity`
- 覆盖 E2E-1、CFG-1..4、FB-1..3、FI-1..4（§D），**故障注入只在本地影子库进行**。
- DoD：见 §F-P1。

### P2 隔离真实运行（生产零接触；待批准，审批 A7）

- 本地装 Neo4j 5.26 + 载入**生产 dump 只读副本**（从服务器 `backups/neo4j/dump_<date>/` 拷出，不建隧道、不直连生产）+ 本地影子库 + 真实 DeepSeek key。
- 同一 brief 各跑一次 legacy / langgraph，按 §D-2/§D-3 口径比对。
- DoD：见 §F-P2。

### P3 生产发布准备与发布（待批准，审批 A2/A3/A4）

1. 备份包 + 基线快照（§E.1）
2. 依赖在临时 venv 试解（diff 仅新增，§E.2）
3. `backend/scripts/init_langgraph_checkpoint.py` 引导 schema（autocommit；§C.8）
4. 最小文件集上传（逐文件 sha256 MATCH，§E.5）
5. 面板脚本重启（前置：无在跑 run）
6. **legacy 基线运行 1 次**（审批 A5，记录耗时/兜底/快照）
- DoD：见 §F-P3。

### P4 灰度（canary，白名单管理员；待批准，审批 A6）

- 写 `system_config.rnd_engine = {"mode":"canary","users":[...]}`（记录旧值用于配置回滚）。
- 按 §E.4 四类任务跑满覆盖门槛。
- DoD：见 §F-P4。

### P5 全局切换 + 观察 + 收尾（待批准）

- `{"mode":"langgraph"}` 全局；观察 72h，与 legacy 基线对比。
- 收尾：`DEPLOY.md` 迁移小节转正、`AGENTS.md` §8/§14、`README.md`；卫生项 §E.10。
- DoD：见 §F-P5。

---

## B. 逐文件修改清单

### B.1 新增（13）

| 文件 | 作用 | 关键约束 |
|---|---|---|
| `backend/app/services/rnd_graph/__init__.py` | 包入口 | 仅导出 build/run |
| `backend/app/services/rnd_graph/state.py` | `RndGraphState` | 六个 Agent **各自独立字段** + 输入字段 + error；**无 reducer**、无聚合键；仅 JSON 兼容类型 |
| `backend/app/services/rnd_graph/context.py` | `RunContext` | `session_factory`/`neo4j_factory`/`llm_client`/`owner_token`；**不进 State**，经 `runtime.context` 传入 |
| `backend/app/services/rnd_graph/nodes.py` | 六个 node 工厂 | 只包装既有 `_run_*`；不复制组方/检索/兜底；节点内自开短会话；节点重放幂等守卫 |
| `backend/app/services/rnd_graph/graph.py` | 线性图构建 | 由 `AGENT_STEP_DEFS.sequence` 派生；编译期断言"必须线性"；不引入分支/并行 |
| `backend/app/services/rnd_graph/checkpointer.py` | Saver 工厂 + 运行期校验 | `autocommit=True`、`row_factory=dict_row`、`options="-c search_path=langgraph,public"`；只校验不建表 |
| `backend/app/services/rnd_graph/run_lock.py` | 租约锁 | `ON CONFLICT DO NOTHING`；禁自动接管；按 owner 释放 |
| `backend/app/services/rnd_graph/runner.py` | `run_langgraph(run_id)` | 取锁 → invoke → 成功/失败收尾（复用 `_apply_run_success/_apply_run_failure`）；从 step 行派生快照列表与 `final_report` |
| `backend/app/services/rnd_engine.py` | 引擎决策/固定/查询 | system_config → env → 默认 legacy（TTL 15s）；**同事务 pin 写入**；缺 pin 判定 |
| `backend/app/db/langgraph_schema.py` | schema/表**存在性校验** | 启动路径零 DDL；DDL 常量供 CLI 复用 |
| `backend/scripts/init_langgraph_checkpoint.py` | 运维 CLI（唯一建表入口） | autocommit；`CREATE SCHEMA` + `PostgresSaver.setup()` + `run_engine`/`run_lock` DDL；打印表清单 |
| `backend/scripts/rnd_engine_switch.py` | 开关切换/回滚脚本 | 读旧值 → 写新值 → 打印回滚命令；不含凭据 |
| `scripts/accept_rnd_engine_parity.py` | Mock 等价 + 故障注入 | 自建影子库；假 LLM/假 Neo4j；规范化比较；`--offline` 禁网断言 |
| `scripts/accept_rnd_api_regression.py` | 只读契约与历史回放回归 | **仅 GET**；不建测试账号、不写库 |

### B.2 修改（7，均为最小/加法式；逐项标注**骑带内容**）

| 文件 | 改动 | 骑带内容（须审核确认） |
|---|---|---|
| `backend/app/api/routes.py` | ① `create_workflow_run` 先决策引擎并把 `engine_pin` 传给 `start_run`；② `_run_workflow_in_background` 改为读 pin 分派（legacy 原路径 / langgraph runner / 异常即 failed 不降级） | 该文件 HEAD 版含管理端"工作流配置"端点（`/admin/workflow/agents*`）与导入端点；**均为新增端点，不改既有行为** |
| `backend/app/services/rnd_workflow_orchestrator.py` | 仅 4 处机械抽取：新增 `_run_master_control()`、`_run_master_control_final()`；抽出 `_apply_run_success()`（现 `resume_run:230-252`）、`_apply_run_failure()`（现 `:264-295`）；`resume_run` 改调它们 | **无**；组方/检索/兜底/`_assemble_final_report`/KB5 回注逻辑零改动 |
| `backend/app/core/config.py` | 新增 `rnd_engine`(legacy)、`rnd_engine_cache_ttl_seconds`(15)、`rnd_langgraph_schema`(langgraph)、`rnd_langgraph_pool_max`(2)、`rnd_langgraph_validate_on_start`(True)、`rnd_orphan_sweep_enabled`(False)、`rnd_orphan_stale_minutes`(30) | agent-config 相关 4 个上限设置（无行为影响）；**生产不需要新增任何 env 键** |
| `backend/app/repositories/postgres_repository.py` | 仅新增只读方法 `get_system_config_value(key)` | agent-config 往返/版本方法（新增方法，不改既有） |
| `backend/app/db/models.py` | 映射 `workflow_step_run.used_fallback/skipped`、`AgentConfigRevision` | 1 张新表（`create_all` 加法创建） |
| `backend/app/main.py` | 启动时调用 `validate_langgraph_runtime()`（**只校验**） | 无 |
| `backend/requirements.txt` | 增 3 个 `==` 固定依赖（P1 定版） | 无 |
| `DEPLOY.md` / `AGENTS.md` / `README.md` | 文档更新 | 文档 |

> 说明：最小文件集 = 实测 8 个差异文件；其余 74 个文件与生产逐字节一致，不做任何同步。

### B.3 冻结不改（显式清单）

`backend/app/schemas/rnd.py` · `backend/app/services/agent_config_service.py` · `backend/app/db/init_db.py` · `backend/app/db/seed_data.py` · `backend/app/services/{qa_orchestrator,qa_routing,qa_answer_templates,graph_retriever,question_classifier,entity_resolver,kg_import_core,kg_import_service}.py` · `frontend/**`（含 `frontend/dist`） · nginx 配置 · Neo4j 图谱与 Cypher · 认证/体质/导入模块 · `workflow_run`/`workflow_step_run`/`graph_snapshot` 既有字段、索引与**全部历史数据**。

---

## C. 数据库与事务设计

### C.1 State 与运行依赖

```
RndGraphState（仅 JSON 兼容，写入 Checkpoint）        RunContext（runtime.context，不入 State）
  run_id: str            session_id: str                session_factory: Callable[[], Session]
  question: str          brief: dict                    neo4j_factory: Callable[[], Neo4jRepository]
  master_control: dict        ← 各 Agent 独立字段          llm_client: DeepSeekClient（线程安全池）
  formula_generation: dict    ← 互不覆盖                  owner_token: str（租约标识）
  efficacy_prediction: dict   ← 无 reducer 也安全合并      run_id / session_id（只读）
  flavor_prediction: dict
  replacement_mapping: dict
  master_control_final: dict
  error: str | None
```

- **不做** `steps: dict[...]` 聚合键（会被后续节点整体覆盖）；**不做** `snapshots` 累积键。
- `related_graph_snapshots` 由 runner 从 DB 派生：`list_workflow_step_runs(run_id)`（按 `sequence`）中非空 `graph_snapshot_id` 依次收集 —— 与 legacy 累积顺序天然一致。
- `final_report` 由 runner 读六条 step 行后调用既有 `_assemble_final_report` 组装，不新增汇总逻辑。
- 快照外键不变量：研发 session 由 `create_workflow_session()` 同时建 WorkflowSession 与**同 id 的影子 ChatSession**（`status='workflow_shadow'`），`graph_snapshot.session_id` 的 FK（→ `chat_session.id`）依赖该不变量；**不得"修复"外键或动历史数据**。

### C.2 Run 创建 + 引擎固定（同一事务）

```
POST /api/rnd/sessions/{sid}/runs
 └─ engine = rnd_engine.decide(user_id)            # system_config → env → legacy
 └─ start_run(sid, question, engine_pin=engine)
      BEGIN（同一 SessionLocal 事务）
        workflow_session.status = "running"
        run = INSERT workflow_run(status="queued")            # flush
        INSERT INTO langgraph.run_engine(run_id, engine, pinned_at)   # 同事务
      COMMIT
 └─ background_tasks.add_task(_run_workflow_in_background, run_id)
```

- 同库（`neo4j_agents`）内跨 schema 可同事务 —— 这正是选择"同库独立 schema"而非独立数据库的关键理由。
- **固定失败不得静默降级**：pin 写入异常（含 schema/表缺失）→ 事务回滚 → 接口返回 **503**，不入队、不执行。
- 执行入口读 pin：`legacy` → 现路径原样；`langgraph` → runner；读 pin 出错 → Run 置 `failed` + 失败骨架 + ERROR 日志（不降级）。

### C.3 Run 级独占租约锁（第一阶段禁止自动接管）

```sql
CREATE TABLE IF NOT EXISTS langgraph.run_lock (
  run_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL);

-- 领取：只要存在锁行（含已过期）即放弃，绝不自动接管
INSERT INTO langgraph.run_lock (run_id, owner, expires_at)
VALUES (%s, %s, now() + make_interval(secs => %s))
ON CONFLICT (run_id) DO NOTHING
RETURNING owner;
```

- 有返回行 ⇒ 取得执行权；无返回行 ⇒ WARN（`run_lock held, skip dispatch`），**不改 Run 状态、不接管**。
- 人工处理：`SELECT run_id, owner, expires_at FROM langgraph.run_lock WHERE run_id=%s;` → 确认无存活进程后 `DELETE FROM langgraph.run_lock WHERE run_id=%s AND owner=%s;` → 重新投递。
- 心跳每 30s（租约 180s）；结束（成功/失败/异常）按 owner 释放。
- 作用域：**仅 langgraph 路径**；legacy 行为保持不变。
- **阶段二若要自动接管**：必须先有单调递增 fencing token 且每次业务写入校验 token（校验失败拒绝写入）；本阶段不实现。

### C.4 节点重放幂等、invoke 语义与崩溃窗口

**invoke 约定**
- 首次执行：`graph.invoke(initial_state, config, durability="sync")`（同步落盘：每个 super-step 的 checkpoint 写成功后才推进；**取值以 P1 锁定版本的实测签名为准并记录**，若该版本不支持该键则以"节点返回前确保 checkpoint 落盘"的等价语义实现）。
- 恢复：`graph.invoke(None, config, ...)`，仅当**同时**满足 5 项前置：
  1. 该 `run_id` 在 `langgraph.checkpoints` 中存在记录，且最后 checkpoint 的 `channel_versions` 覆盖已提交 step；
  2. `run_lock` 无其他存活 owner（或已确认并人工释放）；
  3. 待恢复 Run 已被显式标记"可恢复"（隔离环境专用开关，**生产恒为关**）；
  4. 已提交 StepRun 与 checkpoint state 一致（不一致 → **拒绝恢复**并告警）；
  5. 引擎 pin = `langgraph`（legacy 的 Run 永不进入该路径）。

**四个崩溃窗口**

| 窗口 | 情形 | 机制 | 结果 |
|---|---|---|---|
| W1 | 节点内 step 行已提交，checkpoint 未写 | 节点入口守卫：`(run_id, agent_key)` 已有 `completed` 行 → 复用其 `output_payload`/`graph_snapshot_id`，**不再调用 LLM、不新增行**（日志 `reused=true`），随后正常返回让 checkpoint 落盘 | 无重复行、无重复计费 |
| W2 | checkpoint 写入失败（PG 错误） | graph 抛错 → 失败收尾（Run=failed + 骨架），**不自动重试**；**已提交 StepRun 保留**；不得出现重复步骤或悬空引用 | 生产语义 = 失败 |
| W3 | 进程崩溃，Run 停在 `running` | 阶段一**不自动续跑**；`rnd_orphan_sweep_enabled`（默认 off）仅把超时 Run 标 `failed` + 骨架 | 与 legacy 一致的失败语义 |
| W4 | 手动恢复（**仅隔离环境**） | 从最后 checkpoint 续跑；已 checkpoint 的 super-step 不重跑，W1 守卫兜住边界 | 技术验证项，不作生产承诺 |

### C.5 marker 写入时机、事务边界与 pin 完备性

| marker | 写入时机 | 事务边界 | 语义 |
|---|---|---|---|
| `rnd_engine_metrics_started_at` | **P0b 同一事务**（两列 DDL 与 marker 一次提交） | `BEGIN; ALTER TABLE …; INSERT system_config …; COMMIT;`（PG DDL 可事务化） | `created_at < marker` 的 step 行，`used_fallback/skipped` **为未测量值**，不得当作真实 FALSE；统计查询必须带 `created_at >= marker` |
| `rnd_engine_migrated_at` | A3 引导的**第二段独立事务**（第一段 autocommit 建 schema/表，因含 `CREATE INDEX CONCURRENTLY` 不能入事务） | 单独 `BEGIN; INSERT/UPDATE system_config; COMMIT;` | 该时刻之后的 Run **必须**有 pin；之前 = 历史 Run，解释为 legacy |

- **引导顺序硬约束**：段①建对象 → 段②写 marker 成功 → 才允许开启引擎开关；段②失败则开关保持 `legacy`。
- **pin 完备性校验**（入 §F-P4 DoD 与巡检）：

```sql
SELECT count(*) FROM workflow_run r
WHERE r.created_at >= (SELECT config_value::timestamptz FROM system_config WHERE config_key='rnd_engine_migrated_at')
  AND NOT EXISTS (SELECT 1 FROM langgraph.run_engine p WHERE p.run_id = r.id);   -- 必须为 0
```

### C.6 失败与恢复边界

- 生产：任何节点异常 → 复用 legacy 失败语义（`run.status=failed`、固定失败骨架、`workflow_session.status=active`、异常上抛由 ASGI 记录）。
- Checkpoint 手动恢复**仅作为隔离环境的技术验证**（§D FI-2），不进入生产运维手册的常规动作，**不承诺生产自动续跑**。

### C.7 依赖与并发

- 每节点**自开短会话**（`RunContext.session_factory`），用完即关；**不跨节点共享 `Session`**，为阶段二并行留出安全边界。
- Neo4j driver 与 httpx 客户端为连接池对象，可安全共享（只读语义）。
- PG 连接预算：稳态 +1（checkpointer 池 max 2）+ 每 Run 峰值 3～4 条短会话；迁移前核对 `max_connections` 与现有池参数。

### C.8 Checkpointer 连接与建表

- 连接参数：`autocommit=True`、`row_factory=psycopg.rows.dict_row`、`options="-c search_path=langgraph,public"`。
- 库表（`checkpoints`/`checkpoint_blobs`/`checkpoint_writes`/`checkpoint_migrations`）由库自身在**当前 search_path 首段**创建（其 DDL 为非限定表名）。
- 建表**只由 CLI** 执行（autocommit；`setup()` 含 `CREATE INDEX CONCURRENTLY`，不能落事务）：`CREATE SCHEMA IF NOT EXISTS langgraph AUTHORIZATION <app_user>` → `PostgresSaver.setup()` → `run_engine`/`run_lock` DDL。
- FastAPI 启动**只校验**：schema 存在、5 张表存在、只读探测；**不执行任何 DDL/迁移**。校验失败 → 告警；若开关为 langgraph 则建 Run 返回 503（明确报错，不静默降级）。
- 断言：`public` 内**不得**出现 `checkpoint%`；新表必须全部位于 `langgraph`。
- 已知限制：官方"可配置 schema"仍为开放需求（langgraph#7345），故必须用 `search_path` 实现隔离并**显式断言**。

### C.9 业务表写入面（不改结构）

`workflow_run{status, final_report, summary_metrics, related_graph_snapshots}` · `workflow_session{status,title,last_brief}` · `workflow_step_run{status,input_payload,output_payload,latency_ms,graph_snapshot_id,prompt_version,used_fallback,skipped}` · `graph_snapshot{新增行}` · `chat_session`（仅建会话时的影子行）。
**禁止**任何 UPDATE/DELETE 作用于历史行；P0b 只做两列加法。

---

## D. 端到端与故障测试矩阵

### D-1 用例总表

| ID | 场景 | 环境 | 通过判据 |
|---|---|---|---|
| E2E-1 | 同 brief 双引擎等价 | 本地影子库 + 假 LLM/假 Neo4j | 按 §D-2 规范化规则**逐项相等** |
| E2E-2 | 真实链路（真 LLM + 真 Neo4j 副本） | 隔离 | 按 §D-3 归因比较通过；快照数与同 brief 的 legacy 实测值相等（可为 0） |
| E2E-3 | 接口契约与历史回放 | 生产**只读（仅 GET）** | 10 条 run 的 JSON sha256 与基线一致；`/api/rnd/*` 状态码与结构不变 |
| E2E-4 | 其他工作台不受影响 | 生产**只读（仅 GET）** | `/api/health`、`/api/admin/overview`、`/api/admin/workflow-logs`、`/api/constitution/types`、`GET /api/constitution/questionnaire` 状态码与结构不变 |
| CFG-1 | 某 Agent 提示词停用 | 隔离 | `skipped=true`、`used_fallback=true`、`latency_ms=0`、下游键集完整；两引擎一致 |
| CFG-2 | 提示词改写 | 隔离 | `prompt_version=v{n}`；版本历史与回滚后取值一致 |
| CFG-3 | `master_control_final` 无独立模板 | 隔离 | 回退 `master_control` 模板；`prompt_version` 与 legacy 相同 |
| CFG-4 | 管理端参数钳制与版本回滚 | 隔离 | 与迁移前行为一致（管理端 dry-run 正常） |
| FB-1 | LLM 返回空/结构不匹配 | 隔离 | 走兜底：`used_fallback=true`、键集=兜底契约；两引擎一致 |
| FB-2 | LLM 抛异常/超时/402 | 隔离 | 与 legacy 实测行为一致（`generate_structured_output` 内部捕获 → 兜底，不使整 Run 失败） |
| FB-3 | 图谱 0 命中 | 隔离 | 快照数 = 0 且与 legacy 一致 |
| FI-1 | 两 Worker 并发领取同一 Run | 隔离 | 仅一方取得锁并执行；另一方 WARN 放弃且 **Run 状态不变**；无重复 `(run_id, agent_key)` |
| FI-2 | 节点提交后、Checkpoint 写入前崩溃 → 手动恢复 | 隔离 | 恢复后该节点 `reused=true`、无重复 LLM 调用与重复行；最终完成 |
| FI-3 | Checkpoint 写入失败 | 隔离 | **已提交 StepRun 保留**；Run=`failed` + 骨架；无重复步骤；无悬空引用（`graph_snapshot_id` 均可 join）；不自动重试 |
| FI-4 | 进程重启后 Run 停 `running` | 隔离 | sweep（显式开启）仅标 `failed`，**不自动续跑** |
| FI-5 | 重复投递/重复点击 | 隔离 | 受租约与幂等守卫保护；不产生第二次执行 |
| FI-6 | PG 连接中断/重连 | 隔离 | checkpointer 池自愈；节点失败按 W2 处理 |
| FI-7 | schema/表缺失（严禁自动建表） | 隔离 | 启动告警且不建表；建 Run 返回 503 明确报错 |
| HIST-1 | 历史 Run 不可变 | 生产只读 | 行数 + 关键列校验和 + 回放哈希三者与 P0a 基线一致 |
| OPS-1 | 开关切换与配置回滚 | 生产（审批） | 写入后 ≤15s 生效；恢复旧值/删行即回退，无需重启 |
| OPS-2 | 依赖安装前后 | 生产（审批） | `pip freeze` 差异**仅新增** 3 项，无版本变动 |
| OPS-3 | 日志脱敏 | 生产（审批） | 新增日志不含问题原文/用户名/邮箱/密钥/令牌 |

> **FI-1…FI-7 只在本地影子库/隔离环境执行**；生产只跑 E2E-3、E2E-4、HIST-1、OPS-*。
> `POST /api/chat/.../messages/stream`（写 `chat_message`/`qa_trace`）与所有写库端点**一律归入隔离环境测试**，不得列入生产只读验收。

### D-2 规范化比较规则（Mock）

**忽略字段**（永不作相等要求）：`id`、`run_id`、`session_id`、`step_id`、`graph_snapshot_id`、`created_at`、`updated_at`、`latency_ms`（改为量级区间）、LLM 回显字段（如 `_kb5_echo`）、任何绝对时间。

**比较项**：①六步 `agent_key`/`sequence` 序列；②每步 `input_payload` 键集与取值（除忽略字段）；③每步 `output_payload` 键集与业务值、列表顺序（组成/君臣佐使/替代候选顺序参与比较）；④`used_fallback`/`skipped` 逐元素；⑤快照**数量与"由哪几步产生"**（不比 id）；⑥`final_report` 结构与业务值；⑦`summary_metrics` 各计数。

### D-3 真实模型归因比较（E2E-2）

| 场景 | legacy 实测 | langgraph 实测 | 判定 |
|---|---|---|---|
| 双引擎均正常 | 成功、无兜底 | 成功、无兜底 | 通过（比结构/约束/来源） |
| 双引擎均兜底 | 兜底 | 兜底 | **通过**（同因同果，非迁移缺陷） |
| legacy 兜底 / langgraph 正常 | 兜底 | 正常 | 通过（记为改善，留证） |
| legacy 正常 / langgraph 兜底 | 正常 | 兜底 | **不通过**：须复现 ≥2 次并定位（LLM 抖动 / 超时阈值 / payload 差异），归因后再判 |
| 任一失败（异常） | — | — | 不通过，按 legacy 失败语义核对 |

补充：两引擎使用**相同 brief 输入**；统计每步远程调用次数与重试日志行数；文字值仅做定性抽查，不设阈值。

### D-4 调用与重试统计口径

- 远程生成调用：**上限 6 次/Run**（不含 brief，brief 为本地解析）。
- 重试：`_post_json_with_retry` 只对连接建立失败与 `{429,500,502,503,504}` 重试（读/写超时不重试）；以日志行 `LLM 返回可重试状态码（第 x/y 次）`、`LLM 连接失败（第 x/y 次）` 统计，**单独计数，不并入 6 次**。

---

## E. 生产发布、灰度与回滚（全部待批准）

### E.1 备份与基线（发布前，A1 前提）

```
backups/pre-langgraph-<ts>/
├── app/  scripts/  requirements.txt      # 旧后端整树拷贝（回滚用）
├── .env                                   # 0600 副本（预期其后不改动）
├── pip-freeze-before.txt
├── pg/neo4j_agents.schema-only.sql        # 结构快照
└── baseline/                              # P0a 行数、校验和、10 条 run 回放 JSON
```

另记录 `system_config.rnd_engine` 旧值（或"不存在"）作为配置回滚依据。**Neo4j 不做 dump**（本迁移只读图谱）。

### E.2 版本固定

`langgraph`、`langgraph-checkpoint-postgres`、`psycopg-pool` 一律 `==` 固定并成对核对兼容性（源码含 major0/minor<5 告警规则）；禁止 `>=`/`~=`；Python 3.11、PostgreSQL 15.19、Neo4j 5.26 保持现状；临时 venv 试解产物 `pip-freeze-diff.txt` 归档。

### E.3 数据库变更（只增）

仅 5 类：`langgraph` schema、库自带 4 表、`run_engine`、`run_lock`、`workflow_step_run` 两列（P0b），外加两个 marker 行。**不改**既有表结构/约束/索引/数据；**不回填**历史行。

### E.4 灰度任务类别与覆盖门槛（绑定真实实体）

**数据版本指纹**：86,484 节点 / 207,356 关系（2026-10-14 实测）。

| 类别 | 绑定输入（真实图谱） | 预期结果（可判定） |
|---|---|---|
| **T1 名方同源化** | 问："把四君子汤改造成药食同源代餐粉"；`Formula{formula_name:'四君子汤'}`：herbs=[炙甘草,人参,白术,茯苓,甘草]、role_herbs=[炙甘草,茯苓,白术,人参]、sources=[方剂学各论,《太平惠民和剂局方》宋]（检索亦可能命中 `乌蝎四君子汤`，含川乌/全蝎） | `kb5_formula_context` 非空且含上述字段；`original_formula.name` ∈ 命中集合；君臣佐使来自 `role_herbs`；非药食同源药味走替代或剔除说明（含川乌时须标注风险） |
| **T2 无 KB5 命中** | 问："研发一款助眠代餐粉，只用普通食品原料"（实测 Formula 名含"助眠/睡眠/代餐"者=0） | `kb5_formula_context` 为空；方剂由候选药食同源药材生成；`original_formula` 为空且不虚构原方 |
| **T3 替代映射密集** | 问："用供应更稳定的原料替换配方中的高价原料"；`人参 → 15 条 CAN_REPLACE`、`白术 → 15 条`、`甘草 → 0`、`茯苓 → 0` | 替换项必须有 `CAN_REPLACE` 支撑并展示 KB4 原始分与综合可信度；`甘草/茯苓` 须明确"不建议替代"，不得虚构候选 |
| **T4 人群/风味约束** | 问："给上班族做一款不苦的补气饮品"；CDB1：ConsumerProfile=106、Flavor=34、Effect=1570 | 人群画像字段来自 `ConsumerProfile/Segment`；风味字段引用已存在 Flavor；禁忌/合规字段齐备 |

**门槛**：4 类各 ≥1 次成功、总计 ≥4 次成功、0 failed；每次 6 步；快照数与同 brief 的 legacy 基线**相等**（含 0）；**T1 必须包含上次失败过的那道题**；观察 ≥24h（含一次失败重试场景）后才申请全局切换。

### E.5 发布通道（禁止明文凭据）

- 上传改用 **SSH 密钥或会话级环境变量**（`paramiko` + agent/key，或密码取自进程环境变量，仅存内存）。
- **不在仓库落地含密码的新脚本**；上传/校验逻辑以临时脚本执行、用后删除，且先自查 `grep -nE "(PASSWORD|TOKEN|SECRET)\s*=\s*[\"'][^\"']+"` 为空。
- 现存 `deploy_*.py` / `push_*.py` 内的明文口令列为卫生项（§E.10），建议轮换（A8）。

### E.6 回滚（**不含 DROP SCHEMA**）

| 编号 | 触发 | 操作 | 影响/耗时 |
|---|---|---|---|
| **R1** | 新引擎行为异常 | 恢复 `system_config.rnd_engine` 旧值（或删除该行） | ≤15s 生效、无需重启；在跑 Run 按 pin 跑完 |
| **R2** | 代码级问题 | 覆盖 `backups/pre-langgraph-<ts>/{app,scripts,requirements.txt}` + 按需回退依赖 + 面板脚本重启 | 数秒停机 |
| **R3** | 配置项异常 | 恢复 `system_config` 对应行；复核 `.env` 未变（本阶段生产**不新增 env 键**，故 `.env` 无需回滚） | 即时 |

> `DROP SCHEMA langgraph` **不是回滚手段**：清理新引擎状态须单独审批、先导出备份，并确认无 Run 需要恢复。

### E.7 测试环境数据脱敏

- P2 仅使用**图谱 dump 副本**（业务数据，视为敏感，禁止入 git；`neo4j_backups/` 已在忽略清单）。
- 本地 PG **不恢复**生产 `app_user`/`auth_session`/`captcha_code`/`chat_message`；影子库由脚本自建并只造合成用户。
- 若确需排障而拷贝生产行：对 `app_user.email/password_hash`、`auth_session.token_hash/ip/user_agent`、`captcha_code.*`、`chat_message.content` 做掩码；副本用后即删并留删除记录。

### E.8 运行历史留存

- 历史 Run/Step/Snapshot **只读**：发布前后比对行数 + 关键列校验和 + 回放 JSON sha256（HIST-1）。
- `langgraph` 状态保留策略：阶段一观察期内**全留、不清理**（如需清理单列审批）。

### E.9 日志脱敏

- 新增日志字段白名单：`run_id`、`session_id`（uuid）、`engine`、`agent_key`、`sequence`、`latency_ms`、`used_fallback`、`skipped`、`reused`、`snapshot_id?`、`status`。
- **禁止**记录：问题原文、brief 内容、用户名/邮箱/IP、`Authorization`、密钥、完整 payload；异常堆栈保留但不得附带请求体。
- DoD：新日志行的 grep 审计（OPS-3）。

### E.10 卫生项（P5，独立审批 A8）

1. 清理未跟踪部署脚本中的明文口令（转密钥/环境变量），并**建议轮换**该 SSH 口令。
2. 归档临时 venv 试解产物与依赖 diff。
3. 建立 `langgraph` schema 体积与租约过期告警（SQL 检查项纳入 `DEPLOY.md` 巡检清单）。

### E.11 审批点（生产动作待批准，逐项确认）

| 编号 | 动作 | 写生产库 | 用户影响 |
|---|---|---|---|
| **A0** | P0a 只读审计 | 否 | 无（只读，无需批准） |
| **A1** | P0b 最小补丁（两列 DDL + marker） | 是（加法） | 无（不重启） |
| **A2** | 安装 3 个新依赖到生产 venv | 否 | 无 |
| **A3** | 引导 `langgraph` schema/表 + 写 `rnd_engine_migrated_at` | 是（新增 schema + 1 行） | 无 |
| **A4** | 上传最小文件集 + 重启（须无在跑 Run） | 否 | 数秒中断 |
| **A5** | legacy 基线运行 1 次（真实 LLM 计费） | 是（新增行） | 无 |
| **A6** | canary 开关 → 全局切换 | 是（配置行） | 白名单 → 全体 |
| **A7** | 拉取生产 Neo4j dump 副本到本地（只读导出） | 否 | 无 |
| **A8** | 部署脚本凭据清理与口令轮换 | 否 | 无 |

---

## F. 每阶段 DoD 验收标准

**P0a 只读审计**：①差异清单 = 8 文件且 74 文件 MATCH 有记录；②DB 结构/数据基线落盘；③10 条 run 回放 JSON sha256 归档；④无在跑 Run 与磁盘/连接数记录；⑤全过程无 DDL/DML/重启。

**P0b 最小补丁**：①两列存在且默认 FALSE；②marker `rnd_engine_metrics_started_at` 已写入；③行数与关键列校验和与补丁前一致；④`/api/health` 200；⑤旧应用行为零变化（历史回放哈希不变）。

**P1 本地实现 + Mock**：①E2E-1、CFG-1..4、FB-1..3 **0 差异**；②新表 100% 落在 `langgraph`，`public` 无 `checkpoint%`；③FI-1/FI-2/FI-3/FI-4 通过；④legacy 路径 step 行与基线 fixture 完全一致；⑤Mock 阶段零外网调用且可反复执行。

**P2 隔离真实运行**：①E2E-2 按 §D-3 归因比较通过；②生产 PG/Neo4j 零写入证据；③数据脱敏执行记录；④与 legacy 基线耗时同量级（单步 9–41s 参考）。

**P3 发布准备与发布**：①备份包完整且回滚演练完成（本地模拟）；②依赖 diff 仅新增 3 项；③schema 引导后表清单 = 5 且断言通过；④最小文件集上传逐文件 sha256 MATCH；⑤重启后 `/api/health` 200；⑥E2E-3/E2E-4/HIST-1 全绿；⑦legacy 基线运行成功并留指标。

**P4 canary**：①T1–T4 门槛达标（≥4 成功、0 failed）；②每次 6 步、快照数与基线一致；③pin 行与 checkpoint 行存在、无重复 step 行；④pin 完备性校验 = 0；⑤前端渲染与导出无异常；⑥观察 ≥24h 无异常；⑦R1 回滚演练一次并复切。

**P5 全局切换与收尾**：①观察 72h 指标不劣于 legacy（成功率、单步耗时、兜底率）；②文档三处更新完成；③卫生项完成或已排期；④复核"DROP SCHEMA 未出现在任何回滚流程中"。

---

## 附录 P0a 基线（实测 2026-10-14）

### A1 三方一致性

- 本地 = GitHub `origin/codex/rnd-fix-2026-08-26`，代码 HEAD `4aba4e24`；生产约等于 `d5936f1c` + P18 上线批次。
- 逐文件 sha256（排除 `_vendor`/`*.bak-*`/`uploads`/`__pycache__` 噪声）：`MATCH=74 DIFF=8 SRV_ONLY=0 LOC_ONLY=3`。
- 差异 8 个文件：**新增** `backend/app/services/agent_config_service.py`；**内容不同** `backend/.env.example`、`backend/app/api/routes.py`、`backend/app/core/config.py`、`backend/app/db/init_db.py`、`backend/app/db/models.py`、`backend/app/repositories/postgres_repository.py`、`backend/app/services/deepseek_client.py`、`backend/app/services/rnd_workflow_orchestrator.py`。
- 服务器独有：17 个 `*.bak-<ts>`、`backend/uploads/avatars/*.png`；本地独有：`backend/_vendor/**`（约 2500 文件）、`backend/scripts/run_backend.ps1|stop_backend.ps1`。

### A2 生产结构基线

PostgreSQL **15.19**；库 `neo4j_agents`（业务用户 `neo4j_agents`，非超管）；schema 仅 `public`；18 张业务表；**无** `agent_config_revision`；**无** `checkpoint%` 表；`workflow_step_run` **无** `used_fallback` / `skipped` 列（列清单：id, run_id, agent_key, sequence, status, input_payload, output_payload, latency_ms, graph_snapshot_id, prompt_version, created_at, updated_at）。

### A3 生产数据基线

| 表 | 行数/说明 |
|---|---|
| `workflow_run` | 10（completed 9 / failed 1；最近一次 2026-09-01 17:32） |
| `workflow_step_run` | 56（全部 completed；master_control 10、formula_generation 10、其余各 9） |
| `graph_snapshot` | 45（37 条被研发步骤引用 + 8 条属知识问答工作台） |
| `workflow_session` | 10（与影子 `chat_session` 同 id，10/10 命中） |
| `chat_session` | 16 |
| `app_user` | 4 |
| `auth_session` | 53（其中 51 条已过期） |
| `import_batch` | 0 |

legacy 单步耗时实测：**9–41s**（`master_control_final` 最慢：avg 28.7s / max 41.6s；`efficacy_prediction` 最快：avg 11.9s）。

### A4 图谱指纹（只读）

**86,484 节点 / 207,356 关系**；`Compound=0`；批次标记残留 0。

标签分布：ConsumerReview 63522、Symptom 11125、Formula 3155、ConsumerSegment 3033、Source 2063、Effect 1570、Herb 865、Taboo 419、ComplianceRule 228、Product 192、ConsumerProfile 106、EffectCategory 51、RiskExpression 46、Flavor 34、ConstitutionQuestion 30、NatureFlavor 22、Meridian 14、ConstitutionType 9。

### A5 灰度绑定实体（真实存在）

- T1：`四君子汤` herbs=[炙甘草,人参,白术,茯苓,甘草]、role_herbs=[炙甘草,茯苓,白术,人参]、sources=[方剂学各论,《太平惠民和剂局方》宋]；同检索亦命中 `乌蝎四君子汤`（川乌、全蝎）。
- T3：`人参` 15 条 `CAN_REPLACE`、`白术` 15 条、`甘草` 0、`茯苓` 0。
- T2：Formula 名含"助眠/睡眠/代餐" = 0。
- T4：ConsumerProfile 106、Flavor 34、Effect 1570。

### A6 运维事实

- 宝塔 nginx **无 systemd 单元**（`systemctl is-active nginx` = inactive）：只用 `/www/server/nginx/sbin/nginx -t && -s reload`。
- 后端重启走面板脚本 `/www/server/python_project/vhost/scripts/neo4j-agents-backend_cmd.sh`。
- `backups/pre-*` 回滚点仅保留 **7 天**（`find -mtime +7 -delete`）；每日备份仅覆盖 `neo4j_agents` 库 + Neo4j dump + `.env`。
- 站点 vhost `118.24.185.45.conf`：3 个 server 块（443 mmfh.com.cn/www、80 同域名 301、80 IP 直连）；`/api` 反代 127.0.0.1:8000；`client_max_body_size 50m`；敏感文件屏蔽正则。

### A7 本地环境基线

- PostgreSQL 17.9（在建，库 `postgres`，19 张表含 `agent_config_revision`）。
- **Neo4j 未安装/未运行**（7687/7474 均不可连）；`neo4j_backups/` 有 2 份旧 JSON（2026-06）。
- 前端 dev 代理 → `http://127.0.0.1:8000`；本地 `.env` 无 `NEO4J_*` 键；DeepSeek 旧 key 仍有效（HTTP 200）。
- 无 pytest 测试套件：仅有未跟踪 `.tmp-*/` 脚本与 `scripts/load_test.py`。

---

## 附：阶段一非目标

并行/扇出执行、自适应调度、证据核验与反馈修正、Human-in-the-loop 中断、节点级重试策略、前端与 `/api/rnd/*` 契约改动、Neo4j 写入、知识问答/体质等模块改造、引入外部可观测服务、历史数据迁移或回填、生产自动续跑。
