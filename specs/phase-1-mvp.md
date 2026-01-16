# Phase 1: MVP

## Objective

Deliver a functional coding agent with core capabilities: natural language interaction, essential file/shell tools, basic TUI, configuration, session persistence, and permission system.

## Deliverables

### 1. Project Setup

#### 1.1 Repository Initialization
- [x] Initialize git repository
- [x] Create `.gitignore` (Python, IDE, OS artifacts)
- [x] Set up `pyproject.toml` with uv
- [x] Configure ruff (linting + formatting)
- [x] Set up pytest configuration
- [x] Create GitHub Actions CI workflow

#### 1.2 Project Structure
```
pygent/
├── src/
│   └── pygent/
│       ├── __init__.py
│       ├── cli.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── loop.py
│       │   ├── providers.py
│       │   └── permissions.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── filesystem.py
│       │   └── shell.py
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── widgets.py
│       │   └── styles.tcss
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   └── loader.py
│       └── session/
│           ├── __init__.py
│           ├── models.py
│           └── storage.py
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_tools/
│   │   ├── test_filesystem.py
│   │   └── test_shell.py
│   └── test_config.py
├── pyproject.toml
└── .github/
    └── workflows/
        └── ci.yml
```

#### 1.3 Dependencies
```toml
[project]
dependencies = [
    "textual>=0.50.0",
    "litellm>=1.0.0",
    "httpx>=0.27.0",
    "aiofiles>=23.0.0",
    "pydantic>=2.0.0",
    "tomli>=2.0.0",          # TOML parsing (Python <3.11)
    "tomli-w>=1.0.0",        # TOML writing
    "click>=8.0.0",          # CLI framework
    "rich>=13.0.0",          # Rich text (used by Textual)
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]
```

---

### 2. Core Agent Loop

#### 2.1 Agent Class (`core/agent.py`)
```python
class Agent:
    """Main agent orchestrator.

    Attributes:
        provider: LLM provider instance.
        tools: Tool registry.
        permissions: Permission manager.
        session: Current session state.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        permissions: PermissionManager,
        session: Session,
    ) -> None: ...

    async def run(self, user_message: str) -> AsyncIterator[AgentEvent]: ...
```

#### 2.2 Conversation Loop (`core/loop.py`)
```python
async def conversation_loop(
    agent: Agent,
    messages: list[Message],
) -> AsyncIterator[LoopEvent]:
    """Execute the agent loop until no more tool calls.

    Yields:
        LoopEvent: Text output, tool calls, tool results, or completion.
    """
```

**Loop Logic:**
1. Send messages + tools to LLM
2. Process response content blocks
3. If text block → yield to UI
4. If tool_use block → check permissions → execute → append result
5. If tool results exist → loop back to step 1
6. If no tool calls → complete

#### 2.3 Provider Wrapper (`core/providers.py`)
```python
class LLMProvider:
    """Wrapper around litellm for LLM interactions.

    Provides a clean async interface and handles tool formatting.
    """

    def __init__(self, model: str, api_key: str | None = None) -> None: ...

    async def complete(
        self,
        messages: list[dict],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse: ...
```

#### 2.4 Permission Manager (`core/permissions.py`)
```python
class ToolRisk(Enum):
    LOW = "low"        # Auto-approved
    MEDIUM = "medium"  # Prompts unless session override
    HIGH = "high"      # Always prompts

class PermissionManager:
    """Manages tool execution permissions.

    Attributes:
        session_override: If True, skip prompts for MEDIUM risk.
        prompt_callback: Async function to prompt user for permission.
    """

    async def check(self, tool_name: str, risk: ToolRisk, args: dict) -> bool:
        """Check if tool execution is permitted.

        Returns:
            True if permitted, False if denied.
        """
```

---

### 3. Tool System

#### 3.1 Tool Base (`tools/base.py`)
```python
from typing import Callable, ParamSpec, TypeVar
from functools import wraps

P = ParamSpec("P")
R = TypeVar("R")

@dataclass
class ToolDefinition:
    """Tool definition for LLM consumption.

    Attributes:
        name: Unique tool identifier.
        description: What the tool does (shown to LLM).
        input_schema: JSON Schema for parameters.
        risk: Risk level for permission system.
        function: The actual async function to execute.
    """
    name: str
    description: str
    input_schema: dict
    risk: ToolRisk
    function: Callable[..., Awaitable[str]]


def tool(
    name: str,
    description: str,
    risk: ToolRisk = ToolRisk.LOW,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to register a function as an agent tool.

    Automatically generates JSON schema from type hints.
    """
```

#### 3.2 Tool Registry (`tools/registry.py`)
```python
class ToolRegistry:
    """Central registry for all available tools.

    Provides lookup by name and serialization for LLM.
    """

    def register(self, tool: ToolDefinition) -> None: ...
    def get(self, name: str) -> ToolDefinition | None: ...
    def list_definitions(self) -> list[dict]: ...  # For LLM
```

#### 3.3 Filesystem Tools (`tools/filesystem.py`)

**read_file**
```python
@tool(
    name="read_file",
    description="Read the contents of a file at the given path",
    risk=ToolRisk.LOW,
)
async def read_file(path: str) -> str:
    """Read file contents.

    Args:
        path: Path to the file (absolute or relative to cwd).

    Returns:
        File contents as string.

    Raises:
        FileNotFoundError: If file doesn't exist.
    """
```

**list_files**
```python
@tool(
    name="list_files",
    description="List files and directories at the given path",
    risk=ToolRisk.LOW,
)
async def list_files(path: str = ".", recursive: bool = False) -> str:
    """List directory contents.

    Args:
        path: Directory path (default: current directory).
        recursive: If True, list recursively.

    Returns:
        JSON array of file/directory entries.
    """
```

**edit_file**
```python
@tool(
    name="edit_file",
    description="Edit a file by replacing old_str with new_str",
    risk=ToolRisk.MEDIUM,
)
async def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Edit file via string replacement.

    Args:
        path: Path to file.
        old_str: Exact string to find and replace.
        new_str: Replacement string.

    Returns:
        Success message or error description.
    """
```

#### 3.4 Shell Tools (`tools/shell.py`)

**shell**
```python
@tool(
    name="shell",
    description="Execute a shell command and return output",
    risk=ToolRisk.HIGH,
)
async def shell(command: str, timeout: int = 60) -> str:
    """Execute shell command.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        Combined stdout and stderr, plus exit code.
    """
```

---

### 4. Configuration System

#### 4.1 Settings Models (`config/settings.py`)
```python
from pydantic import BaseModel

class LLMSettings(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    api_key: str | None = None  # Falls back to env var

class PermissionSettings(BaseModel):
    auto_approve_low_risk: bool = True
    session_override_allowed: bool = True

class TUISettings(BaseModel):
    theme: str = "dark"
    show_tool_panel: bool = True

class SystemPromptSettings(BaseModel):
    content: str = "You are a helpful coding assistant..."

class Settings(BaseModel):
    llm: LLMSettings = LLMSettings()
    permissions: PermissionSettings = PermissionSettings()
    tui: TUISettings = TUISettings()
    system_prompt: SystemPromptSettings = SystemPromptSettings()
```

#### 4.2 Config Loader (`config/loader.py`)
```python
async def load_config(
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
) -> Settings:
    """Load and merge configuration from multiple sources.

    Priority (highest to lowest):
    1. Project config (.pygent/config.toml)
    2. User config (~/.config/pygent/config.toml)
    3. Defaults

    Args:
        user_config_path: Override user config location.
        project_config_path: Override project config location.

    Returns:
        Merged Settings instance.
    """
```

**Default Paths:**
- User: `~/.config/pygent/config.toml`
- Project: `./.pygent/config.toml`

---

### 5. Session Management

#### 5.1 Session Models (`session/models.py`)
```python
from datetime import datetime
from pydantic import BaseModel

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str | list[ContentBlock]
    timestamp: datetime

class ToolInvocation(BaseModel):
    tool_name: str
    arguments: dict
    result: str
    timestamp: datetime

class Session(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message]
    tool_history: list[ToolInvocation]
    working_directory: str
    metadata: dict = {}
```

#### 5.2 Session Storage (`session/storage.py`)
```python
class SessionStorage:
    """JSON-based session persistence.

    Sessions stored at: ~/.local/share/pygent/sessions/
    """

    def __init__(self, storage_dir: Path | None = None) -> None: ...

    async def save(self, session: Session) -> None: ...
    async def load(self, session_id: str) -> Session | None: ...
    async def list_sessions(self) -> list[SessionSummary]: ...
    async def delete(self, session_id: str) -> bool: ...
```

**Storage Format:**
```
~/.local/share/pygent/sessions/
├── abc123.json
├── def456.json
└── index.json  # Quick lookup of session metadata
```

---

### 6. Terminal User Interface

#### 6.1 Main Application (`tui/app.py`)
```python
from textual.app import App
from textual.widgets import Header, Footer

class PygentApp(App):
    """Main Textual application.

    Layout:
    ┌─────────────────────────────────────────┐
    │ Header (Pygent - session name)          │
    ├─────────────────────┬───────────────────┤
    │                     │                   │
    │   Conversation      │   Tool Activity   │
    │   Panel             │   Panel           │
    │                     │                   │
    ├─────────────────────┴───────────────────┤
    │ Input Area                              │
    ├─────────────────────────────────────────┤
    │ Footer (keybindings, status)            │
    └─────────────────────────────────────────┘
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+s", "save_session", "Save"),
        ("ctrl+p", "toggle_permissions", "Toggle Permissions"),
    ]
```

#### 6.2 Custom Widgets (`tui/widgets.py`)
```python
class ConversationPanel(Widget):
    """Scrollable conversation display with markdown rendering."""

class ToolPanel(Widget):
    """Tool activity feed showing invocations and results."""

class MessageInput(Widget):
    """Multi-line input with submit handling."""

class PermissionPrompt(Widget):
    """Modal for permission requests."""
```

#### 6.3 Styles (`tui/styles.tcss`)
```css
/* Textual CSS for pygent */

Screen {
    layout: grid;
    grid-size: 2 3;
    grid-rows: auto 1fr auto;
}

#conversation {
    column-span: 1;
    border: solid $primary;
}

#tools {
    column-span: 1;
    border: solid $secondary;
}

#input {
    column-span: 2;
    height: auto;
    max-height: 10;
}
```

---

### 7. CLI Entry Point

#### 7.1 CLI Commands (`cli.py`)
```python
import click

@click.group()
@click.version_option()
def cli():
    """Pygent - AI-powered coding agent."""

@cli.command()
@click.option("--session", "-s", help="Resume a session by ID")
@click.option("--new", "-n", is_flag=True, help="Start a new session")
def chat(session: str | None, new: bool):
    """Start interactive chat session."""

@cli.command()
def sessions():
    """List saved sessions."""

@cli.command()
@click.argument("session_id")
def resume(session_id: str):
    """Resume a specific session."""

@cli.command()
def config():
    """Show current configuration."""
```

---

### 8. Testing

#### 8.1 Test Configuration (`conftest.py`)
```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider that returns canned responses."""
    provider = AsyncMock()
    provider.complete.return_value = LLMResponse(
        content=[TextBlock(text="Hello!")],
        stop_reason="end_turn",
    )
    return provider

@pytest.fixture
def temp_session_dir(tmp_path):
    """Temporary directory for session storage."""
    return tmp_path / "sessions"
```

#### 8.2 Test Coverage Requirements
- [ ] `core/agent.py` - Agent initialization, run loop
- [ ] `core/loop.py` - Conversation loop, tool handling
- [ ] `core/permissions.py` - Risk-based permission checks
- [ ] `tools/filesystem.py` - All file operations
- [ ] `tools/shell.py` - Command execution, timeout
- [ ] `config/loader.py` - Config merging, defaults
- [ ] `session/storage.py` - Save, load, list, delete

---

### 9. CI/CD

#### 9.1 GitHub Actions Workflow (`.github/workflows/ci.yml`)
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint with ruff
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Type check with mypy
        run: uv run mypy src/

      - name: Run tests
        run: uv run pytest --cov=pygent --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

---

## Acceptance Criteria

### Functional
- [x] User can start pygent and enter natural language prompts
- [x] Agent correctly calls tools based on user requests
- [x] File read/list operations work correctly
- [x] File edit operations perform exact string replacement
- [x] Shell commands execute with proper output capture
- [x] Permission prompts appear for MEDIUM/HIGH risk tools
- [x] Sessions persist between runs
- [x] Config loads from TOML files

### Non-Functional
- [x] All tests pass on Python 3.10, 3.11, 3.12 (CI workflow implemented as identified in Phase 1)
- [x] No ruff lint errors
- [x] Full type coverage (mypy strict)
- [ ] Response time <500ms for tool execution (excluding LLM latency) - not formally benchmarked

---

## Implementation Order

1. **Week 1: Foundation**
   - Project setup (uv, pyproject.toml, CI)
   - Tool base classes and registry
   - Filesystem tools (read, list, edit)

2. **Week 2: Core Loop**
   - LLM provider wrapper
   - Permission manager
   - Agent class and conversation loop

3. **Week 3: Persistence**
   - Configuration system
   - Session models and storage

4. **Week 4: TUI**
   - Basic Textual app structure
   - Conversation and tool panels
   - Input handling
   - Permission prompt modal

5. **Week 5: Integration & Polish**
   - Shell tool
   - CLI entry points
   - End-to-end testing
   - Bug fixes

---

*Document Version: 1.0*
*Created: 2026-01-16*
