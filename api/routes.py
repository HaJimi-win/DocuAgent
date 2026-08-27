"""
API 路由模块：FastAPI 所有接口
包含：文件上传、Agent同步执行、Agent SSE流式执行、对话历史、文件列表
"""
import os
import json
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import WORKSPACE, logger
from core.agents import agent_graph
from core.parsers import (
    parse_document, calculate_md5,
    load_upload_records, save_upload_record,
)
from storage.history_db import save_message, get_history
from storage.vector_store import add_documents

# API 限流：按IP限制
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


# ============================================================
# 文件上传接口
# ============================================================
@router.post("/upload")
@limiter.limit("20/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    上传文件接口：
    - 支持 txt/csv/pdf/docx/xlsx/xls
    - MD5去重，重复文件不重复入库
    - 多格式解析，流式读取大文件
    - 解析后批量写入向量库
    """
    logger.info("收到文件上传: %s (%.1fKB)", file.filename, file.size / 1024 if file.size else 0)

    # 1. 校验文件格式
    ext = os.path.splitext(file.filename)[1].lower()
    from config import SUPPORTED_EXTENSIONS
    if ext not in SUPPORTED_EXTENSIONS:
        logger.warning("不支持的文件格式: %s", ext)
        raise HTTPException(status_code=400, detail=f"不支持的格式: {ext}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    # 2. 保存文件到workspace
    save_path = os.path.join(WORKSPACE, file.filename)
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info("文件保存成功: %s", save_path)
    except Exception as e:
        logger.error("文件保存失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    # 3. MD5去重检查
    try:
        file_md5 = calculate_md5(save_path)
        records = load_upload_records()
        if file_md5 in records:
            logger.info("文件已存在（MD5去重）: %s", file.filename)
            return {
                "ok": True,
                "filename": file.filename,
                "skipped": True,
                "message": f"文件已存在（内容完全相同），已跳过重复入库。上传时间: {records[file_md5]['upload_time']}",
            }
    except Exception as e:
        logger.warning("MD5计算失败，跳过去重: %s", e)
        file_md5 = None

    # 4. 多格式解析（流式读取大文件）
    try:
        chunks = parse_document(save_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("文档解析异常: %s", e)
        raise HTTPException(status_code=500, detail=f"文档解析失败: {e}")

    if not chunks:
        logger.warning("文档解析后无有效内容: %s", file.filename)
        return {"ok": True, "filename": file.filename, "chunks": 0, "message": "文档中未提取到有效文本内容。"}

    # 5. 批量写入向量库
    try:
        add_documents(chunks)
        logger.info("向量库写入成功: %s, 切片数: %d", file.filename, len(chunks))
    except Exception as e:
        logger.error("向量库写入失败: %s", e)
        raise HTTPException(status_code=500, detail=f"向量库写入失败: {e}")

    # 6. 记录上传信息
    if file_md5:
        records[file_md5] = {
            "filename": file.filename,
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chunk_count": len(chunks),
            "file_size": os.path.getsize(save_path),
        }
        save_upload_record(records)

    return {
        "ok": True,
        "filename": file.filename,
        "chunks": len(chunks),
        "skipped": False,
        "message": f"上传成功，已解析为{len(chunks)}个文本片段并存入向量库。",
    }


# ============================================================
# Agent 同步执行接口
# ============================================================
@router.post("/run-agent")
@limiter.limit("10/minute")
async def run_agent(request: Request, payload: dict):
    """
    执行Agent任务接口（同步返回，等待全部完成）：
    - 接收用户问题，执行Agent循环
    - 保存对话历史到SQLite
    - 返回执行历史和最终答案
    """
    user_q = payload.get("query", "").strip()
    session_id = payload.get("session_id", "default")

    if not user_q:
        raise HTTPException(status_code=400, detail="问题不能为空")

    logger.info("收到Agent任务: session=%s, query=%s", session_id, user_q[:50])
    save_message(session_id, "user", user_q)

    try:
        stream = agent_graph.stream(
            {"messages": [("user", user_q)], "user_query": user_q},
            stream_mode="values",
        )
        output_messages = []
        for s in stream:
            if "messages" in s:
                output_messages.append(s["messages"][-1])

        final_answer = output_messages[-1].content if output_messages else "未生成回答"
        logger.info("Agent任务完成, 总消息数: %d", len(output_messages))
        save_message(session_id, "assistant", final_answer)

        return {
            "answer": final_answer,
            "history": [m.content for m in output_messages],
        }
    except Exception as e:
        logger.error("Agent执行失败: %s", e, exc_info=True)
        error_msg = f"Agent执行失败: {e}"
        save_message(session_id, "assistant", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# ============================================================
# Agent SSE 流式执行接口
# ============================================================
def _agent_stream_generator(user_q: str, session_id: str):
    """SSE流式生成器：Agent每执行一步就推送一条事件"""
    save_message(session_id, "user", user_q)
    try:
        stream = agent_graph.stream(
            {"messages": [("user", user_q)], "user_query": user_q},
            stream_mode="values",
        )
        step_count = 0
        final_answer = ""
        for s in stream:
            if "messages" in s:
                msg = s["messages"][-1]
                step_count += 1
                msg_type = "tool_call" if (hasattr(msg, "tool_calls") and msg.tool_calls) else "text"
                event_data = json.dumps({
                    "step": step_count,
                    "type": msg_type,
                    "content": msg.content,
                    "tool_calls": [tc["name"] for tc in msg.tool_calls] if (hasattr(msg, "tool_calls") and msg.tool_calls) else [],
                }, ensure_ascii=False)
                yield f"event: step\ndata: {event_data}\n\n"
                final_answer = msg.content

        save_message(session_id, "assistant", final_answer)
        logger.info("SSE Agent任务完成, 总步数: %d", step_count)
        done_data = json.dumps({"answer": final_answer, "steps": step_count}, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"
    except Exception as e:
        logger.error("SSE Agent执行失败: %s", e, exc_info=True)
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        save_message(session_id, "assistant", f"执行失败: {e}")
        yield f"event: error\ndata: {error_data}\n\n"


@router.post("/run-agent/stream")
@limiter.limit("10/minute")
async def run_agent_stream(request: Request, payload: dict):
    """
    SSE流式执行Agent任务接口：
    - Agent每执行一步（思考/工具调用）实时推送到前端
    - 事件类型：step（每一步）、done（完成）、error（错误）
    - 前端用 EventSource 或 fetch+ReadableStream 接收
    """
    user_q = payload.get("query", "").strip()
    session_id = payload.get("session_id", "default")

    if not user_q:
        raise HTTPException(status_code=400, detail="问题不能为空")

    logger.info("收到SSE Agent任务: session=%s, query=%s", session_id, user_q[:50])

    return StreamingResponse(
        _agent_stream_generator(user_q, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 对话历史查询接口
# ============================================================
@router.get("/history")
async def get_chat_history(session_id: str = "default", limit: int = 50):
    """查询对话历史接口"""
    history = get_history(session_id, limit)
    return {"session_id": session_id, "count": len(history), "history": history}


# ============================================================
# 已上传文件列表接口
# ============================================================
@router.get("/files")
async def list_uploaded_files():
    """列出已上传的文件列表"""
    records = load_upload_records()
    files = []
    for md5, info in records.items():
        files.append({
            "filename": info.get("filename"),
            "upload_time": info.get("upload_time"),
            "chunk_count": info.get("chunk_count", 0),
            "file_size": info.get("file_size", 0),
            "md5": md5,
        })
    # 也列出workspace里的实际文件
    workspace_files = []
    for f in os.listdir(WORKSPACE):
        fp = os.path.join(WORKSPACE, f)
        if os.path.isfile(fp) and not f.endswith(".json") and not f.endswith(".db"):
            workspace_files.append(f)
    return {"recorded_files": files, "workspace_files": workspace_files}
