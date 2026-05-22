# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

AI-powered learning assistant — chat app where users ask questions and get AI tutoring. An intent Router classifies every message into intents (chat/profile/resource/path/tutor/assessment). Resource intents trigger parallel generation across up to 6 resource agents (document/mindmap/quiz/video/code/reading), each with anti-hallucination review. Path/Tutor/Assessment agents run independently. A persistent student profile is built by extracting 7 learning dimensions from each conversation.

## Stack

- **Backend**: Python 3.14+ / FastAPI / SQLAlchemy (async) / SQLite (aiosqlite) / uv / LangGraph / LangChain
- **LLM**: OpenAI-compatible API (defaults to Qwen3-Max via Alibaba DashScope)
- **Frontend**: React 19 / TypeScript / Vite / Zustand / react-markdown / markmap (mind map)
- **Auth**: JWT (python-jose, HS256, 7-day expiry) + bcrypt password hashing

## Commands

```bash
# Backend
cd backend
uv sync                          # install Python deps
cp .env.example .env             # then edit OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
uv run python main.py            # start dev server on port 8000

# Frontend
cd frontend
npm install
npm run dev                      # start Vite dev server (proxied to :8000)
npm run build                    # typecheck + production build
npm run lint                     # ESLint
```

## Architecture

### Backend (`backend/`)

| File | Role |
|---|---|
| `main.py` | FastAPI app — 14 endpoints (auth, conversations, chat, profile, materials, exercises, resources). SSE chat endpoint calls Router for intent classification, then runs agent pipeline dynamically based on intents. Background tasks handle profile extraction and exercise parsing. **Critical**: the chat endpoint must `return StreamingResponse(event_stream(), media_type="text/event-stream")` — missing this causes blank responses. |
| `auth.py` | JWT creation/verification via python-jose, bcrypt password hashing. `get_current_user` FastAPI dependency (HTTPBearer). All routes protected. |
| `models.py` | 6 SQLAlchemy tables: `users` (1:N conversations, 1:1 profile, 1:N exercises), `conversations` (1:N messages), `messages`, `student_profiles` (7 learning dimensions), `exercises` (question_type, options as JSON string, answer, explanation), `resources` (resource_type, topic, content, file_name, reviewed). |
| `multi_agent.py` | Router + agent pipeline orchestrator. `detect_intent()` calls coordinator for intent classification. `run_agent_pipeline()` executes intents via LangGraph state graph: send_response → profile (serial) → resource (parallel) → path → tutor → assessment → finalize. All JSON-producing agents use `hidden_delta` during generation — raw JSON never reaches chat. Clean content is streamed after `_parse_agent_output()` (+ anti-hallucination for resource agents). Mindmap content auto-wrapped with `<!--MINDMAP-->` markers. |
| `agent_prompts.py` | System prompts for 12 agents: Coordinator (intent classification → JSON), 6 resource agents (Document/Quiz/Mindmap/VideoScript/CodeExample/Reading), Path/Tutor/Assessment agents, Anti-Hallucination reviewer, and Profile analyzer (7 dimensions). |
| `exercise_parser.py` | Two parsers: `parse_exercises_from_content()` for legacy markdown-format exercises, `parse_exercises_from_json()` for Quiz agent's structured JSON output. Choice questions: option-group–anchored. Fill-blank: `___` validation. True-false: keyword extraction (正确/错误). Deduplicates by question text. |
| `profile_agent.py` | Extracts 7 dimensions from conversation history via LLM. Merges non-empty values into `StudentProfile`. |
| `openai_client.py` | Singleton `AsyncOpenAI` client. `stream_chat` (async generator, max_tokens=4096), `chat_complete` (full string). Loads config from `backend/.env`. |
| `database.py` | Async SQLAlchemy engine + session factory (`sqlite+aiosqlite`). `async_session` context manager for inline DB ops. |
| `schemas.py` | Pydantic models for API request/response shapes. |

### Frontend (`frontend/src/`)

| File | Role |
|---|---|
| `App.tsx` | Auth gate, manages panel state (`"materials" | "exercises" | null`), wires `exerciseCount` + `onShowExercises` to ChatArea. |
| `hooks/useAuth.ts` | Zustand store: token, user, isAuthenticated, login/register/logout/checkAuth actions. |
| `hooks/useConversations.ts` | Zustand store: conversations, messages, streamingContent, agentStatus, progress, completed, totalResources, exerciseCount, sendMessage (SSE consumer). |
| `api/chat.ts` | All backend endpoint wrappers. `chatWithStream` reads SSE via ReadableStream, dispatches callbacks. **Hidden deltas** (`parsed.hidden`) are skipped — not added to streamingContent. `onComplete` receives `(total, quizTotal)`. |
| `components/ChatArea.tsx` | Routes to ExercisePanel/MaterialsPanel (no active chat), or MessageList+ChatInput (active chat). Shows ProgressBar + agentStatus during generation. |
| `components/MessageList.tsx` | Renders messages + streamingContent. Shows completion notices: "查看学习资料 →" (when totalResources>0) and "开始练习 →" (when exerciseCount>0). |
| `components/ProgressBar.tsx` | Visual progress bar: gradient fill track + `{current}/{total}` step label. Receives `ProgressEvent` from store. |
| `components/MarkdownView.tsx` | Splits content by `<!--FILE:-->`/`<!--ENDFILE-->` and `<!--MINDMAP-->`/`<!--ENDMINDMAP-->` markers. File segments → FileCard. Mindmap segments → MindMapView (interactive SVG). Code blocks → Prism. Remaining → ReactMarkdown. |
| `components/MindMapView.tsx` | Renders markdown nested lists as SVG mind map via `markmap-lib` + `markmap-view`. Also supports Mermaid diagram syntax. PNG download button (SVG → Canvas → PNG at 2x). |
| `components/ExercisePanel.tsx` | Interactive quiz browser: filter by type, grouped by subject. Choice/TrueFalse/FillBlank exercises with answer checking. |
| `components/FileCard.tsx` | Downloadable file card (icon, name, size, download). |
| `components/MaterialsPanel.tsx` | Lists historical learning materials with section icons. |
| `types/index.ts` | TypeScript interfaces: Conversation, Message, User, Exercise, StudentProfile, Resource, ProgressEvent. |

## SSE protocol

The agent pipeline streams content via Server-Sent Events. All SSE lines are `data: <json>\n\n`.

| Event | Format | Notes |
|---|---|---|
| delta | `{"delta":"..."}` | Token-by-token content, rendered in chat |
| hidden delta | `{"hidden":true,"delta":"..."}` | Skipped by frontend — raw JSON from agent generation |
| status | `{"type":"status","status":"正在生成..."}` | Agent status bar text |
| progress | `{"type":"progress","current":1,"total":3,"label":"...","resource_type":"..."}` | ProgressBar component input |
| save resource | `{"type":"_save","rtype":"...","topic":"...","content":"...","reviewed":true}` | Intercepted by main.py, saved as Resource row |
| save quiz | `{"type":"_save_quiz","rtype":"quiz","topic":"...","content":"..."}` | Intercepted by main.py, parsed inline → Exercise rows |
| complete | `{"type":"complete","total":3,"quiz_total":5}` | End of agent output; triggers completion notices |
| done | `data: [DONE]\n\n` | End-of-stream sentinel |

## Agent pipeline execution order

```
Router (detect_intent) → yield coordinator response
                       → [profile node, serial]
                       → [resource agents, parallel via asyncio.gather]
                         → hidden_delta (raw JSON, not rendered)
                         → anti_hallucination review
                         → clean delta (reviewed content, rendered)
                       → [path node] → hidden_delta → clean delta
                       → [tutor node] → hidden_delta → clean delta
                       → [assessment node] → hidden_delta → clean delta
                       → finalize → save events → complete → [DONE]
```

LangGraph state graph chain: send_response → profile → resource_router → path → tutor → assessment → finalize → END. Conditional edges route based on which intents are present. The coordinator response is streamed immediately; agent content is streamed only after parsing and (for resources) anti-hallucination review.

## Key behaviors

### Intent routing
- Every user message goes through the **Router** (coordinator) for intent classification. Returns `intents`, `target_topic`, `target_resource_types`, and a `response`.
- If intents only contain `["chat"]`, no agents run — only the coordinator's response is sent, character by character.
- `["profile"]` triggers inline profile extraction (serial, before other agents).
- `["resource"]` triggers parallel resource agent generation. `target_resource_types` determines which agents run (defaults to document+mindmap+quiz).
- `["path"]`, `["tutor"]`, `["assessment"]` trigger their respective agents.

### Content visibility
- **All JSON-wrapped agent output is hidden** during generation — tokens are sent as `hidden_delta` and skipped by both main.py and the frontend.
- After parsing (`_parse_agent_output`) and anti-hallucination review (for resources), **clean content is streamed** as regular `delta` with a section header (e.g. `## 📖 课程讲解文档`).
- Mindmap content is auto-wrapped with `<!--MINDMAP-->...<!--ENDMINDMAP-->` markers so the frontend renders it as an interactive SVG with PNG download.

### Quiz → Exercise flow
- Quiz agent output is sent as `_save_quiz` (not `_save`). Main.py intercepts this, calls `parse_exercises_from_json()`, and saves **Exercise rows directly** (not as Resource).
- Quiz content is **never shown in chat**. Instead, a completion notice with "开始练习 →" button appears.
- Legacy markdown-format exercises (from Resources) are still extracted via background task.

### Profile & exercise extraction
- Profile extraction runs as a **background task** after every response (silently fails, never blocks).
- Exercise extraction from Resources runs as a background task. Quiz exercises are saved **inline** during the SSE loop.

### Data
- Conversation titles are derived from the first user message (truncated to 40 chars).
- Database is auto-created on first run (SQLite file `backend/chat.db`). Delete to reset.
- All API endpoints except auth register/login are protected by `get_current_user` JWT dependency.
- Exercise parser is sensitive to LLM output format: choice questions need `A.`/`B.`/`C.`/`D.` option lines; fill-blanks need `___` markers; true-false answers need 正确/错误 keywords; answers need `答案：X` or `> 💡 答案与解析` blocks.

## Configuration

Backend `.env` keys (see `backend/.env.example`):

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | API key for OpenAI-compatible provider | (required) |
| `OPENAI_BASE_URL` | Base URL override (e.g., DashScope `https://dashscope.aliyuncs.com/compatible-mode/v1`) | OpenAI default |
| `OPENAI_MODEL` | Model name | `gpt-4o` |
