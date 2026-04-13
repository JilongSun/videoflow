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


def _get_video_url(result) -> str:
    return str(result)


async def test_wanx_vace_video_edit_api():
    video = os.getenv("TEST_VIDEO_PATH")
    image_paths = _split_images(os.getenv("TEST_IMAGE_PATHS", ""))
    mask_image = os.getenv("TEST_MASK_IMAGE_PATH")
    prompt = os.getenv("TEST_PROMPT", "将视频中的产品替换为参考图中的产品，其他内容不变")

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
    video_url = _get_video_url(result)
    print(f"[wanx2.1-vace-plus] video_url={video_url}")


async def test_wan27_videoedit_api():
    video = os.getenv("TEST_VIDEO_PATH")
    image_paths = _split_images(os.getenv("TEST_IMAGE_PATHS", ""))
    prompt = os.getenv("TEST_PROMPT", "将视频中的产品替换为参考图中的产品，其他内容不变")

    if not (video and image_paths):
        print("[SKIP] test_wan27_videoedit_api 缺少必要环境变量")
        return

    seed_env = os.getenv("TEST_WAN27_SEED")
    seed = int(seed_env) if seed_env else None

    result = await wan_videoedit27.ainvoke(
        prompt=prompt,
        image=image_paths[:4],
        video=video,
        negative_prompt=os.getenv("TEST_NEGATIVE_PROMPT"),
        resolution=os.getenv("TEST_WAN27_RESOLUTION", "1080P"),
        duration=0,
        ratio=os.getenv("TEST_WAN27_RATIO"),
        audio_setting=os.getenv("TEST_WAN27_AUDIO_SETTING", "origin"),
        prompt_extend=os.getenv("TEST_WAN27_PROMPT_EXTEND", "false").lower() == "true",
        watermark=os.getenv("TEST_WAN27_WATERMARK", "false").lower() == "true",
        seed=seed,
    )
    video_url = _get_video_url(result)
    print(f"[wan2.7-videoedit] video_url={video_url}")


async def main():
    await test_wanx_vace_video_edit_api()
    await test_wan27_videoedit_api()


if __name__ == "__main__":
    asyncio.run(main())
