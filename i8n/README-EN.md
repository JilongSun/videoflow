# VideoFlow

An intelligent workflow system for automated AI-generated videos. It integrates various AI models and video processing capabilities, supporting a complete workflow from video search, editing, to publishing.

## 🚀 Features

- **AI-Driven Video Editing**: Leverage advanced artificial intelligence models for intelligent editing of video content.
- **Multi-Model Integration**: Support for multiple AI models (RunwayML, Alibaba Tongyi Wanxiang, etc.).
- **Intelligent Workflow**: Visual workflow system built on LangGraph.
- **Multi-Platform Integration**: Support integrating with enterprise collaboration platforms like Feishu/Lark.
- **Automated Processing**: One-stop automated processing from video search, editing, to output.

## 🛠 Tech Stack

- **Backend**: Python 3.12+, FastAPI, LangGraph
- **AI Models**: OpenAI API, DashScope API, RunwayML API, Vision-Language Models (VL Models)
- **MCP Services**: Model Context Protocol 1.12.4, Xiaohongshu (RED) MCP integration
- **Video Processing**: FFmpeg, OpenCV

## 📋 Core Modules

### 1. Video Editing Workflow

- Automated video editing process
- Support for object replacement in videos
- Integration of multiple AI models for video processing

### 2. AI Model Integration

- RunwayML integration
- Alibaba Tongyi Wanxiang integration (temporarily deprecated)
- DashScope model support
- ait8 runway (API issues, currently not supported)
- Custom model base classes

### 3. VL Model Integration

- Vision-Language model support, providing video content understanding and analysis capabilities

### 4. MCP Service Integration

- Model Context Protocol service, supporting Xiaohongshu (RED) MCP integration

### 5. Crawler & Downloader

- Douyin (TikTok) video search and download
- Support for multiple video sources

### 6. File Processor

- Video processing functions
- Image processing functions
- File upload and storage

### 7. Feishu (Lark) Integration

- Feishu bot integration
- Message sending and receiving functions
- Real-time collaboration support

## 🏗️ Project Structure

```
videoflow/
├── app/                    # FastAPI application entry
│   ├── main.py            # Main application
│   ├── models/            # Data models
│   └── routers/           # API routes
├── videoflow/             # Core functionality modules
│   ├── core/              # Core business logic
│   │   ├── graph.py       # Workflow definitions
│   │   ├── chatmodel.py   # AI model integration (including VL models)
│   │   └── agents.py      # Intelligent agents
│   ├── feishu/            # Feishu (Lark) integration
│   ├── mcps/              # MCP service integration
│   │   ├── __init__.py
│   │   └── client.py      # MCP client implementation
│   ├── utils/             # Utility functions
│   │   ├── crawlers/      # Web crawlers
│   │   ├── downloader/    # Downloaders
│   │   └── file_processor/ # File processors
│   └── core/settings.py   # Configuration settings
├── main.py               # Application startup entry
├── .env.example          # Environment variables template
├── pyproject.toml       # Project configuration
└── .miscellaneous/      # Miscellaneous files
```

## 🔧 Environment Setup

### Option 1: Using uv (Recommended)

1. **Clone the project**

   ```bash
   git clone <repository-url>
   cd videoflow
   ```

2. **Create a virtual environment and install dependencies using uv**

   ```bash
   uv venv
   uv sync
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit the .env file to configure the necessary API keys and parameters
   ```

4. **Configure Xiaohongshu MCP**

   The Xiaohongshu MCP comes from the [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) repository.

   Related files are located in the `.miscellaneous/xiaohongshu-mcp/` directory:
   - `xiaohongshu-mcp-windows-amd64.exe` - MCP service executable file
   - `cookies.json` - Xiaohongshu login credentials file

5. **Run the application**

   ```bash
   uv run python main.py
   ```

### Option 2: Use pre-compiled executable directly for Windows users

For Windows users, we provide pre-compiled executable files:

1. **Download the compiled version**
   - Download from the Release page

2. **Configure environment variables**
   - Edit the `.env` file to configure necessary API keys and parameters

3. **Configure Xiaohongshu MCP**

   The Xiaohongshu MCP comes from the [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) repository.

4. **Run the application**

   ```cmd
   main.exe
   ```

## 📝 Usage Instructions

### Start the Service

```bash
python main.py
```

### API Access

Once the service is started, the API service will be available at `http://127.0.0.1:8000`

### Feishu (Lark) Integration

Supports initiating video editing tasks and receiving results via the Feishu bot.

### Detailed Configuration

1. **API Documentation**: After starting the application, visit `http://localhost:8000/docs` to view the Swagger documentation.
2. **Workflow Configuration**: Define and modify workflows in `videoflow/core/graph.py`.
3. **Model Configuration**: Configure AI model parameters in `videoflow/core/chatmodel.py`.
4. **VL Model Usage**: The system supports vision-language models, which can be used for video content understanding and analysis.
5. **MCP Service**: Supports integration with social media platforms like Xiaohongshu through the Model Context Protocol.

### MCP Integration Details

#### Xiaohongshu MCP Integration

The Xiaohongshu MCP service comes from the [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp) repository, providing the following features:

- **Content Creation**: Supports automatic generation and publishing of Xiaohongshu notes.
- **User Interaction**: Interactions with the Xiaohongshu platform via the MCP protocol.
- **Data Synchronization**: Synchronizes Xiaohongshu platform data to the local system.

#### MCP Client Implementation

The MCP client implementation is located in `videoflow/mcps/client.py`, with main functions including:

- **Connection Management**: Manages connections with MCP services.
- **Protocol Handling**: Handles MCP protocol communication.
- **Error Handling**: Provides a comprehensive error handling mechanism.

## 🤝 Contribution

Issues and Pull Requests are welcome to help improve the project.

## 📄 License

[MIT License](LICENSE)

## 🔗 Related Links

- **Xiaohongshu MCP Repository**: [`https://github.com/xpzouying/xiaohongshu-mcp`](https://github.com/xpzouying/xiaohongshu-mcp)
- **MCP Official Documentation**: [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- **Project Homepage**: [VideoFlow GitHub Repository]