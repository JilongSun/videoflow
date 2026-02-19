# 加载 .env 文件中的环境变量
import os, asyncio
from dotenv import load_dotenv

load_dotenv()
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequestBody,
    CreateMessageRequest,
    ReplyMessageRequest,
    P2ImMessageReceiveV1,
    ReplyMessageRequestBody,
)
from .utils import send_message
from typing import Literal, Annotated, Union, Any
import json, httpx, asyncio

messagetype = Union[
    Literal["text"], Literal["post"]
]  # 消息类型，text 纯文本或 post 富文本，目前用户发送一张图片必然是富文本，因为有空格


# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    message_type: messagetype = data.event.message.message_type
    content = ""
    if message_type == "text":
        temp = json.loads(data.event.message.content)["text"]
        content = temp
        if not "@_" in content:
            return
    elif message_type == "post":
        at_count = 0
        temp: list[dict] = json.loads(data.event.message.content)["content"]
        for item in temp:
            for subitem in item:
                if subitem["tag"] == "img":
                    content += f'**{subitem["image_key"]}**'
                elif subitem["tag"] == "text":
                    content += subitem["text"]
                elif subitem["tag"] == "at":
                    at_count += 1
        if at_count == 0:
            return
    else:
        content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"
    if data.event.message.chat_type == "p2p":
        send_message("已收到请求", data.event.message.chat_type, data.event.message.chat_id)  # type: ignore
    else:
        send_message("已收到请求", data.event.message.chat_type, data.event.message.message_id)  # type: ignore

    async def func():
        httpx.post(
            "http://localhost:8000/chat/chat",
            json={
                "content": content,
                "feishu": [data.event.message.chat_type, data.event.message.message_id],
            },
            timeout=999999,
        )

    # if data.event.message.parent_id is None and data.event.message.root_id is None:
    #     asyncio.create_task(func())


# 注册事件回调
# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)


# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.

wsClient = lark.ws.Client(
    lark.APP_ID,  # type: ignore
    lark.APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)


def main():
    #  启动长连接，并注册事件处理器。
    #  Start long connection and register event handler.
    wsClient.start()


async def amain():
    async def inner():
        await asyncio.to_thread(main)

    asyncio.create_task(inner())


if __name__ == "__main__":
    main()
    # asyncio.run(amain())
