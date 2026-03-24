from typing import List
from videoflow.utils.file_processor import get_file_path, video_processor
from videoflow.core.chatmodel import qwen3vl_dashchat
from videoflow.utils import log
from langchain_core.output_parsers import StrOutputParser
import json


async def analyze_video(video_path: str, object_keyword: str) -> dict:
    """使用 Qwen3-VL 分析视频中目标物体出现的时间段

    Args:
        video_path: 视频文件名（outputs/videos/ 下）
        object_keyword: 要检测的目标物体关键词

    Returns:
        {"duration_seconds": int, "time_slices": [[start, end], ...]}
    """
    log.info(f"analyze_video: video={video_path}, object={object_keyword}")

    duration = await video_processor.detect_video_len(video_path)

    if duration <= 5:
        log.info(f"analyze_video: 视频时长 {duration}s ≤ 5s，无需分割")
        return {"duration_seconds": duration, "time_slices": []}

    parser = StrOutputParser()
    chain = qwen3vl_dashchat | parser
    result_json = await chain.ainvoke(
        {"video": video_path, "object": object_keyword}  # type: ignore
    )
    time_slices = json.loads(result_json)
    log.info(f"analyze_video: 检测到时间片段 {time_slices}")

    return {"duration_seconds": duration, "time_slices": time_slices}
