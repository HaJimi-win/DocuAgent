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
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)

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
# 向量嵌入模型（独立配置，支持与LLM不同的模型）
# ============================================================
# Embedding 独立配置（硅基流动的对话模型不能直接当Embedding用）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", os.getenv("LLM_API_KEY"))
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", os.getenv("LLM_MODEL"))

logger.info("正在初始化向量嵌入模型: %s", EMBEDDING_MODEL)
embedding = OpenAIEmbeddings(
    api_key=EMBEDDING_API_KEY,
    base_url=EMBEDDING_BASE_URL,
    model=EMBEDDING_MODEL,
    # 非 OpenAI 提供商（SiliconFlow/Ollama/vLLM 等）不支持 token IDs 作为 input，
    # 必须设为 False 以直接发送原始文本字符串，否则会报 20015 参数无效错误
    check_embedding_ctx_length=False,
)

logger.info("向量嵌入模型初始化完成: %s", EMBEDDING_MODEL)
