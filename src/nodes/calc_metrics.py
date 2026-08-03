"""
计算节点 — 节点④（Agent 节点）

LLM 拿到已验证的数据后，自主决定调用哪些 calculator 工具，
计算衍生财务指标，供下游 generate_report 使用。
"""
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage

from src.state.research_state import ResearchState
from src.models.main_model import main_llm
from src.prompts.calc_prompt import CALC_PROMPT
from src.tools.calculator import (
    calc_pe_ratio,
    calc_pb_ratio,
    calc_roe,
    calc_growth_rate,
)

TOOLS = [calc_pe_ratio, calc_pb_ratio, calc_roe, calc_growth_rate]
llm_with_tools = main_llm.bind_tools(TOOLS)
TOOL_MAP: Dict[str, Any] = {t.name: t for t in TOOLS}


def _format_data_prompt(data: dict) -> str:
    """把 extracted_data 转成 LLM 可读的字符串，只列出有值的字段。"""
    lines = []
    for key, value in data.items():
        if value is not None:
            if isinstance(value, float):
                lines.append(f"  {key}: {round(value, 4)}")
            else:
                lines.append(f"  {key}: {value}")
    return "\n".join(lines) if lines else "（暂无数据）"


def _format_verified_prompt(verified_items: list) -> str:
    """把 verified_items 转成 LLM 可读的验证结果说明。"""
    lines = []
    for item in verified_items:
        pub = item.get("public_value")
        conf = item.get("confidence", "unverified")
        if pub is not None and conf != "unverified":
            name = item.get("metric_name", "?")
            rep = item.get("report_value")
            lines.append(f"  {name}: 研报={rep}, 公开数据={pub}, 置信度={conf}")
    if not lines:
        return ""
    return "以下数据已经过联网验证，请优先使用高置信度的公开值：\n" + "\n".join(lines)


async def calc_metrics(state: ResearchState) -> dict:
    """Agent 节点主入口"""

    data: dict = state.get("extracted_data") or {}
    if not data:
        return {"calculated_metrics": {"raw": {}, "derived": {}, "ai_summary": "无数据可供计算"}}

    available_data = _format_data_prompt(data)
    verified_text = _format_verified_prompt(state.get("verified_items") or [])
    prompt = CALC_PROMPT.format(available_data=available_data, verified_data=verified_text)

    response = await llm_with_tools.ainvoke([HumanMessage(content=prompt)])

    tool_calls: List[dict] = getattr(response, "tool_calls", []) or []
    ai_summary: str = response.content if hasattr(response, "content") else ""

    derived: Dict[str, dict] = {}
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool = TOOL_MAP.get(tool_name)

        if tool is None:
            continue

        try:
            result = await tool.ainvoke(tool_args)
            derived[tool_name] = {"value": result, "source": "calculated"}
        except Exception as e:
            derived[tool_name] = {"value": None, "source": "calculated", "error": str(e)}

    raw = {}
    for field in ["revenue", "net_profit", "eps", "revenue_growth",
                  "net_profit_growth", "pe_ratio", "pb_ratio", "roe"]:
        raw[field] = data.get(field)

    return {
        "calculated_metrics": {
            "raw": raw,
            "derived": derived,
            "ai_summary": ai_summary.strip(),
        }
    }
