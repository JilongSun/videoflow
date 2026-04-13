import os
import sys
import asyncio
from typing import List

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

from videoflow.core.chatmodel import wanx, wan_videoedit27


def _split_images(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_task_id(result) -> str:
    return result


async def test_wanx_vace_video_edit_api():
    """
    运行前设置环境变量：
    TEST_VIDEO_PATH, TEST_IMAGE_PATHS, TEST_MASK_IMAGE_PATH, TEST_PROMPT
    可选：TEST_MASK_FRAME_ID, TEST_MASK_TYPE, TEST_EXPAND_RATIO
    """
    video = os.getenv("TEST_VIDEO_PATH")
    image_paths = _split_images(os.getenv("TEST_IMAGE_PATHS", ""))
    mask_image = os.getenv("TEST_MASK_IMAGE_PATH")
    prompt = os.getenv(
        "TEST_PROMPT", "将视频中的产品替换为参考图中的产品，其他内容不变"
    )

    if not (video and image_paths and mask_image):
        print("[SKIP] test_wanx_vace_video_edit_api 缺少必要环境变量")
        return

    result = await wanx.ainvoke(
        prompt=prompt,
        image=image_paths,
        video=video,
        mask_image=mask_image,
        mask_frame_id=int(os.getenv("TEST_MASK_FRAME_ID", "1")),
        mask_type=os.getenv("TEST_MASK_TYPE", "tracking"),
        expand_ratio=float(os.getenv("TEST_EXPAND_RATIO", "0.05")),
        prompt_extend=os.getenv("TEST_PROMPT_EXTEND", "false").lower() == "true",
        watermark=os.getenv("TEST_WATERMARK", "false").lower() == "true",
    )
    task_id = _get_task_id(result)
    print(f"[wanx2.1-vace-plus] task_id={task_id}")


async def test_wan27_videoedit_api():
    video = "test_0_3.mp4"
    image_paths = ["feishu_6c8f309df53g.png"]
    prompt = "将视频中的猫替换为参考图中的猫，其他内容不变"

    result = await wan_videoedit27.ainvoke(
        prompt=prompt, image=image_paths[:4], video=video, duration=0
    )
    task_id = _get_task_id(result)
    print(f"[wan2.7-videoedit] task_id={task_id}")


async def get(id):
    result = await wan_videoedit27._get_task_result(id)
    print(f"查询结果: {result}")


async def main():
    # await test_wanx_vace_video_edit_api()
    await test_wan27_videoedit_api()


if __name__ == "__main__":
    # asyncio.run(main())
    asyncio.run(get("513a08a6-64db-414c-8dc7-ec5d7f0d6b4b"))
