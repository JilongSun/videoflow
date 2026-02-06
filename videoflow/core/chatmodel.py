from langchain_core.callbacks import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.runnables import Runnable
from pydantic import Field, BaseModel
from typing import Optional, Annotated, Dict, Any, List, Union, Tuple
from .settings import runway_ait8, wanx_dashscpoe
from videoflow.utils.file_processor import write_file, read_file, get_file_path
from videoflow.utils.file_processor import (
    video_processor,
    image_processor,
    file_processor_provider,
)
from langchain_core.language_models.base import (
    BaseLanguageModel,
    LangSmithParams,
    LanguageModelInput,
)
from dashscope import ImageSynthesis
from videoflow.utils import log
from abc import ABC, abstractmethod
import httpx, dashscope, os, aiofiles, json


class VideoEditBase(BaseChatModel, ABC):
    model_name: str = Field(..., description="模型名称")
    platform_name: str = Field(..., description="平台名称")
    base_url: str = Field(..., description="API 基础 URL")
    api_key: str = Field(..., description="API 密钥")  # 动态获取
    timeout: Optional[Annotated[int, Field(description="API 请求超时时间（秒）")]] = 300
    retries: Optional[Annotated[int, Field(description="API 请求重试次数")]] = 3
    if_taskid: bool = Field(True, description="ai第三方是否是返回任务ID")
    end_point: str = Field(..., description="API 路由")
    status: Optional[set] = Field(
        ..., description="如果是taskid的形式，就必须有任务状态"
    )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        放弃使用同步的_generate方法，重写异步的_agenerate方法,
        因为原本的_agenerate是创建新线程调用_generate，_generate内部仍然是同步的
        """
        ...

    @property
    def _llm_type(self) -> str:
        return self.platform_name + self.model_name

    @abstractmethod
    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult: ...

    async def _get_task_result(self, task_id: str) -> Annotated[bool, "是否完成"]:
        raise NotImplementedError("请实现 _get_task_result 方法")

    async def _wait_for_task_completion(self, task_id: str):
        while True:
            result = await self._get_task_result(task_id)
            if result:
                break

    async def _get_urls(
        self, file_names: Union[List[str], str]
    ) -> Union[List[str], str]:
        if isinstance(file_names, str):
            return await self._get_url(file_names)
        elif isinstance(file_names, list):
            temp = []
            for file_name in file_names:
                temp.append(await self._get_url(file_name))
            return temp
        else:
            raise ValueError("file_names 必须是字符串或字符串列表")

    async def _get_url(self, file_name: str) -> str:
        """
        使用ait8的oss储存获得url
        """
        if file_name.startswith(("http", "https")):
            return file_name
        url = "https://ai.t8star.cn/v1/files"
        payload = {}
        api_key = os.getenv("AIT8_API_KEY", None)
        if not api_key:
            log.error("AIT8_API_KEY 环境变量未配置")
            raise ValueError("AIT8_API_KEY 环境变量未配置")
        path = await get_file_path(file_name)

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


class WanxDashscope(VideoEditBase):
    async def ainvoke(
        self,
        image: List[str],
        video: str,
        mask_image: str,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        temp_dic = {
            "image": image,
            "video": video,
            "mask_image": mask_image,
        }
        return await super().ainvoke(json.dumps(temp_dic), config, stop=stop, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # temp = json.loads(messages[-1].content)
        # image: List[str] = temp["image"]
        # video: str = temp["video"]
        # mask_image: str = temp["mask_image"]
        # image_url = await self._get_urls(image)
        # video_url = await self._get_urls(video)
        # mask_image_url = await self._get_urls(mask_image)
        image_url = [
            "https://files.closeai.fans/filesystem/uploads/54826/40a317576e75460e94cde709b9999e50/black_cat.webp"
        ]
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
            "ref_images_url": image_url,
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
        log.info(f"response.status_code: {response.status_code}")
        log.info(f"response.content: {response.content}")
        res: dict = response.json()
        if self.if_taskid:
            task_id = res["output"]["task_id"]
            log.info(f"task_id: {task_id}")
            await self._wait_for_task_completion(task_id)

        return res

    async def _get_task_result(self, task_id: str) -> Annotated[bool, "是否完成"]:
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
        res = response.json()["output"]
        status = res.get("status")
        if status == "SUCCEEDED":
            log.info(f"Task {task_id} is SUCCEEDED")
            return res
        else:
            log.info(f"Task {task_id} is {status}")
            return res


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


runway = RunwayAit8(**runway_ait8.model_dump())

wanx = WanxDashscope(**wanx_dashscpoe.model_dump())
