import json
import os

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import init_db, get_session, async_session
from models import Conversation, Message, StudentProfile, User, Exercise, Resource
from schemas import (
    ConversationOut, ConversationListItem, ChatRequest, ProfileOut,
    UserRegister, UserLogin, UserOut, TokenResponse,
)
from multi_agent import (
    detect_intent,
    run_agent_pipeline,
    get_pipeline_profile_updates,
)
from profile_agent import (
    extract_profile_dimensions,
    get_or_create_profile,
    update_student_profile,
    format_profile_for_context,
    format_profile_as_markdown,
)
from auth import hash_password, verify_password, create_access_token, get_current_user
from exercise_parser import parse_exercises_from_content


# ── 给定生成资源的后缀名 ─────────────────────────────────────────────────

FILE_EXTENSIONS = {
    "document": ".md", "quiz": ".md", "mindmap": ".md",
    "video": ".md", "code": ".py", "reading": ".md",
    "path": ".md", "tutor": ".md", "assessment": ".md",
}

FILE_LABELS = {
    "document": "课程讲解文档", "quiz": "配套练习题",
    "mindmap": "知识点思维导图", "video": "教学视频脚本",
    "code": "代码实操案例", "reading": "拓展阅读材料",
    "path": "学习路径规划", "tutor": "答疑辅导",
    "assessment": "学习效果评估",
}


def _generate_file_name(rtype: str, topic: str) -> str:
    label = FILE_LABELS.get(rtype, rtype)
    ext = FILE_EXTENSIONS.get(rtype, ".md")
    safe_topic = "".join(c for c in (topic or "未命名") if c not in r'\/:*?"<>|')[:40]
    return f"{safe_topic}_{label}{ext}"


# ── 创建App实例 ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Chat Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# 在创建 app 之后，添加静态文件挂载
static_dir = "/app/static" if os.path.exists("/app/static") else "../static"
if os.path.exists(static_dir):
    # 挂载静态文件
    app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")


    # 处理 SPA 路由：所有找不到的路径都返回 index.html
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        index_path = f"{static_dir}/index.html"
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return exc



# --- 认证识别接口(进行JWT令牌校验,和JAVA类似) ---

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(req: UserRegister, session: AsyncSession = Depends(get_session)):
    stmt = select(User).where(User.username == req.username)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(username=req.username, password_hash=hash_password(req.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, username=user.username, created_at=user.created_at),
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: UserLogin, session: AsyncSession = Depends(get_session)):
    stmt = select(User).where(User.username == req.username)
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, username=user.username, created_at=user.created_at),
    )


@app.get("/api/auth/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, created_at=user.created_at)


# --- 对话相关接口 ---

@app.post("/api/conversations")
async def create_conversation(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = Conversation(user_id=user.id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


@app.get("/api/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await session.execute(stmt)
    convs = result.scalars().all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in convs
    ]


@app.get("/api/conversations/{conv_id}")
async def get_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
        .options(selectinload(Conversation.messages))
    )
    result = await session.execute(stmt)
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in conv.messages
        ],
    }


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Verify ownership
    stmt = select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
    result = await session.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Conversation not found")

    await session.execute(delete(Message).where(Message.conversation_id == conv_id))
    await session.execute(delete(Conversation).where(Conversation.id == conv_id))
    await session.commit()
    return {"ok": True}


@app.post("/api/conversations/{conv_id}/chat")
async def chat(
    conv_id: str,
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
    result = await session.execute(stmt)
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update title from first user message
    if conv.title == "New Chat":
        conv.title = req.content[:40] + ("..." if len(req.content) > 40 else "")

    # Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=req.content)
    conv.updated_at = datetime.now(timezone.utc)
    session.add(user_msg)
    await session.commit()

    # Fetch full history
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in messages]

    # Load student profile
    profile = await get_or_create_profile(session, user.id)
    profile_context = format_profile_for_context(profile)

    # Call Router for intent classification (always)
    coordinator_result = await detect_intent(req.content, history, profile_context)
    intents = coordinator_result.get("intents", ["chat"])
    response_text = coordinator_result.get("response", "你好！有什么可以帮你的？")
    target_topic = coordinator_result.get("target_topic")
    target_resource_types = coordinator_result.get("target_resource_types", ["document", "mindmap", "quiz"])

    action_intents = [i for i in intents if i != "chat"]
    has_action = len(action_intents) > 0

    async def event_stream():
        accumulated = response_text
        resource_count = 0
        exercise_count = 0
        quiz_topics: list[str] = []

        if not has_action:
            for char in response_text:
                yield f"data: {json.dumps({'delta': char})}\n\n"
        else:
            try:
                async for event in run_agent_pipeline(
                        history=history,
                        user_content=req.content,
                        profile_context=profile_context,
                        intents=intents,
                        target_topic=target_topic,
                        target_resource_types=target_resource_types,
                        coordinator_response=response_text,
                ):
                    # Intercept _save_quiz events — parse JSON, save exercises inline
                    if '"_save_quiz"' in event:
                        try:
                            data = json.loads(event[6:].strip())
                            if data.get("type") == "_save_quiz":
                                from exercise_parser import parse_exercises_from_json as _parse
                                content = data["content"]
                                print(f"[quiz] Parsing quiz content, len={len(content)}, topic={data['topic'][:40]}", flush=True)
                                exercises = _parse(content, data["topic"])
                                print(f"[quiz] Parsed {len(exercises)} exercises", flush=True)
                                if exercises:
                                    async with async_session() as s:
                                        for i, q in enumerate(exercises):
                                            ex = Exercise(
                                                user_id=user.id, conversation_id=conv_id,
                                                message_id=None, subject=data["topic"][:80],
                                                question_type=q["question_type"],
                                                question_number=i + 1,
                                                question=q["question"],
                                                options=json.dumps(q.get("options", []), ensure_ascii=False),
                                                answer=q.get("answer", ""),
                                                explanation=q.get("explanation", ""),
                                            )
                                            s.add(ex)
                                        await s.commit()
                                    exercise_count += len(exercises)
                                    quiz_topics.append(data["topic"][:40])
                                    print(
                                        f"[quiz] Saved {len(exercises)} exercises for '{data['topic'][:40]}'",
                                        flush=True)
                                else:
                                    print(f"[quiz] WARNING: parse_exercises_from_json returned empty for '{data['topic'][:40]}', content preview: {content[:200]}", flush=True)
                                continue
                        except Exception as e:
                            print(f"[quiz] ERROR parsing/saving exercises: {e}", flush=True)
                            import traceback
                            traceback.print_exc()

                    # Intercept _save events — save as Resource (skip quiz)
                    if '"_save"' in event:
                        try:
                            data = json.loads(event[6:].strip())
                            if data.get("type") == "_save":
                                async with async_session() as s:
                                    r = Resource(
                                        user_id=user.id, conversation_id=conv_id,
                                        resource_type=data["rtype"], topic=data["topic"][:80],
                                        content=data["content"],
                                        file_name=_generate_file_name(data["rtype"], data["topic"]),
                                        reviewed=1 if data.get("reviewed") else 0,
                                    )
                                    s.add(r)
                                    await s.commit()
                                    resource_count += 1
                                    print(
                                        f"[resource] Saved {data['rtype']}: {data['topic'][:40]} ({len(data['content'])} chars)",
                                        flush=True)
                                continue
                        except Exception:
                            pass

                    # Skip hidden deltas (quiz JSON — not rendered in chat)
                    if '"hidden": true' in event:
                        continue

                    yield event
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            # Profile updates from pipeline
            profile_updates = get_pipeline_profile_updates()
            if profile_updates:
                try:
                    await update_student_profile(session, profile_updates, user.id)
                except Exception:
                    pass

            # Completion text
            parts: list[str] = []
            if resource_count > 0:
                parts.append(f"已为你生成 {resource_count} 个学习资料，点击下方按钮查看")
            if exercise_count > 0:
                topics_str = "、".join(quiz_topics)
                parts.append(f"已生成 {exercise_count} 道关于「{topics_str}」的练习题，点击下方按钮跳转练习")
            if parts:
                completion = "\n\n✅ " + "；".join(parts)
                accumulated += completion
                for char in completion:
                    yield f"data: {json.dumps({'delta': char})}\n\n"

        # Save assistant message
        try:
            assistant_msg = Message(conversation_id=conv_id, role="assistant", content=accumulated)
            session.add(assistant_msg)
            conv.updated_at = datetime.now(timezone.utc)
            await session.commit()
            print(f"[chat] Successfully saved assistant message for conv {conv_id}", flush=True)
        except Exception as e:
            print(f"[chat] Error saving assistant message: {e}", flush=True)
            await session.rollback()

        yield "data: [DONE]\n\n"

        if accumulated:
            extract_messages = history + [{"role": "assistant", "content": accumulated}]
            background_tasks.add_task(_extract_and_update_profile, extract_messages, user.id)
            # Quiz exercises are already saved inline above; this background
            # task only handles legacy markdown-format exercises from Resources.
            background_tasks.add_task(_extract_exercises_from_resources, conv_id, user.id, conv.title)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _extract_and_update_profile(messages: list[dict], user_id: str):
    """Background task: extract and update student profile."""
    try:
        from database import async_session
        new_dims = await extract_profile_dimensions(messages)
        if new_dims:
            async with async_session() as session:
                await update_student_profile(session, new_dims, user_id)
    except Exception:
        pass


async def _extract_exercises_from_resources(conv_id: str, user_id: str, subject: str):
    """Background task: parse quiz resources (JSON format) and extract exercises."""
    try:
        from database import async_session
        from exercise_parser import parse_exercises_from_json
        async with async_session() as session:
            stmt = select(Resource).where(
                Resource.conversation_id == conv_id,
                Resource.resource_type == "quiz",
            )
            result = await session.execute(stmt)
            quiz_resources = result.scalars().all()

            for quiz in quiz_resources:
                parsed = parse_exercises_from_json(quiz.content, subject)
                for i, q in enumerate(parsed):
                    exercise = Exercise(
                        user_id=user_id,
                        conversation_id=conv_id,
                        message_id=None,
                        subject=subject[:80],
                        question_type=q["question_type"],
                        question_number=i + 1,
                        question=q["question"],
                        options=json.dumps(q.get("options", []), ensure_ascii=False),
                        answer=q.get("answer", ""),
                        explanation=q.get("explanation", ""),
                    )
                    session.add(exercise)
            await session.commit()
    except Exception:
        pass


# --- 学生用户画像相关接口 ---

@app.get("/api/student/profile")
async def get_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await get_or_create_profile(session, user.id)
    return {
        "id": profile.id,
        "major_background": profile.major_background,
        "knowledge_base": profile.knowledge_base,
        "cognitive_style": profile.cognitive_style,
        "learning_goals": profile.learning_goals,
        "weak_points": profile.weak_points,
        "schedule_preference": profile.schedule_preference,
        "content_preference": profile.content_preference,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@app.post("/api/student/profile/extract")
async def extract_profile(
    req: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv_id = req.get("conversation_id")
    if not conv_id:
        raise HTTPException(status_code=400, detail="conversation_id required")

    # Verify conversation belongs to user
    conv_stmt = select(Conversation).where(
        Conversation.id == conv_id, Conversation.user_id == user.id
    )
    conv_result = await session.execute(conv_stmt)
    if not conv_result.scalars().first():
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in messages]

    new_dims = await extract_profile_dimensions(history)
    if new_dims:
        profile = await update_student_profile(session, new_dims, user.id)
        return {
            "id": profile.id,
            "major_background": profile.major_background,
            "knowledge_base": profile.knowledge_base,
            "cognitive_style": profile.cognitive_style,
            "learning_goals": profile.learning_goals,
            "weak_points": profile.weak_points,
            "schedule_preference": profile.schedule_preference,
            "content_preference": profile.content_preference,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
    return {"ok": False, "message": "No new dimensions extracted"}


@app.get("/api/student/profile/markdown")
async def get_profile_markdown(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await get_or_create_profile(session, user.id)
    return {"markdown": format_profile_as_markdown(profile)}

#——————TODO
# --- 学习资料接口(定义比较广泛) ---

MATERIAL_SECTION_MARKERS = [
    "## 📖 课程讲解文档",
    "## 🧠 知识点思维导图",
    "## ✏️ 配套练习题",
    "## 🎬 教学视频脚本",
    "## 💻 代码实操案例",
    "## 📚 拓展阅读材料",
    "## 🗺️ 学习路径规划",
    "## 💡 答疑辅导",
    "## 📊 学习效果评估",
]


@app.get("/api/materials")
async def list_materials(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return all multi-agent generated learning materials for the current user."""
    stmt = (
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user.id,
            Message.role == "assistant",
        )
        .order_by(Message.created_at.desc())
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    materials = []
    for msg in messages:
        # Check if this message contains multi-agent generated content
        found_sections = [m for m in MATERIAL_SECTION_MARKERS if m in msg.content]
        if not found_sections:
            continue

        # Get conversation title
        conv_stmt = select(Conversation.title).where(Conversation.id == msg.conversation_id)
        conv_result = await session.execute(conv_stmt)
        conv_title = conv_result.scalars().first() or "Unknown"

        # Extract subject from content (first heading or conversation title)
        subject = conv_title
        for line in msg.content.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                subject = line.lstrip("# ").strip()
                break

        # Build preview (skip section headers, take first meaningful paragraph)
        preview = ""
        skip_next = True
        for line in msg.content.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue
            preview = stripped[:120] + ("..." if len(stripped) > 120 else "")
            break

        materials.append({
            "message_id": msg.id,
            "conversation_id": msg.conversation_id,
            "conversation_title": conv_title,
            "subject": subject[:80],
            "preview": preview,
            "sections": found_sections,
            "created_at": msg.created_at.isoformat(),
        })

    return materials


# --- 练习题的接口 ---

@app.get("/api/exercises")
async def list_exercises(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return all parsed exercises for the current user."""
    stmt = (
        select(Exercise)
        .where(Exercise.user_id == user.id)
        .order_by(Exercise.created_at.desc())
    )
    result = await session.execute(stmt)
    exercises = result.scalars().all()

    return [
        {
            "id": e.id,
            "conversation_id": e.conversation_id,
            "subject": e.subject,
            "question_type": e.question_type,
            "question_number": e.question_number,
            "question": e.question,
            "options": json.loads(e.options) if e.options else [],
            "answer": e.answer,
            "explanation": e.explanation,
            "created_at": e.created_at.isoformat(),
        }
        for e in exercises
    ]


# --- 资源相关接口 ---

@app.get("/api/resources/all")
async def list_all_resources(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """(把当前用户生成的资源按对话模块进行分组)Return all resources for the current user, grouped by conversation."""
    stmt = (
        select(Resource)
        .where(Resource.user_id == user.id)
        .order_by(Resource.created_at.desc())
    )
    result = await session.execute(stmt)
    resources = result.scalars().all()
    print(f"[resources] list_all_resources user={user.id} count={len(resources)}", flush=True)

    grouped: dict[str, list[dict]] = {}
    for r in resources:
        key = r.conversation_id
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "id": r.id,
            "conversation_id": r.conversation_id,
            "resource_type": r.resource_type,
            "topic": r.topic,
            "content": r.content,
            "file_name": r.file_name,
            "reviewed": bool(r.reviewed),
            "created_at": r.created_at.isoformat(),
        })
    return grouped


@app.get("/api/resources")
async def list_resources(
    conversation_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return resources, optionally filtered by conversation."""
    stmt = select(Resource).where(Resource.user_id == user.id)
    if conversation_id:
        stmt = stmt.where(Resource.conversation_id == conversation_id)
    stmt = stmt.order_by(Resource.created_at.asc())
    result = await session.execute(stmt)
    resources = result.scalars().all()
    return [
        {
            "id": r.id,
            "conversation_id": r.conversation_id,
            "resource_type": r.resource_type,
            "topic": r.topic,
            "content": r.content,
            "file_name": r.file_name,
            "reviewed": bool(r.reviewed),
            "created_at": r.created_at.isoformat(),
        }
        for r in resources
    ]


@app.get("/api/resources/{resource_id}/download")
async def download_resource(
    resource_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """(把资源转换成可下载的文件形式)Download a resource as a file."""
    from fastapi.responses import Response
    stmt = select(Resource).where(Resource.id == resource_id, Resource.user_id == user.id)
    result = await session.execute(stmt)
    r = result.scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")

    from urllib.parse import quote

    content_type_map = {
        ".md": "text/markdown; charset=utf-8",
        ".py": "text/x-python; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }
    ext = FILE_EXTENSIONS.get(r.resource_type, ".md")
    media_type = content_type_map.get(ext, "text/plain; charset=utf-8")

    # (将中文文件名转换成ASCII码编码的形式)RFC 5987: encode non-ASCII filename for Content-Disposition
    encoded_name = quote(r.file_name, safe="")
    fallback = f"{r.resource_type}{ext}"

    return Response(
        content=r.content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{fallback}";'
                f" filename*=UTF-8''{encoded_name}"
            ),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



