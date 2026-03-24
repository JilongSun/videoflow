from typing import List, Optional, Union
from videoflow.utils.crawlers.crawler import crawler
from videoflow.utils import log


async def search_video(
    keyword: str, publish_time: Optional[Union[int, str]] = "1"
) -> List[str]:
    """搜索抖音视频，返回候选视频链接列表

    Args:
        keyword: 视频搜索关键词
        publish_time: 发布时间筛选，1=最近1天，7=最近7天

    Returns:
        视频分享链接列表
    """
    log.info(f"search_video: keyword={keyword}, publish_time={publish_time}")
    results = await crawler.search_video(keyword, publish_time)
    if not results:
        log.warning(f"search_video: 未找到相关视频, keyword={keyword}")
        return []
    return results
