from langchain.agents import create_agent
from langchain.tools import tool
from langchain.agents.middleware import after_model, AgentState
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.runtime import Runtime
from videoflow.utils import log
from videoflow.core.chatmodel import qwendashchat
from videoflow.demo.feishu.utils import send_message, polling_reply_message
from videoflow.mcps.client import MCPServerStreamableHttp
import asyncio, json


VIDEOFLOW_MCP_URL = "http://127.0.0.1:18070/mcp"


@tool
async def search_video(keyword: str, publish_time: str = "1") -> str:
    """搜索抖音视频，返回候选视频链接列表

    Args:
        keyword: 视频搜索关键词
        publish_time: 发布时间筛选，"1"=最近1天
    """
    async with MCPServerStreamableHttp(
        params={"url": VIDEOFLOW_MCP_URL, "timeout": 9999},
        name="videoflow-mcp",
    ) as mcp:
        result = await mcp.call_tool("tool_search_video", {
            "keyword": keyword,
            "publish_time": publish_time,
        })
        return str(result.content)


@tool
async def run_video_workflow(
    image_url: str,
    video_keyword: str,
    message_id: str,
    video_url: str = "",
) -> str:
    """执行完整的视频编辑工作流，会自动处理视频选择的人机交互

    Args:
        image_url: 图片HTTP URL
        video_keyword: 视频搜索关键词
        message_id: 飞书 message_id，用于人机交互
        video_url: 直接提供视频URL则跳过搜索（可选）
    """
    async with MCPServerStreamableHttp(
        params={"url": VIDEOFLOW_MCP_URL, "timeout": 9999},
        name="videoflow-mcp",
    ) as mcp:
        args = {
            "image_url": image_url,
            "video_keyword": video_keyword,
        }
        if video_url:
            args["video_url"] = video_url

        result = await mcp.call_tool("tool_run_video_workflow", args)
        result_text = result.content[0].text  # type: ignore
        result_data = json.loads(result_text)

        if result_data.get("status") == "pending_selection":
            # 需要人工选择视频 → 通过飞书交互
            candidates = result_data["candidates"]
            session_id = result_data["session_id"]

            send_msg_id = await asyncio.to_thread(
                send_message,
                "\n".join(candidates) + "\n请选择一个视频",
                "group",
                message_id,
            )
            # 轮询飞书等待用户回复
            reply = await polling_reply_message(send_msg_id)
            content = json.loads(reply)["text"]
            content = "http" + content.split("http")[1]

            # 恢复工作流
            resume_result = await mcp.call_tool("tool_resume_video_workflow", {
                "session_id": session_id,
                "selected_video_url": content,
            })
            return str(resume_result.content)

        return str(result.content)


@after_model
async def send_to_feishu(state: AgentState, runtime: Runtime):
    """发送到飞书"""
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
    system_prompt="""你是ai助手，你需要根据用户的问题，调用自己所持有的工具或者工作流，来解决用户的需求，或者回答用户的一些日常问题。
    作为一名助手，说话要谨慎简洁，只能回答自己能力范围的问题，只能按照自己所拥有的工具的能力来回答。
    同时你在执行每一步时都要告诉用户你在干什么，比如在调用工具时，你需要告诉用户你调用什么工具，在你觉得缺少调用工具的参数时，也可以先询问用户你缺少什么参数。
    由于用户通常是通过飞书沟通的，会有系统提示词告诉你message_id,用来作为工作流的启动参数，不是通过飞书时就不会有message_id这个参数。
    """,
    tools=[search_video, run_video_workflow],
    middleware=[send_to_feishu],
)
