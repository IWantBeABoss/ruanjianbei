from datetime import datetime
from pydantic import BaseModel, field_validator


#将每一个函数的参数都进行一个封装(与JAVA类似的操作QAQ)
#后期维护直接改这个TODO

class UserRegister(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("Password must be at least 4 characters")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    content: str


class ProfileOut(BaseModel):
    id: str = ""
    major_background: str = ""
    knowledge_base: str = ""
    cognitive_style: str = ""
    learning_goals: str = ""
    weak_points: str = ""
    schedule_preference: str = ""
    content_preference: str = ""
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    conversation_id: str | None = None
