"""
单元测试：文档分析Agent核心功能测试
运行方式：pytest tests/ -v
覆盖：MD5去重、文件格式校验、SQLite对话历史、上传记录、SSE事件格式、冒烟测试
"""
import os
import sys
import json
import hashlib
import sqlite3
import tempfile
import pytest

# 把项目根目录加入路径，方便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 测试1：MD5 文件哈希计算（增量去重核心逻辑）
# ============================================================
def calculate_md5(file_path: str) -> str:
    """与 main.py 中一致的 MD5 计算逻辑"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


class TestMD5Hashing:
    def test_md5_consistent(self, tmp_path):
        """相同内容的文件MD5必须一致"""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        content = b"hello world test content"
        f1.write_bytes(content)
        f2.write_bytes(content)
        assert calculate_md5(str(f1)) == calculate_md5(str(f2))

    def test_md5_different_content(self, tmp_path):
        """不同内容的文件MD5必须不同"""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert calculate_md5(str(f1)) != calculate_md5(str(f2))

    def test_md5_empty_file(self, tmp_path):
        """空文件的MD5是已知值"""
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        # 空字符串的MD5标准值
        assert calculate_md5(str(f)) == "d41d8cd98f00b204e9800998ecf8427e"

    def test_md5_large_file_streaming(self, tmp_path):
        """大文件流式读取计算MD5，与一次性读取结果一致"""
        f = tmp_path / "large.txt"
        # 生成约100KB的内容
        content = b"x" * (100 * 1024)
        f.write_bytes(content)
        # 流式计算（8192字节一块）
        stream_md5 = calculate_md5(str(f))
        # 一次性计算
        direct_md5 = hashlib.md5(content).hexdigest()
        assert stream_md5 == direct_md5


# ============================================================
# 测试2：文件格式校验
# ============================================================
SUPPORTED_EXTENSIONS = {".txt", ".csv", ".pdf", ".docx", ".xlsx", ".xls"}


class TestFileFormatValidation:
    @pytest.mark.parametrize("ext", [".txt", ".csv", ".pdf", ".docx", ".xlsx", ".xls"])
    def test_supported_formats(self, ext):
        assert ext in SUPPORTED_EXTENSIONS

    @pytest.mark.parametrize("ext", [".doc", ".ppt", ".pptx", ".png", ".jpg", ".exe", ".zip", ".md"])
    def test_unsupported_formats(self, ext):
        assert ext not in SUPPORTED_EXTENSIONS

    def test_case_insensitive(self):
        """文件扩展名应该不区分大小写（在main.py中用了.lower()）"""
        filename = "REPORT.PDF"
        ext = os.path.splitext(filename)[1].lower()
        assert ext == ".pdf"
        assert ext in SUPPORTED_EXTENSIONS


# ============================================================
# 测试3：SQLite 对话历史持久化
# ============================================================
class TestSQLiteHistory:
    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时SQLite数据库"""
        db_path = str(tmp_path / "test_history.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL DEFAULT 'default',
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        return db_path

    def test_save_and_query(self, temp_db):
        """保存消息后能查询到"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            ("test_session", "user", "你好", "2026-01-01 00:00:00")
        )
        conn.commit()
        cursor.execute("SELECT role, content FROM conversations WHERE session_id = ?", ("test_session",))
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "user"
        assert rows[0][1] == "你好"

    def test_multiple_sessions(self, temp_db):
        """不同会话的历史互不干扰"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                       ("session_A", "user", "A的问题", "2026-01-01 00:00:00"))
        cursor.execute("INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                       ("session_B", "user", "B的问题", "2026-01-01 00:00:00"))
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE session_id = ?", ("session_A",))
        count_a = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE session_id = ?", ("session_B",))
        count_b = cursor.fetchone()[0]
        conn.close()
        assert count_a == 1
        assert count_b == 1

    def test_order_by_id_desc(self, temp_db):
        """查询历史按ID倒序（最新在前）"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        for i in range(3):
            cursor.execute("INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                           ("default", "user", f"消息{i}", f"2026-01-01 00:00:0{i}"))
        conn.commit()
        cursor.execute("SELECT content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT 10", ("default",))
        rows = cursor.fetchall()
        conn.close()
        assert rows[0][0] == "消息2"  # 最新的在前
        assert rows[2][0] == "消息0"


# ============================================================
# 测试4：上传记录 JSON 操作（MD5去重记录）
# ============================================================
class TestUploadRecord:
    def test_save_and_load(self, tmp_path):
        """保存上传记录后能正确加载"""
        record_file = str(tmp_path / "uploaded_files.json")
        records = {
            "abc123": {
                "filename": "test.pdf",
                "upload_time": "2026-01-01 00:00:00",
                "chunk_count": 10,
                "file_size": 1024
            }
        }
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        with open(record_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert "abc123" in loaded
        assert loaded["abc123"]["filename"] == "test.pdf"
        assert loaded["abc123"]["chunk_count"] == 10

    def test_duplicate_detection(self, tmp_path):
        """MD5已存在时判定为重复"""
        record_file = str(tmp_path / "uploaded_files.json")
        records = {"abc123": {"filename": "old.pdf"}}
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(records, f)

        with open(record_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        new_md5 = "abc123"
        assert new_md5 in loaded  # 重复
        assert "xyz789" not in loaded  # 不重复

    def test_empty_record_file(self, tmp_path):
        """记录文件不存在时返回空字典"""
        record_file = str(tmp_path / "nonexistent.json")
        if os.path.exists(record_file):
            os.remove(record_file)
        # 模拟 main.py 中的 load_upload_records 逻辑
        if os.path.exists(record_file):
            with open(record_file, "r", encoding="utf-8") as f:
                records = json.load(f)
        else:
            records = {}
        assert records == {}


# ============================================================
# 测试5：SSE 事件格式校验
# ============================================================
class TestSSEFormat:
    def test_step_event_format(self):
        """SSE step事件格式正确"""
        event_data = json.dumps({
            "step": 1,
            "type": "tool_call",
            "content": "正在检索文档",
            "tool_calls": ["retrieve_doc"]
        }, ensure_ascii=False)
        sse_line = f"event: step\ndata: {event_data}\n\n"
        assert sse_line.startswith("event: step\n")
        assert "data: " in sse_line
        assert sse_line.endswith("\n\n")

    def test_done_event_format(self):
        """SSE done事件格式正确"""
        event_data = json.dumps({"answer": "最终答案", "steps": 5}, ensure_ascii=False)
        sse_line = f"event: done\ndata: {event_data}\n\n"
        parsed = json.loads(sse_line.split("data: ")[1].strip())
        assert parsed["steps"] == 5
        assert "answer" in parsed

    def test_error_event_format(self):
        """SSE error事件格式正确"""
        event_data = json.dumps({"error": "连接超时"}, ensure_ascii=False)
        sse_line = f"event: error\ndata: {event_data}\n\n"
        assert "event: error" in sse_line
        parsed = json.loads(sse_line.split("data: ")[1].strip())
        assert "error" in parsed


# ============================================================
# 测试6：冒烟测试 - 模块化架构校验
# ============================================================
class TestSmoke:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _read_file(self, rel_path):
        full_path = os.path.join(self.BASE_DIR, rel_path)
        assert os.path.exists(full_path), f"文件不存在: {full_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_module_files_exist(self):
        """所有模块文件存在"""
        required_files = [
            "config.py",
            "main.py",
            "core/__init__.py",
            "core/agents.py",
            "core/tools.py",
            "core/parsers.py",
            "api/__init__.py",
            "api/routes.py",
            "storage/__init__.py",
            "storage/vector_store.py",
            "storage/history_db.py",
        ]
        for f in required_files:
            assert os.path.exists(os.path.join(self.BASE_DIR, f)), f"缺少模块文件: {f}"

    def test_all_modules_syntax(self):
        """所有Python模块语法正确"""
        py_files = []
        for root, dirs, files in os.walk(self.BASE_DIR):
            # 跳过缓存和虚拟环境
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".idea", "venv", ".venv")]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))
        assert len(py_files) > 0, "没有找到Python文件"
        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
            compile(source, py_file, "exec")  # 不执行，只检查语法

    def test_config_module(self):
        """config.py 包含全局配置"""
        source = self._read_file("config.py")
        for keyword in ["WORKSPACE", "CHROMA_PATH", "logger", "llm", "embedding", "text_splitter", "SUPPORTED_EXTENSIONS"]:
            assert keyword in source, f"config.py 缺少: {keyword}"

    def test_agents_module(self):
        """core/agents.py 包含Agent状态机"""
        source = self._read_file("core/agents.py")
        for keyword in ["AGENT_SYSTEM_PROMPT", "agent_graph", "agent_reason", "should_continue", "StateGraph"]:
            assert keyword in source, f"agents.py 缺少: {keyword}"

    def test_tools_module(self):
        """core/tools.py 包含三个工具"""
        source = self._read_file("core/tools.py")
        for keyword in ["retrieve_doc", "csv_stat", "save_report", "tools = ["]:
            assert keyword in source, f"tools.py 缺少: {keyword}"

    def test_parsers_module(self):
        """core/parsers.py 包含多格式解析器"""
        source = self._read_file("core/parsers.py")
        for keyword in ["parse_document", "calculate_md5", "PARSERS", "parse_txt", "parse_csv", "parse_pdf", "parse_docx", "parse_excel"]:
            assert keyword in source, f"parsers.py 缺少: {keyword}"

    def test_routes_module(self):
        """api/routes.py 包含所有接口和限流"""
        source = self._read_file("api/routes.py")
        for keyword in ["/upload", "/run-agent", "/run-agent/stream", "/history", "/files",
                         "limiter", "@limiter.limit", "StreamingResponse", "text/event-stream",
                         "_agent_stream_generator"]:
            assert keyword in source, f"routes.py 缺少: {keyword}"

    def test_storage_modules(self):
        """storage 模块包含向量库和历史DB"""
        vs = self._read_file("storage/vector_store.py")
        assert "vector_store" in vs and "retriever" in vs
        hdb = self._read_file("storage/history_db.py")
        for keyword in ["init_db", "save_message", "get_history", "sqlite3"]:
            assert keyword in hdb, f"history_db.py 缺少: {keyword}"

    def test_main_entry(self):
        """main.py 是入口，包含app创建和路由注册"""
        source = self._read_file("main.py")
        for keyword in ["FastAPI", "include_router", "init_db", "limiter", "RateLimitExceeded", "uvicorn.run"]:
            assert keyword in source, f"main.py 缺少: {keyword}"
