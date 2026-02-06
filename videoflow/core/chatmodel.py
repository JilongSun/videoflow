from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from pydantic import Field, BaseModel
from typing import Optional, Annotated, Dict, Any, List
from .settings import runway_ait8, wanx_dashscpoe
from videoflow.utils.file_processor import write_file, read_file, get_file_path
from videoflow.utils.file_processor import video_processor, image_processor
from dashscope import ImageSynthesis
from videoflow.utils import log
import httpx, dashscope


class RunwayAit8(BaseModel):
    model_name: str = Field(..., description="模型名称")
    platform_name: str = Field(..., description="平台名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., description="API 密钥")  # 动态获取
    timeout: Optional[Annotated[int, Field(description="API 请求超时时间（秒）")]] = 300
    retries: Optional[Annotated[int, Field(description="API 请求重试次数")]] = 3
    if_taskid: bool = Field(..., description="ai第三方是否是返回任务ID")
    end_point: str = Field(..., description="API 路由")

    async def _generate(self, image: str, video: str):
        # image_url = await self.get_url(image)
        # video_url = await self.get_url(video)
        image_url = "https://files.closeai.fans/filesystem/uploads/54826/40a317576e75460e94cde709b9999e50/black_cat.webp"
        video_url = "https://files.closeai.fans/filesystem/uploads/54826/abb0f2dccbd54db9a73f25dd50450bdf/test_0_3.mp4"
        url = self.base_url + self.end_point
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        request_body = {
            "video": video_url,
            "prompt": "按照图片替换视频中的猫",
            "images": [image_url],
            "options": {"seconds": 5},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )
        print(response.status_code)
        print(response.content)


class WanxDashscope(BaseModel):
    model_name: str = Field(..., description="模型名称")
    platform_name: str = Field(..., description="平台名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., description="API 密钥")  # 动态获取
    timeout: Optional[Annotated[int, Field(description="API 请求超时时间（秒）")]] = 300
    retries: Optional[Annotated[int, Field(description="API 请求重试次数")]] = 3
    if_taskid: bool = Field(..., description="ai第三方是否是返回任务ID")
    end_point: str = Field(..., description="API 路由")
    

    async def _generate(
        self, image: List[str], video: str, mask_image: Optional[str] = None
    ):
        """
        wanx当前输入图像只支持一张
        """
        # image_url = await self.get_url(image)
        # video_url = await self.get_url(video)
        image_url = "https://files.closeai.fans/filesystem/uploads/54826/40a317576e75460e94cde709b9999e50/black_cat.webp"
        video_url = "https://files.closeai.fans/filesystem/uploads/54826/abb0f2dccbd54db9a73f25dd50450bdf/test_0_3.mp4"
        mask_image_url = "https://files.closeai.fans/filesystem/uploads/54826/82550662ea0e4bc3a81fdd3791c5278e/white_test.jpg"
        url = self.base_url + self.end_point
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        input = {
            "prompt": "按照图片替换视频中的猫",
            "function": "video_edit",
            "video_url": video_url,
            "ref_images_url": [image_url],
            "mask_image_url": mask_image_url,
            "options": {"seconds": 5},
        }
        request_body = {
            "model": self.model_name,
            "input": input,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )
            print(response.status_code)
            print(response.content)
        return response.json()

    async def _get_task_result(self, task_id: str):
        status = set(["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"])
        url = self.base_url + "/tasks" + f"/{task_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
        res = response.json()
        status = res.get("status")
        if status == "SUCCEEDED":
            log.info(f"Task {task_id} is SUCCEEDED")
            return res
        else:
            log.info(f"Task {task_id} is {status}")
            return res


runway = RunwayAit8(**runway_ait8.model_dump())

wanx = WanxDashscope(**wanx_dashscpoe.model_dump())
