from typing import Dict, Any, Optional, List, TypedDict, Annotated, Union, cast, Tuple
from mcp.types import TextContent
from langgraph.graph import StateGraph, END, MessagesState, START, END, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import tool
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
from videoflow.mcps.client import MCPServerStreamableHttp
from .chatmodel import gen4aleph, qwen3vl_dashchat
from ..feishu.utils import (
    get_tenant_access_token,
    download_image_fromfeishu,
    polling_reply_message,
    send_message,
)
import asyncio, json, os, httpx, uuid


class VideoEditState(BaseModel):
    """
    专门用于视频编辑的工作流状态
    用户在启动工作流时，必须要提供抖音搜索关键词，以及用来替换的图片
    """

    messages: Annotated[list[AnyMessage], add_messages]
    image_url: str = Field(
        ...,
        description="用户上传的图片url或者飞书imagekey,或者本地图片，当用户是通过飞书调用时，只通过聊天框发送图片",
    )
    video_keyword: str = Field(
        ...,
        description="用户输入的视频关键词, 用于视频搜索，用户在调用大模型时要提供搜索关键字",
    )
    message_id: str = Field(
        ...,
        description="如果是通过飞书发送消息的，则需要message_id来返回消息",
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
        self.graph.add_node("update_redbook", self.update_redbook)
        self.graph.add_edge(START, "download_image")
        self.graph.add_conditional_edges(
            "download_image",
            lambda state: "search_video" if not state.video_url else "split_video",
        )
        self.graph.add_edge("search_video", "select_video")
        self.graph.add_edge("select_video", "split_video")
        self.graph.add_edge("split_video", "object_replace")
        self.graph.add_edge("object_replace", "update_redbook")
        self.graph.add_edge("update_redbook", END)

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """开始节点,初始化状态"""
        if state.video_url is None:
            raise ValueError("视频url不能为空")
        if state.message_id is None:
            raise ValueError("如果是通过飞书分享链接，则需要message_id来返回消息")
        if not state.video_time_slice:
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

        elif state.video_time_slice:
            task_list = [
                asyncio.create_task(gen4aleph.ainvoke([state.image_url], video_url[1]))
                for video_url in state.video_time_slice
            ]
            edited_videos = await asyncio.gather(*task_list)
            for edited_video, total_list in zip(edited_videos, state.video_time_slice):
                edited_name = "edited" + total_list[1]
                if edited_video.content is None:
                    raise ValueError(f"视频编辑失败, 视频url: {total_list[1]}")
                content = cast(str, edited_video.content)
                await write_file(edited_name, content)
                total_list.append(edited_name)
            new_video = await video_processor.concatenate_video(
                state.video_time_slice, state.video_url
            )
            state.result = new_video
            send_message_id = await asyncio.to_thread(
                send_message,
                state.result + "这是你编辑后的视频,在电脑本地",
                "group",
                state.message_id,
            )
        return state

    async def update_redbook(self, state: VideoEditState) -> VideoEditState:
        """更新用户的小红书"""
        if state.message_id is None:
            raise ValueError("如果是通过飞书分享链接，则需要message_id来更新小红书")
        if state.result is None:
            raise ValueError("上传小红书时结果不能为空")
        async with MCPServerStreamableHttp(
            params={"url": "http://127.0.0.1:18060/mcp", "timeout": 9999},
            name="xiaohongshu-mcp",
        ) as mcp_server:
            temp_a = await mcp_server.call_tool("check_login_status", None)
            temp_b = cast(TextContent, temp_a.content[0])
            text = cast(str, temp_b.text)
            if not "已登录" in text:
                log.error("小红书登录失败, 请先登录小红书")
                send_message_id = await asyncio.to_thread(
                    send_message,
                    state.result + "小红书未登录，请手动上传",
                    "group",
                    state.message_id,
                )
            else:
                log.info("小红书已登录")
                args = {
                    "content": state.result,
                    "title": "视频编辑",
                    "video": await get_file_path(state.result),
                }
                temp_a = await mcp_server.call_tool("publish_with_video", args)
                temp_b = cast(TextContent, temp_a.content[0])
                text = cast(str, temp_b.text)
                log.info(f"小红书上传成功, 视频id: {text}")
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

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        """根据用户输入的时间范围, 分割视频"""
        if state.video_url is None:
            raise ValueError("视频url不能为空")
        if state.message_id is None:
            raise ValueError("如果是通过飞书分享链接，则需要message_id来返回消息")
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
        这是视频编辑工作流
        """
        config = {
            "configurable": {
                "thread_id": state.message_id if state.message_id else str(uuid.uuid4())
            }
        }
        state_out: Union[VideoEditState, Command] = state

        async def process(state_in: Union[VideoEditState, Command]):
            return await self.workflow.ainvoke(state_in, config)  # type: ignore

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
            elif chunk["complete"] is not None:
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
