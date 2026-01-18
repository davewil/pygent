# Phase 4: Polish & Distribution

## Objective

Prepare pygent for public release: finalize customization features, comprehensive documentation, PyPI packaging, and distribution infrastructure. This phase transforms pygent from a working tool into a polished, distributable product.

## Prerequisites

- Phases 1-3 completed
- Core functionality stable
- Test coverage >80%
- No critical bugs

---

## Deliverables

### 1. System Prompt Customization

#### 1.1 User-Level Configuration
```toml
# ~/.config/pygent/config.toml

[system_prompt]
# Base prompt (replaces default entirely)
content = """
You are a senior software engineer helping with coding tasks.
Always write clean, well-tested code.
Prefer simple solutions over complex ones.
"""

# Or use a file reference
# file = "~/.config/pygent/prompt.md"

# Append to default prompt instead of replacing
append = """
Additional context: I work primarily on Python and TypeScript projects.
"""
```

#### 1.2 Project-Level Overrides
```
.pygent/
├── config.toml       # Project settings
└── prompt.md         # Project-specific prompt
```

```toml
# .pygent/config.toml

[system_prompt]
# Project prompt appends to user prompt
file = "prompt.md"
mode = "append"  # or "replace"
```

```markdown
<!-- .pygent/prompt.md -->

# Pygent Project Context

This is the pygent project - an AI coding agent.

## Architecture
- Async Python with Textual TUI
- Tool-based architecture with decorator registration
- Risk-tiered permission system

## Coding Standards
- Full type hints (strict mypy)
- Google-style docstrings
- 120 character line length
- Use ruff for formatting

## Important Files
- `src/pygent/core/agent.py` - Main agent loop
- `src/pygent/tools/base.py` - Tool decorator
- `src/pygent/tui/app.py` - TUI application
```

#### 1.3 Prompt Template Variables
```python
TEMPLATE_VARIABLES = {
    "project_name": "Name of current project",
    "project_type": "Detected project type (python, node, etc.)",
    "current_dir": "Current working directory",
    "git_branch": "Current git branch",
    "date": "Current date",
    "os": "Operating system",
}

# Usage in prompt:
content = """
You are working on {project_name}, a {project_type} project.
Current branch: {git_branch}
"""
```

#### 1.4 Prompt Management CLI
```python
@cli.group()
def prompt():
    """Manage system prompts."""

@prompt.command()
def show():
    """Show the effective system prompt."""

@prompt.command()
@click.argument("path")
def set(path: str):
    """Set system prompt from file."""

@prompt.command()
def edit():
    """Open system prompt in $EDITOR."""

@prompt.command()
def reset():
    """Reset to default system prompt."""
```

---

### 2. Configuration Polish

#### 2.1 Config Validation
```python
from pydantic import validator, ValidationError

class Settings(BaseModel):
    """Application settings with validation."""

    @validator("llm")
    def validate_model(cls, v):
        valid_models = get_valid_models()
        if v.model not in valid_models:
            raise ValueError(f"Unknown model: {v.model}")
        return v
```

#### 2.2 Config CLI Commands
```python
@cli.group()
def config():
    """Manage configuration."""

@config.command()
def show():
    """Show current configuration."""

@config.command()
def edit():
    """Open config in $EDITOR."""

@config.command()
def path():
    """Show config file paths."""

@config.command()
def init():
    """Create default config file."""

@config.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str):
    """Set a configuration value."""
```

#### 2.3 Environment Variable Support
```python
ENV_MAPPINGS = {
    "PYGENT_MODEL": "llm.model",
    "PYGENT_API_KEY": "llm.api_key",
    "PYGENT_MAX_TOKENS": "llm.max_tokens",
    "ANTHROPIC_API_KEY": "llm.api_key",  # Fallback
    "OPENAI_API_KEY": "llm.api_key",     # Alternative
}
```

---

### 3. Documentation

#### 3.1 README.md
```markdown
# Pygent

AI-powered coding agent for the command line.

## Features
- Natural language coding assistance
- File operations, git, search, web fetching
- Risk-tiered permission system
- Session persistence
- Rich terminal UI

## Installation
pip install pygent
# or
uv install pygent

## Quick Start
pygent chat

## Configuration
...

## Documentation
Full documentation at https://pygent.dev
```

#### 3.2 User Documentation (docs/)
```
docs/
├── getting-started.md
├── configuration.md
├── tools/
│   ├── filesystem.md
│   ├── git.md
│   ├── search.md
│   ├── shell.md
│   └── web.md
├── customization/
│   ├── system-prompts.md
│   ├── project-config.md
│   └── permissions.md
├── advanced/
│   ├── sessions.md
│   ├── keyboard-shortcuts.md
│   └── templates.md
└── troubleshooting.md
```

#### 3.3 API Documentation
```python
# Auto-generated from docstrings using mkdocs + mkdocstrings
```

#### 3.4 Contributing Guide
```markdown
# CONTRIBUTING.md

## Development Setup
uv sync --all-extras

## Running Tests
uv run pytest

## Code Style
- Run `uv run ruff check .` before committing
- Run `uv run ruff format .` to format
- Run `uv run mypy src/` for type checking

## Pull Request Process
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit PR with description

## Release Process
...
```

---

### 4. PyPI Packaging

#### 4.1 pyproject.toml Finalization
```toml
[project]
name = "pygent"
version = "0.1.0"
description = "AI-powered coding agent for the command line"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["ai", "agent", "cli", "coding", "llm", "anthropic"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development",
    "Topic :: Software Development :: Code Generators",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/yourname/pygent"
Documentation = "https://pygent.dev"
Repository = "https://github.com/yourname/pygent"
Issues = "https://github.com/yourname/pygent/issues"

[project.scripts]
pygent = "pygent.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 4.2 Version Management
```python
# src/pygent/__init__.py
__version__ = "0.1.0"

# Accessed via:
# pygent --version
```

#### 4.3 Build & Publish Workflow
```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Trusted publishing

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

#### 4.4 Test PyPI First
```bash
# Test release process
uv build
uv publish --repository testpypi

# Verify installation
pip install --index-url https://test.pypi.org/simple/ pygent
```

---

### 5. Release Process

#### 5.1 Versioning Strategy
- **Semantic Versioning**: MAJOR.MINOR.PATCH
- Pre-release: `0.x.y` until API stabilizes
- Alpha/Beta tags: `0.1.0a1`, `0.1.0b1`, `0.1.0rc1`

#### 5.2 Changelog
```markdown
# CHANGELOG.md

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.1.0] - 2024-XX-XX

### Added
- Initial release
- Core agent loop with litellm integration
- File tools: read, list, edit, create, delete, move, copy
- Git tools: status, diff, log, add, commit, checkout, push, pull
- Search tools: grep, find_files, find_definition
- Shell command execution
- Web fetching
- Risk-tiered permission system
- Textual-based TUI with split view
- Session persistence (JSON)
- TOML configuration
- Custom system prompts
```

#### 5.3 Release Checklist
```markdown
## Release Checklist

### Pre-release
- [ ] All tests passing on CI
- [ ] Version bumped in `__init__.py`
- [ ] CHANGELOG.md updated
- [ ] Documentation reviewed
- [ ] README accurate

### Release
- [ ] Create GitHub release with tag `vX.Y.Z`
- [ ] Verify PyPI publish workflow triggered
- [ ] Verify package on PyPI
- [ ] Test installation: `pip install pygent`

### Post-release
- [ ] Announce on relevant channels
- [ ] Monitor for critical issues
- [ ] Update documentation site
```

---

### 6. Quality Assurance

#### 6.1 End-to-End Testing
```python
# tests/e2e/test_full_workflow.py

async def test_create_edit_commit_flow():
    """Test complete workflow: create file, edit, git commit."""

async def test_search_and_refactor_flow():
    """Test searching code and performing edits."""

async def test_session_persistence():
    """Test saving and resuming sessions."""
```

#### 6.2 Cross-Platform Testing
```yaml
# .github/workflows/ci.yml

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
```

#### 6.3 Performance Benchmarks
```python
# tests/benchmarks/test_performance.py

def test_startup_time():
    """Startup should be <500ms."""

def test_tool_execution_overhead():
    """Tool dispatch overhead should be <10ms."""

def test_large_file_handling():
    """Should handle files up to 10MB."""

def test_session_load_time():
    """Session load should be <100ms."""
```

---

### 7. Error Messages & UX

#### 7.1 Friendly Error Messages
```python
ERROR_MESSAGES = {
    "no_api_key": """
No API key configured.

Set your API key in one of these ways:
1. Environment variable: export ANTHROPIC_API_KEY=your-key
2. Config file: pygent config set llm.api_key your-key

Get an API key at: https://console.anthropic.com/
""",
    "model_not_found": """
Model '{model}' not found or not accessible.

Available models:
- claude-sonnet-4-20250514 (recommended)
- claude-3-5-haiku-20241022 (faster, cheaper)

Check your API key permissions at: https://console.anthropic.com/
""",
}
```

#### 7.2 First-Run Experience
```python
async def first_run_setup():
    """Guide new users through initial setup.

    Steps:
    1. Welcome message
    2. API key configuration
    3. Model selection
    4. Quick tutorial offer
    """
```

#### 7.3 Help System
```python
@cli.command()
@click.argument("topic", required=False)
def help(topic: str | None):
    """Show help for a topic.

    Topics:
    - tools: Available tools and their usage
    - config: Configuration options
    - shortcuts: Keyboard shortcuts
    - permissions: Permission system explained
    """
```

---

### 8. Telemetry & Analytics (Optional)

#### 8.1 Anonymous Usage Statistics
```python
# Opt-in only, disabled by default

class Telemetry:
    """Anonymous usage telemetry.

    Collects:
    - Tool usage frequency (no content)
    - Error rates (no sensitive info)
    - Performance metrics
    - Feature usage

    Never collects:
    - Conversation content
    - File contents
    - API keys
    - Personal information
    """

    def __init__(self, enabled: bool = False) -> None: ...
```

#### 8.2 Configuration
```toml
[telemetry]
enabled = false  # Opt-in, default off
```

---

### 9. Logging Infrastructure

#### 9.1 Loguru Setup

Add `loguru` dependency for file-based logging that doesn't interfere with the TUI.

```python
# src/pygent/core/logging.py

from pathlib import Path
from loguru import logger

# Remove default stderr handler (would corrupt TUI)
logger.remove()

LOG_DIR = Path("~/.local/share/pygent/logs").expanduser()
LOG_FILE = LOG_DIR / "pygent.log"

def setup_logging(level: str = "DEBUG") -> None:
    """Configure logging to file with rotation.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.add(
        LOG_FILE,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",      # Rotate when file reaches 10MB
        retention="7 days",    # Keep logs for 7 days
        compression="gz",      # Compress rotated files
        enqueue=True,          # Thread-safe async logging
    )
```

#### 9.2 Configuration

```toml
# ~/.config/pygent/config.toml

[logging]
level = "INFO"          # DEBUG, INFO, WARNING, ERROR
# file = "~/.local/share/pygent/logs/pygent.log"  # Custom path
```

```python
# settings.py addition

class LoggingSettings(BaseModel):
    """Logging configuration."""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str | None = None  # Override default log path
```

#### 9.3 Integration Points

Add logging throughout the codebase:

```python
# core/agent.py
from loguru import logger

class Agent:
    async def run(self, message: str) -> AsyncIterator[LoopEvent]:
        logger.info("Starting agent run", message_length=len(message))
        try:
            async for event in conversation_loop(...):
                logger.debug("Loop event", event_type=event.type)
                yield event
        except Exception as e:
            logger.exception("Agent run failed")
            raise

# tools/filesystem.py
@tool(name="read_file", ...)
async def read_file(path: str) -> str:
    logger.debug("Reading file", path=path)
    # ...
    logger.debug("File read complete", path=path, size=len(content))

# core/providers.py
async def complete(self, messages, tools, max_tokens):
    logger.debug("LLM request", model=self.model, message_count=len(messages))
    # ...
    logger.debug("LLM response", stop_reason=response.stop_reason)
```

#### 9.4 Log Report CLI Command

```python
# cli.py

import tarfile
from datetime import datetime

@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--days", default=7, help="Include logs from last N days")
def report(output: str | None, days: int) -> None:
    """Package logs for bug reporting.

    Creates a compressed archive of recent logs with sensitive
    data (API keys, absolute paths) redacted.
    """
    log_dir = Path("~/.local/share/pygent/logs").expanduser()

    if not log_dir.exists():
        click.echo("No logs found.")
        return

    # Default output path
    if output is None:
        output = f"pygent-report-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"

    # Collect and sanitize logs
    with tarfile.open(output, "w:gz") as tar:
        for log_file in log_dir.glob("*.log*"):
            # Read and redact sensitive info
            content = _redact_sensitive(log_file.read_text())
            # Add to archive with sanitized content
            # ...

    click.echo(f"Report created: {output}")
    click.echo("Please attach this file to your GitHub issue.")


def _redact_sensitive(content: str) -> str:
    """Remove API keys, absolute paths, and other sensitive data."""
    import re

    # Redact API keys
    content = re.sub(r'(api[_-]?key["\s:=]+)["\']?[\w-]+', r'\1[REDACTED]', content, flags=re.I)
    content = re.sub(r'(sk-[a-zA-Z0-9]{20,})', '[REDACTED_KEY]', content)

    # Redact home directory paths
    home = str(Path.home())
    content = content.replace(home, "~")

    return content
```

#### 9.5 Log Levels Guide

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Detailed diagnostic info (tool args, file contents preview) |
| `INFO` | Normal operation milestones (session start, tool execution) |
| `WARNING` | Unexpected but recoverable situations (cache miss, retry) |
| `ERROR` | Failures that affect functionality (API error, file not found) |

#### 9.6 Testing Considerations

```python
# conftest.py

@pytest.fixture(autouse=True)
def disable_logging():
    """Disable file logging during tests."""
    from loguru import logger
    logger.disable("pygent")
    yield
    logger.enable("pygent")
```

---

### 10. Future-Proofing

#### 10.1 Plugin System Foundation
```python
# Placeholder for future plugin system

class PluginBase(ABC):
    """Base class for pygent plugins.

    Plugins can:
    - Register custom tools
    - Add TUI widgets
    - Extend configuration
    """

    @abstractmethod
    def register(self, app: PygentApp) -> None: ...
```

#### 10.2 API Stability
```python
# Public API marked explicitly
__all__ = [
    "Agent",
    "tool",
    "ToolRisk",
    "Session",
    "Settings",
]
```

---

## Acceptance Criteria

### Functional
- [x] System prompts customizable at user and project level
- [x] Template variables work in prompts
- [x] Environment variables override config files
- [x] Config CLI commands functional
- [x] Config validation with helpful error messages
- [x] Logging infrastructure with Loguru (file-based, no TUI interference)
- [x] Log report command for bug reporting (`pygent report`)
- [ ] Documentation complete and accurate
- [x] First-run experience smooth
- [ ] Package installable from PyPI (last step)

### Non-Functional
- [ ] Install time <30s
- [ ] Startup time <500ms
- [ ] No deprecation warnings
- [ ] Works on Python 3.10, 3.11, 3.12
- [ ] Works on Linux, macOS, Windows

---

## Implementation Order

1. **System Prompt Customization** (3 days) ✓
   - User-level config
   - Project-level overrides
   - Template variables
   - CLI commands

2. **Configuration Polish** (2 days) ✓
   - Validation
   - CLI enhancements
   - Environment variables

3. **Logging Infrastructure** (1 day) ✓
   - Loguru setup with file rotation
   - Configuration integration
   - Add logging to core modules
   - `pygent report` command

4. **Documentation** (4 days)
   - README finalization
   - User documentation
   - API documentation
   - Contributing guide

5. **Quality Assurance** (3 days) ✓
   - E2E tests
   - Cross-platform testing
   - Performance benchmarks

6. **UX Polish** (2 days) ✓
   - Error messages
   - First-run experience
   - Help system

7. **PyPI Packaging & Release** (2 days) - LAST
   - pyproject.toml finalization
   - Build verification
   - Publish workflow
   - Final testing
   - Create release
   - Publish to PyPI
   - Announce

---

## Post-Release Roadmap

After v0.1.0, consider:
- Streaming responses
- Multi-file refactoring
- Language server integration
- Plugin system
- Team features
- Local model support (Ollama)
- Voice input
- IDE extensions

---

*Document Version: 1.3*
*Created: 2026-01-16*
*Updated: 2026-01-18 - Added UX Polish (error messages, first-run experience, help system)*
