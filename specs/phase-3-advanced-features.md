# Phase 3: Advanced Features

## Objective

Enhance chapgent with advanced capabilities: test running integration, project scaffolding, enhanced TUI features, and improved context awareness. This phase elevates chapgent from a tool collection to an intelligent development companion.

## Prerequisites

- Phase 1 & 2 completed
- Full tool suite operational
- Permission system mature
- Session management stable

---

## Deliverables

### 1. Test Runner Integration (`tools/testing.py`)

#### 1.1 run_tests
```python
@tool(
    name="run_tests",
    description="Run project tests using the appropriate test framework",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.TESTING,
)
async def run_tests(
    path: str | None = None,
    pattern: str | None = None,
    verbose: bool = False,
    coverage: bool = False,
    fail_fast: bool = False,
) -> str:
    """Run project tests.

    Args:
        path: Specific test file or directory.
        pattern: Test name pattern to match.
        verbose: Enable verbose output.
        coverage: Run with coverage reporting.
        fail_fast: Stop on first failure.

    Returns:
        Test results summary with pass/fail counts.
    """
```

#### 1.2 Test Framework Detection
```python
class TestFramework(Enum):
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    MOCHA = "mocha"
    VITEST = "vitest"
    GO_TEST = "go test"
    CARGO_TEST = "cargo test"
    UNKNOWN = "unknown"

async def detect_test_framework(project_path: Path) -> TestFramework:
    """Auto-detect test framework from project files.

    Detection rules:
    - pytest.ini, pyproject.toml [tool.pytest] → pytest
    - package.json with jest → jest
    - package.json with vitest → vitest
    - go.mod → go test
    - Cargo.toml → cargo test
    """
```

#### 1.3 Test Output Parsing
```python
@dataclass
class TestResult:
    name: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration: float | None
    error_message: str | None
    file_path: str | None
    line_number: int | None

@dataclass
class TestSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    results: list[TestResult]

async def parse_test_output(
    output: str,
    framework: TestFramework,
) -> TestSummary:
    """Parse test runner output into structured results."""
```

#### 1.4 TUI Test Results Widget
```python
class TestResultsPanel(Widget):
    """Display test results with collapsible failure details.

    Features:
    - Summary bar (✓ 45 passed, ✗ 2 failed, ○ 3 skipped)
    - Expandable failure details
    - Click to navigate to failing test
    - Re-run button for failed tests
    """
```

---

### 2. Project Scaffolding (`tools/scaffold.py`)

#### 2.1 create_project
```python
@tool(
    name="create_project",
    description="Create a new project from a template",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.PROJECT,
)
async def create_project(
    name: str,
    template: str,
    path: str = ".",
    options: dict | None = None,
) -> str:
    """Create a new project.

    Args:
        name: Project name.
        template: Template identifier (e.g., "python-cli", "fastapi").
        path: Parent directory for new project.
        options: Template-specific options.

    Returns:
        Summary of created files and next steps.
    """
```

#### 2.2 Built-in Templates
```python
TEMPLATES = {
    "python-cli": {
        "description": "Python CLI application with Click",
        "files": [
            "pyproject.toml",
            "src/{name}/__init__.py",
            "src/{name}/cli.py",
            "src/{name}/main.py",
            "tests/conftest.py",
            "tests/test_main.py",
            ".gitignore",
            "README.md",
        ],
        "options": {
            "use_typer": {"type": "bool", "default": False},
            "include_docker": {"type": "bool", "default": False},
        },
    },
    "python-lib": {
        "description": "Python library for PyPI distribution",
        # ...
    },
    "fastapi": {
        "description": "FastAPI web application",
        # ...
    },
}
```

#### 2.3 list_templates
```python
@tool(
    name="list_templates",
    description="List available project templates",
    risk=ToolRisk.LOW,
    category=ToolCategory.PROJECT,
)
async def list_templates() -> str:
    """List available project templates.

    Returns:
        JSON array of templates with descriptions.
    """
```

#### 2.4 add_component
```python
@tool(
    name="add_component",
    description="Add a component or feature to an existing project",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.PROJECT,
)
async def add_component(
    component: str,
    name: str | None = None,
    options: dict | None = None,
) -> str:
    """Add a component to current project.

    Args:
        component: Component type (e.g., "model", "route", "test").
        name: Component name.
        options: Component-specific options.

    Components vary by project type:
    - Python: model, service, test, cli_command
    - FastAPI: route, model, schema, middleware
    """
```

---

### 3. Enhanced TUI

#### 3.1 Session Sidebar
```python
class SessionSidebar(Widget):
    """Collapsible sidebar showing session list.

    Features:
    - List recent sessions
    - Session search/filter
    - Quick switch between sessions
    - Session metadata preview
    - Delete session option
    """
```

#### 3.2 Command Palette
```python
class CommandPalette(Widget):
    """Fuzzy-search command palette (Ctrl+P).

    Commands:
    - New Session
    - Open Session...
    - Save Session
    - Toggle Tool Panel
    - Toggle Permission Override
    - Change Model
    - Open Config
    - List Tools
    - Clear Conversation
    - Export Session
    """
```

#### 3.3 Markdown Rendering
```python
class MarkdownDisplay(Widget):
    """Enhanced markdown rendering.

    Features:
    - Syntax-highlighted code blocks
    - Tables
    - Links (clickable to open)
    - Images (as placeholders)
    - Task lists
    - Horizontal rules
    """
```

#### 3.4 Tool Execution Progress
```python
class ToolProgress(Widget):
    """Show real-time progress for long-running tools.

    Features:
    - Spinner/progress bar
    - Elapsed time
    - Cancel button (Ctrl+C)
    - Output streaming for shell commands
    """
```

#### 3.5 Keyboard Shortcuts Enhancement
```python
BINDINGS = [
    # Existing
    ("ctrl+c", "quit", "Quit"),
    ("ctrl+n", "new_session", "New Session"),
    ("ctrl+s", "save_session", "Save"),
    ("ctrl+p", "toggle_permissions", "Toggle Permissions"),

    # Implemented
    ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),  # ✅ Implemented
    ("ctrl+shift+p", "command_palette", "Commands"),  # ✅ Implemented
    ("ctrl+t", "toggle_tools", "Toggle Tool Panel"),  # ✅ Implemented
    ("ctrl+l", "clear", "Clear"),  # ✅ Implemented

    # New (TODO)
    ("ctrl+/", "help", "Help"),
    ("ctrl+o", "open_session", "Open Session"),
    ("f5", "rerun_last", "Re-run Last"),
    ("escape", "cancel", "Cancel"),
]
```

---

### 4. Context Awareness System

#### 4.1 Project Context Model
```python
@dataclass
class ProjectContext:
    """Detected project information.

    Attributes:
        type: Project type (python, node, go, rust, etc.)
        root: Project root directory
        name: Project name
        version: Project version
        dependencies: List of dependencies
        scripts: Available scripts/commands
        test_framework: Detected test framework
        git_info: Git repository info
        config_files: Relevant config files
    """
    type: str
    root: Path
    name: str | None
    version: str | None
    dependencies: list[str]
    scripts: dict[str, str]
    test_framework: TestFramework
    git_info: GitInfo | None
    config_files: list[Path]
```

#### 4.2 Project Detection
```python
async def detect_project_context(path: Path = Path.cwd()) -> ProjectContext:
    """Detect project type and gather context.

    Detection sources:
    - pyproject.toml, setup.py → Python
    - package.json → Node.js
    - go.mod → Go
    - Cargo.toml → Rust
    - .git → Git info
    - Various config files
    """
```

#### 4.3 Context Injection
```python
def build_system_prompt(
    base_prompt: str,
    context: ProjectContext,
    user_overrides: str | None,
) -> str:
    """Build system prompt with project context.

    Injects:
    - Project type and structure
    - Available commands
    - Coding conventions
    - User customizations
    """
```

#### 4.4 .gitignore Respect
```python
class GitIgnoreFilter:
    """Filter file operations based on .gitignore.

    Used by:
    - list_files tool
    - grep_search tool
    - find_files tool
    - Project scaffolding
    """

    def __init__(self, root: Path) -> None: ...
    def is_ignored(self, path: Path) -> bool: ...
    def filter_paths(self, paths: Iterable[Path]) -> list[Path]: ...
```

---

### 5. Error Recovery System

#### 5.1 Smart Error Handling
```python
class ErrorRecovery:
    """Intelligent error handling with retry suggestions.

    Features:
    - Parse common error patterns
    - Suggest fixes for known issues
    - Auto-retry with modifications
    - Learn from successful recoveries
    """

    async def handle_tool_error(
        self,
        tool_name: str,
        error: Exception,
        context: dict,
    ) -> RecoveryAction:
        """Determine recovery action for tool error.

        Returns:
            RecoveryAction with retry flag and suggestions.
        """
```

#### 5.2 Common Error Patterns
```python
ERROR_PATTERNS = {
    "FileNotFoundError": {
        "suggest": "Check if the file path is correct. Use list_files to see available files.",
        "auto_retry": False,
    },
    "PermissionError": {
        "suggest": "File permissions issue. Check file ownership and permissions.",
        "auto_retry": False,
    },
    "git_not_a_repository": {
        "suggest": "Not inside a git repository. Initialize with git init or navigate to a repo.",
        "auto_retry": False,
    },
    "module_not_found": {
        "suggest": "Module not installed. Run: pip install {module}",
        "auto_retry": False,
    },
}
```

---

### 6. Conversation Features

#### 6.1 Message Editing
```python
class EditableMessage(Widget):
    """Allow editing of previous user messages.

    Features:
    - Click to edit
    - Re-run from edited point
    - Fork conversation
    """
```

#### 6.2 Conversation Branching
```python
class ConversationBranch:
    """Support for conversation branching.

    When user edits a previous message:
    - Create branch point
    - Allow switching between branches
    - Preserve all branches in session
    """
```

#### 6.3 Export Options
```python
@cli.command()
@click.option("--format", type=click.Choice(["markdown", "json", "html"]))
@click.argument("session_id")
def export(session_id: str, format: str):
    """Export a session to various formats."""
```

---

### 7. Performance Optimizations

#### 7.1 Tool Result Caching
```python
class ToolCache:
    """Cache expensive tool results.

    Caches:
    - File reads (invalidated on modification)
    - Directory listings
    - Git status (short TTL)
    - Search results (content-hash based)
    """

    def __init__(self, max_size: int = 100, ttl: int = 60) -> None: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    def invalidate(self, pattern: str) -> None: ...
```

#### 7.2 Parallel Tool Execution
```python
async def execute_tools_parallel(
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
    permissions: PermissionManager,
) -> list[ToolResult]:
    """Execute multiple tool calls in parallel where safe.

    Safety rules:
    - Read operations can run in parallel
    - Write operations run sequentially
    - Same-file operations run sequentially
    """
```

#### 7.3 Lazy Loading
```python
# Defer heavy imports until needed
def get_git_tools():
    from chapgent.tools.git import git_status, git_diff, ...
    return [git_status, git_diff, ...]
```

---

### 8. Testing Additions

#### 8.1 Test Runner Tests
```python
async def test_detect_pytest_framework(tmp_path):
    """Test pytest detection."""

async def test_run_tests_with_failures(tmp_path, mock_pytest):
    """Test handling of test failures."""

async def test_parse_pytest_output():
    """Test pytest output parsing."""
```

#### 8.2 Scaffolding Tests
```python
async def test_create_python_cli_project(tmp_path):
    """Test Python CLI template generation."""

async def test_add_component_to_project(tmp_path):
    """Test adding component to existing project."""
```

#### 8.3 TUI Integration Tests
```python
async def test_command_palette():
    """Test command palette interaction."""

async def test_session_sidebar():
    """Test session switching."""
```

---

## Acceptance Criteria

### Functional
- [x] Test runner detects framework automatically
- [x] Test results displayed in structured format
- [x] Project scaffolding creates valid project structures
- [x] Templates are customizable
- [x] Command palette accessible and functional (CommandPalette: 53 tests)
- [x] Session sidebar shows all sessions (SessionsSidebar: 28 tests)
- [x] Project context correctly detected
- [x] .gitignore respected in file operations
- [x] Error recovery provides intelligent suggestions for common errors

### Non-Functional
- [x] Tool caching reduces redundant operations (ToolCache: 48 tests)
- [x] Parallel tool execution for read operations (Parallel: 58 tests)
- [x] TUI remains responsive during long operations (ToolProgress: 56 tests)
- [ ] Memory usage stays bounded with large sessions
- [x] All features have test coverage (Context Awareness: 92 tests, Test Runner: 72 tests, Scaffolding: 77 tests, Error Recovery: 43 tests, ToolCache: 48 tests, Parallel: 58 tests, Session Sidebar: 28 tests, Command Palette: 53 tests, ToolProgress: 56 tests)

---

## Implementation Order

1. **Context Awareness** (4 days)
   - Project type detection
   - Context model implementation
   - .gitignore integration
   - System prompt enhancement

2. **Test Runner** (5 days)
   - Framework detection
   - run_tests tool
   - Output parsing
   - Results widget

3. **TUI Enhancements** (5-6 days)
   - Command palette
   - Session sidebar
   - Keyboard shortcuts
   - Progress indicators

4. **Project Scaffolding** (4 days)
   - Template system
   - Built-in templates
   - add_component tool

5. **Error Recovery & Performance** (3 days)
   - Error pattern handling
   - Tool caching
   - Parallel execution

6. **Testing & Polish** (3 days)
   - Comprehensive tests
   - Performance tuning
   - Documentation

---

*Document Version: 1.0*
*Created: 2026-01-16*
