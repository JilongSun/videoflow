from typing import Any, Dict, List, Optional, Annotated
from pydantic import BaseModel, Field


class VideoEditState(BaseModel):
    """共享状态定义，供不同工作流复用。"""

    image_input: str = Field(..., description="用户上传图片，本地路径或 URL")
    video_input: Annotated[str, "本地视频路径"]
    prompt: str = Field(..., description="编辑提示词")
    video_keyword: str = Field(..., description="视频关键词")
    session_id: str = Field(default="", description="会话 ID")
    model_type: str = Field(
        default="wan2.7-videoedit",
        description="编辑模型类型，支持 wan2.7-videoedit/runway-gen4aleph",
    )
    model_options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="模型参数覆盖，如 resolution/audio_setting 等",
    )
    mask_image_input: Optional[str] = Field(
        default=None,
        description="可选 mask 输入（为未来支持 wanx2.1-vace 预留）",
    )

    video_time_slice: Annotated[
        Optional[List[List]],
        "[[[start_sec, end_sec], sliced_video, edited_sliced_video]]",
    ] = None
    preview_slice: Optional[str] = None
    work_dirs: Optional[Dict[str, str]] = None
    manifest_path: Optional[str] = None
    slice_manifest: Optional[List[Dict[str, Any]]] = None

    result: Optional[str] = None
    complete: Optional[bool] = None
