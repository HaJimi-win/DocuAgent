"""
Agent 工具模块：检索、CSV统计、报告保存
每个工具带异常处理，失败时返回错误信息给大模型。
"""
import os
from langchain_core.tools import tool
import pandas as pd

from config import WORKSPACE, logger
from storage.vector_store import retriever


@tool
def retrieve_doc(query: str) -> str:
    """检索已上传文档知识库，获取相关片段。当用户问题涉及文档内容时使用。
    Args:
        query: 用户查询问题
    """
    try:
        docs = retriever.invoke(query)
        if not docs:
            return "知识库中未找到相关内容，请确认文档已上传。"
        result = "\n====片段====\n".join([d.page_content for d in docs])
        logger.info("检索文档成功, query=%s, 命中%d段", query[:30], len(docs))
        return result
    except Exception as e:
        logger.error("文档检索失败: %s", e)
        return f"文档检索工具执行失败: {e}"


@tool
def csv_stat(file_name: str) -> str:
    """对workspace下csv文件做基础统计，输出描述信息。当用户需要数据分析时使用。
    Args:
        file_name: workspace目录下的csv文件名（仅文件名，不含路径）
    """
    try:
        fp = os.path.join(WORKSPACE, file_name)
        if not os.path.exists(fp):
            return f"文件不存在: {file_name}，请确认文件名是否正确。"
        df = pd.read_csv(fp)
        result = f"形状:{df.shape}\n描述统计:\n{df.describe().to_string()}"
        logger.info("CSV统计成功: %s", file_name)
        return result
    except Exception as e:
        logger.error("CSV统计失败: %s", e)
        return f"CSV统计工具执行失败: {e}"


@tool
def save_report(report_content: str, out_filename: str) -> str:
    """把分析报告保存为markdown到workspace目录。当用户要求保存/导出报告时使用。
    Args:
        report_content: markdown报告文本
        out_filename: 输出文件名，如 analysis.md（建议以.md结尾）
    """
    try:
        # 安全校验：防止路径穿越
        if ".." in out_filename or "/" in out_filename or "\\" in out_filename:
            return "文件名不合法，不能包含路径分隔符。"
        out_path = os.path.join(WORKSPACE, out_filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        logger.info("报告保存成功: %s (%d字节)", out_filename, len(report_content))
        return f"报告已保存:{out_path}"
    except Exception as e:
        logger.error("报告保存失败: %s", e)
        return f"报告保存工具执行失败: {e}"


# 工具集合
tools = [retrieve_doc, csv_stat, save_report]
