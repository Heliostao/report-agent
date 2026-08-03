"""节点③ 的纯函数工具集：筛选、格式化、JSON解析。"""
import json
import re
from typing import Any, Dict


# 需要验证的数字指标
NUMERIC_FIELDS = {
    "revenue", "revenue_growth", "net_profit", "net_profit_growth",
    "eps", "pe_ratio", "pb_ratio", "roe",
    "forecast_revenue", "forecast_net_profit",
}

# 字段 → 中文标签（填入 Prompt 时消除歧义）
METRIC_LABELS: Dict[str, str] = {
    "revenue":              "营收（亿元）",
    "revenue_growth":       "营收同比增长率（%）",
    "net_profit":           "归母净利润（亿元）",
    "net_profit_growth":    "净利润同比增长率（%）",
    "eps":                  "每股收益 EPS（元/股）",
    "pe_ratio":             "市盈率 PE（倍）",
    "pb_ratio":             "市净率 PB（倍）",
    "roe":                  "净资产收益率 ROE（%）",
    "forecast_revenue":     "预测营收（亿元）",
    "forecast_net_profit":  "预测净利润（亿元）",
}

LABEL_TO_KEY: Dict[str, str] = {v: k for k, v in METRIC_LABELS.items()}


def parse_json(text: str) -> Any:
    """从 LLM 返回文本中提取 JSON，兼容 markdown 代码块包裹和尾部多余文字。

    策略：
      1. 优先匹配 ```json ... ``` 代码块。
      2. 回退：用 json.JSONDecoder.raw_decode 扫描文本中的 { 或 [，
         只解析第一个完整合法 JSON 值，自动忽略尾部额外文字。
    """
    cleaned = text.strip()

    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        return json.loads(m.group(1).strip())

    decoder = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch in ("{", "["):
            try:
                obj, _ = decoder.raw_decode(cleaned[i:])
                return obj
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从文本中提取 JSON: {text[:200]}")


def filter_fields(extracted_data: dict) -> dict:
    """筛选出有值的数字指标。"""
    numeric = {}
    for k, v in extracted_data.items():
        if v is not None and k in NUMERIC_FIELDS:
            numeric[k] = v
    return numeric


def metrics_text(numeric: dict) -> str:
    """将数字指标格式化为中文清单，用于 Prompt。"""
    return "\n".join(
        f"{METRIC_LABELS.get(k, k)}: {v}"
        for k, v in numeric.items()
    )
