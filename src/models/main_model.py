"""
主要的LLM模型 — main_llm
负责节点①②③④⑤
"""
from langchain_openai import ChatOpenAI

from src.config.util_config import main_model, main_model_url, main_model_api_key

main_llm = ChatOpenAI(
    model=main_model,
    base_url=main_model_url,
    temperature=0.3,
    api_key=main_model_api_key,
)


