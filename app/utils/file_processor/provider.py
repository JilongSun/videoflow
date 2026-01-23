from .image_processor import image_processor
from .base import file_processor, FP
from typing import TypeVar, Awaitable, Any, Optional, Generic


class File_Processor_Provider(Generic[FP]):
    def __init__(self):
        self.image_processor = image_processor
        self.processor_list: list[FP] = [self.image_processor]

    def get_processor(self, filename: str) -> FP:
        for processor in self.processor_list:
            if filename.endswith(processor.extensions):
                return processor
        raise ValueError(f"不支持的文件扩展名: {filename}")


file_processor_provider = File_Processor_Provider()


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
        file_processor_provider = File_Processor_Provider()
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
        file_processor_provider = File_Processor_Provider()
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
        file_processor_provider = File_Processor_Provider()
    processor = file_processor_provider.get_processor(filename)
    return await processor.get_file_path(filename, path)