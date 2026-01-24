from typing import TYPE_CHECKING, Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from chapgent.config.settings import Settings
from chapgent.core.agent import Agent
from chapgent.core.logging import logger
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tui.commands import parse_slash_command

if TYPE_CHECKING:
    from chapgent.core.stream_provider import StreamingClaudeCodeProvider
from chapgent.tui.screens import (
    ConfigShowScreen,
    HelpScreen,
    LLMSettingsScreen,
    SystemPromptScreen,
    ThemePickerScreen,
    ToolsScreen,
    TUISettingsScreen,
)
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
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+p", "command_palette", "Commands"),
        ("ctrl+t", "toggle_tools", "Toggle Tools"),
        ("ctrl+l", "clear", "Clear"),
        ("ctrl+shift+c", "copy_selection", "Copy"),
    ]

    def __init__(
        self,
        agent: Agent | None = None,
        storage: SessionStorage | None = None,
        settings: Settings | None = None,
        streaming_provider: "StreamingClaudeCodeProvider | None" = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.storage = storage
        self.settings = settings or Settings()
        self.streaming_provider = streaming_provider
        self._streaming_content: str = ""  # Buffer for accumulated streaming content

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

        # Run agent (streaming or regular mode)
        logger.debug(f"on_input_submitted: streaming_provider={self.streaming_provider is not None}, agent={self.agent is not None}")
        if self.streaming_provider:
            logger.debug("Calling run_streaming_agent_loop")
            self.run_streaming_agent_loop(user_input)
        elif self.agent:
            logger.debug("Calling run_agent_loop")
            self.run_agent_loop(user_input)
        else:
            self.query_one(ConversationPanel).append_assistant_message("Error: No agent attached to this session.")

    @work(exclusive=True)
    async def run_agent_loop(self, user_input: str) -> None:
        """Run the agent loop in the background."""
        if not self.agent:
            return

        try:
            async for event in self.agent.run(user_input):
                if event.type == "text" and event.content:
                    self.query_one(ConversationPanel).append_assistant_message(event.content)
                elif event.type == "llm_error":
                    error_msg = f"LLM Error: {event.error_message or event.content or 'Unknown error'}"
                    self.query_one(ConversationPanel).append_assistant_message(error_msg)
                    self.notify(error_msg, severity="error")
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
        except Exception as e:
            error_msg = f"Agent error: {e}"
            self.query_one(ConversationPanel).append_assistant_message(error_msg)
            self.notify(error_msg, severity="error")

    @work(exclusive=True)
    async def run_streaming_agent_loop(self, user_input: str) -> None:
        """Run the streaming agent loop for Claude Max mode.

        This method uses the StreamingClaudeCodeProvider to stream responses
        directly from Claude Code CLI, updating the UI incrementally.
        """
        logger.info(f"run_streaming_agent_loop called with input: {user_input[:50]}...")
        if not self.streaming_provider:
            logger.error("No streaming provider in run_streaming_agent_loop!")
            return

        from chapgent.core.loop import streaming_conversation_loop

        logger.debug(f"Starting streaming loop for: {user_input[:50]}...")

        # Reset streaming content buffer
        self._streaming_content = ""

        # Create streaming message placeholder
        panel = self.query_one(ConversationPanel)
        panel.append_streaming_message()

        try:
            event_count = 0
            async for event in streaming_conversation_loop(
                self.streaming_provider,
                user_input,
            ):
                event_count += 1
                logger.debug(f"Event {event_count}: type={event.type}, content_len={len(event.content) if event.content else 0}")

                if event.type == "text_delta" and event.content:
                    # Accumulate text deltas and update the streaming message
                    self._streaming_content += event.content
                    panel.update_streaming_message(self._streaming_content)
                    logger.debug(f"Updated message, total len={len(self._streaming_content)}")

                elif event.type == "tool_call" and event.tool_name and event.tool_id:
                    try:
                        self.query_one(ToolPanel).append_tool_call(
                            tool_name=event.tool_name,
                            tool_id=event.tool_id,
                            start_time=event.timestamp,
                        )
                    except Exception:
                        pass  # ToolPanel might not be present

                elif event.type == "tool_result" and event.tool_id and event.content is not None:
                    try:
                        self.query_one(ToolPanel).update_tool_result(
                            tool_id=event.tool_id,
                            tool_name=event.tool_name or "",
                            result=event.content,
                            is_error=False,
                            cached=event.cached,
                        )
                    except Exception:
                        pass  # ToolPanel might not be present

                elif event.type == "llm_error":
                    error_msg = f"LLM Error: {event.error_message or event.content or 'Unknown error'}"
                    # Finalize any streaming message first
                    panel.finalize_streaming_message()
                    panel.append_assistant_message(error_msg)
                    self.notify(error_msg, severity="error")

                elif event.type == "finished":
                    # Finalize the streaming message
                    panel.finalize_streaming_message()
                    logger.info(f"Streaming finished with {event_count} events")

        except Exception as e:
            import traceback
            error_msg = f"Streaming error: {e}"
            logger.error(f"Streaming error: {e}\n{traceback.format_exc()}")
            panel.finalize_streaming_message()
            panel.append_assistant_message(error_msg)
            self.notify(error_msg, severity="error")

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

    def action_copy_selection(self) -> None:
        """Copy selected messages to clipboard."""
        try:
            panel = self.query_one(ConversationPanel)
            content = panel.get_selected_content()
            if content:
                self.copy_to_clipboard(content)
                self.notify("Copied to clipboard.", severity="information")
            else:
                self.notify("No messages selected.", severity="warning")
        except Exception:
            self.notify("Could not copy to clipboard.", severity="error")

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

    def action_show_llm_settings(self) -> None:
        """Show the LLM settings modal."""

        def handle_llm_settings(result: dict[str, Any] | None) -> None:
            """Handle the LLM settings from the modal."""
            if result is not None:
                # Persist settings to config
                try:
                    from chapgent.config.writer import save_config_value

                    # Save each setting
                    save_config_value("llm.provider", result["provider"])
                    save_config_value("llm.model", result["model"])
                    save_config_value("llm.max_output_tokens", str(result["max_output_tokens"]))

                    self.notify(
                        f"LLM settings updated: {result['provider']}/{result['model']}",
                        severity="information",
                    )

                    # Update settings if available
                    if self.settings:
                        self.settings.llm.provider = result["provider"]
                        self.settings.llm.model = result["model"]
                        self.settings.llm.max_output_tokens = result["max_output_tokens"]
                except Exception as e:
                    self.notify(f"Error saving LLM settings: {e}", severity="error")

        # Get current settings
        current_provider = self.settings.llm.provider if self.settings else None
        current_model = self.settings.llm.model if self.settings else None
        current_max_output_tokens = self.settings.llm.max_output_tokens if self.settings else None

        self.push_screen(
            LLMSettingsScreen(
                current_provider=current_provider,
                current_model=current_model,
                current_max_output_tokens=current_max_output_tokens,
            ),
            callback=handle_llm_settings,
        )

    def action_show_tui_settings(self) -> None:
        """Show the TUI settings modal."""

        def handle_tui_settings(result: dict[str, Any] | None) -> None:
            """Handle the TUI settings from the modal."""
            if result is not None:
                # Persist settings to config
                try:
                    from chapgent.config.writer import save_config_value

                    # Save each setting
                    save_config_value("tui.show_sidebar", str(result["show_sidebar"]).lower())
                    save_config_value("tui.show_tool_panel", str(result["show_tool_panel"]).lower())

                    self.notify(
                        "TUI settings updated. Restart to apply sidebar/panel changes.",
                        severity="information",
                    )

                    # Update settings if available
                    if self.settings:
                        self.settings.tui.show_sidebar = result["show_sidebar"]
                        self.settings.tui.show_tool_panel = result["show_tool_panel"]
                except Exception as e:
                    self.notify(f"Error saving TUI settings: {e}", severity="error")

        # Get current settings
        show_sidebar = self.settings.tui.show_sidebar if self.settings else True
        show_tool_panel = self.settings.tui.show_tool_panel if self.settings else True
        current_theme = self.theme if hasattr(self, "theme") else None

        self.push_screen(
            TUISettingsScreen(
                show_sidebar=show_sidebar,
                show_tool_panel=show_tool_panel,
                current_theme=current_theme,
            ),
            callback=handle_tui_settings,
        )

    def action_show_help(self, topic: str | None = None) -> None:
        """Show the help screen modal.

        Args:
            topic: Optional topic to display directly.
        """
        self.push_screen(HelpScreen(topic=topic))

    def action_show_tools(self, category: str | None = None) -> None:
        """Show the tools screen modal.

        Args:
            category: Optional category to filter by.
        """
        self.push_screen(ToolsScreen(category=category))

    def action_show_prompt_settings(self) -> None:
        """Show the system prompt settings modal."""

        def handle_prompt_settings(result: dict[str, Any] | None) -> None:
            """Handle the system prompt settings from the modal."""
            if result is not None:
                # Persist settings to config
                try:
                    from chapgent.config.writer import save_config_value

                    # Save each setting
                    if result.get("content"):
                        save_config_value("system_prompt.content", result["content"])
                    save_config_value("system_prompt.mode", result["mode"])
                    if result.get("file"):
                        save_config_value("system_prompt.file", result["file"])

                    self.notify("System prompt settings updated.", severity="information")

                    # Update settings if available
                    if self.settings:
                        self.settings.system_prompt.content = result.get("content")
                        self.settings.system_prompt.mode = result["mode"]
                        self.settings.system_prompt.file = result.get("file")
                except Exception as e:
                    self.notify(f"Error saving prompt settings: {e}", severity="error")

        # Get current settings
        current_content = self.settings.system_prompt.content if self.settings else None
        current_mode = self.settings.system_prompt.mode if self.settings else "append"
        current_file = self.settings.system_prompt.file if self.settings else None

        self.push_screen(
            SystemPromptScreen(
                current_content=current_content,
                current_mode=current_mode,
                current_file=current_file,
            ),
            callback=handle_prompt_settings,
        )

    def action_show_config(self) -> None:
        """Show the config display modal."""
        self.push_screen(ConfigShowScreen(settings=self.settings))

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

        if command.name == "tools":
            await self._handle_tools_command(args)
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
        topic = args[0] if args else None
        self.action_show_help(topic=topic)

    async def _handle_tools_command(self, args: list[str]) -> None:
        """Handle the /tools command.

        Args:
            args: Command arguments (optional category name).
        """
        category = args[0] if args else None
        self.action_show_tools(category=category)

    async def _handle_config_command(self, args: list[str]) -> None:
        """Handle the /config command.

        Args:
            args: Command arguments (e.g., ["show"] or ["set", "key", "value"]).
        """
        if not args or args[0] == "show":
            # Show current configuration using the modal screen
            self.action_show_config()
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
