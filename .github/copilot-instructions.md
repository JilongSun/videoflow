# VideoFlow 项目指南

## 架构概览

VideoFlow 是一个 AI 驱动的视频自动化工作流系统，以 **MCP Server** 形式对外提供视频搜索/编辑能力，供任意 Agent 调用。

```
外部 Agent ──→ MCP Server (18070) ──→ core/tools/* ──→ 业务逻辑
                                          │
                        ┌─────────────────┼─────────────────┐
                        ↓                 ↓                 ↓
                  抖音爬虫/下载      AI 视频编辑        视频分析/处理
                  (TikHub SDK)   (Runway Gen4Aleph)   (Qwen3-VL + FFmpeg)

Demo (飞书+FastAPI) ──→ MCP Client ──→ MCP Server
```

### 运行流程说明

VideoFlow 仅作为 MCP 服务端，**不直接与用户交互**，所有人机交互均由外部 Agent 实现。推荐的标准流程如下：

1. **参数收集**  
      用户向 Agent 发起视频编辑请求。Agent 检查所需参数（如图片、关键词、本地视频等），如有缺失，主动向用户提问，直到参数齐全。

2. **准备本地视频素材**  
      如果用户需要从抖音找素材，Agent 先调用 `tool_search_video` 搜索候选，再由用户确认后调用 `tool_download_video` 下载到本地；如果用户已提供本地视频，则跳过此步骤。

3. **启动工作流**  
      Agent 调用 MCP 的 `tool_run_video_workflow`，传入图片、关键词和本地视频路径，启动完整视频编辑流程。

4. **首片预览确认（视频 > 5 秒时）**  
      工作流会先处理第一个 5 秒分片并通过 `interrupt()` 暂停，返回包含 `__interrupt__` 的结果。Agent 需将预览展示给用户确认，然后调用 `tool_resume_video_workflow` 继续或中止。

5. **返回结果**  
      MCP 返回最终结果给 Agent，由 Agent 再反馈给用户。

6. **thread_id/session_id 管理**  
      `session_id` 用于标识一次工作流执行，也用于 `interrupt/resume` 的状态关联。若 Agent 需要链路追踪，可自行传入；否则 MCP 会自动生成。

> MCP 只负责业务流程和中断点的状态管理，所有用户交互、参数补全、决策均由 Agent 层实现。

### 核心模块

| 模块 | 职责 |
|------|------|
| `videoflow/mcp_server/server.py` | MCP Server 启动入口（Streamable HTTP, port 18070） |
| `videoflow/mcp_server/tools.py` | MCP Tool 注册（薄壳，调用 core/tools） |
| `videoflow/core/tools/` | 全部业务逻辑：search、download、analyze、edit |
| `videoflow/core/settings.py` | 配置管理，`MySettings` → `PlatformConfig` → `ModelSettings` 层级 |
| `videoflow/core/chatmodel.py` | 自定义 LangChain `BaseChatModel` 实现，封装 Runway、DashScope 等 AI 模型 |
| `videoflow/core/graph.py` | LangGraph 4 节点状态机：download_image → split_video → preview_first_slice（interrupt）→ object_replace |
| `videoflow/mcps/client.py` | MCP 客户端基类（供 demo 或其他模块使用） |
| `videoflow/utils/file_processor/` | Provider 模式的文件处理器（图片/视频/文档），输出到 `outputs/` |
| `videoflow/utils/crawlers/` | TikHub API 封装，抖音视频搜索与下载 |
| `videoflow/demo/` | 测试演示模块（飞书 WebSocket + LangChain Agent + FastAPI） |

## 构建与运行

```bash
# 安装依赖（推荐 uv）
uv venv && uv sync

# 配置环境变量
cp .env.example .env
# 必填：DASHSCOPE_API_KEY, RUNWAY_API_KEY, AIT8_API_KEY, TIKHUB_API_KEY
# 必填：N8N_BINARY_PATH

# 启动 MCP Server（主入口）
python main.py
# MCP: http://127.0.0.1:18070/mcp

# 启动 Demo（飞书+Agent+FastAPI，需先启动 MCP Server）
python demo_main.py
# API: http://127.0.0.1:8000  |  文档: http://127.0.0.1:8000/docs
```

## 测试

`test.py` 包含各子系统的异步集成测试函数，按需取消注释后运行：

```bash
python test.py
```

## 代码风格与惯例

- **异步优先**：所有 I/O 使用 async/await（aiofiles、httpx）；阻塞操作（ffmpeg、TikHub SDK）通过 `asyncio.to_thread()` 桥接
- **并行处理**：视频分片编辑使用 `asyncio.gather()` 并发
- **日志**：统一使用 loguru 的 `log`（从 `videoflow.utils` 导入），不要用 `print` 或 `logging`
- **类型标注**：大量使用 `Annotated[T, "description"]` 和 `Union` 类型；Pydantic v2 模型
- **配置**：所有密钥通过 `.env` + `pydantic-settings` 管理，按 `{PLATFORM_NAME}_API_KEY` 命名
- **文件输出**：统一写入 `outputs/images`、`outputs/videos`、`outputs/docs`，通过 `file_processor_provider` 路由

## 注意事项

- Runway Gen4Aleph 限制视频 ≤5 秒，较长视频会自动分片处理后拼接
- LangGraph 使用 `MemorySaver`（内存检查点），重启后状态丢失
- 视频编辑工作流只接受本地视频输入；抖音搜索与下载需先通过独立 MCP tools 完成
- MCP Server 端口 18070，Demo FastAPI 端口 8000
- Demo 模块的飞书轮询回复间隔 10 秒，无退避策略
- 小红书发布功能已剥离，作为独立 MCP 服务（端口 18060）供 Agent 直接调用
