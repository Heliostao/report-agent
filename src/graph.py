"""
LangGraph 工作流定义

流程：
  START → router_node → chat_node → END
                      → parse_document → extract_data → verify_data
                        → calc_metrics → generate_report → review_quality
                          → END（通过）
                          → generate_report（不通过，最多 1 次重试）
"""
import re

from langgraph.graph import START, END, StateGraph
from src.state.research_state import ResearchState
from src.nodes.parse_document import parse_document
from src.nodes.extract_data import extract_data
from src.nodes.verify_data import verify_data
from src.nodes.calc_metrics import calc_metrics
from src.nodes.generate_report import generate_report
from src.nodes.review_quality import review_quality
from src.nodes.chat import chat_node
from src.memory.short_term import get_checkpointer
from src.models.assist_model import assist_llm
from src.prompts.chat_prompt import ROUTER_PROMPT

workflow = StateGraph(ResearchState)


async def router_node(state: ResearchState) -> dict:
    """用 assist_llm 判断用户意图是闲聊还是研报分析。"""
    file_path = state.get("file_path")
    user_message = state.get("user_message", "")

    if file_path:
        return {"intent": "research"}

    if not user_message.strip():
        return {"intent": "chat"}

    prompt = ROUTER_PROMPT.format(user_message=user_message[:1000])
    resp = await assist_llm.ainvoke(prompt)
    raw = resp.content.strip()
    m = re.search(r"\b(chat|research)\b", raw, re.IGNORECASE)
    intent = m.group(1).lower() if m else "research"
    return {"intent": intent}


def route_intent(state: ResearchState):
    intent = state.get("intent", "research")
    if intent == "chat":
        return "chat_node"
    return "parse_document_node"


workflow.add_node("router_node", router_node)
workflow.add_node("chat_node", chat_node)
workflow.add_node("parse_document_node", parse_document)
workflow.add_node("extract_data_node", extract_data)
workflow.add_node("verify_data_node", verify_data)
workflow.add_node("calc_metrics_node", calc_metrics)
workflow.add_node("generate_report_node", generate_report)
workflow.add_node("review_quality_node", review_quality)


def test_quality(state: ResearchState):
    """审核结果路由：通过 → END, 不通过且未超限 → 重试, 超限 → END"""
    if state.get("review_passed"):
        return END
    if state["review_retry_count"] > 1:
        return END
    return "generate_report_node"


def route_after_generate(state: ResearchState):
    """报告生成后路由：首次 → 审核, 重写 → END"""
    if state.get("review_retry_count", 0) >= 1:
        return END
    return "review_quality_node"


workflow.add_edge(START, "router_node")
workflow.add_conditional_edges("router_node", route_intent, {
    "chat_node": "chat_node",
    "parse_document_node": "parse_document_node",
})
workflow.add_edge("chat_node", END)
def route_after_parse(state: ResearchState):
    """文档解析后路由：有错误则中止，成功则继续提取。"""
    if state.get("error"):
        return END
    return "extract_data_node"


workflow.add_conditional_edges("parse_document_node", route_after_parse, {
    "extract_data_node": "extract_data_node",
    END: END,
})
workflow.add_edge("extract_data_node", "verify_data_node")
workflow.add_edge("verify_data_node", "calc_metrics_node")
workflow.add_edge("calc_metrics_node", "generate_report_node")
workflow.add_conditional_edges("generate_report_node", route_after_generate, {
    "review_quality_node": "review_quality_node",
    END: END,
})
workflow.add_conditional_edges("review_quality_node", test_quality)

_checkpointer = get_checkpointer()
HAS_CHECKPOINTER = _checkpointer is not None
graph = workflow.compile(checkpointer=_checkpointer) if _checkpointer else workflow.compile()
