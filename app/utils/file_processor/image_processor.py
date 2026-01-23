from .base import file_processor
import os
from pathlib import Path

current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class Image_Processor(file_processor):
    def __init__(self, file_reader_path: str = None, file_writer_path: str = None):
        self.file_reader_folder = file_reader_path or str(
            root_path / "outputs" / "images"
        )
        self.file_writer_folder = file_writer_path or str(
            root_path / "outputs" / "images"
        )
        os.makedirs(self.file_reader_folder, exist_ok=True)
        os.makedirs(self.file_writer_folder, exist_ok=True)
        self.extensions = set([".jpg", ".jpeg", ".png"])

    async def read_file(self, filename: str, path: str = None):
        with open(os.path.join(path or self.file_reader_folder, filename), "rb") as f:
            image = f.read()
        return image

    async def write_file(self, filename: str, content: bytes, path: str = None):
        with open(os.path.join(path or self.file_writer_folder, filename), "wb") as f:
            f.write(content)

image_processor = Image_Processor()
