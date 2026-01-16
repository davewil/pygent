import pytest
from textual.widgets import Footer, Header

from pygent.tui.app import PygentApp
from pygent.tui.widgets import ConversationPanel, MessageInput, ToolPanel


@pytest.mark.asyncio
async def test_app_startup():
    """Test that the app starts execution and shows key widgets."""
    app = PygentApp()
    async with app.run_test():
        # Check if the app is running
        assert app.is_running

        # Check for main layout components
        assert app.query_one(Header)
        assert app.query_one(Footer)
        assert app.query_one(ConversationPanel)
        assert app.query_one(ToolPanel)
        assert app.query_one(MessageInput)


@pytest.mark.asyncio
async def test_app_quit_binding():
    """Test that the quit binding works."""
    app = PygentApp()
    async with app.run_test() as pilot:
        await pilot.press("ctrl+c")
        assert not app.is_running
