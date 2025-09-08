from mcp.server.fastmcp import FastMCP
from typing import Any
STUDENTS = {
    "mustafa_2024": {
        "user_id": "mustafa_2024",
        "name": "Mustafa",
        "active_cursor_position": {"topic_id": "00_prompt_engineering"},
    }
}

COURSES = {
    "PROMPT_ENGINEERING_101": {
        "course_id": "PROMPT_ENGINEERING_101",
        "toc": [
            {"name": "Prompt Engineering Fundamentals", "description": "Core concepts and principles"},
            {"name": "Six-Part Prompting Framework", "description": "Structured approach to prompting"},
            {"name": "Context Engineering Tutorial", "description": "Using context effectively"},
        ],
    }
}



TOPICS = {
    "00_prompt_engineering": {
        "title": "Introduction to Prompt Engineering",
        "content": "Learn the basics of prompt engineering - how to write clear instructions for AI systems.",
        "topic_id": "00_prompt_engineering",
        "content_resource_urls": {
            "01": "file://01_prompt_engineering.md",
            "02": "file://02_six_part_prompting_framework.md",
            "03": "file://03_context_engineering_tutorial.md"
        }
    }
}

mcp_app: FastMCP = FastMCP(name="STUDY_MODE_TOOLBOX", stateless_http=True,)

@mcp_app.tool(
    name="get_student_profile",
    description="Get basic student information for teaching"
)
def get_student_profile(user_id: str, auth_token: str) -> dict[str, Any]:
    if user_id in STUDENTS:
        return STUDENTS[user_id]
    raise ValueError(f"Student {user_id} not found")

@mcp_app.tool(
    name="get_course_basic_info", 
    description="Get basic course information"
)
def get_course_basic_info(course_id: str, auth_token: str) -> dict[str, Any]:
    if course_id in COURSES:
        return COURSES[course_id]
    raise ValueError(f"Course {course_id} not found")

@mcp_app.tool(
    name="get_table_of_contents",
    description="Get course modules list"
)
def get_table_of_contents(course_id: str, auth_token: str) -> dict[str, Any]:
    print(f"Getting table of contents for course {course_id}")
    if course_id in COURSES:
        toc = COURSES[course_id]["toc"]
        # Return a flat dictionary with each module as a key-value pair
        result = {"course_id": course_id, "total_modules": len(toc)}
        for i, module in enumerate(toc):
            result[f"module_{i}"] = f"{module['name']}: {module['description']}"
        return result
    raise ValueError(f"Course {course_id} not found")

@mcp_app.tool(
    name="get_personalized_content",
    description="Get content for a topic"
)
def get_personalized_content(topic_id: str, user_id: str, auth_token: str) -> dict[str, Any]:
    if topic_id in TOPICS:
        content_resource_urls = TOPICS[topic_id]["content_resource_urls"]
        result = {}
        # load content from resource urls from local filesystem
        for key, url in content_resource_urls.items():
            path = url.replace("file://", "./")
            with open(path, "r", encoding="utf-8") as f:
                result[key] = f.read()
        return result
    raise ValueError(f"Topic {topic_id} not found")

@mcp_app.tool(
    name="check_topic_completion",
    description="Check if student completed a topic"
)
def check_topic_completion(topic_id: str, user_id: str, auth_token: str) -> bool:
    if topic_id in TOPICS:
        return False  # Simple: nobody completed anything yet
    raise ValueError(f"Topic {topic_id} not found")

@mcp_app.tool(
    name="get_current_topic",
    description="Get student's current topic"
)
def get_current_topic(user_id: str, auth_token: str) -> dict[str, Any]:
    if user_id in STUDENTS:
        student = STUDENTS[user_id]
        topic = TOPICS.get(student["active_cursor_position"]["topic_id"], {})
        content_resource_urls = topic["content_resource_urls"]
        result = {}
        # load content from resource urls from local filesystem
        for key, url in content_resource_urls.items():
            path = url.replace("file://", "./")
            with open(path, "r", encoding="utf-8") as f:
                result[key] = f.read()

        return {
            "topic_id": student["active_cursor_position"]["topic_id"],
            "topic_details": topic,
            "topic_content_data": result
        }

streamable_http_app = mcp_app.streamable_http_app()
