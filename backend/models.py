import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship

from database import Base


#定义数据库字段的部分

def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    exercises = relationship("Exercise", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, default="New Chat")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    major_background = Column(Text, default="")
    knowledge_base = Column(Text, default="")
    cognitive_style = Column(Text, default="")
    learning_goals = Column(Text, default="")
    weak_points = Column(Text, default="")
    schedule_preference = Column(Text, default="")
    content_preference = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="profile")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    message_id = Column(String, ForeignKey("messages.id"), nullable=True)
    subject = Column(String, default="")
    question_type = Column(String, nullable=False)  # choice, fill_blank, true_false
    question_number = Column(Integer, default=1)
    question = Column(Text, default="")
    options = Column(Text, default="[]")  # JSON array for choice questions
    answer = Column(Text, default="")
    explanation = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="exercises")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    resource_type = Column(String, nullable=False)  # document|quiz|mindmap|video|code|reading|path|tutor|assessment
    topic = Column(String, default="")
    content = Column(Text, default="")
    file_name = Column(String, default="")
    reviewed = Column(Integer, default=0)  # 0=未审核, 1=已审核
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User")
