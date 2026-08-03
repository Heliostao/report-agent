"""
mcp-aktools 客户端封装
通过 Streamable-HTTP 连接本地 Docker 部署的 mcp-aktools，提供 A 股金融数据查询。
端点：http://localhost:8808/mcp（Docker 内部 80 端口）

工具清单：
  - search:             公司名/关键词 → 股票代码
  - stock_info:         价格、市值等详细信息
  - stock_indicators_a: A 股关键财务指标（PE/PB/ROE/营收/利润等）
  - stock_prices:       历史价格
  - stock_news:         个股新闻
"""
import json
import re
import httpx

from src.config.util_config import aktools_mcp_url

# 单例
_httpx_client: httpx.AsyncClient | None = None
_session_id: str | None = None
_request_counter: int = 0


def _next_id() -> int:
    global _request_counter
    _request_counter += 1
    return _request_counter


async def _init_session() -> None:
    """初始化 MCP 会话，获取 session-id。"""
    global _httpx_client, _session_id

    if _session_id is not None:
        return

    _httpx_client = httpx.AsyncClient(timeout=60.0)

    resp = await _httpx_client.post(
        aktools_mcp_url,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "report-agent", "version": "1.0"},
            },
            "id": _next_id(),
        },
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    resp.raise_for_status()

    # FastMCP 2.0 在响应头中返回 session ID
    _session_id = resp.headers.get("mcp-session-id", "")
    if not _session_id:
        # 兼容旧版大写 header
        _session_id = resp.headers.get("Mcp-Session-Id", "")

    # 发送 initialized 通知
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if _session_id:
        headers["mcp-session-id"] = _session_id
    await _httpx_client.post(
        aktools_mcp_url,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
    )

    print(f"[aktools] MCP 会话初始化成功 (session={_session_id[:12]}...)" if _session_id else
          "[aktools] MCP 会话初始化成功 (无 session header)")


def _parse_sse_body(text: str) -> dict:
    """从 SSE 文本中提取 JSON-RPC 响应体。
    SSE 格式: event:xxx\ndata:{json}\n\n
    返回解析后的 JSON 对象，或空字典。
    """
    # 匹配 data: 行中的 JSON-RPC response
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("data:"):
            data_str = stripped[5:].strip()
            if data_str:
                try:
                    return json.loads(data_str)
                except json.JSONDecodeError:
                    continue
    # 尝试直接匹配 JSON 块（某些实现直接返回裸 JSON 多行）
    match = re.search(r'\{[^{}]*"jsonrpc"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def _call_tool(tool_name: str, arguments: dict) -> str:
    """调用 MCP 工具，返回 content[0].text 文本。"""
    if _session_id is None:
        await _init_session()

    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if _session_id:
        headers["mcp-session-id"] = _session_id

    resp = await _httpx_client.post(
        aktools_mcp_url,
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": _next_id(),
        },
        headers=headers,
    )
    resp.raise_for_status()

    # 尝试解析响应体：先 JSON，失败则 SSE
    raw_text = resp.text
    content_type = resp.headers.get("content-type", "")

    body: dict = {}
    if "text/event-stream" in content_type or raw_text.startswith("event:"):
        body = _parse_sse_body(raw_text)
        if not body:
            return ""
    else:
        try:
            body = resp.json()
        except json.JSONDecodeError:
            return ""

    if "error" in body:
        raise RuntimeError(f"MCP 工具 [{tool_name}] 错误: {body['error']}")

    content = body.get("result", {}).get("content", [])
    if isinstance(content, list) and len(content) > 0:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            return first.get("text", "")
        return str(first)
    return json.dumps(content, ensure_ascii=False)


async def warmup() -> None:
    """预热 MCP 连接，Server 启动时调用。"""
    try:
        await _init_session()
        print("[aktools] 预热成功")
    except Exception as e:
        print(f"[aktools] 预热失败: {e}")


async def search_stock(keyword: str) -> str:
    """搜索股票代码，返回文本（可能包含多个匹配结果）。"""
    return await _call_tool("search", {"keyword": keyword})


async def get_stock_info(symbol: str) -> str:
    """获取股票详细信息（价格、市值、PE/PB 等）。"""
    return await _call_tool("stock_info", {"symbol": symbol})


async def get_financial_indicators_a(symbol: str) -> str:
    """获取 A 股关键财务指标（营收、利润、ROE、EPS 等）。"""
    return await _call_tool("stock_indicators_a", {"symbol": symbol})


async def get_stock_news(symbol: str) -> str:
    """获取个股相关新闻。"""
    return await _call_tool("stock_news", {"symbol": symbol})
