from videoflow.utils import log
from tikhub import Client
from ..file_processor import read_file, write_file
from typing import Union, Optional
import os, httpx, json, asyncio


class Crawler:
    def __init__(
        self,
    ):
        if api_key := os.getenv("TIKHUB_API_KEY", None):
            self.api_key = "Bearer " + api_key.strip()
        else:
            raise ValueError("TIKHUB_API_KEY is not set")
        self.base_url = "https://api.tikhub.io"

        log.info(f"爬虫工具初始化完成，API_KEY: {self.api_key}")

        self.tikhub_client = Client(api_key=self.api_key)

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
        log.info(f"搜索视频 {target} 完成，状态码: {response.status_code}")
        await asyncio.sleep(1)
        if response.status_code == 200:
            log.info(response.content)
            await write_file("aaa.json", response.content)
            return response.content
        else:
            log.error(f"搜索视频 {target} 失败，状态码: {response.status_code}")
            return None


crawler = Crawler()
