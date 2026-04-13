from langchain_core.callbacks import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.outputs import ChatResult, Generation, ChatGeneration
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, SystemMessage
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
    wanx_dashscpoe,
    wan_videoedit27_dashscope,
    gen4aleph_runway,
    qwen_dashscope,
    ModelSettings,
    qwen3vl_dashscope,
)
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
from dashscope import MultiModalConversation, AioMultiModalConversation
import dashscope
from abc import ABC, abstractmethod
from runwayml import RunwayML, AsyncRunwayML
from pathlib import Path
import httpx, os, aiofiles, json, asyncio

__all__ = [
    "gen4aleph",
    "qwendashchat",
    "wanx",
    "wan_videoedit27",
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

    async def _get_task_result(self, task_id: str) -> Dict[str, Any]:
        raise NotImplementedError("请实现 _get_task_result 方法")

    async def _wait_for_task_completion(
        self,
        task_id: str,
        *,
        poll_interval: int = 5,
        timeout_seconds: int = 1800,
        progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        elapsed = 0
        while elapsed <= timeout_seconds:
            result = await self._get_task_result(task_id)
            status = result.get("task_status") or result.get("status")

            if progress_callback is not None:
                update = {
                    "task_id": task_id,
                    "task_status": status,
                    "video_url": result.get("video_url"),
                    "raw": result,
                }
                maybe_awaitable = progress_callback(update)
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable

            if status == "SUCCEEDED":
                return result
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise ValueError(f"任务 {task_id} 失败，状态={status}, 详情={result}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"任务 {task_id} 轮询超时，超过 {timeout_seconds}s")

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
    阿里的wanx2.1-vace-plus模型(局部编辑)
    """

    async def ainvoke(  # type: ignore
        self,
        prompt: str,
        image: List[str],
        video: str,
        mask_image: Optional[str] = None,
        mask_frame_id: int = 1,
        mask_type: str = "tracking",
        expand_ratio: float = 0.05,
        expand_mode: str = "hull",
        control_condition: Optional[str] = None,
        prompt_extend: bool = False,
        watermark: bool = False,
        size: str = "1280*720",
        obj_or_bg: Optional[List[str]] = None,
        seed: Optional[int] = None,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        temp_dic = {
            "prompt": prompt,
            "image": image,
            "video": video,
            "mask_image": mask_image,
            "mask_frame_id": mask_frame_id,
            "mask_type": mask_type,
            "expand_ratio": expand_ratio,
            "expand_mode": expand_mode,
            "control_condition": control_condition,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
            "size": size,
            "obj_or_bg": obj_or_bg,
            "seed": seed,
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
        progress_callback = cast(
            Optional[Callable[[Dict[str, Any]], Any]], kwargs.get("progress_callback")
        )
        prompt: str = temp["prompt"]
        image: List[str] = temp["image"]
        video: str = temp["video"]
        mask_image: Optional[str] = temp.get("mask_image")
        if mask_image is None:
            raise ValueError("wanx2.1-vace video_edit 需要传入 mask_image")

        image_url = cast(List[str], await self._get_urls(image))
        video_url = await self._get_urls(video)
        mask_image_url = await self._get_urls(mask_image)

        parameters: Dict[str, Any] = {
            "mask_type": temp.get("mask_type", "tracking"),
            "expand_ratio": temp.get("expand_ratio", 0.05),
            "expand_mode": temp.get("expand_mode", "hull"),
            "prompt_extend": temp.get("prompt_extend", False),
            "watermark": temp.get("watermark", False),
            "size": temp.get("size", "1280*720"),
        }

        control_condition = temp.get("control_condition")
        if control_condition:
            parameters["control_condition"] = control_condition

        seed = temp.get("seed")
        if seed is not None:
            parameters["seed"] = seed

        obj_or_bg = temp.get("obj_or_bg")
        if obj_or_bg:
            parameters["obj_or_bg"] = obj_or_bg

        url = self.base_url + self.end_point  # type: ignore
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        input = {
            "prompt": prompt,
            "function": "video_edit",
            "video_url": video_url,
            "ref_images_url": image_url,
            "mask_image_url": mask_image_url,
            "mask_frame_id": temp.get("mask_frame_id", 1),
        }

        request_body = {
            "model": self.model_name,
            "input": input,
            "parameters": parameters,
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
        if response.status_code >= 400:
            raise ValueError(
                f"wanx2.1-vace 请求失败: {response.status_code} {response.text}"
            )
        res: dict = response.json()
        task_id = res.get("output", {}).get("task_id")
        if not task_id:
            raise ValueError(f"wanx2.1-vace 未返回 task_id: {res}")

        polled = await self._wait_for_task_completion(
            task_id,
            progress_callback=progress_callback,
        )
        video_url = polled.get("video_url")
        if not video_url:
            raise ValueError(f"wanx2.1-vace 任务成功但未返回 video_url: {polled}")

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=BaseMessage(
                        content=video_url,
                        type="video_edit,wanx",
                    )
                )
            ]
        )

    async def _get_task_result(self, task_id: str) -> Dict[str, Any]:
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
        res = response.json().get("output", {})
        status = res.get("task_status") or res.get("status")
        if status == "SUCCEEDED":
            log.info(f"Task {task_id} is SUCCEEDED")
        else:
            log.info(f"Task {task_id} is {status}")
        return res


class WanVideoEdit27Dashscope(VideoEditBase):
    """
    阿里的wan2.7-videoedit模型（指令编辑）
    """

    async def ainvoke(  # type: ignore
        self,
        prompt: str,
        image: List[str],
        video: str,
        negative_prompt: Optional[str] = None,
        resolution: str = "1080P",
        duration: int = 0,
        ratio: Optional[str] = None,
        audio_setting: str = "origin",
        prompt_extend: bool = False,
        watermark: bool = False,
        seed: Optional[int] = None,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        temp_dic = {
            "prompt": prompt,
            "image": image,
            "video": video,
            "negative_prompt": negative_prompt,
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
            "audio_setting": audio_setting,
            "prompt_extend": prompt_extend,
            "watermark": watermark,
            "seed": seed,
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
        progress_callback = cast(
            Optional[Callable[[Dict[str, Any]], Any]], kwargs.get("progress_callback")
        )
        prompt: str = temp["prompt"]
        image: List[str] = temp["image"]
        video: str = temp["video"]

        detected_duration = await video_processor.detect_video_len(video)
        if detected_duration < 2:
            raise ValueError(
                f"wan2.7-videoedit 要求输入视频时长 >= 2s，当前={detected_duration:.3f}s"
            )
        if detected_duration > 10:
            raise ValueError(
                f"wan2.7-videoedit 要求输入视频时长 <= 10s，当前={detected_duration:.3f}s"
            )

        if not image:
            raise ValueError("wan2.7-videoedit 至少需要一张参考图")
        if len(image) > 4:
            raise ValueError("wan2.7-videoedit 最多支持4张参考图")

        image_urls = cast(List[str], await self._get_urls(image))
        video_url = await self._get_urls(video)

        media = [{"type": "video", "url": video_url}]
        media.extend(
            {"type": "reference_image", "url": image_url} for image_url in image_urls
        )

        input_data: Dict[str, Any] = {
            "prompt": prompt,
            "media": media,
        }

        negative_prompt = temp.get("negative_prompt")
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt

        req_duration = temp.get("duration", 0)
        if req_duration not in (0, None):
            if abs(float(req_duration) - detected_duration) > 0.5:
                raise ValueError(
                    "wan2.7-videoedit 要求 duration 与输入视频时长一致；"
                    f"当前 duration={req_duration}, video_duration={detected_duration:.3f}s"
                )

        parameters: Dict[str, Any] = {
            "resolution": temp.get("resolution", "1080P"),
            # duration=0 让平台自动使用输入视频时长，可避免与输入时长不一致
            "duration": 0,
            "audio_setting": temp.get("audio_setting", "origin"),
            "prompt_extend": temp.get("prompt_extend", False),
            "watermark": temp.get("watermark", False),
        }

        ratio = temp.get("ratio")
        if ratio:
            parameters["ratio"] = ratio

        seed = temp.get("seed")
        if seed is not None:
            parameters["seed"] = seed

        request_body = {
            "model": self.model_name,
            "input": input_data,
            "parameters": parameters,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        url = self.base_url + self.end_point  # type: ignore

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )

        log.info(f"wan2.7-videoedit response.status_code: {response.status_code}")
        log.info(f"wan2.7-videoedit response.content: {response.content}")
        if response.status_code >= 400:
            raise ValueError(
                f"wan2.7-videoedit 请求失败: {response.status_code} {response.text}"
            )

        res: dict = response.json()
        task_id = res.get("output", {}).get("task_id")
        log.info(f"wan2.7-videoedit task_id: {task_id}")
        if not task_id:
            raise ValueError(f"wan2.7-videoedit 未返回 task_id: {res}")

        polled = await self._wait_for_task_completion(
            task_id,
            progress_callback=progress_callback,
        )
        video_url = polled.get("video_url")
        if not video_url:
            raise ValueError(f"wan2.7-videoedit 任务成功但未返回 video_url: {polled}")

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=BaseMessage(
                        content=video_url,
                        type="video_edit,wan2.7-videoedit",
                    )
                )
            ]
        )

    async def _get_task_result(self, task_id: str) -> Dict[str, Any]:
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
        res = response.json().get("output", {})
        status = res.get("task_status") or res.get("status")
        if status == "SUCCEEDED":
            log.info(f"Task {task_id} is SUCCEEDED")
        else:
            log.info(f"Task {task_id} is {status}")
        return res


class Gen4AlephRunway(VideoEditBase):
    """
    runway的gen4_aleph模型
    """

    def model_post_init(self, __context: Any) -> None:
        self.client = AsyncRunwayML(api_key=self.api_key)

    async def ainvoke(  # type: ignore
        self,
        prompt: str,
        image: List[str],
        video: str,
        mask_image: Optional[str] = None,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        temp_dic = {
            "prompt": prompt,
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
        prompt = temp["prompt"]
        image_url = await self._get_urls(image)
        video_url = await self._get_urls(video)
        input = {
            "model": self.model_name,
            "video_uri": video_url,
            "prompt_text": prompt,
            "references": [
                {
                    "type": "image",
                    "uri": image_url[0],
                }
            ],
            "extra_headers": {"Content-Type": "application/json"},
        }
        self.client: AsyncRunwayML

        log.info(f"input: {input},开始调用genaleph模型")
        tt = await self.client.video_to_video.create(**input)
        task = await tt.wait_for_task_output()

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
        file_path = Path(file_name)
        if file_path.is_file():
            file = str(file_path.resolve())
        else:
            file = await get_file_path(file_name)
        response = await self.client.uploads.create_ephemeral(
            file=Path(file), timeout=self.timeout
        )
        return response.uri


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


class Qwen3vlDashscope(VideoEditBase):
    async def ainvoke(  # type: ignore
        self,
        input: Dict[str, str],
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        temp = json.dumps(input)
        return await super().ainvoke(temp, config, stop=stop, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        temp = cast(str, messages[0].content)
        data = json.loads(temp)
        video = data["video"]
        object = data["object"]
        local_path = await get_file_path(video)
        video_path = f"file://{local_path}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"video": video_path, "fps": 2},
                    {
                        "text": f"""你是一位视频编辑工作流的视频分析师，由于视频编辑大模型只能处理5秒的视频!!!(注意最多只有5秒！！！)，因此，你需要说出视频中{object}出现的开始时间和结束时间.
                     由于你只能看到一些帧数的图片，因此，当看到一些非整数时间时，可以扩大时间，要求结构化输出，结构如下:
                     由列表套列表的形式[[开始时间, 结束时间], [开始时间, 结束时间], ...]（结束时间和开始时间的差值最大5秒！！！），最后一段可以小于5秒，比如一个13秒的视频，{object}在第1.2秒出现直到结束，可以返回：
                     [[1,6],[6,11],[11,13]],只能返回结果，不能返回任何思考及中间过程"""
                    },
                ],
            }
        ]  # type: ignore
        response = await AioMultiModalConversation.call(
            api_key=self.api_key,  # type: ignore
            model=self.model_name,
            messages=messages,
        )
        res = response.output.choices[0].message.content[0]["text"]  # type: ignore
        log.info(f"qwen3vl_dashscope返回结果: {res}")
        return ChatResult(
            generations=[
                ChatGeneration(message=BaseMessage(content=res, type="qwen3vl"))
            ]
        )


qwen3vl_dashchat = Qwen3vlDashscope(**qwen3vl_dashscope.model_dump())

wanx = WanxDashscope(**wanx_dashscpoe.model_dump())

wan_videoedit27 = WanVideoEdit27Dashscope(**wan_videoedit27_dashscope.model_dump())

gen4aleph = Gen4AlephRunway(**gen4aleph_runway.model_dump())

qwendashchat = QwenDashscopeChat(**qwen_dashscope.model_dump())
