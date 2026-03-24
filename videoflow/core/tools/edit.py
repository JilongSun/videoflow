from typing import List, Optional
from videoflow.utils.file_processor import write_file, get_file_path, video_processor
from videoflow.core.chatmodel import gen4aleph
from videoflow.utils import log
from typing import cast
import asyncio


async def edit_video(
    video_path: str, image_path: str, prompt: Optional[str] = None
) -> dict:
    """使用 Runway Gen4Aleph AI 编辑单个视频片段（≤5s）

    Args:
        video_path: 视频文件名
        image_path: 参考图片文件名
        prompt: 编辑提示词（可选）

    Returns:
        {"success": bool, "edited_file": str | None}
    """
    log.info(f"edit_video: video={video_path}, image={image_path}")
    res = await gen4aleph.ainvoke([image_path], video_path)
    if res.content is None:
        log.error(f"edit_video: 编辑失败")
        return {"success": False, "edited_file": None}

    edited_name = "edited_" + video_path
    content = cast(str, res.content)
    await write_file(edited_name, content)
    log.info(f"edit_video: 编辑完成, output={edited_name}")
    return {"success": True, "edited_file": edited_name}


async def split_video(video_path: str, time_slices: List[List[int]]) -> dict:
    """按时间段分割视频

    Args:
        video_path: 视频文件名
        time_slices: 时间段列表 [[start_sec, end_sec], ...]

    Returns:
        {"slices": [{"start": int, "end": int, "file": str}, ...]}
    """
    log.info(f"split_video: video={video_path}, slices={time_slices}")
    result_slices = []
    for item in time_slices:
        start, end = item[0], item[1]
        sliced_file = await video_processor.split_video(
            video_path, start=start, end=end
        )
        result_slices.append({
            "start": start,
            "end": end,
            "file": sliced_file,
        })
    log.info(f"split_video: 分割完成, {len(result_slices)} 个片段")
    return {"slices": result_slices}


async def concatenate_video(video_list: List[dict], original_video: str) -> dict:
    """拼接多段编辑后的视频

    Args:
        video_list: [{"start": int, "end": int, "sliced_file": str, "edited_file": str}, ...]
        original_video: 原始视频文件名

    Returns:
        {"success": bool, "output_file": str | None}
    """
    log.info(f"concatenate_video: {len(video_list)} 段, original={original_video}")
    # 转换为 graph.py 原来的格式: [[[start, end], sliced, edited], ...]
    formatted = [
        [[item["start"], item["end"]], item["sliced_file"], item["edited_file"]]
        for item in video_list
    ]
    result = await video_processor.concatenate_video(formatted, original_video)
    log.info(f"concatenate_video: 拼接完成, output={result}")
    return {"success": True, "output_file": result}
