# Chapgent

AI-powered coding agent for the terminal.

## Installation

```bash
pip install chapgent
```

Or install from source:

```bash
git clone https://github.com/davewil/chapgent.git
cd chapgent
pip install -e .
```

## Quick Start

```bash
# Start a chat session
chapgent chat

# Use mock mode (no API key needed)
chapgent chat --mock

# List available tools
chapgent tools

# View configuration
chapgent config show
```

## Configuration

Chapgent uses TOML configuration files with the following priority:

1. Environment variables (highest)
2. Project config (`.chapgent.toml` in current directory)
3. User config (`~/.config/chapgent/config.toml`)
4. Defaults (lowest)

### Environment Variables

```bash
export CHAPGENT_MODEL="claude-sonnet-4-20250514"
export CHAPGENT_API_KEY="your-api-key"
export CHAPGENT_MAX_TOKENS=4096
```

### Config Commands

```bash
chapgent config path      # Show config file locations
chapgent config init      # Create default config
chapgent config set llm.model "claude-sonnet-4-20250514"
chapgent config edit      # Open in $EDITOR
```

## Development

### Setup

```bash
# Clone and install dev dependencies
git clone https://github.com/davewil/chapgent.git
cd chapgent
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/chapgent

# Run specific test file
pytest tests/test_tools/test_filesystem.py -v
```

## Code Standards

### Async Python

- **Use `asyncio.Lock` for async code** - Never use `threading.Lock` for async-safe operations like caching
- **Wrap blocking calls with `asyncio.to_thread()`** - For blocking operations like `shutil.copy2`, `shutil.move`
- **`asyncio.gather()` preserves order** - Results match input order, useful for parallel execution

### Pydantic v2

- **Validator decorators** - Use `@field_validator` and `@model_validator` (not the old `@validator`)
- **Classmethod required** - `@field_validator` requires `@classmethod` decorator
- **Error handling** - `ValidationError.errors()` returns list of dicts with `"loc"` and `"msg"` keys

### CLI (Click)

- **Command groups** - Use `@cli.group()` for subcommands via `@group.command()`
- **Boolean env vars** - Support multiple true values: `"true"`, `"1"`, `"yes"`, `"on"`

### Git Operations

- **Git outputs to stderr on success** - Commands like `checkout` and `push` write to stderr even on success; always check both stdout and stderr

### File Operations

- **Path expansion** - Use `Path.expanduser()` for `~` expansion in user paths
- **Preserve metadata** - Use `shutil.copy2` (not `shutil.copy`) to preserve timestamps and permissions
- **Glob patterns** - `test_*.py` doesn't recurse; use `**/test_*.py` for recursive matching

### Caching

- **LRU implementation** - `OrderedDict.move_to_end(key)` is O(1), efficient for LRU caches
- **Deterministic keys** - Use `json.dumps(args, sort_keys=True)` + SHA256 for cache keys

### TUI (Textual)

- **Modal screen queries** - Use `app.screen` instead of `app.query_one()` for modal widgets
- **Input Enter handling** - `Input` widget captures Enter via `on_input_submitted()`, not screen keybindings
- **Deferred callbacks** - Use `call_later()` in `push_screen` callbacks to defer action execution

## Testing Standards

### Property-Based Testing (Hypothesis)

- **Isolate `tmp_path` fixtures** - Use `uuid.uuid4()` subdirectories per example to avoid state pollution:
  ```python
  @given(content=st.text())
  @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
  async def test_something(self, tmp_path, content):
      unique_dir = tmp_path / str(uuid.uuid4())
      unique_dir.mkdir()
      # ... test code using unique_dir
  ```

- **Suppress fixture health check** - Add `suppress_health_check=[HealthCheck.function_scoped_fixture]` when using pytest fixtures with `@given`

- **Use named parameters** - Hypothesis `@given` parameters must be keyword form when combined with pytest fixtures

### Async Testing

- **Avoid AsyncMock cleanup warnings** - Replace `AsyncMock` with `MagicMock` + explicit async methods:
  ```python
  # Instead of AsyncMock(), use:
  mock = MagicMock()
  async def async_return():
      return "result"
  mock.some_method = async_return
  ```

### Pytest Collection

- **Prevent false collection** - Add `__test__ = False` to classes/enums with "Test" in the name:
  ```python
  class TestFramework(StrEnum):
      __test__ = False  # Prevent pytest collection
      PYTEST = "pytest"
  ```

### Config Priority Testing

- **API key precedence** - Test explicit priority ordering (e.g., `CHAPGENT_API_KEY > ANTHROPIC_API_KEY`)
- **Use `monkeypatch.delenv(raising=False)`** - Cleaner than try/except for clearing env vars

## Architecture

```
src/chapgent/
├── cli.py              # CLI entry point (Click)
├── config/             # Configuration system
│   ├── loader.py       # Config file loading
│   ├── settings.py     # Pydantic models
│   └── prompt.py       # System prompt handling
├── context/            # Project context detection
│   ├── detection.py    # Auto-detect project type
│   └── prompt.py       # Context-aware prompts
├── core/               # Core agent infrastructure
│   ├── agent.py        # Agent class
│   ├── loop.py         # Conversation loop
│   ├── cache.py        # Tool result caching
│   ├── parallel.py     # Parallel tool execution
│   ├── recovery.py     # Error recovery
│   └── logging.py      # Loguru logging setup
├── session/            # Session management
│   ├── models.py       # Session/Message models
│   └── storage.py      # Session persistence
├── tools/              # Tool implementations
│   ├── base.py         # Tool decorator & registry
│   ├── filesystem.py   # File operations
│   ├── git.py          # Git operations
│   ├── search.py       # grep, find, definitions
│   ├── shell.py        # Shell command execution
│   ├── testing.py      # Test runner
│   ├── scaffold.py     # Project scaffolding
│   └── web.py          # Web fetching
└── tui/                # Terminal UI (Textual)
    ├── app.py          # Main application
    ├── widgets.py      # Custom widgets
    └── styles.tcss     # Styling
```

## License

MIT
