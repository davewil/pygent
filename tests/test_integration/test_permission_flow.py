import asyncio
from unittest.mock import AsyncMock

import pytest
from pygent.core.agent import Agent
from pygent.core.permissions import PermissionManager
from pygent.core.providers import LLMProvider
from pygent.session.models import Session
from pygent.tools.base import ToolRisk, tool
from pygent.tools.registry import ToolRegistry
from pygent.tui.app import PygentApp
from pygent.tui.widgets import MessageInput, PermissionPrompt, ToolResultItem


@tool(name="high_risk_tool", description="A high risk tool", risk=ToolRisk.HIGH)
async def high_risk_tool() -> str:
    return "executed"


@pytest.fixture
def mock_agent():
    provider = AsyncMock(spec=LLMProvider)
    # Configure provider to return a tool call
    from pygent.core.providers import LLMResponse, ToolUseBlock

    response_tool = LLMResponse(
        content=[
            ToolUseBlock(
                id="call_123",
                name="high_risk_tool",
                input={},
            )
        ],
        stop_reason="tool_use",
    )

    response_stop = LLMResponse(content=[], stop_reason="end_turn")

    provider.complete.side_effect = [response_tool, response_stop, response_stop]

    tools = ToolRegistry()
    tools.register(high_risk_tool)

    session = Session(
        id="test_session",
        messages=[],
        tool_history=[],
        working_directory=".",
    )

    # Permission manager will be set by the app or test setup
    return Agent(provider, tools, None, session)


@pytest.mark.asyncio
async def test_permission_flow_allow(mock_agent):
    """Test that accepting the permission prompt executes the tool."""

    # Setup App with Agent
    app = PygentApp(agent=mock_agent)

    # Callback to signal app to request permission
    async def prompt_callback(name, risk, args):
        return await app.get_permission(name, args)

    permissions = PermissionManager(prompt_callback=prompt_callback)
    mock_agent.permissions = permissions

    async with app.run_test() as pilot:
        # Submit a message to trigger the agent
        app.query_one("#input", MessageInput).value = "run tool"
        await pilot.press("enter")

        # Wait for the permission prompt to appear
        # Polling for screen
        for _ in range(10):
            await asyncio.sleep(0.1)
            if isinstance(app.screen, PermissionPrompt):
                break
        else:
            pytest.fail("PermissionPrompt did not appear")

        assert isinstance(app.screen, PermissionPrompt)

        # Click "Yes" (assuming we add a button with id 'yes')
        await pilot.click("#btn-yes")

        # Wait for tool execution to complete
        await pilot.pause()
        await pilot.pause()  # Extra pause for worker

        # Check tool panel for result
        tool_panel = app.query_one("ToolPanel")
        results = tool_panel.query(ToolResultItem)
        assert any("executed" in r.result for r in results)


@pytest.mark.asyncio
async def test_permission_flow_deny(mock_agent):
    """Test that denying the permission prompt blocks execution."""

    app = PygentApp(agent=mock_agent)

    async def prompt_callback(name, risk, args):
        return await app.get_permission(name, args)

    permissions = PermissionManager(prompt_callback=prompt_callback)
    mock_agent.permissions = permissions

    async with app.run_test() as pilot:
        app.query_one("#input", MessageInput).value = "run tool"
        await pilot.press("enter")

        for _ in range(10):
            await asyncio.sleep(0.1)
            if isinstance(app.screen, PermissionPrompt):
                break
        else:
            pytest.fail("PermissionPrompt did not appear")

        assert isinstance(app.screen, PermissionPrompt)

        # Click "No"
        await pilot.click("#btn-no")

        tool_panel = app.query_one("ToolPanel")
        results = []
        for _ in range(20):  # Increased polling
            await asyncio.sleep(0.1)
            results = tool_panel.query(ToolResultItem)
            # print(f"DEBUG IN TEST: Found items: {[r.result for r in results]}")
            if any("Permission Denied" in r.result for r in results):
                break
        else:
            # Re-enable print for debugging if failure
            print(f"DEBUG: Final items found: {[r.result for r in results]}")
            pytest.fail("Permission Denied result did not appear")

        results = tool_panel.query(ToolResultItem)
        assert any("Permission Denied" in r.result for r in results)
