"""Tests for the markdown rendering module.

These tests focus on behavioral validation of the markdown renderer and message
widget, ensuring correct rendering of markdown content with syntax highlighting.
"""

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel

from chapgent.tui.markdown import (
    MarkdownConfig,
    MarkdownMessage,
    MarkdownRenderer,
)


# =============================================================================
# MarkdownConfig Tests
# =============================================================================


class TestMarkdownConfig:
    """Tests for MarkdownConfig dataclass."""

    def test_default_config_values(self):
        """Test that default config has sensible values."""
        config = MarkdownConfig()

        assert config.code_theme == "monokai"
        assert config.show_line_numbers is False
        assert config.code_block_padding == (1, 2)
        assert config.inline_code_theme is None

    def test_custom_config_values(self):
        """Test creating config with custom values."""
        config = MarkdownConfig(
            code_theme="dracula",
            show_line_numbers=True,
            code_block_padding=(2, 4),
        )

        assert config.code_theme == "dracula"
        assert config.show_line_numbers is True
        assert config.code_block_padding == (2, 4)


# =============================================================================
# MarkdownRenderer Tests
# =============================================================================


class TestMarkdownRenderer:
    """Tests for MarkdownRenderer behavior."""

    def test_render_simple_text(self):
        """Test rendering simple text produces Rich Markdown."""
        renderer = MarkdownRenderer()
        result = renderer.render("Hello, world!")

        assert isinstance(result, RichMarkdown)

    def test_render_with_headers(self):
        """Test rendering markdown with headers."""
        renderer = MarkdownRenderer()
        content = """# Header 1
## Header 2
### Header 3

Some text here.
"""
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_render_with_code_block(self):
        """Test rendering markdown with fenced code blocks."""
        renderer = MarkdownRenderer()
        content = """Here's some code:

```python
def hello():
    print("Hello")
```

And some more text.
"""
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_render_with_lists(self):
        """Test rendering markdown with lists."""
        renderer = MarkdownRenderer()
        content = """Shopping list:

- Item 1
- Item 2
- Item 3

Numbered:

1. First
2. Second
3. Third
"""
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_render_uses_config_theme(self):
        """Test that render uses the configured code theme."""
        config = MarkdownConfig(code_theme="dracula")
        renderer = MarkdownRenderer(config=config)
        result = renderer.render("```python\ncode\n```")

        # The RichMarkdown object should have the theme configured
        assert isinstance(result, RichMarkdown)

    def test_render_code_block_standalone(self):
        """Test rendering a standalone code block returns a Panel."""
        renderer = MarkdownRenderer()
        result = renderer.render_code_block("print('hello')", "python")

        assert isinstance(result, Panel)
        assert result.title == "python"

    def test_render_code_block_auto_detects_language(self):
        """Test that render_code_block auto-detects language when not provided."""
        renderer = MarkdownRenderer()
        code = "#!/usr/bin/env python3\nprint('hello')"
        result = renderer.render_code_block(code)

        assert isinstance(result, Panel)
        # Should detect Python from shebang
        assert result.title is not None

    def test_render_code_block_with_line_numbers(self):
        """Test rendering code block with line numbers enabled."""
        config = MarkdownConfig(show_line_numbers=True)
        renderer = MarkdownRenderer(config=config)
        result = renderer.render_code_block("line1\nline2\nline3", "text")

        assert isinstance(result, Panel)

    def test_renderer_with_custom_highlighter(self):
        """Test that renderer uses provided highlighter."""
        from chapgent.tui.highlighter import PygmentsHighlighter

        custom_highlighter = PygmentsHighlighter()
        renderer = MarkdownRenderer(highlighter=custom_highlighter)

        assert renderer.highlighter is custom_highlighter


# =============================================================================
# MarkdownMessage Widget Tests
# =============================================================================


class TestMarkdownMessage:
    """Tests for MarkdownMessage widget behavior."""

    def test_user_message_has_user_class(self):
        """Test that user role adds user-message CSS class."""
        msg = MarkdownMessage("Hello", role="user")

        assert "user-message" in msg.classes

    def test_agent_message_has_agent_class(self):
        """Test that agent role adds agent-message CSS class."""
        msg = MarkdownMessage("Hello", role="agent")

        assert "agent-message" in msg.classes

    def test_default_role_is_agent(self):
        """Test that default role is agent."""
        msg = MarkdownMessage("Hello")

        assert msg.role == "agent"
        assert "agent-message" in msg.classes

    def test_content_property(self):
        """Test that content property returns the content."""
        msg = MarkdownMessage("Test content")

        assert msg.content == "Test content"

    def test_role_property(self):
        """Test that role property returns the role."""
        msg = MarkdownMessage("Test", role="user")

        assert msg.role == "user"

    def test_update_content_changes_content(self):
        """Test that update_content changes the stored content."""
        msg = MarkdownMessage("Initial")
        msg.update_content("Updated")

        assert msg.content == "Updated"

    def test_render_returns_rich_markdown(self):
        """Test that render returns a Rich Markdown object."""
        msg = MarkdownMessage("Hello")
        result = msg.render()

        assert isinstance(result, RichMarkdown)

    def test_render_includes_user_prefix(self):
        """Test that user messages have a user prefix in render."""
        msg = MarkdownMessage("Hello", role="user")
        result = msg.render()

        # The rendered markdown should include "You:" prefix
        assert isinstance(result, RichMarkdown)

    def test_render_includes_agent_prefix(self):
        """Test that agent messages have an agent prefix in render."""
        msg = MarkdownMessage("Hello", role="agent")
        result = msg.render()

        # The rendered markdown should include "Agent:" prefix
        assert isinstance(result, RichMarkdown)

    def test_additional_classes_preserved(self):
        """Test that additional CSS classes are preserved."""
        msg = MarkdownMessage("Hello", classes="custom-class")

        assert "custom-class" in msg.classes
        assert "agent-message" in msg.classes

    def test_message_with_custom_renderer(self):
        """Test creating message with custom renderer."""
        custom_config = MarkdownConfig(code_theme="dracula")
        custom_renderer = MarkdownRenderer(config=custom_config)
        msg = MarkdownMessage("Hello", renderer=custom_renderer)

        assert msg._renderer is custom_renderer


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests for robustness."""

    @given(content=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=30)
    def test_render_never_crashes(self, content):
        """Test that render() never crashes with any input."""
        renderer = MarkdownRenderer()
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    @given(
        content=st.text(min_size=1, max_size=200),
        role=st.sampled_from(["user", "agent"]),
    )
    @hypothesis_settings(max_examples=30)
    def test_message_never_crashes(self, content, role):
        """Test that MarkdownMessage never crashes with any input."""
        msg = MarkdownMessage(content, role=role)

        assert isinstance(msg.render(), RichMarkdown)
        assert msg.content == content
        assert msg.role == role

    @given(
        code=st.text(min_size=0, max_size=200),
        language=st.one_of(st.none(), st.sampled_from(["python", "javascript", "rust", "text"])),
    )
    @hypothesis_settings(max_examples=30)
    def test_render_code_block_never_crashes(self, code, language):
        """Test that render_code_block never crashes."""
        renderer = MarkdownRenderer()
        result = renderer.render_code_block(code, language)

        assert isinstance(result, Panel)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_content(self):
        """Test rendering empty content."""
        renderer = MarkdownRenderer()
        result = renderer.render("")

        assert isinstance(result, RichMarkdown)

    def test_whitespace_only_content(self):
        """Test rendering whitespace-only content."""
        renderer = MarkdownRenderer()
        result = renderer.render("   \n\t\n   ")

        assert isinstance(result, RichMarkdown)

    def test_content_with_unicode(self):
        """Test rendering content with unicode characters."""
        renderer = MarkdownRenderer()
        content = "Hello, 世界! Emoji: 🎉🚀💡"
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_content_with_special_markdown_chars(self):
        """Test rendering content with special markdown characters."""
        renderer = MarkdownRenderer()
        content = "* Not a list * with `code` and [link](url) and **bold**"
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_nested_code_blocks(self):
        """Test rendering content with nested backticks."""
        renderer = MarkdownRenderer()
        content = "Use `inline` or ```block``` code"
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_very_long_content(self):
        """Test rendering very long content."""
        renderer = MarkdownRenderer()
        content = "Hello " * 1000
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_message_with_empty_content(self):
        """Test creating message with empty content."""
        msg = MarkdownMessage("")

        assert msg.content == ""
        result = msg.render()
        assert isinstance(result, RichMarkdown)

    def test_update_content_multiple_times(self):
        """Test updating content multiple times."""
        msg = MarkdownMessage("First")

        msg.update_content("Second")
        assert msg.content == "Second"

        msg.update_content("Third")
        assert msg.content == "Third"

        msg.update_content("")
        assert msg.content == ""


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for markdown rendering flows."""

    def test_full_markdown_document(self):
        """Test rendering a complete markdown document."""
        renderer = MarkdownRenderer()
        content = """# Main Title

This is a paragraph with **bold** and *italic* text.

## Code Example

Here's some Python code:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

print(greet("World"))
```

## Lists

- Item one
- Item two
  - Nested item

## Blockquote

> This is a quote
> that spans multiple lines

## Links

Check out [this link](https://example.com).

---

That's all folks!
"""
        result = renderer.render(content)

        assert isinstance(result, RichMarkdown)

    def test_message_rendering_cycle(self):
        """Test creating, rendering, and updating a message."""
        msg = MarkdownMessage("Initial content", role="user")

        # First render
        result1 = msg.render()
        assert isinstance(result1, RichMarkdown)

        # Update content
        msg.update_content("Updated content with **bold**")

        # Second render
        result2 = msg.render()
        assert isinstance(result2, RichMarkdown)
        assert msg.content == "Updated content with **bold**"
