"""
全局配置模块：日志、目录、大模型、嵌入模型、文本切片器、常量
所有其他模块从这里导入全局单例，避免循环导入。
"""
import os
import sys
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# ============================================================
# 目录常量
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(BASE_DIR, "workspace")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
UPLOAD_RECORD = os.path.join(WORKSPACE, "uploaded_files.json")
DB_PATH = os.path.join(WORKSPACE, "chat_history.db")

for d in [WORKSPACE, CHROMA_PATH, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

# ============================================================
# 支持的文件格式
# ============================================================
SUPPORTED_EXTENSIONS = {".txt", ".csv", ".pdf", ".docx", ".xlsx", ".xls"}

# ============================================================
# 日志系统：控制台 + 文件双输出
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("doc_agent")

# ============================================================
# 文本切片器
# ============================================================
text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)

# ============================================================
# 大模型（可插拔：云端API / Ollama本地）
# ============================================================
logger.info("正在初始化大模型...")
llm = ChatOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    model=os.getenv("LLM_MODEL"),
    temperature=0,
)
logger.info("大模型初始化完成: %s", os.getenv("LLM_MODEL"))

# ============================================================
# 向量嵌入模型
# ============================================================
logger.info("正在初始化向量嵌入模型...")
embedding = OpenAIEmbeddings(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
)
