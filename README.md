# VideoFlow

基于AI自动化生成视频的智能工作流系统，集成了多种AI模型和视频处理能力，支持从视频搜索、编辑到发布的完整流程。

## 🚀 功能特性

- **AI驱动的视频编辑**：利用先进的人工智能模型实现视频内容的智能编辑
- **多模型集成**：支持多种AI模型（RunwayML、阿里通义万相等）
- **智能工作流**：基于LangGraph构建的可视化工作流系统
- **多平台集成**：支持飞书等企业协作平台集成
- **自动化处理**：从视频搜索、编辑到输出的一站式自动化处理

## 🛠 技术栈

- **后端**: Python 3.12+, FastAPI, LangGraph
- **AI 模型**: OpenAI API, DashScope API, RunwayML API, 视觉语言模型(VL模型)
- **MCP服务**: Model Context Protocol 1.12.4, 小红书MCP集成
- **视频处理**: FFmpeg, OpenCV

## 📋 核心模块

### 1. 视频编辑工作流

- 自动化视频编辑流程
- 支持视频中对象替换
- 集成多种AI模型进行视频处理

### 2. AI模型集成

- RunwayML集成
- 阿里通义万相集成（暂时废弃）
- DashScope模型支持
- ait8 runway(接口有问题，暂不支持)
- 自定义模型基类

### 3. VL模型集成

- 视觉语言模型支持，提供视频内容理解和分析能力

### 4. MCP服务集成

- Model Context Protocol服务，支持小红书MCP集成

### 5. 爬虫与下载器

- 抖音视频搜索与下载
- 支持多种视频源

### 6. 文件处理器

- 视频处理功能
- 图像处理功能
- 文件上传与存储

### 7. 飞书集成

- 飞书机器人集成
- 消息收发功能
- 实时协作支持

## 🏗️ 项目结构

```
videoflow/
├── app/                    # FastAPI应用入口
│   ├── main.py            # 主应用
│   ├── models/            # 数据模型
│   └── routers/           # API路由
├── videoflow/             # 核心功能模块
│   ├── core/              # 核心业务逻辑
│   │   ├── graph.py       # 工作流定义
│   │   ├── chatmodel.py   # AI模型集成（包含VL模型）
│   │   └── agents.py      # 智能代理
│   ├── feishu/            # 飞书集成
│   ├── mcps/              # MCP服务集成
│   │   ├── __init__.py
│   │   └── client.py      # MCP客户端实现
│   ├── utils/             # 工具函数
│   │   ├── crawlers/      # 网络爬虫
│   │   ├── downloader/    # 下载器
│   │   └── file_processor/ # 文件处理器
│   └── core/settings.py   # 配置设置
├── main.py               # 应用启动入口
├── .env.example          # 环境变量模板
├── pyproject.toml       # 项目配置
└── .miscellaneous/      # 杂项文件
```

## 🔧 环境配置

### 方案一：使用 uv（推荐）

1. **克隆项目**

   ```bash
   git clone <repository-url>
   cd videoflow
   ```

2. **使用 uv 创建虚拟环境并安装依赖**

   ```bash
   uv venv
   uv sync
   ```

3. **配置环境变量**

   ```bash
   cp .env.example .env
   # 编辑 .env 文件，配置必要的 API 密钥和参数
   ```

4. **配置小红书MCP**

   小红书MCP来自 [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) 仓库。

   相关文件位于 `.miscellaneous/xiaohongshu-mcp/` 目录：
   - `xiaohongshu-mcp-windows-amd64.exe` - MCP服务可执行文件
   - `cookies.json` - 小红书登录凭证文件

5. **运行应用**

   ```bash
   uv run python main.py
   ```

### 方案二：Windows 用户直接使用编译好的可执行文件

对于 Windows 用户，我们提供了编译好的可执行文件：

1. **下载编译好的版本**
   - 从 Release 页面下载

2. **配置环境变量**
   - 编辑 `.env` 文件，配置必要的 API 密钥和参数

3. **配置小红书MCP**

   小红书MCP来自 [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) 仓库。

4. **运行应用**

   ```cmd
   main.exe
   ```

## 📝 使用说明

### 启动服务

```bash
python main.py
```

### API访问

服务启动后将在 `http://127.0.0.1:8000` 提供API服务

### 飞书集成

支持通过飞书机器人进行视频编辑任务的发起和结果接收

### 详细配置

1. **API 文档**: 启动应用后访问 `http://localhost:8000/docs` 查看 Swagger 文档
2. **工作流配置**: 在 `videoflow/core/graph.py` 中定义和修改工作流
3. **模型配置**: 在 `videoflow/core/chatmodel.py` 中配置 AI 模型参数
4. **VL模型使用**: 系统支持视觉语言模型，可用于视频内容理解和分析
5. **MCP服务**: 支持通过Model Context Protocol与小红书等社交媒体平台集成

### MCP集成详情

#### 小红书MCP集成

小红书MCP服务来自 [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) 仓库，提供以下功能：

- **内容创作**: 支持小红书笔记内容的自动生成和发布
- **用户交互**: 通过MCP协议与小红书平台进行交互
- **数据同步**: 同步小红书平台的数据到本地系统

#### MCP客户端实现

MCP客户端实现位于 `videoflow/mcps/client.py`，主要功能包括：

- **连接管理**: 管理与MCP服务的连接
- **协议处理**: 处理MCP协议通信
- **错误处理**: 提供完善的错误处理机制

## 🤝 贡献

欢迎提交Issue和Pull Request来帮助改进项目。

## 📄 许可证

[MIT License](LICENSE)

## 🔗 相关链接

- **小红书MCP仓库**: [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp)
- **MCP官方文档**: [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- **项目主页**: [VideoFlow GitHub Repository]
