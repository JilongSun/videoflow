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
from typing import Literal, Annotated, Union, Any, Dict
import json

client = lark.Client.builder().app_id(lark.APP_ID).app_secret(lark.APP_SECRET).build()  # type: ignore


def send_message(
    content: Union[str, list, Dict], chat_type: Literal["p2p", "group"], message_id: str
):
    send = json.dumps({"text": content})
    if chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(message_id)
                .msg_type("text")
                .content(send)
                .build()
            )
            .build()
        )
        # 使用发送OpenAPI发送消息
        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.message.create(request)

        if not response.success():
            raise Exception(
                f"client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    else:
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder().content(send).msg_type("text").build()
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
