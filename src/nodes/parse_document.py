"""
节点①：解析文档

读取 txt/md 纯文本研报 → SemanticChunker 语义切分 → 输出 chunks →
写入 Chroma 向量库，供后续报告生成做 RAG 交叉验证。
"""
import os
from langchain_experimental.text_splitter import SemanticChunker
from src.rag.embeddings import embeddings
from src.rag.chroma_store import add_chunks, get_indexed_sources
from src.state.research_state import ResearchState, DocumentChunk


def _extract_plain(file_path: str):
    """多编码尝试读取 txt/md 纯文本文件。"""
    for encoding in ["utf-8"]:
        try:
            with open(file_path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {file_path}")


async def parse_document(state: ResearchState) -> dict:
    """提取全文 → SemanticChunker 语义切分 → 输出 chunks → 写入 Chroma"""

    file_path = state.get("file_path")
    user_message = state.get("user_message", "")

    if file_path:
        raw_text = _extract_plain(file_path)
    elif user_message.strip():
        raw_text = user_message.strip()
        file_path = None
    else:
        return {"error": "没有可解析的输入（既无文件路径也无文本内容）"}

    segments = SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=85,
    ).split_text(raw_text)

    result_chunks = []
    for i, seg in enumerate(segments):
        result_chunks.append(DocumentChunk(
            index=i,
            text=seg,
            chunk_type="text",
            heading="",
        ))

    if file_path:
        indexed = get_indexed_sources()
        if file_path not in indexed:
            try:
                add_chunks(
                    [{"text": c["text"], "chunk_type": c.get("chunk_type", "text"),
                      "index": c.get("index", 0)} for c in result_chunks],
                    source=file_path,
                )
            except Exception:
                pass

    return {"raw_text": raw_text, "chunks": result_chunks}
