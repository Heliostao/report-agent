"""
verify_data 节点的 Prompt 模板

相比旧版的三段式（预判→生成搜索词→比对），新版简化为一步：
  直接拿 mcp-aktools 返回的金融数据库真实数据与研报数值做比对，LLM 一次性输出所有指标的验证结果。
"""
from textwrap import dedent

COMPARE_WITH_DB_PROMPT = dedent("""\
你是一位财务数据交叉验证专家。请比对研报提取数据与金融数据库返回的真实数据，逐条给出验证结论。

## 公司信息
公司：{company_name}
股票代码：{stock_code}

## 研报提取的数据
{report_metrics}

## 金融数据库返回的数据
{db_data}

## 验证规则
1. 对每条研报指标，在数据库数据中查找对应值
2. 如果数据库返回了对应数值，计算偏差：|研报值 - 数据库值| / 数据库值 × 100%
3. 根据偏差判定置信度：
   - "high" — 偏差 < 5%
   - "medium" — 偏差 5%-20%
   - "low" — 偏差 > 20%
4. 如果数据库未返回该指标（例如某些指标不在库存数据中），判定为 "unverified"

## 输出要求
以 JSON 数组格式返回，每条包含：
- metric_name: 指标名称（与输入的研报数据一致）
- report_value: 研报声称值（数字）
- public_value: 数据库中查到的值（数字，找不到填 null）
- confidence: "high" / "medium" / "low" / "unverified"
- discrepancy_note: 差异说明，一句话。如 "研报 105 亿，DB 102 亿，偏差 2.9%，基本一致"

要求：
1. 只返回合法 JSON 数组，不要任何额外文字
2. 对每个输入指标都必须给出判断，不要遗漏
3. public_value 只填能在数据库数据中明确找到的数字，不要推测
""")
