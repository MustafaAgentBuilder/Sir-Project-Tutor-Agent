# chainlit_app.py
import chainlit as cl
from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent
import asyncio

# Import the agent setup (which no longer runs the greeting)
from main import get_tutor_agent

# Keys for the session (main returns these too)
TutorAgent = None
Session = None
USER_ID = None
COURSE_ID = None
AUTH_TOKEN = None

@cl.on_chat_start
async def start():
    global TutorAgent, Session, USER_ID, COURSE_ID, AUTH_TOKEN

    # Create the agent & session (does NOT run greeting)
    TutorAgent, Session, USER_ID, COURSE_ID, AUTH_TOKEN = await get_tutor_agent()

    # Initialize history in user session
    cl.user_session.set("history", [])

    # Build greeting input for the agent
    initial_session_message = f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; action=greet , auth_token={AUTH_TOKEN}"

    # Create an empty message in UI and stream the greeting into it
    msg = cl.Message(content="")
    await msg.send()

    # Stream the greeting from the agent into UI
    ai_response = Runner.run_streamed(TutorAgent, initial_session_message, session=Session)

    async for event in ai_response.stream_events():
        # stream token deltas into the open UI message
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            token = event.data.delta
            await msg.stream_token(token)

    # after streaming is done, fill final content and update message
    msg.content = ai_response.final_output
    await msg.update()

    # store greeting in history
    history = cl.user_session.get("history", [])
    history.append({'role': 'assistant', 'content': ai_response.final_output})
    cl.user_session.set("history", history)


@cl.on_message
async def main(message: cl.Message):
    # Build runtime input with session info
    runtime_input = f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; user_input={message.content} , auth_token={AUTH_TOKEN}"

    # Create a streaming message placeholder
    msg = cl.Message(content="")
    await msg.send()

    # Run agent in streaming mode and stream tokens to UI
    ai_response = Runner.run_streamed(TutorAgent, runtime_input, session=Session)

    async for event in ai_response.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            token = event.data.delta
            await msg.stream_token(token)

    # update final message
    msg.content = ai_response.final_output
    await msg.update()

    # Update history
    history = cl.user_session.get("history", [])
    history.append({'role': 'user', 'content': message.content})
    history.append({'role': 'assistant', 'content': ai_response.final_output})
    cl.user_session.set("history", history)
