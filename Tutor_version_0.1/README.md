# 📘 Tutor AI Agent with MCP Integration

This project creates an **AI Tutor Agent** that runs on top of the **OpenAI Agents SDK** with support for **MCP (Model Context Protocol) tools**. The agent can greet a student, fetch their course/session context dynamically, and maintain conversations across a session.

---

## 🚀 Features

* **Async Agent Execution** with `asyncio`
* **Dynamic Student + Course Context** passed at runtime
* **MCP Tool Integration** via HTTP (fetch student profile, topics, etc.)
* **SQLite Session Storage** to persist conversations
* **Tracing Support** (optional, can send logs to OpenAI’s tracing platform)
* **Customizable Instructions** through `v2_prompt.py`

---

## 📂 File Overview

* **`main.py`** → Main entry point (your provided code).
* **`v2_prompt.py`** → Stores the `STUDY_MODE_AGENT_FINAL_V3` prompt template.
* **`.env`** → Stores secrets like API keys.

---

## 🔑 Environment Variables (`.env`)

You must create a `.env` file with the following:

```env
GEMINI_API_KEY=your_google_gemini_api_key
TRACING_API_KEY=your_openai_tracing_key   # optional
```

---

## 📦 Dependencies

* `agents` (OpenAI Agents SDK)
* `dotenv` (load API keys)
* `asyncio` (async execution)
* `sqlite3` (session storage)

Install them:

```bash
pip install openai-agents python-dotenv
```

---

## 🛠️ Code Walkthrough

### 1. Load Environment

```python
_ = load_dotenv(find_dotenv())
```

Loads `.env` file so secrets (API keys) are available.

---

### 2. Provider Setup

```python
Provider = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
```

* **`AsyncOpenAI`**: Wrapper to call APIs asynchronously.
* **`base_url`**: Uses Google’s Gemini API (but in OpenAI-compatible format).

---

### 3. Model Definition

```python
model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash",
    openai_client=Provider,
)
```

* **Model**: `gemini-2.0-flash`
* **OpenAI-like API client**: Uses Gemini under the hood.

---

### 4. Tracing Setup

```python
set_tracing_disabled(True)
TRACING_KEY = os.getenv("TRACING_API_KEY")
if TRACING_KEY:
    set_tracing_export_api_key(TRACING_KEY)
```

* **Tracing** helps debug agent steps (tool calls, decisions).
* Disabled by default. If `TRACING_API_KEY` is set, logs will export to OpenAI Tracing.

---

### 5. MCP Server

```python
mcp_params = MCPServerStreamableHttpParams(url="http://localhost:8000/mcp")
async with MCPServerStreamableHttp(params=mcp_params, name="TutorMCPToolbox") as mcp_server:
```

* Connects agent to your MCP server at **`http://localhost:8000/mcp`**
* MCP tools will be available (like `get_student_profile`, `get_current_topic`, etc.)

---

### 6. Agent Setup

```python
instructions = STUDY_MODE_AGENT_FINAL_V3.format(
    co_teacher_name="Sir Junaid",
    assistant_name="Suzzi",
    auth_token="123131332432"
)
TutorAgent = Agent(
    name="TutorAgent",
    model=model,
    instructions=instructions,
    mcp_servers=[mcp_server],
)
```

* **Prompt Template**: Injects teacher’s name + assistant name.
* **Agent**: AI brain connected to MCP.

---

### 7. Dynamic Session Identity

```python
USER_ID = "student_01"
COURSE_ID = "PROMPT_ENGINEERING_101"
auth_token = "123131332432"
```

* Each session belongs to **one student + one course**.
* These IDs are passed dynamically to allow tool fetching.

---

### 8. Initial Greeting

```python
initial_session_message = (
    f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; action=greet  ,  auth_token = {auth_token}"
)
result = await Runner.run(starting_agent=TutorAgent, input=initial_session_message, session=session)
```

* Sends the **first hidden message**.
* Triggers agent greeting: “Hello, I am Suzzi, your co-tutor with Sir Junaid…”
* **This is not shown to the student directly.**

---

### 9. Interactive Loop

```python
while True:
    user_text = input("[USER]: ")
    if user_text.strip().lower() in ("exit", "quit"):
        break

    runtime_input = f"[SESSION] user_id={USER_ID}; course_id={COURSE_ID}; user_input={user_text} ,  auth_token = {auth_token}"
    with trace("TutorAgent Run"):
        result = await Runner.run(starting_agent=TutorAgent, input=runtime_input, session=session)
        print(result.final_output)
```

* Keeps asking the student for input.
* Always attaches `user_id` + `course_id` to messages so the agent knows which student it’s serving.
* Uses `trace` so you can debug runs if tracing is enabled.

---

### 10. Error Handling

```python
except Exception as e:
    print(f"Error during agent setup or runtime: {e}")
```

Prevents the agent from crashing silently.

---

## ⚡ How it Works (Flow)

1. **Startup**: Loads env, sets up provider, tracing, and MCP server.
2. **Agent Initialization**: Builds `TutorAgent` with your `STUDY_MODE_AGENT_FINAL_V3` prompt.
3. **Greeting**: Agent introduces itself when session starts.
4. **Interactive Chat**: Student inputs go in → Agent processes → MCP tools fetch needed data → Response back.
5. **Session Persistence**: Saved in SQLite (`student_session.db`).

---

✅ With this setup:

* **Prompts are dynamic** → You can swap `USER_ID` + `COURSE_ID` at runtime.
* **Hidden First Message** → Ensures the agent always greets properly.
* **MCP Connected** → Agent fetches student context in real-time.

