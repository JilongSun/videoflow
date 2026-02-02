from .base import file_processor
from pathlib import Path
from typing import Optional, cast, Tuple, Annotated, Union
from app.models.router_model import file_content
from videoflow.utils.logger_config import log
from downloader.apis.api_client import MainAPIClient
from downloader.core.downloader import VideoDownloader
import os, aiofiles, httpx, base64, asyncio

__all__ = ["video_processor"]

current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class VideoDownloaderTab:
    """
    一个专门通过分享链接从douyin下载视频的处理类
    """

    def __init__(
        self,
    ):
        if api_key := os.getenv("TIKHUB_API_KEY", None):
            self.api_key = "Bearer " + api_key.strip()
        else:
            raise ValueError("TIKHUB_API_KEY is not set")
        self.base_url = "https://api.tikhub.io"
        self.client = MainAPIClient(
            api_key=self.api_key,
            base_url=self.base_url,
            proxy=None,
        )

    async def _download_video(
        self, url: str, download_path: str
    ) -> Tuple[
        Annotated[bool, "是否成功"], Annotated[Union[str, None], "视频ID, 失败时为None"]
    ]:
        log.info(f"Getting video info for URL: {url}")
        video_info = await asyncio.to_thread(self.client.get_data, url, clean_data=True)
        log.info(f"Received video info: {video_info}")
        if not isinstance(video_info, dict):
            log.error("Failed to retrieve video info")
            return False, None
        if not video_info.get("video_urls"):
            log.error("No video URLs found in response")
            return False, None
        # 确保设置正确的media_type
        if "media_type" not in video_info:
            video_info["media_type"] = "video"  # 在Video Tab中，默认为视频类型
        log.info("Preparing to download video")
        downloader = VideoDownloader(
            download_path=download_path,
            use_description=False,
            skip_existing=True,
            max_workers=4,
        )
        result = await asyncio.to_thread(downloader.main_downloader, video_info)
        if result["success"] and result["files"]:
            log.info(f"Download successful. Files: {result['files']}")
            return True, result["files"][0]
        else:
            error_msg = "\n".join(result["errors"]) if result["errors"] else None
            log.error(f"Download failed: {error_msg}")
            return False, None


class VideoProcessor(file_processor):
    def __init__(
        self,
        file_reader_path: Optional[str] = None,
        file_writer_path: Optional[str] = None,
    ):
        super().__init__()
        self.file_reader_folder = (
            file_reader_path
            or os.getenv("VIDEO_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "videos")
        )
        self.file_writer_folder = (
            file_writer_path
            or os.getenv("VIDEO_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "videos")
        )
        os.makedirs(self.file_reader_folder, exist_ok=True)
        os.makedirs(self.file_writer_folder, exist_ok=True)
        self._extensions: tuple[str, ...] = (".mp4", ".avi", ".mov")
        self.video_downloader = VideoDownloaderTab()

    async def read_file(self, filename: str, path: Optional[str] = None):
        log.info(
            f"读图片接受参数: 文件名：{filename}, 路径: {path or self.file_reader_folder}"
        )
        async with aiofiles.open(
            os.path.join(path or self.file_reader_folder, filename), "rb"
        ) as f:
            image = await f.read()
        log.info(f"读图片成功: 文件名：{filename}")
        return image

    async def write_file(
        self, filename: str, content: file_content, path: Optional[str] = None
    ) -> bool:
        log.info(
            f"写图片接受参数: 文件名：{filename}, 内容：{content if len(content) < 10 else content[:10]}, 类型: {type(content)}"
        )
        bin_content = await self._get_bin(content)
        async with aiofiles.open(
            os.path.join(path or self.file_writer_folder, filename), "wb"
        ) as f:
            await f.write(bin_content)
        log.info(f"写图片成功: 文件名：{filename}")
        return True

    async def get_file_path(self, filename: str, path: Optional[str] = None) -> str:
        return str(Path(path or self.file_writer_folder) / filename)

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions

    async def _video_download(
        self, url: str, file_name: str, download_path: Optional[str] = None
    ):

        success, video_id = await self.video_downloader._download_video(
            url, download_path or self.file_writer_folder + "/" + file_name
        )
        return success, video_id

    async def video_download(
        self, url: str, file_name: str, download_path: Optional[str] = None
    ):
        success, video_id = await self._video_download(url, file_name, download_path)
        return success, video_id


video_processor = VideoProcessor()
