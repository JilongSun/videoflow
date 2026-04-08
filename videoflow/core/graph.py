from typing import Dict, Any, Optional, List, Annotated, cast
from pathlib import Path
from langgraph.graph import StateGraph, END, START
from langgraph.types import interrupt, Command
from videoflow.utils import log
from pydantic import BaseModel, Field
from videoflow.utils.file_processor import (
    write_file,
    video_processor,
    materialize_file,
)
from .chatmodel import gen4aleph
import asyncio, uuid, math


MAX_SLICE_SEC = 5  # Runway Gen4Aleph 单次处理上限


class VideoEditState(BaseModel):
    """
    视频编辑工作流状态。
    第一层（MVP）：固定 5 秒切分 → 全量送 Runway → 拼接
    第二层（质量控制）：先处理首片 → interrupt 等待人工确认 → 批量处理剩余
    """

    # --- runway inputs ---
    image_input: str = Field(
        ...,
        description="用户上传的图片url (HTTP)或本地图片路径",
    )
    video_input: Annotated[str, "本地视频路径"]
    prompt: str = Field(
        ...,
        description="用户输入的编辑提示，用于指导视频编辑模型",
    )

    # --- business parameters ---
    video_keyword: str = Field(
        ...,
        description="用户输入的视频关键词, 用于素材检索或视频分析",
    )
    session_id: str = Field(
        default="",
        description="工作流会话ID，用于标识一次执行",
    )
    video_time_slice: Annotated[
        Optional[List[List]],
        "[[[start_sec, end_sec], sliced_video, edited_sliced_video]]",
    ] = None
    preview_slice: Annotated[
        Optional[str],
        "首片编辑结果文件名，用于人工预览确认",
    ] = None
    result: Optional[str] = None
    complete: Annotated[
        Optional[bool],
        "是否完成视频编辑工作流",
    ] = None


class VideoFlowWorkflow:
    """视频处理工作流框架

    流程: prepare_media_inputs → split_video → preview_first_slice → object_replace → END
                                              ↑
                                        interrupt() 等待人工确认
    """

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow: Optional[Any] = None
        self._checkpointer_cm: Optional[Any] = None
        self._checkpointer: Optional[Any] = None
        self._workflow_lock = asyncio.Lock()

    def _get_sqlite_checkpointer(self) -> Any:
        # 持久化到项目根目录下的 .langgraph/checkpoints.db
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError as e:
            raise ImportError(
                "缺少依赖 langgraph-checkpoint-sqlite，请先执行 `uv sync` 或安装该包"
            ) from e

        project_root = Path(__file__).resolve().parents[2]
        checkpoint_dir = project_root / ".langgraph"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_db = checkpoint_dir / "checkpoints.db"
        log.info(f"使用 SQLite 持久化检查点: {checkpoint_db}")
        # from_conn_string 返回 async context manager
        return AsyncSqliteSaver.from_conn_string(str(checkpoint_db))

    async def _ensure_workflow(self) -> None:
        if self.workflow is not None:
            return

        async with self._workflow_lock:
            if self.workflow is not None:
                return

            checkpointer_cm = self._get_sqlite_checkpointer()
            checkpointer = await checkpointer_cm.__aenter__()
            self._checkpointer_cm = checkpointer_cm
            self._checkpointer = checkpointer
            self.workflow = self.compile(checkpointer=checkpointer)

    def _setup_workflow(self):
        """设置工作流节点和边"""
        self.graph.add_node("prepare_media_inputs", self.prepare_media_inputs)
        self.graph.add_node("split_video", self.split_video)
        self.graph.add_node("preview_first_slice", self.preview_first_slice)
        self.graph.add_node("object_replace", self.object_replace)

        self.graph.add_edge(START, "prepare_media_inputs")
        self.graph.add_edge("prepare_media_inputs", "split_video")
        self.graph.add_edge("split_video", "preview_first_slice")
        self.graph.add_edge("preview_first_slice", "object_replace")
        self.graph.add_edge("object_replace", END)

    # ── 节点实现 ──────────────────────────────────────

    async def prepare_media_inputs(self, state: VideoEditState) -> VideoEditState:
        """统一素材落地：将图片和视频都放入项目 outputs 目录。"""
        state.image_input = await materialize_file(state.image_input, "image")
        state.video_input = await materialize_file(state.video_input, "video")
        log.info(f"素材落地完成: image={state.image_input}, video={state.video_input}")
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """固定 5 秒等分切割视频"""
        total_sec = await video_processor.detect_video_len(state.video_input)

        if total_sec <= MAX_SLICE_SEC:
            log.info(f"视频时长 {total_sec}s ≤ {MAX_SLICE_SEC}s，无需分割")
            return state

        # 按固定 5 秒切分
        num_slices = math.ceil(total_sec / MAX_SLICE_SEC)
        log.info(f"视频时长 {total_sec}s，将切为 {num_slices} 个分片")

        temp_list = []
        for i in range(num_slices):
            start = i * MAX_SLICE_SEC
            end = min((i + 1) * MAX_SLICE_SEC, total_sec)
            new_video = await video_processor.split_video(
                state.video_input, start=start, end=end
            )
            temp_list.append([[start, end], new_video])

        state.video_time_slice = temp_list
        return state

    async def preview_first_slice(self, state: VideoEditState) -> VideoEditState:
        """处理首片并 interrupt 等待人工确认效果

        - 视频 ≤ 5s (无分片): 直接处理，不中断
        - 视频 > 5s (有分片): 先处理第 1 片，interrupt 展示预览，
          Agent 确认后再继续批量处理剩余片段
        """
        if not state.video_time_slice:
            # 无分片，跳过预览直接走 object_replace
            return state

        first_slice = state.video_time_slice[0]
        log.info(f"处理首片预览: {first_slice[1]} ({first_slice[0]})")

        res = await gen4aleph.ainvoke(state.prompt, [state.image_input], first_slice[1])
        if res.content is None:
            raise ValueError(f"首片编辑失败: {first_slice[1]}")

        edited_name = "edited_" + first_slice[1]
        await write_file(edited_name, cast(str, res.content))
        first_slice.append(edited_name)
        state.preview_slice = edited_name

        log.info(f"首片预览已生成: {edited_name}，等待人工确认")

        # interrupt: 暂停工作流，将预览信息返回给 Agent
        decision = interrupt(
            {
                "preview_video": edited_name,
                "original_slice": first_slice[1],
                "time_range": first_slice[0],
                "remaining_slices": len(state.video_time_slice) - 1,
                "message": "首片编辑预览已生成，请确认效果是否满意。",
            }
        )

        # Agent 通过 Command(resume={"approved": True/False}) 恢复
        if not decision.get("approved", False):
            state.complete = False
            state.result = "用户拒绝了首片预览效果，工作流中止"
            log.info("用户拒绝首片预览，工作流中止")
            # 返回状态，object_replace 会检查 complete 跳过处理
            return state

        log.info("用户确认首片效果，继续处理剩余分片")
        return state

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """AI 视频编辑：替换视频中的物体

        - 无分片: 直接处理整个视频
        - 有分片: 首片已在 preview_first_slice 中处理完成，
          这里只处理剩余分片，然后拼接
        """
        # 如果用户拒绝了预览，直接结束
        if state.complete is False:
            return state

        if not state.video_time_slice:
            # 视频 ≤ 5s，直接处理
            log.info(f"视频无需分割，直接编辑: {state.video_input}")
            res = await gen4aleph.ainvoke(
                state.prompt,
                [state.image_input],
                state.video_input,
            )
            if res.content is None:
                raise ValueError("视频编辑失败")
            state.result = cast(str, res.content)
            await write_file("edited_" + state.video_input, state.result)

        else:
            # 首片已在 preview_first_slice 中完成，处理剩余分片
            remaining = state.video_time_slice[1:]
            if remaining:
                log.info(f"开始并行处理剩余 {len(remaining)} 个分片")
                tasks = [
                    asyncio.create_task(
                        gen4aleph.ainvoke(state.prompt, [state.image_input], s[1])
                    )
                    for s in remaining
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for res, slice_info in zip(results, remaining):
                    if isinstance(res, BaseException):
                        log.error(
                            f"分片编辑失败: {slice_info[1]} "
                            f"({slice_info[0]}), 错误: {res}"
                        )
                        raise ValueError(
                            f"分片编辑失败: {slice_info[1]} ({slice_info[0]}), "
                            f"错误: {res}"
                        )
                    edited_video = res
                    if edited_video.content is None:
                        raise ValueError(f"分片编辑返回空结果: {slice_info[1]}")
                    edited_name = "edited_" + slice_info[1]
                    await write_file(edited_name, cast(str, edited_video.content))
                    slice_info.append(edited_name)

            # 拼接所有分片（包括已处理的首片）
            new_video = await video_processor.concatenate_video(
                state.video_time_slice, state.video_input
            )
            state.result = new_video

        state.complete = True
        return state

    # ── 编译与执行 ──────────────────────────────────────

    def compile(self, checkpointer: Optional[Any] = None):
        if checkpointer is None:
            raise ValueError("compile 需要已初始化的 checkpointer")
        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState) -> Dict[str, Any]:
        """启动视频编辑工作流（第一阶段调用）"""
        await self._ensure_workflow()
        session_id = state.session_id or str(uuid.uuid4())
        state.session_id = session_id
        config = {"configurable": {"thread_id": session_id}}
        if self.workflow is None:
            raise RuntimeError("workflow 初始化失败")
        return await self.workflow.ainvoke(state, config)  # type: ignore

    async def resume(self, session_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        """恢复被 interrupt 暂停的工作流（第二阶段调用）

        Args:
            session_id: 工作流会话ID（与第一阶段相同）
            decision: 人工确认结果，如 {"approved": True}
        """
        await self._ensure_workflow()
        config = {"configurable": {"thread_id": session_id}}
        if self.workflow is None:
            raise RuntimeError("workflow 初始化失败")
        return await self.workflow.ainvoke(Command(resume=decision), config)  # type: ignore


video_flow_workflow = VideoFlowWorkflow()
