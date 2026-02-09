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
)  # type: ignore
import json


# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    res_content = ""
    if data.event.message.message_type == "text":  # type: ignore
        res_content = json.loads(data.event.message.content)["text"]  # type: ignore
    else:
        res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

    content = json.dumps(
        {"text": f"收到你发送的消息：{res_content}\nReceived message:{res_content}"}
    )

    if data.event.message.chat_type == "p2p":  # type: ignore
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)  # type: ignore
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        # 使用发送OpenAPI发送消息
        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.message.create(request)  # type: ignore

        if not response.success():
            raise Exception(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    else:
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)  # type: ignore
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )
        # 使用回复OpenAPI回复消息
        # Use send OpenAPI to send messages
        # https://open.larkoffice.com/document/server-docs/im-v1/message/reply
        response: ReplyMessageResponse = client.im.v1.message.reply(request)  # type: ignore
        if not response.success():
            raise Exception(
                f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )


# 注册事件回调
# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)


# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.
client = lark.Client.builder().app_id(lark.APP_ID).app_secret(lark.APP_SECRET).build()  # type: ignore
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
    # main()
    asyncio.run(amain())