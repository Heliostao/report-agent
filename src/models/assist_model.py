"""
用于审核的LLM — assist_llm
仅负责节点⑥质量审核，temperature=0 确保审核稳定
"""
from langchain_openai import ChatOpenAI

from src.config.util_config import assist_model, assist_model_url, assist_model_api_key

assist_llm = ChatOpenAI(
    model=assist_model,
    base_url=assist_model_url,
    temperature=0,
    api_key=assist_model_api_key,
)

