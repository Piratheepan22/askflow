# backend/app/schemas.py
from datetime import datetime
from pydantic import BaseModel, field_validator

class ChatRequest(BaseModel):
    conversation_id: int | None = None   # optional: None starts a new chat
    message: str                          # required
class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True   # allow building this from an ORM object
class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Username must be between 3 and 20 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes)")
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"