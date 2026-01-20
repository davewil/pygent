"""Context awareness module for detecting project type and gathering context."""

from chapgent.context.detection import (
    GitIgnoreFilter,
    detect_project_context,
)
from chapgent.context.models import (
    GitInfo,
    ProjectContext,
    ProjectType,
    TestFramework,
)
from chapgent.context.prompt import build_system_prompt

__all__ = [
    "GitInfo",
    "GitIgnoreFilter",
    "ProjectContext",
    "ProjectType",
    "TestFramework",
    "build_system_prompt",
    "detect_project_context",
]
