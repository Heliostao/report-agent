"""
计算节点工具 — 4 个纯数学计算 @tool
LLM 负责决策调用哪些工具，Python 负责精确算术。
"""
from typing import Optional
from langchain_core.tools import tool


@tool
def calc_pe_ratio(price: float, eps: float) -> Optional[float]:
    """计算市盈率（PE）= 股价 / 每股收益。EPS 为 0 或 None 时返回 None。"""
    if not eps:
        return None
    return round(price / eps, 2)


@tool
def calc_pb_ratio(price: float, book_value_per_share: float) -> Optional[float]:
    """计算市净率（PB）= 股价 / 每股净资产。每股净资产为 0 或 None 时返回 None。"""
    if not book_value_per_share:
        return None
    return round(price / book_value_per_share, 2)


@tool
def calc_roe(net_income: float, equity: float) -> Optional[float]:
    """计算净资产收益率（ROE）= 净利润 / 净资产。净资产为 0 或 None 时返回 None。"""
    if not equity:
        return None
    return round(net_income / equity, 4)


@tool
def calc_growth_rate(current: float, previous: float) -> Optional[float]:
    """计算同比增长率 = (当期 - 上期) / |上期|。上期为 0 或 None 时返回 None。"""
    if not previous:
        return None
    return round((current - previous) / abs(previous), 4)


