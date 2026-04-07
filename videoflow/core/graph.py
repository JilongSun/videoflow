from typing import Dict, Any, Optional, List, Annotated, cast
from pathlib import Path
from langgraph.graph import StateGraph, END, START
from langgraph.types import interrupt, Command
from videoflow.utils import log
from pydantic import BaseModel, Field
from videoflow.utils.file_processor import (
    write_file,
    image_processor,
    video_processor,
)
from .chatmodel import gen4aleph
import asyncio, uuid, httpx, math, importlib, shutil, mimetypes
from urllib.parse import urlparse


MAX_SLICE_SEC = 5  # Runway Gen4Aleph 单次处理上限


class VideoEditState(BaseModel):
    """
    视频编辑工作流状态。
    第一层（MVP）：固定 5 秒切分 → 全量送 Runway → 拼接
    第二层（质量控制）：先处理首片 → interrupt 等待人工确认 → 批量处理剩余
    """

    # --- media inputs ---
    image_input: str = Field(
        ...,
        description="用户上传的图片url (HTTP)或本地图片路径",
    )
    video_input: Annotated[str, "本地视频路径"]

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
        self.workflow = self.compile()

    def _get_sqlite_checkpointer(self) -> Any:
        # 持久化到项目根目录下的 .langgraph/checkpoints.db
        try:
            sqlite_module = importlib.import_module("langgraph.checkpoint.sqlite")
            SqliteSaver = getattr(sqlite_module, "SqliteSaver")
        except ImportError as e:
            raise ImportError(
                "缺少依赖 langgraph-checkpoint-sqlite，请先执行 `uv sync` 或安装该包"
            ) from e

        project_root = Path(__file__).resolve().parents[2]
        checkpoint_dir = project_root / ".langgraph"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_db = checkpoint_dir / "checkpoints.db"
        log.info(f"使用 SQLite 持久化检查点: {checkpoint_db}")
        return SqliteSaver.from_conn_string(str(checkpoint_db))

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

    @staticmethod
    def _is_url(path: str) -> bool:
        return path.startswith(("http://", "https://"))

    @staticmethod
    def _guess_name_from_url(url: str, default_name: str) -> str:
        parsed = urlparse(url)
        base = Path(parsed.path).name
        return base if base else default_name

    @staticmethod
    def _guess_ext_from_content_type(
        content_type: Optional[str],
        default_ext: str,
    ) -> str:
        if not content_type:
            return default_ext
        guessed_ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        return guessed_ext or default_ext

    async def _materialize_media(
        self,
        resource: str,
        media_type: str,
    ) -> str:
        """将输入素材统一落地到项目 outputs 目录，并返回本地文件名。"""
        if media_type not in {"image", "video"}:
            raise ValueError(f"不支持的 media_type: {media_type}")

        if media_type == "image":
            writer_dir = Path(image_processor.file_writer_folder)
            default_name = f"image_{uuid.uuid4().hex[:8]}.webp"
            default_ext = ".webp"
        else:
            writer_dir = Path(video_processor.file_writer_folder)
            default_name = f"video_{uuid.uuid4().hex[:8]}.mp4"
            default_ext = ".mp4"

        writer_dir.mkdir(parents=True, exist_ok=True)

        # 1) URL: 直接下载到项目目录
        if self._is_url(resource):
            file_name = self._guess_name_from_url(resource, default_name)
            async with httpx.AsyncClient() as client:
                response = await client.get(resource, timeout=600)
                response.raise_for_status()
            if not Path(file_name).suffix:
                file_name = file_name + self._guess_ext_from_content_type(
                    response.headers.get("content-type"),
                    default_ext,
                )
            success = await write_file(file_name, response.content)
            if not success:
                raise RuntimeError(f"下载并写入失败: {resource} -> {file_name}")
            log.info(f"{media_type} URL 下载成功: {resource} -> {file_name}")
            return file_name

        # 2) 先尝试直接当作已在项目 outputs 中的文件名
        existing_in_output = writer_dir / resource
        if existing_in_output.is_file():
            log.info(f"{media_type} 已在项目目录中: {existing_in_output}")
            return resource

        # 3) 本地路径: 若在项目内，尽量转成文件名；否则复制到项目目录
        source_path = Path(resource)
        if not source_path.is_absolute():
            source_path = source_path.resolve()

        if not source_path.is_file():
            raise FileNotFoundError(f"{media_type} 输入不存在: {resource}")

        source_name = source_path.name
        if not Path(source_name).suffix:
            source_name = source_name + default_ext
        target_path = writer_dir / source_name

        project_root = Path(__file__).resolve().parents[2]
        is_inside_project = project_root in source_path.parents

        # 若已在对应 outputs 目录，直接复用
        if source_path.parent == writer_dir:
            log.info(f"{media_type} 已在目标目录中: {source_path}")
            return source_path.name

        # 不在项目根目录或在项目内但不在 outputs，都复制到标准目录，保证后续路径一致
        await asyncio.to_thread(shutil.copy2, str(source_path), str(target_path))
        log.info(
            f"{media_type} 已落地到项目目录: {source_path} -> {target_path}, "
            f"inside_project={is_inside_project}"
        )
        return target_path.name

    async def prepare_media_inputs(self, state: VideoEditState) -> VideoEditState:
        """统一素材落地：将图片和视频都放入项目 outputs 目录。"""
        state.image_input = await self._materialize_media(
            state.image_input,
            media_type="image",
        )
        state.video_input = await self._materialize_media(
            state.video_input,
            media_type="video",
        )
        log.info(f"素材落地完成: image={state.image_input}, video={state.video_input}")
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """固定 5 秒等分切割视频"""
        if state.video_input.startswith(("http://", "https://")):
            raise ValueError(
                "video_input 必须是本地视频文件，请先下载到本地后再启动工作流"
            )

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

        res = await gen4aleph.ainvoke([state.image_input], first_slice[1])
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
                    asyncio.create_task(gen4aleph.ainvoke([state.image_input], s[1]))
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
            checkpointer = self._get_sqlite_checkpointer()
        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState) -> Dict[str, Any]:
        """启动视频编辑工作流（第一阶段调用）"""
        session_id = state.session_id or str(uuid.uuid4())
        state.session_id = session_id
        config = {"configurable": {"thread_id": session_id}}
        return await self.workflow.ainvoke(state, config)  # type: ignore

    async def resume(self, session_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        """恢复被 interrupt 暂停的工作流（第二阶段调用）

        Args:
            session_id: 工作流会话ID（与第一阶段相同）
            decision: 人工确认结果，如 {"approved": True}
        """
        config = {"configurable": {"thread_id": session_id}}
        return await self.workflow.ainvoke(Command(resume=decision), config)  # type: ignore


video_flow_workflow = VideoFlowWorkflow()
