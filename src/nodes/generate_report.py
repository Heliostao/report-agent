"""
报告生成节点 — 节点⑤

整合前面所有节点的数据，调用 LLM 生成结构化研报分析报告。
审核打回重试时（review_feedback 非空），在 prompt 中追加修改要求。

RAG 检索链路：
  查询列表 → MMR Retriever(k=5, fetch_k=10) → CrossEncoderReranker(top_n=5)
  → 全局最相关且不重复的 chunk → 注入 prompt 交叉验证章节
"""
from typing import Dict, List, Any

from langchain_core.messages import HumanMessage

from src.state.research_state import ResearchState, ReportSummary
from src.models.main_model import main_llm
from src.prompts.report_prompt import REPORT_PROMPT
from src.rag.chroma_store import _get_vector_store


# ──────────────── 格式化辅助函数 ────────────────

def _format_company_info(data: dict) -> str:
    """格式化公司基本信息块"""
    lines = []
    if data.get("company_name"):
        lines.append(f"- 公司名称：{data['company_name']}")
    if data.get("stock_code"):
        lines.append(f"- 股票代码：{data['stock_code']}")
    if data.get("industry"):
        lines.append(f"- 所属行业：{data['industry']}")
    if data.get("reporter"):
        lines.append(f"- 发布机构：{data['reporter']}")
    if data.get("report_date"):
        lines.append(f"- 发布日期：{data['report_date']}")
    if data.get("rating"):
        lines.append(f"- 评级：{data['rating']}")
    if data.get("target_price") is not None:
        lines.append(f"- 目标价：{data['target_price']}")
    return "\n".join(lines) if lines else "（无基本信息）"


def _format_financial_data(data: dict) -> str:
    """格式化财务数据块，只列有值的字段"""
    fields = [
        ("营收", "revenue"),
        ("营收增长率", "revenue_growth"),
        ("净利润", "net_profit"),
        ("净利润增长率", "net_profit_growth"),
        ("每股收益(EPS)", "eps"),
        ("市盈率(PE)", "pe_ratio"),
        ("市净率(PB)", "pb_ratio"),
        ("净资产收益率(ROE)", "roe"),
        ("预测营收", "forecast_revenue"),
        ("预测净利润", "forecast_net_profit"),
    ]
    lines = []
    for label, key in fields:
        val = data.get(key)
        if val is not None:
            lines.append(f"- {label}：{val}")
    return "\n".join(lines) if lines else "（无财务数据）"


def _format_verified_summary(verified_items: list) -> str:
    """格式化验证结果摘要，按置信度分级标注"""
    if not verified_items:
        return "（未进行数据验证）"

    groups: Dict[str, List[dict]] = {"high": [], "medium": [], "low": [], "unverified": []}
    for item in verified_items:
        conf = item.get("confidence", "unverified")
        groups.setdefault(conf, []).append(item)

    lines = []
    level_labels = {
        "high": "高置信度（偏差 < 5%）",
        "medium": "中置信度（偏差 5%-20%）",
        "low": "低置信度（偏差 > 20%）",
        "unverified": "未验证（无公开数据对比）",
    }
    for level, label in level_labels.items():
        items = groups.get(level, [])
        if not items:
            continue
        lines.append(f"\n### {label}")
        for item in items:
            name = item.get("metric_name", "?")
            rv = item.get("report_value")
            pv = item.get("public_value")
            note = item.get("discrepancy_note", "")
            if pv is not None:
                lines.append(f"- {name}：研报值={rv}，公开值={pv}，{note}")
            else:
                lines.append(f"- {name}：研报值={rv}，{note}")

    return "\n".join(lines)


def _format_derived_metrics(calculated: dict) -> str:
    """格式化计算衍生指标，标注 source=calculated"""
    derived = calculated.get("derived", {}) if calculated else {}
    if not derived:
        return "（无衍生计算指标）"

    lines = []
    for tool_name, info in derived.items():
        if not isinstance(info, dict):
            continue
        value = info.get("value")
        if value is not None and "error" not in info:
            lines.append(f"- {tool_name}：{value}（来源：推算）")
    return "\n".join(lines) if lines else "（无有效衍生指标）"


def _format_risk_warnings(risks: Any) -> str:
    """格式化风险提示列表"""
    if not risks:
        return "（无风险提示）"
    if isinstance(risks, list):
        return "\n".join(f"- {r}" for r in risks)
    return str(risks)


# ──────────────── RAG 交叉验证检索 ────────────────

async def _retrieve_cross_validation(
    company_name: str, industry: str, data: dict
) -> str:
    """RAG 检索链路：

    查询列表 → MMR 检索(k=5, fetch_k=10) → CrossEncoderReranker 全局重排(top_n=5)
    → 返回 5 条最相关且不重复的 chunk

    若 reranker 不可用，降级为 MMR 去重。
    """
    try:
        store = _get_vector_store()
    except Exception:
        return ""

    try:
        # ── 构造查询列表 ──
        queries = []
        if company_name:
            queries.append(f"{company_name} 评级 目标价")
            queries.append(f"{company_name} 营收 净利润 财务数据")
            queries.append(f"{company_name} 核心观点 投资建议")
        if industry:
            queries.append(f"{industry} 行业 研报 分析")
        for metric, label in [("revenue", "营收"), ("eps", "EPS"), ("pe_ratio", "PE")]:
            if data.get(metric) is not None:
                queries.append(f"{company_name} {label}")

        if not queries:
            return ""

        # ── MMR 检索器 ──
        base_retriever = store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10, "lambda_mult": 0.7},
        )

        # ── 尝试启用 Reranker ──
        retriever = base_retriever
        try:
            from langchain.retrievers import ContextualCompressionRetriever
            from langchain_community.document_compressors import CrossEncoderReranker

            reranker = CrossEncoderReranker(
                model="BAAI/bge-reranker-large",
                top_n=5,
            )
            retriever = ContextualCompressionRetriever(
                base_compressor=reranker,
                base_retriever=base_retriever,
            )
        except ImportError:
            # sentence-transformers 未安装或模型首次下载中，降级用纯 MMR
            pass

        # ── 多查询并发检索 ──
        seen = set()
        all_docs = []
        for q in queries:
            try:
                docs = await retriever.ainvoke(q)
            except Exception:
                continue
            for doc in docs:
                # 用 page_content 前 80 字符去重（reranker 后 chunk 已精炼，误杀风险低）
                key = doc.page_content[:80]
                if key not in seen:
                    seen.add(key)
                    all_docs.append(doc)

        if not all_docs:
            return ""

        # ── 格式化注入 prompt ──
        lines = ["以下是从历史研报库中检索到的相关内容，请用于交叉验证：", ""]
        for i, doc in enumerate(all_docs, 1):
            source = doc.metadata.get("source", "unknown")
            filename = source.replace("\\", "/").split("/")[-1] if source else "unknown"
            lines.append(f"**参考片段 {i}** [来源: {filename}]")
            lines.append(doc.page_content.strip())
            lines.append("")
        return "\n".join(lines)

    finally:
        store._client.close()


# ──────────────── 报告组装 ────────────────

def _build_summary(data: dict, verified_items: list, calculated: dict) -> ReportSummary:
    """从已有数据中简单组装 final_report 摘要（避免额外 LLM 调用）"""
    company = data.get("company_name", "该公司")
    rating = data.get("rating", "")
    thesis = data.get("core_thesis", "")
    one_liner = f"{company}（评级：{rating}）。{thesis}" if rating or thesis else f"{company}研报分析。"
    if len(one_liner) > 200:
        one_liner = one_liner[:197] + "..."

    key_parts = []
    for label, key in [("营收", "revenue"), ("净利润", "net_profit"),
                        ("EPS", "eps"), ("PE", "pe_ratio"), ("ROE", "roe")]:
        val = data.get(key)
        if val is not None:
            key_parts.append(f"{label}: {val}")
    key_data_table = " | ".join(key_parts) if key_parts else "无关键数据"

    if not verified_items:
        confidence_note = "数据未经联网验证。"
    else:
        high = sum(1 for v in verified_items if v.get("confidence") == "high")
        total = len(verified_items)
        confidence_note = f"共验证 {total} 项指标，其中高置信度 {high} 项。"

    risks = data.get("risk_warnings", [])
    if risks:
        risk_highlight = "；".join(risks[:3])
        if len(risks) > 3:
            risk_highlight += f" 等共 {len(risks)} 条风险"
    else:
        risk_highlight = "研报未明确列出风险因素。"

    return ReportSummary(
        one_liner=one_liner,
        key_data_table=key_data_table,
        confidence_note=confidence_note,
        risk_highlight=risk_highlight,
    )


# ──────────────── 主节点 ────────────────

async def generate_report(state: ResearchState) -> dict:
    """报告生成节点"""

    data: dict = state.get("extracted_data") or {}
    verified_items: list = state.get("verified_items") or []
    calculated: dict = state.get("calculated_metrics") or {}
    review_feedback: str = state.get("review_feedback", "")

    if not data:
        return {
            "draft_report": "数据不足，无法生成研报分析报告。请检查上游节点是否正常执行。",
            "final_report": ReportSummary(
                one_liner="数据不足",
                key_data_table="无",
                confidence_note="无",
                risk_highlight="无",
            ),
        }

    company_info = _format_company_info(data)
    financial_data = _format_financial_data(data)
    verified_summary = _format_verified_summary(verified_items)
    derived_metrics = _format_derived_metrics(calculated)
    core_thesis = data.get("core_thesis", "（无核心观点）")
    risk_warnings = _format_risk_warnings(data.get("risk_warnings"))

    # ── RAG 交叉验证检索 ──
    company_name = data.get("company_name", "")
    industry = data.get("industry", "")
    cross_validation = ""
    if company_name:
        cross_validation = await _retrieve_cross_validation(company_name, industry, data)
        if not cross_validation:
            cross_validation = "（历史研报库中暂无该公司或行业的相关研报，无法进行交叉验证。）"

    review_feedback_section = ""
    if review_feedback:
        review_feedback_section = (
            "## 修改要求\n"
            "上一版报告存在以下问题，请针对性地重新撰写：\n"
            f"{review_feedback}\n"
        )

    prompt = REPORT_PROMPT.format(
        company_info=company_info,
        financial_data=financial_data,
        verified_summary=verified_summary,
        derived_metrics=derived_metrics,
        cross_validation=cross_validation,
        core_thesis=core_thesis,
        risk_warnings=risk_warnings,
        review_feedback_section=review_feedback_section,
    )

    response = await main_llm.ainvoke([HumanMessage(content=prompt)])
    draft_report: str = response.content.strip() if hasattr(response, "content") else ""

    final_report = _build_summary(data, verified_items, calculated)

    return {
        "draft_report": draft_report,
        "final_report": final_report,
        "cross_validation": cross_validation,
    }
