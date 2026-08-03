"""
短期记忆 — MemorySaver Checkpointer（进程内存）

在 LangGraph 中，短期记忆 = Checkpointer。
每个节点执行前后自动持久化 State，支持中断恢复和审计回溯。

使用 MemorySaver 而非 RedisSaver，因为当前版本的 RedisSaver 未实现
异步接口（aget_tuple），而我们的 graph 节点均为 async，必须走 ainvoke。
MemorySaver 的 aget_tuple 内部用 asyncio.to_thread 包装同步 get_tuple，
可在异步流程中正常工作。
"""
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer():
    """获取 MemorySaver Checkpointer，始终可用。"""
    try:
        saver = MemorySaver()
        return saver
    except Exception:
        return None
