from .base import file_processor
from pathlib import Path
from typing import Optional, cast, Tuple, Annotated, Union, List
from .base import file_content
from videoflow.utils.logger_config import log
from videoflow.utils.downloader.apis.api_client import MainAPIClient
from videoflow.utils.downloader.core.downloader import VideoDownloader
import os, aiofiles, httpx, base64, asyncio, ffmpeg, uuid

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
        self, url: str, download_path: str, file_name: Optional[str] = None
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
            file_name=file_name,
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

    def _parse_fps(self, fps_str: str) -> float:
        """将 ffprobe 帧率字符串安全解析为 float，避免 eval。"""
        if not fps_str or fps_str == "0/0":
            return 30.0
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            den_val = float(den) if float(den) != 0 else 1.0
            return float(num) / den_val
        return float(fps_str)

    def _resolve_local_video_path(self, video: str) -> Path:
        """支持纯文件名或绝对/相对本地路径。"""
        p = Path(video)
        if p.is_file():
            return p.resolve()
        return Path(self.file_writer_folder) / video

    def _session_dir(self, session_id: str) -> Path:
        sid = (session_id or "default").strip()
        return Path(self.file_writer_folder) / "sessions" / sid

    async def ensure_session_dirs(self, session_id: str) -> dict[str, str]:
        root = self._session_dir(session_id)
        dirs = {
            "root": root,
            "input": root / "input",
            "slices": root / "slices",
            "edited": root / "edited",
            "final": root / "final",
            "manifest": root / "manifest",
            "temp": root / "temp",
        }
        for d in dirs.values():
            Path(d).mkdir(parents=True, exist_ok=True)
        return {k: str(v) for k, v in dirs.items()}

    async def read_file(self, filename: str, path: Optional[str] = None):
        log.info(
            f"读视频接受参数: 文件名：{filename}, 路径: {path or self.file_reader_folder}"
        )
        async with aiofiles.open(
            os.path.join(path or self.file_reader_folder, filename), "rb"
        ) as f:
            res = await f.read()
        log.info(f"读视频成功: 文件名：{filename}")
        return res

    async def write_file(
        self, filename: str, content: file_content, path: Optional[str] = None
    ) -> bool:
        log.info(
            f"写视频接受参数: 文件名：{filename}, 内容：{content if len(content) < 10 else content[:10]}, 类型: {type(content)}"
        )
        bin_content = await self._get_bin(content)
        async with aiofiles.open(
            os.path.join(path or self.file_writer_folder, filename), "wb"
        ) as f:
            await f.write(bin_content)
        log.info(f"写视频成功: 文件名：{filename}")
        return True

    async def get_file_path(self, filename: str, path: Optional[str] = None) -> str:
        return str((Path(path or self.file_writer_folder) / filename).resolve())

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions

    @property
    def default_extension(self) -> str:
        return ".mp4"

    async def video_download_fromweb(
        self,
        url: str,
        file_name: Optional[str] = None,
        download_path: Optional[str] = None,
    ):

        success, video_id = await self.video_downloader._download_video(
            url, download_path or self.file_writer_folder, file_name
        )
        return success, video_id

    async def split_video(
        self,
        video_id: str,
        *,
        start: Union[int, float],
        end: Union[int, float],
        session_id: Optional[str] = None,
        slice_index: Optional[int] = None,
    ) -> str:
        """Trim the input so that the output contains one continuous subpart of the input.

        Args:
            start: Specify the time of the start of the kept section, i.e. the frame with the timestamp start will be the
                first frame in the output.
            end: Specify the time of the first frame that will be dropped, i.e. the frame immediately preceding the one
                with the timestamp end will be the last frame in the output.
            start_pts: This is the same as start, except this option sets the start timestamp in timebase units instead of
                seconds.
            end_pts: This is the same as end, except this option sets the end timestamp in timebase units instead of
                seconds.
            duration: The maximum duration of the output in seconds.
            start_frame: The number of the first frame that should be passed to the output.
            end_frame: The number of the first frame that should be dropped.
        """
        video_path = self._resolve_local_video_path(video_id)
        idx = slice_index if slice_index is not None else 0
        start_ms = int(float(start) * 1000)
        end_ms = int(float(end) * 1000)
        slice_name = f"slice_{idx:03d}_{start_ms:08d}_{end_ms:08d}.mp4"

        if session_id:
            dirs = await self.ensure_session_dirs(session_id)
            out_path = Path(dirs["slices"]) / slice_name
        else:
            out_path = Path(self.file_writer_folder) / slice_name

        def func():
            (
                ffmpeg.input(str(video_path), ss=float(start), to=float(end))
                .output(
                    str(out_path),
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(quiet=True)
            )

        await asyncio.to_thread(func)
        return str(out_path)

    async def concatenate_video(
        self,
        video_list: list[List],
        original_video: str,
        session_id: Optional[str] = None,
    ) -> Annotated[str, "合并后的视频名"]:
        """将分片一次性拼接成最终视频（避免循环重编码）。

        video_list: [ [[start,end], sliced_video, edited_sliced_video?], ... ]
        优先使用 edited_sliced_video；若不存在则使用 sliced_video。
        """
        if not video_list:
            raise ValueError("video_list 不能为空")

        original_path = self._resolve_local_video_path(original_video)
        sid = session_id or uuid.uuid4().hex[:8]
        dirs = await self.ensure_session_dirs(sid)
        temp_dir = Path(dirs["temp"])
        final_dir = Path(dirs["final"])
        final_name = f"final_{sid}_{original_path.stem}.mp4"
        final_path = final_dir / final_name

        probe_original = await asyncio.to_thread(ffmpeg.probe, str(original_path))
        video_stream_original = next(
            (s for s in probe_original["streams"] if s["codec_type"] == "video"),
            None,
        )
        if video_stream_original is None:
            raise ValueError(f"原视频缺少视频流: {original_path}")
        original_width = int(video_stream_original["width"])
        original_height = int(video_stream_original["height"])
        original_fps = self._parse_fps(
            video_stream_original.get("r_frame_rate", "30/1")
        )

        normalized_files: list[Path] = []
        for i, item in enumerate(video_list):
            selected = item[2] if len(item) >= 3 else item[1]
            seg_path = self._resolve_local_video_path(cast(str, selected))
            seg_probe = await asyncio.to_thread(ffmpeg.probe, str(seg_path))
            seg_duration = float(seg_probe["format"].get("duration", 0.0) or 0.0)

            seg_in = ffmpeg.input(str(seg_path))
            seg_v = (
                seg_in.video.filter("scale", original_width, original_height)
                .filter("setsar", "1/1")
                .filter("fps", fps=original_fps)
            )
            has_audio = any(
                s.get("codec_type") == "audio" for s in seg_probe["streams"]
            )
            if has_audio:
                seg_a = seg_in.audio
            else:
                duration = seg_duration if seg_duration > 0 else 0.1
                seg_a = ffmpeg.input(
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    f="lavfi",
                ).filter("atrim", duration=duration)

            norm_path = temp_dir / f"norm_{i:03d}.mp4"

            def _normalize():
                (
                    ffmpeg.output(
                        seg_v,
                        seg_a,
                        str(norm_path),
                        vcodec="libx264",
                        acodec="aac",
                        pix_fmt="yuv420p",
                        movflags="+faststart",
                        shortest=None,
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )

            await asyncio.to_thread(_normalize)
            normalized_files.append(norm_path)

        concat_list_path = temp_dir / "concat_list.txt"
        concat_content = "".join(f"file '{p.as_posix()}'\n" for p in normalized_files)
        async with aiofiles.open(concat_list_path, "w", encoding="utf-8") as f:
            await f.write(concat_content)

        def _concat():
            (
                ffmpeg.input(str(concat_list_path), format="concat", safe=0)
                .output(
                    str(final_path),
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(quiet=True)
            )

        await asyncio.to_thread(_concat)
        log.info(f"视频拼接完成: {final_path}")
        return str(final_path)

    async def detect_video_len(
        self, video: str
    ) -> Annotated[int, "视频时长（整数秒）"]:
        path = self._resolve_local_video_path(video)

        def func():
            return ffmpeg.probe(str(path))

        probe = await asyncio.to_thread(func)
        duration_seconds = int(float(probe["format"]["duration"]))
        log.info(f"视频时长: {duration_seconds}")
        return duration_seconds


video_processor = VideoProcessor()
