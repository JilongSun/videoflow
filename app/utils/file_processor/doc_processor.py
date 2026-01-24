from .base import file_processor
import os, aiofiles
from pathlib import Path
from typing import Optional


current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class DocProcessor(file_processor):
    def __init__(
        self,
        file_reader_path: Optional[str] = None,
        file_writer_path: Optional[str] = None,
    ):
        self.file_reader_folder = file_reader_path or str(
            root_path / "outputs" / "docs"
        )
        self.file_writer_folder = file_writer_path or str(
            root_path / "outputs" / "docs"
        )
        os.makedirs(self.file_reader_folder, exist_ok=True)
        os.makedirs(self.file_writer_folder, exist_ok=True)
        self._extensions: tuple[str, ...] = (".txt", ".docx")

    async def read_file(self, filename: str, path: Optional[str] = None):
        async with aiofiles.open(os.path.join(path or self.file_reader_folder, filename), "rb") as f:
            image = await f.read()
        return image

    async def write_file(
        self, filename: str, content: bytes, path: Optional[str] = None
    ) -> bool:
        async with aiofiles.open(os.path.join(path or self.file_writer_folder, filename), "wb") as f:
            await f.write(content)
        return True

    async def get_file_path(self, filename: str, path: Optional[str] = None) -> str:
        return str(Path(path or self.file_writer_folder) / filename)

    @property
    def extensions(self) -> tuple[str, ...]:
        return self._extensions

doc_processor = DocProcessor()
