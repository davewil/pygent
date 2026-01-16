from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Pretty, Static


class ConversationPanel(Static):
    """Display for the conversation history."""

    BORDER_TITLE = "💬 Conversation"

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="conversation-messages")

    def append_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        scroll.mount(Static(f"👤 You: {content}", classes="user-message"))
        scroll.scroll_end(animate=False)

    def append_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        scroll.mount(Static(f"🤖 Agent: {content}", classes="agent-message"))
        scroll.scroll_end(animate=False)


class ToolResultItem(Static):
    """Widget to display a tool result."""

    def __init__(self, content: str, tool_name: str, result: str, **kwargs):
        super().__init__(content, **kwargs)
        self.tool_name = tool_name
        self.result = result


class ToolPanel(Static):
    """Display for tool activity."""

    BORDER_TITLE = "🔧 Tools"

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="tool-output")

    def append_tool_call(self, tool_name: str, tool_id: str) -> None:
        """Append a tool call to the panel."""
        scroll = self.query_one("#tool-output", VerticalScroll)
        scroll.mount(Static(f"⏳ Running: {tool_name}", classes="tool-call"))
        scroll.scroll_end(animate=False)

    def append_tool_result(self, tool_name: str, result: str) -> None:
        """Append a tool result to the panel."""
        # Truncate long results for display
        display_result = result[:200] + "..." if len(result) > 200 else result
        item = ToolResultItem(f"✅ {tool_name}: {display_result}", tool_name, result, classes="tool-result")
        scroll = self.query_one("#tool-output", VerticalScroll)
        scroll.mount(item)
        scroll.scroll_end(animate=False)


class MessageInput(Input):
    """Input widget for user messages."""

    def on_mount(self) -> None:
        self.placeholder = "Type your message..."


class PermissionPrompt(ModalScreen[bool]):
    """Modal to ask for permission."""

    def __init__(self, tool_name: str, args: dict):
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        yield Static(f"Allow execution of tool '{self.tool_name}'?")
        yield Pretty(self.args)
        with Horizontal(classes="buttons"):
            yield Button("Yes", variant="success", id="btn-yes")
            yield Button("No", variant="error", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)
