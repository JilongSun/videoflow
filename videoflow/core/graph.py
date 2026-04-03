from typing import Dict, Any, Optional, List, Annotated, cast
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.output_parsers import StrOutputParser
from videoflow.utils import log
from pydantic import BaseModel, Field
from videoflow.utils.file_processor import (
    write_file,
    video_processor,
)
from .chatmodel import gen4aleph, qwen3vl_dashchat
import asyncio, json, uuid, httpx


class VideoEditState(BaseModel):
    """
    专门用于视频编辑的工作流状态
    用户在启动工作流时，必须要提供抖音搜索关键词，以及用来替换的图片
    """

    image_input: str = Field(
        ...,
        description="用户上传的图片url (HTTP)或本地图片路径",
    )
    video_keyword: str = Field(
        ...,
        description="用户输入的视频关键词, 用于素材检索或视频分析",
    )
    session_id: str = Field(
        default="",
        description="工作流会话ID，用于标识一次执行",
    )
    video_input: Annotated[str, "本地视频文件名或本地视频路径"]
    video_time_slice: Annotated[
        Optional[List[List]],
        "[[[start_sec,end_sec],sliced-video,edited-sliced-video]]",
    ] = None
    result: Optional[str] = None
    complete: Annotated[
        Optional[bool],
        "是否完成视频编辑工作流",
    ] = None
    # model_config = {"extra": "allow"}


class VideoFlowWorkflow:
    """视频处理工作流框架"""

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow = self.compile()
        self.parser = StrOutputParser()

    def _setup_workflow(self):
        """设置工作流节点和边"""

        # 定义工作流节点
        self.graph.add_node("download_image", self.download_image)
        self.graph.add_node("object_replace", self.object_replace)
        self.graph.add_node("split_video", self.split_video)
        self.graph.add_edge(START, "download_image")
        self.graph.add_edge("download_image", "split_video")
        self.graph.add_edge("split_video", "object_replace")
        self.graph.add_edge("object_replace", END)

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """AI 视频编辑：替换视频中的物体"""
        if not state.video_time_slice:
            log.info(
                "视频无需分割，直接替换对象,开始编辑视频,本地视频: "
                + state.video_input
            )
            res = await gen4aleph.ainvoke(
                [state.image_input],
                state.video_input,
            )
            if res.content is None:
                raise ValueError("视频编辑失败")
            state.result = cast(str, res.content)
            await write_file("edited_" + state.video_input, state.result)

        elif state.video_time_slice:
            log.info("视频需要分割，替换对象,开始编辑视频,本地视频: " + state.video_input)
            task_list = [
                asyncio.create_task(gen4aleph.ainvoke([state.image_input], video_input[1]))
                for video_input in state.video_time_slice
            ]
            edited_videos = await asyncio.gather(*task_list)
            for edited_video, total_list in zip(edited_videos, state.video_time_slice):
                edited_name = "edited_" + total_list[1]
                if edited_video.content is None:
                    raise ValueError(f"视频编辑失败, 视频文件: {total_list[1]}")
                content = cast(str, edited_video.content)
                await write_file(edited_name, content)
                total_list.append(edited_name)
            new_video = await video_processor.concatenate_video(
                state.video_time_slice, state.video_input
            )
            state.result = new_video
        state.complete = True
        return state

    async def download_image(self, state: VideoEditState) -> VideoEditState:
        """下载用户上传的图片，支持 HTTP URL 或本地文件"""
        if state.image_input.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                response = await client.get(state.image_input, timeout=300)
                response.raise_for_status()
            # 从 URL 提取文件名
            url_path = state.image_input.split("?")[0].split("/")[-1]
            file_name = url_path if "." in url_path else url_path + ".webp"
            success = await write_file(file_name, response.content)
            if not success:
                raise Exception(f"写入图片到本地失败: {file_name}")
            log.info(f"下载图片成功: {file_name}")
            state.image_input = file_name
        else:
            log.info(f"使用本地图片: {state.image_input}")
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """根据本地视频时长进行分割"""
        if state.video_input.startswith(("http://", "https://")):
            raise ValueError("video_input 必须是本地视频文件，请先下载到本地后再启动工作流")
        sec = await video_processor.detect_video_len(state.video_input)
        if sec <= 5:
            log.info(f"视频时长小于5秒，无需分割，本地视频: {state.video_input}")
        else:
            log.info(f"视频时长大于5秒，需要分割，本地视频: {state.video_input}")
            chain = qwen3vl_dashchat | self.parser
            duration_seconds_json = await chain.ainvoke(
                {"video": state.video_input, "object": state.video_keyword}  # type: ignore
            )
            duration_seconds = json.loads(duration_seconds_json)
            log.info(
                f"视频时长为{sec}秒，需要分割为{duration_seconds}秒,本地视频: {state.video_input}"
            )
            state.video_time_slice = duration_seconds
            temp_list = []
            for item in duration_seconds:
                start = item[0]
                end = item[1]
                new_video = await video_processor.split_video(
                    state.video_input, start=start, end=end
                )
                temp_list.append([item, new_video])
            state.video_time_slice = temp_list
        return state

    def compile(self, checkpointer: Optional[MemorySaver] = None):
        if checkpointer is None:
            checkpointer = MemorySaver()

        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState) -> Dict[str, Any]:
        """
        执行视频编辑工作流。
        """
        session_id = state.session_id or str(uuid.uuid4())
        state.session_id = session_id
        config = {"configurable": {"thread_id": session_id}}
        return await self.workflow.ainvoke(state, config)  # type: ignore


video_flow_workflow = VideoFlowWorkflow()
