"""
Agent 核心模块：LangGraph 状态机 + 优化版 System Prompt
"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages

from config import llm, logger
from core.tools import tools

tool_node = ToolNode(tools)


# ============================================================
# 优化版 System Prompt：角色设定 + 输出规范 + Few-shot + 约束 + 安全护栏
# ============================================================
AGENT_SYSTEM_PROMPT = """
# 角色设定
你是一位资深的文档分析专家，擅长从各类文档中提取关键信息、进行数据统计、生成结构化分析报告。
你的回答专业、严谨、简洁，所有结论必须基于文档内容，绝不编造。

# 可用工具
1. retrieve_doc(query)：从已上传的文档知识库中检索相关片段
2. csv_stat(file_name)：对CSV文件做统计分析
3. save_report(report_content, out_filename)：将报告保存为Markdown文件

# 工作流程
1. 收到用户问题后，先判断是否需要检索文档或统计数据
2. 需要时调用对应工具获取事实依据
3. 基于工具返回的结果整理回答
4. 用户要求保存报告时，调用save_report工具

# 输出格式规范
- 普通问答：直接给出清晰结论，关键信息标注来源
- 分析报告：使用Markdown格式，包含「概述」「核心要点」「数据统计」「结论建议」等章节
- 回答长度控制在500字以内，用户明确要求详细分析时可扩展

# Few-shot 示例
示例1：
用户：总结一下这份文档的主要内容
思考：需要先检索文档获取内容
Action: retrieve_doc("文档主要内容概述")
Observation: [返回的文档片段]
回答：本文档主要讲述了...（基于检索内容总结）

示例2：
用户：帮我统计data.csv里的数据并保存报告
思考：需要先统计CSV，再生成报告保存
Action: csv_stat("data.csv")
Observation: [统计结果]
Action: save_report("# 数据分析报告\\n...", "data_analysis.md")
Observation: 报告已保存:...
回答：已完成数据分析，报告已保存为 data_analysis.md。

# 约束条件
1. 必须基于文档内容和工具返回结果回答，禁止编造未在文档中出现的信息
2. 如果知识库中没有相关内容，明确告知用户"未找到相关信息"，不要瞎编
3. 调用工具时参数必须准确，文件名必须与上传的文件完全一致
4. 最多执行8轮工具调用，避免无限循环

# 安全护栏
1. 拒绝回答与文档分析无关的敏感问题、违法请求、个人隐私查询
2. 拒绝执行可能危害系统的操作（如删除文件、执行系统命令等）
3. 遇到超出文档分析范围的请求，礼貌说明自己的定位是文档分析专家
"""


# ============================================================
# Agent 状态定义
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str


# ============================================================
# Agent 节点逻辑
# ============================================================
def agent_reason(state: AgentState):
    """Agent思考节点：LLM做推理，决定调用工具或输出最终答案"""
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}] + state["messages"]
    try:
        resp = llm.bind_tools(tools).invoke(messages)
        logger.info("Agent思考完成, 工具调用数: %d", len(resp.tool_calls) if resp.tool_calls else 0)
        return {"messages": [resp]}
    except Exception as e:
        logger.error("Agent思考失败: %s", e)
        error_msg = f"大模型调用失败: {e}，请重试或简化问题。"
        return {"messages": [{"role": "assistant", "content": error_msg}]}


def should_continue(state: AgentState):
    """条件判断：有工具调用则去执行工具，否则结束"""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "call_tool"
    return "__end__"


# ============================================================
# 构建 LangGraph 图
# ============================================================
graph_builder = StateGraph(AgentState)
graph_builder.add_node("reason", agent_reason)
graph_builder.add_node("call_tool", tool_node)

graph_builder.add_conditional_edges(
    "reason",
    should_continue,
    {"call_tool": "call_tool", "__end__": END},
)
graph_builder.add_edge("call_tool", "reason")
graph_builder.set_entry_point("reason")
agent_graph = graph_builder.compile()
logger.info("LangGraph Agent图构建完成")
