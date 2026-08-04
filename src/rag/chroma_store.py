"""ChromaDB 向量库管理：入库、检索、同步"""
import chromadb
from langchain_chroma import Chroma

from src.config.util_config import chroma_collection, chroma_host, chroma_port
from src.rag.embeddings import embeddings


def _get_vector_store():
    """通过 HttpClient 连接 Docker 中的 Chroma Server。"""
    client = chromadb.HttpClient(
        host=chroma_host or "localhost",
        port=int(chroma_port or 8000),
    )
    return Chroma(
        client=client,
        collection_name=chroma_collection or "research_reports",
        embedding_function=embeddings,
    )


def add_documents(docs, source: str = None):
    """将 LangChain Document 列表写入 Chroma 向量库。"""
    if not docs:
        return
    store = _get_vector_store()
    try:
        if source:
            for doc in docs:
                doc.metadata.setdefault("source", source)
        store.add_documents(documents=docs)
    finally:
        store._client.close()


def get_indexed_sources():
    store = _get_vector_store()
    try:
        data = store.get(include=["metadatas"])
        metadatas = data.get("metadatas") or []
        sources = {m.get("source") for m in metadatas if m and m.get("source")}
        return sources
    finally:
        store._client.close()
