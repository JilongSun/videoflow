import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv()
import asyncio
import pprint
from videoflow.utils.crawlers.crawler import crawler


async def test_search_video():
    keyword = "猫咪"
    print(f"\n[test_search_video] 关键词: {keyword}")
    result = await crawler.search_video(keyword)
    print(f"[test_search_video] 返回类型: {type(result)}")
    print(f"[test_search_video] 返回数量: {len(result) if result else 0}")
    print("[test_search_video] 返回结果:")
    pprint.pprint(result)
    return result


if __name__ == "__main__":
    asyncio.run(test_search_video())
