from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)
from pydantic import Field
from typing import Optional, List, Annotated, Any, Dict
from videoflow.utils import log
import os


class MySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_to_lower=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        暂时只支持从.env文件加载配置
        """
        return init_settings, dotenv_settings


class PlatformConfig(MySettings):
    # 基础平台配置
    platform_name: str = Field(..., description="平台名称")

    # API 配置
    base_url: Optional[str] = Field(default=None, description="API 基础 URL")
    api_key: Optional[str] = Field(default=None, description="API 密钥")  # 动态获取

    timeout: Optional[Annotated[int, Field(description="API 请求超时时间（秒）")]] = 300
    retries: Optional[Annotated[int, Field(description="API 请求重试次数")]] = 3

    if_taskid: bool = Field(..., description="ai第三方是否是返回任务ID")

    def model_post_init(self, __context: Any) -> None:
        """
        模型初始化后调用，用于动态获取对应平台的 API key
        """
        # 根据 platform_name 构建环境变量名
        env_api_key_name = f"{self.platform_name}_api_key".upper()

        # 从环境变量中获取对应的 API key
        platform_api_key = os.getenv(env_api_key_name)
        if platform_api_key:
            # 如果找到了对应的 API key，则更新 api_key 字段
            self.api_key = platform_api_key
            log.info(f"✅ 成功获取 {self.platform_name} 的 API key")
        else:
            # 如果没有找到，保持原有的 api_key 值或给出警告
            log.error(f"⚠️  未找到环境变量 {env_api_key_name}，使用默认 API key")
            raise ValueError(f"未找到环境变量 {env_api_key_name}，请在 .env 文件中配置")
        self._check_platform()

    def _check_platform(self):
        if self.platform_name == "ait8":
            self._process_ait8()
        elif self.platform_name == "dashscope":
            self._process_dashscope()

    def _process_ait8(self):
        self.base_url = "https://ai.t8star.cn"

    def _process_dashscope(self):
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"


class ModelSettings(PlatformConfig):
    model_name: str = Field(..., description="模型名称")
    body: Dict[str, Any] = Field(..., description="模型请求体")
    end_point: str = Field(..., description="API 路由")


# 创建全局配置实例
runway_ait8 = ModelSettings(
    platform_name="ait8",
    if_taskid=True,
    model_name="runway-aleph",
    body={
        "video": "string",
        "prompt": "string",
        "images": ["string"],
        "options": {"seconds": 0},
    },
    end_point="/runway/v1/pro/aleph",
)

wanx_dashscpoe = ModelSettings(
    platform_name="dashscope",
    if_taskid=True,
    model_name="wanx2.1-vace-plus",
    body={
        "model": "str",
        "function": "str",
        "video": "url",
        "prompt": "url",
        "images": ["url"],
        "options": {"seconds": 0},
    },
    end_point="services/aigc/video-generation/video-synthesis",
)

__all__ = ["runway_ait8", "wanx_dashscpoe"]
