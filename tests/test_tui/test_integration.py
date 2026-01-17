import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from pygent.core.agent import Agent
from pygent.core.loop import LoopEvent
from pygent.tui.app import PygentApp
from pygent.tui.widgets import ConversationPanel, MessageInput, ToolPanel, ToolProgressItem


@pytest.mark.asyncio
async def test_tui_integration_with_mock_agent():
    """Test that the app integrates with the agent correctly."""

    # 1. Setup Mock Agent
    mock_agent = MagicMock(spec=Agent)
    # agent.run is an async generator, so it should NOT be an AsyncMock (which is awaitable).
    # It should be a standard Mock that returns an async iterator.
    mock_agent.session = MagicMock()
    mock_agent.session.id = "test-session-id"

    # Define the events the agent will yield
    # Note: tool_result needs tool_id to match the tool_call for proper progress tracking
    now = datetime.now()
    events = [
        LoopEvent(type="text", content="Hello from Agent"),
        LoopEvent(type="tool_call", tool_name="test_tool", tool_id="call_1", timestamp=now),
        LoopEvent(type="tool_result", tool_name="test_tool", tool_id="call_1", content="Tool Output", timestamp=now),
        LoopEvent(type="finished"),
    ]

    async def event_generator(*args, **kwargs):
        for event in events:
            yield event
            # Small yield to let the TUI process messages
            await asyncio.sleep(0.01)

    mock_agent.run.side_effect = event_generator

    # 2. Initialize App with Mock Agent
    app = PygentApp(agent=mock_agent)

    async with app.run_test() as pilot:
        # 3. Simulate User Input
        msg_input = app.query_one(MessageInput)
        msg_input.value = "Hello Agent"
        await pilot.press("enter")

        # Give some time for the worker to process events
        await pilot.pause(0.5)

        # 4. Verify Agent was called
        mock_agent.run.assert_called_with("Hello Agent")

        # 5. Verify UI Updates
        conv_panel = app.query_one(ConversationPanel)
        tool_panel = app.query_one(ToolPanel)

        # Inspect the content of the panels
        # We need to find the Static widgets we added.
        # Note: ConversationPanel is a Static, so we should filter for our classes.

        user_msgs = conv_panel.query(".user-message")
        assert user_msgs, "No user messages found"
        user_msg_widget = user_msgs.last()

        # Helper to extract text from a widget's render output
        def get_text_content(widget):
            from rich.segment import Segment

            # render() returns an iterable of Segments usually
            render_result = widget.render()
            if hasattr(render_result, "__iter__"):
                return "".join(s.text for s in render_result if isinstance(s, Segment))
            return str(render_result)

        user_msgs = conv_panel.query(".user-message")
        assert user_msgs, "No user messages found"
        user_msg_widget = user_msgs.last()
        assert "Hello Agent" in get_text_content(user_msg_widget)

        # Check assistant message
        agent_msgs = conv_panel.query(".agent-message")
        assert agent_msgs, "No agent messages found"
        assert "Hello from Agent" in get_text_content(agent_msgs.last())

        # Check tool panel - now uses ToolProgressItem widgets with .tool-progress class
        tool_progress_items = tool_panel.query(ToolProgressItem)
        assert tool_progress_items, "No tool progress items found"
        progress_item = tool_progress_items.last()
        assert progress_item.tool_name == "test_tool"
        assert progress_item.result == "Tool Output"
