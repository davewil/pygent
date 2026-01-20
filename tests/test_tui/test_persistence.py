from unittest.mock import AsyncMock, MagicMock

import pytest

from chapgent.core.agent import Agent
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tui.app import ChapgentApp


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
    app = ChapgentApp(agent=mock_agent, storage=mock_storage)

    # Simulate saving
    await app.action_save_session()

    # Check if save was called with the agent's session
    mock_storage.save.assert_called_once_with(mock_agent.session)


@pytest.mark.asyncio
async def test_action_save_session_no_storage(mock_agent):
    """Test that action_save_session handles missing storage gracefully."""
    app = ChapgentApp(agent=mock_agent, storage=None)

    # Should not raise error
    await app.action_save_session()


@pytest.mark.asyncio
async def test_action_save_session_no_agent(mock_storage):
    """Test that action_save_session handles missing agent gracefully."""
    app = ChapgentApp(agent=None, storage=mock_storage)

    # Should not call save
    await app.action_save_session()
    mock_storage.save.assert_not_called()
