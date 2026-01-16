# Pygent: Vision Document

## Overview

**Pygent** is an AI-powered coding agent CLI tool built in Python. It provides developers with an intelligent assistant that can read, write, search, and execute code within their projects through natural language interaction.

## Core Philosophy

- **Agent = LLM + Loop + Tokens**: Simple, transparent architecture
- **Developer-first**: Built by developers, for developers
- **Safety-conscious**: Risk-tiered permissions protect against unintended actions
- **Extensible**: Clean abstractions enable provider switching and tool additions
- **Modern Python**: Async-native, fully typed, contemporary tooling

## Target Users

- Professional developers seeking AI-assisted coding workflows
- Teams wanting a customizable, self-hosted coding agent
- Developers who prefer CLI tools over IDE integrations

## Key Features

### Intelligent Agent Loop
- Natural language interface for coding tasks
- Automatic tool selection and chaining
- Context-aware responses based on project structure
- Conversation history with session persistence

### Comprehensive Tool Suite
| Category | Capabilities |
|----------|-------------|
| **Filesystem** | Read, list, edit, create, delete files |
| **Execution** | Shell commands, test runners |
| **Search** | Grep/ripgrep-style code search |
| **Web** | Fetch URLs, API interactions |
| **Git** | Version control operations |
| **Project** | Scaffolding, project analysis |

### Risk-Tiered Permission System
| Risk Level | Behavior | Examples |
|------------|----------|----------|
| `LOW` | Auto-approved | read_file, list_files, search |
| `MEDIUM` | User prompted | edit_file, create_file, delete |
| `HIGH` | Always prompts | shell, git push, web requests |

- Permissions can be disabled at session level for trusted workflows
- Clear user notification of all tool invocations

### Rich Terminal Interface
- Split-view layout: conversation panel + tool activity panel
- Syntax-highlighted code output
- Real-time tool execution status
- Session management UI

### Project Intelligence
- Auto-detects `.git` repositories
- Reads `pyproject.toml`, `package.json` for project context
- Respects `.gitignore` in file operations
- Project-local configuration via `.pygent/` directory

### Customizable Behavior
- User-level system prompts in config
- Project-level prompt overrides (`.pygent/prompt.md`)
- Configurable model selection and parameters

## Technical Architecture

### Stack
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.10+ | Broad compatibility, async support |
| TUI Framework | Textual | Modern, async-native, rich widgets |
| HTTP Client | httpx | Async HTTP, modern API |
| LLM Abstraction | litellm | 100+ providers, unified interface |
| Config Format | TOML | Human-readable, Python-native |
| Session Storage | JSON | Simple, portable, debuggable |
| Package Manager | uv | Fast, modern, Rust-based |
| Testing | pytest | Industry standard |
| Linting | ruff | Fast, comprehensive |
| CI/CD | GitHub Actions | Standard, well-integrated |

### Project Structure
```
pygent/
├── src/
│   └── pygent/
│       ├── __init__.py
│       ├── cli.py                 # Entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py           # Main agent class
│       │   ├── loop.py            # Conversation loop
│       │   ├── providers.py       # litellm wrapper
│       │   └── permissions.py     # Risk-tiered permission system
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py            # Tool decorator & base classes
│       │   ├── registry.py        # Tool registration
│       │   ├── filesystem.py      # read, list, edit, create, delete
│       │   ├── shell.py           # Command execution
│       │   ├── search.py          # Code search
│       │   ├── web.py             # HTTP fetching
│       │   └── git.py             # Git operations
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py             # Main Textual application
│       │   ├── widgets.py         # Custom widgets
│       │   ├── screens.py         # Application screens
│       │   └── styles.tcss        # Textual CSS
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py        # Configuration models
│       │   └── loader.py          # TOML loading
│       └── session/
│           ├── __init__.py
│           ├── models.py          # Session data models
│           └── storage.py         # JSON persistence
├── tests/
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_tools/
│   └── test_tui/
├── pyproject.toml
├── README.md
└── .github/
    └── workflows/
        └── ci.yml
```

### Code Standards
- **Typing**: Full static type hints (strict mypy compliance)
- **Docstrings**: Google style
- **Line Length**: 120 characters
- **Formatting**: ruff format
- **Linting**: ruff check

## Design Patterns

### Tool Registration (Decorator Pattern)
```python
from pygent.tools import tool, ToolRisk

@tool(
    name="read_file",
    description="Read the contents of a file at the given path",
    risk=ToolRisk.LOW
)
async def read_file(path: str) -> str:
    """Read file contents.

    Args:
        path: Absolute or relative path to the file.

    Returns:
        The file contents as a string.
    """
    async with aiofiles.open(path) as f:
        return await f.read()
```

### Provider Abstraction
```python
from pygent.core.providers import LLMProvider

async def run_agent():
    provider = LLMProvider(
        model="anthropic/claude-sonnet-4-20250514",
        api_key=config.api_key
    )
    response = await provider.complete(messages, tools)
```

### Permission Flow
```
Tool Invoked → Check Risk Level →
  LOW: Execute immediately
  MEDIUM: Prompt user (unless session override)
  HIGH: Always prompt user
→ Execute → Return result to LLM → Notify user
```

## Configuration

### User Config (`~/.config/pygent/config.toml`)
```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
max_tokens = 4096

[permissions]
auto_approve_low_risk = true
session_override_allowed = true

[tui]
theme = "dark"
show_tool_panel = true

[system_prompt]
content = """
You are a helpful coding assistant...
"""
```

### Project Config (`.pygent/config.toml`)
```toml
[project]
type = "python"
test_command = "pytest"

[context]
include = ["src/**/*.py", "tests/**/*.py"]
exclude = ["**/node_modules/**"]
```

### Project Prompt Override (`.pygent/prompt.md`)
```markdown
You are working on the Pygent project, a Python CLI tool...
Focus on maintaining async patterns and type safety.
```

## Delivery Phases

1. **Phase 1 - MVP**: Core loop, essential tools, basic TUI, config, sessions, permissions
2. **Phase 2 - Extended Tools**: Git, web, search, file create/delete
3. **Phase 3 - Advanced Features**: Test runner, scaffolding, enhanced TUI
4. **Phase 4 - Polish & Distribution**: Project auto-discovery, prompt customization, PyPI release

See individual phase documents for detailed specifications.

## Success Criteria

- Clean, maintainable codebase with >80% test coverage
- Sub-second response latency for tool execution
- Intuitive permission prompts that don't interrupt flow
- Seamless session persistence and resumption
- Easy provider switching via config
- PyPI installable with `uv install pygent` or `pip install pygent`

## Future Considerations (Post-v1.0)

- Streaming responses
- Multi-file refactoring tools
- Language server protocol integration
- Plugin system for custom tools
- Team/enterprise features
- Local model support via Ollama

---

*Document Version: 1.0*
*Created: 2026-01-16*
