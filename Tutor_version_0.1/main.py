# main.py
import asyncio
import os
from dotenv import load_dotenv, find_dotenv

from agents import (
    Agent,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    Runner,
    SQLiteSession,
    set_tracing_disabled
)
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from PROMPTS.tutor_prompt import TUTOR_AGENT_FINAL_PROMPT

# Load env
load_dotenv(find_dotenv())

# Provider setup (Gemini, OpenAI-compatible mode)
Provider = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=Provider,
)

# Disable tracing
set_tracing_disabled(True)

# Tavily Key
tavily_api = os.getenv('TAVILY_API_KEY')

async def get_tutor_agent():
    """
    Create and return (TutorAgent, session, USER_ID, COURSE_ID, AUTH_TOKEN, mcp_servers).
    Prepares and connects MCP servers. Caller must handle cleanup.
    Raises ValueError if no MCP servers can be connected.
    """
    print("🔍 Starting get_tutor_agent")
    # Define MCP server URLs
    SERVER_URL_1 = "http://localhost:8001/mcp"
    SERVER_URL_2 = f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api}"

    # MCP parameters
    mcp_params_1 = MCPServerStreamableHttpParams(url=SERVER_URL_1)
    mcp_params_2 = MCPServerStreamableHttpParams(url=SERVER_URL_2)

    print(f"MCP SERVER URL 1 -> {mcp_params_1}")
    print(f"MCP SERVER URL 2 -> {mcp_params_2}")

    mcp_servers = []

    # Server 1
    try:
        mcp_server_1 = MCPServerStreamableHttp(params=mcp_params_1, name="TutorMCPToolbox")
        await mcp_server_1.connect()
        mcp_servers.append(mcp_server_1)
        print(f"✅ Connected to {mcp_server_1.name}")
        # print(f"Cache Tools List Enabled: {mcp_server_1.cache_tools_list}")
    except Exception as e:
        print(f"❌ Failed to connect to TutorMCPToolbox: {e}")

    # Server 2
    try:
        mcp_server_2 = MCPServerStreamableHttp(params=mcp_params_2, name="TavilySearchMCP")
        await mcp_server_2.connect()
        mcp_servers.append(mcp_server_2)
        print(f"✅ Connected to {mcp_server_2.name}")
        # print(f"Cache Tools List Enabled: {mcp_server_2.cache_tools_list}")
    except Exception as e:
        print(f"❌ Failed to connect to TavilySearchMCP: {e}")

    if not mcp_servers:
        raise ValueError("⚠️ No MCP servers could be connected - agent will have no tools!")

    # Create SQLite session
    session = SQLiteSession(session_id="student_session.db")

    # Define USER_ID
    USER_ID = "Mustafa"
    
    # Format instructions with USER_ID
    instructions = TUTOR_AGENT_FINAL_PROMPT.format(
        co_teacher_name="Sir Junaid",
        assistant_name="Suzzi",
        auth_token=os.getenv("AUTH_TOKEN", "123131332432"),
        student_name=USER_ID  # Replace [student name] with USER_ID
    )
  


    # Create the agent with multiple MCP servers
    TutorAgent = Agent(
        name="TutorAgent",
        model=model,
        instructions=instructions,
        mcp_servers=mcp_servers,  # Pass connected servers
    )

    COURSE_ID = "PROMPT_ENGINEERING_101"
    AUTH_TOKEN = os.getenv("AUTH_TOKEN", "123131332432")

    # print(f"🎯 Agent created with {len(mcp_servers)} MCP servers")

    return TutorAgent, session, USER_ID, COURSE_ID, AUTH_TOKEN, mcp_servers
