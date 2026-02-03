from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class Author(BaseModel):
    nickname: str = Field(..., description="作者昵称")
    model_config = {"extra": "ignore"}


class Music(BaseModel):
    music_id: str = Field(..., description="音乐字符串ID")
    model_config = {"extra": "ignore"}


class Statistics(BaseModel):
    model_config = {"extra": "ignore"}


class VideoPlayAddr(BaseModel):
    uri: str = Field(..., description="视频播放地址")
    model_config = {"extra": "ignore"}


class Video(BaseModel):
    play_addr: VideoPlayAddr = Field(..., description="视频播放地址信息")
    model_config = {"extra": "ignore"}


class AwemeInfo(BaseModel):
    aweme_id: str = Field(..., description="aweme_id")
    desc: str = Field(..., description="视频描述,相关标签")
    author: Author = Field(..., description="视频作者信息")
    music: Music = Field(..., description="视频音乐信息")
    video: Video = Field(..., description="视频信息")
    share_url: str = Field(..., description="视频分享链接")
    statistics: Statistics = Field(..., description="视频统计信息")
    model_config = {"extra": "ignore"}


class Data2(BaseModel):
    type: int = Field(..., description="编号代表图像或者视频")
    aweme_info: List[AwemeInfo] = Field(..., description="视频信息")
    model_config = {"extra": "ignore"}


class Data1(BaseModel):
    data: List[Data2] = Field(..., description="返回核心数据")
    model_config = {"extra": "ignore"}


class TkhubInfo(BaseModel):
    code: int = Field(..., description="状态码")
    request_id: str = Field(..., description="请求ID")
    message: str = Field(..., description="返回消息")
    message_zh: str = Field(..., description="返回消息")
    time: Optional[str] = None
    time_stamp: Optional[int] = None
    cache_url: Optional[str] = None
    router: str = Field(..., description="申请的接口端点")
    params: Optional[Dict[str, Any]] = None
    data: Optional[Data1] = None

    model_config = {"extra": "ignore"}
