from typing import Dict, Any, Optional, List, TypedDict
from langgraph.graph import StateGraph, END, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from langchain_core.tools import tool
from videoflow.core.settings import (
    ModelSettings,
    runway_ait8,
    wanx_dashscpoe,
    gen4aleph_runway,
    qwen_dashscope,
)
from videoflow.utils import log
import asyncio
import json


class VideoEditState(MessagesState):
    """专门用于视频编辑的工作流状态"""

    user_input: str
    video_url: str
    image_url: str
    result: Optional[Dict[str, Any]]


class VideoFlowWorkflow:
    """视频处理工作流框架"""

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup_workflow()
        self.workflow = self.graph.compile()

    def _setup_workflow(self):
        """设置工作流节点和边"""

        # 定义工作流节点
        self.graph.add_node("object_replace", self.object_replace)
        self.graph.add_node("note", self.note)
        self.graph.add_edge(START, "start")
        self.graph.add_edge("object_replace", "note")
        self.graph.add_edge("note", END)

    def object_replace(self, state: VideoEditState) -> VideoEditState:
        """开始节点,初始化状态"""
        return state

    def note(self, state: VideoEditState) -> VideoEditState:
        return state

    def compile(self, checkpointer: Optional[MemorySaver] = None):
        """编译工作流,暂时先不添加记忆功能"""
        # if checkpointer is None:
        #     checkpointer = MemorySaver()

        return self.graph.compile(checkpointer=checkpointer)
    
    async def _call__(self, state: VideoEditState) -> Dict[str, Any]:
        """调用工作流"""
        return await self.workflow.ainvoke(state)


class WorkFlowManager:
    def __init__(self):
        self._workflow = []

    def __call__(self):
        return self._workflow

    def __len__(self):
        return len(self._workflow)


workflow_manager = WorkFlowManager()
