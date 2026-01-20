"""Syntax highlighting abstraction for code blocks.

This module provides an abstract interface for syntax highlighting that can be
implemented by different backends. The default implementation uses Pygments via
Rich's Syntax class, with architecture designed to support future tree-sitter
migration for streaming responses.

Features:
- Abstract base class for pluggable highlighters
- Pygments-based default implementation
- Language alias normalization (py → python, js → javascript)
- Language detection from code content or filename
- Theme support via Pygments color schemes
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from rich.text import Text


@dataclass
class HighlightedCode:
    """Result of syntax highlighting.

    Attributes:
        text: Rich Text object with styling applied.
        language: Normalized language identifier.
        line_count: Number of lines in the code.
    """

    text: Text
    language: str
    line_count: int


class SyntaxHighlighter(ABC):
    """Abstract base for syntax highlighting implementations.

    This interface allows swapping highlighting backends (e.g., Pygments to
    tree-sitter) without changing consuming code. Implementations must handle
    language normalization and provide graceful fallbacks for unsupported
    languages.
    """

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
            theme: Pygments color theme name.

        Returns:
            HighlightedCode with styled Rich Text.
        """
        ...

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """Check if the highlighter supports a language.

        Args:
            language: Language identifier to check.

        Returns:
            True if the language is supported, False otherwise.
        """
        ...

    @abstractmethod
    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        """Attempt to detect language from code content or filename.

        Args:
            code: Source code to analyze.
            filename: Optional filename for extension-based detection.

        Returns:
            Detected language identifier, or None if detection failed.
        """
        ...


class PygmentsHighlighter(SyntaxHighlighter):
    """Pygments-based syntax highlighting (default implementation).

    Uses Rich's Syntax class which wraps Pygments for rendering. Provides
    language alias normalization and graceful fallback for unsupported
    languages.

    Attributes:
        LANGUAGE_ALIASES: Mapping of common language variations to canonical names.
    """

    LANGUAGE_ALIASES: dict[str, str] = {
        "py": "python",
        "py3": "python",
        "python3": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "jsx": "javascript",
        "rb": "ruby",
        "rs": "rust",
        "yml": "yaml",
        "sh": "bash",
        "shell": "bash",
        "zsh": "bash",
        "dockerfile": "docker",
        "md": "markdown",
        "cs": "csharp",
        "c++": "cpp",
        "h": "c",
        "hpp": "cpp",
        "kt": "kotlin",
        "pl": "perl",
        "hs": "haskell",
    }

    def normalize_language(self, language: str) -> str:
        """Normalize a language identifier to its canonical form.

        Args:
            language: Language identifier (may be an alias).

        Returns:
            Canonical language name.
        """
        return self.LANGUAGE_ALIASES.get(language.lower(), language.lower())

    def highlight(
        self,
        code: str,
        language: str,
        *,
        line_numbers: bool = False,
        theme: str = "monokai",
    ) -> HighlightedCode:
        """Highlight code using Pygments via Rich's Syntax class.

        Args:
            code: Source code to highlight.
            language: Language identifier (e.g., "python", "javascript").
            line_numbers: Whether to include line numbers.
            theme: Pygments color theme name.

        Returns:
            HighlightedCode with styled Rich Text.
        """
        from rich.syntax import Syntax

        # Normalize language name
        lang = self.normalize_language(language)

        # Check if language is supported, fallback to text if not
        if not self.supports_language(lang):
            lang = "text"

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
        """Check if Pygments supports a language.

        Args:
            language: Language identifier to check.

        Returns:
            True if Pygments has a lexer for the language.
        """
        from pygments.lexers import get_lexer_by_name  # type: ignore[import-untyped]
        from pygments.util import ClassNotFound  # type: ignore[import-untyped]

        lang = self.normalize_language(language)
        try:
            get_lexer_by_name(lang)
            return True
        except ClassNotFound:
            return False

    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        """Detect language from code content or filename.

        Uses Pygments' heuristics to guess the language from shebang lines,
        content analysis, or file extension.

        Args:
            code: Source code to analyze.
            filename: Optional filename for extension-based detection.

        Returns:
            Detected language identifier, or None if detection failed.
        """
        from pygments.lexers import ClassNotFound, guess_lexer, guess_lexer_for_filename

        try:
            if filename:
                lexer = guess_lexer_for_filename(filename, code)
            else:
                lexer = guess_lexer(code)
            # Lexer aliases is a list of str
            aliases: list[str] = lexer.aliases
            return aliases[0] if aliases else str(lexer.name).lower()
        except ClassNotFound:
            return None


class TreeSitterHighlighter(SyntaxHighlighter):
    """Tree-sitter based syntax highlighting (for streaming support).

    This implementation will be completed in a future phase when streaming
    response support is added. Tree-sitter provides incremental parsing which
    is essential for efficient re-highlighting during streaming.

    Raises:
        NotImplementedError: Always, as this is a placeholder for future work.
    """

    def __init__(self) -> None:
        """Initialize TreeSitterHighlighter.

        Raises:
            NotImplementedError: Always, as tree-sitter support is planned for future.
        """
        raise NotImplementedError(
            "TreeSitterHighlighter is planned for future implementation. "
            "Use PygmentsHighlighter for now."
        )

    def highlight(
        self,
        code: str,
        language: str,
        *,
        line_numbers: bool = False,
        theme: str = "monokai",
    ) -> HighlightedCode:
        """Not implemented."""
        raise NotImplementedError

    def supports_language(self, language: str) -> bool:
        """Not implemented."""
        raise NotImplementedError

    def detect_language(self, code: str, filename: str | None = None) -> str | None:
        """Not implemented."""
        raise NotImplementedError


def get_highlighter() -> SyntaxHighlighter:
    """Get the default syntax highlighter.

    Returns:
        A PygmentsHighlighter instance.
    """
    return PygmentsHighlighter()
