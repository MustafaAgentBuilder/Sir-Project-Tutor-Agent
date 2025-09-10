# Tutor.AI — Complete Technical Developer Guide 

> **Purpose:** One clear, complete doc for your Sir and dev team.
> Balanced language so juniors and seniors can both follow. This includes architecture, schemas, connectors, error handling, scaling, security, deployment, local dev, and migration strategy — everything needed to build Tutor.AI + universal LMS integration.

---

# 1. Big Picture (Short)

* **Product:** Tutor.AI = AI Co-Teacher platform + universal LMS integration layer.
* **Modes:**

  * **Phase 1 (Now):** Standalone Tutor.AI app (teachers upload or link content).
  * **Phase 2 (Later):** Connector/MCP servers map Canvas, Moodle, Blackboard → **LMS-DM** (one internal schema). Tutor.AI works inside any LMS.
* **Core idea:** Build one Tutor.AI core that only understands LMS-DM. Build small connectors for each LMS that translate to/from LMS-DM.

---

# 2. Tech Stack (Explicit)

* **Language:** Python 3.10+ (type hints).
* **Web framework:** FastAPI (async). Run with **Uvicorn**.
* **LLM / Agent SDK:** OpenAI Agents SDK (or another provider SDK supporting tools).
* **Schema / Validation:** Pydantic for LMS-DM models.
* **DB:** PostgreSQL (primary). Use UUIDs, Alembic for migrations.
* **Cache / Broker:** Redis (cache, rate-limiter, Celery broker).
* **Background Jobs:** Celery or RQ (Redis-backed).
* **Containers:** Docker + docker-compose for local dev.
* **Cloud hosting:** Cloud Run / AWS ECS / Azure Container Instances or K8s for scale.
* **CI/CD:** GitHub Actions.
* **Secrets:** Cloud KMS (GCP) / AWS Secrets Manager / HashiCorp Vault.
* **Auth:** OAuth2 for LMS connectors; JWT for app users.
* **Observability:** Sentry (errors), Prometheus + Grafana (metrics), structured logs.
* **Version control:** GitHub. Course content versioned in GitHub repo (for Git-based AI-native LMS later).

---

# 3. Architecture (Text Diagram)

```
[Canvas / Moodle / Blackboard]  <--->  [Connector (per LMS) / MCP server]
                                              |
                                              v
                                       [API Gateway / LMS-DM Service]
                                              |
                                              v
                                   [Tutor.AI core (FastAPI + Agent SDK)]
                                              |
    -------------------------------------------------------------------------------
    |                         |                     |                          |
 [Web UI React/Vue]   [Background Workers]   [Postgres DB]    [Redis (cache & broker)]
```

* Connectors handle OAuth, rate-limits, mapping to LMS-DM.
* Tutor.AI core talks only LMS-DM. Connectors hide LMS differences.

---

# 4. LMS-DM — Minimal Schema (Pydantic)

Create `models/lms_dm.py`. Start small; extend later.

```python
from pydantic import BaseModel
from typing import Optional, List

class User(BaseModel):
    user_id: str
    name: str
    role: str  # "student" | "teacher"
    email: Optional[str]

class Course(BaseModel):
    course_id: str
    title: str
    description: Optional[str]
    instructor: Optional[User]

class Assignment(BaseModel):
    assignment_id: str
    course_id: str
    title: str
    due_date: Optional[str]  # ISO8601
    content: Optional[str]
    max_points: Optional[int]

class Submission(BaseModel):
    submission_id: str
    assignment_id: str
    user_id: str
    content_url: Optional[str]
    score: Optional[float]
    feedback: Optional[str]
```

---

# 5. Database Schema (Core Tables + Indexes)

Use UUID primary keys, sensible indexes.

**Core tables**

* `users` (id PK UUID, name, email, role, created\_at)
* `courses` (id PK, title, description, instructor\_id FK, source, source\_id, created\_at)
* `assignments` (id PK, course\_id FK, title, content, due\_date, max\_points)
* `submissions` (id PK, assignment\_id FK, user\_id FK, content\_url, score, feedback, created\_at)
* `connectors` (id, lms\_name, config json, status)
* `tokens` (id, user\_id, connector\_id, encrypted\_token, refresh\_token, expires\_at)
* `audit_logs` (id, user\_id, action, details json, created\_at)
* `jobs` (id, type, payload json, status, attempts, last\_error, created\_at, finished\_at)

**Index suggestions**

* `idx_assignments_course_id` on `assignments(course_id)`.
* `idx_submissions_user_id` on `submissions(user_id)`.
* `idx_courses_source` on `(source, source_id)`.
* Partition `audit_logs` and `submissions` by date when they grow large.
* Add read-replicas for reporting.

**Sample SQL (Postgres)**

```sql
CREATE TABLE courses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  instructor_id uuid REFERENCES users(id),
  source text NOT NULL,
  source_id text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_courses_source_sourceid ON courses(source, source_id);
```

---

# 6. Connector Design (Responsibilities & Endpoints)

Each connector (one per LMS) offers the same façade endpoints in LMS-DM.

**Responsibilities**

* Handle OAuth2 (or API token).
* Rate-limit, retry, and circuit-breaker for LMS API calls.
* Map LMS JSON → LMS-DM models (mapper module).
* Expose REST endpoints the Tutor.AI core can call.
* Push grades/content back to LMS on request.
* Audit logs for actions.

**Common MCP-style endpoints**

```
POST /auth                        -> store/refresh tokens
GET  /courses                     -> return [Course] in LMS-DM
GET  /courses/{id}/assignments    -> return [Assignment]
GET  /courses/{id}/content/{cid}  -> return raw content/text
POST /courses/{id}/assignments/{aid}/grade -> push grade
GET  /users/{id}/profile          -> return User
```

**Mapping example**

* Canvas `course.id` → LMS-DM `course_id`
* Canvas `assignment.due_at` → LMS-DM `due_date` (normalize to ISO8601)
* Moodle `fullname` → LMS-DM `title`

Keep `connectors/<lms_name>/mapper.py` for mapping functions.

---

# 7. Example Connector Code (Canvas sketch)

Use `httpx` (async) for production.

```python
# connectors/canvas/main.py (sketch)
from fastapi import FastAPI, Header, HTTPException
import httpx
from models.lms_dm import Course

app = FastAPI()
CANVAS_BASE = "https://canvas.instructure.com/api/v1"

@app.get('/courses')
async def get_courses(authorization: str = Header(...)):
    headers = {'Authorization': authorization}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{CANVAS_BASE}/courses", headers=headers)
    r.raise_for_status()
    canvas_courses = r.json()
    return [Course(course_id=str(c['id']), title=c.get('name',''),
                   description=c.get('course_code','')).dict()
            for c in canvas_courses]
```

Notes:

* Add pagination handling.
* Add retries with tenacity or custom logic.
* Store tokens securely.

---

# 8. Tutor.AI Core — FastAPI + Agent SDK (how it uses connectors)

Tutor.AI core orchestrates LLM/agent calls and calls connectors for data.

**Example: ask\_ai endpoint**

```python
from fastapi import FastAPI
from pydantic import BaseModel
from openai_agents import AgentClient  # pseudocode

app = FastAPI()
agent = AgentClient(api_key=...)

class AskIn(BaseModel):
    user_id: str
    course_id: str
    question: str

@app.post('/ai/ask')
async def ask_ai(data: AskIn):
    context = await call_connector_get_toc(data.course_id)  # tool call
    prompt = f"Context:\n{context}\nQuestion: {data.question}"
    resp = await agent.run(prompt)
    return {'answer': resp}
```

**Agent tools** (register these for the Agent SDK):

* `getStudentProfile(userID)`
* `getCourseBasicInfo(courseID)`
* `getTableOfContent(courseID)`
* `getPersonalizedContent(topicID, userID)`
* `pushGrade(assignmentID, userID, score)`

Tool implementations call connector endpoints (MCP).

---

# 9. Error Handling & Retry Strategies

**Principles**

* Always set network timeouts.
* Use exponential backoff for retries.
* Make calls idempotent where possible (use `idempotency_key`).
* Circuit breaker: open when many failures, pause calls for some time.
* Dead-Letter Queue (DLQ) for tasks that fail after N retries.

**Python example with tenacity**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30),
       retry=retry_if_exception_type(httpx.HTTPError))
def call_lms(url, headers):
    r = httpx.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()
```

**Background jobs**

* Celery tasks should use `retry()` with countdown.
* After max retries, move to DLQ (Redis list or `jobs` table with `status='failed'`) and create ops alert (Slack/email).

---

# 10. Background Job Failure Handling & DLQ

* Retry with exponential backoff (e.g., 3 attempts: 10s, 60s, 300s).
* If still failing, mark job `failed` and write to DLQ.
* Alert ops and show DLQ items in admin UI with a “Retry” button.
* Make tasks idempotent: use `job_id` and unique constraints to avoid duplicates.

---

# 11. API Rate Limiting & Throttling

**Two directions:**

* **Outgoing to LMS connectors**: respect LMS limits. Use per-connector token-bucket counters (Redis). Queue or delay requests when near limit.
* **Incoming to our APIs**: protect endpoints with per-user / per-IP limits. Use `slowapi` or `fastapi-limiter` (Redis-backed).

**Behavior**

* If exceeding: respond `429 Too Many Requests` with `Retry-After` header or queue the work for background processing.

---

# 12. Caching Strategy (beyond Redis basics)

* **CDN** (CloudFront/Cloudflare) for static assets and images.
* **Redis**: cache course TOC, small content blocks, rate-limit counters.
* **Cache-aside** pattern: read from cache; on miss read DB and set cache. TTL short for changing content (e.g., 60s).
* **Invalidate** caches on content updates; publish invalidation via Redis Channels.

---

# 13. Load Balancing & Horizontal Scaling

* Keep app stateless. Use JWT for sessions or Redis for shared session data.
* Use cloud Load Balancer in front of app instances.
* Autoscale based on CPU, latency, and queue length metrics.
* Use managed DB with read replicas.

---

# 14. Worker Scaling Logic

* Scale workers on queue length (e.g., scale up if queue > 100).
* Use Kubernetes HPA with custom metrics (queue length) from Prometheus.
* For spikes, use serverless tasks where possible.

---

# 15. Authentication Flows (Diagrams & Steps)

## A. Connector OAuth2 (Admin install)

```
[Admin] -> /connect/canvas/start -> Canvas OAuth consent -> redirect to /connect/canvas/callback?code=...
Our backend exchanges code -> Canvas returns access_token + refresh_token -> store encrypted
```

* Admin registers app on LMS side and sets redirect URI.
* Request only needed scopes (read\_courses, read\_submissions, write\_grades).
* Refresh tokens before expiry.

## B. App Users (JWT)

* `POST /login` -> validate -> return `access_token` (JWT, short-lived) + `refresh_token`.
* All requests use `Authorization: Bearer <access_token>`.
* Implement token revocation (blacklist) for logout.

---

# 16. Data Migration Strategy Between Phases

From Phase 1 (our app source-of-truth) → Phase 2 (LMS as source):

1. **Export/Normalize** Phase 1 content into LMS-DM JSON.
2. **Match & Map**: Find LMS course matches by (title + instructor + date). If ambiguous, ask admin to choose.
3. **Source flag**: mark `source = 'tutor-app'` or `source = 'canvas'`. If `connector` present, decide which is canonical (prefer LMS if connector exists, unless teacher opts otherwise).
4. **Backfill** with rate-limited jobs to import LMS content into tables.
5. **Conflict handling**: provide admin UI to resolve merges.
6. **Alembic migrations** for DB structural changes; test in staging; snapshot before run.

---

# 17. Local Development Setup (Step-by-step)

**Prereqs:** Docker, docker-compose, Python 3.10, Node (for UI), Git.

**Repo layout**

```
/tutorai
  /api
  /connectors/canvas
  /web
  docker-compose.yml
  .env.example
```

**.env.example**

```
DATABASE_URL=postgresql://postgres:example@postgres:5432/tutorai
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=sk-...
JWT_SECRET=super-secret
CANVAS_CLIENT_ID=...
CANVAS_CLIENT_SECRET=...
SENTRY_DSN=
```

**Quick local run**

1. `cp .env.example .env` and fill values.
2. `docker-compose up --build`
3. Backend: `http://localhost:8080/docs` (FastAPI docs).
4. Frontend: `http://localhost:3000`.
5. Use `ngrok` for OAuth webhooks: `ngrok http 8080`.

---

# 18. Docker & docker-compose (Starter files)

**Dockerfile** (FastAPI)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY pyproject.toml poetry.lock /app/
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . /app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**docker-compose.yml** (simplified)

```yaml
version: '3.8'
services:
  app:
    build: ./api
    ports: ['8080:8080']
    env_file: .env
  redis:
    image: redis:7
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: example
  worker:
    build: ./api
    command: celery -A app.worker worker --loglevel=info
    depends_on: ['redis','postgres']
  web:
    build: ./web
    ports: ['3000:3000']
```

---

# 19. Observability & Monitoring

* **Sentry** for error tracking (stack traces, user context).
* **Prometheus + Grafana** for metrics: request latency, error rate, queue length, DB connections.
* **Structured logs** (JSON) with request\_id and trace\_id.
* **Audit logs** for data access (who accessed student data, when).
* Alerts: DLQ depth, high error rate, worker crashes, LMS 5xx spikes.

---

# 20. Testing & QA

* **Unit tests** for mapping functions, model validation, auth flows.
* **Integration tests** with LMS sandbox (Canvas test instances). Use VCR/fixtures to record HTTP interactions.
* **E2E tests** (Playwright/Cypress) for web UI flows.
* **Security tests**: token leakage, scope denial, rate-limit enforcement.
* Add test coverage checks in CI.

---

# 21. API Documentation Strategy

* Use FastAPI's auto OpenAPI `/docs`.
* Publish Postman / Insomnia collection and examples.
* Use `/v1/` prefix for versioning. Maintain `API_CHANGES.md` for breaking changes.

---

# 22. MCP (Model Context Protocol) — Clear Definition & Usage

**Plain words:** MCP = a small standard for connectors to expose structured tool-like endpoints that agents can call. It’s how the LLM/Agent asks for data (TOC, student profile, content) and the connector responds with LMS-DM JSON.

**Tool example**

```json
{
  "name": "getTableOfContent",
  "args": { "courseID": "string", "authToken": "string" },
  "returns": { "topics": [ { "id":"", "title":"", "subtopics":[...] } ] }
}
```

* Agent calls connector endpoints as tools.
* Connector returns LMS-DM JSON.
* Agent uses it to generate answers, quizzes, or push grades.

---

# 23. Security & Compliance (FERPA/GDPR)

* **FERPA (US):** protect student records; maintain audit trails; implement least-privilege access.
* **GDPR (EU):** data export & deletion, consent logs.
* **Encryption:** AES-256 for tokens at rest; HTTPS/TLS in transit.
* **Data minimization:** fetch only needed fields.
* **Anonymization:** anonymize PII for model training unless consented.

---

# 24. Runbook (Short Ops)

* **Lost token:** revoke, notify admin, prompt re-auth.
* **Connector 5xx spike:** circuit-breaker open, alert ops, pause outgoing calls.
* **DLQ items:** check DLQ dashboard, inspect error, re-run after fix.
* **Slow queries:** check DB indexes, add read replica for heavy reads.
* **High queue length:** scale workers.

---

# 25. Development Checklist — Phase 1 (MVP)

1. Create repos: `tutorai/core`, `tutorai/connectors/canvas`, `tutorai/web`.
2. Implement `models/lms_dm.py`.
3. FastAPI scaffold: auth, health-check, `/ai/ask` endpoint.
4. OpenAI Agents SDK wrapper: `ask_ai`.
5. Canvas connector: `GET /courses`, `GET /courses/{id}/assignments`.
6. Minimal React UI: login, course list, AI chat, content upload.
7. Local dev with docker-compose, `.env.example`.
8. Unit tests + one Canvas sandbox integration test.
9. GitHub Actions: tests → build → push image.
10. Deploy to staging; test with 1 pilot course.

---

# 26. Development Checklist — Phase 2 (Integrations & UX)

1. Add Moodle & Blackboard connectors.
2. Build in-LMS widget (JS snippet / iframe / LTI where possible).
3. Implement grade push: `POST /push_grade` -> connector -> LMS.
4. Implement advanced agent tools: `generate_quiz`, `summarize_course`, `personalized_study_plan`.
5. Add analytics dashboard (dropped into admin panel).
6. Add enterprise onboarding docs for institutions.

---

# 27. Migration & Versioning Strategy

* Use Alembic for DB migrations. Test migrations in staging before prod.
* Keep content versioned in GitHub for AI-native LMS (Git-based commits).
* Provide migration scripts that map old data to LMS-DM. Snapshot DB before migrations.

---

# 28. FAQ (Short)

* **DLQ?** Dead-Letter Queue for failed background tasks.
* **Idempotent?** Design tasks so re-running doesn’t duplicate results.
* **Token security?** Encrypt tokens; use KMS/Vault.
* **How scale workers?** Autoscale based on queue length.

---

# 29. Next Immediate Steps (Actionable)

1. Create GitHub repos & invite devs.
2. Implement `models/lms_dm.py` and FastAPI scaffold.
3. Build Canvas connector with `GET /courses` and `GET /courses/{id}/assignments`.
4. Add OpenAI Agents SDK stub and `ai/ask` endpoint.
5. Local demo with docker-compose and run 1 pilot test.

---

# 30. Appendix — Useful Code Snippets

**Retry example (tenacity)**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30),
       retry=retry_if_exception_type(httpx.HTTPError))
def call_lms(url, headers):
    r = httpx.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()
```

**Canvas mapping snippet**

```python
# connectors/canvas/mapper.py
from models.lms_dm import Course

def canvas_to_course(c):
    return Course(
        course_id=str(c.get('id','')),
        title=c.get('name','Untitled Course'),
        description=c.get('course_code','')
    )
```

**.env.example**

```
DATABASE_URL=postgresql://postgres:example@postgres:5432/tutorai
REDIS_URL=redis://redis:6379/0
OPENAI_API_KEY=sk-...
JWT_SECRET=super-secret
CANVAS_CLIENT_ID=...
CANVAS_CLIENT_SECRET=...
SENTRY_DSN=
```

---

# Closing (One-line pitch)

**Tutor.AI** — Build one powerful AI co-teacher that plugs into every LMS, saves teachers time, personalizes student learning, and scales to institutions worldwide.

