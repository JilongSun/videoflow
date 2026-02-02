from videoflow.utils import log
from ..file_processor import read_file, write_file
from ..file_processor.video_processor import video_processor
from typing import Union, Optional
from tikhub_sdk_v2.rest import ApiException
import os, httpx, json, asyncio, uuid, tikhub_sdk_v2


class Crawler:
    def __init__(
        self,
    ):
        """
        初始化 douyin 爬虫工具
        tikhub_sdk_v2改成了上下文打开方式
        with self.tikhub_client(configuration) as api_client:
            api_instance = tikhub_sdk_v2.TikTokAppV3APIApi(api_client)
        """
        if api_key := os.getenv("TIKHUB_API_KEY", None):
            self.api_key = "Bearer " + api_key.strip()
        else:
            raise ValueError("TIKHUB_API_KEY is not set")
        self.base_url = "https://api.tikhub.io"

        log.info(f"爬虫工具初始化完成，API_KEY: {self.api_key}")
        self.configuration = tikhub_sdk_v2.Configuration(host=self.base_url)
        self.configuration.access_token = self.api_key
        self.tikhub_client = tikhub_sdk_v2.ApiClient

    async def search_video(
        self, target: str, publish_time: Optional[Union[int, str]] = "1"
    ):
        if isinstance(publish_time, int):
            publish_time = str(publish_time)
        endpoint = "/api/v1/douyin/search/fetch_video_search_v1"
        payload = {
            "keyword": target,
            "cursor": 0,
            "sort_type": "0",
            "publish_time": publish_time,
            "filter_duration": "0",
            "content_type": "0",
            "search_id": "",
            "backtrace": "",
        }
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        url = self.base_url + endpoint

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, json=payload, headers=headers, timeout=9999
            )
        name = uuid.uuid4().hex[:4]
        await write_file(f"{target}_{name}.json", response.content)
        log.info(f"搜索视频 {target} 完成，状态码: {response.status_code}")
        await asyncio.sleep(1)
        if response.status_code == 200:
            log.info(response.content)
            return response.content
        else:
            log.error(f"搜索视频 {target} 失败，状态码: {response.status_code}")
            return None

    async def download_video(
        self,
        url: str,
        file_name: Optional[str] = None,
        download_path: Optional[str] = None,
    ):
        success, video_id = await video_processor.video_download_fromweb(
            url,
            file_name=file_name,
            download_path=download_path,
        )
        return success, video_id


crawler = Crawler()
