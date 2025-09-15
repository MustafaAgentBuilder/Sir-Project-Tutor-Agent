import asyncio
import os
from dotenv import load_dotenv, find_dotenv

from agents import (
    Agent,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    Runner,
    SQLiteSession,
    set_tracing_export_api_key,
    trace,
    set_tracing_disabled 
)
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from tutor_prompt import TUTOR_AGENT_FINAL_PROMPT

# Load env
_ = load_dotenv(find_dotenv())

# Model provider (keep your key in .env)
Provider = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=Provider,
)
set_tracing_disabled(True)

# Tracing key from env if you use tracing (do NOT hardcode)
TRACING_KEY = os.getenv("TRACING_API_KEY")
if TRACING_KEY:
    set_tracing_export_api_key(TRACING_KEY)

async def main():

    # Configure MCP server client so agent's tool calls go to http://localhost:8000/mcp
    mcp_params = MCPServerStreamableHttpParams(url="http://localhost:8000/mcp")
    async with MCPServerStreamableHttp(params=mcp_params, name="TutorMCPToolbox") as mcp_server:
        try:
            session = SQLiteSession(session_id="student_session.db")

            # Build instructions: only static safe fields (no user_id, no auth_token)
            instructions = TUTOR_AGENT_FINAL_PROMPT.format(
                co_teacher_name="Sir Junaid",
                assistant_name="Suzzi",
                auth_token = "123131332432"
            )

            TutorAgent = Agent(
                name="TutorAgent",
                model=model,
                instructions=instructions,
                mcp_servers=[mcp_server],
            )

            # ---------- DYNAMIC RUN: send user_id and course_id at runtime ----------
            # These are safe non-secret identifiers: agent will use them to call MCP tools.
            USER_ID = "student_01"
            COURSE_ID = "PROMPT_ENGINEERING_101"
            auth_token = "123131332432"

            # The first message tells the agent which student + course this session is for.
            # IMPORTANT: Do NOT include auth tokens here.
            initial_session_message = (
                f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; action=greet  ,  auth_token = {auth_token}"
            )

            # Run the agent; agent will call MCP tools (get_student_profile, get_current_topic, etc.)
            result = await Runner.run(starting_agent=TutorAgent, input=initial_session_message, session=session)
            print(result.final_output)

            # Interactive loop: every user message should include (or be associated with) the same user_id/course_id
            # We'll attach a small prefix to each user input so the agent knows the session identity.
            while True:
                user_text = input("[USER]: ")
                if user_text.strip().lower() in ("exit", "quit"):
                    break

                # Prepend session identity to the user message so agent can use it for tool calls
                runtime_input = f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; user_input={user_text} ,  auth_token = {auth_token}"
                with trace("TutorAgent Run"):
                    result = await Runner.run(starting_agent=TutorAgent, input=runtime_input, session=session)
                    print(result.final_output)

        except Exception as e:
            print(f"Error during agent setup or runtime: {e}")

if __name__ == "__main__":
    asyncio.run(main())
