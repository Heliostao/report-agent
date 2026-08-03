"""聊天回复节点 — 纯闲聊 + 历史研报查询。Checkpointer 管理对话记忆。"""
import re
from src.state.research_state import ResearchState
from src.models.assist_model import assist_llm
from src.prompts.chat_prompt import CHAT_PROMPT, CHAT_WITH_DB_PROMPT, CHAT_SUB_INTENT_PROMPT
from src.memory.long_term import search_reports_by_company, get_recent_reports

_MAX_HISTORY_MSGS = 10  # 最多保留最近 10 条消息，防止 prompt 膨胀


def _format_history(messages: list[dict]) -> str:
    if not messages:
        return "（暂无）"
    recent = messages[-_MAX_HISTORY_MSGS:]
    lines = []
    for msg in recent:
        label = "用户" if msg.get("role") == "user" else "助手"
        lines.append(f"{label}：{msg.get('content', '')}")
    return "\n".join(lines)


async def _classify_sub_intent(user_message: str, history_text: str) -> str:
    """用 assist_llm 判断聊天子意图：chat / query_history"""
    prompt = CHAT_SUB_INTENT_PROMPT.format(
        user_message=user_message[:500],
        history=history_text[:1000],
    )
    resp = await assist_llm.ainvoke(prompt)
    raw = resp.content.strip().lower()
    m = re.search(r"\b(query_history|chat)\b", raw)
    return m.group(1) if m else "chat"


def _search_db(user_message: str) -> list[dict]:
    """从 PostgreSQL 搜索相关的历史研报记录。

    策略: 先取最近所有报告的公司名列表，匹配用户消息中提到的公司；
          如果没匹配到，用 get_recent_reports 返回最近 5 条作为兜底。
    """
    # 尝试从用户消息中匹配已知公司
    recent = get_recent_reports(50)
    known = [r for r in recent if r.get("company_name")]
    matched = []
    for r in known:
        name = r.get("company_name", "")
        if name and name in user_message:
            matched.append(r)

    if matched:
        # 精确匹配到了，返回匹配结果
        return matched[:5]

    # 没有精确匹配，用模糊搜索
    results = search_reports_by_company(user_message, limit=5)
    if results:
        return results

    # 完全搜不到，返回最近报告作为兜底提示
    return get_recent_reports(5)


def _format_db_records(records: list[dict]) -> str:
    """将数据库记录格式化为可读文本。"""
    if not records:
        return "（数据库无历史记录）"
    lines = []
    for r in records:
        name = r.get("company_name", "未知")
        code = r.get("stock_code", "")
        rating = r.get("rating", "")
        target = r.get("target_price")
        one_liner = r.get("one_liner", "")
        created = r.get("created_at", "")
        parts = [f"- 公司：{name}"]
        if code:
            parts.append(f"代码：{code}")
        if rating:
            parts.append(f"评级：{rating}")
        if target is not None:
            parts.append(f"目标价：{target}元")
        if one_liner:
            parts.append(f"摘要：{one_liner}")
        if created:
            parts.append(f"分析时间：{created}")
        lines.append("  ".join(parts))
    return "\n".join(lines)


async def chat_node(state: ResearchState) -> dict:
    user_message = state.get("user_message", "")
    messages = state.get("messages", [])
    history_text = _format_history(messages)

    # Step 1: 判断子意图
    sub_intent = await _classify_sub_intent(user_message, history_text)

    # Step 2: 根据意图选择 prompt
    if sub_intent == "query_history":
        # 搜索 PostgreSQL
        db_records = _search_db(user_message)
        db_text = _format_db_records(db_records)
        prompt = CHAT_WITH_DB_PROMPT.format(
            db_records=db_text,
            history=history_text,
            user_message=user_message,
        )
    else:
        prompt = CHAT_PROMPT.format(
            user_message=user_message,
            history=history_text,
        )

    resp = await assist_llm.ainvoke(prompt)

    # 追加本轮对话到历史
    new_messages = list(messages)
    new_messages.append({"role": "user", "content": user_message})
    new_messages.append({"role": "assistant", "content": resp.content})

    return {"chat_reply": resp.content, "messages": new_messages}
