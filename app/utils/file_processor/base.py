import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import TypeVar, Awaitable, Any, Optional, Annotated

FP = TypeVar("FP", bound="file_processor")


current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class file_processor(ABC):
    @abstractmethod
    async def read_file(self, filename: str, path: Optional[str] = None) -> bytes:
        pass

    @abstractmethod
    async def write_file(
        self, filename: str, content: Any, path: Optional[str] = None
    ) -> bool:
        pass

    @abstractmethod
    async def get_file_path(self, filename: str, path: Optional[str] = None) -> str:
        pass

    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        pass
