"""线性图构建（v2.1 §B.1）。

- 节点顺序/依赖**从 AGENT_STEP_DEFS.sequence 派生**，不写死 1..6；
- 编译期断言"必须线性"：注册表必须是单链（sequence 连续、每个中间节点的 upstream 恰为前一节点、
  末节点 upstream 覆盖全部前序），且编译后的图恰好是 START→n1→n2→…→n6→END 一条链（无分支/并行）；
- 不引入分支、并行、重试策略、条件边。
"""

from typing import Any

from app.services.rnd_graph.context import RunContext
from app.services.rnd_graph.nodes import NODE_FACTORIES
from app.services.rnd_graph.state import AGENT_STATE_KEYS, RndGraphState
from app.services.rnd_workflow_orchestrator import AGENT_STEP_DEFS, AgentStepDef


class GraphShapeError(RuntimeError):
    """注册表或编译结果不满足"固定串行六步"时抛出（编译期断言）。"""


def ordered_step_defs() -> tuple[AgentStepDef, ...]:
    """按 sequence 升序返回注册表（sequence 的唯一事实来源仍是 AGENT_STEP_DEFS）。"""
    return tuple(sorted(AGENT_STEP_DEFS, key=lambda step: step.sequence))


def step_keys() -> tuple[str, ...]:
    """按执行顺序返回六个 agent_key。"""
    return tuple(step.agent_key for step in ordered_step_defs())


def assert_linear(defs: tuple[AgentStepDef, ...]) -> None:
    """编译期断言：注册表必须描述**固定串行单链**（不允许分支/并行/跳步/环）。

    判定规则：
    1. sequence 恰为连续的 1..N（执行顺序唯一且无跳号）；
    2. agent_key 唯一，且与 RndGraphState 的六个 Agent 字段一一对应；
    3. 数据依赖只能指向前序节点：``set(upstream) ⊆ 前序 keys``、``set(downstream) ⊆ 后续 keys``；
    4. 首节点无 upstream；末节点是唯一汇总点，upstream 必须覆盖全部前序节点（串行六步的既有语义）；
    5. 每个节点都有实现（NODE_FACTORIES）。
    """
    if not defs:
        raise GraphShapeError("AGENT_STEP_DEFS 为空，无法构建六步图")
    sequences = [step.sequence for step in defs]
    if sequences != list(range(1, len(defs) + 1)):
        raise GraphShapeError(f"sequence 必须是连续的 1..{len(defs)}，实际为 {sequences}")
    keys = [step.agent_key for step in defs]
    if len(set(keys)) != len(keys):
        raise GraphShapeError(f"agent_key 重复：{keys}")
    if set(keys) != set(AGENT_STATE_KEYS):
        raise GraphShapeError(
            f"AGENT_STEP_DEFS 与 RndGraphState 字段不一致：注册表={keys} state={list(AGENT_STATE_KEYS)}"
        )
    for index, step in enumerate(defs):
        previous = keys[:index]
        following = keys[index + 1 :]
        if index == 0:
            if step.upstream:
                raise GraphShapeError(f"首节点 {step.agent_key} 不应有 upstream，实际 {step.upstream}")
        elif not set(step.upstream).issubset(set(previous)):
            raise GraphShapeError(
                f"节点 {step.agent_key} 的 upstream 指向前序之外（产生环或前向依赖）：{step.upstream} ⊄ {previous}"
            )
        if not set(step.downstream).issubset(set(following)):
            raise GraphShapeError(
                f"节点 {step.agent_key} 的 downstream 指向后续之外：{step.downstream} ⊄ {following}"
            )
        if index == len(defs) - 1 and set(step.upstream) != set(previous):
            raise GraphShapeError(
                f"末节点 {step.agent_key} 的 upstream 必须覆盖全部前序节点 {previous}，实际 {step.upstream}"
            )
        if index > 0 and not step.upstream:
            raise GraphShapeError(f"节点 {step.agent_key} 缺少 upstream 声明")
        if step.agent_key not in NODE_FACTORIES:
            raise GraphShapeError(f"节点 {step.agent_key} 缺少实现（NODE_FACTORIES）")


def _assert_compiled_shape(compiled: Any, keys: tuple[str, ...]) -> None:
    """编译期断言：编译产物必须恰好是一条链（无分支/并行/环）。"""
    try:
        draw = compiled.get_graph()
        node_ids = {str(name) for name in draw.nodes}
        edges = {(str(edge.source), str(edge.target)) for edge in draw.edges}
    except Exception as exc:  # pragma: no cover - 图内省 API 变化时明确报错，不静默放过
        raise GraphShapeError(f"无法内省编译后的图，线性断言失败：{exc}") from exc

    expected_nodes = {"__start__", "__end__", *keys}
    if node_ids != expected_nodes:
        raise GraphShapeError(f"编译后节点集合异常：{sorted(node_ids)} != {sorted(expected_nodes)}")
    expected_edges = {("__start__", keys[0])}
    expected_edges.update((keys[index], keys[index + 1]) for index in range(len(keys) - 1))
    expected_edges.add((keys[-1], "__end__"))
    if edges != expected_edges:
        raise GraphShapeError(f"编译后边集合不是单链：{sorted(edges)} != {sorted(expected_edges)}")


def build_rnd_graph(*, checkpointer: Any = None, context_schema: Any = RunContext) -> Any:
    """构建并编译固定串行六步图。

    ``checkpointer``：``BaseCheckpointSaver`` 实例（生产用 langgraph schema 的 PostgresSaver；
    隔离环境可传 InMemorySaver / 异常注入用替身）。为 None 时编译成无 checkpoint 的图。
    """
    from langgraph.graph import END, START, StateGraph

    defs = ordered_step_defs()
    assert_linear(defs)
    keys = tuple(step.agent_key for step in defs)

    builder = StateGraph(RndGraphState, context_schema=context_schema)
    for step in defs:
        builder.add_node(step.agent_key, NODE_FACTORIES[step.agent_key])
    builder.add_edge(START, keys[0])
    for index in range(len(keys) - 1):
        builder.add_edge(keys[index], keys[index + 1])
    builder.add_edge(keys[-1], END)

    compiled = builder.compile(checkpointer=checkpointer)
    _assert_compiled_shape(compiled, keys)
    return compiled
