from mcp.server.fastmcp import FastMCP
from videoflow.core.graph import VideoFlowWorkflow
from videoflow.core.progress import progress_store
from videoflow.core.progress import WorkflowPhase
from videoflow.utils.crawlers.crawler import crawler
from videoflow.utils import log
from typing import Any, Optional, Union
import uuid, asyncio


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
    model_type: str = "wan2.7-videoedit",
    model_options: Optional[dict] = None,
    session_id: Optional[str] = None,
) -> dict:
    """启动视频编辑工作流（第一阶段）。

    工具会立即返回 started 状态与 session_id，实际处理在后台执行。
    Agent 应在收到返回后立刻把 session_id 告知用户，方便后续查询进度。

    对于超出模型单次上限的视频（如 runway 为 5 秒、wan2.7 为 10 秒），
    后台工作流会先处理首个分片并进入 waiting_approval；
    Agent 通过 `tool_get_workflow_progress` 获取 interrupt_payload 进行用户确认，
    再调用 `tool_resume_video_workflow` 继续。

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
        model_type: 模型类型，支持 wan2.7-videoedit/runway-gen4aleph；默认 wan2.7-videoedit
        model_options: 模型可选参数（字典），例如 resolution/audio_setting/prompt_extend
        session_id: 会话 ID（可选，不提供则自动生成）
    """
    from videoflow.core.graph import VideoEditState

    sid = session_id or str(uuid.uuid4())
    existing = progress_store.get(sid)
    if existing is not None and existing.start_requested:
        log.warning(f"会话已执行过启动操作，跳过重复启动: {sid}")
        return {
            "session_id": sid,
            "status": "already_started",
            "message": f"session_id={sid} 已执行过启动操作",
        }

    state = VideoEditState(
        prompt=prompt,
        image_input=image_input,
        video_keyword=video_keyword,
        session_id=sid,
        video_input=video_input,
        model_type=model_type,
        model_options=model_options,
    )
    progress_store.create_if_absent(sid)
    progress_store.set_model_type(sid, model_type)
    progress_store.mark_start_requested(sid)
    asyncio.create_task(_run_workflow_bg(state, sid))
    log.info(f"工作流已启动（后台）: {sid}")
    return {"session_id": sid, "status": "started"}


async def _run_workflow_bg(state: Any, session_id: str) -> None:
    """后台任务：运行工作流直到完成或中断，结果写入 progress_store。"""
    try:
        async with VideoFlowWorkflow() as wf:
            result = await wf.ainvoke(state)

        interrupted = result.get("__interrupt__")
        if interrupted:
            # 取第一个中断 payload（LangGraph 返回列表）
            payload = interrupted[0].value if hasattr(interrupted[0], "value") else interrupted[0]
            progress_store.set_interrupt_payload(session_id, payload)
            progress_store.set_phase(session_id, WorkflowPhase.WAITING_APPROVAL)
            log.info(f"[bg] 工作流中断，等待确认: {session_id}")
        else:
            progress_store.set_result(session_id, result)
            log.info(f"[bg] 工作流完成: {session_id}")
    except Exception as e:
        log.error(f"[bg] 工作流异常: {session_id} → {e}")
        progress_store.set_phase(session_id, WorkflowPhase.FAILED)
        progress_store.set_result(session_id, {"error": str(e)})


@mcp.tool()
async def tool_resume_video_workflow(
    session_id: str,
    approved: bool,
) -> dict:
    """恢复被暂停的视频编辑工作流（第二阶段，后台执行）。

    当 `tool_get_workflow_progress` 返回 phase=waiting_approval 时，
    Agent 应展示 interrupt_payload 中的预览给用户确认，然后调用此工具。
    工具立即返回，恢复在后台进行，可继续通过 `tool_get_workflow_progress` 轮询。

    Args:
        session_id: 第一阶段返回的会话 ID
        approved: 用户是否确认首片预览效果满意
    """
    session = progress_store.get(session_id)
    if session is None:
        return {
            "session_id": session_id,
            "status": "not_found",
            "message": f"session_id={session_id} 不存在，无法恢复",
        }
    if session.phase != WorkflowPhase.WAITING_APPROVAL:
        return {
            "session_id": session_id,
            "status": "invalid_phase",
            "message": (
                f"session_id={session_id} 当前阶段为 {session.phase.value}，"
                "仅 waiting_approval 阶段允许恢复"
            ),
            "phase": session.phase.value,
        }
    if session.resume_requested:
        return {
            "session_id": session_id,
            "status": "already_resumed",
            "message": f"session_id={session_id} 已执行过恢复操作",
        }

    progress_store.mark_resume_requested(session_id, approved)
    asyncio.create_task(_resume_workflow_bg(session_id, {"approved": approved}))
    log.info(f"工作流恢复已启动（后台）: {session_id}, approved={approved}")
    return {"session_id": session_id, "status": "resuming"}


async def _resume_workflow_bg(session_id: str, decision: dict) -> None:
    """后台任务：从 SQLite checkpoint 恢复工作流。"""
    try:
        async with VideoFlowWorkflow() as wf:
            result = await wf.resume(session_id, decision)
        progress_store.set_result(session_id, result)
        progress_store.set_phase(session_id, WorkflowPhase.COMPLETED)
        log.info(f"[bg] 工作流恢复完成: {session_id}")
    except Exception as e:
        log.error(f"[bg] 工作流恢复异常: {session_id} → {e}")
        progress_store.set_phase(session_id, WorkflowPhase.FAILED)
        progress_store.set_result(session_id, {"error": str(e)})


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
    log.info(f"查询工作流进度: {session_id}")
    summary = progress_store.get_summary(session_id)
    if summary is None:
        log.warning(f"未找到会话: {session_id}")
        return {"error": f"未找到会话: {session_id}", "session_id": session_id}
    return summary
