"""LangGraph 研发协同串行六步编排层（阶段一，默认引擎仍为 legacy）。

设计约束（《LangGraph 研发协同迁移实施计划 v2.1》§B.1/§C）：
- 六个 Node 只做胶水：包装既有 ``RnDWorkflowOrchestrator`` 的 ``_run_*`` / ``_run_step``，
  不复制组方、检索、兜底与报告组装逻辑；
- 图由 ``AGENT_STEP_DEFS.sequence`` 派生，编译期断言"必须线性"，不引入分支/并行/重试；
- 运行依赖（RunContext）经 ``runtime.context`` 传入，不进 State；
- 包级导出仅 build/run；import 期不触碰 langgraph / psycopg（两个可选依赖按需延迟导入）。
"""

from app.services.rnd_graph.graph import build_rnd_graph, step_keys
from app.services.rnd_graph.runner import run_langgraph

__all__ = ["build_rnd_graph", "step_keys", "run_langgraph"]
