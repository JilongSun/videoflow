# VideoFlow 项目指南

## 架构概览

VideoFlow 是一个 AI 驱动的视频自动化工作流系统。核心流程：用户（通过飞书或 API）发起任务 → LangChain Agent 调度 → LangGraph 工作流执行视频搜索/编辑/发布。

```
飞书 WebSocket ─→ FastAPI ─→ LangChain Agent ─→ LangGraph Workflow
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ↓                     ↓                     ↓
                      抖音爬虫/下载          AI 视频编辑              MCP 小红书发布
                      (TikHub SDK)      (Runway Gen4Aleph)      (Streamable HTTP)
```

### 核心模块

| 模块 | 职责 |
|------|------|
| `videoflow/core/settings.py` | 配置管理，`MySettings` → `PlatformConfig` → `ModelSettings` 层级，动态从 `.env` 读取 `{PLATFORM}_API_KEY` |
| `videoflow/core/chatmodel.py` | 自定义 LangChain `BaseChatModel` 实现，封装 Runway、DashScope 等 AI 模型 |
| `videoflow/core/agents.py` | LangChain `create_agent` + `@after_model` 中间件，主入口 `supervised_agent` |
| `videoflow/core/graph.py` | LangGraph 6 节点状态机：download_image → search_video → select_video → split_video → object_replace → update_redbook |
| `videoflow/feishu/` | 飞书 WebSocket 长连接 + REST API（消息收发、图片下载、轮询回复） |
| `videoflow/mcps/client.py` | MCP 客户端，连接小红书 MCP 服务（`http://127.0.0.1:18060/mcp`） |
| `videoflow/utils/file_processor/` | Provider 模式的文件处理器（图片/视频/文档），输出到 `outputs/` |
| `videoflow/utils/crawlers/` | TikHub API 封装，抖音视频搜索与下载 |
| `app/` | FastAPI 应用，路由分为 `chat_router`（Agent 入口）和 `util_router`（文件/搜索工具） |

## 构建与运行

```bash
# 安装依赖（推荐 uv）
uv venv && uv sync

# 配置环境变量
cp .env.example .env
# 必填：DASHSCOPE_API_KEY, RUNWAY_API_KEY, AIT8_API_KEY, TIKHUB_API_KEY
# 必填：N8N_BINARY_PATH, CONTAINER_ID（飞书）

# 启动服务
python main.py
# API: http://127.0.0.1:8000  |  文档: http://127.0.0.1:8000/docs

# 可选：启动小红书 MCP 服务
# .miscellaneous/xiaohongshu-mcp/xiaohongshu-mcp-windows-amd64.exe
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
- 飞书轮询回复间隔 10 秒，无退避策略
- 工作流中断后通过 `Command(resume=...)` 恢复，详见 `graph.py` 的 `select_video` 节点
