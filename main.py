"""
项目入口：组装 FastAPI 应用，注册路由，启动服务
模块化架构：
  config.py            全局配置（日志、LLM、嵌入模型、常量）
  core/
    agents.py          Agent状态机 + System Prompt
    tools.py           工具定义（检索/统计/保存）
    parsers.py         多格式文档解析 + MD5去重
  api/
    routes.py          FastAPI路由（上传/执行/流式/历史/文件）
  storage/
    vector_store.py    Chroma向量库
    history_db.py      SQLite对话历史
运行：python main.py  -> 浏览器访问 http://127.0.0.1:8001
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from config import logger
from api.routes import router, limiter
from storage.history_db import init_db

# 初始化数据库
init_db()

# 创建 FastAPI 应用
app = FastAPI(title="DocuAgent - 文档智能分析服务")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册限流
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 注册路由
app.include_router(router)


@app.get("/")
async def index():
    """返回前端页面"""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 50)
    logger.info("DocuAgent 服务启动中（模块化架构）...")
    logger.info("访问地址: http://127.0.0.1:8001")
    logger.info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001)
