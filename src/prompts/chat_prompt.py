"""
意图路由 + 聊天的提示词模板
"""
from textwrap import dedent

ROUTER_PROMPT = dedent("""\
你是意图分类器。只输出一个词：chat 或 research。

- chat：问候、闲聊、能力询问、查询历史、角色确认、感谢告别。
  示例："你好"、"你是谁"、"你能做什么"、"你是研报助手吗"、"之前分析过哪些"
- research：用户要分析新的研报/财务数据/公司。
  示例："帮我分析这份年报"、"宁德时代去年营收多少"、"这份研报怎么看"

注意：含"分析""研报"等词汇但实质是能力询问 → chat，不是 research。

用户：{user_message}
输出：\
""")

CHAT_SUB_INTENT_PROMPT = dedent("""\
判断意图，输出 query_history 或 chat。

- query_history：查询历史研报数据库信息。如"上次长鑫评级""之前分析过哪些公司"
- chat：其他一切对话（问候、闲聊、能力询问等）

用户：{user_message}
历史：{history}
输出：\
""")

CHAT_PROMPT = dedent("""\
你是投研 Report Agent。回答简洁，不超过三句话。

对话历史：
{history}

用户：{user_message}\
""")

CHAT_WITH_DB_PROMPT = dedent("""\
你是投研 Report Agent。基于以下数据库记录回答用户。

记录：
{db_records}

历史：
{history}

用户：{user_message}

要求：只基于记录回答，不编造；无匹配信息时明确告知；不超过五句话。\
""")
