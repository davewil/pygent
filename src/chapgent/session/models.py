from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ContentBlock]
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolInvocation(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: str
    timestamp: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: list[Message] = []
    tool_history: list[ToolInvocation] = []
    working_directory: str = "."
    metadata: dict[str, Any] = {}


class SessionSummary(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    working_directory: str
    metadata: dict[str, Any]
