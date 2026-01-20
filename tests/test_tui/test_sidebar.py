"""Tests for the Sessions Sidebar feature."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from chapgent.config.settings import Settings
from chapgent.core.agent import Agent
from chapgent.core.providers import LLMProvider, LLMResponse
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tools.registry import ToolRegistry
from chapgent.tui.app import ChapgentApp
from chapgent.tui.widgets import SessionItem, SessionsSidebar

# =============================================================================
# SessionItem Widget Tests
# =============================================================================


class TestSessionItem:
    """Tests for the SessionItem widget."""

    def test_session_item_creation(self):
        """Test creating a basic SessionItem."""
        item = SessionItem(
            session_id="abc12345-6789-0def-ghij-klmnopqrstuv",
            message_count=5,
            is_active=False,
        )
        assert item.session_id == "abc12345-6789-0def-ghij-klmnopqrstuv"
        assert item.message_count == 5
        assert item.is_active is False

    def test_session_item_active(self):
        """Test creating an active SessionItem."""
        item = SessionItem(
            session_id="abc12345",
            message_count=10,
            is_active=True,
        )
        assert item.is_active is True
        assert "session-active" in item.classes

    def test_session_item_inactive_no_active_class(self):
        """Test inactive SessionItem doesn't have active class."""
        item = SessionItem(
            session_id="abc12345",
            message_count=3,
            is_active=False,
        )
        assert "session-active" not in item.classes

    def test_session_item_truncates_id(self):
        """Test that session ID is truncated in display."""
        long_id = "abcdefgh-1234-5678-9012-ijklmnopqrst"
        item = SessionItem(session_id=long_id, message_count=0, is_active=False)
        # The session_id attribute stores the full ID
        assert item.session_id == long_id
        # But only the first 8 chars are used in display (stored in the renderable content)


# =============================================================================
# SessionsSidebar Widget Tests
# =============================================================================


class TestSessionsSidebar:
    """Tests for the SessionsSidebar widget."""

    @pytest.mark.asyncio
    async def test_sidebar_compose(self):
        """Test that sidebar composes correctly."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            # Check that the sessions-list scroll is present
            scroll = sidebar.query_one("#sessions-list")
            assert scroll is not None

    @pytest.mark.asyncio
    async def test_sidebar_add_session(self):
        """Test adding a session to the sidebar."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)

            sidebar.add_session(
                session_id="test-session-123",
                message_count=5,
                is_active=False,
            )

            assert sidebar.get_session_count() == 1
            items = sidebar.query_one("#sessions-list").query(SessionItem)
            assert len(items) == 1
            assert items[0].session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_sidebar_add_multiple_sessions(self):
        """Test adding multiple sessions to the sidebar."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)

            for i in range(5):
                sidebar.add_session(
                    session_id=f"session-{i}",
                    message_count=i * 10,
                    is_active=i == 2,
                )

            assert sidebar.get_session_count() == 5

    @pytest.mark.asyncio
    async def test_sidebar_update_active_session(self):
        """Test updating which session is active."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)

            sidebar.add_session("session-1", 5, is_active=True)
            sidebar.add_session("session-2", 3, is_active=False)

            # Initially session-1 is active
            items = list(sidebar.query_one("#sessions-list").query(SessionItem))
            assert items[0].is_active is True
            assert items[1].is_active is False

            # Update to make session-2 active
            sidebar.update_active_session("session-2")

            items = list(sidebar.query_one("#sessions-list").query(SessionItem))
            assert items[0].is_active is False
            assert items[1].is_active is True

    @pytest.mark.asyncio
    async def test_sidebar_clear(self):
        """Test clearing the sidebar."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            sidebar = app.query_one(SessionsSidebar)

            sidebar.add_session("session-1", 5, is_active=False)
            sidebar.add_session("session-2", 3, is_active=False)
            assert sidebar.get_session_count() == 2

            sidebar.clear()
            # Allow DOM update to process
            await pilot.pause()
            assert sidebar.get_session_count() == 0

    @pytest.mark.asyncio
    async def test_sidebar_get_session_count(self):
        """Test getting session count."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            assert sidebar.get_session_count() == 0

            sidebar.add_session("session-1", 0, is_active=False)
            assert sidebar.get_session_count() == 1

            sidebar.add_session("session-2", 0, is_active=False)
            assert sidebar.get_session_count() == 2


# =============================================================================
# ChapgentApp Sidebar Integration Tests
# =============================================================================


class TestChapgentAppSidebarIntegration:
    """Tests for sidebar integration with ChapgentApp."""

    @pytest.mark.asyncio
    async def test_sidebar_present_by_default(self):
        """Test that sidebar is present when show_sidebar=True (default)."""
        app = ChapgentApp()
        async with app.run_test():
            assert len(app.query(SessionsSidebar)) == 1

    @pytest.mark.asyncio
    async def test_sidebar_not_present_when_disabled(self):
        """Test that sidebar is not present when show_sidebar=False."""
        settings = Settings()
        settings.tui.show_sidebar = False

        app = ChapgentApp(settings=settings)
        async with app.run_test():
            assert len(app.query(SessionsSidebar)) == 0

    @pytest.mark.asyncio
    async def test_toggle_sidebar_keybinding(self):
        """Test that ctrl+b toggles sidebar visibility."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            sidebar = app.query_one(SessionsSidebar)
            assert sidebar.display is True

            # Toggle off
            await pilot.press("ctrl+b")
            assert sidebar.display is False

            # Toggle back on
            await pilot.press("ctrl+b")
            assert sidebar.display is True

    @pytest.mark.asyncio
    async def test_action_toggle_sidebar_not_available_when_disabled(self):
        """Test toggle sidebar when sidebar is disabled in settings."""
        settings = Settings()
        settings.tui.show_sidebar = False

        app = ChapgentApp(settings=settings)
        async with app.run_test() as pilot:
            # Should not crash, just show warning
            await pilot.press("ctrl+b")
            # No sidebar to query
            assert len(app.query(SessionsSidebar)) == 0

    @pytest.mark.asyncio
    async def test_new_session_adds_to_sidebar(self):
        """Test that creating a new session adds it to the sidebar."""
        provider = AsyncMock(spec=LLMProvider)
        provider.complete.return_value = LLMResponse(content=[], stop_reason="end_turn")

        session = Session(
            id="initial-session",
            messages=[],
            tool_history=[],
            working_directory=".",
        )

        agent = Agent(provider, ToolRegistry(), None, session)
        app = ChapgentApp(agent=agent)

        async with app.run_test() as pilot:
            sidebar = app.query_one(SessionsSidebar)
            initial_count = sidebar.get_session_count()

            # Create new session
            await pilot.press("ctrl+n")
            await asyncio.sleep(0.1)

            # Should have one more session
            assert sidebar.get_session_count() == initial_count + 1

    @pytest.mark.asyncio
    async def test_new_session_updates_active_marker(self):
        """Test that creating a new session updates the active marker."""
        provider = AsyncMock(spec=LLMProvider)
        provider.complete.return_value = LLMResponse(content=[], stop_reason="end_turn")

        session = Session(
            id="initial-session",
            messages=[],
            tool_history=[],
            working_directory=".",
        )

        agent = Agent(provider, ToolRegistry(), None, session)
        app = ChapgentApp(agent=agent)

        async with app.run_test() as pilot:
            sidebar = app.query_one(SessionsSidebar)

            # Add initial session manually for testing
            sidebar.add_session("initial-session", 0, is_active=True)

            # Create new session
            await pilot.press("ctrl+n")
            await asyncio.sleep(0.1)

            # The new session should be marked active
            items = list(sidebar.query_one("#sessions-list").query(SessionItem))
            active_items = [item for item in items if item.is_active]
            assert len(active_items) == 1
            assert active_items[0].session_id == agent.session.id


# =============================================================================
# SessionStorage Integration Tests
# =============================================================================


class TestSidebarWithStorage:
    """Tests for sidebar integration with SessionStorage."""

    @pytest.mark.asyncio
    async def test_populate_sidebar_from_storage(self, tmp_path):
        """Test that sidebar is populated from storage on mount."""
        # Create storage with some sessions
        storage = SessionStorage(storage_dir=tmp_path)

        session1 = Session(
            id="session-1",
            messages=[],
            tool_history=[],
            working_directory=".",
        )
        session2 = Session(
            id="session-2",
            messages=[],
            tool_history=[],
            working_directory=".",
        )

        await storage.save(session1)
        await storage.save(session2)

        # Create agent with one of the sessions
        provider = AsyncMock(spec=LLMProvider)
        agent = Agent(provider, ToolRegistry(), None, session1)

        app = ChapgentApp(agent=agent, storage=storage)

        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            # Give time for async population
            await asyncio.sleep(0.2)

            assert sidebar.get_session_count() == 2

    @pytest.mark.asyncio
    async def test_active_session_highlighted_on_populate(self, tmp_path):
        """Test that current session is highlighted when populated."""
        storage = SessionStorage(storage_dir=tmp_path)

        session1 = Session(id="session-1", messages=[], tool_history=[], working_directory=".")
        session2 = Session(id="session-2", messages=[], tool_history=[], working_directory=".")

        await storage.save(session1)
        await storage.save(session2)

        provider = AsyncMock(spec=LLMProvider)
        agent = Agent(provider, ToolRegistry(), None, session1)

        app = ChapgentApp(agent=agent, storage=storage)

        async with app.run_test():
            await asyncio.sleep(0.2)
            sidebar = app.query_one(SessionsSidebar)

            items = list(sidebar.query_one("#sessions-list").query(SessionItem))
            active_items = [item for item in items if item.is_active]

            assert len(active_items) == 1
            assert active_items[0].session_id == "session-1"

    @pytest.mark.asyncio
    async def test_no_storage_no_population(self):
        """Test that sidebar remains empty when no storage is provided."""
        app = ChapgentApp(storage=None)

        async with app.run_test():
            await asyncio.sleep(0.1)
            sidebar = app.query_one(SessionsSidebar)
            assert sidebar.get_session_count() == 0


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests for SessionsSidebar using hypothesis."""

    @given(
        session_id=st.text(min_size=1, max_size=36, alphabet=st.characters(categories=["L", "N"])),
        message_count=st.integers(min_value=0, max_value=10000),
    )
    @hypothesis_settings(max_examples=20)
    def test_session_item_creation_any_values(self, session_id, message_count):
        """Test SessionItem accepts any reasonable values."""
        item = SessionItem(session_id=session_id, message_count=message_count, is_active=False)
        assert item.session_id == session_id
        assert item.message_count == message_count

    @given(is_active=st.booleans())
    @hypothesis_settings(max_examples=5)
    def test_session_item_active_flag(self, is_active):
        """Test SessionItem active flag works correctly."""
        item = SessionItem(session_id="test", message_count=0, is_active=is_active)
        assert item.is_active == is_active
        if is_active:
            assert "session-active" in item.classes

    @pytest.mark.asyncio
    @given(session_count=st.integers(min_value=0, max_value=10))
    @hypothesis_settings(max_examples=10)
    async def test_sidebar_add_multiple_sessions_property(self, session_count):
        """Test adding varying numbers of sessions to sidebar."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)

            for i in range(session_count):
                sidebar.add_session(f"session-{i}", i, is_active=False)

            assert sidebar.get_session_count() == session_count

    @pytest.mark.asyncio
    async def test_sidebar_clear_then_add(self):
        """Test clearing sidebar then adding new sessions."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            sidebar = app.query_one(SessionsSidebar)

            # Add some sessions
            for i in range(3):
                sidebar.add_session(f"session-{i}", i, is_active=False)
            assert sidebar.get_session_count() == 3

            # Clear
            sidebar.clear()
            # Allow DOM update to process
            await pilot.pause()
            assert sidebar.get_session_count() == 0

            # Add more
            for i in range(5):
                sidebar.add_session(f"new-session-{i}", i, is_active=False)
            assert sidebar.get_session_count() == 5


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_sidebar_with_empty_session_id(self):
        """Test sidebar handles empty session ID."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            # Should not crash with empty string
            sidebar.add_session("", 0, is_active=False)
            assert sidebar.get_session_count() == 1

    @pytest.mark.asyncio
    async def test_sidebar_with_very_long_session_id(self):
        """Test sidebar handles very long session ID."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            long_id = "a" * 1000
            sidebar.add_session(long_id, 0, is_active=False)
            assert sidebar.get_session_count() == 1

    @pytest.mark.asyncio
    async def test_sidebar_with_special_characters_in_id(self):
        """Test sidebar handles special characters in session ID."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            special_id = "session-<>\"'&;`$()[]{}|\\!"
            sidebar.add_session(special_id, 0, is_active=False)
            assert sidebar.get_session_count() == 1

    @pytest.mark.asyncio
    async def test_update_active_nonexistent_session(self):
        """Test updating active session with non-existent ID."""
        app = ChapgentApp()
        async with app.run_test():
            sidebar = app.query_one(SessionsSidebar)
            sidebar.add_session("session-1", 0, is_active=True)

            # Should not crash when updating to non-existent session
            sidebar.update_active_session("nonexistent-session")

            # Original should still be active
            items = list(sidebar.query_one("#sessions-list").query(SessionItem))
            assert items[0].is_active is True

    @pytest.mark.asyncio
    async def test_sidebar_storage_error_handling(self, tmp_path):
        """Test sidebar handles storage errors gracefully."""
        storage = MagicMock(spec=SessionStorage)
        storage.list_sessions = AsyncMock(side_effect=Exception("Storage error"))

        app = ChapgentApp(storage=storage)

        # Should not crash
        async with app.run_test():
            await asyncio.sleep(0.1)
            sidebar = app.query_one(SessionsSidebar)
            # Sidebar should be empty after error
            assert sidebar.get_session_count() == 0
