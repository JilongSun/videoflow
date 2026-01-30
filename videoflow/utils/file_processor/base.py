import os, aiofiles, httpx, base64
from pathlib import Path
from abc import ABC, abstractmethod
from typing import TypeVar, Awaitable, Any, Optional, Annotated
from app.models.router_model import file_content
from videoflow.utils import log

FP = TypeVar("FP", bound="file_processor")


current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class file_processor(ABC):
    def __init__(self) -> None:
        pp = os.getenv('N8N_BINARY_PATH', None)
        if not pp:
            log.error("N8N_BINARY_PATH 环境变量未配置")
            raise ValueError("N8N_BINARY_PATH 环境变量未配置")
        else:
            self.n8n_binary_path = Path(pp)
            log.info(f"n8n二进制文件存储地址: {self.n8n_binary_path}")

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

    async def _get_bin(self, content: file_content | bytes) -> bytes:
        """
        将文件内容转换为二进制数据,
        支持URL和base64编码后的内容
        """
        if isinstance(content, bytes):
            return content
        elif isinstance(content, str):
            if content.startswith(("http://", "https://")):
                async with httpx.AsyncClient() as client:
                    response = await client.get(content)
                    response.raise_for_status()  # 检查请求是否成功
                return response.content
            elif content.startswith("filesystem-v2:"):
                target_path = self.n8n_binary_path / content.split('filesystem-v2:')[-1]
                log.info(f"读取n8n二进制文件地址 {target_path}")
                async with aiofiles.open(str(target_path), 'rb') as f:
                    return await f.read()
            else:
                # 提取base64编码部分
                base64_str = base64.b64decode(content)
                return base64.b64decode(base64_str)
        raise ValueError(f"Unsupported content type: {type(content)}")
