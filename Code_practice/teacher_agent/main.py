# main.py
# World-Class Tutor (simplified, with personalization + optional MCP)
# Fixed: indentation, prompts, MCP-safe handling, and JSON brace escaping.

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv, find_dotenv

# OpenAI Agents SDK imports
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, ModelSettings, SQLiteSession , set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from openai.types.shared import Reasoning
from prompts import TUTOR_AGENT_PROMPT, PERSONALIZATION_AGENT_PROMPT
# Load environment variables from .env
_ = load_dotenv(find_dotenv())


set_tracing_disabled(True)  # disable tracing for simplicity
# -------------------------
# Config (set these in .env)
# -------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # required
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"  # optional
MODEL_NAME = "gemini-2.5-flash"
SESSION_ID = "tutor_session_simple"

# -------------------------
# Data structures
# -------------------------
@dataclass
class StudentContext:
    user_id: str
    name: str
    background: str
    current_skill_level: str
    learning_goals: List[str]
    preferred_pace: str
    time_constraints: str
    learning_style: str
    completed_topics: List[str]
    current_topic: Optional[str] = None
    auth_token: str = "tutor_session_2024"

# Dummy student for testing
DUMMY_STUDENT = StudentContext(
    user_id="mustafa_2024",
    name="Mustafa",
    background="Computer Science student with basic Python knowledge, interested in AI and web development.",
    current_skill_level="intermediate",
    learning_goals=["Master Prompt Engineering", "Build applications with OpenAI SDK"],
    preferred_pace="medium",
    time_constraints="2-3 hours per week",
    learning_style="hands-on",
    completed_topics=[]
)


# -------------------------
# Main Tutor System
# -------------------------
class WorldClassTutorSystem:
    def __init__(self, student: StudentContext):
        # create Gemini (OpenAI-compatible) client
        self.client = AsyncOpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.student = student
        self.session = None
        self.tutor_agent = None
        self.personal_agent = None
        self.mcp_client = None

        # personalization trigger words
        self.personal_triggers = [
            "explain", "help me", "help me understand", "more examples",
            "too difficult", "too easy", "make it easier", "personalize"
        ]

    async def init_agents(self):
        """Initialize session, connect to MCP (optional), and create agents.
           If MCP not available we pass an empty list so Agent creation succeeds."""
        self.session = SQLiteSession(session_id=f"tutor_{self.student.user_id}")

        # Try connect to MCP server (optional). If it fails, use empty list.
        mcp_servers = []
        try:
            mcp_params = MCPServerStreamableHttpParams(url=MCP_SERVER_URL)
            self.mcp_client = MCPServerStreamableHttp(params=mcp_params, name="STUDY_MODE_TOOLBOX", cache_tools_list=False)
            await self.mcp_client.connect()
            mcp_servers = [self.mcp_client]
            print(f"[SYSTEM] Connected to MCP server: {MCP_SERVER_URL}")
        except Exception as e:
            print(f"[SYSTEM] Could not connect to MCP server ({MCP_SERVER_URL}). Running without MCP. Error: {e}")

        # Create Tutor agent (pass list even if empty)
        tutor_instructions = TUTOR_AGENT_PROMPT.format(
            assistant_name="TutorGPT",
            co_teacher_name="Sir Junaid",
            user_id=self.student.user_id,
            course_id="PROMPT_ENGINEERING_101",
            auth_token=self.student.auth_token,
            student_name=self.student.name,
            level=self.student.current_skill_level,
            style=self.student.learning_style,
            goals=", ".join(self.student.learning_goals),
            topics_line="Prompt Engineering, Six Part Prompting Framework, Context Engineering Tutorial",
        )

        self.tutor_agent = Agent(
            name="Sir Junaid's AI Co-Teacher",
            mcp_servers=mcp_servers,  # ALWAYS a list (maybe empty)
            model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=self.client),
            instructions=tutor_instructions,
            model_settings=ModelSettings(temperature=0.7, reasoning=Reasoning(effort="high")),
        )

        # Create Personalization agent.
        personal_instructions = PERSONALIZATION_AGENT_PROMPT.format(
            user_id=self.student.user_id,
            student_background=self.student.background,
            skill_level=self.student.current_skill_level,
            learning_style=self.student.learning_style,
            learning_goals=", ".join(self.student.learning_goals),
            preferred_pace=self.student.preferred_pace,
        )

        self.personal_agent = Agent(
            name="Content Personalization Specialist",
            mcp_servers=[],  # keep empty (personalization usually doesn't need MCP)
            model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=self.client),
            instructions=personal_instructions,
            model_settings=ModelSettings(temperature=0.6, reasoning=Reasoning(effort="low")),
        )

    async def send_entry_welcome(self) -> str:
        """Ask Tutor Agent to produce the welcome message (trigger greeting)."""
        # We send a clear instruction so the agent greets the student in the exact format.
        greeting_prompt = (
            "Greet the student exactly like this:\n"
            "Hello Mustafa! I'm TutorGPT, your AI co-teacher working with Sir Junaid for Prompt Engineering 101. Are you ready to begin?"
        )
        try:
            result = await Runner.run(self.tutor_agent, greeting_prompt, session=self.session)
            return result.final_output.strip()
        except Exception as e:
            return f"Error getting welcome from tutor: {e}"

    async def _process_learning_interaction(self, user_input: str) -> str:
        """Send user input to tutor agent (the tutor may use MCP tools if available)."""
        enhanced_input = (
            f"Student Input: {user_input}\n\n"
            f"Student Level: {self.student.current_skill_level}; Style: {self.student.learning_style}\n"
            "If tools are available, you may use them to fetch course content."
        )
        try:
            result = await Runner.run(self.tutor_agent, enhanced_input, session=self.session)
            return result.final_output
        except Exception as e:
            return f"Technical issue with tutor: {e}"

    def _needs_personalization(self, user_input: str) -> bool:
        low = user_input.lower()
        return any(t in low for t in self.personal_triggers)

    async def _get_personalized_plan(self, recent_input: str) -> Optional[str]:
        """Ask Personalization Agent for a short JSON plan (string)."""
        prompt = (
            f"Student background: {self.student.background}\n"
            f"Recent student input: {recent_input}\n\n"
            "Return the short JSON plan only (use keys plan_steps, adjustments, estimated_time, note)."
        )
        try:
            result = await Runner.run(self.personal_agent, prompt, session=self.session)
            return result.final_output.strip()
        except Exception as e:
            return f"Personalization error: {e}"

    async def _handoff_personalization_then_continue(self, recent_input: str) -> Optional[str]:
        """Get plan, then ask tutor to continue using that plan."""
        plan = await self._get_personalized_plan(recent_input)
        if not plan:
            return None
        tutor_prompt = (
            "Incorporate this short personalized plan and continue teaching the next step succinctly.\n\n"
            f"Plan:\n{plan}\n\n"
            f"Student Input: {recent_input}\n\n"
            "Now give one short, clear teaching response."
        )
        try:
            result = await Runner.run(self.tutor_agent, tutor_prompt, session=self.session)
            return result.final_output.strip()
        except Exception as e:
            return f"Error while tutor used plan: {e}"

    async def start_learning_session(self):
        """Main interactive loop."""
        await self.init_agents()
        print("🚀 Junaid's World-Class AI Co-Teacher (simplified)")
        print("=" * 60)

        welcome = await self.send_entry_welcome()
        print(f"\n[TUTOR]: {welcome}\n")

        while True:
            try:
                user_input = input(f"[{self.student.name}]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting. Goodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "bye"):
                print("🎓 Session ended. Progress saved.")
                break

            # Step 1: Tutor answers normally
            reply = await self._process_learning_interaction(user_input)
            print(f"\n[TUTOR]: {reply}\n")

            # Step 2: If personalization requested -> generate plan and ask tutor to continue
            if self._needs_personalization(user_input):
                print("[SYSTEM]: Personalization triggered. Generating short plan...")
                plan_text = await self._get_personalized_plan(user_input)
                print(f"\n[PERSONALIZATION PLAN]: {plan_text}\n")
                follow = await self._handoff_personalization_then_continue(user_input)
                print(f"\n[TUTOR - Personalized Followup]: {follow}\n")

# -------------------------
# Run program
# -------------------------
async def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Put GEMINI_API_KEY=your_key in a .env file.")
        return
    tutor_system = WorldClassTutorSystem(DUMMY_STUDENT)
    await tutor_system.start_learning_session()

if __name__ == "__main__":
    asyncio.run(main())
