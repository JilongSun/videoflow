import os, aiofiles, httpx, base64, uuid, shutil, mimetypes, asyncio
from pathlib import Path
from abc import ABC, abstractmethod
from typing import TypeVar, Awaitable, Any, Optional, Annotated, Union
from urllib.parse import urlparse
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

    @property
    @abstractmethod
    def default_extension(self) -> str:
        """默认文件扩展名，如 '.mp4', '.webp', '.json'"""
        pass

    # ── 文件名 & 路径工具方法 ──────────────────────────

    @staticmethod
    def _is_url(path: str) -> bool:
        return path.startswith(("http://", "https://"))

    @staticmethod
    def _is_bare_filename(resource: str) -> bool:
        """判断输入是否为纯文件名（不含目录分隔符）。"""
        return (
            os.sep not in resource
            and "/" not in resource
            and not Path(resource).is_absolute()
        )

    @staticmethod
    def _ensure_filename(value: str) -> str:
        """提取纯文件名，拒绝含目录分隔符或路径穿越的字符串。"""
        name = Path(value).name
        if not name or name in (".", ".."):
            raise ValueError(f"无效的文件名: {value!r}")
        return name

    @staticmethod
    def _safe_target_name(writer_dir: Path, desired_name: str) -> str:
        """若目标目录已存在同名文件，追加短 UUID 避免覆盖。"""
        target = writer_dir / desired_name
        if not target.exists():
            return desired_name
        stem = Path(desired_name).stem
        ext = Path(desired_name).suffix
        safe_name = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
        log.debug(f"文件名冲突，重命名: {desired_name} -> {safe_name}")
        return safe_name

    @staticmethod
    def _guess_name_from_url(url: str, default_name: str) -> str:
        parsed = urlparse(url)
        base = Path(parsed.path).name
        return base if base else default_name

    @staticmethod
    def _guess_ext_from_content_type(
        content_type: Optional[str],
        default_ext: str,
    ) -> str:
        if not content_type:
            return default_ext
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        return guessed or default_ext

    # ── 资源落地（核心方法） ──────────────────────────

    async def materialize(self, resource: str) -> str:
        """将任意来源（URL / 文件名 / 本地路径）落地到本处理器的 outputs 目录。

        Returns:
            纯文件名（不含目录），文件保证存在于 self.file_writer_folder 中。
        """
        writer_dir = Path(self.file_writer_folder)
        default_ext = self.default_extension
        default_name = f"file_{uuid.uuid4().hex[:8]}{default_ext}"
        writer_dir.mkdir(parents=True, exist_ok=True)

        # ── 1) URL: 下载到 outputs 目录 ──
        if self._is_url(resource):
            file_name = self._guess_name_from_url(resource, default_name)
            async with httpx.AsyncClient() as client:
                response = await client.get(resource, timeout=600)
                response.raise_for_status()
            if not Path(file_name).suffix:
                file_name += self._guess_ext_from_content_type(
                    response.headers.get("content-type"),
                    default_ext,
                )
            file_name = self._ensure_filename(file_name)
            file_name = self._safe_target_name(writer_dir, file_name)
            success = await self.write_file(file_name, response.content)
            if not success:
                raise RuntimeError(f"下载并写入失败: {resource} -> {file_name}")
            log.info(f"URL 下载成功: {resource} -> {file_name}")
            return file_name

        # ── 2) 纯文件名: 检查是否已在 outputs 目录中 ──
        if self._is_bare_filename(resource):
            if (writer_dir / resource).is_file():
                log.info(f"已在项目目录中: {writer_dir / resource}")
                return resource

        # ── 3) 本地路径（绝对或相对）: 解析并复制到 outputs ──
        source_path = Path(resource).resolve()

        if not source_path.is_file():
            raise FileNotFoundError(f"输入不存在: {resource}")

        # 已在目标 outputs 目录中，直接返回纯文件名
        if source_path.parent.resolve() == writer_dir.resolve():
            log.info(f"已在目标目录中: {source_path}")
            return source_path.name

        # 复制到 outputs 目录，带冲突保护
        desired_name = source_path.name
        if not Path(desired_name).suffix:
            desired_name += default_ext
        safe_name = self._safe_target_name(writer_dir, desired_name)
        target_path = writer_dir / safe_name
        await asyncio.to_thread(shutil.copy2, str(source_path), str(target_path))
        log.info(f"已落地到项目目录: {source_path} -> {target_path}")
        return safe_name

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