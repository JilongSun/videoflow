from .base import file_processor
from videoflow.utils.logger_config import log
from app.models.router_model import file_content
from pathlib import Path
from typing import Optional
import os, aiofiles, base64

__all__ = ["doc_processor"]

current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class DocProcessor(file_processor):
    def __init__(
        self,
        file_reader_path: Optional[str] = None,
        file_writer_path: Optional[str] = None,
    ):
        super().__init__()
        self.file_reader_folder = (
            file_reader_path
            or os.getenv("DOCUMENT_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "docs")
        )
        self.file_writer_folder = (
            file_writer_path
            or os.getenv("DOCUMENT_OUTPUT_PATH", None)
            or str(root_path / "outputs" / "docs")
        )
        os.makedirs(self.file_reader_folder, exist_ok=True)
        os.makedirs(self.file_writer_folder, exist_ok=True)
        self._extensions: tuple[str, ...] = (".txt", ".docx", ".json")

    async def read_file(self, filename: str, path: Optional[str] = None):
        log.info(
            f"读文档接受参数: 文件名：{filename}, 路径: {path or self.file_reader_folder}"
        )
        async with aiofiles.open(
            os.path.join(path or self.file_reader_folder, filename), "rb"
        ) as f:
            image = await f.read()
        log.info(f"读文档成功: 文件名：{filename}")
        return image

    async def write_file(
        self, filename: str, content: file_content, path: Optional[str] = None
    ) -> bool:
        log.info(
            f"写文档接受参数: 文件名：{filename}, 内容：{content if len(content) < 10 else content[:10]}, 类型: {type(content)}"
        )
        # 转换为二进制数据
        bin_content = await self._get_bin(content)

        async with aiofiles.open(
            os.path.join(path or self.file_writer_folder, filename), "wb"
        ) as f:
            await f.write(bin_content)
        log.info(f"写文档成功: 文件名：{filename}")
        return True

    async def get_file_path(self, filename: str, path: Optional[str] = None) -> str:
        return str(Path(path or self.file_writer_folder) / filename)

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions


doc_processor = DocProcessor()
