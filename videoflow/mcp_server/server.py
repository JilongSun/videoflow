from videoflow.mcp_server.tools import mcp
from videoflow.utils import log


def create_mcp_server():
    """创建并返回 MCP Server 实例"""
    log.info("VideoFlow MCP Server 初始化完成")
    return mcp


def run_server():
    """启动 MCP Server（Streamable HTTP transport）"""
    server = create_mcp_server()
    log.info("启动 VideoFlow MCP Server: http://127.0.0.1:18070/mcp")
    server.run(transport="streamable-http", host="127.0.0.1", port=18070)
