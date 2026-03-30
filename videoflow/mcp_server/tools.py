from mcp.server.fastmcp import FastMCP
from videoflow.core.graph import video_flow_workflow
from videoflow.utils import log
from typing import Optional, Union, List


mcp = FastMCP(
    "VideoFlow",
    instructions="VideoFlow 是一个 AI 视频编辑工作流 MCP 服务。"
    "支持视频搜索、下载、AI分析、分割、编辑（Runway Gen4Aleph）和拼接。"
    "可以单独调用各个工具，也可以通过 run_video_workflow 执行完整工作流。",
    port=18070,
)


@mcp.tool()
async def tool_run_video_workflow(
    image_url: str,
    video_keyword: str,
    video_url: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """执行完整的视频编辑工作流（基于 LangGraph 状态机）

    流程: 下载图片 → 搜索视频 → (中断返回候选列表) → 分割 → 编辑 → 拼接

    当未提供 video_url 时，会搜索视频并返回候选列表，status 为 "pending_selection"。
    此时需要调用 tool_resume_video_workflow 传入选择的视频文件名来恢复工作流。

    Args:
        image_url: 图片 HTTP URL
        video_keyword: 视频搜索关键词
        video_url: 直接提供已下载的视频文件名，跳过搜索（可选）
        session_id: 会话 ID（可选，不提供则自动生成）
    """
    from videoflow.core.graph import VideoEditState

    state = VideoEditState(
        image_url=image_url,
        video_keyword=video_keyword,
        session_id=session_id or "",
        video_url=video_url,
    )
    return await video_flow_workflow.ainvoke(state)


@mcp.tool()
async def tool_resume_video_workflow(
    session_id: str,
    selected_video_file: str,
) -> dict:
    """恢复中断的视频编辑工作流

    在 tool_run_video_workflow 返回 pending_selection 后，用户选择视频后调用此工具继续。

    Args:
        session_id: 工作流会话 ID（从 tool_run_video_workflow 的返回值中获取）
        selected_video_file: 用户选择的视频文件名（已下载到本地）
    """
    return await video_flow_workflow.resume(session_id, selected_video_file)
