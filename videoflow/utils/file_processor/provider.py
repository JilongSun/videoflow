from .image_processor import image_processor
from .doc_processor import doc_processor
from .base import file_processor, FP
from typing import TypeVar, Awaitable, Any, Optional, Generic, cast

__all__ = ["file_processor_provider", "read_file", "write_file", "get_file_path"]


class FileProcessorProvider(Generic[FP]):
    def __init__(self):
        self._processor_list: list[FP] = []

    def get_processor(self, filename: str) -> FP:
        for processor in self.processor_list:
            if filename.endswith(processor.extensions):
                return cast(FP, processor)
        raise ValueError(f"不支持的文件扩展名: {filename}")

    @property
    def processor_list(self) -> list[FP]:
        return self._processor_list

    def register(self, processor: FP):
        self.processor_list.append(processor)


file_processor_provider = FileProcessorProvider()
file_processor_provider.register(image_processor)
file_processor_provider.register(doc_processor)


async def read_file(filename: str, path: Optional[str] = None) -> bytes:
    """
    读取文件
    Args:
        filename (str): 文件名
        path (str, optional): 文件路径. Defaults to None.
    Returns:
        any: 文件内容
    """
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = FileProcessorProvider()
    processor = file_processor_provider.get_processor(filename)
    return await processor.read_file(filename, path)


async def write_file(filename: str, content: Any, path: Optional[str] = None) -> bool:
    """
    写入文件
    Args:
        filename (str): 文件名
        content (any): 文件内容
        path (str, optional): 文件路径. Defaults to None.
    Returns:
        bool: 是否写入成功
    """
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = FileProcessorProvider()
    processor = file_processor_provider.get_processor(filename)
    return await processor.write_file(filename, content, path)


async def get_file_path(filename: str, path: Optional[str] = None) -> str:
    """
    获取文件路径
    Args:
        filename (str): 文件名
        path (str, optional): 文件路径. Defaults to None.
    Returns:
        str: 文件路径
    """
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = FileProcessorProvider()
    processor = file_processor_provider.get_processor(filename)
    return await processor.get_file_path(filename, path)
