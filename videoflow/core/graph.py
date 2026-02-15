from typing import Dict, Any, Optional, List, TypedDict, Annotated, Union, cast
from langgraph.graph import StateGraph, END, MessagesState, START, END, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import tool
from videoflow.core.settings import (
    ModelSettings,
    runway_ait8,
    wanx_dashscpoe,
    gen4aleph_runway,
    qwen_dashscope,
)
from videoflow.utils import log
from pydantic import BaseModel, Field
from videoflow.utils.file_processor import write_file, read_file, get_file_path
from videoflow.utils.crawlers.crawler import crawler
from .chatmodel import gen4aleph
from ..feishu.utils import (
    get_tenant_access_token,
    download_image_fromfeishu,
    polling_reply_message,
    send_message,
)
import asyncio, json, os, httpx


class VideoEditState(BaseModel):
    """专门用于视频编辑的工作流状态"""

    messages: Annotated[list[AnyMessage], add_messages]
    image_url: str = Field(
        ..., description="用户上传的图片url或者飞书imagekey,或者本地图片"
    )
    video_keyword: str = Field(..., description="用户输入的视频关键词, 用于视频搜索")
    video_url: Annotated[
        Optional[str], "用户上传的视频url或者飞书videokey或者本地视频"
    ] = None
    provide_video_url: Annotated[
        Optional[List[str]], "从抖音上爬取的视频url列表，由用户选择一个下载"
    ] = None
    message_id: Annotated[
        Optional[str], "如果是通过飞书发送消息的，则需要message_id来返回消息"
    ] = None
    result: Optional[str] = None
    # model_config = {"extra": "allow"}


class VideoFlowWorkflow:
    """视频处理工作流框架"""

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow = self.compile()

    def _setup_workflow(self):
        """设置工作流节点和边"""

        # 定义工作流节点
        self.graph.add_node("download_image", self.download_image)
        self.graph.add_node("object_replace", self.object_replace)
        self.graph.add_node("search_video", self.search_video)
        self.graph.add_node("select_video", self.select_video)
        self.graph.add_edge(START, "download_image")
        self.graph.add_conditional_edges(
            "download_image",
            lambda state: "search_video" if not state.video_url else "object_replace",
        )
        self.graph.add_edge("search_video", "select_video")
        self.graph.add_edge("select_video", "object_replace")
        self.graph.add_edge("object_replace", END)

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """开始节点,初始化状态"""
        if state.video_url is None:
            raise ValueError("视频url不能为空")
        if state.message_id is None:
            raise ValueError("如果是通过飞书分享链接，则需要message_id来返回消息")
        res = await gen4aleph.ainvoke(
            [state.image_url],
            state.video_url,
        )
        if res.content is None:
            raise ValueError("视频编辑失败")
        state.result = cast(str, res.content)
        send_message_id = await asyncio.to_thread(
            send_message,
            state.result + "这是你编辑后的视频",
            "group",
            state.message_id,
        )
        await write_file("edited" + state.video_url, state.result)
        return state

    async def download_image(self, state: VideoEditState) -> VideoEditState:
        """下载用户上传的图片"""
        if state.image_url.startswith("img_v3") or state.image_url.endswith(".webp"):
            if state.message_id is None:
                raise ValueError("如果是通过飞书分享链接，则需要message_id来下载图片")
            else:
                res = await download_image_fromfeishu(state.message_id, state.image_url)
                success = await write_file(state.image_url + ".webp", res)
                if not success:
                    log.error(f"写入图片到本地失败, 图片key: {state.image_url}")
                    raise Exception(f"写入图片到本地失败, 图片key: {state.image_url}")
                log.info(f"写入图片到本地成功, 图片key: {state.image_url}")
                state.image_url = state.image_url + ".webp"
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

    def compile(self, checkpointer: Optional[MemorySaver] = None):
        if checkpointer is None:
            checkpointer = MemorySaver()

        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState, config) -> Dict[str, Any]:
        """调用工作流"""
        state_out: Union[VideoEditState, Command] = state

        async def process(state_in: Union[VideoEditState, Command]):
            return await self.workflow.ainvoke(state_in, config)

        while True:
            chunk = await process(state_out)
            if "__interrupt__" in chunk:
                interrupt_info = chunk["__interrupt__"][0].value
                if "provide_video_url" in interrupt_info:
                    if state.message_id is None:
                        raise ValueError(
                            "如果是通过飞书分享链接，则需要message_id来返回消息"
                        )
                    send_message_id = await asyncio.to_thread(
                        send_message,
                        "\n".join(interrupt_info["provide_video_url"])
                        + "请选择一个视频",
                        "group",
                        state.message_id,
                    )
                    temp = await polling_reply_message(send_message_id)
                    content = json.loads(temp)["text"]
                    content = "http" + content.split("http")[1]
                    success, video_id = await crawler.download_video(
                        content, file_name=state.message_id + ".mp4"
                    )
                    if not success:
                        log.error(f"下载视频失败, 视频url: {content}")
                        raise Exception(f"下载视频失败, 视频url: {content}")
                    state_out = Command(resume=state.message_id + ".mp4")
            elif chunk["result"] is not None:
                break
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
