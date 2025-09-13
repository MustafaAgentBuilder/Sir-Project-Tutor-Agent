import asyncio
import os
from dotenv import load_dotenv, find_dotenv
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, ModelSettings, SQLiteSession , set_tracing_export_api_key,trace
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.response_input_text_param import ResponseInputTextParam
from prompts import STUDY_MODE_V2 , PERSONALIZED_TUTOR_V1
# Load environment variables from .env


_ = load_dotenv(find_dotenv())




Provider = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# Set up the chat completion model with the API provider.
model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=Provider,
)

set_tracing_export_api_key("Add_your_Openai_api_key")


async def main():
    mcp_params = MCPServerStreamableHttpParams(url="http://localhost:8000/mcp")
    async with MCPServerStreamableHttp(params=mcp_params,name="TutorMCPToolbox")as mcp_server:
        try:
            session = SQLiteSession(session_id="student_session")

            PersonizedTutorAgent = Agent(
                name="PersonizedTutorAgent",
                model=model,
                model_settings=ModelSettings(temperature=1),
                instructions=PERSONALIZED_TUTOR_V1.format(user_id="muhammad", course_id="AI-101", auth_token="1234567890", co_teacher_name="Sir Junaid", assistant_name="parry"),
                mcp_servers=[mcp_server],
            )
            
            
            TutorAgent = Agent(
                name="TutorAgent",
                model=model,
                model_settings=ModelSettings(temperature=0.7),
                instructions=STUDY_MODE_V2.format(user_id="muhammad", course_id="AI-101", auth_token="1234567890", co_teacher_name="Sir Junaid", assistant_name="parry"),
                mcp_servers=[mcp_server],
                tools=[
                    PersonizedTutorAgent.as_tool(
                        tool_name="personalized_tutor",
                        tool_description="Generates a personalized study plan based on the student's profile, learning style, goals, and current progress.",
                    
                    )
                ]
            )




            result = await Runner.run(starting_agent=TutorAgent, input="Hello",session=session)
            print(result.final_output)


            while True:
                user_input = input("[USER]: ")
                if user_input == "exit":
                    break
                with trace("TutorAgent Run"):

                    input_message = EasyInputMessageParam(
                        role="user",
                        type="message",
                        content=[
                            ResponseInputTextParam(
                                text=user_input,
                                type="input_text"
                            )
                        ]
                    )
                    result = await Runner.run(starting_agent=TutorAgent, input=input_message,session=session)
                    print(result.final_output)


        except Exception as e:
            print(f"An error occurred during agent setup or tool listing: {e}")

if __name__ == "__main__":
    asyncio.run(main())