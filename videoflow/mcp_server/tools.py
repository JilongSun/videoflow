from mcp.server.fastmcp import FastMCP
from videoflow.core.graph import video_flow_workflow
from videoflow.core.progress import progress_store
from videoflow.utils.crawlers.crawler import crawler
from videoflow.utils import log
from typing import Optional, Union
import uuid


mcp = FastMCP(
    "VideoFlow",
    instructions="VideoFlow 是一个 AI 视频编辑工作流 MCP 服务。"
    "支持独立视频搜索与下载（tool_search_video/tool_download_video）以及"
    "基于本地视频的完整工作流执行（tool_run_video_workflow）。",
    port=18070,
)


@mcp.tool()
async def tool_search_video(
    keyword: str,
    publish_time: Union[int, str] = "7",
) -> list:
    """独立搜索视频候选列表。

    Args:
        keyword: 视频搜索关键词
        publish_time: 发布时间筛选，支持 1/7/182 等（按 TikHub 接口约定）

    Returns:
        视频候选链接列表（最多 10 条）
    """
    return await crawler.search_video(keyword, publish_time)


@mcp.tool()
async def tool_download_video(
    video_url: str,
    file_name: Optional[str] = None,
    download_path: Optional[str] = None,
) -> dict:
    """通过分享链接下载视频到本地。

    Args:
        video_url: 视频分享链接（HTTP URL）
        file_name: 本地文件名（可选，不指定则自动生成）
        download_path: 本地下载路径（可选，默认为 outputs/videos）

    Returns:
        包含 success（下载是否成功）和 video_id（本地视频 ID）的字典
    """
    success, video_id = await crawler.download_video(
        video_url, file_name=file_name, download_path=download_path
    )
    return {"success": success, "video_id": video_id}


@mcp.tool()
async def tool_run_video_workflow(
    prompt: str,
    image_input: str,
    video_keyword: str,
    video_input: str,
    session_id: Optional[str] = None,
) -> dict:
    """启动视频编辑工作流（第一阶段）。

    对于 > 5 秒的视频，工作流会先处理首个分片并返回预览结果，
    此时返回值中包含 `__interrupt__` 字段，Agent 需调用
    `tool_resume_video_workflow` 确认后继续。

    对于 ≤ 5 秒的视频，工作流一次性完成。

    Args:
        prompt: 视频编辑提示词，描述对视频的修改意图。分两种模式：
            - 不使用参考图片（直接描述替换效果）：
              例："Turn the wheels of the taxi to blocks of ice. Keep everything else the same."
            - 使用参考图片（将 image_input 中的物体替换到视频中）：
              例："Replace the cat in the video with the cat in the picture"
        image_input: 参考图片来源，可以是 HTTP URL 或本地图片文件名；
            若提示词不涉及参考图片，可传空字符串
        video_keyword: 视频关键词，用于素材检索或视频分析
        video_input: 本地视频路径
        session_id: 会话 ID（可选，不提供则自动生成）
    """
    from videoflow.core.graph import VideoEditState

    log.info(
        f"启动视频编辑工作流，视频输入: {video_input}, 提示词: {prompt}, 参考图片: {image_input}, 视频关键词: {video_keyword}, 会话ID: {session_id or ''}"
    )
    state = VideoEditState(
        prompt=prompt,
        image_input=image_input,
        video_keyword=video_keyword,
        session_id=session_id or "",
        video_input=video_input,
    )
    return await video_flow_workflow.ainvoke(state)


@mcp.tool()
async def tool_resume_video_workflow(
    session_id: str,
    approved: bool,
) -> dict:
    """恢复被暂停的视频编辑工作流（第二阶段）。

    当 `tool_run_video_workflow` 返回 `__interrupt__` 时，
    Agent 应展示预览给用户确认，然后调用此工具恢复工作流。

    Args:
        session_id: 第一阶段返回的会话 ID
        approved: 用户是否确认首片预览效果满意
    """
    return await video_flow_workflow.resume(session_id, {"approved": approved})


@mcp.tool()
async def tool_create_session() -> dict:
    """创建一个新的工作流会话 ID。

    Agent 必须在调用 `tool_run_video_workflow` 之前先调用此工具获取 session_id，
    并将 session_id 告知用户，方便用户后续查询进度。

    Returns:
        包含 session_id 的字典
    """
    session_id = str(uuid.uuid4())[0:6]  # 生成一个简短的随机 session_id
    log.info(f"创建新会话: {session_id}")
    return {"session_id": session_id}


@mcp.tool()
async def tool_get_workflow_progress(
    session_id: str,
) -> dict:
    """查询视频编辑工作流的执行进度。

    返回当前阶段（phase）、各分片完成状态和总体完成百分比。

    Args:
        session_id: 工作流会话 ID

    Returns:
        包含 phase、percent、slices 等进度信息的字典；
        若 session_id 不存在则返回错误提示
    """
    summary = progress_store.get_summary(session_id)
    if summary is None:
        return {"error": f"未找到会话: {session_id}", "session_id": session_id}
    return summary
