from langchain.agents import create_agent
from langchain.tools import tool
from langchain.agents.middleware import after_model, AgentState
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.runtime import Runtime
from videoflow.utils import log
from .chatmodel import qwendashchat
from .graph import workflow_manager, video_flow_workflow
from videoflow.feishu.utils import send_message
import asyncio


@tool
async def get_weather(city: str) -> str:
    """
    获取城市的天气
    """
    return f"{city}的天气是晴朗的"


@after_model
async def send_to_feishu(state: AgentState, runtime: Runtime):
    """
    发送到飞书
    """
    log.info(f"触发send_to_feishu，这是state: {state}")
    messages = state["messages"][-1]
    if isinstance(messages, AIMessage):
        if runtime.context is not None:
            await asyncio.to_thread(
                send_message,
                messages.content,
                runtime.context.chat_type,
                runtime.context.message_id,
            )
            log.info(f"触发send_to_feishu，这是context: {runtime.context}")
    return None


supervised_agent = create_agent(
    model=qwendashchat,
    system_prompt="""你是ai助手，你需要根据用户的问题，调用自己做持有的工具或者工作流，来解决用户的需求，或者回答用户的一些日常问题。
    作为一名助手，说话要谨慎简介，只能回答自己能力范围的时候，只能按照自己所拥有的工具的能力来回答.
    同时你在执行每一步时都要告诉用户你在干什么，比如在调用工具时，你需要告诉用户你调用什么工具，在你觉得缺少调用工具的参数时，也可以先询问用户你缺少什么参数
    由于用户通常是通过飞书沟通的，会有系统提示词告诉你message_id,用来作为工作流的启动参数，不是通过飞书时就不会有message_id这个参数
    """,
    tools=[workflow_manager.get_num, video_flow_workflow.ainvoke],
    middleware=[send_to_feishu],
)
