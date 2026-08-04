# Report Agent — 智能投研研报分析系统 V1.2

基于 LangGraph 多智能体协作框架，实现从非结构化研报文档到结构化投资分析报告的自动化 Pipeline。

## V1.2 更新

- **文档解析上云**：本地 mineru 引擎（PyTorch + VLM 模型）替换为 `langchain-mineru` flash 云端模式，免 GPU、免 token，依赖包减少 4 个，磁盘占用减少约 8GB
- **验证简化**：数据验证 Prompt 三段式合并为一步比对，减少 LLM 调用

## V1.12 更新

- **mineru 本地引擎集成**：PDF/Office/图片文档解析改用 `mineru` 本地引擎（HuggingFace VLM + PyTorch），一键调用 `do_parse()` 自动识别布局、表格、公式，输出结构化 Markdown。VLM 模型首次运行时自动下载至 `~/.cache/huggingface/hub/`（约 2.3GB），后续缓存复用，全程本地推理无需联网
- Office 文档（docx/pptx/xlsx）改为 mineru 内置解析器，移除 python-docx / python-pptx / openpyxl 自定义文本提取分支
- 代码清理：移除 `langchain-experimental`、`pypdf` 等未使用依赖，删除 `add_chunks`、`get_retriever`、`get_stock_news`、`get_file_history` 等无引用函数，移除 `redis_url` 无用配置

## V1.11 修复

- **MinerU API 调用修正**：MinerU v4 只接受公网 URL（不支持本地文件上传），修复了此前通过 multipart 上传导致"远程主机强迫关闭"的错误（V1.12 已统一改用 mineru 本地引擎处理本地文件）
- 前端文件上传区域、服务器白名单、`research_state` 注释统一更新为支持全部格式，消除残留的"仅 txt/md"描述
- `server.py` 改为二进制直接落盘，不再强制 UTF-8 decode
- 前端页脚左下角标注版本号

## V1.1 更新

- **PDF/Word/PPT 原生支持**：集成 MinerU v4 API（vlm 多模态解析），支持本地文件和云端 URL，自动识别表格、图表、排版，输出高质量 Markdown
- **RAG 检索链路重构**：MMR（最大边际相关性）检索 + CrossEncoderReranker（bge-reranker-large）全局重排，替代此前粗糙的相似度搜索
- **文档分割升级**：RecursiveCharacterTextSplitter（chunk_size=1024，overlap=150，中文分隔符优先级）替代 SemanticChunker，保证每个 chunk 为完整语义单元
- **MinerU SDK 客户端**：新增 `mineru_client.py`，完整封装 create_task → 轮询 → 解析全链路，支持 multipart 文件上传与 URL 提交两种模式，PyPDFLoader 自动降级
- **配置层扩展**：`.env` 新增 `MINERU_API_KEY`，`requirements.txt` 新增 `sentence-transformers`、`langchain`

## 核心能力

- **文档解析**：`langchain-mineru`（MinerULoader flash 模式）云端解析 PDF/Word/PPT/Excel/图片 → Markdown，免费免 token，RecursiveCharacterTextSplitter 语义切片入库
- **财务提取**：LLM 读取全文 Markdown，自动提取营收、净利润、EPS、PE、目标价、评级等关键指标
- **数据验证**：通过 MCP 协议对接 A 股金融数据库，交叉比对并标注置信度
- **指标计算**：工具调用方式计算 PE、PB、ROE 等衍生估值指标
- **报告生成**：整合提取 + 验证 + 计算 + RAG 交叉验证（MMR 检索 + Reranker 重排），生成七章结构化研报
- **质量审核**：独立审核模型复核准确性，不通过则带反馈重试（最多 1 次）
- **闲聊对话**：支持自然语言查询历史分析记录和自由对话

## 技术栈

| 层级 | 技术 |
|------|------|
| 编排框架 | LangGraph（StateGraph + Checkpointer） |
| LLM | ChatOpenAI 双模型（主模型提取 + 审核模型复查） |
| 文档解析 | langchain-mineru（MinerULoader flash 模式，云端解析） |
| 嵌入 | Ollama `nomic-embed-text` |
| 向量库 | ChromaDB |
| 检索链路 | MMR + CrossEncoderReranker（bge-reranker-large） |
| 长期记忆 | PostgreSQL |
| 短期记忆 | LangGraph MemorySaver |
| 金融数据 | MCP 协议（AKTools） |
| 服务层 | FastAPI + Uvicorn |
| 前端 | 原生 HTML/CSS/JS（Served by FastAPI） |

## 数据流架构

```
输入文件（PDF/Word/PPT/Excel/图片/txt/md）
  → langchain-mineru 云端解析 → Markdown 全文
      ├── raw_text（完整 Markdown）→ extract_data（LLM 穷举提取财务指标）
      └── chunks（RecursiveCharacterTextSplitter 切片）→ ChromaDB 入库
            → generate_report（MMR 检索 + Reranker 重排 → 交叉验证）
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Docker（运行 ChromaDB、PostgreSQL、MCP 服务）
- Ollama（本地 embedding 模型）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

首次运行时会自动下载 bge-reranker-large 模型（约 1.3GB），后续缓存复用。

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

# MinerU 文档解析（免费额度：每天 1000 页，超出降速）
MINERU_API_KEY=你的MinerUAPIKey
```

### 5. 拉取 Embedding 模型

```bash
ollama pull nomic-embed-text
```

### 6. 启动服务

```bash
python -m src.server
```

访问 `http://localhost:8001`，上传 pdf/doc/docx/ppt/pptx/xls/xlsx/txt/md/png/jpg/jpeg 格式研报即可分析。

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
├── rag/                   # ChromaDB 向量检索 & MinerU 客户端
│   ├── chroma_store.py
│   ├── document_util.py
│   ├── embeddings.py
│   └── mineru_client.py
├── tools/                 # 工具函数
└── static/                # 前端页面

```

## License

MIT
