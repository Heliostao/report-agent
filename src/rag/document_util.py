"""文档加载器映射，支持 .md / .txt"""
import os

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_core.documents import Document

LOADER_MAP = {
    ".md": UnstructuredMarkdownLoader,
}


def load_document(file_path: str):
    """根据扩展名自动选择 Loader 加载文档。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return _load_txt_with_fallback(file_path)
    loader_cls = LOADER_MAP.get(ext)
    if not loader_cls:
        raise ValueError(f"不支持的文件格式: {ext}")
    return loader_cls(file_path).load()


def _load_txt_with_fallback(file_path: str):
    """UTF-8 → GBK 编码回退加载 txt。"""
    for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            return [Document(page_content=text, metadata={"source": file_path})]
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法识别文件编码: {file_path}")
