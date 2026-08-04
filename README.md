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

## MVP 迭代记录

**V1.0** — 基础研报分析流水线：纯文本输入 → 数据提取 → 联网验证 → 指标计算 → 报告生成 → 质量审核，6 节点 LangGraph 工作流。双模型策略（主模型 qwen3.7-plus 负责生成，辅助模型 deepseek-v4-pro 负责审核），Ollama 本地 embedding + ChromaDB 向量库 + PostgreSQL 长期记忆。

**V1.1** — 文档解析突破：集成 MinerU v4 API，PDF/Word/PPT/Excel/图片直接上传解析为结构化 Markdown。RAG 检索链路从纯相似度搜索重构为 MMR 检索 + CrossEncoderReranker（bge-reranker-large）全局重排。文档分割从 SemanticChunker 切换为 RecursiveCharacterTextSplitter（中文标点优先分隔符）。

**V1.11** — API 修复与前端完善：修正 MinerU v4 仅接受公网 URL 的调用方式，server.py 改为二进制直接落盘，前端全格式文件上传、页脚版本号。

**V1.12** — 本地 GPU 引擎尝试：集成 mineru 本地引擎（HuggingFace VLM + PyTorch），GPU 本地推理 PDF/Office 文档。移除 python-docx、python-pptx 等自定义解析分支，统一由 mineru 处理。清理 langchain-experimental、pypdf 等未使用依赖。

**V1.2** — 轻量化上云：本地 mineru 引擎切回云端 `langchain-mineru` flash 模式，移除 torch/torchvision/transformers/accelerate 四个重型依赖，磁盘占用减少约 8GB，部署门槛大幅降低。新增 router_node 意图分类节点，闲聊与研究双通道分离。验证 Prompt 三段式合并为一步比对。

## 系统架构

```mermaid
graph TD
    START([用户输入 文件/文本]) --> ROUTER{router_node<br/>LLM 意图分类}
    ROUTER -->|chat| CHAT[chat_node<br/>闲聊对话 / 历史查询]
    CHAT --> END1([结束])
    ROUTER -->|research| PARSE[parse_document<br/>MinerU 云端解析<br/>+ 语义切片 + 向量入库]
    PARSE -->|解析成功| EXTRACT[extract_data<br/>两步 LLM 提取<br/>元信息 + 财务数据]
    PARSE -->|解析失败| END2([结束])
    EXTRACT --> VERIFY[verify_data<br/>MCP 金融数据库<br/>交叉比对 + 置信度标注]
    VERIFY --> CALC[calc_metrics<br/>Agent 自主决策<br/>调用 PE/PB/ROE 计算工具]
    CALC --> REPORT[generate_report<br/>RAG 交叉验证 + LLM<br/>生成七章结构化研报]
    REPORT -->|首次生成| REVIEW[review_quality<br/>独立模型 5 维度审核<br/>数字溯源 / 来源标注]
    REPORT -->|重写后| END3([结束])
    REVIEW -->|通过| END4([结束])
    REVIEW -->|不通过 ≤1次| REPORT
    REVIEW -->|不通过 >1次| END5([结束])
```

## 核心流程

**router_node（意图分类）** — LLM 全量语义判断用户输入是闲聊还是研报分析。有文件上传则直接进入研究流程。曾用关键词匹配但"你是研报助手吗"之类的能力询问含"研报"关键词会被误判，故全量交给 LLM。

**chat_node（闲聊对话）** — 二级意图分类：纯闲聊（≤3 句回复）或历史查询（从 PostgreSQL 搜索过往分析记录）。支持模糊搜索公司名，保留最近 10 条对话记忆。

**parse_document（文档解析）** — `langchain-mineru` flash 模式下，文件上传至 mineru.net 云端解析为结构化 Markdown，自动识别表格、公式、排版。输出经 RecursiveCharacterTextSplitter（chunk_size=1024, overlap=150, 中文标点优先）语义切片后写入 ChromaDB，已索引文件自动去重。

**extract_data（数据提取）** — 两步 LLM 提取：先提取公司名、股票代码、评级、目标价等元信息，再基于上下文提取营收、净利润、EPS、PE、PB、ROE 等 17 个财务指标及核心观点、风险提示。两步各自独立容错，一步失败不阻断另一路。

**verify_data（数据验证）** — MCP 协议对接 AKTools A 股金融数据库。自动搜索股票代码 → 拉取公开财报指标 → LLM 一次性比对研报值，输出四级置信度（high/medium/low/unverified）。

**calc_metrics（指标计算，Agent 节点）** — LLM 自主决策调用 4 个 Python 计算工具（calc_pe_ratio / calc_pb_ratio / calc_roe / calc_growth_rate）。优先使用验证通过的高置信度公开数据替代研报原始值。LLM 不负责数学运算，只负责决策调用哪些工具。

**generate_report（报告生成）** — 整合提取 + 验证 + 计算 + RAG 交叉验证（多查询 MMR 检索 + CrossEncoderReranker 重排），生成七章结构化 Markdown 研报：研报概览、核心观点解读、关键财务分析、估值与验证分析、历史研报交叉验证、风险提示、总结。所有数字标注来源，低置信度指标强制提醒。

**review_quality（质量审核）** — 独立模型（温度=0）从数据准确性、来源标注、置信度披露、章节完整性、格式规范五维度审核。硬约束：RAG 交叉验证引用必须有原文依据，数字必须在源数据中有对应值。不通过则带具体反馈回退重写，最多 1 次。

## MinerU 集成说明

研报分析的核心瓶颈在于 PDF 解析：券商研报普遍使用双栏排版、嵌入图表、混合表格，传统 PyPDF2/pdfplumber 等工具提取效果极差，表格错位、段落断裂是常态。

本项目选用 [MinerU](https://mineru.net) 解决文档解析问题，其 VLM 多模态模型能自动识别 PDF/Word/PPT/Excel/图片中的布局、表格、公式和排版，输出高质量 Markdown。集成方式采用 [langchain-mineru](https://pypi.org/project/langchain-mineru/) 的 `MinerULoader`，flash 模式免费免注册，文件上传至 mineru.net 云端完成解析，返回 LangChain Document 对象直接接入后续 RAG 流程。整个解析链路无需 GPU、无需本地模型、无需额外配置，一行 `pip install langchain-mineru` 即可。

Flash 模式限制：单文件 ≤10MB、≤20 页。超出限制可申请免费 API Token 切换 precision 模式（支持 200MB、600 页，更好的表格/公式识别）。

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
├── nodes/                 # 7 个节点文件（+ router_node 内联在 graph.py）
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
