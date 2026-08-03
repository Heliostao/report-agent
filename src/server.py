"""FastAPI 服务 — 前端 API 桥接"""
import os
import uuid
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.graph import graph, HAS_CHECKPOINTER
from src.memory.long_term import init_db, save_report
from src.mcps.aktools_client import warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server 启动时预热 MCP 连接，避免首次调用握手耗时。"""
    await warmup()
    yield


app = FastAPI(title="Report Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


# ────────────── 请求模型 ──────────────

class TextInput(BaseModel):
    message: str
    session_id: str = ""


# ────────────── API ──────────────

def _config(session_id: str = ""):
    """返回固定 thread_id 配置，让 Checkpointer 生效。未提供时自动生成。"""
    if HAS_CHECKPOINTER:
        tid = session_id or str(uuid.uuid4())
        return {"configurable": {"thread_id": tid}}
    return None


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/analyze/text")
async def analyze_text(body: TextInput):
    """接收用户消息，Checkpointer 自动管理对话历史。"""
    session_id = body.session_id or str(uuid.uuid4())
    cfg = _config(session_id)
    invoke_args = {"user_message": body.message}
    result = await graph.ainvoke(invoke_args, cfg) if cfg else await graph.ainvoke(invoke_args)

    if result.get("intent") == "chat":
        return {
            "type": "chat",
            "reply": result.get("chat_reply", ""),
            "messages": result.get("messages", []),
            "session_id": session_id,
        }

    # 研报结果 — 始终保存
    init_db()
    save_report(result)

    return {
        "type": "report",
        "report": result.get("draft_report", ""),
        "review_passed": result.get("review_passed", False),
        "review_feedback": result.get("review_feedback", ""),
    }


@app.post("/api/analyze/file")
async def analyze_file(file: UploadFile = File(...)):
    """接收 .txt/.md 文件，运行完整研报分析流程。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".txt", ".md"):
        return {"type": "error", "message": f"不支持的文件格式: {ext}，仅支持 .txt / .md"}

    content = await file.read()
    text = content.decode("utf-8")

    # 写入临时文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=ext, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        cfg = _config()  # 文件分析不需要跨会话记忆
        result = await graph.ainvoke({"file_path": tmp_path}, cfg) if cfg else await graph.ainvoke({"file_path": tmp_path})

        # 始终保存
        init_db()
        save_report(result)

        return {
            "type": "report",
            "report": result.get("draft_report", ""),
            "review_passed": result.get("review_passed", False),
            "review_feedback": result.get("review_feedback", ""),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ────────────── 静态文件 ──────────────

if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main():
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
