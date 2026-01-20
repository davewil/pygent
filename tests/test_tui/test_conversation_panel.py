"""Behavioral tests for ConversationPanel with markdown rendering.

These tests verify that the ConversationPanel correctly renders messages
with markdown support, syntax highlighting, and proper styling.
"""

import pytest
from rich.markdown import Markdown as RichMarkdown

from chapgent.tui.app import ChapgentApp
from chapgent.tui.markdown import MarkdownMessage
from chapgent.tui.widgets import ConversationPanel


class TestConversationPanelMessages:
    """Tests for message rendering in ConversationPanel."""

    @pytest.mark.asyncio
    async def test_user_message_renders_markdown(self):
        """User messages should render with markdown support."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            panel.append_user_message("Hello **world**")

            # Verify MarkdownMessage widget was created
            messages = panel.query(MarkdownMessage)
            assert len(messages) == 1

            # Verify role and content
            msg = messages[0]
            assert msg.role == "user"
            assert "Hello **world**" in msg.content

    @pytest.mark.asyncio
    async def test_agent_message_renders_markdown(self):
        """Agent messages should render with markdown support."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            panel.append_assistant_message("Here is some `code`")

            # Verify MarkdownMessage widget was created
            messages = panel.query(MarkdownMessage)
            assert len(messages) == 1

            # Verify role and content
            msg = messages[0]
            assert msg.role == "agent"
            assert "code" in msg.content

    @pytest.mark.asyncio
    async def test_messages_have_correct_css_classes(self):
        """Messages should have role-based CSS classes for styling."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            panel.append_user_message("User says hi")
            panel.append_assistant_message("Agent responds")

            user_msgs = panel.query(".user-message")
            agent_msgs = panel.query(".agent-message")

            assert len(user_msgs) == 1
            assert len(agent_msgs) == 1

    @pytest.mark.asyncio
    async def test_code_block_in_message(self):
        """Messages with code blocks should be rendered correctly."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            code_content = """Here's some code:

```python
def hello():
    print("Hello")
```
"""
            panel.append_assistant_message(code_content)

            messages = panel.query(MarkdownMessage)
            assert len(messages) == 1

            # The message content should include the code block
            assert "python" in messages[0].content
            assert "def hello" in messages[0].content


class TestConversationPanelStreaming:
    """Tests for streaming message support."""

    @pytest.mark.asyncio
    async def test_append_streaming_message_creates_empty_message(self):
        """append_streaming_message should create an empty agent message."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            streaming_msg = panel.append_streaming_message()

            assert streaming_msg is not None
            assert streaming_msg.role == "agent"
            assert streaming_msg.content == ""
            assert streaming_msg.id == "streaming-message"

    @pytest.mark.asyncio
    async def test_update_streaming_message_changes_content(self):
        """update_streaming_message should update the message content."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            panel.append_streaming_message()

            # Update content
            panel.update_streaming_message("First update")
            streaming_msg = panel.query_one("#streaming-message", MarkdownMessage)
            assert streaming_msg.content == "First update"

            # Update again
            panel.update_streaming_message("Second update")
            assert streaming_msg.content == "Second update"

    @pytest.mark.asyncio
    async def test_finalize_streaming_message_marks_complete(self):
        """finalize_streaming_message should mark the message as finalized."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ConversationPanel)
            panel.append_streaming_message()
            panel.update_streaming_message("Final content")
            panel.finalize_streaming_message()

            # The message should still exist with content
            agent_msgs = panel.query(".agent-message")
            assert len(agent_msgs) == 1
            assert agent_msgs[0].content == "Final content"


class TestConversationPanelThemeIntegration:
    """Tests for theme-aware syntax highlighting."""

    @pytest.mark.asyncio
    async def test_renderer_uses_app_theme(self):
        """Renderer should use syntax theme based on app theme."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            # Get renderer and check it was created
            renderer = panel._get_renderer()
            assert renderer is not None

            # Config should have a code_theme set
            assert renderer.config.code_theme is not None

    @pytest.mark.asyncio
    async def test_reset_renderer_clears_cache(self):
        """reset_renderer should clear the cached renderer."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            # Get renderer once
            renderer1 = panel._get_renderer()

            # Reset and get again
            panel.reset_renderer()
            renderer2 = panel._get_renderer()

            # Should be different instances
            assert renderer1 is not renderer2


class TestConversationPanelClear:
    """Tests for clearing conversation history."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_messages(self):
        """clear() should remove all messages from the panel."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ConversationPanel)

            # Add some messages
            panel.append_user_message("User message 1")
            panel.append_assistant_message("Agent message 1")
            panel.append_user_message("User message 2")

            # Verify messages exist
            assert len(panel.query(MarkdownMessage)) == 3

            # Clear and wait for DOM update
            panel.clear()
            await pilot.pause()

            # Verify all cleared
            assert len(panel.query(MarkdownMessage)) == 0


class TestMarkdownMessageRender:
    """Tests for MarkdownMessage rendering."""

    @pytest.mark.asyncio
    async def test_message_render_returns_rich_markdown(self):
        """MarkdownMessage.render() should return a Rich Markdown object."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)
            panel.append_assistant_message("Test content")

            messages = panel.query(MarkdownMessage)
            render_result = messages[0].render()

            assert isinstance(render_result, RichMarkdown)

    @pytest.mark.asyncio
    async def test_message_render_includes_role_prefix(self):
        """Rendered message should include role prefix."""
        app = ChapgentApp()
        async with app.run_test():
            panel = app.query_one(ConversationPanel)

            panel.append_user_message("Hello")
            panel.append_assistant_message("Hi")

            messages = panel.query(MarkdownMessage)

            # User message should have "You:" prefix
            user_render = str(messages[0].render())
            # The prefix is embedded in the markdown as **You:**
            assert "You" in user_render or messages[0]._role == "user"

            # Agent message should have "Agent:" prefix
            agent_render = str(messages[1].render())
            # The prefix is embedded in the markdown as **Agent:**
            assert "Agent" in agent_render or messages[1]._role == "agent"
