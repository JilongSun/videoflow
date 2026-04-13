from typing import Any, Optional
from langgraph.graph import StateGraph, START, END

from .state import VideoEditState


class SubjectMaskReplaceWorkflow:
    """特征：主体抠图 + 局部替换 + 拼接。"""

    name = "subject_mask_replace"

    def __init__(self):
        self.graph = StateGraph(VideoEditState)
        self._setup()

    def _setup(self) -> None:
        # 最小可讨论节点：抠图 + 调用模型
        self.graph.add_node("prepare_media", self.prepare_media)
        self.graph.add_node("split_video", self.split_video)
        self.graph.add_node("mask_subject", self.mask_subject)
        self.graph.add_node("replace_masked", self.replace_masked)
        self.graph.add_node("concat_video", self.concat_video)

        self.graph.add_edge(START, "prepare_media")
        self.graph.add_edge("prepare_media", "split_video")
        self.graph.add_edge("split_video", "mask_subject")
        self.graph.add_edge("mask_subject", "replace_masked")
        self.graph.add_edge("replace_masked", "concat_video")
        self.graph.add_edge("concat_video", END)

    async def prepare_media(self, state: VideoEditState) -> VideoEditState:
        return state

    async def split_video(self, state: VideoEditState) -> VideoEditState:
        return state

    async def mask_subject(self, state: VideoEditState) -> VideoEditState:
        return state

    async def replace_masked(self, state: VideoEditState) -> VideoEditState:
        return state

    async def concat_video(self, state: VideoEditState) -> VideoEditState:
        state.complete = True
        return state

    def compile(self, checkpointer: Optional[Any] = None):
        if checkpointer is None:
            raise ValueError("checkpointer is required")
        return self.graph.compile(checkpointer=checkpointer)
