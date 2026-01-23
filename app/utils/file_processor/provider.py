from .image_processor import image_processor
from .base import file_processor
from typing import TypeVar

fp = TypeVar("文件处理", bound="file_processor")


class File_Processor_Provider:
    def __init__(self):
        self.image_processor = image_processor
        self.processor_list = [self.image_processor]

    def get_processor(self, filename: str) -> fp:
        for processor in self.processor_list:
            if filename.endswith(tuple(processor.extensions)):
                return processor
        raise ValueError(f"不支持的文件扩展名: {filename}")


file_processor_provider = File_Processor_Provider()


def read_file(filename: str, path: str = None):
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = File_Processor_Provider()
    return file_processor_provider.get_processor(filename).read_file(filename, path)


def write_file(filename: str, content: any, path: str = None):
    global file_processor_provider
    if file_processor_provider is None:
        file_processor_provider = File_Processor_Provider()
    return file_processor_provider.get_processor(filename).write_file(
        filename, content, path
    )
