from datetime import datetime, timezone
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field

Role = Literal["normal", "super_admin"]


class User(BaseModel):
    """Documento de usuario armazenado na collection `users`."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    role: Role = "normal"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    email: str
    password: str
    role: Role = "normal"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Role] = None


class UserPublic(BaseModel):
    """Formato devolvido pela API — nunca inclui password_hash."""
    id: str
    email: str
    role: Role
    created_at: datetime
