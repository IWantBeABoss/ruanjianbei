import json
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openai_client import chat_complete
from models import StudentProfile
from agent_prompts import PROFILE_PROMPT

DIMENSION_LABELS = {
    "major_background": "专业背景",
    "knowledge_base": "知识基础",
    "cognitive_style": "认知风格",
    "learning_goals": "学习目标",
    "weak_points": "知识短板",
    "schedule_preference": "学习节奏",
    "content_preference": "内容偏好",
}


async def extract_profile_dimensions(messages: list[dict]) -> dict:
    """Analyze conversation and extract 7 profile dimensions as a dict."""
    conversation_text = ""
    for m in messages:
        role_label = "学生" if m["role"] == "user" else "AI导师"
        conversation_text += f"{role_label}：{m['content']}\n\n"

    if len(messages) < 2:
        return {}

    try:
        result = await chat_complete([
            {"role": "system", "content": PROFILE_PROMPT},
            {"role": "user", "content": f"请分析以下对话，提取学生画像：\n\n{conversation_text}"},
        ])
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return {k: v for k, v in data.items() if v}
    except (json.JSONDecodeError, Exception):
        pass

    return {}


async def get_or_create_profile(session: AsyncSession, user_id: str) -> StudentProfile:
    """Get existing profile for user or create default one."""
    stmt = select(StudentProfile).where(StudentProfile.user_id == user_id)
    result = await session.execute(stmt)
    profile = result.scalars().first()
    if not profile:
        profile = StudentProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


async def update_student_profile(
    session: AsyncSession,
    new_dimensions: dict,
    user_id: str,
) -> StudentProfile:
    """Merge new dimensions into existing profile (only overwrite non-empty values)."""
    profile = await get_or_create_profile(session, user_id)

    field_map = {
        "major_background": "major_background",
        "knowledge_base": "knowledge_base",
        "cognitive_style": "cognitive_style",
        "learning_goals": "learning_goals",
        "weak_points": "weak_points",
        "schedule_preference": "schedule_preference",
        "content_preference": "content_preference",
    }

    for key, value in new_dimensions.items():
        if key in field_map and value and isinstance(value, str) and value.strip():
            setattr(profile, field_map[key], value.strip())

    import datetime
    profile.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await session.commit()
    await session.refresh(profile)
    return profile


def format_profile_for_context(profile: StudentProfile) -> str:
    """Convert profile to a concise context string for agent prompts."""
    parts = []
    fields = [
        ("major_background", "专业背景"),
        ("knowledge_base", "知识基础"),
        ("cognitive_style", "认知风格"),
        ("learning_goals", "学习目标"),
        ("weak_points", "知识短板"),
        ("schedule_preference", "学习节奏"),
        ("content_preference", "内容偏好"),
    ]
    for attr, label in fields:
        value = getattr(profile, attr, "")
        if value and value.strip():
            parts.append(f"- {label}：{value.strip()}")

    if not parts:
        return ""

    return "[学生档案]\n" + "\n".join(parts)


def format_profile_as_markdown(profile: StudentProfile) -> str:
    """Format profile as rich Markdown for display."""
    fields = [
        ("major_background", "🎓 专业背景"),
        ("knowledge_base", "📚 知识基础"),
        ("cognitive_style", "🧠 认知风格"),
        ("learning_goals", "🎯 学习目标"),
        ("weak_points", "🔧 知识短板"),
        ("schedule_preference", "⏱️ 学习节奏"),
        ("content_preference", "📋 内容偏好"),
    ]

    lines = ["# 📋 我的学习档案\n"]
    has_any = False
    for attr, label in fields:
        value = getattr(profile, attr, "")
        if value and value.strip():
            lines.append(f"## {label}\n{value.strip()}\n")
            has_any = True

    if not has_any:
        lines.append("> 学习档案尚未建立。继续对话，系统将自动分析并构建你的学习画像。\n")
        lines.append("> 多聊一些关于你学习的内容（专业、课程、遇到的困难等），档案会逐渐丰富。")

    lines.append(f"\n---\n*最后更新：{profile.updated_at.strftime('%Y-%m-%d %H:%M') if profile.updated_at else '刚刚'}*")
    return "\n".join(lines)
