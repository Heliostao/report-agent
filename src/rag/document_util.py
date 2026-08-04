"""文档加载器，支持 .pdf / .doc / .docx / .ppt / .pptx / .xls / .xlsx / .txt / .md / 公网 URL
统一返回 List[Document]

所有 PDF / Office / 图片 / URL 统一通过 langchain-mineru 的 MinerULoader 处理，
在 mineru.net 云端解析，本地无需 GPU。
"""

import os

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document


def load_document(file_path: str):
    """根据扩展名自动选择 Loader，返回 List[Document]。"""
    is_url = file_path.startswith(("http://", "https://"))
    ext = os.path.splitext(file_path.split("?")[0])[1].lower()

    # ── PDF / Office / 图片 / URL → MinerULoader（云端解析，flash 模式免费）──
    if is_url or ext in (
        ".pdf", ".doc", ".docx", ".ppt", ".pptx",
        ".xls", ".xlsx", ".png", ".jpg", ".jpeg",
    ):
        return _load_via_mineru(file_path)

    # ── Markdown ──
    if ext == ".md":
        return _load_md(file_path)

    # ── 纯文本 ──
    if ext == ".txt":
        return _load_txt_with_fallback(file_path)

    raise ValueError(
        f"不支持的文件格式: {ext}，"
        f"支持 .pdf / .doc / .docx / .ppt / .pptx / .xls / .xlsx / .txt / .md"
    )


def _load_via_mineru(source: str):
    """通过 MinerULoader 云端解析（flash 模式，免费免 API Token）。"""
    from langchain_mineru import MinerULoader

    print(f"[mineru] 开始解析: {source}")
    loader = MinerULoader(source=source, mode="flash")
    docs = loader.load()
    for doc in docs:
        doc.metadata.setdefault("source", source)
        doc.metadata["parser"] = "mineru_flash"
    print(f"[mineru] 解析完成，共 {sum(len(d.page_content) for d in docs)} 字符")
    return docs


# ── Markdown / 纯文本 ──

def _load_md(file_path: str):
    docs = UnstructuredMarkdownLoader(file_path).load()
    for doc in docs:
        doc.metadata.setdefault("source", file_path)
    return docs


def _load_txt_with_fallback(file_path: str):
    for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            return [Document(page_content=text, metadata={"source": file_path})]
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {file_path}")
