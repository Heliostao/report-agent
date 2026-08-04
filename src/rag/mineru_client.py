"""MinerU 文档解析客户端 - 基于 langchain-mineru

MinerULoader 是 MinerU 的官方 LangChain 集成，统一处理本地文件和公网 URL：
  - flash 模式（默认）：免费，无需 API Token，云端解析，文件 ≤10MB / ≤20 页
  - precision 模式：需申请免费 API Token，云端解析，文件 ≤200MB / ≤600 页

所有解析均在 mineru.net 云端完成，本地无需 GPU / PyTorch / 模型下载。
"""

from langchain_core.documents import Document
from langchain_mineru import MinerULoader


def parse_to_documents(source: str, mode: str = "flash") -> list[Document]:
    """使用 MinerULoader 解析文件或 URL，返回 LangChain Document 列表。

    Args:
        source: 本地文件路径 或 公网 URL
        mode: "flash"（免费免 token）或 "precision"（需设置 MINERU_TOKEN 环境变量）
    """
    loader = MinerULoader(source=source, mode=mode)
    docs = loader.load()
    for doc in docs:
        doc.metadata.setdefault("source", source)
        doc.metadata["parser"] = f"mineru_{mode}"
    return docs
