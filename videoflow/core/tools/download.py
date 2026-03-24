from typing import Optional, Tuple
from videoflow.utils.file_processor import write_file, get_file_path
from videoflow.utils.crawlers.crawler import crawler
from videoflow.utils import log
import httpx, aiofiles


async def download_video(
    video_url: str, file_name: Optional[str] = None
) -> dict:
    """下载视频到本地

    Args:
        video_url: 视频分享链接（抖音等）
        file_name: 保存的文件名，不提供则自动生成

    Returns:
        {"success": bool, "file_name": str | None}
    """
    log.info(f"download_video: url={video_url}, file_name={file_name}")
    success, video_id = await crawler.download_video(
        video_url, file_name=file_name
    )
    if not success:
        log.error(f"download_video: 下载失败, url={video_url}")
        return {"success": False, "file_name": None}
    log.info(f"download_video: 下载成功, file={video_id}")
    return {"success": True, "file_name": video_id}


async def download_image(image_url: str, file_name: Optional[str] = None) -> dict:
    """下载图片到本地，支持 HTTP URL

    Args:
        image_url: 图片的 HTTP URL
        file_name: 保存的文件名，不提供则从 URL 推断

    Returns:
        {"success": bool, "file_name": str | None}
    """
    log.info(f"download_image: url={image_url}")
    if not image_url.startswith(("http://", "https://")):
        # 本地路径，直接返回
        return {"success": True, "file_name": image_url}

    if file_name is None:
        # 从 URL 推断文件名
        url_path = image_url.split("?")[0].split("/")[-1]
        if "." in url_path:
            file_name = url_path
        else:
            file_name = url_path + ".webp"

    async with httpx.AsyncClient() as client:
        response = await client.get(image_url, timeout=300)
        response.raise_for_status()

    success = await write_file(file_name, response.content)
    if not success:
        log.error(f"download_image: 写入失败, file_name={file_name}")
        return {"success": False, "file_name": None}

    log.info(f"download_image: 下载成功, file={file_name}")
    return {"success": True, "file_name": file_name}
