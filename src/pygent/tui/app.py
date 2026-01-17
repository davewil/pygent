from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from pygent.config.settings import Settings
from pygent.core.agent import Agent
from pygent.session.models import Session
from pygent.session.storage import SessionStorage
from pygent.tui.widgets import (
    CommandPalette,
    ConversationPanel,
    MessageInput,
    PermissionPrompt,
    SessionsSidebar,
    ToolPanel,
)


class PygentApp(App[None]):
    """Main Textual application for Pygent."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+s", "save_session", "Save"),
        ("ctrl+p", "toggle_permissions", "Toggle Permissions"),
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+shift+p", "command_palette", "Commands"),
        ("ctrl+t", "toggle_tools", "Toggle Tools"),
        ("ctrl+l", "clear", "Clear"),
    ]

    def __init__(
        self,
        agent: Agent | None = None,
        storage: SessionStorage | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.storage = storage
        self.settings = settings or Settings()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Horizontal(id="main-content"):
            if self.settings.tui.show_sidebar:
                yield SessionsSidebar()
            yield ConversationPanel()
            if self.settings.tui.show_tool_panel:
                yield ToolPanel()
        yield MessageInput(id="input")
        yield Footer()

    async def on_mount(self) -> None:
        """Handle app mount."""
        self.theme = self.settings.tui.theme
        if self.agent:
            self.title = f"Pygent - {self.agent.session.id[:8]}"

        # Populate sessions sidebar if available
        await self._populate_sessions_sidebar()

    async def on_input_submitted(self, message: MessageInput.Submitted) -> None:
        """Handle input submission."""
        user_input = message.value
        if not user_input.strip():
            return

        # Clear input
        message.input.value = ""

        # Update UI
        self.query_one(ConversationPanel).append_user_message(user_input)

        # Run agent
        if self.agent:
            self.run_agent_loop(user_input)
        else:
            self.query_one(ConversationPanel).append_assistant_message("Error: No agent attached to this session.")

    @work(exclusive=True)
    async def run_agent_loop(self, user_input: str) -> None:
        """Run the agent loop in the background."""
        if not self.agent:
            return

        async for event in self.agent.run(user_input):
            if event.type == "text" and event.content:
                self.query_one(ConversationPanel).append_assistant_message(event.content)
            elif event.type == "tool_call" and event.tool_name and event.tool_id:
                try:
                    self.query_one(ToolPanel).append_tool_call(
                        tool_name=event.tool_name,
                        tool_id=event.tool_id,
                        start_time=event.timestamp,
                    )
                except Exception:
                    pass  # ToolPanel might not be present
            elif event.type == "tool_result" and event.tool_name and event.tool_id and event.content is not None:
                try:
                    self.query_one(ToolPanel).update_tool_result(
                        tool_id=event.tool_id,
                        tool_name=event.tool_name,
                        result=event.content,
                        is_error=False,
                        cached=event.cached,
                    )
                except Exception:
                    pass  # ToolPanel might not be present
            elif event.type == "permission_denied" and event.tool_name:
                try:
                    self.query_one(ToolPanel).update_permission_denied(
                        tool_id=event.tool_id or "",
                        tool_name=event.tool_name,
                    )
                except Exception:
                    pass  # ToolPanel might not be present

    async def get_permission(self, tool_name: str, args: dict[str, Any]) -> bool:
        """Prompt user for permission to execute a tool."""
        # We need to wrap the screen push in a way that we can await the result
        # app.push_screen returns a awaitable that waits for dismissal
        # but we need the result.
        # push_screen_wait is not a standard method, but push_screen returns an awaitable
        # if wait_for_dismiss=True (which is not default).
        # Actually push_screen returns a Future-like object or we can use wait_for_return?
        # Textual's standard pattern for modal result is:
        return await self.push_screen_wait(PermissionPrompt(tool_name, args))

    async def action_save_session(self) -> None:
        """Save the current session."""
        if not self.agent or not self.storage:
            self.notify("Error: No agent or storage available to save.", severity="error")
            return

        try:
            await self.storage.save(self.agent.session)
            self.notify(f"Session {self.agent.session.id} saved.", severity="information")
        except Exception as e:
            self.notify(f"Error saving session: {e}", severity="error")

    async def action_new_session(self) -> None:
        """Start a new session."""
        import uuid

        if not self.agent:
            return

        # Create new session
        new_session = Session(
            id=str(uuid.uuid4()),
            working_directory=".",
            messages=[],
            tool_history=[],
        )
        self.agent.session = new_session

        # Update UI
        self.query_one(ConversationPanel).clear()
        try:
            self.query_one(ToolPanel).clear()
        except Exception:
            pass  # ToolPanel might not be present

        # Update sidebar - add new session and mark it active
        try:
            sidebar = self.query_one(SessionsSidebar)
            sidebar.add_session(
                session_id=new_session.id,
                message_count=0,
                is_active=True,
            )
            sidebar.update_active_session(new_session.id)
        except Exception:
            pass  # Sidebar might not be present

        self.title = f"Pygent - {new_session.id[:8]}"
        self.notify("Started new session.")

    def action_toggle_permissions(self) -> None:
        """Toggle tool execution permissions."""
        if not self.agent:
            return

        pm = self.agent.permissions
        pm.session_override = not pm.session_override
        state = "ENABLED (Auto-approve MEDIUM risk)" if pm.session_override else "DISABLED (Always prompt)"
        self.notify(f"Permission Override: {state}", severity="information")

    def action_toggle_sidebar(self) -> None:
        """Toggle the sessions sidebar visibility."""
        try:
            sidebar = self.query_one(SessionsSidebar)
            sidebar.display = not sidebar.display
            state = "shown" if sidebar.display else "hidden"
            self.notify(f"Sessions sidebar {state}.", severity="information")
        except Exception:
            # Sidebar not present in compose (show_sidebar=False in settings)
            self.notify("Sessions sidebar not available.", severity="warning")

    def action_toggle_tools(self) -> None:
        """Toggle the tool panel visibility."""
        try:
            tool_panel = self.query_one(ToolPanel)
            tool_panel.display = not tool_panel.display
            state = "shown" if tool_panel.display else "hidden"
            self.notify(f"Tool panel {state}.", severity="information")
        except Exception:
            # Tool panel not present in compose (show_tool_panel=False in settings)
            self.notify("Tool panel not available.", severity="warning")

    def action_clear(self) -> None:
        """Clear the current conversation."""
        try:
            self.query_one(ConversationPanel).clear()
            self.notify("Conversation cleared.", severity="information")
        except Exception:
            pass

        try:
            self.query_one(ToolPanel).clear()
        except Exception:
            pass  # ToolPanel might not be present

    def action_command_palette(self) -> None:
        """Show the command palette."""

        def handle_command(result: str | None) -> None:
            """Handle the selected command from the palette."""
            if result is not None:
                # Execute the action corresponding to the selected command
                action_method = getattr(self, f"action_{result}", None)
                if action_method is not None:
                    # Use call_later to run the action outside of the callback
                    self.call_later(action_method)

        self.push_screen(CommandPalette(), callback=handle_command)

    async def _populate_sessions_sidebar(self) -> None:
        """Populate the sessions sidebar with saved sessions."""
        if not self.storage or not self.settings.tui.show_sidebar:
            return

        try:
            sidebar = self.query_one(SessionsSidebar)
        except Exception:
            return  # Sidebar not present

        # Get current session ID if available
        current_session_id = self.agent.session.id if self.agent else None

        # Load and display sessions
        try:
            sessions = await self.storage.list_sessions()
            for session_summary in sessions:
                is_active = session_summary.id == current_session_id
                sidebar.add_session(
                    session_id=session_summary.id,
                    message_count=session_summary.message_count,
                    is_active=is_active,
                )
        except Exception as e:
            self.notify(f"Error loading sessions: {e}", severity="warning")


if __name__ == "__main__":
    # TODO: In real usage, this should load config and init agent
    app = PygentApp()
    app.run()
