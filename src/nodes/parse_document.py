"""
节点①：解析文档

加载文档（支持 PDF / txt / md）→ RecursiveCharacterTextSplitter 语义分割 →
输出 chunks + raw_text → 写入 Chroma 向量库，供后续报告生成做 RAG 交叉验证。
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from src.rag.document_util import load_document
from src.rag.chroma_store import add_documents, get_indexed_sources
from src.state.research_state import ResearchState, DocumentChunk


async def parse_document(state: ResearchState) -> dict:
    """加载文档 → RecursiveCharacterTextSplitter 分割 → 输出 chunks → 写入 Chroma"""

    file_path = state.get("file_path")
    user_message = state.get("user_message", "")

    # ── 1. 加载文档 ──
    if file_path:
        docs = load_document(file_path)
        raw_text = "\n\n".join(d.page_content for d in docs)
    elif user_message.strip():
        raw_text = user_message.strip()
        file_path = None
        docs = []
    else:
        return {"error": "没有可解析的输入（既无文件路径也无文本内容）"}

    # ── 2. 语义分割 ──
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1024,
        chunk_overlap=150,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
    )

    if docs:
        chunks = splitter.split_documents(docs)
    else:
        # 纯文本输入（无文件），手动包装为 Document 再分割
        doc = Document(page_content=raw_text, metadata={"source": "user_input"})
        chunks = splitter.split_documents([doc])

    # ── 3. 转换为 State 中的 DocumentChunk ──
    result_chunks = []
    for i, chunk in enumerate(chunks):
        result_chunks.append(DocumentChunk(
            index=i,
            text=chunk.page_content,
            chunk_type="text",
            heading=chunk.metadata.get("heading", ""),
        ))

    # ── 4. 写入 Chroma 向量库 ──
    if file_path:
        indexed = get_indexed_sources()
        if file_path not in indexed:
            try:
                add_documents(chunks, source=file_path)
            except Exception as e:
                print(f"[parse_document] Chroma 写入失败（不影响后续环节）：{e}")

    return {"raw_text": raw_text, "chunks": result_chunks}
