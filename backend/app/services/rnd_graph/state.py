"""RndGraphState：LangGraph 图的 State 定义（v2.1 §C.1）。

硬约定：
- 六个 Agent **各自一个独立字段**，互不覆盖；**不得**出现 ``steps`` / ``snapshots`` 之类的聚合键
  （聚合键会被后续节点整体覆盖），也**不得**使用 reducer（``Annotated[..., reducer]``）。
- 只放 JSON 兼容数据（会写入 checkpoint）。
- 运行依赖（RunContext）放 ``runtime.context``，不入 State。
- ``run_id`` / ``session_id`` 只读；``error`` 供失败语义留痕。
- 旧 run_id / step_id / graph_snapshot_id / 时间戳不参与任何等价比较（v2.1 §0.2 修订 2）。
"""

from typing import Any, TypedDict

#: 六个 Agent 的 State 字段名（与 ``AGENT_STEP_DEFS.agent_key`` 一一对应，图构建时断言相等）
AGENT_STATE_KEYS: tuple[str, ...] = (
    "master_control",
    "formula_generation",
    "efficacy_prediction",
    "flavor_prediction",
    "replacement_mapping",
    "master_control_final",
)

#: 输入字段（只读，不参与 Agent 输出）
INPUT_STATE_KEYS: tuple[str, ...] = ("run_id", "session_id", "question", "brief")

#: 全部 State 键（不含 error 之外的非业务键）
EXTRA_STATE_KEYS: tuple[str, ...] = ("error",)

STATE_KEYS: tuple[str, ...] = INPUT_STATE_KEYS + AGENT_STATE_KEYS + EXTRA_STATE_KEYS


class RndGraphState(TypedDict, total=False):
    """串行六步图 State。

    ``total=False``：节点只返回自己的那一个字段；LangGraph 对该字段做整体替换（无 reducer 也安全）。
    """

    run_id: str
    session_id: str
    question: str
    brief: dict[str, Any]
    master_control: dict[str, Any]
    formula_generation: dict[str, Any]
    efficacy_prediction: dict[str, Any]
    flavor_prediction: dict[str, Any]
    replacement_mapping: dict[str, Any]
    master_control_final: dict[str, Any]
    error: str | None


def initial_state(*, run_id: str, session_id: str, question: str, brief: dict[str, Any]) -> RndGraphState:
    """构造首次执行的初始 State（只含输入字段；六个 Agent 字段由节点各自写入）。"""
    return {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "brief": brief,
    }


def json_incompatible_paths(value: Any, *, path: str = "$") -> list[str]:
    """返回非 JSON 兼容值的路径列表（只报告，不改数据、不抛异常）。

    供 runner 在 invoke 前做一次廉价自检：State 必须可 JSON 序列化（checkpoint 会落盘）。
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return []
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            if not isinstance(key, str):
                paths.append(f"{path}.<non-str-key:{type(key).__name__}>")
                continue
            paths.extend(json_incompatible_paths(item, path=f"{path}.{key}"))
        return paths
    if isinstance(value, (list, tuple)):
        paths = []
        for index, item in enumerate(value):
            paths.extend(json_incompatible_paths(item, path=f"{path}[{index}]"))
        return paths
    return [f"{path}:{type(value).__name__}"]
