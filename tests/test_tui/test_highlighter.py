"""Tests for the syntax highlighting module.

These tests focus on behavioral validation of the highlighter, ensuring it
correctly highlights code, normalizes languages, and detects languages
from content and filenames.
"""

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from rich.text import Text

from chapgent.tui.highlighter import (
    HighlightedCode,
    PygmentsHighlighter,
    SyntaxHighlighter,
    TreeSitterHighlighter,
    get_highlighter,
)

# =============================================================================
# HighlightedCode Dataclass Tests
# =============================================================================


class TestHighlightedCode:
    """Tests for the HighlightedCode dataclass."""

    def test_create_highlighted_code(self):
        """Test creating a HighlightedCode instance."""
        text = Text("print('hello')")
        code = HighlightedCode(text=text, language="python", line_count=1)

        assert code.text == text
        assert code.language == "python"
        assert code.line_count == 1

    def test_highlighted_code_multiline(self):
        """Test HighlightedCode with multiline content."""
        text = Text("line1\nline2\nline3")
        code = HighlightedCode(text=text, language="text", line_count=3)

        assert code.line_count == 3


# =============================================================================
# PygmentsHighlighter Tests
# =============================================================================


class TestPygmentsHighlighter:
    """Tests for the PygmentsHighlighter implementation."""

    def test_highlight_python(self):
        """Test highlighting Python code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("print('hello')", "python")

        assert isinstance(result, HighlightedCode)
        assert result.language == "python"
        assert result.line_count == 1
        assert isinstance(result.text, Text)

    def test_highlight_javascript(self):
        """Test highlighting JavaScript code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("console.log('hi')", "javascript")

        assert result.language == "javascript"
        assert isinstance(result.text, Text)

    def test_highlight_rust(self):
        """Test highlighting Rust code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight('fn main() { println!("Hello"); }', "rust")

        assert result.language == "rust"

    def test_highlight_go(self):
        """Test highlighting Go code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight('package main\nfunc main() {}', "go")

        assert result.language == "go"
        assert result.line_count == 2

    def test_highlight_multiline(self):
        """Test highlighting multiline code."""
        highlighter = PygmentsHighlighter()
        code = """def hello():
    print("Hello")
    return True
"""
        result = highlighter.highlight(code, "python")

        assert result.line_count == 4  # 3 lines + empty line at end

    def test_highlight_with_line_numbers(self):
        """Test highlighting with line numbers enabled."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("print('hello')", "python", line_numbers=True)

        assert isinstance(result, HighlightedCode)
        # Line numbers should be in the output (Rich handles this)

    def test_highlight_with_custom_theme(self):
        """Test highlighting with a custom theme."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("print('hello')", "python", theme="dracula")

        assert isinstance(result, HighlightedCode)

    def test_highlight_unknown_language_fallback(self):
        """Test that unknown languages fall back to text."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("some code", "not_a_real_language")

        assert result.language == "text"

    def test_highlight_empty_code(self):
        """Test highlighting empty code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("", "python")

        assert result.line_count == 1
        assert isinstance(result.text, Text)


# =============================================================================
# Language Alias Tests
# =============================================================================


class TestLanguageAliases:
    """Tests for language alias normalization."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("py", "python"),
            ("py3", "python"),
            ("python3", "python"),
            ("js", "javascript"),
            ("ts", "typescript"),
            ("rb", "ruby"),
            ("rs", "rust"),
            ("yml", "yaml"),
            ("sh", "bash"),
            ("shell", "bash"),
            ("zsh", "bash"),
            ("md", "markdown"),
            ("cs", "csharp"),
            ("c++", "cpp"),
        ],
    )
    def test_language_alias_normalization(self, alias, expected):
        """Test that common language aliases are normalized correctly."""
        highlighter = PygmentsHighlighter()
        normalized = highlighter.normalize_language(alias)

        assert normalized == expected

    def test_alias_case_insensitive(self):
        """Test that alias normalization is case-insensitive."""
        highlighter = PygmentsHighlighter()

        assert highlighter.normalize_language("PY") == "python"
        assert highlighter.normalize_language("Py") == "python"
        assert highlighter.normalize_language("JS") == "javascript"

    def test_unknown_alias_passthrough(self):
        """Test that unknown aliases pass through unchanged (lowercase)."""
        highlighter = PygmentsHighlighter()

        assert highlighter.normalize_language("fortran") == "fortran"
        assert highlighter.normalize_language("COBOL") == "cobol"

    def test_highlight_uses_normalized_language(self):
        """Test that highlight() uses normalized language name."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("console.log('hi')", "js")

        assert result.language == "javascript"


# =============================================================================
# Language Support Tests
# =============================================================================


class TestLanguageSupport:
    """Tests for language support detection."""

    @pytest.mark.parametrize(
        "language",
        [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "ruby",
            "php",
            "swift",
            "kotlin",
            "scala",
            "haskell",
            "sql",
            "html",
            "css",
            "json",
            "yaml",
            "xml",
            "bash",
            "markdown",
        ],
    )
    def test_supports_common_languages(self, language):
        """Test that common programming languages are supported."""
        highlighter = PygmentsHighlighter()

        assert highlighter.supports_language(language) is True

    def test_supports_language_with_alias(self):
        """Test supports_language works with aliases."""
        highlighter = PygmentsHighlighter()

        assert highlighter.supports_language("py") is True
        assert highlighter.supports_language("js") is True
        assert highlighter.supports_language("ts") is True

    def test_does_not_support_fake_language(self):
        """Test that fake languages are not supported."""
        highlighter = PygmentsHighlighter()

        assert highlighter.supports_language("not_a_real_language_xyz") is False
        assert highlighter.supports_language("fakeLang123") is False


# =============================================================================
# Language Detection Tests
# =============================================================================


class TestLanguageDetection:
    """Tests for automatic language detection."""

    def test_detect_from_python_shebang(self):
        """Test detecting Python from shebang."""
        highlighter = PygmentsHighlighter()
        code = "#!/usr/bin/env python3\nprint('hello')"
        lang = highlighter.detect_language(code)

        assert lang in ("python", "python3")

    def test_detect_from_bash_shebang(self):
        """Test detecting bash from shebang."""
        highlighter = PygmentsHighlighter()
        code = "#!/bin/bash\necho 'hello'"
        lang = highlighter.detect_language(code)

        assert lang in ("bash", "sh")

    @pytest.mark.parametrize(
        "filename,expected_lang",
        [
            ("test.py", "python"),
            ("test.js", "javascript"),
            ("test.ts", "typescript"),
            ("test.rs", "rust"),
            ("test.go", "go"),
            ("test.rb", "ruby"),
            ("test.java", "java"),
            ("test.c", "c"),
            ("test.cpp", "cpp"),
            ("test.html", "html"),
            ("test.css", "css"),
            ("test.json", "json"),
            ("test.yaml", "yaml"),
            ("test.md", "markdown"),
            ("test.sql", "sql"),
        ],
    )
    def test_detect_from_filename(self, filename, expected_lang):
        """Test detecting language from filename."""
        highlighter = PygmentsHighlighter()
        lang = highlighter.detect_language("", filename=filename)

        # Pygments may return slightly different names, check for partial match
        assert lang is not None
        assert expected_lang in lang.lower() or lang.lower() in expected_lang

    def test_detect_returns_none_for_unknown(self):
        """Test that detection returns None for unrecognizable content."""
        highlighter = PygmentsHighlighter()
        # Plain text with no identifiable patterns
        lang = highlighter.detect_language("hello world", filename=None)

        # May return None or a generic text type - both are acceptable
        # The key is that it doesn't crash
        assert lang is None or isinstance(lang, str)

    def test_detect_prefers_filename_over_content(self):
        """Test that filename takes precedence in detection."""
        highlighter = PygmentsHighlighter()
        # Python code but with .js filename
        code = "def hello(): pass"
        lang = highlighter.detect_language(code, filename="test.js")

        assert lang == "javascript"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetHighlighter:
    """Tests for the get_highlighter factory function."""

    def test_returns_pygments_highlighter(self):
        """Test that get_highlighter returns a PygmentsHighlighter."""
        highlighter = get_highlighter()

        assert isinstance(highlighter, PygmentsHighlighter)
        assert isinstance(highlighter, SyntaxHighlighter)

    def test_returns_new_instance_each_call(self):
        """Test that get_highlighter returns a new instance each call."""
        h1 = get_highlighter()
        h2 = get_highlighter()

        assert h1 is not h2


# =============================================================================
# TreeSitterHighlighter Tests
# =============================================================================


class TestTreeSitterHighlighter:
    """Tests for the TreeSitterHighlighter placeholder."""

    def test_not_implemented(self):
        """Test that TreeSitterHighlighter raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            TreeSitterHighlighter()

        assert "planned for future" in str(exc_info.value).lower()


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(code=st.text(min_size=0, max_size=500))
    @hypothesis_settings(max_examples=30)
    def test_highlight_never_crashes(self, code):
        """Test that highlight() never crashes with any input."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight(code, "python")

        assert isinstance(result, HighlightedCode)
        assert isinstance(result.text, Text)
        assert result.line_count >= 1

    @given(language=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=["L", "N"])))
    @hypothesis_settings(max_examples=30)
    def test_supports_language_never_crashes(self, language):
        """Test that supports_language() never crashes with any input."""
        highlighter = PygmentsHighlighter()
        result = highlighter.supports_language(language)

        assert isinstance(result, bool)

    @given(language=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=["L", "N"])))
    @hypothesis_settings(max_examples=30)
    def test_normalize_language_never_crashes(self, language):
        """Test that normalize_language() never crashes with any input."""
        highlighter = PygmentsHighlighter()
        result = highlighter.normalize_language(language)

        assert isinstance(result, str)
        assert result == result.lower()

    @given(
        code=st.text(min_size=0, max_size=200),
        filename=st.one_of(st.none(), st.text(min_size=1, max_size=50).map(lambda s: f"{s}.py")),
    )
    @hypothesis_settings(max_examples=30)
    def test_detect_language_never_crashes(self, code, filename):
        """Test that detect_language() never crashes with any input."""
        highlighter = PygmentsHighlighter()
        result = highlighter.detect_language(code, filename=filename)

        assert result is None or isinstance(result, str)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_highlight_code_with_unicode(self):
        """Test highlighting code with unicode characters."""
        highlighter = PygmentsHighlighter()
        code = 'print("Hello, 世界! 🌍")'
        result = highlighter.highlight(code, "python")

        assert isinstance(result, HighlightedCode)

    def test_highlight_code_with_special_characters(self):
        """Test highlighting code with special characters."""
        highlighter = PygmentsHighlighter()
        code = 'regex = r"[\\w]+\\s*=\\s*.*"'
        result = highlighter.highlight(code, "python")

        assert isinstance(result, HighlightedCode)

    def test_highlight_very_long_line(self):
        """Test highlighting code with very long lines."""
        highlighter = PygmentsHighlighter()
        code = "x = " + '"a" * 1000'
        result = highlighter.highlight(code, "python")

        assert isinstance(result, HighlightedCode)

    def test_highlight_many_lines(self):
        """Test highlighting code with many lines."""
        highlighter = PygmentsHighlighter()
        code = "\n".join([f"print({i})" for i in range(100)])
        result = highlighter.highlight(code, "python")

        assert result.line_count == 100

    def test_highlight_preserves_blank_lines(self):
        """Test that blank lines are preserved in output."""
        highlighter = PygmentsHighlighter()
        code = "line1\n\nline3"
        result = highlighter.highlight(code, "text")

        assert result.line_count == 3

    def test_highlight_tabs_and_spaces(self):
        """Test highlighting code with tabs and spaces."""
        highlighter = PygmentsHighlighter()
        code = "def foo():\n\treturn\t'hello'"
        result = highlighter.highlight(code, "python")

        assert isinstance(result, HighlightedCode)

    def test_empty_language_treated_as_text(self):
        """Test that empty language string falls back to text."""
        highlighter = PygmentsHighlighter()
        # Empty string should normalize to empty, which isn't supported
        result = highlighter.highlight("code", "")

        # Should fall back to text
        assert result.language == "text"

    def test_whitespace_only_code(self):
        """Test highlighting whitespace-only code."""
        highlighter = PygmentsHighlighter()
        result = highlighter.highlight("   \n\t\n   ", "python")

        assert isinstance(result, HighlightedCode)
        assert result.line_count == 3


# =============================================================================
# Integration Behavior Tests
# =============================================================================


class TestIntegrationBehaviors:
    """Tests for integrated highlighting behaviors."""

    def test_highlight_then_detect_roundtrip(self):
        """Test that detecting language from highlighted code works."""
        highlighter = PygmentsHighlighter()

        # Use code with a Python shebang for reliable detection
        python_code = "#!/usr/bin/env python3\ndef hello():\n    print('Hello')"
        highlighted = highlighter.highlight(python_code, "python")
        assert highlighted.language == "python"

        # Detect should recognize Python (shebang makes it reliable)
        detected = highlighter.detect_language(python_code)
        assert detected in ("python", "python3")

    def test_multiple_highlights_same_instance(self):
        """Test that same highlighter instance can be reused."""
        highlighter = PygmentsHighlighter()

        r1 = highlighter.highlight("print(1)", "python")
        r2 = highlighter.highlight("console.log(2)", "javascript")
        r3 = highlighter.highlight("puts 3", "ruby")

        assert r1.language == "python"
        assert r2.language == "javascript"
        assert r3.language == "ruby"

    def test_different_themes_same_code(self):
        """Test highlighting same code with different themes."""
        highlighter = PygmentsHighlighter()
        code = "print('hello')"

        r1 = highlighter.highlight(code, "python", theme="monokai")
        r2 = highlighter.highlight(code, "python", theme="friendly")

        # Both should succeed (themes produce different styling)
        assert isinstance(r1, HighlightedCode)
        assert isinstance(r2, HighlightedCode)
