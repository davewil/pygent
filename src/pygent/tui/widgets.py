from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Pretty, Static


class ConversationPanel(Static):
    """Display for the conversation history."""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="conversation-messages")

    def append_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self.query_one("#conversation-messages").mount(Static(f"User: {content}", classes="user-message"))

    def append_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        self.query_one("#conversation-messages").mount(Static(f"Agent: {content}", classes="agent-message"))


class ToolResultItem(Static):
    """Widget to display a tool result."""

    def __init__(self, content: str, tool_name: str, result: str, **kwargs):
        super().__init__(content, **kwargs)
        self.tool_name = tool_name
        self.result = result


class ToolPanel(Static):
    """Display for tool activity."""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="tool-output")

    def append_tool_call(self, tool_name: str, tool_id: str) -> None:
        """Append a tool call to the panel."""
        self.query_one("#tool-output").mount(Static(f"Running: {tool_name} ({tool_id})", classes="tool-call"))

    def append_tool_result(self, tool_name: str, result: str) -> None:
        """Append a tool result to the panel."""
        item = ToolResultItem(f"Result ({tool_name}): {result}", tool_name, result, classes="tool-result")
        self.query_one("#tool-output").mount(item)


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
