from langchain_core.callbacks import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.outputs import ChatResult, Generation, ChatGeneration
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langchain_core.runnables import Runnable
from pydantic import Field, BaseModel
from typing import (
    Optional,
    Annotated,
    Dict,
    Any,
    List,
    Union,
    Tuple,
    cast,
    Sequence,
    Callable,
)
from .settings import (
    runway_ait8,
    wanx_dashscpoe,
    gen4aleph_runway,
    qwen_dashscope,
    ModelSettings,
)
from .graph import workflow_manager, video_flow_workflow
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
from videoflow.utils import log
from abc import ABC, abstractmethod
from runwayml import RunwayML
from pathlib import Path
import httpx, os, aiofiles, json, asyncio

__all__ = [
    "gen4aleph",
    "qwendashchat",
    "runway",
    "wanx",
]


class VideoEditBase(BaseChatModel, ModelSettings, ABC):
    # model_name: str = Field(..., description="模型名称")
    # platform_name: str = Field(..., description="平台名称")
    # base_url: str = Field(..., description="API 基础 URL")
    # api_key: str = Field(..., description="API 密钥")  # 动态获取
    # timeout: Optional[Annotated[int, Field(description="API 请求超时时间（秒）")]] = 300
    # retries: Optional[Annotated[int, Field(description="API 请求重试次数")]] = 3
    # if_taskid: bool = Field(True, description="ai第三方是否是返回任务ID")
    # end_point: str = Field(..., description="API 路由")
    # status: Optional[set] = Field(
    #     ..., description="如果是taskid的形式，就必须有任务状态"
    # )

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
    """
    阿里的wanx2.1-vace模型，废弃不用
    """

    async def ainvoke(  # type: ignore
        self,
        image: List[str],
        video: str,
        mask_image: Optional[str] = None,
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
        temp = json.loads(cast(str, messages[-1].content))
        image: List[str] = temp["image"]
        video: str = temp["video"]
        mask_image: str = temp["mask_image"]
        image_url = await self._get_urls(image)
        video_url = await self._get_urls(video)
        mask_image_url = await self._get_urls(mask_image)
        url = self.base_url + self.end_point  # type: ignore
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        # todo: 这里的prompt需要根据实际的需求来修改
        # todo: 还需要测试参考图像和obj
        input = {
            "prompt": "将猫替换成黑猫,只需要做单纯的猫的替换，不要添加任何其他的元素，注意一定要显示风格的！",
            "function": "video_edit",
            "video_url": video_url,
            # "ref_images_url": image_url,
            "mask_image_url": mask_image_url,
            "mask_frame_id": 1,
            "options": {"seconds": 5},
        }
        parameters = {
            "obj_or_bg ": ["obj"],
        }
        request_body = {
            "model": self.model_name,
            "input": input,
            # "parameters": parameters,
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
        task_id = None
        if self.if_taskid:
            task_id = res["output"]["task_id"]
            log.info(f"task_id: {task_id}")
            # await self._wait_for_task_completion(task_id)

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=BaseMessage(
                        content=task_id if task_id else "error", type="video_edit,wanx"
                    )
                )
            ]
        )

    async def _get_task_result(self, task_id: str) -> Annotated[bool, "是否完成"]:
        url = self.base_url + "/tasks" + f"/{task_id}"  # type: ignore
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


class Gen4AlephRunway(VideoEditBase):
    """
    runway的gen4_aleph模型
    """

    def model_post_init(self, __context: Any) -> None:
        self.client = RunwayML(api_key=self.api_key)

    async def ainvoke(  # type: ignore
        self,
        image: List[str],
        video: str,
        mask_image: Optional[str] = None,
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
        temp = json.loads(cast(str, messages[-1].content))
        image: List[str] = temp["image"]
        video: str = temp["video"]
        image_url = await self._get_urls(image)
        video_url = await self._get_urls(video)
        input = {
            "model": self.model_name,
            "video_uri": video_url,
            "prompt_text": "Replace the cat in the video with the cat in the picture",
            "references": [
                {
                    "type": "image",
                    "uri": image_url[0],
                }
            ],
            "extra_headers": {"Content-Type": "application/json"},
        }
        self.client: RunwayML

        def gen():
            log.info(f"input: {input},开始调用genaleph模型")
            res = self.client.video_to_video.create(**input).wait_for_task_output()
            return res

        task = await asyncio.to_thread(gen)
        if task is None:
            raise ValueError("task is None")
        elif task.status == "SUCCEEDED":
            res = task.output[0]
            log.info(f"genaleph模型返回结果: {res}")
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=BaseMessage(content=res, type="video_edit,genaleph")
                    )
                ]
            )
        else:
            raise ValueError(f"task status is Failed")

    async def _get_url(self, file_name: str) -> str:
        """
        如果使用runway就是用他们自家的临时uri储存
        """
        if file_name.startswith("runway://"):
            return file_name
        elif file_name.startswith(("http", "https")):
            raise ValueError("runway模型只支持runway://开头的uri")
        file = await get_file_path(file_name)
        response = self.client.uploads.create_ephemeral(file=Path(file))
        return response.uri


class RunwayAit8(BaseModel):
    """
    ait8的runway模型暂时弃用，api调用似乎有问题，并且还需要接入langchain
    """

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


class QwenDashscopeChat(VideoEditBase):
    def model_post_init(self, __context: Any) -> None:
        self.client: ChatOpenAI = ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,  # type: ignore
            timeout=self.timeout,
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        res = await self.client._agenerate(messages, stop, run_manager, **kwargs)
        log.info(f"QwenDashscopeChat返回结果: {res}")
        return res

    async def ainvoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        res = await self.client.ainvoke(input)
        log.info(f"QwenDashscopeChat返回结果: {res}")
        return res

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: dict | str | bool | None = None,
        strict: bool | None = None,
        parallel_tool_calls: bool | None = None,
        response_format=None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self.client.bind_tools(
            tools,
            tool_choice=tool_choice,
            strict=strict,
            parallel_tool_calls=parallel_tool_calls,
            response_format=response_format,
            **kwargs,
        )


runway = RunwayAit8(**runway_ait8.model_dump())

wanx = WanxDashscope(**wanx_dashscpoe.model_dump())

gen4aleph = Gen4AlephRunway(**gen4aleph_runway.model_dump())

qwendashchat = QwenDashscopeChat(**qwen_dashscope.model_dump())
