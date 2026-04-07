from .image_processor import image_processor
from .doc_processor import doc_processor
from .video_processor import video_processor
from .base import file_processor, FP
from typing import TypeVar, Awaitable, Any, Optional, Generic, cast
import os

__all__ = ["file_processor_provider", "read_file", "write_file", "get_file_path", "materialize_file"]


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
file_processor_provider.register(video_processor)


# ── 按类型快速查找处理器 ──
_TYPE_TO_PROCESSOR = {
    "image": image_processor,
    "video": video_processor,
    "doc": doc_processor,
}


async def materialize_file(resource: str, media_type: str) -> str:
    """将任意来源的文件落地到项目 outputs 对应目录，返回纯文件名。

    Args:
        resource: URL / 本地路径 / 纯文件名
        media_type: 处理器类型，如 "image", "video", "doc"
    """
    processor = _TYPE_TO_PROCESSOR.get(media_type)
    if processor is None:
        raise ValueError(f"不支持的 media_type: {media_type!r}，可选: {list(_TYPE_TO_PROCESSOR)}")
    return await processor.materialize(resource)


def _validate_filename(filename: str) -> str:
    """确保 filename 是纯文件名，拒绝含路径分隔符或穿越字符的输入。

    这是文件 I/O 的最后一道防线，防止外部传入的路径绕过
    outputs 目录约束，导致路径穿越或读写任意位置。
    """
    basename = os.path.basename(filename)
    if basename != filename or not basename or basename in (".", ".."):
        raise ValueError(
            f"filename 必须是纯文件名（不含目录路径），收到: {filename!r}"
        )
    return basename


async def read_file(filename: str, path: Optional[str] = None) -> bytes:
    """
    读取文件
    Args:
        filename (str): 文件名
        path (str, optional): 文件路径. Defaults to None.
    Returns:
        any: 文件内容
    """
    filename = _validate_filename(filename)
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
    filename = _validate_filename(filename)
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
    filename = _validate_filename(filename)
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = FileProcessorProvider()
    processor = file_processor_provider.get_processor(filename)
    return await processor.get_file_path(filename, path)
