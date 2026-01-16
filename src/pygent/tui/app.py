from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from pygent.config.settings import Settings
from pygent.core.agent import Agent
from pygent.session.models import Session
from pygent.session.storage import SessionStorage
from pygent.tui.widgets import ConversationPanel, MessageInput, PermissionPrompt, ToolPanel


class PygentApp(App[None]):
    """Main Textual application for Pygent."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+s", "save_session", "Save"),
        ("ctrl+p", "toggle_permissions", "Toggle Permissions"),
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
            yield ConversationPanel()
            if self.settings.tui.show_tool_panel:
                yield ToolPanel()
        yield MessageInput(id="input")
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount."""
        self.theme = self.settings.tui.theme
        if self.agent:
            self.title = f"Pygent - {self.agent.session.id[:8]}"

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
            print(f"DEBUG: Event received: {event.type}")
            if event.type == "text" and event.content:
                self.query_one(ConversationPanel).append_assistant_message(event.content)
            elif event.type == "tool_call" and event.tool_name and event.tool_id:
                self.query_one(ToolPanel).append_tool_call(event.tool_name, event.tool_id)
            elif event.type == "tool_result" and event.tool_name and event.content:
                self.query_one(ToolPanel).append_tool_result(event.tool_name, event.content)
            elif event.type == "permission_denied":
                self.query_one(ToolPanel).append_tool_result(str(event.tool_name), "Permission Denied")

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


if __name__ == "__main__":
    # TODO: In real usage, this should load config and init agent
    app = PygentApp()
    app.run()
