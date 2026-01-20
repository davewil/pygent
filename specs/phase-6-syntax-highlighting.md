# Phase 6: Syntax Highlighting & Markdown Rendering

## Overview

Enhance the conversation window to render markdown content with full syntax highlighting for code blocks. This phase implements Rich/Pygments-based rendering with an architecture designed to support future migration to tree-sitter for streaming responses.

## Objectives

1. **Full Markdown Rendering** - Headers, lists, bold/italic, links, blockquotes, and code blocks
2. **Syntax Highlighting** - Language-aware code highlighting with theme support
3. **Extensible Architecture** - Abstract rendering interface to support future tree-sitter integration
4. **Theme Consistency** - Syntax colors that complement the existing TUI themes

---

## Architecture

### Design Principles

1. **Separation of Concerns** - Parsing (markdown → AST) is separate from rendering (AST → styled output)
2. **Pluggable Highlighters** - Abstract interface allows swapping Pygments for tree-sitter later
3. **Streaming-Ready** - Architecture supports incremental rendering for future streaming responses
4. **Theme Integration** - Syntax themes map to Textual's theme system

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ConversationPanel                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   MarkdownMessage                         │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │              MarkdownRenderer                       │  │  │
│  │  │  ┌─────────────┐    ┌─────────────────────────┐    │  │  │
│  │  │  │  Markdown   │───▶│   SyntaxHighlighter     │    │  │  │
│  │  │  │   Parser    │    │   (Pygments/TreeSitter) │    │  │  │
│  │  │  └─────────────┘    └─────────────────────────┘    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### New Files

| File | Purpose |
|------|---------|
| `src/chapgent/tui/markdown.py` | Markdown parsing and rendering |
| `src/chapgent/tui/highlighter.py` | Syntax highlighting abstraction |
| `src/chapgent/tui/themes/syntax.py` | Syntax color schemes |
| `tests/test_tui/test_markdown.py` | Markdown rendering tests |
| `tests/test_tui/test_highlighter.py` | Syntax highlighting tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/chapgent/tui/widgets.py` | Replace `Static` with `MarkdownMessage` widget |
| `src/chapgent/tui/styles.tcss` | Add markdown element styles |
| `src/chapgent/tui/__init__.py` | Export new components |

---

## Implementation Phases

### Phase 1: Syntax Highlighter Abstraction

Create an abstract interface for syntax highlighting that can be implemented by Pygments now and tree-sitter later.

**File:** `src/chapgent/tui/highlighter.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from rich.text import Text


@dataclass
class HighlightedCode:
    """Result of syntax highlighting."""
    text: Text  # Rich Text object with styling
    language: str
    line_count: int


class SyntaxHighlighter(ABC):
    """Abstract base for syntax highlighting implementations."""

    @abstractmethod
    def highlight(
        self,
        code: str,
        language: str,
        *,
        line_numbers: bool = False,
        theme: str = "monokai",
    ) -> HighlightedCode:
        """Highlight code and return styled Rich Text.

        Args:
            code: Source code to highlight.
            language: Language identifier (e.g., "python", "javascript").
            line_numbers: Whether to include line numbers.
            theme: Color theme name.

        Returns:
            HighlightedCode with styled Rich Text.
        """
        ...

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if the highlighter supports a language."""
        ...

    @abstractmethod
    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        """Attempt to detect language from code content or filename."""
        ...


class PygmentsHighlighter(SyntaxHighlighter):
    """Pygments-based syntax highlighting (default implementation)."""

    # Language alias mapping for common variations
    LANGUAGE_ALIASES: dict[str, str] = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "rb": "ruby",
        "rs": "rust",
        "yml": "yaml",
        "sh": "bash",
        "shell": "bash",
        "zsh": "bash",
        "dockerfile": "docker",
        "md": "markdown",
    }

    def highlight(
        self,
        code: str,
        language: str,
        *,
        line_numbers: bool = False,
        theme: str = "monokai",
    ) -> HighlightedCode:
        from rich.syntax import Syntax

        # Normalize language name
        lang = self.LANGUAGE_ALIASES.get(language.lower(), language.lower())

        syntax = Syntax(
            code,
            lang,
            theme=theme,
            line_numbers=line_numbers,
            word_wrap=True,
        )

        # Convert to Rich Text for embedding in other content
        text = Text()
        text.append_text(syntax.highlight(code))

        return HighlightedCode(
            text=text,
            language=lang,
            line_count=code.count("\n") + 1,
        )

    def supports_language(self, language: str) -> bool:
        from pygments.lexers import get_lexer_by_name, ClassNotFound

        lang = self.LANGUAGE_ALIASES.get(language.lower(), language.lower())
        try:
            get_lexer_by_name(lang)
            return True
        except ClassNotFound:
            return False

    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        from pygments.lexers import guess_lexer, guess_lexer_for_filename, ClassNotFound

        try:
            if filename:
                lexer = guess_lexer_for_filename(filename, code)
            else:
                lexer = guess_lexer(code)
            return lexer.aliases[0] if lexer.aliases else lexer.name.lower()
        except ClassNotFound:
            return None


# Future tree-sitter implementation stub
class TreeSitterHighlighter(SyntaxHighlighter):
    """Tree-sitter based syntax highlighting (for streaming support).

    This implementation will be completed in a future phase when
    streaming response support is added.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "TreeSitterHighlighter is planned for future implementation. "
            "Use PygmentsHighlighter for now."
        )

    def highlight(self, code: str, language: str, **kwargs) -> HighlightedCode:
        raise NotImplementedError

    def supports_language(self, language: str) -> bool:
        raise NotImplementedError

    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        raise NotImplementedError


# Default highlighter instance
def get_highlighter() -> SyntaxHighlighter:
    """Get the default syntax highlighter."""
    return PygmentsHighlighter()
```

---

### Phase 2: Markdown Renderer

Create a markdown renderer that produces Rich renderables with syntax-highlighted code blocks.

**File:** `src/chapgent/tui/markdown.py`

```python
from dataclasses import dataclass, field
from rich.console import Console, ConsoleOptions, RenderResult, Group
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import Static

from .highlighter import SyntaxHighlighter, get_highlighter


@dataclass
class MarkdownConfig:
    """Configuration for markdown rendering."""

    # Code block settings
    code_theme: str = "monokai"
    show_line_numbers: bool = False
    code_block_padding: tuple[int, int] = (1, 2)  # (vertical, horizontal)

    # Inline code settings
    inline_code_style: str = "bold cyan"

    # Header styles
    h1_style: str = "bold magenta"
    h2_style: str = "bold blue"
    h3_style: str = "bold cyan"

    # Other elements
    blockquote_style: str = "italic dim"
    link_style: str = "underline blue"


class MarkdownRenderer:
    """Renders markdown content with syntax-highlighted code blocks.

    This renderer parses markdown and produces Rich renderables suitable
    for display in Textual widgets. Code blocks are extracted and
    highlighted using the configured SyntaxHighlighter.
    """

    def __init__(
        self,
        highlighter: SyntaxHighlighter | None = None,
        config: MarkdownConfig | None = None,
    ) -> None:
        self.highlighter = highlighter or get_highlighter()
        self.config = config or MarkdownConfig()

    def render(self, content: str) -> RichMarkdown:
        """Render markdown content to Rich Markdown.

        Args:
            content: Raw markdown string.

        Returns:
            Rich Markdown object ready for display.
        """
        # Rich's Markdown class handles most rendering
        # We customize code block handling via a custom code_theme
        return RichMarkdown(
            content,
            code_theme=self.config.code_theme,
            inline_code_style=self.config.inline_code_style,
        )

    def render_code_block(
        self,
        code: str,
        language: str | None = None,
    ) -> Panel:
        """Render a standalone code block with syntax highlighting.

        Args:
            code: Source code to highlight.
            language: Language identifier (auto-detected if None).

        Returns:
            Rich Panel containing highlighted code.
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
    """A Textual widget that renders markdown content.

    Replaces plain Static widgets in ConversationPanel to provide
    rich markdown rendering with syntax highlighting.
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
        # Set CSS class based on role
        role_class = "user-message" if role == "user" else "agent-message"
        if classes:
            classes = f"{classes} {role_class}"
        else:
            classes = role_class

        super().__init__(name=name, id=id, classes=classes)

        self._content = content
        self._role = role
        self._renderer = renderer or MarkdownRenderer()

    def render(self) -> RichMarkdown:
        """Render the markdown content."""
        # Add role prefix
        prefix = "👤 You: " if self._role == "user" else "🤖 Agent: "
        full_content = f"{prefix}{self._content}"

        return self._renderer.render(full_content)

    def update_content(self, content: str) -> None:
        """Update the message content (for streaming support)."""
        self._content = content
        self.refresh()
```

---

### Phase 3: Syntax Theme Integration

Create syntax color schemes that complement the existing Textual themes.

**File:** `src/chapgent/tui/themes/syntax.py`

```python
"""Syntax highlighting themes mapped to Textual themes.

Each Textual theme maps to a Pygments theme that provides
complementary colors for code highlighting.
"""

# Mapping from Textual theme to Pygments theme
THEME_MAPPING: dict[str, str] = {
    # Dark themes
    "textual-dark": "monokai",
    "dracula": "dracula",
    "monokai": "monokai",
    "nord": "nord",
    "gruvbox": "gruvbox-dark",
    "tokyo-night": "github-dark",

    # Light themes
    "textual-light": "friendly",
    "solarized-light": "solarized-light",
    "github-light": "github-light",
}

# Default fallbacks
DEFAULT_DARK_THEME = "monokai"
DEFAULT_LIGHT_THEME = "friendly"


def get_syntax_theme(textual_theme: str) -> str:
    """Get the Pygments theme for a Textual theme.

    Args:
        textual_theme: Name of the Textual theme.

    Returns:
        Corresponding Pygments theme name.
    """
    if textual_theme in THEME_MAPPING:
        return THEME_MAPPING[textual_theme]

    # Guess based on theme name
    if "light" in textual_theme.lower():
        return DEFAULT_LIGHT_THEME
    return DEFAULT_DARK_THEME


def is_dark_theme(textual_theme: str) -> bool:
    """Check if a Textual theme is a dark theme."""
    light_indicators = ["light", "solarized-light"]
    return not any(ind in textual_theme.lower() for ind in light_indicators)
```

---

### Phase 4: Widget Integration

Update `ConversationPanel` to use `MarkdownMessage` widgets.

**File:** `src/chapgent/tui/widgets.py` (modifications)

```python
# Add import at top
from .markdown import MarkdownMessage, MarkdownRenderer, MarkdownConfig
from .themes.syntax import get_syntax_theme

# Modify ConversationPanel class

class ConversationPanel(Static):
    """Display for the conversation history with markdown rendering."""

    BORDER_TITLE = "💬 Conversation"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._renderer: MarkdownRenderer | None = None

    def _get_renderer(self) -> MarkdownRenderer:
        """Get or create the markdown renderer with current theme."""
        if self._renderer is None:
            # Get syntax theme based on current app theme
            syntax_theme = get_syntax_theme(self.app.theme)
            config = MarkdownConfig(code_theme=syntax_theme)
            self._renderer = MarkdownRenderer(config=config)
        return self._renderer

    def on_mount(self) -> None:
        """Reset renderer when mounted to pick up theme."""
        self._renderer = None

    def watch_theme(self) -> None:
        """Reset renderer when theme changes."""
        self._renderer = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="conversation-messages")

    def append_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            content,
            role="user",
            renderer=self._get_renderer(),
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)

    def append_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            content,
            role="agent",
            renderer=self._get_renderer(),
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)

    # New method for streaming support (future use)
    def append_streaming_message(self) -> MarkdownMessage:
        """Append an empty assistant message for streaming updates.

        Returns:
            The MarkdownMessage widget that can be updated incrementally.
        """
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            "",
            role="agent",
            renderer=self._get_renderer(),
            id="streaming-message",
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)
        return message

    def update_streaming_message(self, content: str) -> None:
        """Update the current streaming message content."""
        try:
            message = self.query_one("#streaming-message", MarkdownMessage)
            message.update_content(content)
        except Exception:
            pass  # No streaming message active

    def finalize_streaming_message(self) -> None:
        """Convert streaming message to regular message."""
        try:
            message = self.query_one("#streaming-message", MarkdownMessage)
            message.id = None  # Remove special ID
        except Exception:
            pass
```

---

### Phase 5: Style Updates

Add TCSS styles for markdown elements.

**File:** `src/chapgent/tui/styles.tcss` (additions)

```css
/* Markdown Message Styles */

MarkdownMessage {
    padding: 1 2;
    margin: 1 0;
}

MarkdownMessage.user-message {
    background: $primary-darken-2;
    color: $text;
    border: round $primary;
}

MarkdownMessage.agent-message {
    background: $secondary-darken-2;
    color: $text;
    border: round $secondary;
}

/* Code block container */
MarkdownMessage .code-block {
    background: $surface;
    margin: 1 0;
    padding: 1 2;
    border: solid $primary-darken-3;
}

/* Inline code */
MarkdownMessage .inline-code {
    background: $surface-darken-1;
    color: $text;
}

/* Blockquotes */
MarkdownMessage .blockquote {
    border-left: thick $primary;
    padding-left: 2;
    color: $text-muted;
}

/* Headers */
MarkdownMessage .h1 {
    text-style: bold;
    color: $primary;
    margin: 1 0;
}

MarkdownMessage .h2 {
    text-style: bold;
    color: $secondary;
    margin: 1 0;
}

MarkdownMessage .h3 {
    text-style: bold;
    color: $accent;
}

/* Lists */
MarkdownMessage .list-item {
    margin-left: 2;
}

/* Links */
MarkdownMessage .link {
    color: $primary;
    text-style: underline;
}
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_tui/test_highlighter.py`

```python
import pytest
from chapgent.tui.highlighter import (
    PygmentsHighlighter,
    HighlightedCode,
    get_highlighter,
)


class TestPygmentsHighlighter:
    def test_highlight_python(self):
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("print('hello')", "python")

        assert isinstance(result, HighlightedCode)
        assert result.language == "python"
        assert result.line_count == 1

    def test_highlight_with_alias(self):
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("console.log('hi')", "js")

        assert result.language == "javascript"

    def test_supports_language(self):
        highlighter = PygmentsHighlighter()

        assert highlighter.supports_language("python")
        assert highlighter.supports_language("javascript")
        assert highlighter.supports_language("rust")
        assert not highlighter.supports_language("not-a-language")

    def test_detect_language_from_code(self):
        highlighter = PygmentsHighlighter()

        # Python shebang
        lang = highlighter.detect_language("#!/usr/bin/env python\nprint('hi')")
        assert lang == "python"

    def test_detect_language_from_filename(self):
        highlighter = PygmentsHighlighter()

        assert highlighter.detect_language("", "test.py") == "python"
        assert highlighter.detect_language("", "test.js") == "javascript"
        assert highlighter.detect_language("", "test.rs") == "rust"


class TestGetHighlighter:
    def test_returns_pygments_by_default(self):
        highlighter = get_highlighter()
        assert isinstance(highlighter, PygmentsHighlighter)
```

**File:** `tests/test_tui/test_markdown.py`

```python
import pytest
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel

from chapgent.tui.markdown import (
    MarkdownRenderer,
    MarkdownConfig,
    MarkdownMessage,
)


class TestMarkdownRenderer:
    def test_render_simple_text(self):
        renderer = MarkdownRenderer()
        result = renderer.render("Hello world")

        assert isinstance(result, RichMarkdown)

    def test_render_with_code_block(self):
        renderer = MarkdownRenderer()
        content = """Here is some code:

```python
def hello():
    print("Hello")
```
"""
        result = renderer.render(content)
        assert isinstance(result, RichMarkdown)

    def test_render_code_block_standalone(self):
        renderer = MarkdownRenderer()
        result = renderer.render_code_block("print('hello')", "python")

        assert isinstance(result, Panel)
        assert result.title == "python"

    def test_render_code_block_auto_detect(self):
        renderer = MarkdownRenderer()
        code = "#!/usr/bin/env python\nprint('hello')"
        result = renderer.render_code_block(code)

        assert isinstance(result, Panel)

    def test_custom_config(self):
        config = MarkdownConfig(
            code_theme="dracula",
            show_line_numbers=True,
        )
        renderer = MarkdownRenderer(config=config)

        assert renderer.config.code_theme == "dracula"
        assert renderer.config.show_line_numbers is True


class TestMarkdownMessage:
    @pytest.fixture
    def app(self):
        """Mock Textual app for testing."""
        from unittest.mock import MagicMock
        app = MagicMock()
        app.theme = "textual-dark"
        return app

    def test_user_message_class(self):
        msg = MarkdownMessage("Hello", role="user")
        assert "user-message" in msg.classes

    def test_agent_message_class(self):
        msg = MarkdownMessage("Hello", role="agent")
        assert "agent-message" in msg.classes

    def test_update_content(self):
        msg = MarkdownMessage("Initial")
        msg.update_content("Updated")

        assert msg._content == "Updated"
```

### Integration Tests

```python
# tests/test_tui/test_markdown_integration.py

import pytest
from textual.pilot import Pilot

from chapgent.tui.app import ChapgentApp


class TestMarkdownIntegration:
    @pytest.mark.asyncio
    async def test_code_block_rendering(self):
        """Test that code blocks render with highlighting."""
        app = ChapgentApp()

        async with app.run_test() as pilot:
            # Simulate agent response with code
            panel = app.query_one("#conversation", ConversationPanel)
            panel.append_assistant_message("""
Here's a Python example:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```
""")

            # Verify MarkdownMessage was created
            messages = panel.query(MarkdownMessage)
            assert len(messages) == 1
            assert "agent-message" in messages[0].classes
```

---

## Future Enhancements (Tree-sitter Migration Path)

When implementing streaming response support, the tree-sitter migration would involve:

### 1. Install tree-sitter dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing deps
    "tree-sitter>=0.21.0",
]

[project.optional-dependencies]
languages = [
    "tree-sitter-python>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
    "tree-sitter-rust>=0.21.0",
    "tree-sitter-go>=0.21.0",
    # Add more as needed
]
```

### 2. Implement TreeSitterHighlighter

```python
class TreeSitterHighlighter(SyntaxHighlighter):
    """Tree-sitter based highlighting with incremental parsing."""

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}
        self._languages = self._load_languages()

    def highlight_incremental(
        self,
        code: str,
        language: str,
        old_tree: Tree | None = None,
    ) -> tuple[HighlightedCode, Tree]:
        """Incrementally highlight code, reusing previous parse tree.

        This is the key advantage for streaming: only re-parse changed portions.
        """
        parser = self._get_parser(language)
        tree = parser.parse(code.encode(), old_tree)

        # Walk tree and apply highlighting
        styled = self._apply_highlighting(code, tree, language)

        return HighlightedCode(text=styled, language=language), tree
```

### 3. Update MarkdownMessage for streaming

```python
class StreamingMarkdownMessage(MarkdownMessage):
    """Extended message widget with incremental tree-sitter support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parse_trees: dict[int, Tree] = {}  # Cache trees by code block index

    def update_content_streaming(self, content: str) -> None:
        """Update with incremental re-highlighting."""
        # Detect which code blocks changed
        # Re-parse only changed blocks using cached trees
        # Update display incrementally
```

---

## Dependencies

### Required (already in project)

- `rich>=13.0.0` - Already installed, provides `Syntax` and `Markdown`
- `textual>=0.50.0` - Already installed, TUI framework

### No new dependencies needed for Phase 1

Pygments is included with Rich, so no additional packages are required.

---

## Verification

### Manual Testing

1. Start the TUI: `chapgent chat`
2. Ask the agent to write code in various languages
3. Verify:
   - Code blocks have syntax highlighting
   - Colors match the current theme
   - Headers, lists, and other markdown elements render correctly
   - Switching themes updates syntax colors

### Automated Testing

```bash
# Run all markdown/highlighting tests
uv run pytest tests/test_tui/test_markdown.py tests/test_tui/test_highlighter.py -v

# Run with coverage
uv run pytest tests/test_tui/test_markdown.py tests/test_tui/test_highlighter.py --cov=chapgent.tui.markdown --cov=chapgent.tui.highlighter
```

---

## Implementation Order

1. **Phase 1: Highlighter Abstraction** ✓ COMPLETE
   - Created `highlighter.py` with `SyntaxHighlighter` ABC
   - Implemented `PygmentsHighlighter` with language alias normalization
   - Added 89 behavioral tests (unit + property-based with Hypothesis)

2. **Phase 2: Markdown Renderer** ✓ COMPLETE
   - Created `markdown.py` with `MarkdownRenderer` and `MarkdownConfig`
   - Created `MarkdownMessage` widget with role-based styling
   - Added 35 behavioral tests (unit + property-based with Hypothesis)
   - Exports added to `tui/__init__.py`

3. **Phase 3: Theme Integration**
   - Create `themes/syntax.py`
   - Map Textual themes to Pygments themes
   - Add tests

4. **Phase 4: Widget Integration**
   - Update `ConversationPanel` to use `MarkdownMessage`
   - Add streaming support methods (for future use)
   - Integration tests

5. **Phase 5: Styles & Polish**
   - Add TCSS styles for markdown elements
   - Manual testing across themes
   - Documentation updates

---

## Acceptance Criteria

### Functional

- [ ] Code blocks display with syntax highlighting
- [x] Language detection works for unlabeled code blocks (PygmentsHighlighter.detect_language)
- [x] 50+ languages supported (via Pygments) - tested 22 common languages
- [ ] Headers render with distinct styles (h1, h2, h3)
- [ ] Lists render with proper indentation
- [ ] Inline code renders with distinct background
- [ ] Blockquotes render with left border
- [ ] Links render with underline style
- [ ] Theme changes update syntax colors

### Non-Functional

- [x] No new dependencies required
- [ ] Rendering adds <50ms latency for typical messages
- [x] All tests pass (89 highlighter tests)
- [x] Architecture supports future tree-sitter migration (TreeSitterHighlighter stub)

---

*Document Version: 1.2*
*Created: 2026-01-20*
*Updated: 2026-01-20* - Phase 2 complete
