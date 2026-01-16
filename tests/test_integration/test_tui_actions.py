import asyncio
from unittest.mock import AsyncMock

import pytest
from pygent.config.settings import Settings
from pygent.core.agent import Agent
from pygent.core.permissions import PermissionManager
from pygent.core.providers import LLMProvider, LLMResponse, ToolUseBlock
from pygent.session.models import Session
from pygent.tools.base import ToolRisk, tool
from pygent.tools.registry import ToolRegistry
from pygent.tui.app import PygentApp
from pygent.tui.widgets import MessageInput, PermissionPrompt, ToolResultItem


@tool(name="medium_risk_tool", description="A medium risk tool", risk=ToolRisk.MEDIUM)
async def medium_risk_tool() -> str:
    return "executed"


@pytest.fixture
def mock_agent():
    provider = AsyncMock(spec=LLMProvider)

    response_tool = LLMResponse(
        content=[
            ToolUseBlock(
                id="call_medium",
                name="medium_risk_tool",
                input={},
            )
        ],
        stop_reason="tool_use",
    )

    response_stop = LLMResponse(content=[], stop_reason="end_turn")

    # Return tool call then stop
    provider.complete.side_effect = [response_tool, response_stop, response_tool, response_stop]

    tools = ToolRegistry()
    tools.register(medium_risk_tool)

    session = Session(
        id="test_session",
        messages=[],
        tool_history=[],
        working_directory=".",
    )

    return Agent(provider, tools, None, session)


@pytest.mark.asyncio
async def test_action_toggle_permissions(mock_agent):
    """Test that Ctrl+P toggles permission override and bypasses prompt."""

    app = PygentApp(agent=mock_agent)

    async def prompt_callback(name, risk, args):
        return await app.get_permission(name, args)

    permissions = PermissionManager(prompt_callback=prompt_callback)
    mock_agent.permissions = permissions

    async with app.run_test() as pilot:
        # 1. First run without override - should prompt
        app.query_one("#input", MessageInput).value = "run tool"
        await pilot.press("enter")

        # Poll for screen
        for _ in range(10):
            await asyncio.sleep(0.1)
            if isinstance(app.screen, PermissionPrompt):
                break
        else:
            pytest.fail("PermissionPrompt did not appear as expected")

        assert isinstance(app.screen, PermissionPrompt)
        await pilot.click("#btn-yes")
        await pilot.pause()

        # 2. Toggle override
        print("DEBUG: Toggling via action call")
        app.action_toggle_permissions()
        print(f"DEBUG: App PM override: {app.agent.permissions.session_override}")
        assert app.agent.permissions.session_override is True
        assert mock_agent.permissions.session_override is True

        # 3. Second run with override - should NOT prompt
        app.query_one("#input", MessageInput).value = "run tool again"
        await pilot.press("enter")

        # Wait a bit
        for _ in range(10):
            await asyncio.sleep(0.1)
            if app.query(ToolResultItem).filter(".tool-result"):  # If results appear
                break

        # Ensure no prompt is active
        assert not isinstance(app.screen, PermissionPrompt)

        # Check tool panel for result
        tool_panel = app.query_one("ToolPanel")
        results = tool_panel.query(ToolResultItem)
        assert any("executed" in r.result for r in results)


@pytest.mark.asyncio
async def test_action_new_session(mock_agent):
    """Test that Ctrl+N clears the UI and starts a new session."""

    app = PygentApp(agent=mock_agent)

    async with app.run_test() as pilot:
        # Add some messages
        app.query_one("ConversationPanel").append_user_message("Hello")
        app.query_one("ToolPanel").append_tool_call("test_tool", "123")

        old_session_id = mock_agent.session.id

        # Press Ctrl+N
        await pilot.press("ctrl+n")

        assert mock_agent.session.id != old_session_id
        assert len(app.query_one("#conversation-messages").children) == 0
        assert len(app.query_one("#tool-output").children) == 0


@pytest.mark.asyncio
async def test_settings_integration_no_tool_panel():
    """Test that ToolPanel is not yielded if show_tool_panel is False."""
    settings = Settings()
    settings.tui.show_tool_panel = False

    app = PygentApp(settings=settings)
    async with app.run_test():
        from pygent.tui.widgets import ToolPanel

        assert len(app.query(ToolPanel)) == 0
