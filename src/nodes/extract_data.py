"""
节点②：提取关键信息

分两步提取研报中的结构化数据：
  Step 1 — 元信息（公司、评级、目标价等）
  Step 2 — 财务数据 + 核心观点 + 风险提示
"""
from typing import TypedDict, List
from src.models.main_model import main_llm
from src.state.research_state import ResearchState, ExtractedData
from src.prompts.extraction_prompt import META_EXTRACTION_PROMPT, FINANCIAL_EXTRACTION_PROMPT


class MetaOutput(TypedDict, total=False):
    """Step 1 元信息提取的输出结构"""
    company_name: str
    stock_code: str
    report_date: str
    reporter: str
    rating: str
    target_price: float
    industry: str


class FinancialOutput(TypedDict, total=False):
    """Step 2 财务数据 + 观点提取的输出结构"""
    revenue: float
    revenue_growth: float
    net_profit: float
    net_profit_growth: float
    eps: float
    pe_ratio: float
    pb_ratio: float
    roe: float
    forecast_revenue: float
    forecast_net_profit: float
    core_thesis: str
    risk_warnings: List[str]


async def extract_data(state: ResearchState) -> dict:
    """节点②：从解析后的 chunks 中提取结构化投资数据"""

    chunks = state.get("chunks") or []
    all_text = "\n\n".join(c["text"] for c in chunks)
    if not all_text.strip():
        return {"extracted_data": {}}

    try:
        meta_chain = main_llm.with_structured_output(MetaOutput)
        meta: MetaOutput = await meta_chain.ainvoke(
            META_EXTRACTION_PROMPT.format(all_text=all_text)
        )
    except Exception:
        meta: MetaOutput = {}

    try:
        financial_chain = main_llm.with_structured_output(FinancialOutput)
        financial: FinancialOutput = await financial_chain.ainvoke(
            FINANCIAL_EXTRACTION_PROMPT.format(
                all_text=all_text,
                company_name=meta.get("company_name") or "未知",
                stock_code=meta.get("stock_code") or "未知",
                report_date=meta.get("report_date") or "未知",
            )
        )
    except Exception:
        financial: FinancialOutput = {}

    extracted: ExtractedData = {**meta, **financial}  # type: ignore[typeddict-item]

    return {"extracted_data": extracted}
