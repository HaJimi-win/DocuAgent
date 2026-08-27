# DocuAgent

> 基于 FastAPI + LangGraph 的本地文档智能分析 Agent，支持多格式文档解析、向量检索、Agent 工具调用、SSE 流式输出。

基于 FastAPI + LangGraph 构建的前后端分离文档智能体系统。支持上传多格式文档（TXT/CSV/PDF/Word/Excel），自动解析存入向量知识库，Agent 可自主调用检索、数据统计、报告生成等工具完成复杂文档分析任务。支持 SSE 流式输出，API 限流，完整单元测试，模块化架构。

## 版本信息

- **当前版本**：v1.5（报告确认中间层 + 自动命名 + 重新生成）
- **上一版本**：v1.4.1（嵌入 API 兼容性热修复）
- **初始版本**：v1.0
- **最后更新**：2026-08-27

## 功能特性

### 核心功能
- **多格式文档解析**：支持 TXT、CSV、PDF、Word(.docx)、Excel(.xlsx/.xls) 共6种格式
- **向量检索**：Agent 自主调用检索工具，从 Chroma 向量知识库中获取相关文档片段
- **CSV 统计**：对上传的 csv 文件执行基础统计分析（形状、描述统计）
- **报告导出**：Agent 自动将分析结果整理为 Markdown 报告并保存到本地
- **工具调用闭环**：基于 LangGraph 状态机实现「思考 → 调用工具 → 观测结果 → 再思考」的 Agent 循环
- **模型可插拔**：支持云端 LLM API 与 Ollama 本地开源模型一键切换

### v1.5 功能
- **报告确认中间层**：Agent 生成报告后不直接保存，而是展示预览并暂停，等待用户确认
- **确认保存**：用户确认报告内容和文件名后，一键保存到 workspace
- **重新生成**：不满意可重新生成报告（支持填写反馈意见），新报告覆盖前一份暂存，避免占空间
- **自动命名**：按 `[报告类型]_[主体/范围]_[时间]_[版本].md` 格式自动生成文件名，用户可修改
- **版本追踪**：每次重新生成版本号递增（v1→v2→v3...），最终保存时记录版本

### v1.1 功能
- **增量更新去重**：文件 MD5 哈希校验，重复上传自动跳过，避免向量库冗余
- **对话历史持久化**：SQLite 数据库存储对话记录，支持历史查询
- **大文档流式读取**：TXT 按行流式读取、PDF 逐页提取、Word 逐段提取，避免大文件内存溢出
- **日志系统**：标准 logging 模块，控制台 + 文件双输出，关键节点全打点
- **全链路异常处理**：上传/解析/向量库/Agent/工具各环节异常捕获，友好错误提示
- **Prompt 工程优化**：角色设定、输出格式规范、Few-shot 示例、约束条件、安全护栏
- **已上传文件管理**：前端展示已入库文件列表（文件名/片段数/大小/上传时间）

### v1.2 新增功能
- **SSE 流式输出**：Agent 每执行一步（思考/工具调用）实时推送到前端，避免请求超时，用户可实时看到 Agent 干活过程
- **API 限流**：基于 slowapi 按 IP 限流，上传接口 20次/分钟，Agent 执行接口 10次/分钟，防止频繁调用烧 token
- **单元测试**：32个 pytest 测试用例，覆盖 MD5去重、文件格式校验、SQLite历史、上传记录、SSE格式、冒烟测试
- **双接口模式**：保留同步 `/run-agent`（等待全部完成），新增 `/run-agent/stream`（SSE流式），前端默认使用流式

## 技术架构（v1.3 模块化分层）

```
前端（浏览器 HTML/JS）
    │  HTTP / SSE 请求
    ▼
┌─────────────────────────────────────────┐
│  API 层 (api/routes.py)                  │
│  /upload  /run-agent  /run-agent/stream │
│  /history  /files  + slowapi限流         │
├─────────────────────────────────────────┤
│  核心层 (core/)                          │
│  agents.py  LangGraph状态机 + Prompt     │
│  tools.py   检索/统计/保存工具           │
│  parsers.py 6种格式解析 + MD5去重        │
│  report_manager.py 报告暂存/命名/重生成  │
├─────────────────────────────────────────┤
│  存储层 (storage/)                       │
│  vector_store.py  Chroma向量库           │
│  history_db.py    SQLite对话历史          │
├─────────────────────────────────────────┤
│  配置层 (config.py)                      │
│  日志 / LLM / Embedding / TextSplitter   │
└─────────────────────────────────────────┘

数据持久化
    ├── Chroma 向量库    chroma_db/
    ├── SQLite 数据库    workspace/chat_history.db
    ├── JSON 上传记录    workspace/uploaded_files.json
    └── 日志文件         logs/app.log
```

## 项目结构（v1.3 模块化架构）

```
project_doc_agent/
├── config.py           # 全局配置：日志、目录、LLM、嵌入模型、文本切片器、常量
├── main.py             # 入口：创建FastAPI app、注册路由、启动服务（精简版）
├── README.md           # 项目文档
├── static/
│   └── index.html      # 前端交互页面（SSE流式实时输出）
├── tests/
│   └── test_main.py    # 单元测试（37个用例）
├── core/               # 核心业务逻辑
│   ├── __init__.py
│   ├── agents.py       # Agent状态机 + 优化版System Prompt
│   ├── tools.py        # 工具定义（检索/CSV统计/报告保存）
│   ├── parsers.py      # 多格式文档解析器 + MD5增量去重
│   └── report_manager.py # 报告确认中间层（暂存/自动命名/重新生成/保存）
├── api/                # API层
│   ├── __init__.py
│   └── routes.py       # FastAPI路由（上传/同步执行/SSE流式/历史/文件列表）+ 限流
├── storage/            # 存储层
│   ├── __init__.py
│   ├── vector_store.py # Chroma向量库初始化与检索
│   └── history_db.py   # SQLite对话历史持久化
├── workspace/          # 原始文件 & 生成报告 & 对话历史DB & 上传记录
├── chroma_db/          # Chroma 向量库持久化目录
└── logs/               # 运行日志目录（app.log）
```

### 模块职责说明

| 模块 | 职责 | 关键内容 |
|---|---|---|
| `config.py` | 全局配置与单例 | 日志系统、目录常量、LLM、Embedding、TextSplitter |
| `core/agents.py` | Agent核心 | LangGraph状态机、System Prompt、思考节点、条件判断 |
| `core/tools.py` | Agent工具 | retrieve_doc、csv_stat、save_report（带异常处理） |
| `core/parsers.py` | 文档解析 | 6种格式解析器、MD5去重、上传记录管理 |
| `core/report_manager.py` | 报告确认中间层 | 报告预览暂存、自动命名、重新生成、确认保存、标记解析 |
| `api/routes.py` | API接口 | 5个接口、SSE流式生成器、slowapi限流 |
| `storage/vector_store.py` | 向量存储 | Chroma初始化、retriever、批量写入 |
| `storage/history_db.py` | 历史存储 | SQLite初始化、保存消息、查询历史 |
| `main.py` | 入口 | 组装app、注册路由、限流异常处理、启动uvicorn |

## 环境要求

- Python 3.10 ~ 3.12
- 大模型 API Key（OpenAI 兼容接口）或本地 Ollama 服务

## 安装与运行

### 1. 安装依赖

```bash
pip install fastapi uvicorn langgraph langchain langchain-community langchain-openai langchain-chroma langchain-text-splitters chromadb python-dotenv pydantic pandas pypdf python-docx slowapi pytest python-multipart
```

> v1.1 新增：`pypdf`（PDF解析）、`python-docx`（Word解析）
> v1.2 新增：`slowapi`（API限流）、`pytest`（单元测试）、`python-multipart`（FastAPI文件上传必需）

### 2. 配置大模型

编辑 `.env` 文件：

**模式A：云端 API（推荐调试用）**
```env
LLM_API_KEY=sk-你的key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**模式B：Ollama 本地 Qwen 模型（私有化）**
```env
LLM_API_KEY=dummy
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen3:14b
```
> 使用 Ollama 前需先安装 Ollama 并执行 `ollama pull qwen3:14b`

### 3. 启动服务

```bash
python main.py
```

启动后控制台会输出日志，同时日志写入 `logs/app.log`。

### 4. 访问前端

浏览器打开 `http://127.0.0.1:8001`

### 5. 运行单元测试

```bash
pytest tests/ -v
```

## 使用流程

1. **上传文档**：选择本地文件（支持 TXT/CSV/PDF/Word/Excel），点击「上传并解析」
   - 系统自动计算 MD5，重复文件会提示并跳过入库
   - 大文档流式解析，前端显示上传状态
2. **查看已上传文件**：文件列表区展示所有已入库文件（文件名/片段数/大小/时间）
3. **输入分析任务**：在文本框中描述你想要 Agent 完成的分析任务
   - 示例：`总结文档主要内容，并对csv数据做统计，保存为 analysis.md`
4. **执行任务**：点击「执行Agent任务」，**SSE流式实时展示** Agent 每一步的思考和工具调用
5. **报告确认**（如任务涉及生成报告）：
   - Agent 生成报告预览后自动暂停，页面显示「报告预览确认」区
   - 检查报告内容，确认或修改文件名（自动按 `[报告类型]_[主体]_[时间]_[版本].md` 命名）
   - 满意则点击「✅ 确认保存」→ 报告写入 workspace
   - 不满意则点击「🔄 重新生成」→ 可填写反馈意见，AI 重新生成一份报告（覆盖前一份预览，版本号递增）
6. **查看结果**：最终结果实时展示在页面，生成的报告保存在 `workspace/` 目录
7. **查看历史**：点击「查看对话历史」，右侧面板展示持久化的对话记录

## API 接口

| 方法 | 路径 | 限流 | 说明 |
|---|---|---|---|
| GET | `/` | - | 前端页面 |
| POST | `/upload` | 20次/分钟 | 上传文件（支持6种格式，MD5去重，自动解析入库） |
| POST | `/run-agent` | 10次/分钟 | 同步执行 Agent 任务（等待全部完成后返回） |
| POST | `/run-agent/stream` | 10次/分钟 | SSE 流式执行 Agent 任务（实时推送每一步） |
| GET | `/history` | - | 查询对话历史（参数: `session_id`, `limit`） |
| GET | `/files` | - | 列出已上传文件列表 |
| POST | `/confirm-report` | - | 确认保存报告预览（参数: `session_id`, `filename`） |
| POST | `/regenerate-report` | - | 重新生成报告预览（参数: `session_id`, `user_query`, `feedback`） |

### SSE 流式接口事件说明

`/run-agent/stream` 返回 `text/event-stream`，包含以下事件类型：

| 事件 | data 字段 | 说明 |
|---|---|---|
| `step` | `{step, type, content, tool_calls}` | Agent 每执行一步推送一次，type 为 `tool_call` 或 `text` |
| `await_confirm` | `{content, filename, version, steps}` | 报告预览已生成，等待用户确认（收到此事件后流程暂停，不发 done） |
| `done` | `{answer, steps}` | 任务完成，返回最终答案和总步数 |
| `error` | `{error}` | 执行出错，返回错误信息 |

## Agent 可用工具

| 工具名 | 功能 |
|---|---|
| `retrieve_doc` | 从向量知识库检索相关文档片段 |
| `csv_stat` | 对 workspace 下的 csv 文件做基础统计 |
| `save_report` | 报告保存工具（v1.5 起由系统自动处理，Agent 输出报告预览标记即可） |

> **v1.5 变更**：Agent 不再直接调用 `save_report` 保存报告。当用户要求生成报告时，Agent 用 `===REPORT_PREVIEW===` 标记包裹报告内容输出，系统自动暂存并弹出确认区，由用户确认后保存。

## Agent Prompt 体系

System Prompt 包含以下模块：
- **角色设定**：资深文档分析专家，专业严谨简洁
- **工具说明**：3个工具的功能和使用场景
- **工作流程**：判断→调用→整理→保存的标准流程
- **输出格式规范**：普通问答 / 分析报告的 Markdown 结构
- **Few-shot 示例**：2个完整示例（文档总结、CSV统计+保存报告）
- **约束条件**：基于文档、不编造、参数准确、最多8轮
- **安全护栏**：拒绝敏感/违法/越权请求

## 单元测试覆盖

共 37 个测试用例，7 个测试类：

| 测试类 | 用例数 | 覆盖内容 |
|---|---|---|
| TestMD5Hashing | 4 | MD5一致性、不同内容、空文件、大文件流式计算 |
| TestFileFormatValidation | 15 | 6种支持格式参数化、8种不支持格式、大小写不敏感 |
| TestSQLiteHistory | 3 | 保存查询、多会话隔离、倒序排序 |
| TestUploadRecord | 3 | 保存加载、重复检测、空文件处理 |
| TestSSEFormat | 3 | step/done/error 三种事件格式校验 |
| TestSmoke | 9 | 模块文件存在性、全模块语法、各模块关键字校验、入口校验 |

运行方式：`pytest tests/ -v`

## 注意事项

- 首次上传文档会自动构建向量索引，大文档（PDF/Word）可能需要几秒到几十秒
- 生成的报告文件位于 `workspace/` 目录
- 向量库数据持久化在 `chroma_db/`，重启服务后历史文档仍可检索
- 对话历史持久化在 `workspace/chat_history.db`（SQLite）
- 运行日志保存在 `logs/app.log`，排查问题时可查看
- API 限流按 IP 计算，超出限制返回 429 状态码
- 前端默认使用 SSE 流式接口，Agent 每一步实时展示，不会超时
- 若使用 Ollama 小参数模型（如 8B），工具调用成功率可能下降，建议使用 14B 及以上模型
- PDF 解析依赖 `pypdf`，Word 解析依赖 `python-docx`，未安装时对应格式会提示安装
- 使用非 OpenAI 兼容 embeddings 提供商（SiliconFlow、Ollama、vLLM、OpenRouter 等）时，`OpenAIEmbeddings` 必须设置 `check_embedding_ctx_length=False`，否则会发送 token ID 数组导致 API 返回 400 错误（本项目已在 `config.py` 中默认配置）

## 版本更新记录

### v1.5（2026-08-27）报告确认中间层 + 自动命名 + 重新生成

**核心功能**
- 新增报告确认中间层：Agent 生成报告后不直接保存，而是展示预览并暂停，等待用户确认
- 确认保存：用户确认报告内容和文件名后一键保存到 workspace
- 重新生成：不满意可重新生成报告（支持填写反馈意见），新报告覆盖前一份暂存，避免占空间
- 自动命名：按 `[报告类型]_[主体/范围]_[时间]_[版本].md` 格式自动生成文件名，用户可修改
- 版本追踪：每次重新生成版本号递增（v1→v2→v3...）

**新增模块**
- `core/report_manager.py`：报告暂存（内存字典，按 session_id）、自动命名（类型推断+主体提取）、重新生成（LLM 基于上下文重写）、确认保存、报告标记解析

**协议变更**
- Agent System Prompt 新增「报告预览输出规范」：用 `===REPORT_PREVIEW===` / `===REPORT_END===` 标记包裹报告内容
- Agent 不再直接调用 `save_report` 工具，改为输出报告预览标记由系统处理
- SSE 新增 `await_confirm` 事件：携带报告内容、建议文件名、版本号，收到后流程暂停等待用户操作
- 新增 API：`POST /confirm-report`（确认保存）、`POST /regenerate-report`（重新生成）

**前端变更**
- 新增「报告预览确认」卡片：Markdown 渲染预览、文件名输入框、确认保存/重新生成按钮
- 重新生成支持填写反馈意见（如"更简洁""增加数据部分"）
- 简单 Markdown 渲染器（标题/粗体/列表/代码/引用/表格）

### v1.4.1（2026-08-27）嵌入 API 兼容性热修复

**根因修复**
- 彻底修复 SiliconFlow embeddings API 返回 `20015 The parameter is invalid` 的问题
- 根因：`langchain_openai >= 1.0` 的 `OpenAIEmbeddings` 默认 `check_embedding_ctx_length=True`，会先用 tiktoken 将文本转为 token ID 数组（如 `[[82805, 17161, 22656]]`）再发送；而 SiliconFlow / Ollama / vLLM 等非 OpenAI 提供商的 embeddings 接口只接受文本字符串作为 `input`，不接受 token IDs
- 修复：在 `config.py` 中显式设置 `check_embedding_ctx_length=False`，直接发送原始文本字符串
- v1.4 中对 20015 的修复仅补充了 `model` 参数，未触及此根因，问题仍然存在

**配置变更**
- `config.py` 中 `OpenAIEmbeddings` 初始化新增 `check_embedding_ctx_length=False`
- 无需修改 `.env`，代码层面自动生效

**兼容性改进**
- 对所有非 OpenAI 兼容 embeddings 提供商（SiliconFlow、Ollama、vLLM、OpenRouter 等）均生效
- 保留与官方 OpenAI API 的兼容性（设为 False 后 OpenAI 同样正常工作）

### v1.4（2026-08-27）硅基流动适配 + 嵌入模型优化

**核心修复**
- 修复 `OpenAIEmbeddings` 初始化时缺失 `model` 参数的问题，现在正确从环境变量读取模型名
- 新增 `EMBEDDING_MODEL` 环境变量，支持对话模型与嵌入模型独立配置
- 调整文本切片大小：`chunk_size` 从 600 降至 500，`chunk_overlap` 从 100 降至 80，适配 `BAAI/bge-large-zh-v1.5` 的 512 token 上限
- 修复向量库写入时报错 `20012 Model does not exist`（补充 `model` 参数）；`20015 The parameter is invalid` 在本版本未完全修复，详见 v1.4.1

**配置变更**
- `.env` 文件新增 `EMBEDDING_MODEL` 变量，用于指定嵌入模型
- 若未设置 `EMBEDDING_MODEL`，则自动回退到 `LLM_MODEL` 的值（向后兼容）
- 推荐配置示例：
  ```env
  LLM_API_KEY=sk-你的 key
  LLM_BASE_URL=https://api.siliconflow.cn/v1
  LLM_MODEL=deepseek-ai/DeepSeek-V3          # 对话模型（用于问答）
  EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5     # 嵌入模型（用于向量化）
  ```

**兼容性改进**
- 支持硅基流动（SiliconFlow）平台的 Embedding API
- 支持 `BAAI/bge-large-zh-v1.5`、`BAAI/bge-m3` 等开源嵌入模型
- 保留与 OpenAI、Ollama 的兼容性

### v1.3（2026-08-27）模块化重构

**架构重构**
- 将单文件 main.py（739行）拆分为模块化架构，按职责分层
- 新增 `config.py`：全局配置与单例（日志、LLM、Embedding、TextSplitter、常量）
- 新增 `core/` 核心层：
  - `agents.py`：LangGraph 状态机 + 优化版 System Prompt
  - `tools.py`：三个 Agent 工具（检索/统计/保存），带异常处理
  - `parsers.py`：6种格式文档解析器 + MD5 增量去重 + 上传记录管理
- 新增 `api/` API层：
  - `routes.py`：5个接口 + SSE 流式生成器 + slowapi 限流
- 新增 `storage/` 存储层：
  - `vector_store.py`：Chroma 向量库初始化与检索
  - `history_db.py`：SQLite 对话历史持久化
- `main.py` 精简为入口文件（约50行），只做组装和启动

**工程质量**
- 模块间依赖清晰，无循环导入
- 每个模块独立职责，便于维护和测试
- 单元测试从 32 个增加到 37 个，新增模块化架构冒烟测试（9个用例）
- 所有 37 个测试通过（0.31秒）

### v1.2（2026-08-27）

**体验优化（P2）**
- 新增 SSE 流式输出接口 `/run-agent/stream`，Agent 每执行一步实时推送到前端
- 前端改用 fetch + ReadableStream 解析 SSE 事件流，实时展示思考/工具调用过程
- 保留同步接口 `/run-agent` 兼容旧调用方式
- SSE 事件包含 step（每一步）、done（完成）、error（错误）三种类型

**工程化（P2）**
- 新增 API 限流（slowapi）：上传接口 20次/分钟，Agent执行接口 10次/分钟
- 限流按 IP 计算，超出返回 429，防止频繁调用烧 token
- 新增 32 个 pytest 单元测试用例，覆盖6大模块
- 测试不依赖大模型和向量库，纯函数测试，可离线运行

### v1.1（2026-08-27）

**代码质量优化（P0）**
- 新增标准 logging 日志系统，控制台 + `logs/app.log` 文件双输出
- 全链路异常处理：上传/解析/向量库写入/Agent执行/工具调用各环节加 try-except
- Agent System Prompt 全面优化：角色设定、输出格式规范、2个Few-shot示例、约束条件、安全护栏

**功能增强（P1）**
- 新增 PDF 解析支持（pypdf 逐页提取文本）
- 新增 Word(.docx) 解析支持（python-docx 段落+表格提取）
- 新增 Excel(.xlsx/.xls) 解析支持（pandas 多Sheet转文本）
- 新增文件 MD5 增量去重，重复上传自动跳过入库
- 新增对话历史持久化（SQLite），`/history` 接口查询
- 新增大文档流式读取（TXT按行/PDF逐页/Word逐段），避免内存溢出
- 新增 `/files` 接口，前端展示已上传文件列表

**前端升级**
- 双列布局：执行日志 + 对话历史并排展示
- 已上传文件列表展示（文件名/片段数/大小/上传时间）
- 上传状态细化（成功/去重跳过/失败）
- 对话历史面板，支持点击加载

### v1.0（初始版本）

- 基于 FastAPI + LangGraph 的前后端分离架构
- 支持 TXT/CSV 文档上传解析
- Chroma 向量知识库检索
- Agent 工具调用闭环（检索/统计/保存报告）
- 云端 API / Ollama 本地模型可插拔切换
