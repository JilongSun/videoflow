from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from videoflow.core.agents import supervised_agent
from ..models.router_model import Chat2Model
from videoflow.utils import log
from langchain.messages import HumanMessage
from pydantic import BaseModel

__all__ = ["router"]


router = APIRouter(prefix="/chat", tags=["和大模型狗头，及调用工作流"])


class FeiShuId(BaseModel):
    chat_type: str
    message_id: str


@router.post("/chat")
async def chat_endpoint(
    request: Chat2Model,
):
    log.info(f"大模型接口接受参数: 用户输入：{request.content}")
    if request.feishu is not None:
        id = FeiShuId(chat_type=request.feishu[0], message_id=request.feishu[1])
        config = {"configurable": {"thread_id": id.message_id}}
        res = await supervised_agent.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=request.content + f"message_id: {id.message_id}"
                    )
                ]
            },
            config,
        )
    else:
        res = await supervised_agent.ainvoke(
            {"messages": [HumanMessage(content=request.content)]},
        )
    return {"content": res["messages"][-1].content}
