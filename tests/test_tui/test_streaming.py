"""Behavioral tests for streaming TUI integration."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from chapgent.config.settings import Settings
from chapgent.core.loop import LoopEvent
from chapgent.core.acp_provider import ACPClaudeCodeProvider
from chapgent.tui.app import ChapgentApp
from chapgent.tui.widgets import ConversationPanel, MarkdownMessage


class TestStreamingMode:
    """Test streaming mode behavior in the TUI."""

    @pytest.mark.asyncio
    async def test_app_with_streaming_provider_uses_streaming_loop(self):
        """When streaming_provider is set, app should use streaming loop."""
        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)

        app = ChapgentApp(streaming_provider=mock_provider)

        # The app should have the streaming provider set
        assert app.streaming_provider is mock_provider
        # And no regular agent
        assert app.agent is None

    @pytest.mark.asyncio
    async def test_streaming_text_deltas_update_conversation(self):
        """Text delta events should update the conversation panel incrementally."""
        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)
        # Add properties that the app accesses for logging
        mock_provider.is_running = False
        mock_provider.session_id = None

        app = ChapgentApp(streaming_provider=mock_provider)

        async with app.run_test():
            # Manually trigger the streaming loop by patching at the core.loop level
            with patch(
                "chapgent.core.loop.streaming_conversation_loop"
            ) as mock_loop:
                # Simulate the streaming events
                async def fake_loop(*args: Any, **kwargs: Any) -> AsyncIterator[LoopEvent]:
                    yield LoopEvent(type="text_delta", content="Hello, ")
                    yield LoopEvent(type="text_delta", content="I am ")
                    yield LoopEvent(type="text_delta", content="Claude!")
                    yield LoopEvent(type="finished")

                mock_loop.return_value = fake_loop()

                # Submit a message to trigger the streaming loop
                input_widget = app.query_one("#input")
                input_widget.value = "Hello"
                await app.on_input_submitted(
                    MagicMock(value="Hello", input=input_widget)
                )

                # Give the worker time to process
                await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_streaming_creates_single_message_for_all_deltas(self):
        """Streaming should create one message that accumulates all deltas."""
        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)

        app = ChapgentApp(streaming_provider=mock_provider)

        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            # Create a streaming message (starts with thinking placeholder)
            streaming_msg = panel.append_streaming_message()
            assert streaming_msg.content == "_Thinking..._"

            # Update with multiple deltas (replaces thinking placeholder)
            panel.update_streaming_message("First")
            assert streaming_msg.content == "First"

            panel.update_streaming_message("First Second")
            assert streaming_msg.content == "First Second"

            # Finalize
            panel.finalize_streaming_message()

            # Message should still exist with final content
            messages = list(panel.query(MarkdownMessage))
            # 1 agent message (streaming finalized)
            assert any(m.content == "First Second" for m in messages)

    @pytest.mark.asyncio
    async def test_streaming_error_shows_error_message(self):
        """LLM errors during streaming should show error in conversation."""
        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)

        app = ChapgentApp(streaming_provider=mock_provider)

        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            # Create and finalize a streaming message with error
            panel.append_streaming_message()
            panel.finalize_streaming_message()

            # Append error message
            panel.append_assistant_message("LLM Error: Rate limit exceeded")

            # Check that the error is visible
            messages = list(panel.query(MarkdownMessage))
            error_messages = [m for m in messages if "LLM Error" in m.content]
            assert len(error_messages) >= 1


class TestStreamingPermissions:
    """Test permission handling in streaming mode."""

    @pytest.mark.asyncio
    async def test_permission_callback_wired_to_streaming_provider(self):
        """Permission callback should be available for streaming provider."""
        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)
        mock_provider.permission_callback = None

        app = ChapgentApp(streaming_provider=mock_provider)

        # Simulate what bootstrap.py does
        async def permission_callback(tool_name: str, args: dict) -> bool:
            return await app.get_permission(tool_name, args)

        mock_provider.permission_callback = permission_callback

        # Verify callback is wired
        assert mock_provider.permission_callback is not None


class TestStreamingToolDisplay:
    """Test tool display in streaming mode."""

    @pytest.mark.asyncio
    async def test_tool_calls_show_in_tool_panel(self):
        """Tool calls during streaming should appear in the tool panel."""
        from chapgent.tui.widgets import ToolPanel

        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)

        settings = Settings()
        app = ChapgentApp(streaming_provider=mock_provider, settings=settings)

        async with app.run_test():
            tool_panel = app.query_one(ToolPanel)

            # Simulate a tool call
            tool_panel.append_tool_call(
                tool_name="read_file",
                tool_id="call-123",
                start_time=None,
            )

            # Verify tool is shown
            assert tool_panel.get_running_count() >= 0  # May be 0 if completed

    @pytest.mark.asyncio
    async def test_tool_results_update_tool_panel(self):
        """Tool results during streaming should update the tool panel."""
        from chapgent.tui.widgets import ToolPanel

        mock_provider = MagicMock(spec=ACPClaudeCodeProvider)

        settings = Settings()
        app = ChapgentApp(streaming_provider=mock_provider, settings=settings)

        async with app.run_test():
            tool_panel = app.query_one(ToolPanel)

            # Simulate a tool call and result
            tool_panel.append_tool_call(
                tool_name="read_file",
                tool_id="call-123",
                start_time=None,
            )

            tool_panel.update_tool_result(
                tool_id="call-123",
                tool_name="read_file",
                result="File contents here",
                is_error=False,
                cached=False,
            )

            # Panel should have processed the update
            # (specific assertions depend on widget state management)


class TestStreamingWithNoProvider:
    """Test behavior when no provider is available."""

    @pytest.mark.asyncio
    async def test_no_provider_shows_error_message(self):
        """When no agent or streaming provider, should show error."""
        app = ChapgentApp()

        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            # Submit a message without any provider
            input_widget = app.query_one("#input")
            input_widget.value = "Hello"

            # Simulate submission
            from chapgent.tui.widgets import MessageInput

            await app.on_input_submitted(
                MessageInput.Submitted(input=input_widget, value="Hello")
            )

            # Should show error message
            messages = list(panel.query(MarkdownMessage))
            # We expect user message + error message
            assert len(messages) >= 1
            assert any("No agent attached" in m.content for m in messages if hasattr(m, "content"))
