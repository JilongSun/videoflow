from mcp.server.fastmcp import FastMCP
from videoflow.core.tools import (
    search_video,
    download_video,
    download_image,
    analyze_video,
    edit_video,
    split_video,
    concatenate_video,
)
from videoflow.core.graph import video_flow_workflow
from videoflow.utils import log
from typing import Optional, Union, List


mcp = FastMCP(
    "VideoFlow",
    instructions="VideoFlow 是一个 AI 视频编辑工作流 MCP 服务。"
    "支持视频搜索、下载、AI分析、分割、编辑（Runway Gen4Aleph）和拼接。"
    "可以单独调用各个工具，也可以通过 run_video_workflow 执行完整工作流。",
)


@mcp.tool()
async def tool_search_video(keyword: str, publish_time: str = "1") -> list:
    """搜索抖音视频，返回候选视频分享链接列表

    Args:
        keyword: 视频搜索关键词
        publish_time: 发布时间筛选，"1"=最近1天，"7"=最近7天
    """
    return await search_video(keyword, publish_time)


@mcp.tool()
async def tool_download_video(video_url: str, file_name: Optional[str] = None) -> dict:
    """下载抖音视频到本地

    Args:
        video_url: 视频分享链接
        file_name: 保存的文件名（可选，不提供则自动生成）
    """
    return await download_video(video_url, file_name)


@mcp.tool()
async def tool_download_image(image_url: str, file_name: Optional[str] = None) -> dict:
    """下载图片到本地，支持 HTTP URL

    Args:
        image_url: 图片的 HTTP URL
        file_name: 保存的文件名（可选）
    """
    return await download_image(image_url, file_name)


@mcp.tool()
async def tool_analyze_video(video_path: str, object_keyword: str) -> dict:
    """使用 AI（Qwen3-VL）分析视频中目标物体出现的时间段

    Args:
        video_path: 视频文件名（位于 outputs/videos/ 下）
        object_keyword: 要检测的目标物体关键词（如"猫"、"狗"）
    """
    return await analyze_video(video_path, object_keyword)


@mcp.tool()
async def tool_split_video(video_path: str, time_slices: list) -> dict:
    """按时间段分割视频

    Args:
        video_path: 视频文件名
        time_slices: 时间段列表，格式 [[start_sec, end_sec], ...]
    """
    return await split_video(video_path, time_slices)


@mcp.tool()
async def tool_edit_video(
    video_path: str, image_path: str, prompt: Optional[str] = None
) -> dict:
    """使用 Runway Gen4Aleph AI 编辑视频（替换视频中的物体），单片段≤5秒

    Args:
        video_path: 视频文件名
        image_path: 参考图片文件名（用于替换的目标图片）
        prompt: 编辑提示词（可选）
    """
    return await edit_video(video_path, image_path, prompt)


@mcp.tool()
async def tool_concatenate_video(video_list: list, original_video: str) -> dict:
    """拼接多段编辑后的视频

    Args:
        video_list: 视频片段信息列表，格式 [{"start": int, "end": int, "sliced_file": str, "edited_file": str}, ...]
        original_video: 原始视频文件名
    """
    return await concatenate_video(video_list, original_video)


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
        messages=[],
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
