from typing import Any, Dict, Optional, List, cast
from pathlib import Path
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command, interrupt
from videoflow.utils import log
from videoflow.utils.file_processor import (
    video_processor,
    materialize_file,
    get_file_path,
)
from videoflow.core.chatmodel import gen4aleph
from videoflow.core.progress import progress_store, WorkflowPhase, SliceStatus
import asyncio
import uuid
import math
import json
import shutil

from .state import VideoEditState


MAX_SLICE_SEC = 5  # Runway Gen4Aleph 单次处理上限


class SliceReplaceWorkflow:
    """特征：固定 5 秒切片 + 分片替换 + 拼接。"""

    name = "slice_replace"

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow: Optional[Any] = None
        self._checkpointer_cm: Optional[Any] = None

    async def __aenter__(self):
        self._checkpointer_cm = self._get_sqlite_checkpointer()
        if self._checkpointer_cm is None:
            raise RuntimeError("无法获取 checkpointer，无法进入工作流上下文")
        checkpointer = await self._checkpointer_cm.__aenter__()
        self.workflow = self.compile(checkpointer=checkpointer)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._checkpointer_cm:
            await self._checkpointer_cm.__aexit__(exc_type, exc_val, exc_tb)
            self._checkpointer_cm = None
        self.workflow = None
        return False

    def _get_sqlite_checkpointer(self) -> Any:
        # 持久化到项目根目录下的 .langgraph/checkpoints.db
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError as e:
            raise ImportError(
                "缺少依赖 langgraph-checkpoint-sqlite，请先执行 `uv sync` 或安装该包"
            ) from e

        project_root = Path(__file__).resolve().parents[3]
        checkpoint_dir = project_root / ".langgraph"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_db = checkpoint_dir / "checkpoints.db"
        log.info(f"使用 SQLite 持久化检查点: {checkpoint_db}")
        return AsyncSqliteSaver.from_conn_string(str(checkpoint_db))

    def _setup_workflow(self) -> None:
        self.graph.add_node("prepare_media_inputs", self.prepare_media_inputs)
        self.graph.add_node("split_video", self.split_video)
        self.graph.add_node("preview_first_slice", self.preview_first_slice)
        self.graph.add_node("object_replace", self.object_replace)

        self.graph.add_edge(START, "prepare_media_inputs")
        self.graph.add_edge("prepare_media_inputs", "split_video")
        self.graph.add_edge("split_video", "preview_first_slice")
        self.graph.add_edge("preview_first_slice", "object_replace")
        self.graph.add_edge("object_replace", END)

    async def _write_video_to_path(self, path: str, content: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        await video_processor.write_file(p.name, content, str(p.parent))

    async def _persist_manifest(self, state: VideoEditState) -> None:
        if not state.manifest_path or state.slice_manifest is None:
            return
        data = {
            "session_id": state.session_id,
            "video_input": state.video_input,
            "prompt": state.prompt,
            "slices": state.slice_manifest,
            "result": state.result,
        }

        def _dump() -> None:
            p = Path(state.manifest_path or "")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        await asyncio.to_thread(_dump)

    async def _stage_file_to_session_input(
        self,
        source_path: str,
        session_input_dir: str,
        prefix: str,
    ) -> str:
        """将素材复制到会话 input 目录，返回绝对路径。"""
        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(f"素材文件不存在: {source_path}")
        dst = Path(session_input_dir) / f"{prefix}_{src.name}"
        if src.resolve() == dst.resolve():
            return str(dst)
        await asyncio.to_thread(shutil.copy2, str(src), str(dst))
        return str(dst)

    async def prepare_media_inputs(self, state: VideoEditState) -> VideoEditState:
        """统一素材落地并归档到会话目录。"""
        progress_store.set_phase(state.session_id, WorkflowPhase.PREPARING)
        state.work_dirs = await video_processor.ensure_session_dirs(state.session_id)
        state.manifest_path = str(
            Path(state.work_dirs["manifest"]) / "workflow_manifest.json"
        )

        image_name = await materialize_file(state.image_input, "image")
        video_name = await materialize_file(state.video_input, "video")

        image_src_path = Path(image_name)
        if not image_src_path.is_file():
            image_src_path = Path(await get_file_path(image_name))

        video_src_path = Path(video_name)
        if not video_src_path.is_file():
            video_src_path = Path(await get_file_path(video_name))

        state.image_input = await self._stage_file_to_session_input(
            str(image_src_path),
            state.work_dirs["input"],
            "image",
        )
        state.video_input = await self._stage_file_to_session_input(
            str(video_src_path),
            state.work_dirs["input"],
            "video",
        )

        log.info(
            f"素材会话归档完成: image={state.image_input}, video={state.video_input}"
        )
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """固定 5 秒等分切割视频"""
        progress_store.set_phase(state.session_id, WorkflowPhase.SPLITTING)
        total_sec = await video_processor.detect_video_len(state.video_input)

        if total_sec <= MAX_SLICE_SEC:
            log.info(f"视频时长 {total_sec}s <= {MAX_SLICE_SEC}s，无需分割")
            progress_store.init_slices(state.session_id, [[0, total_sec]])
            state.slice_manifest = [
                {
                    "index": 0,
                    "start": 0,
                    "end": total_sec,
                    "source_video": state.video_input,
                    "edited_video": None,
                    "status": "pending",
                    "error": None,
                }
            ]
            await self._persist_manifest(state)
            return state

        num_slices = math.ceil(total_sec / MAX_SLICE_SEC)
        log.info(f"视频时长 {total_sec}s，将切为 {num_slices} 个分片")

        temp_list = []
        time_ranges = []
        manifest_items: List[Dict[str, Any]] = []
        for i in range(num_slices):
            start = i * MAX_SLICE_SEC
            end = min((i + 1) * MAX_SLICE_SEC, total_sec)
            new_video = await video_processor.split_video(
                state.video_input,
                start=start,
                end=end,
                session_id=state.session_id,
                slice_index=i,
            )
            temp_list.append([[start, end], new_video])
            time_ranges.append([start, end])
            manifest_items.append(
                {
                    "index": i,
                    "start": start,
                    "end": end,
                    "source_video": new_video,
                    "edited_video": None,
                    "status": "pending",
                    "error": None,
                }
            )

        state.video_time_slice = temp_list
        state.slice_manifest = manifest_items
        progress_store.init_slices(state.session_id, time_ranges)
        await self._persist_manifest(state)
        return state

    async def preview_first_slice(self, state: VideoEditState) -> VideoEditState:
        if not state.video_time_slice:
            return state

        progress_store.set_phase(state.session_id, WorkflowPhase.PREVIEW)
        work_dirs = state.work_dirs or await video_processor.ensure_session_dirs(
            state.session_id
        )
        state.work_dirs = work_dirs
        first_slice = state.video_time_slice[0]
        log.info(f"处理首片预览: {first_slice[1]} ({first_slice[0]})")

        progress_store.update_slice(state.session_id, 0, SliceStatus.PROCESSING)
        try:
            res = await gen4aleph.ainvoke(
                state.prompt, [state.image_input], first_slice[1]
            )
            if res.content is None:
                raise ValueError(f"首片编辑失败: {first_slice[1]}")
        except Exception as e:
            progress_store.update_slice(
                state.session_id, 0, SliceStatus.FAILED, error=str(e)
            )
            progress_store.set_phase(state.session_id, WorkflowPhase.FAILED)
            if state.slice_manifest:
                state.slice_manifest[0]["status"] = "failed"
                state.slice_manifest[0]["error"] = str(e)
                await self._persist_manifest(state)
            raise

        start, end = first_slice[0]
        start_ms = int(float(start) * 1000)
        end_ms = int(float(end) * 1000)
        edited_path = str(
            Path(work_dirs["edited"])
            / f"slice_000_{start_ms:08d}_{end_ms:08d}.edited.mp4"
        )
        await self._write_video_to_path(edited_path, cast(str, res.content))
        first_slice.append(edited_path)
        state.preview_slice = edited_path
        progress_store.update_slice(state.session_id, 0, SliceStatus.COMPLETED)
        if state.slice_manifest:
            state.slice_manifest[0]["status"] = "completed"
            state.slice_manifest[0]["edited_video"] = edited_path
            await self._persist_manifest(state)

        log.info(f"首片预览已生成: {edited_path}，等待人工确认")
        progress_store.set_phase(state.session_id, WorkflowPhase.WAITING_APPROVAL)

        decision = interrupt(
            {
                "preview_video": edited_path,
                "original_slice": first_slice[1],
                "time_range": first_slice[0],
                "remaining_slices": len(state.video_time_slice) - 1,
                "message": "首片编辑预览已生成，请确认效果是否满意。",
            }
        )

        if not decision.get("approved", False):
            state.complete = False
            state.result = "用户拒绝了首片预览效果，工作流中止"
            log.info("用户拒绝首片预览，工作流中止")
            progress_store.set_phase(state.session_id, WorkflowPhase.CANCELLED)
            await self._persist_manifest(state)
            return state

        log.info("用户确认首片效果，继续处理剩余分片")
        return state

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        if state.complete is False:
            return state

        work_dirs = state.work_dirs or await video_processor.ensure_session_dirs(
            state.session_id
        )
        state.work_dirs = work_dirs

        if not state.video_time_slice:
            log.info(f"视频无需分割，直接编辑: {state.video_input}")
            progress_store.set_phase(state.session_id, WorkflowPhase.BATCH_PROCESSING)
            progress_store.update_slice(state.session_id, 0, SliceStatus.PROCESSING)
            try:
                res = await gen4aleph.ainvoke(
                    state.prompt,
                    [state.image_input],
                    state.video_input,
                )
                if res.content is None:
                    raise ValueError("视频编辑失败")
            except Exception as e:
                progress_store.update_slice(
                    state.session_id, 0, SliceStatus.FAILED, error=str(e)
                )
                progress_store.set_phase(state.session_id, WorkflowPhase.FAILED)
                if state.slice_manifest:
                    state.slice_manifest[0]["status"] = "failed"
                    state.slice_manifest[0]["error"] = str(e)
                    await self._persist_manifest(state)
                raise

            final_path = str(Path(work_dirs["final"]) / f"final_{state.session_id}.mp4")
            state.result = final_path
            await self._write_video_to_path(final_path, cast(str, res.content))
            progress_store.update_slice(state.session_id, 0, SliceStatus.COMPLETED)
            if state.slice_manifest:
                state.slice_manifest[0]["status"] = "completed"
                state.slice_manifest[0]["edited_video"] = final_path
                await self._persist_manifest(state)

        else:
            remaining = state.video_time_slice[1:]
            if remaining:
                progress_store.set_phase(state.session_id, WorkflowPhase.BATCH_PROCESSING)
                log.info(f"开始并行处理剩余 {len(remaining)} 个分片")

                async def _process_slice(idx: int, slice_video: str):
                    progress_store.update_slice(
                        state.session_id, idx, SliceStatus.PROCESSING
                    )
                    try:
                        r = await gen4aleph.ainvoke(
                            state.prompt, [state.image_input], slice_video
                        )
                        if r.content is None:
                            raise ValueError(f"分片编辑返回空结果: {slice_video}")
                        progress_store.update_slice(
                            state.session_id, idx, SliceStatus.COMPLETED
                        )
                        return r
                    except Exception as e:
                        progress_store.update_slice(
                            state.session_id, idx, SliceStatus.FAILED, error=str(e)
                        )
                        if state.slice_manifest and idx < len(state.slice_manifest):
                            state.slice_manifest[idx]["status"] = "failed"
                            state.slice_manifest[idx]["error"] = str(e)
                        raise

                tasks = [
                    asyncio.create_task(_process_slice(i + 1, s[1]))
                    for i, s in enumerate(remaining)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, (res, slice_info) in enumerate(zip(results, remaining), start=1):
                    if isinstance(res, BaseException):
                        log.error(
                            f"分片编辑失败: {slice_info[1]} ({slice_info[0]}), 错误: {res}"
                        )
                        progress_store.set_phase(state.session_id, WorkflowPhase.FAILED)
                        await self._persist_manifest(state)
                        raise ValueError(
                            f"分片编辑失败: {slice_info[1]} ({slice_info[0]}), 错误: {res}"
                        )
                    edited_video = res
                    start, end = slice_info[0]
                    start_ms = int(float(start) * 1000)
                    end_ms = int(float(end) * 1000)
                    edited_path = str(
                        Path(work_dirs["edited"])
                        / f"slice_{i:03d}_{start_ms:08d}_{end_ms:08d}.edited.mp4"
                    )
                    await self._write_video_to_path(
                        edited_path, cast(str, edited_video.content)
                    )
                    slice_info.append(edited_path)
                    if state.slice_manifest and i < len(state.slice_manifest):
                        state.slice_manifest[i]["status"] = "completed"
                        state.slice_manifest[i]["edited_video"] = edited_path
                await self._persist_manifest(state)

            progress_store.set_phase(state.session_id, WorkflowPhase.CONCATENATING)
            new_video = await video_processor.concatenate_video(
                state.video_time_slice,
                state.video_input,
                session_id=state.session_id,
            )
            state.result = new_video

        state.complete = True
        progress_store.set_phase(state.session_id, WorkflowPhase.COMPLETED)
        await self._persist_manifest(state)
        return state

    def compile(self, checkpointer: Optional[Any] = None):
        if checkpointer is None:
            raise ValueError("compile 需要已初始化的 checkpointer")
        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState) -> Dict[str, Any]:
        if self.workflow is None:
            raise RuntimeError("请通过 async with SliceReplaceWorkflow() 使用")
        session_id = state.session_id or str(uuid.uuid4())
        state.session_id = session_id
        if progress_store.get(session_id) is None:
            progress_store.create(session_id)
        config = {"configurable": {"thread_id": session_id}}
        return await self.workflow.ainvoke(state, config)  # type: ignore

    async def resume(self, session_id: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        if self.workflow is None:
            raise RuntimeError("请通过 async with SliceReplaceWorkflow() 使用")
        config = {"configurable": {"thread_id": session_id}}
        return await self.workflow.ainvoke(Command(resume=decision), config)  # type: ignore


class VideoFlowWorkflow(SliceReplaceWorkflow):
    """兼容旧导出名称，等价于 SliceReplaceWorkflow。"""
