"""
报告管理模块：报告预览暂存、自动命名、重新生成、确认保存
实现"生成预览 → 用户确认 → 保存/重新生成"的中间层流程
"""
import os
import re
from datetime import datetime
from config import llm, WORKSPACE, logger

# ============================================================
# 报告暂存（内存字典，按 session_id 存储，重新生成时覆盖）
# ============================================================
# 结构: { session_id: { "content": str, "meta": dict, "version": int, "created_at": str } }
_pending_reports: dict = {}


def store_pending_report(session_id: str, content: str, meta: dict = None):
    """暂存待确认的报告预览（覆盖前一份，避免占空间）"""
    existing = _pending_reports.get(session_id)
    version = existing["version"] + 1 if existing else 1
    _pending_reports[session_id] = {
        "content": content,
        "meta": meta or {},
        "version": version,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    logger.info("报告预览已暂存: session=%s, version=v%d, 长度=%d",
                session_id, version, len(content))


def get_pending_report(session_id: str) -> dict | None:
    """获取待确认的报告预览"""
    return _pending_reports.get(session_id)


def clear_pending_report(session_id: str):
    """清除暂存的报告（保存成功后调用）"""
    if session_id in _pending_reports:
        del _pending_reports[session_id]
        logger.info("报告暂存已清除: session=%s", session_id)


# ============================================================
# 自动命名：[报告类型] + [主体/范围] + [时间] + [版本/状态]
# ============================================================
def _detect_report_type(content: str) -> str:
    """从报告内容推断报告类型"""
    text = content[:500]
    if any(kw in text for kw in ["统计", "数据分析", "数据报告", "describe", "均值", "标准差"]):
        return "数据分析报告"
    if any(kw in text for kw in ["总结", "概述", "主要内容", "摘要"]):
        return "内容总结报告"
    if any(kw in text for kw in ["研究", "调研", "分析报告", "研究报告"]):
        return "研究分析报告"
    return "文档分析报告"


def _extract_subject(content: str, user_query: str = "") -> str:
    """从用户问题或报告内容提取主体/范围"""
    # 优先从用户问题提取
    if user_query:
        # 去掉常见动词，保留名词主体
        cleaned = re.sub(r"(总结|分析|统计|生成|保存|报告|文档|一下|帮我|请)", "", user_query)
        cleaned = cleaned.strip().strip("，。、,.!?！？")
        if cleaned and len(cleaned) <= 30:
            return cleaned
    # 从报告标题提取（第一个 # 开头的行）
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            title = re.sub(r"^#+\s*", "", line).strip()
            if title and len(title) <= 30:
                return title
            break
    return "文档分析"


def generate_filename(content: str, user_query: str = "", version: int = 1) -> str:
    """
    自动生成报告文件名
    格式：[报告类型]_[主体/范围]_[时间]_[版本].md
    示例：研究分析报告_水稻协同作业技术_20260827_v1.md
    """
    report_type = _detect_report_type(content)
    subject = _extract_subject(content, user_query)
    date_str = datetime.now().strftime("%Y%m%d")
    # 清理主体中的非法文件名字符
    subject = re.sub(r'[\\/:*?"<>|\s]+', "_", subject).strip("_")
    if not subject:
        subject = "文档分析"
    filename = f"{report_type}_{subject}_{date_str}_v{version}.md"
    return filename


# ============================================================
# 重新生成报告（基于已有上下文 + 用户反馈，调用 LLM）
# ============================================================
REGENERATE_PROMPT = """
你是一位资深文档分析专家。请基于以下上下文重新生成一份 Markdown 格式的分析报告。

# 原始用户需求
{user_query}

# 已有报告内容（参考但不要完全照搬）
{old_content}

# 用户反馈（如有）
{feedback}

# 要求
1. 重新组织结构和表述，生成一份与原报告不同的新报告
2. 所有结论必须基于已有内容，不要编造新信息
3. 使用 Markdown 格式，包含清晰的章节标题
4. 报告长度适中，重点突出
5. 直接输出报告内容，不要输出额外的解释或对话

现在请生成新报告：
"""


def regenerate_report(session_id: str, user_query: str = "", feedback: str = "") -> dict:
    """
    重新生成报告预览（覆盖前一份）
    返回: {"content": str, "filename": str, "version": int}
    """
    pending = get_pending_report(session_id)
    if not pending:
        raise ValueError("没有待确认的报告，无法重新生成")

    old_content = pending["content"]
    prompt = REGENERATE_PROMPT.format(
        user_query=user_query or "（未提供）",
        old_content=old_content,
        feedback=feedback or "（无特殊反馈，请重新组织报告）",
    )

    try:
        logger.info("正在重新生成报告: session=%s, version=v%d",
                    session_id, pending["version"] + 1)
        resp = llm.invoke(prompt)
        new_content = resp.content if hasattr(resp, "content") else str(resp)

        # 暂存新报告（覆盖前一份）
        store_pending_report(session_id, new_content, pending.get("meta", {}))
        new_pending = get_pending_report(session_id)
        filename = generate_filename(new_content, user_query, new_pending["version"])

        logger.info("报告重新生成成功: session=%s, version=v%d",
                    session_id, new_pending["version"])
        return {
            "content": new_content,
            "filename": filename,
            "version": new_pending["version"],
        }
    except Exception as e:
        logger.error("报告重新生成失败: %s", e)
        raise


# ============================================================
# 确认保存报告
# ============================================================
def confirm_save_report(session_id: str, filename: str = None) -> dict:
    """
    确认保存暂存的报告到 workspace
    返回: {"ok": bool, "filename": str, "path": str, "version": int}
    """
    pending = get_pending_report(session_id)
    if not pending:
        raise ValueError("没有待确认的报告")

    content = pending["content"]
    version = pending["version"]

    # 文件名处理
    if not filename:
        filename = generate_filename(content, "", version)
    # 确保以 .md 结尾
    if not filename.endswith(".md"):
        filename += ".md"
    # 安全校验：防止路径穿越
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("文件名不合法，不能包含路径分隔符")

    out_path = os.path.join(WORKSPACE, filename)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("报告保存成功: %s (v%d, %d字节)", filename, version, len(content))
        # 保存成功后清除暂存
        clear_pending_report(session_id)
        return {
            "ok": True,
            "filename": filename,
            "path": out_path,
            "version": version,
        }
    except Exception as e:
        logger.error("报告保存失败: %s", e)
        raise


# ============================================================
# 从 Agent 输出中解析报告预览（检测标记）
# ============================================================
REPORT_START = "===REPORT_PREVIEW==="
REPORT_META = "===REPORT_META==="
REPORT_END = "===REPORT_END==="


def parse_report_preview(text: str) -> dict | None:
    """
    从 Agent 输出文本中解析报告预览
    检测 ===REPORT_PREVIEW=== ... ===REPORT_END=== 标记
    返回: {"content": str, "meta": dict} 或 None
    """
    if REPORT_START not in text:
        return None

    try:
        # 提取报告内容
        start_idx = text.index(REPORT_START) + len(REPORT_START)
        end_idx = text.index(REPORT_END, start_idx) if REPORT_END in text[start_idx:] else len(text)
        content = text[start_idx:end_idx].strip()

        # 提取元数据（如果有）
        meta = {}
        if REPORT_META in content:
            meta_idx = content.index(REPORT_META)
            meta_text = content[meta_idx + len(REPORT_META):].strip()
            content = content[:meta_idx].strip()
            # 尝试解析 JSON 元数据
            try:
                import json
                meta = json.loads(meta_text)
            except Exception:
                meta = {"raw": meta_text}

        if content:
            logger.info("从 Agent 输出中解析到报告预览: 长度=%d", len(content))
            return {"content": content, "meta": meta}
    except Exception as e:
        logger.warning("解析报告预览失败: %s", e)
    return None


def strip_report_markers(text: str) -> str:
    """从文本中移除报告标记，返回干净的展示文本"""
    if REPORT_START not in text:
        return text
    # 移除标记行，保留报告内容供展示
    result = text
    for marker in [REPORT_START, REPORT_META, REPORT_END]:
        result = result.replace(marker, "")
    return result.strip()
