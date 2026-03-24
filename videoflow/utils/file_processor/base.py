import os, aiofiles, httpx, base64
from pathlib import Path
from abc import ABC, abstractmethod
from typing import TypeVar, Awaitable, Any, Optional, Annotated, Union
from videoflow.utils import log

# file_content: URL / base64 / filesystem-v2 路径，本质都是 str
file_content = Union[str, bytes]

FP = TypeVar("FP", bound="file_processor")


current_path = Path(__file__)
root_path = current_path.parent.parent.parent.parent


class file_processor(ABC):
    def __init__(self) -> None:
        pp = os.getenv("N8N_BINARY_PATH", None)
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
        支持URL和n8n的filesystem-v2
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
                target_path = self.n8n_binary_path / content.split("filesystem-v2:")[-1]
                log.info(f"读取n8n二进制文件地址 {target_path}")
                async with aiofiles.open(str(target_path), "rb") as f:
                    return await f.read()
            else:
                # 将字符串转换成二进制数据
                return content.encode("utf-8")
        raise ValueError(f"Unsupported content type: {type(content)}")

    async def _to_base64(self, file_name: str):
        """
        将本地图片文件转换为base64编码

        Args:
            image_path (str): 图片文件的路径

        Returns:
            str: base64编码的字符串
        """
        binary_data = await self.read_file(file_name)

        # 将二进制数据转换为base64编码
        base64_encoded = base64.b64encode(binary_data)
        # 将bytes类型转换为字符串
        base64_string = base64_encoded.decode("utf-8")

        return base64_string
    
    async def get_url(self, file_name: str):
        """
        使用ait8的oss储存获得url
        """
        ...
        url = "https://ai.t8star.cn/v1/files"
        payload = {}
        api_key = os.getenv("AIT8_API_KEY", None)
        if not api_key:
            log.error("AIT8_API_KEY 环境变量未配置")
            raise ValueError("AIT8_API_KEY 环境变量未配置")
        path = await self.get_file_path(file_name)
        
        # 使用异步文件操作
        async with aiofiles.open(path, "rb") as f:
            file_content = await f.read()
        
        # 构建异步上传的文件数据
        files = {"file": (file_name, file_content, "application/octet-stream")}
        
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        
        # 使用异步HTTP客户端
        async with httpx.AsyncClient() as client:
            res = await client.post(
                url,
                headers=headers,
                data=payload,
                files=files,
                timeout=3000,
            )
        
        if res.status_code == 200:
            return res.json()["url"]
        else:
            raise Exception(f"获取文件url失败: {res.status_code} {res.content}")