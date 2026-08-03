"""
定义共享状态
这个状态包含所有用到的字段
0：用户输入研报文件（.txt / .md），也就是纯文本文件路径
1：纯文本文件读取后按语义切分为 chunks，输出 llm 能看懂的片段列表
2：将这些片段给 llm 看，让其从诸多片段中提取出有用的信息，产出 ExtractedData 即提取后的数据
3：提取完数据还没完，还要进行联网验证是否正确，通过 MCP Server 进行联网验证，并查询过往历史研报，标注置信度 VerifiedItem
4：接着拿到数据调用工具，纯计算比率，将原始数据变成可分析的比率 calculated_metrics
5：主模型将分析后的结果生成一个报告 draft_report，包括原始数据、验证结果、分析指标，通过 RAG 检索是否存在矛盾需标注
6：审核模型将报告进行审核，判断是否存在问题，通过时把结果写入 PostgresStore，不通过时给出修改意见（最多一次）

"""
from typing import TypedDict, List, Optional, Literal


# 切分后的文档片段
class DocumentChunk(TypedDict):
    index: int  # 片段的索引
    text: str  # 片段的文本内容
    chunk_type: Literal["text", "table", "image", "mixed"]  # 片段的类型
    heading: str  # 所属的标题

# 提取后的数据
class ExtractedData(TypedDict, total=False):
    company_name: str  # 公司名称
    stock_code: str  # 股票代码
    report_date: str  # 研报发布日期
    reporter: str  # 发布研报的机构名称
    rating: str  # 评级：研报原文评级（如推荐/买入/增持/中性等），保持原文原样
    target_price: float  # 目标价
    industry: str  # 所属行业分类
    revenue: float  # 营收
    revenue_growth: float  # 营收增长率
    net_profit: float  # 净利润
    net_profit_growth: float  # 净利润增长率
    eps: float  # 每股收益
    pe_ratio: float  # 市盈率
    pb_ratio: float  # 市净率
    roe: float  # 净资产收益率
    forecast_revenue: float  # 预测营收
    forecast_net_profit: float  # 预测净利润
    core_thesis: str  # 核心观点
    risk_warnings: List[str]  # 风险提示列表

# 验证后的数据
class VerifiedItem(TypedDict):
    metric_name: str  # 指标名称
    report_value: float  # 研报声称的值
    public_value: Optional[float]  # 公开数据中的值
    confidence: Literal["high", "medium", "low", "unverified"]  # 置信度
    discrepancy_note: str  # 差异说明

# 最终的报告
class ReportSummary(TypedDict):
    one_liner: str  # 一句话结论
    key_data_table: str  # 关键数据表
    confidence_note: str  # 数据可信度说明
    risk_highlight: str  # 风险提示

# 定义共享状态
class ResearchState(TypedDict, total=False):
    # 输入
    file_path: str  # 研报文件路径（.txt / .md，可选）
    user_message: str  # 用户直接输入的文本（可选，意图路由用）
    # 意图路由
    intent: str  # "chat" | "research"，由 router_node 判定
    chat_reply: str  # chat 节点的回复
    # 对话历史（用于闲聊上下文记忆）
    messages: List[dict]  # [{"role": "user"|"assistant", "content": str}]
    # 生产
    raw_text: str  # 全文文本
    chunks: List[DocumentChunk]  # 按章节切分的文档片段列表
    extracted_data: ExtractedData  # 提取后的结构化数据
    verified_items: List[VerifiedItem]  # 验证后的数据项列表
    calculated_metrics: dict  # 计算后的财务指标
    cross_validation: str  # RAG 交叉验证检索结果（历史研报库匹配内容，供审核对照使用）
    draft_report: str  # 生成的报告草稿
    # 审核
    review_passed: bool  # 是否通过审核
    review_feedback: str  # 审核反馈意见
    review_retry_count: int  # 重试次数
    # 最终输出
    final_report: ReportSummary  # 最终报告
    # 兜底策略
    error: Optional[str]  # 异常信息
