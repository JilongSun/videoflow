from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)
from pydantic import Field
from typing import Optional, List, Annotated, Any, Dict, Union
from videoflow.utils import log
from runwayml import RunwayML
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
    status: Optional[set] = None  # 如果是taskid的形式，就必须有任务状态
    client: Optional[Any] = None  # 如果使用第三方sdk，就需要传入client

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
        if self.if_taskid and not self.status:
            raise ValueError("如果是taskid的形式，就必须有任务状态")

        self._check_platform()

    def _check_platform(self):
        if self.platform_name == "ait8":
            self._process_ait8()
        elif self.platform_name == "dashscope":
            self._process_dashscope()
        elif self.platform_name == "runway":
            self._process_runway()
        else:
            raise ValueError(f"不支持的平台: {self.platform_name}")

    def _process_ait8(self):
        self.base_url = "https://ai.t8star.cn"

    def _process_dashscope(self):
        if self.base_url is None:
            self.base_url = "https://dashscope.aliyuncs.com/api/v1"
        else:
            if self.api_key is None:
                raise ValueError("如dashscopeapi_key没有正确设置")


    def _process_runway(self):
        self.base_url = "https://api.dev.runwayml.com"
        


class ModelSettings(PlatformConfig):
    model_name: str = Field(..., description="模型名称")
    end_point: str = Field(..., description="API 路由")


# 创建全局配置实例
runway_ait8 = ModelSettings(
    platform_name="ait8",
    if_taskid=True,
    model_name="runway-aleph",
    end_point="/runway/v1/pro/aleph",
    status={
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
        "UNKNOWN",
    },
)

wanx_dashscpoe = ModelSettings(
    platform_name="dashscope",
    if_taskid=True,
    model_name="wanx2.1-vace-plus",
    end_point="/services/aigc/video-generation/video-synthesis",
    status={
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
        "UNKNOWN",
    },
)

gen4aleph_runway = ModelSettings(
    platform_name="runway",
    if_taskid=False,
    model_name="gen4_aleph",
    end_point="/v1/video-to-video",
)

qwen_dashscope = ModelSettings(
    platform_name="dashscope",
    if_taskid=False,
    model_name="qwen-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    end_point="使用openai兼容格式不需要end_point",
)

__all__ = [
    "runway_ait8",
    "wanx_dashscpoe",
    "gen4aleph_runway",
    "qwen_dashscope",
    "ModelSettings",
]
