from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from pygent.core.agent import Agent
from pygent.tui.widgets import ConversationPanel, MessageInput, PermissionPrompt, ToolPanel


class PygentApp(App):
    """Main Textual application for Pygent."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+s", "save_session", "Save"),
        ("ctrl+p", "toggle_permissions", "Toggle Permissions"),
    ]

    def __init__(self, agent: Agent | None = None, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield ConversationPanel()
        yield ToolPanel()
        yield MessageInput(id="input")
        yield Footer()

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

    async def get_permission(self, tool_name: str, args: dict) -> bool:
        """Prompt user for permission to execute a tool."""
        # We need to wrap the screen push in a way that we can await the result
        # app.push_screen returns a awaitable that waits for dismissal
        # but we need the result.
        # push_screen_wait is not a standard method, but push_screen returns an awaitable
        # if wait_for_dismiss=True (which is not default).
        # Actually push_screen returns a Future-like object or we can use wait_for_return?
        # Textual's standard pattern for modal result is:
        return await self.push_screen_wait(PermissionPrompt(tool_name, args))


if __name__ == "__main__":
    # TODO: In real usage, this should load config and init agent
    app = PygentApp()
    app.run()
