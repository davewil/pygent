"""Markdown rendering with syntax highlighting for conversation messages.

This module provides markdown rendering capabilities for the TUI, including
syntax-highlighted code blocks. It uses Rich's Markdown class for rendering
with custom code block handling via the SyntaxHighlighter abstraction.

Features:
- Full markdown rendering (headers, lists, code blocks, etc.)
- Syntax highlighting for code blocks
- Configurable themes and styles
- Role-based message styling (user vs agent)
"""

from dataclasses import dataclass, field

from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from textual.events import Click
from textual.widgets import Static

from .highlighter import SyntaxHighlighter, get_highlighter


@dataclass
class MarkdownConfig:
    """Configuration for markdown rendering.

    Attributes:
        code_theme: Pygments theme for code blocks (default: monokai).
        show_line_numbers: Whether to show line numbers in code blocks.
        code_block_padding: Padding for code block panels (vertical, horizontal).
        inline_code_theme: Theme for inline code (None uses code_theme).
        h1_style: Rich style for h1 headers.
        h2_style: Rich style for h2 headers.
        h3_style: Rich style for h3 headers.
        blockquote_style: Rich style for blockquotes.
        link_style: Rich style for links.
    """

    code_theme: str = "monokai"
    show_line_numbers: bool = False
    code_block_padding: tuple[int, int] = field(default_factory=lambda: (1, 2))
    inline_code_theme: str | None = None
    h1_style: str = "bold magenta"
    h2_style: str = "bold blue"
    h3_style: str = "bold cyan"
    blockquote_style: str = "italic dim"
    link_style: str = "underline blue"


class MarkdownRenderer:
    """Renders markdown content with syntax-highlighted code blocks.

    This renderer uses Rich's Markdown class for most rendering, with custom
    handling for code blocks via the SyntaxHighlighter. The result is suitable
    for display in Textual widgets.

    Attributes:
        highlighter: The syntax highlighter for code blocks.
        config: Markdown rendering configuration.
    """

    def __init__(
        self,
        highlighter: SyntaxHighlighter | None = None,
        config: MarkdownConfig | None = None,
    ) -> None:
        """Initialize the markdown renderer.

        Args:
            highlighter: Syntax highlighter for code blocks. Uses default if None.
            config: Markdown rendering configuration. Uses defaults if None.
        """
        self.highlighter = highlighter or get_highlighter()
        self.config = config or MarkdownConfig()

    def render(self, content: str) -> RichMarkdown:
        """Render markdown content to a Rich Markdown renderable.

        Args:
            content: Raw markdown string.

        Returns:
            Rich Markdown object ready for display.
        """
        return RichMarkdown(
            content,
            code_theme=self.config.code_theme,
            inline_code_theme=self.config.inline_code_theme,
        )

    def render_code_block(
        self,
        code: str,
        language: str | None = None,
    ) -> Panel:
        """Render a standalone code block with syntax highlighting.

        This method is useful for rendering code blocks outside of a full
        markdown document, such as when extracting code from tool outputs.

        Args:
            code: Source code to highlight.
            language: Language identifier. Auto-detected if None.

        Returns:
            Rich Panel containing highlighted code with language label.
        """
        # Detect language if not provided
        if not language:
            language = self.highlighter.detect_language(code) or "text"

        # Get highlighted code
        highlighted = self.highlighter.highlight(
            code,
            language,
            line_numbers=self.config.show_line_numbers,
            theme=self.config.code_theme,
        )

        # Wrap in panel with language label
        return Panel(
            highlighted.text,
            title=language,
            title_align="left",
            border_style="dim",
            padding=self.config.code_block_padding,
        )


class MarkdownMessage(Static):
    """A Textual widget that renders markdown content with syntax highlighting.

    This widget is designed to replace plain Static widgets in the conversation
    panel, providing rich markdown rendering with role-based styling.

    Features:
    - Full markdown rendering via Rich
    - Syntax-highlighted code blocks
    - Role-based CSS classes (user-message, agent-message)
    - Content updates for streaming support
    - Selection support for clipboard copy

    Attributes:
        DEFAULT_CSS: Embedded CSS styles for the widget.
    """

    DEFAULT_CSS = """
    MarkdownMessage {
        padding: 1 2;
        margin: 1 0;
    }

    MarkdownMessage.user-message {
        background: $primary-darken-2;
        border: round $primary;
    }

    MarkdownMessage.agent-message {
        background: $secondary-darken-2;
        border: round $secondary;
    }

    MarkdownMessage.selected {
        border: double $warning;
    }
    """

    def __init__(
        self,
        content: str,
        *,
        role: str = "agent",
        renderer: MarkdownRenderer | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize a markdown message widget.

        Args:
            content: The markdown content to render.
            role: Message role ("user" or "agent"). Affects styling.
            renderer: Markdown renderer to use. Uses default if None.
            name: Widget name.
            id: Widget ID.
            classes: Additional CSS classes.
        """
        # Set CSS class based on role
        role_class = "user-message" if role == "user" else "agent-message"
        if classes:
            classes = f"{classes} {role_class}"
        else:
            classes = role_class

        self._content = content
        self._role = role
        self._renderer = renderer or MarkdownRenderer()
        self._selected = False

        # Initialize Static with rendered content
        super().__init__(self._render_markdown(), name=name, id=id, classes=classes)

    def _render_markdown(self) -> RichMarkdown:
        """Render the current content to a Rich Markdown object."""
        prefix = "**You:** " if self._role == "user" else "**Agent:** "
        full_content = f"{prefix}{self._content}"
        return self._renderer.render(full_content)

    def render(self) -> RichMarkdown:
        """Render the markdown content.

        Returns:
            Rich Markdown renderable with role prefix.
        """
        return self._render_markdown()

    @property
    def content(self) -> str:
        """Get the current content."""
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        """Set the content."""
        self._content = value
        self.update(self._render_markdown())

    @property
    def role(self) -> str:
        """Get the message role."""
        return self._role

    def update_content(self, content: str) -> None:
        """Update the message content.

        This method is useful for streaming responses where content
        is received incrementally.

        Args:
            content: New markdown content.
        """
        self._content = content
        # Use Static.update() which properly refreshes the display
        self.update(self._render_markdown())

    @property
    def selected(self) -> bool:
        """Get the selection state."""
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        """Set the selection state.

        Args:
            value: True to select, False to deselect.
        """
        self._selected = value
        if value:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def on_click(self, event: Click) -> None:
        """Handle click events to toggle selection.

        Args:
            event: The click event.
        """
        self.selected = not self.selected
        event.stop()
