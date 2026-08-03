"""
全局配置文件
从env文件中读取配置
"""
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
load_dotenv()

# 主LLM
main_model = os.getenv("MAIN_MODEL", "qwen3.7-plus")
main_model_url = os.getenv("MAIN_BASE_URL" )
main_model_api_key = os.getenv("MAIN_API_KEY")

# 助手LLM
assist_model = os.getenv("ASSIST_MODEL", "deepseek-v4-pro")
assist_model_url = os.getenv("ASSIST_BASE_URL")
assist_model_api_key = os.getenv("ASSIST_API_KEY")

# redis 配置
redis_url = os.getenv("REDIS_URL")

# PostgresSQL配置
postgres_url =os.getenv("POSTGRES_URL")

# chroma配置
chroma_host = os.getenv("CHROMA_HOST")
chroma_port = os.getenv("CHROMA_PORT")
chroma_collection = os.getenv("CHROMA_COLLECTION")

# mcp-aktools — A 股金融数据 MCP（本地 Docker: http://localhost:8808/mcp）
aktools_mcp_url = os.getenv("AKTOOLS_MCP_URL", "http://localhost:8808/mcp")

