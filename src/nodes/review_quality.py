"""
质量审核节点 — 节点⑥

使用 assist_llm（独立模型，temperature=0）审核 draft_report 的质量。
对照源数据检查 5 个维度，给出通过/不通过 + 具体反馈。

审核维度：
  1. 数据准确性 —— 报告数字是否与源数据一致，有无编造
  2. 来源标注   —— 每个数字是否标注「研报数据」「已验证」「推算」
  3. 置信度披露 —— 低/未验证指标是否在报告中提醒
  4. 章节完整性 —— 7 个必选章节是否齐全，风险提示是否遗漏
  5. 格式规范   —— 是否为合法 Markdown

打回机制：
  - passed=True  → 直接 END
  - passed=False → review_retry_count <= 1 时回退到 generate_report
  - passed=False → review_retry_count > 1 时强制 END

边界情况：
  - draft_report 为空 → 短路返回不通过
  - 二次审核仍失败 → 强制接受当前版本
  - LLM 返回或解析失败 → 兜底 passed=False
"""
from typing import TypedDict

from langchain_core.messages import HumanMessage

from src.state.research_state import ResearchState
from src.models.assist_model import assist_llm
from src.prompts.review_prompt import REVIEW_PROMPT
from src.tools.verify_tools import parse_json


class ReviewResult(TypedDict):
    """审核结果"""
    passed: bool
    feedback: str


def _format_source_data(state: ResearchState) -> str:
    """将研报原文片段 + 提取数据 + 验证结果 + 衍生指标 + RAG 交叉验证
    组合为审核对照用的「源数据」。"""
    parts: list[str] = []

    cross_val = (state.get("cross_validation") or "").strip()
    if cross_val and "暂无关" not in cross_val and "无法进行交叉验证" not in cross_val:
        parts.append("## RAG 历史研报交叉验证\n" + cross_val)
    elif cross_val:
        parts.append("## RAG 交叉验证结果\n⚠️ 硬约束：历史研报库中没有任何该公司或行业的相关研报。报告中如出现「历史研报显示」等内容，一律判定为 LLM 编造，直接不通过。")

    chunks = state.get("chunks") or []
    if chunks:
        chunk_lines = ["## 研报原文片段（事实核查唯一依据）"]
        for c in chunks:
            idx = c.get("index", 0)
            text = c.get("text", "").strip()
            heading = c.get("heading", "").strip()
            if not text:
                continue
            label = f"### 片段 {idx + 1}" + (f" [{heading}]" if heading else "")
            chunk_lines.append(f"{label}\n{text}")
        parts.append("\n\n".join(chunk_lines))
    else:
        raw = (state.get("raw_text") or "").strip()
        if raw:
            parts.append(f"## 研报原文（全文）\n```\n{raw[:5000]}\n```")

    data: dict = state.get("extracted_data") or {}
    if data:
        lines = ["## 提取的结构化数据"]
        for label, key in [
            ("公司", "company_name"), ("代码", "stock_code"),
            ("行业", "industry"), ("评级", "rating"),
        ]:
            if data.get(key):
                lines.append(f"- {label}：{data[key]}")
        if data.get("target_price") is not None:
            lines.append(f"- 目标价：{data['target_price']}")
        thesis = data.get("core_thesis", "")
        if thesis:
            lines.append(f"- 核心观点：{thesis}")
        for label, key in [
            ("营收", "revenue"), ("营收增长率", "revenue_growth"),
            ("净利润", "net_profit"), ("净利润增长率", "net_profit_growth"),
            ("EPS", "eps"), ("PE", "pe_ratio"), ("PB", "pb_ratio"), ("ROE", "roe"),
            ("预测营收", "forecast_revenue"), ("预测净利润", "forecast_net_profit"),
        ]:
            val = data.get(key)
            if val is not None:
                lines.append(f"- {label}：{val}")
        risks = data.get("risk_warnings", [])
        if risks:
            lines.append("- 风险列表：")
            for r in risks:
                lines.append(f"  - {r}")
        parts.append("\n".join(lines))

    verified = state.get("verified_items") or []
    if verified:
        lines = ["## 验证结果"]
        for item in verified:
            name = item.get("metric_name", "?")
            rv = item.get("report_value")
            pv = item.get("public_value")
            conf = item.get("confidence", "unverified")
            note = item.get("discrepancy_note", "")
            if pv is not None:
                lines.append(f"- {name}：研报={rv}, 公开={pv}, 置信度={conf}, {note}")
            else:
                lines.append(f"- {name}：研报={rv}, 置信度={conf}, {note}")
        parts.append("\n".join(lines))

    calc = state.get("calculated_metrics") or {}
    derived = calc.get("derived", {})
    if derived:
        lines = ["## 衍生计算指标"]
        for tool_name, info in derived.items():
            if isinstance(info, dict) and "error" not in info:
                val = info.get("value")
                if val is not None:
                    lines.append(f"- {tool_name}：{val}（来源：推算）")
        parts.append("\n".join(lines))

    return "\n\n".join(parts) if parts else "（源数据为空）"


async def review_quality(state: ResearchState) -> dict:
    """审核节点主入口。"""

    draft: str = (state.get("draft_report") or "").strip()

    if not draft:
        return _build_result(
            passed=False,
            feedback="报告为空，请检查上游 generate_report 节点是否正常执行。",
            retry_count=state.get("review_retry_count", 0),
        )
    if len(draft) < 50:
        return _build_result(
            passed=False,
            feedback=f"报告过短（仅 {len(draft)} 字符），内容不完整，请扩充各章节。",
            retry_count=state.get("review_retry_count", 0),
        )

    source_data = _format_source_data(state)

    prompt = REVIEW_PROMPT.format(source_data=source_data, draft_report=draft)
    prompt += '\n请严格按照 JSON 格式回复：{"passed": true或false, "feedback": "审核结果说明"}。注意：只返回这一行 JSON，不要其他内容。'

    try:
        resp = await assist_llm.ainvoke([HumanMessage(content=prompt)])
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        cr: dict = parse_json(content)
        if not isinstance(cr, dict):
            raise TypeError(f"LLM 返回了 {type(cr).__name__}，期望 JSON 对象")
        passed: bool = cr.get("passed", False)
        feedback: str = cr.get("feedback", "")
    except Exception as e:
        passed = False
        feedback = f"审核系统异常：{e}。请人工复核报告。"

    return _build_result(
        passed=passed,
        feedback=feedback or "（无具体反馈）",
        retry_count=state.get("review_retry_count", 0),
    )


def _build_result(passed: bool, feedback: str, retry_count: int) -> dict:
    """构建审核节点的返回字典。retry_count 每次 +1。"""
    new_retry_count = retry_count + 1
    return {
        "review_passed": passed,
        "review_feedback": feedback,
        "review_retry_count": new_retry_count,
    }
