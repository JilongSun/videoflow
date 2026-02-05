from .base import file_processor
from pathlib import Path
from typing import Optional, cast
from app.models.router_model import file_content
from videoflow.utils.logger_config import log
import os, aiofiles, httpx, base64, ffmpeg, asyncio, cv2
import numpy as np


__all__ = ["image_processor"]

current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class ImageProcessor(file_processor):
    def __init__(
        self,
        file_reader_path: Optional[str] = None,
        file_writer_path: Optional[str] = None,
    ):
        super().__init__()
        self.file_reader_folder = (
            file_reader_path
            or os.getenv("IMAGE_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "images")
        )
        self.file_writer_folder = (
            file_writer_path
            or os.getenv("IMAGE_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "images")
        )
        os.makedirs(self.file_reader_folder, exist_ok=True)
        os.makedirs(self.file_writer_folder, exist_ok=True)
        self._extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")

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

    async def get_white_image(self, filename: str) -> str:
        path = await self.get_file_path(filename)
        path = path.replace("images", "videos")
        output_filename = f"white_{filename.split('.')[0]}.jpg"
        output_path = await self.get_file_path(output_filename)
        # cap = cv2.VideoCapture(path)
        # if not cap.isOpened():
        #     log.error(f"错误：无法打开视频文件 '{path}'")
        #     raise ValueError(f"错误：无法打开视频文件 '{path}'")
        # width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        # height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # log.info(f"视频尺寸: Width={width}, Height={height}")
        # white_image = np.full((height, width, 3), 255, dtype=np.uint8)
        # success = cv2.imwrite(output_path, white_image)
        # cap.release()
        # if success:
        #     return output_filename
        # else:
        #     log.error(f"错误：无法保存白色背景图片 '{output_path}'")
        #     raise ValueError(f"错误：无法保存白色背景图片 '{output_path}'")
        probe = ffmpeg.probe(path)
        video_stream = next(
            (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
            None,
        )

        if video_stream is None:
            raise ValueError("未能在文件中找到视频流。")

        # 获取视频的宽度和高度
        width = int(video_stream["width"])
        height = int(video_stream["height"])
        print(f"视频尺寸: {width}x{height}")

        (
            ffmpeg.input(f"color=c=white:s={width}x{height}", f="lavfi")
            .output(output_path, vframes=1, y=None)
            .run(overwrite_output=True)  # 使用overwrite_output=True确保覆盖输出文件
        )
        return output_filename

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions


image_processor = ImageProcessor()
