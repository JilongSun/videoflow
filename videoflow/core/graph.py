from typing import Dict, Any, Optional, List, Annotated, Union, cast
from langgraph.graph import StateGraph, END, START, add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.output_parsers import StrOutputParser
from videoflow.utils import log
from pydantic import BaseModel, Field
from videoflow.utils.file_processor import (
    write_file,
    read_file,
    get_file_path,
    video_processor,
)
from videoflow.utils.crawlers.crawler import crawler
from .chatmodel import gen4aleph, qwen3vl_dashchat
import asyncio, json, uuid, httpx


class VideoEditState(BaseModel):
    """
    专门用于视频编辑的工作流状态
    用户在启动工作流时，必须要提供抖音搜索关键词，以及用来替换的图片
    """

    messages: Annotated[list[AnyMessage], add_messages]
    image_url: str = Field(
        ...,
        description="用户上传的图片url（HTTP）或本地图片文件名",
    )
    video_keyword: str = Field(
        ...,
        description="用户输入的视频关键词, 用于视频搜索",
    )
    session_id: str = Field(
        default="",
        description="工作流会话ID，用于标识和恢复工作流",
    )
    video_url: Annotated[
        Optional[str],
        "用户上传的视频url或者飞书videokey或者本地视频",
    ] = None
    provide_video_url: Annotated[
        Optional[List[str]], "从抖音上爬取的视频url列表，由用户选择一个下载"
    ] = None
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
        self.graph.add_node("search_video", self.search_video)
        self.graph.add_node("select_video", self.select_video)
        self.graph.add_node("split_video", self.split_video)
        self.graph.add_edge(START, "download_image")
        self.graph.add_conditional_edges(
            "download_image",
            lambda state: "search_video" if not state.video_url else "split_video",
        )
        self.graph.add_edge("search_video", "select_video")
        self.graph.add_edge("select_video", "split_video")
        self.graph.add_edge("split_video", "object_replace")
        self.graph.add_edge("object_replace", END)

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """AI 视频编辑：替换视频中的物体"""
        if state.video_url is None:
            raise ValueError("视频url不能为空")
        if not state.video_time_slice:
            log.info("视频无需分割，直接替换对象,开始编辑视频,视频url: " + state.video_url)
            res = await gen4aleph.ainvoke(
                [state.image_url],
                state.video_url,
            )
            if res.content is None:
                raise ValueError("视频编辑失败")
            state.result = cast(str, res.content)
            await write_file("edited_" + state.video_url, state.result)

        elif state.video_time_slice:
            log.info("视频需要分割，替换对象,开始编辑视频,视频url: " + state.video_url)
            task_list = [
                asyncio.create_task(gen4aleph.ainvoke([state.image_url], video_url[1]))
                for video_url in state.video_time_slice
            ]
            edited_videos = await asyncio.gather(*task_list)
            for edited_video, total_list in zip(edited_videos, state.video_time_slice):
                edited_name = "edited_" + total_list[1]
                if edited_video.content is None:
                    raise ValueError(f"视频编辑失败, 视频url: {total_list[1]}")
                content = cast(str, edited_video.content)
                await write_file(edited_name, content)
                total_list.append(edited_name)
            new_video = await video_processor.concatenate_video(
                state.video_time_slice, state.video_url
            )
            state.result = new_video
        state.complete = True
        return state

    async def download_image(self, state: VideoEditState) -> VideoEditState:
        """下载用户上传的图片，支持 HTTP URL 或本地文件"""
        if state.image_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                response = await client.get(state.image_url, timeout=300)
                response.raise_for_status()
            # 从 URL 提取文件名
            url_path = state.image_url.split("?")[0].split("/")[-1]
            file_name = url_path if "." in url_path else url_path + ".webp"
            success = await write_file(file_name, response.content)
            if not success:
                raise Exception(f"写入图片到本地失败: {file_name}")
            log.info(f"下载图片成功: {file_name}")
            state.image_url = file_name
        else:
            log.info(f"使用本地图片: {state.image_url}")
        return state

    async def search_video(self, state: VideoEditState) -> VideoEditState:
        """根据用户输入的视频关键词, 从视频库中选择视频"""
        res = await crawler.search_video(state.video_keyword)
        if res is None:
            log.error(f"从抖音上爬取视频失败, 视频关键词: {state.video_keyword}")
            raise Exception(f"从抖音上爬取视频失败, 视频关键词: {state.video_keyword}")
        else:
            state.provide_video_url = res
        return state

    async def select_video(self, state: VideoEditState) -> VideoEditState:
        """根据用户输入的视频关键词, 从视频库中选择视频"""
        url = interrupt({"provide_video_url": state.provide_video_url})
        state.video_url = url
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """根据用户输入的时间范围, 分割视频"""
        if state.video_url is None:
            raise ValueError("视频url不能为空")
        if isinstance(state.video_url, list):
            raise ValueError("一次只能处理一个视频")
        sec = await video_processor.detect_video_len(state.video_url)
        if sec <= 5:
            log.info(f"视频时长小于5秒，无需分割，视频url: {state.video_url}")
        else:
            log.info(f"视频时长大于5秒，需要分割，视频url: {state.video_url}")
            chain = qwen3vl_dashchat | self.parser
            duration_seconds_json = await chain.ainvoke(
                {"video": state.video_url, "object": state.video_keyword}  # type: ignore
            )
            duration_seconds = json.loads(duration_seconds_json)
            log.info(
                f"视频时长为{sec}秒，需要分割为{duration_seconds}秒,视频url: {state.video_url}"
            )
            state.video_time_slice = duration_seconds
            temp_list = []
            for item in duration_seconds:
                start = item[0]
                end = item[1]
                new_video = await video_processor.split_video(
                    state.video_url, start=start, end=end
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
        当遇到 select_video 中断时，返回候选列表供调用方处理。
        调用方选择后通过 resume() 恢复工作流。
        """
        session_id = state.session_id or str(uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        state_out: Union[VideoEditState, Command] = state

        async def process(state_in: Union[VideoEditState, Command]):
            return await self.workflow.ainvoke(state_in, config)  # type: ignore

        chunk = await process(state_out)
        if "__interrupt__" in chunk:
            interrupt_info = chunk["__interrupt__"][0].value
            if "provide_video_url" in interrupt_info:
                return {
                    "status": "pending_selection",
                    "session_id": session_id,
                    "candidates": interrupt_info["provide_video_url"],
                    "complete": None,
                }
        return chunk

    async def resume(self, session_id: str, selected_video_file: str) -> Dict[str, Any]:
        """
        恢复中断的工作流，传入用户选择的视频文件名。
        """
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        state_out = Command(resume=selected_video_file)
        chunk = await self.workflow.ainvoke(state_out, config)  # type: ignore
        return chunk


class WorkFlowManager:
    def __init__(self):
        self._workflow = []

    def __call__(self):
        return self._workflow

    def get_num(self):
        """
        返回工作流数量
        """
        return len(self._workflow)

    def add_workflow(self, workflow: VideoFlowWorkflow):
        """
        添加工作流
        """
        self._workflow.append(workflow)


video_flow_workflow = VideoFlowWorkflow()
workflow_manager = WorkFlowManager()
workflow_manager.add_workflow(video_flow_workflow)
