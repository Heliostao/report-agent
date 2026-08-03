# Report Agent — 智能投研研报分析系统

基于 LangGraph 多智能体协作框架，实现从非结构化研报文档到结构化投资分析报告的自动化 Pipeline。

## 核心能力

- **文档解析**：语义切片研报文本，写入向量库
- **财务提取**：LLM 自动提取营收、净利润、EPS、PE 等关键指标
- **数据验证**：通过 MCP 协议对接 A 股金融数据库，交叉比对并标注置信度
- **指标计算**：工具调用方式计算 PE、PB、ROE 等衍生估值指标
- **报告生成**：整合提取 + 验证 + 计算 + RAG 历史交叉验证，生成七章结构化研报
- **质量审核**：独立审核模型复核准确性，不通过则带反馈重试（最多 1 次）
- **闲聊对话**：支持自然语言查询历史分析记录和自由对话

## 技术栈

| 层级 | 技术 |
|------|------|
| 编排框架 | LangGraph（StateGraph + Checkpointer） |
| LLM | ChatOpenAI 双模型（主模型提取 + 审核模型复查） |
| 嵌入 | Ollama `nomic-embed-text` |
| 向量库 | ChromaDB |
| 长期记忆 | PostgreSQL |
| 短期记忆 | LangGraph MemorySaver |
| 金融数据 | MCP 协议（AKTools） |
| 服务层 | FastAPI + Uvicorn |
| 前端 | 原生 HTML/CSS/JS（Served by FastAPI） |

## 快速开始

### 1. 环境要求

- Python 3.11+
- Docker（运行 ChromaDB、PostgreSQL、MCP 服务）
- Ollama（本地 embedding 模型）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动基础服务

```bash
# ChromaDB
docker run -d --name chroma -p 8000:8000 chromadb/chroma

# PostgreSQL
docker run -d --name research_postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=research_agent postgres:16

# MCP 金融数据服务
docker run -d --name mcp-aktools -p 8808:80 -e TZ=Asia/Shanghai -e TRANSPORT=http ghcr.io/aahl/mcp-aktools:latest
```

### 4. 配置环境变量

复制并编辑 `.env` 文件，填入你的 API Key：

```env
MAIN_MODEL=qwen3.7-plus
MAIN_API_KEY=你的阿里云百炼APIKey
MAIN_BASE_URL=https://ws-4euf8ziv4pluqn7w.cn-beijing.maas.aliyuncs.com/compatible-mode/v1

ASSIST_MODEL=deepseek-v4-pro
ASSIST_API_KEY=你的DeepSeekAPIKey
ASSIST_BASE_URL=https://api.deepseek.com

POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/research_agent
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_COLLECTION=research_reports
AKTOOLS_MCP_URL=http://127.0.0.1:8808/mcp
```

### 5. 拉取 Embedding 模型

```bash
ollama pull nomic-embed-text
```

### 6. 启动服务

```bash
python -m src.server
```

访问 `http://localhost:8001`，上传 `.txt`/`.md` 格式研报或粘贴文本即可分析。

## 项目结构

```
src/
├── server.py              # FastAPI 入口
├── graph.py               # LangGraph 工作流定义
├── config/                # 配置（环境变量读取）
├── models/                # LLM 模型实例
├── state/                 # 共享状态 TypedDict
├── nodes/                 # 7 个图节点
│   ├── parse_document.py
│   ├── extract_data.py
│   ├── verify_data.py
│   ├── calc_metrics.py
│   ├── generate_report.py
│   ├── review_quality.py
│   └── chat.py
├── mcps/                  # MCP 客户端
├── memory/                # 长/短期记忆
├── prompts/               # Prompt 模板
├── rag/                   # ChromaDB 向量检索
├── tools/                 # 工具函数
└── static/                # 前端页面
```

## License

MIT
