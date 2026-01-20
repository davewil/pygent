from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from chapgent.config.settings import Settings
from chapgent.core.agent import Agent
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tui.commands import format_command_list, get_command_help, parse_slash_command
from chapgent.tui.screens import ThemePickerScreen
from chapgent.tui.widgets import (
    CommandPalette,
    ConversationPanel,
    MessageInput,
    PermissionPrompt,
    SessionsSidebar,
    ToolPanel,
)


class ChapgentApp(App[None]):
    """Main Textual application for Chapgent."""

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
            self.title = f"Chapgent - {self.agent.session.id[:8]}"

        # Populate sessions sidebar if available
        await self._populate_sessions_sidebar()

    async def on_input_submitted(self, message: MessageInput.Submitted) -> None:
        """Handle input submission."""
        user_input = message.value
        if not user_input.strip():
            return

        # Clear input
        message.input.value = ""

        # Check for slash commands
        if user_input.strip().startswith("/"):
            await self._handle_slash_command(user_input.strip())
            return

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

        self.title = f"Chapgent - {new_session.id[:8]}"
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

    def action_show_theme_picker(self) -> None:
        """Show the theme picker modal."""

        def handle_theme(result: str | None) -> None:
            """Handle the selected theme from the picker."""
            if result is not None:
                # Theme was already applied during preview
                # Persist to config
                try:
                    from chapgent.config.writer import save_config_value

                    save_config_value("tui.theme", result)
                    self.notify(f"Theme set to: {result}", severity="information")
                except Exception as e:
                    self.notify(f"Error saving theme: {e}", severity="error")

        current_theme = self.theme if hasattr(self, "theme") else None
        self.push_screen(ThemePickerScreen(current_theme=current_theme), callback=handle_theme)

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

    async def _handle_slash_command(self, user_input: str) -> None:
        """Handle a slash command.

        Args:
            user_input: The full user input starting with '/'.
        """
        command, args = parse_slash_command(user_input)

        if command is None:
            # Unknown command
            self.notify(f"Unknown command: {user_input.split()[0]}", severity="warning")
            self.notify("Type /help for available commands.", severity="information")
            return

        # Handle special commands that need arguments
        if command.name == "help":
            await self._handle_help_command(args)
            return

        if command.name == "config":
            await self._handle_config_command(args)
            return

        # Map action names to actual action methods
        action_name = f"action_{command.action}"
        action_method = getattr(self, action_name, None)

        if action_method is not None:
            # Call the action method
            if callable(action_method):
                result = action_method()
                # If it's a coroutine, await it
                if hasattr(result, "__await__"):
                    await result
        else:
            self.notify(f"Action not implemented: {command.action}", severity="warning")

    async def _handle_help_command(self, args: list[str]) -> None:
        """Handle the /help command.

        Args:
            args: Command arguments (optional topic name).
        """
        if not args:
            # Show list of all commands
            help_text = format_command_list()
            self.query_one(ConversationPanel).append_assistant_message(help_text)
            return

        # Show help for a specific command
        topic = args[0]
        topic_help = get_command_help(topic)

        if topic_help is None:
            self.notify(f"Unknown help topic: {topic}", severity="warning")
            self.notify("Type /help for available commands.", severity="information")
            return

        self.query_one(ConversationPanel).append_assistant_message(topic_help)

    async def _handle_config_command(self, args: list[str]) -> None:
        """Handle the /config command.

        Args:
            args: Command arguments (e.g., ["show"] or ["set", "key", "value"]).
        """
        if not args or args[0] == "show":
            # Show current configuration
            if self.settings:
                config_text = (
                    "Current Configuration:\n"
                    f"  LLM Model: {self.settings.llm.model}\n"
                    f"  LLM Provider: {self.settings.llm.provider}\n"
                    f"  Max Tokens: {self.settings.llm.max_tokens}\n"
                    f"  Theme: {self.settings.tui.theme}\n"
                    f"  Show Tool Panel: {self.settings.tui.show_tool_panel}\n"
                    f"  Show Sidebar: {self.settings.tui.show_sidebar}"
                )
                self.query_one(ConversationPanel).append_assistant_message(config_text)
            else:
                self.notify("No configuration available.", severity="warning")
            return

        if args[0] == "set":
            if len(args) < 3:
                self.notify("Usage: /config set <key> <value>", severity="warning")
                return

            key = args[1]
            value = " ".join(args[2:])  # Join remaining args as value

            try:
                from chapgent.config.writer import save_config_value

                config_path, typed_value = save_config_value(key, value)
                self.notify(f"Set {key} = {typed_value}", severity="information")

                # If theme was changed, apply it immediately
                if key == "tui.theme" and isinstance(typed_value, str):
                    self.theme = typed_value
            except Exception as e:
                self.notify(f"Error setting config: {e}", severity="error")
            return

        self.notify(f"Unknown config subcommand: {args[0]}", severity="warning")
        self.notify("Use /config show or /config set <key> <value>", severity="information")


if __name__ == "__main__":
    # TODO: In real usage, this should load config and init agent
    app = ChapgentApp()
    app.run()
