from langchain.agents import create_agent
from langchain.tools import tool
from langchain.agents.middleware import after_model, AgentState
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.runtime import Runtime
from videoflow.utils import log
from .chatmodel import qwendashchat
from .graph import workflow_manager, video_flow_workflow

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
    system_prompt=qwendashchat.prompt,
    tools=[workflow_manager.get_num, video_flow_workflow.ainvoke],
    middleware=[send_to_feishu],
)
