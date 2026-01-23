import os
from pathlib import Path
from abc import ABC, abstractmethod

current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class file_processor(ABC):
    @abstractmethod
    async def read_file(self, filename: str, path: str = None):
        pass

    @abstractmethod
    async def write_file(self, filename: str, content: bytes, path: str = None):
        pass




