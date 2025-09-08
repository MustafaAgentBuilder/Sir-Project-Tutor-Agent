# World-Class Tutor Agent System using Gemini (OpenAI-compatible) SDK
# Architecture: Multi-Agent System with MCP Tools for GitHub Integration

import asyncio
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import requests
from dotenv import load_dotenv, find_dotenv
from prompts import TUTOR_AGENT_PROMPT, PERSONALIZATION_AGENT_PROMPT

# OpenAI Agents SDK imports
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, ModelSettings, SQLiteSession , set_tracing_disabled , trace , set_tracing_export_api_key
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from openai.types.shared import Reasoning
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.response_input_text_param import ResponseInputTextParam

# Load environment variables
_: bool = load_dotenv(find_dotenv())
set_tracing_disabled(False)

# ============================================================================
# 1. DATA STRUCTURES & CONFIGURATIONS
# ============================================================================
set_tracing_export_api_key("openai_api_key_for_tracing")
@dataclass
class StudentContext:
    """Student profile and learning context"""
    user_id: str
    name: str
    background: str
    current_skill_level: str  # "beginner", "intermediate", "advanced"
    learning_goals: List[str]
    preferred_pace: str  # "slow", "medium", "fast"
    time_constraints: str
    learning_style: str  # "visual", "hands-on", "theoretical", "mixed"
    completed_topics: List[str]
    current_topic: Optional[str] = None
    auth_token: str = "tutor_session_2024"

# ============================================================================
# 2. SYSTEM PROMPTS FOR AGENTS (imported from teacher_agent.prompts)
# ============================================================================

# ============================================================================
# 3. DUMMY STUDENT DATA
# ============================================================================

DUMMY_STUDENT = StudentContext(
    user_id="mustafa_2024",
    name="Mustafa",
    background="Computer Science student from Sialkot with basic Python knowledge, interested in AI and web development. Has worked on small projects but new to Prompt Engineering.",
    current_skill_level="intermediate",
    learning_goals=["Master Prompt Engineering", "Build real-world applications with OpenAI SDK", "Understand MCP tools integration"],
    preferred_pace="medium",
    time_constraints="2-3 hours per week, prefer evening sessions on weekdays",
    learning_style="hands-on",
    completed_topics=[],
    auth_token="student_session_2024"
)

# ============================================================================
# 4. MCP SERVER CONFIGURATION
# ============================================================================

MCP_SERVER_URL = "http://localhost:8000/mcp/"  # Your MCP server URL


# Topics presented to the learner at entry
TEACHING_TOPICS = [
    "Prompt Engineering",
    "Six Part Prompting Framework",
    "Context Engineering Tutorial",
]

# ============================================================================
# 5. MAIN TUTOR AGENT IMPLEMENTATION
# ============================================================================

class WorldClassTutorSystem:
    """Main system orchestrating the tutor agents"""
    
    def __init__(self):
        # Initialize Gemini client via OpenAI-compatible API
        # Reference: https://ai.google.dev/gemini-api/docs/openai
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        
        self.student = DUMMY_STUDENT
        self.current_repo = 'repo1'
        self.session = None
        self.tutor_agent = None
        self.personalization_agent = None
    
    def _build_easy_input(self, text: str) -> list[EasyInputMessageParam]:
        """Construct structured input message for Runner.run using EasyInputMessageParam."""
        return [
            EasyInputMessageParam(
                role="user",
                type="message",
                content=[
                    ResponseInputTextParam(
                        text=text,
                        type="input_text",
                    )
                ],
            )
        ]
    
    async def initialize_agents(self):
        """Initialize both Tutor Agent and Personalization Agent"""
        
        # Create or reuse persistent session (do not clear so history remains visible)
        self.session = SQLiteSession(session_id=f"tutor_{self.student.user_id}")
        
        # MCP enabled: connect to local MCP toolbox to fetch course content
        mcp_params = MCPServerStreamableHttpParams(url=MCP_SERVER_URL)
        self.mcp_server_client = MCPServerStreamableHttp(
            params=mcp_params,
            name="STUDY_MODE_TOOLBOX",
            cache_tools_list=False,
        )
        await self.mcp_server_client.connect()
        mcp_servers_list = [self.mcp_server_client]
        
        # Initialize Main Tutor Agent
        self.tutor_agent = Agent(
            name="Sir Junaid's AI Co-Teacher",
            mcp_servers=mcp_servers_list,
            model=OpenAIChatCompletionsModel(
                model="gemini-2.5-flash", 
                openai_client=self.client
            ),
            instructions=TUTOR_AGENT_PROMPT.format(
                assistant_name="TutorGPT",
                co_teacher_name="Sir Junaid",
                user_id=self.student.user_id,
                course_id="PROMPT_ENGINEERING_101",
                auth_token=self.student.auth_token,
                student_name=self.student.name,
                level=self.student.current_skill_level,
                style=self.student.learning_style,
                goals=", ".join(self.student.learning_goals),
                topics_line=", ".join(TEACHING_TOPICS),
            ),
            model_settings=ModelSettings(
                temperature=0.7, 
                reasoning=Reasoning(effort="high")
            ),
        )
        
        # Initialize Personalization Agent (MCP disabled)
        self.personalization_agent = Agent(
            name="Content Personalization Specialist",
            mcp_servers=mcp_servers_list,
            model=OpenAIChatCompletionsModel(
                model="gemini-2.5-flash", 
                openai_client=self.client
            ),
            instructions=PERSONALIZATION_AGENT_PROMPT.format(
                user_id=self.student.user_id,
                student_background=self.student.background,
                skill_level=self.student.current_skill_level,
                learning_style=self.student.learning_style,
                learning_goals=", ".join(self.student.learning_goals),
                preferred_pace=self.student.preferred_pace
            ),
            model_settings=ModelSettings(
                temperature=0.8, 
                reasoning=Reasoning(effort="medium")
            ),
        )
    
    async def send_entry_welcome(self) -> str:
        """Send the minimal welcome message via LLM when user enters the app."""
        greeting_prompt = (
            "I am a Co-teacher of Sir Junaid. "
            "I will teach you this content. "
            "Are you ready to begin?"
        )
        result = await Runner.run(
            starting_agent=self.tutor_agent,
            input=greeting_prompt,
            session=self.session,
        )
        return result.final_output.strip()

    async def start_learning_session(self):
        """Start the interactive learning session"""
        try:
            await self.initialize_agents()
            
            print("🚀 Initializing Junaid's World-Class AI Co-Teacher...")
            print("=" * 70)
            
            # Single tracing scope for the entire session
            with trace("Tutor AI - session"):
                # Minimal welcome output
                welcome = await self.send_entry_welcome()
                print(f"🤖 [TUTOR AGENT]: {welcome}")
                print("=" * 70)
                
                # Interactive learning loop
                while True:
                    user_input = input(f"\n👨‍🎓 [{self.student.name}]: ")
                    
                    if user_input.lower() in ['exit', 'quit', 'bye']:
                        print("\n🎓 Thank you for learning with Junaid's AI Co-teacher!")
                        print("Your progress has been saved. See you next time! 🌟")
                        break
                    
                    # Process user input through main tutor agent
                    result = await self._process_learning_interaction(user_input)
                    print(f"\n🤖 [TUTOR AGENT]: {result}")
                    
                    # Check if personalization is needed → handoff to personalization agent, then continue tutoring
                    if self._needs_personalization(user_input):
                        tutor_followup = await self._handoff_personalization_then_continue(user_input)
                        if tutor_followup:
                            print(f"\n🤖 [TUTOR AGENT]: {tutor_followup}")
        
        except Exception as e:
            print(f"❌ An error occurred during the learning session: {e}")
    
    async def _process_learning_interaction(self, user_input: str) -> str:
        """Process user interaction through the tutor agent"""
        try:
            # Add context about current learning state
            enhanced_input = f"""
            Student Input: {user_input}
            
            Available MCP tools:
            - get_table_of_contents(course_id, auth_token)
            - get_current_topic(user_id, auth_token)
            - get_personalized_content(topic_id, user_id, auth_token)
            
            Use tools when needed to fetch course TOC or content. Keep responses concise.
            """
            
            result = await Runner.run(
                starting_agent=self.tutor_agent,
                input=enhanced_input,
                session=self.session,
            )
            
            return result.final_output
        
        except Exception as e:
            return f"I'm having a technical moment! Let me help you in a different way: {str(e)}"
    
    def _needs_personalization(self, user_input: str) -> bool:
        """Determine if input requires personalization agent"""
        personalization_triggers = [
            'explain', 'help me understand', 'can you adapt', 'make it easier',
            'too difficult', 'too easy', 'more examples', 'personalize'
        ]
        return any(trigger in user_input.lower() for trigger in personalization_triggers)
    
    async def _get_personalized_plan(self, recent_input: str) -> Optional[str]:
        """Ask personalization agent for a concise learning plan only (tutor keeps teaching)."""
        try:
            personalization_request = f"""
            Student background: {self.student.background}
            Level: {self.student.current_skill_level}; Style: {self.student.learning_style}
            Goals: {', '.join(self.student.learning_goals)}
            Recent student input: {recent_input}

            Task: Return a SHORT plan (not the full lesson) to tailor the upcoming teaching.
            Output JSON keys: plan_steps (3 short bullets), adjustments (2 bullets), estimated_time (string).
            Keep it concise and actionable; the tutor will continue teaching.
            """
            
            result = await Runner.run(
                starting_agent=self.personalization_agent,
                input=personalization_request,
                session=self.session,
            )
            
            return result.final_output
        
        except Exception as e:
            return f"Personalization temporarily unavailable. Continuing with standard teaching approach."

    async def _handoff_personalization_then_continue(self, recent_input: str) -> Optional[str]:
        """Handoff to personalization agent for a short plan, then feed that plan back to the tutor to continue teaching."""
        plan = await self._get_personalized_plan(recent_input)
        if not plan:
            return None
        tutor_prompt = f"""
        Incorporate this short personalized study plan and continue teaching the next step succinctly.
        Plan:
        {plan}
        """
        result = await Runner.run(
            starting_agent=self.tutor_agent,
            input=tutor_prompt,
            session=self.session,
        )
        return result.final_output.strip()

# 7. MAIN EXECUTION
# ============================================================================

async def main():
    """Main execution function"""
    print("🌟 Junaid's World-Class AI Co-Teacher")
    print("Powered by Gemini API (OpenAI-compatible) & MCP Tools")
    print("🚀 Starting learning session...")

    # Initialize and start the tutor system
    tutor_system = WorldClassTutorSystem()

    # Start the interactive learning session
    await tutor_system.start_learning_session()

if __name__ == "__main__":
    # Run the main tutor system
    asyncio.run(main())
    
    # Uncomment to run demo scenario
    # asyncio.run(demo_teaching_scenario())