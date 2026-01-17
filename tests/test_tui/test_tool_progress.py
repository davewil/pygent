"""Tests for the Tool Execution Progress feature."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from pygent.core.agent import Agent
from pygent.core.loop import LoopEvent
from pygent.core.providers import LLMProvider, LLMResponse
from pygent.session.models import Session
from pygent.tools.registry import ToolRegistry
from pygent.tui.app import PygentApp
from pygent.tui.widgets import (
    STATUS_ICONS,
    ToolPanel,
    ToolProgressItem,
    ToolStatus,
    _format_elapsed_time,
)

# =============================================================================
# ToolStatus Enum Tests
# =============================================================================


class TestToolStatus:
    """Tests for the ToolStatus enum."""

    def test_tool_status_values(self):
        """Test ToolStatus enum has expected values."""
        assert ToolStatus.WAITING.value == "waiting"
        assert ToolStatus.RUNNING.value == "running"
        assert ToolStatus.COMPLETED.value == "completed"
        assert ToolStatus.ERROR.value == "error"
        assert ToolStatus.CACHED.value == "cached"
        assert ToolStatus.PERMISSION_DENIED.value == "permission_denied"

    def test_all_statuses_have_icons(self):
        """Test all statuses have corresponding icons."""
        for status in ToolStatus:
            assert status in STATUS_ICONS
            assert len(STATUS_ICONS[status]) > 0


class TestStatusIcons:
    """Tests for STATUS_ICONS mapping."""

    def test_icon_types(self):
        """Test all icons are strings."""
        for icon in STATUS_ICONS.values():
            assert isinstance(icon, str)

    def test_icon_values(self):
        """Test specific icon values."""
        assert STATUS_ICONS[ToolStatus.WAITING] == "⏸"
        assert STATUS_ICONS[ToolStatus.RUNNING] == "⏳"
        assert STATUS_ICONS[ToolStatus.COMPLETED] == "✅"
        assert STATUS_ICONS[ToolStatus.ERROR] == "❌"
        assert STATUS_ICONS[ToolStatus.CACHED] == "📦"
        assert STATUS_ICONS[ToolStatus.PERMISSION_DENIED] == "🚫"


# =============================================================================
# _format_elapsed_time Helper Tests
# =============================================================================


class TestFormatElapsedTime:
    """Tests for _format_elapsed_time helper function."""

    def test_format_very_short_time(self):
        """Test formatting very short elapsed time."""
        start = datetime.now()
        end = start + timedelta(milliseconds=50)
        result = _format_elapsed_time(start, end)
        assert result == "<0.1s"

    def test_format_seconds(self):
        """Test formatting time in seconds."""
        start = datetime.now()
        end = start + timedelta(seconds=1.234)
        result = _format_elapsed_time(start, end)
        assert result == "1.2s"

    def test_format_longer_seconds(self):
        """Test formatting longer time in seconds."""
        start = datetime.now()
        end = start + timedelta(seconds=45.6)
        result = _format_elapsed_time(start, end)
        assert result == "45.6s"

    def test_format_minutes(self):
        """Test formatting time in minutes."""
        start = datetime.now()
        end = start + timedelta(seconds=90)
        result = _format_elapsed_time(start, end)
        assert result == "1m 30.0s"

    def test_format_several_minutes(self):
        """Test formatting several minutes."""
        start = datetime.now()
        end = start + timedelta(minutes=5, seconds=15.5)
        result = _format_elapsed_time(start, end)
        assert result == "5m 15.5s"

    def test_format_with_none_end_time(self):
        """Test formatting with None end time uses current time."""
        start = datetime.now() - timedelta(seconds=2)
        result = _format_elapsed_time(start, None)
        # Should be approximately 2 seconds
        assert "s" in result


# =============================================================================
# ToolProgressItem Widget Tests
# =============================================================================


class TestToolProgressItem:
    """Tests for the ToolProgressItem widget."""

    def test_tool_progress_item_creation(self):
        """Test creating a basic ToolProgressItem."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
            status=ToolStatus.RUNNING,
        )
        assert item.tool_id == "test-123"
        assert item.tool_name == "read_file"
        assert item.status == ToolStatus.RUNNING
        assert item.start_time is not None
        assert item.end_time is None
        assert item.result is None
        assert item.is_error is False

    def test_tool_progress_item_with_start_time(self):
        """Test creating ToolProgressItem with custom start time."""
        start = datetime(2026, 1, 17, 10, 0, 0)
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="shell",
            start_time=start,
        )
        assert item.start_time == start

    def test_tool_progress_item_default_status(self):
        """Test ToolProgressItem defaults to RUNNING status."""
        item = ToolProgressItem(tool_id="test-123", tool_name="read_file")
        assert item.status == ToolStatus.RUNNING

    def test_tool_progress_item_css_classes(self):
        """Test ToolProgressItem has correct CSS classes."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
            status=ToolStatus.RUNNING,
        )
        assert "tool-progress" in item.classes
        assert "tool-progress-running" in item.classes

    def test_tool_progress_item_waiting_status(self):
        """Test ToolProgressItem with WAITING status."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
            status=ToolStatus.WAITING,
        )
        assert "tool-progress-waiting" in item.classes


class TestToolProgressItemUpdateStatus:
    """Tests for ToolProgressItem.update_status method."""

    def test_update_status_to_completed(self):
        """Test updating status to COMPLETED."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
        )
        item.update_status(
            status=ToolStatus.COMPLETED,
            result="File content here",
            is_error=False,
        )
        assert item.status == ToolStatus.COMPLETED
        assert item.result == "File content here"
        assert item.is_error is False
        assert item.end_time is not None

    def test_update_status_to_cached(self):
        """Test updating status with cached=True."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
        )
        item.update_status(
            status=ToolStatus.COMPLETED,
            result="Cached content",
            cached=True,
        )
        assert item.status == ToolStatus.CACHED

    def test_update_status_to_error(self):
        """Test updating status to ERROR."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="shell",
        )
        item.update_status(
            status=ToolStatus.ERROR,
            result="Command failed",
            is_error=True,
        )
        assert item.status == ToolStatus.ERROR
        assert item.is_error is True
        assert item.end_time is not None

    def test_update_status_to_permission_denied(self):
        """Test updating status to PERMISSION_DENIED."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="delete_file",
        )
        item.update_status(
            status=ToolStatus.PERMISSION_DENIED,
            result="Permission denied by user",
            is_error=True,
        )
        assert item.status == ToolStatus.PERMISSION_DENIED
        assert item.end_time is not None

    def test_update_status_changes_css_classes(self):
        """Test that updating status changes CSS classes."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
            status=ToolStatus.RUNNING,
        )
        assert "tool-progress-running" in item.classes

        item.update_status(status=ToolStatus.COMPLETED, result="Done")

        assert "tool-progress-running" not in item.classes
        assert "tool-progress-completed" in item.classes


class TestToolProgressItemRefresh:
    """Tests for ToolProgressItem.refresh_elapsed_time method."""

    def test_refresh_elapsed_time_running(self):
        """Test refreshing elapsed time for running item."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="shell",
            status=ToolStatus.RUNNING,
        )
        # Should not raise
        item.refresh_elapsed_time()

    def test_refresh_elapsed_time_completed(self):
        """Test refreshing elapsed time for completed item does nothing."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="shell",
            status=ToolStatus.RUNNING,
        )
        item.update_status(status=ToolStatus.COMPLETED, result="Done")

        # Should not raise or change anything
        item.refresh_elapsed_time()
        assert item.status == ToolStatus.COMPLETED


class TestToolProgressItemBuildDisplayText:
    """Tests for ToolProgressItem._build_display_text method."""

    def test_display_text_running(self):
        """Test display text for running status."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="shell",
            status=ToolStatus.RUNNING,
        )
        text = item._build_display_text()
        assert "⏳" in text
        assert "shell" in text
        assert "[" in text and "]" in text

    def test_display_text_completed_with_result(self):
        """Test display text for completed status with result."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
        )
        item.update_status(status=ToolStatus.COMPLETED, result="Hello world")
        text = item._build_display_text()
        assert "✅" in text
        assert "read_file" in text
        assert "Hello world" in text

    def test_display_text_truncates_long_result(self):
        """Test display text truncates long results."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
        )
        long_result = "x" * 200
        item.update_status(status=ToolStatus.COMPLETED, result=long_result)
        text = item._build_display_text()
        assert "..." in text

    def test_display_text_permission_denied(self):
        """Test display text for permission denied."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="delete_file",
            status=ToolStatus.PERMISSION_DENIED,
        )
        text = item._build_display_text()
        assert "🚫" in text
        assert "Permission Denied" in text

    def test_display_text_cached(self):
        """Test display text for cached result."""
        item = ToolProgressItem(
            tool_id="test-123",
            tool_name="read_file",
        )
        item.update_status(status=ToolStatus.COMPLETED, result="Cached content", cached=True)
        text = item._build_display_text()
        assert "📦" in text


# =============================================================================
# ToolPanel Widget Tests
# =============================================================================


class TestToolPanel:
    """Tests for the ToolPanel widget."""

    @pytest.mark.asyncio
    async def test_tool_panel_compose(self):
        """Test that ToolPanel composes correctly."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)
            scroll = panel.query_one("#tool-output")
            assert scroll is not None

    @pytest.mark.asyncio
    async def test_tool_panel_append_tool_call(self):
        """Test adding a tool call to the panel."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(
                tool_name="read_file",
                tool_id="test-123",
            )

            # Should have one progress item
            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 1
            assert items[0].tool_name == "read_file"
            assert items[0].tool_id == "test-123"
            assert items[0].status == ToolStatus.RUNNING

    @pytest.mark.asyncio
    async def test_tool_panel_append_tool_call_with_timestamp(self):
        """Test adding a tool call with custom start time."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)
            start_time = datetime(2026, 1, 17, 10, 0, 0)

            panel.append_tool_call(
                tool_name="shell",
                tool_id="test-456",
                start_time=start_time,
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].start_time == start_time

    @pytest.mark.asyncio
    async def test_tool_panel_update_tool_result(self):
        """Test updating a tool call with its result."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            # Add tool call
            panel.append_tool_call(tool_name="read_file", tool_id="test-123")

            # Update with result
            panel.update_tool_result(
                tool_id="test-123",
                tool_name="read_file",
                result="File content",
                is_error=False,
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 1
            assert items[0].status == ToolStatus.COMPLETED
            assert items[0].result == "File content"

    @pytest.mark.asyncio
    async def test_tool_panel_update_tool_result_cached(self):
        """Test updating a tool call with cached result."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="read_file", tool_id="test-123")
            panel.update_tool_result(
                tool_id="test-123",
                tool_name="read_file",
                result="Cached content",
                cached=True,
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].status == ToolStatus.CACHED

    @pytest.mark.asyncio
    async def test_tool_panel_update_tool_result_error(self):
        """Test updating a tool call with error result."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="shell", tool_id="test-123")
            panel.update_tool_result(
                tool_id="test-123",
                tool_name="shell",
                result="Command failed",
                is_error=True,
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].status == ToolStatus.ERROR
            assert items[0].is_error is True

    @pytest.mark.asyncio
    async def test_tool_panel_update_permission_denied(self):
        """Test updating a tool call to permission denied."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="delete_file", tool_id="test-123")
            panel.update_permission_denied(tool_id="test-123", tool_name="delete_file")

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].status == ToolStatus.PERMISSION_DENIED

    @pytest.mark.asyncio
    async def test_tool_panel_update_result_without_call(self):
        """Test updating result for tool that wasn't tracked creates new item."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            # Update without prior append_tool_call
            panel.update_tool_result(
                tool_id="orphan-123",
                tool_name="read_file",
                result="Orphan result",
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 1
            assert items[0].tool_id == "orphan-123"
            assert items[0].status == ToolStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_tool_panel_clear(self):
        """Test clearing the tool panel."""
        app = PygentApp()
        async with app.run_test() as pilot:
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="read_file", tool_id="test-1")
            panel.append_tool_call(tool_name="shell", tool_id="test-2")

            assert len(panel.query_one("#tool-output").query(ToolProgressItem)) == 2

            panel.clear()
            await pilot.pause()

            assert len(panel.query_one("#tool-output").query(ToolProgressItem)) == 0
            assert panel.get_running_count() == 0

    @pytest.mark.asyncio
    async def test_tool_panel_get_running_count(self):
        """Test getting count of running tools."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            assert panel.get_running_count() == 0

            panel.append_tool_call(tool_name="tool1", tool_id="1")
            panel.append_tool_call(tool_name="tool2", tool_id="2")
            assert panel.get_running_count() == 2

            panel.update_tool_result(tool_id="1", tool_name="tool1", result="Done")
            assert panel.get_running_count() == 1

    @pytest.mark.asyncio
    async def test_tool_panel_refresh_running_tools(self):
        """Test refreshing running tools updates their display."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="shell", tool_id="test-123")

            # Should not raise
            panel.refresh_running_tools()

    @pytest.mark.asyncio
    async def test_tool_panel_multiple_tools(self):
        """Test panel handles multiple tools correctly."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            # Add multiple tools
            for i in range(5):
                panel.append_tool_call(tool_name=f"tool{i}", tool_id=f"id-{i}")

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 5

            # Update some
            panel.update_tool_result(tool_id="id-0", tool_name="tool0", result="Done")
            panel.update_tool_result(tool_id="id-2", tool_name="tool2", result="Done", cached=True)

            # Check statuses
            items = list(panel.query_one("#tool-output").query(ToolProgressItem))
            completed = [i for i in items if i.status == ToolStatus.COMPLETED]
            cached = [i for i in items if i.status == ToolStatus.CACHED]
            running = [i for i in items if i.status == ToolStatus.RUNNING]

            assert len(completed) == 1
            assert len(cached) == 1
            assert len(running) == 3


class TestToolPanelLegacyMethod:
    """Tests for ToolPanel legacy append_tool_result method."""

    @pytest.mark.asyncio
    async def test_legacy_append_tool_result(self):
        """Test legacy method still works."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_result("read_file", "Legacy result")

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 1
            assert items[0].status == ToolStatus.COMPLETED


# =============================================================================
# LoopEvent Tests
# =============================================================================


class TestLoopEventTimestamp:
    """Tests for LoopEvent timestamp field."""

    def test_loop_event_with_timestamp(self):
        """Test creating LoopEvent with timestamp."""
        now = datetime.now()
        event = LoopEvent(
            type="tool_call",
            tool_name="read_file",
            tool_id="test-123",
            timestamp=now,
        )
        assert event.timestamp == now

    def test_loop_event_without_timestamp(self):
        """Test creating LoopEvent without timestamp defaults to None."""
        event = LoopEvent(type="text", content="Hello")
        assert event.timestamp is None

    def test_loop_event_tool_result_with_id(self):
        """Test tool_result event includes tool_id."""
        event = LoopEvent(
            type="tool_result",
            content="File content",
            tool_name="read_file",
            tool_id="test-123",
            cached=False,
            timestamp=datetime.now(),
        )
        assert event.tool_id == "test-123"


# =============================================================================
# Integration Tests
# =============================================================================


class TestToolProgressIntegration:
    """Integration tests for tool progress tracking."""

    @pytest.mark.asyncio
    async def test_tool_progress_in_agent_loop(self):
        """Test tool progress items are created during agent loop."""
        provider = AsyncMock(spec=LLMProvider)
        provider.complete.return_value = LLMResponse(content=[], stop_reason="end_turn")

        session = Session(
            id="test-session",
            messages=[],
            tool_history=[],
            working_directory=".",
        )

        agent = Agent(provider, ToolRegistry(), None, session)
        app = PygentApp(agent=agent)

        async with app.run_test():
            panel = app.query_one(ToolPanel)
            # Initially empty
            assert panel.get_running_count() == 0


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests for ToolProgress using hypothesis."""

    @given(
        tool_id=st.text(min_size=1, max_size=36, alphabet=st.characters(categories=["L", "N", "P"])),
        tool_name=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=["L", "N"])),
    )
    @hypothesis_settings(max_examples=20)
    def test_tool_progress_item_creation_any_values(self, tool_id, tool_name):
        """Test ToolProgressItem accepts any reasonable values."""
        item = ToolProgressItem(tool_id=tool_id, tool_name=tool_name)
        assert item.tool_id == tool_id
        assert item.tool_name == tool_name
        assert item.status == ToolStatus.RUNNING

    @given(status=st.sampled_from(list(ToolStatus)))
    @hypothesis_settings(max_examples=10)
    def test_tool_progress_item_any_status(self, status):
        """Test ToolProgressItem works with any status."""
        item = ToolProgressItem(tool_id="test", tool_name="tool", status=status)
        assert item.status == status
        assert f"tool-progress-{status.value}" in item.classes

    @given(
        result=st.text(min_size=0, max_size=500),
        is_error=st.booleans(),
        cached=st.booleans(),
    )
    @hypothesis_settings(max_examples=20)
    def test_tool_progress_item_update_any_values(self, result, is_error, cached):
        """Test ToolProgressItem update_status works with any values."""
        item = ToolProgressItem(tool_id="test", tool_name="tool")

        status = ToolStatus.ERROR if is_error else ToolStatus.COMPLETED
        item.update_status(status=status, result=result, is_error=is_error, cached=cached)

        assert item.result == result
        assert item.is_error == is_error

    @given(elapsed_seconds=st.floats(min_value=0, max_value=3600))
    @hypothesis_settings(max_examples=20)
    def test_format_elapsed_time_any_duration(self, elapsed_seconds):
        """Test _format_elapsed_time works with any duration."""
        start = datetime.now()
        end = start + timedelta(seconds=elapsed_seconds)
        result = _format_elapsed_time(start, end)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    @given(tool_count=st.integers(min_value=0, max_value=20))
    @hypothesis_settings(max_examples=10)
    async def test_tool_panel_multiple_tools_property(self, tool_count):
        """Test ToolPanel handles varying numbers of tools."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            for i in range(tool_count):
                panel.append_tool_call(tool_name=f"tool{i}", tool_id=f"id-{i}")

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == tool_count
            assert panel.get_running_count() == tool_count


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_tool_panel_with_empty_tool_id(self):
        """Test panel handles empty tool_id."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)
            panel.append_tool_call(tool_name="tool", tool_id="")
            assert len(panel.query_one("#tool-output").query(ToolProgressItem)) == 1

    @pytest.mark.asyncio
    async def test_tool_panel_with_very_long_tool_name(self):
        """Test panel handles very long tool names."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)
            long_name = "a" * 200
            panel.append_tool_call(tool_name=long_name, tool_id="test")
            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].tool_name == long_name

    @pytest.mark.asyncio
    async def test_tool_panel_with_special_characters(self):
        """Test panel handles special characters in tool names."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)
            special_name = "tool-<>\"'&;`$"
            panel.append_tool_call(tool_name=special_name, tool_id="test")
            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert items[0].tool_name == special_name

    @pytest.mark.asyncio
    async def test_tool_panel_update_same_tool_twice(self):
        """Test updating the same tool twice uses latest result."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="tool", tool_id="test-123")
            panel.update_tool_result(tool_id="test-123", tool_name="tool", result="First")
            panel.update_tool_result(tool_id="test-123", tool_name="tool", result="Second")

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            assert len(items) == 1
            assert items[0].result == "Second"

    @pytest.mark.asyncio
    async def test_tool_progress_newlines_in_result(self):
        """Test tool progress handles newlines in result."""
        app = PygentApp()
        async with app.run_test():
            panel = app.query_one(ToolPanel)

            panel.append_tool_call(tool_name="tool", tool_id="test-123")
            panel.update_tool_result(
                tool_id="test-123",
                tool_name="tool",
                result="Line1\nLine2\nLine3",
            )

            items = panel.query_one("#tool-output").query(ToolProgressItem)
            text = items[0]._build_display_text()
            # Newlines should be replaced with spaces in display
            assert "\n" not in text

    def test_format_elapsed_time_zero(self):
        """Test formatting zero elapsed time."""
        start = datetime.now()
        result = _format_elapsed_time(start, start)
        assert result == "<0.1s"

    def test_format_elapsed_time_negative(self):
        """Test formatting negative elapsed time (end before start)."""
        end = datetime.now()
        start = end + timedelta(seconds=10)
        # Should not crash, may show <0.1s or negative value
        result = _format_elapsed_time(start, end)
        assert isinstance(result, str)
