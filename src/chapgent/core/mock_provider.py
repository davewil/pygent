"""Mock LLM provider for testing and demos."""

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from chapgent.core.providers import LLMProvider, LLMResponse, TextBlock, TokenUsage, ToolUseBlock
from chapgent.tools.base import ToolDefinition

# Mock token counts (approximate)
MOCK_PROMPT_TOKENS = 100
MOCK_COMPLETION_TOKENS = 50


@dataclass
class MockLLMProvider(LLMProvider):
    """Mock provider that returns canned responses for TUI testing.

    Attributes:
        delay: Optional delay in seconds before responses (for realistic feel).
        tokens_per_response: Mock token count per response (for testing limits).
    """

    def __init__(
        self,
        model: str = "mock",
        api_key: str | None = None,
        delay: float = 0.0,
        tokens_per_response: int = MOCK_PROMPT_TOKENS + MOCK_COMPLETION_TOKENS,
    ) -> None:
        super().__init__(model, api_key)
        self.delay = delay
        self.tokens_per_response = tokens_per_response

    def _mock_usage(self) -> TokenUsage:
        """Generate mock token usage."""
        return TokenUsage(
            prompt_tokens=MOCK_PROMPT_TOKENS,
            completion_tokens=MOCK_COMPLETION_TOKENS,
            total_tokens=self.tokens_per_response,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Return canned responses based on user input patterns.

        Args:
            messages: Conversation messages.
            tools: Available tool definitions.
            max_tokens: Ignored for mock.

        Returns:
            LLMResponse with either text or tool calls.
        """
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # Get the last user message
        user_message = self._get_last_user_message(messages)

        # Check if this is a tool result (continue after tool execution)
        if self._is_tool_result(messages):
            return LLMResponse(
                content=[
                    TextBlock(
                        text=(
                            "I've completed the requested operation. Is there anything else you'd like me to help with?"
                        )
                    )
                ],
                stop_reason="end_turn",
                usage=self._mock_usage(),
            )

        # Analyze user message for tool triggers
        tool_response = self._check_tool_triggers(user_message, tools)
        if tool_response:
            return tool_response

        # Return text response based on keywords
        return self._generate_text_response(user_message)

    def _get_last_user_message(self, messages: list[dict[str, Any]]) -> str:
        """Extract the last user message content."""
        for msg in reversed(messages):
            content = msg.get("content")
            if msg.get("role") == "user" and isinstance(content, str):
                return content
        return ""

    def _is_tool_result(self, messages: list[dict[str, Any]]) -> bool:
        """Check if the last message is a tool result."""
        if messages:
            last = messages[-1]
            return last.get("role") == "tool"
        return False

    def _check_tool_triggers(self, user_message: str, tools: list[ToolDefinition]) -> LLMResponse | None:
        """Check if user message should trigger a tool call."""
        tool_names = set()
        for t in tools:
            tool_names.add(t.name)

        # File reading triggers
        if re.search(r"\bread\b.*\bfile\b|\bshow\b.*\bfile\b|\bcat\b", user_message, re.IGNORECASE):
            if "read_file" in tool_names:
                # Try to extract filename
                filename = self._extract_filename(user_message) or "README.md"
                return LLMResponse(
                    content=[
                        TextBlock(text=f"I'll read the file `{filename}` for you."),
                        ToolUseBlock(id="mock_call_1", name="read_file", input={"path": filename}),
                    ],
                    stop_reason="tool_use",
                    usage=self._mock_usage(),
                )

        # Directory listing triggers
        if re.search(r"\blist\b.*\b(files?|director(y|ies))\b|\bls\b|\bdir\b", user_message, re.IGNORECASE):
            if "list_files" in tool_names:
                path = self._extract_path(user_message) or "."
                return LLMResponse(
                    content=[
                        TextBlock(text=f"I'll list the contents of `{path}`."),
                        ToolUseBlock(id="mock_call_2", name="list_files", input={"path": path, "recursive": False}),
                    ],
                    stop_reason="tool_use",
                    usage=self._mock_usage(),
                )

        # Edit file triggers
        if re.search(r"\bedit\b|\bchange\b|\bmodify\b|\bupdate\b", user_message, re.IGNORECASE):
            if "edit_file" in tool_names:
                return LLMResponse(
                    content=[
                        TextBlock(
                            text=(
                                "To edit a file, I need you to specify the file path "
                                "and what changes to make. For example: "
                                "'edit test.txt, change hello to goodbye'"
                            )
                        )
                    ],
                    stop_reason="end_turn",
                    usage=self._mock_usage(),
                )

        # Shell triggers
        if re.search(r"\brun\b|\bexecute\b|\bshell\b|\bcommand\b", user_message, re.IGNORECASE):
            if "shell" in tool_names:
                # Try to extract command
                cmd = self._extract_command(user_message) or "echo 'Hello from mock shell'"
                return LLMResponse(
                    content=[
                        TextBlock(text="I'll execute the shell command for you."),
                        ToolUseBlock(id="mock_call_3", name="shell", input={"command": cmd}),
                    ],
                    stop_reason="tool_use",
                    usage=self._mock_usage(),
                )

        return None

    def _generate_text_response(self, user_message: str) -> LLMResponse:
        """Generate a text response based on user message."""
        # Greeting patterns
        if re.search(r"\b(hello|hi|hey|greetings)\b", user_message, re.IGNORECASE):
            return LLMResponse(
                content=[
                    TextBlock(
                        text="""Hello! I'm Chapgent, your AI coding assistant. I can help you with:

• **Reading files** - "read file README.md"
• **Listing directories** - "list files in src/"
• **Editing files** - "edit file to change X to Y"
• **Running commands** - "run ls -la"

What would you like me to help you with today?"""
                    )
                ],
                stop_reason="end_turn",
                usage=self._mock_usage(),
            )

        # Help patterns
        if re.search(r"\bhelp\b|\bwhat can you do\b|\bcapabilities\b", user_message, re.IGNORECASE):
            return LLMResponse(
                content=[
                    TextBlock(
                        text="""I'm a coding assistant with access to these tools:

1. **read_file** - Read contents of any file
2. **list_files** - List directory contents
3. **edit_file** - Edit files via string replacement
4. **shell** - Execute shell commands

Just describe what you'd like to do in natural language!"""
                    )
                ],
                stop_reason="end_turn",
                usage=self._mock_usage(),
            )

        # Default response
        default_text = f'I understand you want help with: "{user_message}"\n\n'
        default_text += "Could you be more specific? For example:\n"
        default_text += '- "read file config.py"\n'
        default_text += '- "list files in the current directory"\n'
        default_text += '- "run git status"'
        return LLMResponse(
            content=[TextBlock(text=default_text)],
            stop_reason="end_turn",
            usage=self._mock_usage(),
        )

    def _extract_filename(self, message: str) -> str | None:
        """Try to extract a filename from the message."""
        # Common file patterns
        match = re.search(r"['\"]([^'\"]+\.[a-zA-Z0-9]+)['\"]", message)
        if match:
            return match.group(1)

        match = re.search(r"\b(\S+\.[a-zA-Z0-9]+)\b", message)
        if match:
            return match.group(1)

        return None

    def _extract_path(self, message: str) -> str | None:
        """Try to extract a path from the message."""
        match = re.search(r"['\"]([^'\"]+)['\"]", message)
        if match:
            return match.group(1)

        # Look for common path patterns
        match = re.search(r"\b(\.|\.\.|/\S+|\./\S+|\S+/\S*)\b", message)
        if match:
            return match.group(1)

        return None

    def _extract_command(self, message: str) -> str | None:
        """Try to extract a shell command from the message."""
        # Look for quoted commands
        match = re.search(r"['\"]([^'\"]+)['\"]", message)
        if match:
            return match.group(1)

        # Look for common commands
        match = re.search(r"\b(ls|cat|echo|git|python|pip|uv|npm|node)\s+\S+", message)
        if match:
            return match.group(0)

        return None
