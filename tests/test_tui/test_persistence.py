from unittest.mock import AsyncMock, MagicMock

import pytest

from pygent.core.agent import Agent
from pygent.session.models import Session
from pygent.session.storage import SessionStorage
from pygent.tui.app import PygentApp


@pytest.fixture
def mock_storage():
    storage = MagicMock(spec=SessionStorage)
    storage.save = AsyncMock()
    return storage


@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=Agent)
    agent.session = Session(id="test-session-id", messages=[], tool_history=[])
    return agent


@pytest.mark.asyncio
async def test_action_save_session(mock_storage, mock_agent):
    """Test that action_save_session calls storage.save."""
    app = PygentApp(agent=mock_agent, storage=mock_storage)

    # Simulate saving
    await app.action_save_session()

    # Check if save was called with the agent's session
    mock_storage.save.assert_called_once_with(mock_agent.session)


@pytest.mark.asyncio
async def test_action_save_session_no_storage(mock_agent):
    """Test that action_save_session handles missing storage gracefully."""
    app = PygentApp(agent=mock_agent, storage=None)

    # Should not raise error
    await app.action_save_session()


@pytest.mark.asyncio
async def test_action_save_session_no_agent(mock_storage):
    """Test that action_save_session handles missing agent gracefully."""
    app = PygentApp(agent=None, storage=mock_storage)

    # Should not call save
    await app.action_save_session()
    mock_storage.save.assert_not_called()
