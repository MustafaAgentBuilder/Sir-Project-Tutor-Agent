import chainlit as cl
from contextlib import aclosing
from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent
import asyncio
import json

# Import the agent setup
from main import get_tutor_agent, cleanup_mcp_servers

@cl.on_chat_start
async def start():
    print("🔍 Starting new Chainlit session")
    try:
        TutorAgent, Session, USER_ID, COURSE_ID, AUTH_TOKEN, mcp_servers = await get_tutor_agent()
        cl.user_session.set("TutorAgent", TutorAgent)
        cl.user_session.set("Session", Session)
        cl.user_session.set("USER_ID", USER_ID)
        cl.user_session.set("COURSE_ID", COURSE_ID)
        cl.user_session.set("AUTH_TOKEN", AUTH_TOKEN)
        cl.user_session.set("mcp_servers", mcp_servers)

        # Debug: List available tools
        tools = await TutorAgent.get_all_tools(None)
        print(f"🛠️ Available tools: {tools}")

        cl.user_session.set("history", [])

        initial_session_message = (
            f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; "
            f"action=greet , auth_token={AUTH_TOKEN}"
        )

        print("🚀 Sending greeting to TutorAgent:", initial_session_message)

        # Placeholder
        msg = cl.Message(content="(waiting for agent response...)")
        await msg.send()

        ai_response = Runner.run_streamed(TutorAgent, initial_session_message, session=Session)

        final_output = ""
        async with aclosing(ai_response.stream_events()) as events:
            async for event in events:
                print("EVENT (on_chat_start):", event.type)
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    token = event.data.delta
                    final_output += token
                    await msg.stream_token(token)
                await asyncio.sleep(0)  # Yield to prevent task cancellation

        msg.content = final_output or "(⚠️ No response from agent)"
        await msg.update()

        # Save history
        history = cl.user_session.get("history", [])
        history.append({"role": "assistant", "content": msg.content})
        cl.user_session.set("history", history)

    except ValueError as ve:
        error_text = f"⚠️ Setup error: {str(ve)}"
        print(error_text)
        await cl.Message(content=error_text).send()
        await cleanup_mcp_servers(cl.user_session.get("mcp_servers", []))
    except Exception as e:
        error_text = f"⚠️ Agent setup failed: {str(e)}"
        print(error_text)
        await cl.Message(content=error_text).send()
        await cleanup_mcp_servers(cl.user_session.get("mcp_servers", []))

@cl.on_chat_end
async def end():
    mcp_servers = cl.user_session.get("mcp_servers", [])
    print("🧹 Initiating cleanup in on_chat_end")
    await cleanup_mcp_servers(mcp_servers)
    cl.user_session.set("mcp_servers", [])
    print("🔌 Disconnected all MCP servers")

@cl.on_message
async def main(message: cl.Message):
    TutorAgent = cl.user_session.get("TutorAgent")
    Session = cl.user_session.get("Session")
    USER_ID = cl.user_session.get("USER_ID")
    COURSE_ID = cl.user_session.get("COURSE_ID")
    AUTH_TOKEN = cl.user_session.get("AUTH_TOKEN")

    if TutorAgent is None or Session is None:
        await cl.Message(content="⚠️ Agent not initialized. Please restart the chat.").send()
        return

    # Preprocess input to extract user_input for tool calls
    user_input = message.content
    runtime_input = {
        "user_id": USER_ID,
        "course_id": COURSE_ID,
        "user_input": user_input,
        "auth_token": AUTH_TOKEN
    }
    runtime_input_str = json.dumps(runtime_input)
    print("🚀 Sending runtime input to TutorAgent:", runtime_input_str)

    # Placeholder
    msg = cl.Message(content="")
    await msg.send()

    ai_response = Runner.run_streamed(TutorAgent, runtime_input_str, session=Session)

    final_output = ""
    async with aclosing(ai_response.stream_events()) as events:
        async for event in events:
            print("EVENT (on_message):", event.type)
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                token = event.data.delta
                final_output += token
                await msg.stream_token(token)
            await asyncio.sleep(0)  # Yield to prevent task cancellation

    msg.content = final_output or "(no response)"
    await msg.update()

    # Update history
    history = cl.user_session.get("history", [])
    history.append({"role": "user", "content": message.content})
    history.append({"role": "assistant", "content": msg.content})
    cl.user_session.set("history", history)