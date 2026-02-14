from typing import Dict, Any, Optional, List, TypedDict, Annotated
from langgraph.graph import StateGraph, END, MessagesState, START, END, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
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
from ..feishu.utils import get_tenant_access_token, download_image_fromfeishu
import asyncio, json, os, httpx


class VideoEditState(BaseModel):
    """专门用于视频编辑的工作流状态"""

    messages: Annotated[list[AnyMessage], add_messages]
    image_url: str = Field(
        ..., description="用户上传的图片url或者飞书imagekey,或者本地图片"
    )
    video_url: Optional[str] = Field(
        None, description="用户上传的视频url或者飞书videokey或者本地图片"
    )
    message_id: Annotated[
        Optional[str], "如果是通过飞书发送消息的，则需要message_id来返回消息"
    ] = None
    result: Optional[Dict[str, Any]] = None


class VideoFlowWorkflow:
    """视频处理工作流框架"""

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow = self.graph.compile()

    def _setup_workflow(self):
        """设置工作流节点和边"""

        # 定义工作流节点
        self.graph.add_node("download_inage", self.download_inage)
        self.graph.add_node("object_replace", self.object_replace)
        self.graph.add_edge(START, "download_inage")
        self.graph.add_edge("download_inage", "object_replace")
        self.graph.add_edge("object_replace", END)

    async def object_replace(self, state: VideoEditState) -> VideoEditState:
        """开始节点,初始化状态"""
        print("aaaaaaaaaaaaaaaaaa")
        return state

    async def download_inage(self, state: VideoEditState) -> VideoEditState:
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

    def compile(self, checkpointer: Optional[MemorySaver] = None):
        """编译工作流,暂时先不添加记忆功能"""
        # if checkpointer is None:
        #     checkpointer = MemorySaver()

        return self.graph.compile(checkpointer=checkpointer)

    async def ainvoke(self, state: VideoEditState) -> Dict[str, Any]:
        """调用工作流"""
        return await self.workflow.ainvoke(state)


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
