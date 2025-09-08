

# 🚀 World-Class Tutor Agent

An AI-powered Tutor System built using the OpenAI Agents SDK and Gemini API, with support for MCP servers (optional) and a personalization agent for adaptive learning.

This system acts as a co-teacher to help students learn topics like Prompt Engineering, with adaptive responses, session memory, and tool integration.

---

## ✨ Features

* 🧑‍🏫 **Tutor Agent** – AI co-teacher that can answer questions and guide students.
* ⚙️ **MCP Integration (optional)** – Connects to MCP servers (e.g., GitHub tools, content fetchers).
* 🎯 **Personalization Agent** – Adjusts content based on student background, learning goals, and input.
* 💾 **Session Memory** – Saves student progress using SQLiteSession.
* 👋 **Welcome Message** – Greets the student with a personalized introduction.
* 🔄 **Interactive Loop** – Students can chat, ask for help, and exit anytime.

---

## 📂 Project Structure

```
.
├── main.py                     # Main entry point  
├── prompts.py                  # Tutor & personalization prompt templates  
├── .env                        # Store your API keys here  
├── requirements.txt            # Python dependencies  
└── README.md                   # Project documentation  
```

---

## ⚡ Requirements

* Python 3.11+
* `uv` or `pip` for running
* Gemini API key (Google AI)
* (Optional) MCP server running locally on port 8000

---

## 🔑 Setup

Clone the repo and install dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

(Optional) Run your MCP server (example with FastAPI + Uvicorn):

```bash
uvicorn my_mcp_server:app --host 127.0.0.1 --port 8000
```

---

## ▶️ Run the Tutor Agent

```bash
uv run main.py
```

You should see:

```
🚀 World-Class AI Co-Teacher (simplified)
============================================================

[TUTOR]: Hello Mustafa! I'm TutorGPT, your AI co-teacher for Prompt Engineering 101. Are you ready to begin?
```

---

## 💡 Example Interaction

```
[Mustafa]: explain more examples  
[TUTOR]: Sure! Here’s another example...  
[SYSTEM]: Personalization triggered. Generating short plan...  

[PERSONALIZATION PLAN]: {
  "plan_steps": ["Review basics", "Provide 3 examples"],
  "adjustments": "Simplify explanations",
  "estimated_time": "15 mins",
  "note": "Hands-on examples preferred"
}

[TUTOR - Personalized Followup]: Let’s break it down step by step...
```

---

## ⚙️ MCP Integration

MCP server URL is set in `main.py`:

```python
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"
```

If the server is not running, the system continues without MCP tools.

