"""分片级进度追踪模块（内存存储）"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from videoflow.utils import log


class SliceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowPhase(str, Enum):
    PREPARING = "preparing"
    SPLITTING = "splitting"
    PREVIEW = "preview"
    WAITING_APPROVAL = "waiting_approval"
    BATCH_PROCESSING = "batch_processing"
    CONCATENATING = "concatenating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SliceProgress(BaseModel):
    index: int
    time_range: List[int]
    status: SliceStatus = SliceStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class WorkflowProgress(BaseModel):
    session_id: str
    total_slices: int = 0
    phase: WorkflowPhase = WorkflowPhase.PREPARING
    slices: List[SliceProgress] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: _now())
    updated_at: str = Field(default_factory=lambda: _now())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProgressStore:
    """内存级进度存储，按 session_id 索引"""

    def __init__(self):
        self._store: Dict[str, WorkflowProgress] = {}

    def create(self, session_id: str) -> WorkflowProgress:
        progress = WorkflowProgress(session_id=session_id)
        self._store[session_id] = progress
        log.info(f"[progress] 创建进度: {session_id}")
        return progress

    def get(self, session_id: str) -> Optional[WorkflowProgress]:
        return self._store.get(session_id)

    def set_phase(self, session_id: str, phase: WorkflowPhase) -> None:
        p = self._store.get(session_id)
        if not p:
            return
        p.phase = phase
        p.updated_at = _now()
        log.info(f"[progress] {session_id} phase → {phase.value}")

    def init_slices(self, session_id: str, time_ranges: List[List[int]]) -> None:
        p = self._store.get(session_id)
        if not p:
            return
        p.total_slices = len(time_ranges)
        p.slices = [
            SliceProgress(index=i, time_range=tr)
            for i, tr in enumerate(time_ranges)
        ]
        p.updated_at = _now()

    def update_slice(
        self,
        session_id: str,
        index: int,
        status: SliceStatus,
        error: Optional[str] = None,
    ) -> None:
        p = self._store.get(session_id)
        if not p or index >= len(p.slices):
            return
        s = p.slices[index]
        s.status = status
        if status == SliceStatus.PROCESSING and not s.started_at:
            s.started_at = _now()
        if status in (SliceStatus.COMPLETED, SliceStatus.FAILED):
            s.completed_at = _now()
        if error:
            s.error = error
        p.updated_at = _now()

    def get_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """返回给 MCP 调用方的摘要"""
        p = self._store.get(session_id)
        if not p:
            return None
        completed = sum(1 for s in p.slices if s.status == SliceStatus.COMPLETED)
        failed = sum(1 for s in p.slices if s.status == SliceStatus.FAILED)
        processing = sum(1 for s in p.slices if s.status == SliceStatus.PROCESSING)
        total = p.total_slices or 1  # 避免除零（无分片时视为 1 片）
        percent = round(completed / total * 100)
        return {
            "session_id": p.session_id,
            "phase": p.phase.value,
            "total_slices": p.total_slices,
            "completed": completed,
            "processing": processing,
            "failed": failed,
            "percent": percent,
            "slices": [s.model_dump() for s in p.slices],
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }


progress_store = ProgressStore()
