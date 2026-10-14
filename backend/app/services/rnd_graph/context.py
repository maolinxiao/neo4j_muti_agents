"""RunContext：LangGraph 运行依赖容器（v2.1 §C.1/§C.7）。

- 经 ``runtime.context`` 传给每个节点，**不进 State**（State 只放 JSON 兼容数据）。
- 每个节点用 ``session_factory()`` 自开短会话，并在 ``finally`` 关闭；**不跨节点/线程共享 Session**。
- Neo4j driver 与 httpx 客户端本身是连接池对象，可安全共享（只读语义）。
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RunContext:
    """一次 langgraph Run 的运行依赖。

    ``session_factory``：返回一个新的 SQLAlchemy ``Session``（调用方负责 close）。
    ``neo4j_factory``：返回一个新的 ``Neo4jRepository``（内部共用进程级 driver，close 为 no-op）。
    ``llm_client``：``DeepSeekClient`` 或等价对象（线程安全池）。
    ``owner_token``：Run 级租约锁的持有者标识（``run_lock.owner``）。
    """

    session_factory: Callable[[], Any]
    neo4j_factory: Callable[[], Any]
    llm_client: Any
    owner_token: str
    run_id: str = ""
    session_id: str = ""
    extras: dict[str, Any] = field(default_factory=dict)
