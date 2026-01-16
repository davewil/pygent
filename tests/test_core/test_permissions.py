from unittest.mock import AsyncMock

import pytest

from pygent.core.permissions import PermissionManager
from pygent.tools.base import ToolRisk


@pytest.fixture
def mock_prompt():
    return AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_low_risk_auto_approve(mock_prompt):
    pm = PermissionManager(prompt_callback=mock_prompt)
    result = await pm.check("read_file", ToolRisk.LOW, {"path": "foo"})

    assert result is True
    mock_prompt.assert_not_called()


@pytest.mark.asyncio
async def test_medium_risk_prompts(mock_prompt):
    pm = PermissionManager(prompt_callback=mock_prompt)

    # User approves
    mock_prompt.return_value = True
    result = await pm.check("edit_file", ToolRisk.MEDIUM, {})
    assert result is True
    mock_prompt.assert_called_once()

    # User denies
    mock_prompt.reset_mock()
    mock_prompt.return_value = False
    result = await pm.check("edit_file", ToolRisk.MEDIUM, {})
    assert result is False


@pytest.mark.asyncio
async def test_medium_risk_override(mock_prompt):
    pm = PermissionManager(prompt_callback=mock_prompt, session_override=True)

    result = await pm.check("edit_file", ToolRisk.MEDIUM, {})
    assert result is True
    mock_prompt.assert_not_called()


@pytest.mark.asyncio
async def test_high_risk_always_prompts(mock_prompt):
    # Even with override, high risk should prompt
    pm = PermissionManager(prompt_callback=mock_prompt, session_override=True)

    mock_prompt.return_value = True
    result = await pm.check("shell", ToolRisk.HIGH, {})
    assert result is True
    mock_prompt.assert_called_once()
