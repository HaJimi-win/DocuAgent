"""
向量存储模块：Chroma 向量库初始化与检索
"""
from langchain_chroma import Chroma
from config import embedding, CHROMA_PATH, logger

# 初始化 Chroma 向量库
logger.info("正在初始化Chroma向量库...")
vector_store = Chroma(
    collection_name="doc_agent",
    embedding_function=embedding,
    persist_directory=CHROMA_PATH,
)
retriever = vector_store.as_retriever(k=4)
logger.info("Chroma向量库初始化完成: %s", CHROMA_PATH)


def add_documents(texts: list):
    """批量写入文本切片到向量库"""
    vector_store.add_texts(texts)
