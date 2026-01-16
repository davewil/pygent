from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pygent.tools.base import ToolRisk


class PermissionManager:
    """Manages tool execution permissions.

    Attributes:
        session_override: If True, skip prompts for MEDIUM risk.
        prompt_callback: Async function to prompt user for permission.
    """

    def __init__(
        self,
        prompt_callback: Callable[[str, ToolRisk, dict[str, Any]], Awaitable[bool]],
        session_override: bool = False,
    ) -> None:
        self.prompt_callback = prompt_callback
        self.session_override = session_override

    async def check(self, tool_name: str, risk: ToolRisk, args: dict[str, Any]) -> bool:
        """Check if tool execution is permitted.

        Returns:
            True if permitted, False if denied.
        """
        if risk == ToolRisk.LOW:
            return True

        if risk == ToolRisk.MEDIUM and self.session_override:
            return True

        # MEDIUM (without override) and HIGH always prompt
        return await self.prompt_callback(tool_name, risk, args)
