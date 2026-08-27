"""
对话历史存储模块：SQLite 持久化对话记录
"""
import sqlite3
from datetime import datetime
from config import DB_PATH, logger


def init_db():
    """初始化SQLite数据库，创建对话历史表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)")
    conn.commit()
    conn.close()
    logger.info("SQLite对话历史库初始化完成: %s", DB_PATH)


def save_message(session_id: str, role: str, content: str):
    """保存一条对话消息到SQLite"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("保存对话历史失败: %s", e)


def get_history(session_id: str = "default", limit: int = 50) -> list:
    """查询指定会话的历史对话，返回列表（按时间正序）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1], "time": r[2]} for r in reversed(rows)]
    except Exception as e:
        logger.error("查询对话历史失败: %s", e)
        return []
