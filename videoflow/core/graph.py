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
    current_step: str
    video_url: Optional[str]
    video_task_id: Optional[str]
    video_status: Optional[str]
    model_config: Optional[ModelSettings]
    error: Optional[str]
    result: Optional[Dict[str, Any]]


class VideoFlowWorkflow:
    """视频处理工作流框架"""

    def __init__(self):
        self.workflow = StateGraph(MessagesState)
        self._setup_workflow()

    def _setup_workflow(self):
        """设置工作流节点和边"""

        # 定义工作流节点
        self.workflow.add_node("start", self._start_node)
        self.workflow.add_edge(START, "start")

    def _start_node(self, state: VideoEditState) -> VideoEditState:
        """开始节点,初始化状态"""
        return state

    def compile(self, checkpointer: Optional[MemorySaver] = None):
        """编译工作流,暂时先不添加记忆功能"""
        # if checkpointer is None:
        #     checkpointer = MemorySaver()

        return self.workflow.compile(checkpointer=checkpointer)


class VideoFlowRunner:
    """工作流运行器"""

    def __init__(self):
        self.workflow = VideoFlowWorkflow()
        self.app = self.workflow.compile()

    async def run(
        self, user_input: str, thread_id: Optional[str] = None
    ) -> Dict[str, Any]: ...


if __name__ == "__main__":
    ...
