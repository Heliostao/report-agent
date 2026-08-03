"""
节点③：通过 mcp-aktools 金融数据库核验研报数据

流程：
  1. 筛选需要验证的数字指标
  2. 查股票代码（如果研报未提取到）
  3. 调用 stock_info + stock_indicators_a 获取真实金融数据
  4. LLM 一次性比对研报值和数据库值
  5. 输出 List[VerifiedItem]
"""
import re
from typing import List

from src.models.main_model import main_llm
from src.state.research_state import ResearchState
from src.prompts.verification_prompt import COMPARE_WITH_DB_PROMPT
from src.tools.verify_tools import (
    parse_json,
    filter_fields,
    metrics_text,
    LABEL_TO_KEY,
)
from src.mcps.aktools_client import (
    search_stock,
    get_stock_info,
    get_financial_indicators_a,
)


def _clean_stock_code(code: str) -> str:
    """清理股票代码：去掉 .SZ/.SH 等后缀，保留 6 位纯数字。"""
    if not code:
        return ""
    m = re.search(r"(\d{6})", str(code))
    return m.group(1) if m else str(code).strip()


def _format_db_context(stock_info_text: str, indicators_text: str) -> str:
    """将 MCP 返回的原始文本格式化为 LLM 可读的数据库上下文。"""
    parts = []
    if stock_info_text and stock_info_text.strip():
        parts.append(f"## 股票基本信息\n{stock_info_text.strip()}")
    if indicators_text and indicators_text.strip():
        parts.append(f"## 财务指标数据\n{indicators_text.strip()}")
    return "\n\n".join(parts) if parts else "（金融数据库未返回数据）"


def _build_items_from_llm(
    llm_results: List[dict],
    numeric: dict,
) -> List[dict]:
    """将 LLM 比对结果转为 VerifiedItem 列表。"""
    items = []
    llm_map = {}
    for r in llm_results:
        name = r.get("metric_name", "")
        key = LABEL_TO_KEY.get(name, name)
        llm_map[key] = r

    for name, val in numeric.items():
        rv = float(val) if val is not None else 0.0
        result = llm_map.get(name)
        if result:
            items.append({
                "metric_name": name,
                "report_value": rv,
                "public_value": result.get("public_value"),
                "confidence": result.get("confidence", "unverified"),
                "discrepancy_note": result.get("discrepancy_note", ""),
            })
        else:
            items.append({
                "metric_name": name,
                "report_value": rv,
                "public_value": None,
                "confidence": "unverified",
                "discrepancy_note": "LLM 比对未覆盖此指标",
            })

    return items


async def verify_data(state: ResearchState) -> dict:
    """节点③：MCP 查金融数据 → LLM 比对 → 输出验证结果"""

    extracted = state.get("extracted_data")
    if not extracted:
        return {"verified_items": []}

    numeric = filter_fields(extracted)
    if not numeric:
        return {"verified_items": []}

    company_name = str(extracted.get("company_name", "") or "")
    stock_code = _clean_stock_code(str(extracted.get("stock_code", "") or ""))

    if not stock_code and company_name:
        try:
            search_result = await search_stock(company_name)
            m = re.search(r"(\d{6})", search_result)
            if m:
                stock_code = m.group(1)
        except Exception:
            pass

    db_context = ""
    if stock_code:
        try:
            stock_info = await get_stock_info(stock_code)
        except Exception:
            stock_info = ""

        try:
            indicators = await get_financial_indicators_a(stock_code)
        except Exception:
            indicators = ""

        db_context = _format_db_context(stock_info, indicators)

    if db_context.strip() and db_context != "（金融数据库未返回数据）":
        prompt = COMPARE_WITH_DB_PROMPT.format(
            company_name=company_name or "未知",
            stock_code=stock_code or "未知",
            report_metrics=metrics_text(numeric),
            db_data=db_context,
        )
        resp = await main_llm.ainvoke(prompt)
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        llm_results = parse_json(content)
        if not isinstance(llm_results, list):
            raise TypeError(f"LLM 返回了 {type(llm_results).__name__}，期望数组")
        verified = _build_items_from_llm(llm_results, numeric)
    else:
        verified = []
        for name, val in numeric.items():
            verified.append({
                "metric_name": name,
                "report_value": float(val) if val is not None else 0.0,
                "public_value": None,
                "confidence": "unverified",
                "discrepancy_note": "金融数据库未返回对比数据" if stock_code else "未找到股票代码，无法查询金融数据",
            })

    return {"verified_items": verified}
