"""Help system for chapgent.

Provides topic-based help content for users to understand
how to use various features of chapgent.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HelpTopic:
    """A help topic with title and content."""

    name: str
    title: str
    summary: str
    content: str


# Help topics organized by name
HELP_TOPICS: dict[str, HelpTopic] = {
    "tools": HelpTopic(
        name="tools",
        title="Available Tools",
        summary="Tools available to the AI agent",
        content="""\
Chapgent provides tools that the AI agent can use to help you code.

FILESYSTEM TOOLS
  read_file       Read contents of a file
  list_files      List files in a directory
  edit_file       Edit a file by replacing text
  create_file     Create a new file
  delete_file     Delete a file (HIGH RISK)
  move_file       Move or rename a file
  copy_file       Copy a file

SEARCH TOOLS
  grep_search     Search file contents with regex
  find_files      Find files by glob pattern
  find_definition Find symbol definitions in code

GIT TOOLS
  git_status      Show working tree status
  git_diff        Show changes (staged/unstaged)
  git_log         Show commit history
  git_branch      List/create/delete branches
  git_add         Stage files for commit
  git_commit      Create a commit
  git_checkout    Switch branches or restore files
  git_push        Push to remote (HIGH RISK)
  git_pull        Fetch and merge from remote

SHELL TOOLS
  shell           Execute shell commands (HIGH RISK)

WEB TOOLS
  web_fetch       Fetch content from a URL

TESTING TOOLS
  run_tests       Run tests with auto-detected framework

PROJECT TOOLS
  list_templates  List project templates
  create_project  Create project from template
  list_components List component templates
  add_component   Add component to project

RISK LEVELS
  LOW    - Safe operations (reading files, viewing status)
  MEDIUM - Moderate risk (writing files, git add/commit)
  HIGH   - Destructive operations (delete, shell, git push)

LOW risk tools run automatically. MEDIUM/HIGH risk tools prompt
for permission before executing.

To list all tools: chapgent tools
To filter by category: chapgent tools -c git
""",
    ),
    "config": HelpTopic(
        name="config",
        title="Configuration",
        summary="How to configure chapgent",
        content="""\
Chapgent uses TOML configuration files with the following priority:
  1. Environment variables (highest)
  2. Project config (.chapgent/config.toml)
  3. User config (~/.config/chapgent/config.toml)
  4. Defaults (lowest)

CONFIGURATION COMMANDS
  chapgent config show     Show current configuration
  chapgent config path     Show config file locations
  chapgent config edit     Open config in $EDITOR
  chapgent config init     Create default config file
  chapgent config set      Set a configuration value

SETTING VALUES
  chapgent config set llm.model claude-3-5-haiku-20241022
  chapgent config set llm.provider anthropic
  chapgent config set tui.theme textual-dark

ENVIRONMENT VARIABLES
  ANTHROPIC_API_KEY   API key for Anthropic (recommended)
  OPENAI_API_KEY      API key for OpenAI
  CHAPGENT_API_KEY      Override API key
  CHAPGENT_MODEL        Override model name
  CHAPGENT_PROVIDER     Override provider
  CHAPGENT_MAX_TOKENS   Override max tokens

CONFIGURATION SECTIONS
  [llm]           - LLM provider settings (model, api_key, max_tokens)
  [permissions]   - Permission settings (auto_approve_low_risk)
  [tui]           - TUI settings (theme, show_tool_panel)
  [system_prompt] - Custom system prompt settings
  [logging]       - Log level and file settings

EXAMPLE CONFIG
  [llm]
  model = "claude-sonnet-4-20250514"
  max_tokens = 4096

  [tui]
  theme = "textual-dark"
  show_tool_panel = true

  [system_prompt]
  append = "Focus on Python best practices."
""",
    ),
    "shortcuts": HelpTopic(
        name="shortcuts",
        title="Keyboard Shortcuts",
        summary="Keyboard shortcuts in the TUI",
        content="""\
Chapgent's terminal UI supports the following keyboard shortcuts:

GENERAL
  Ctrl+C          Cancel current operation / Quit
  Ctrl+Q          Quit application
  Ctrl+D          Quit application (EOF)

SESSION MANAGEMENT
  Ctrl+S          Save current session
  Ctrl+N          Start new session
  Ctrl+B          Toggle session sidebar

UI CONTROLS
  Ctrl+P          Toggle permission override (approve MEDIUM risk)
  Ctrl+T          Toggle tool panel visibility
  Ctrl+L          Clear conversation
  Ctrl+Shift+P    Open command palette

NAVIGATION
  Tab             Cycle focus between panels
  Up/Down         Scroll through messages
  Page Up/Down    Scroll quickly
  Home/End        Jump to start/end

INPUT
  Enter           Send message
  Shift+Enter     New line in message
  Escape          Cancel current input

COMMAND PALETTE (Ctrl+Shift+P)
  Type to filter commands
  Up/Down arrows to navigate
  Enter to execute selected command
  Escape to dismiss
""",
    ),
    "permissions": HelpTopic(
        name="permissions",
        title="Permission System",
        summary="Understanding the permission system",
        content="""\
Chapgent uses a risk-tiered permission system to protect your system
from unintended changes.

RISK LEVELS
  LOW    - Safe, read-only operations
           Examples: read_file, list_files, git_status
           Behavior: Auto-approved

  MEDIUM - Operations that modify files safely
           Examples: edit_file, git_add, git_commit
           Behavior: Prompt for permission (can override)

  HIGH   - Potentially destructive operations
           Examples: delete_file, shell, git_push
           Behavior: Always prompt for permission

PERMISSION PROMPT
  When a MEDIUM or HIGH risk tool is invoked, you'll see a prompt:
    "Allow [tool_name] with args: {...}? [y/N]"

  Enter 'y' to approve, anything else to deny.

SESSION OVERRIDE
  Press Ctrl+P to toggle session override mode:
  - When ON: MEDIUM risk tools auto-approve for this session
  - When OFF: MEDIUM risk tools always prompt
  - HIGH risk tools always prompt regardless

CONFIGURATION
  [permissions]
  auto_approve_low_risk = true      # Always true for safety
  session_override_allowed = true   # Allow Ctrl+P toggle

BEST PRACTICES
  1. Review tool arguments before approving
  2. Use session override sparingly
  3. Be extra careful with HIGH risk tools
  4. Check git status before git push
""",
    ),
    "sessions": HelpTopic(
        name="sessions",
        title="Session Management",
        summary="How to manage chat sessions",
        content="""\
Chapgent saves your conversations as sessions that you can resume later.

SESSION COMMANDS
  chapgent sessions          List all saved sessions
  chapgent chat              Start new session
  chapgent chat -s <id>      Resume session by ID
  chapgent resume <id>       Resume session by ID

KEYBOARD SHORTCUTS
  Ctrl+S          Save current session
  Ctrl+N          Start new session
  Ctrl+B          Toggle session sidebar

SESSION SIDEBAR
  The sidebar shows your saved sessions:
  - Click to switch sessions (planned)
  - Active session is highlighted
  - Shows message count for each session

SESSION DATA
  Sessions are stored in: ~/.local/share/chapgent/sessions/

  Each session saves:
  - Conversation messages
  - Tool execution history
  - Working directory

TIPS
  1. Save important sessions before closing
  2. Use descriptive first messages for easy identification
  3. Sessions persist across restarts
  4. Delete old sessions to save space
""",
    ),
    "prompts": HelpTopic(
        name="prompts",
        title="System Prompts",
        summary="Customizing the AI system prompt",
        content="""\
You can customize how the AI agent behaves by modifying the system prompt.

CONFIGURATION
  [system_prompt]
  # Direct content
  content = "You are a helpful coding assistant."

  # Or load from file
  file = "~/.config/chapgent/prompt.md"

  # Append to base prompt instead of replacing
  append = "Focus on Python and TypeScript."
  mode = "append"  # or "replace"

TEMPLATE VARIABLES
  Use these in your prompts:
    {project_name}   - Current project name
    {project_type}   - Detected type (python, node, etc.)
    {current_dir}    - Current working directory
    {git_branch}     - Current git branch
    {date}           - Current date
    {os}             - Operating system

  Example:
    content = "Working on {project_name} ({project_type})."

PROJECT-LEVEL PROMPTS
  Create .chapgent/prompt.md in your project for project-specific
  instructions:

    # Project Guidelines
    - Use pytest for testing
    - Follow PEP 8
    - Prefer dataclasses over dicts

  Configure in .chapgent/config.toml:
    [system_prompt]
    file = "prompt.md"
    mode = "append"

TIPS
  1. Keep prompts concise and focused
  2. Use "append" mode to add to base prompt
  3. Include project-specific conventions
  4. Update prompts as your needs evolve
""",
    ),
    "quickstart": HelpTopic(
        name="quickstart",
        title="Quick Start Guide",
        summary="Get started with chapgent quickly",
        content="""\
Welcome to Chapgent! Here's how to get started:

1. SET UP YOUR API KEY
   export ANTHROPIC_API_KEY=your-api-key-here

   Or add to config:
   chapgent config set llm.api_key your-key

2. START CHATTING
   chapgent chat

3. ASK THE AGENT TO HELP
   Examples:
   - "Read the main.py file and explain what it does"
   - "Find all TODO comments in the codebase"
   - "Create a new Python file called utils.py"
   - "Run the tests and fix any failures"
   - "Initialize a new git repository"

4. APPROVE TOOL USAGE
   - LOW risk tools run automatically
   - MEDIUM/HIGH risk tools ask for permission
   - Press 'y' to approve, anything else to deny

5. SAVE YOUR SESSION
   Press Ctrl+S to save your conversation

6. EXPLORE MORE
   chapgent --help          See all commands
   chapgent help tools      Learn about available tools
   chapgent help shortcuts  See keyboard shortcuts

TIPS
  - Use Ctrl+Shift+P to open the command palette
  - Use Ctrl+B to toggle the session sidebar
  - Use Ctrl+P to toggle permission override mode
""",
    ),
    "troubleshooting": HelpTopic(
        name="troubleshooting",
        title="Troubleshooting",
        summary="Common issues and solutions",
        content="""\
COMMON ISSUES

"No API key configured"
  Solution: Set your API key
    export ANTHROPIC_API_KEY=your-key
    # or
    chapgent config set llm.api_key your-key

"Model not found"
  Solution: Use a valid model name
    chapgent config set llm.model claude-sonnet-4-20250514

"Rate limit exceeded"
  Solution: Wait a few seconds and try again

"Network error"
  Solution: Check your internet connection

"Permission denied"
  Solution: Check file permissions with ls -la

"Not a git repository"
  Solution: Initialize git with: git init

"Session not found"
  Solution: List sessions with: chapgent sessions

TUI DISPLAY ISSUES
  Try a different terminal emulator or theme:
    chapgent config set tui.theme textual-dark

LOGGING
  Check logs for detailed error information:
    chapgent logs           # Show log file path
    tail -f ~/.local/share/chapgent/logs/chapgent.log

REPORT A BUG
  Create a log report:
    chapgent report -o bug-report.tar.gz

  Then open an issue at:
    https://github.com/davewil/chapgent/issues

RESET CONFIGURATION
  If config is corrupted:
    chapgent config init --force
""",
    ),
}


def get_help_topic(topic_name: str) -> HelpTopic | None:
    """Get a help topic by name.

    Args:
        topic_name: The topic name (case-insensitive).

    Returns:
        The HelpTopic, or None if not found.
    """
    return HELP_TOPICS.get(topic_name.lower())


def list_help_topics() -> list[tuple[str, str]]:
    """List all available help topics.

    Returns:
        A list of (name, summary) tuples for all topics.
    """
    return [(topic.name, topic.summary) for topic in HELP_TOPICS.values()]


def search_help(query: str) -> list[HelpTopic]:
    """Search help topics for a query.

    Args:
        query: Search query (case-insensitive).

    Returns:
        List of matching HelpTopics.
    """
    query_lower = query.lower()
    results = []

    for topic in HELP_TOPICS.values():
        # Search in title, summary, and content
        if (
            query_lower in topic.title.lower()
            or query_lower in topic.summary.lower()
            or query_lower in topic.content.lower()
        ):
            results.append(topic)

    return results


def format_help_topic(topic: HelpTopic, width: int = 80) -> str:
    """Format a help topic for display.

    Args:
        topic: The HelpTopic to format.
        width: Maximum line width for the output.

    Returns:
        Formatted string for display.
    """
    lines = [
        "=" * width,
        topic.title.center(width),
        "=" * width,
        "",
        topic.content,
        "",
        "-" * width,
        f"Topic: {topic.name}",
    ]
    return "\n".join(lines)


def get_topic_names() -> list[str]:
    """Get a sorted list of all topic names.

    Returns:
        Sorted list of topic names.
    """
    return sorted(HELP_TOPICS.keys())
