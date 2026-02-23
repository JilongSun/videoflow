from typing import Any, Dict, List, Optional, Union, TypedDict, NotRequired
from datetime import timedelta
from abc import ABC, abstractmethod
from mcp import ClientSession
from mcp import Tool as MCPTool
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    InitializeResult,
    ListPromptsResult,
)
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.shared.message import SessionMessage
from mcp.client.streamable_http import (
    GetSessionIdCallback,
    streamablehttp_client,
)
from contextlib import AbstractAsyncContextManager, AsyncExitStack
import asyncio, gc


class MCPServer(ABC):
    """Base class for Model Context Protocol servers."""

    def __init__(
        self,
    ):
        self.session: ClientSession | None = None
        self.server_initialize_result: InitializeResult | None = None

    @abstractmethod
    async def connect(self):
        """Connect to the server. For example, this might mean spawning a subprocess or
        opening a network connection. The server is expected to remain connected until
        `cleanup()` is called.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """A readable name for the server."""
        pass

    @abstractmethod
    async def cleanup(self):
        """Cleanup the server. For example, this might mean closing a subprocess or
        closing a network connection.
        """
        pass

    @abstractmethod
    async def list_tools(
        self,
    ) -> List:
        """List the tools available on the server."""
        pass

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        meta: dict[str, Any] | None = None,
    ) -> CallToolResult:
        """Invoke a tool on the server."""
        pass

    @abstractmethod
    async def list_prompts(
        self,
    ) -> ListPromptsResult:
        """List the prompts available on the server."""
        pass

    @abstractmethod
    async def get_prompt(self, name: str) -> GetPromptResult:
        """Get a specific prompt from the server.需要自己实现"""
        pass


class _MCPServerWithClientSession(MCPServer, ABC):
    """Base class for MCP servers that use a `ClientSession` to communicate with the server."""

    @property
    def cached_tools(self) -> list[MCPTool] | None:
        return self._tools_list

    def __init__(
        self,
        session: ClientSession | None = None,
        client_session_timeout_seconds: float | None = None,
    ):
        super().__init__()
        self.client_session_timeout_seconds: float | None = (
            client_session_timeout_seconds
        )
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._tools_list: list[MCPTool] | None = None

    @abstractmethod
    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
            GetSessionIdCallback | None,
        ]
    ]:
        """Create the streams for the server."""
        pass

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.cleanup()

    async def connect(self):
        """Connect to the server."""
        connection_succeeded = False
        transport = await self.exit_stack.enter_async_context(self.create_streams())

        # streamablehttp_client returns (read, write, get_session_id)
        # sse_client returns (read, write)
        # async with self.create_streams() as transport:
        read, write, *_ = transport

        session = await self.exit_stack.enter_async_context(
            ClientSession(
                read,
                write,
                (
                    timedelta(seconds=self.client_session_timeout_seconds)
                    if self.client_session_timeout_seconds
                    else None
                ),
            )
        )
        server_result = await session.initialize()
        self.server_initialize_result = server_result
        self.session = session
        connection_succeeded = True

    async def list_tools(
        self,
    ) -> list[MCPTool]:
        """List the tools available on the server."""
        if not self.session:
            raise Exception(
                "Server not initialized. Make sure you call `connect()` first."
            )
        session = self.session
        assert session is not None

        try:
            result = await session.list_tools()
            self._tools_list = result.tools
            return self._tools_list
        except Exception as e:
            raise e

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        meta: dict[str, Any] | None = None,
    ) -> CallToolResult:
        """Invoke a tool on the server."""
        if not self.session:
            raise Exception(
                "Server not initialized. Make sure you call `connect()` first."
            )
        session = self.session
        assert session is not None

        try:
            if meta is None:
                return await self.session.call_tool(tool_name, arguments)
            return await self.session.call_tool(tool_name, arguments)
        except Exception as e:
            raise e

    async def list_prompts(
        self,
    ) -> ListPromptsResult:
        """List the prompts available on the server."""
        if not self.session:
            raise Exception(
                "Server not initialized. Make sure you call `connect()` first."
            )

        return await self.session.list_prompts()

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> GetPromptResult:
        """Get a specific prompt from the server."""
        if not self.session:
            raise Exception(
                "Server not initialized. Make sure you call `connect()` first."
            )

        return await self.session.get_prompt(name, arguments)

    async def cleanup(self):
        """Cleanup the server."""
        await self.exit_stack.aclose()
        if self.session:
            del self.session
            gc.collect()


class MCPServerStreamableHttpParams(TypedDict):
    """Mirrors the params in`mcp.client.streamable_http.streamablehttp_client`."""

    url: str
    """The URL of the server."""

    headers: NotRequired[dict[str, str]]
    """The headers to send to the server."""

    timeout: NotRequired[timedelta | float]
    """The timeout for the HTTP request. Defaults to 5 seconds."""

    sse_read_timeout: NotRequired[timedelta | float]
    """The timeout for the SSE connection, in seconds. Defaults to 5 minutes."""

    terminate_on_close: NotRequired[bool]
    """Terminate on close"""

    httpx_client_factory: NotRequired[Any]
    """Custom HTTP client factory for configuring httpx.AsyncClient behavior."""


class MCPServerStreamableHttp(_MCPServerWithClientSession):
    """MCP server implementation that uses the Streamable HTTP transport. See the [spec]
    (https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)
    for details.
    """

    def __init__(
        self,
        params: MCPServerStreamableHttpParams,
        name: str | None = None,
        client_session_timeout_seconds: float | None = 9999,
    ):
        """Create a new MCP server based on the Streamable HTTP transport."""
        super().__init__(
            client_session_timeout_seconds=client_session_timeout_seconds,
        )

        self.params = params
        self._name = name or f"streamable_http: {self.params['url']}"

    def create_streams(
        self,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
            GetSessionIdCallback | None,
        ]
    ]:
        """Create the streams for the server."""
        # Only pass httpx_client_factory if it's provided
        if "httpx_client_factory" in self.params:
            return streamablehttp_client(
                url=self.params["url"],
                headers=self.params.get("headers", None),
                timeout=self.params.get("timeout", 5),
                sse_read_timeout=self.params.get("sse_read_timeout", 60 * 5),
                terminate_on_close=self.params.get("terminate_on_close", True),
                httpx_client_factory=self.params["httpx_client_factory"],
            )
        else:
            return streamablehttp_client(
                url=self.params["url"],
                headers=self.params.get("headers", None),
                timeout=self.params.get("timeout", 5),
                sse_read_timeout=self.params.get("sse_read_timeout", 60 * 5),
                terminate_on_close=self.params.get("terminate_on_close", True),
            )

    @property
    def name(self) -> str:
        """A readable name for the server."""
        return self._name


async def test_streamable_http():
    async with MCPServerStreamableHttp(
        params={"url": "http://127.0.0.1:18060/mcp", "timeout": 9999},
        name="xiaohongshu-mcp",
    ) as mcp_server:
        tool = await mcp_server.list_tools()
        print(tool)

if __name__ == "__main__":
    asyncio.run(test_streamable_http())
