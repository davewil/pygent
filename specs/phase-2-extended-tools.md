# Phase 2: Extended Tools

## Objective

Expand pygent's tool suite with git operations, web fetching, code search, and additional file operations (create, delete). This phase transforms pygent from a basic assistant into a comprehensive development tool.

## Prerequisites

- Phase 1 MVP completed and stable
- Tool registration system working
- Permission system functional
- TUI displaying tool activity

---

## Deliverables

### 1. Git Tools (`tools/git.py`)

#### 1.1 git_status
```python
@tool(
    name="git_status",
    description="Show the working tree status (modified, staged, untracked files)",
    risk=ToolRisk.LOW,
)
async def git_status() -> str:
    """Get git repository status.

    Returns:
        Formatted status output showing:
        - Staged changes
        - Unstaged changes
        - Untracked files
        - Current branch
    """
```

#### 1.2 git_diff
```python
@tool(
    name="git_diff",
    description="Show changes between commits, commit and working tree, etc.",
    risk=ToolRisk.LOW,
)
async def git_diff(
    path: str | None = None,
    staged: bool = False,
    commit: str | None = None,
) -> str:
    """Show git diff.

    Args:
        path: Limit diff to specific file/directory.
        staged: If True, show staged changes (--cached).
        commit: Compare against specific commit.

    Returns:
        Unified diff output.
    """
```

#### 1.3 git_log
```python
@tool(
    name="git_log",
    description="Show commit history",
    risk=ToolRisk.LOW,
)
async def git_log(
    count: int = 10,
    oneline: bool = True,
    path: str | None = None,
) -> str:
    """Show git commit history.

    Args:
        count: Number of commits to show.
        oneline: If True, show compact format.
        path: Limit to commits affecting path.

    Returns:
        Formatted commit history.
    """
```

#### 1.4 git_add
```python
@tool(
    name="git_add",
    description="Stage files for commit",
    risk=ToolRisk.MEDIUM,
)
async def git_add(paths: list[str]) -> str:
    """Stage files for commit.

    Args:
        paths: List of file paths to stage.

    Returns:
        Confirmation message.
    """
```

#### 1.5 git_commit
```python
@tool(
    name="git_commit",
    description="Create a new commit with staged changes",
    risk=ToolRisk.MEDIUM,
)
async def git_commit(message: str) -> str:
    """Create a commit.

    Args:
        message: Commit message.

    Returns:
        Commit hash and summary.
    """
```

#### 1.6 git_checkout
```python
@tool(
    name="git_checkout",
    description="Switch branches or restore files",
    risk=ToolRisk.MEDIUM,
)
async def git_checkout(
    branch: str | None = None,
    create: bool = False,
    paths: list[str] | None = None,
) -> str:
    """Checkout branch or restore files.

    Args:
        branch: Branch name to checkout.
        create: If True, create new branch (-b).
        paths: Restore specific files from HEAD.

    Returns:
        Status message.
    """
```

#### 1.7 git_push
```python
@tool(
    name="git_push",
    description="Push commits to remote repository",
    risk=ToolRisk.HIGH,
)
async def git_push(
    remote: str = "origin",
    branch: str | None = None,
    set_upstream: bool = False,
) -> str:
    """Push to remote.

    Args:
        remote: Remote name (default: origin).
        branch: Branch to push (default: current).
        set_upstream: If True, set upstream (-u).

    Returns:
        Push result output.
    """
```

#### 1.8 git_pull
```python
@tool(
    name="git_pull",
    description="Fetch and integrate changes from remote",
    risk=ToolRisk.MEDIUM,
)
async def git_pull(
    remote: str = "origin",
    branch: str | None = None,
) -> str:
    """Pull from remote.

    Args:
        remote: Remote name.
        branch: Branch to pull.

    Returns:
        Pull result output.
    """
```

#### 1.9 git_branch
```python
@tool(
    name="git_branch",
    description="List, create, or delete branches",
    risk=ToolRisk.LOW,
)
async def git_branch(
    name: str | None = None,
    delete: bool = False,
    list_all: bool = False,
) -> str:
    """Manage branches.

    Args:
        name: Branch name (for create/delete).
        delete: If True, delete the branch.
        list_all: If True, list remote branches too.

    Returns:
        Branch list or operation result.
    """
```

---

### 2. Web Tools (`tools/web.py`)

#### 2.1 web_fetch
```python
@tool(
    name="web_fetch",
    description="Fetch content from a URL",
    risk=ToolRisk.HIGH,
)
async def web_fetch(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> str:
    """Fetch URL content.

    Args:
        url: URL to fetch (must be HTTPS).
        method: HTTP method (GET, POST, etc.).
        headers: Optional request headers.
        timeout: Request timeout in seconds.

    Returns:
        Response body (truncated if too large).
        For HTML, attempts to extract main content.
    """
```

**Implementation Notes:**
- Force HTTPS (upgrade HTTP automatically)
- Limit response size (1MB default)
- Convert HTML to markdown for readability
- Include status code and headers in response
- Handle common content types (JSON, HTML, plain text)

#### 2.2 web_search (Optional/Future)
```python
@tool(
    name="web_search",
    description="Search the web using a search engine",
    risk=ToolRisk.HIGH,
)
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web.

    Args:
        query: Search query.
        num_results: Number of results to return.

    Returns:
        JSON array of search results with title, URL, snippet.

    Note:
        Requires search API configuration (e.g., SerpAPI, Brave).
    """
```

---

### 3. Code Search Tools (`tools/search.py`)

#### 3.1 grep_search
```python
@tool(
    name="grep_search",
    description="Search for patterns in files using regex",
    risk=ToolRisk.LOW,
)
async def grep_search(
    pattern: str,
    path: str = ".",
    file_pattern: str | None = None,
    ignore_case: bool = False,
    context_lines: int = 0,
    max_results: int = 100,
) -> str:
    """Search file contents with regex.

    Args:
        pattern: Regex pattern to search for.
        path: Directory to search in.
        file_pattern: Glob pattern to filter files (e.g., "*.py").
        ignore_case: Case-insensitive search.
        context_lines: Lines of context around matches.
        max_results: Maximum number of matches to return.

    Returns:
        Formatted search results with file:line:content.
    """
```

**Implementation:**
- Use `asyncio.subprocess` to call `rg` (ripgrep) if available
- Fall back to pure Python implementation
- Respect `.gitignore` by default
- Return structured results: file path, line number, match, context

#### 3.2 find_files
```python
@tool(
    name="find_files",
    description="Find files matching a glob pattern",
    risk=ToolRisk.LOW,
)
async def find_files(
    pattern: str,
    path: str = ".",
    max_depth: int | None = None,
    file_type: str | None = None,
) -> str:
    """Find files by name pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "test_*.py").
        path: Base directory to search.
        max_depth: Maximum directory depth.
        file_type: Filter by type ("file", "directory").

    Returns:
        JSON array of matching paths.
    """
```

#### 3.3 find_definition
```python
@tool(
    name="find_definition",
    description="Find where a symbol (function, class, variable) is defined",
    risk=ToolRisk.LOW,
)
async def find_definition(
    symbol: str,
    language: str | None = None,
    path: str = ".",
) -> str:
    """Find symbol definition.

    Args:
        symbol: Name of function, class, or variable.
        language: Programming language hint.
        path: Search directory.

    Returns:
        File path and line number of definition(s).
    """
```

**Implementation:**
- Use regex patterns for common languages
- Python: `def {symbol}`, `class {symbol}`, `{symbol} =`
- JavaScript/TypeScript: `function {symbol}`, `class {symbol}`, `const {symbol}`
- Consider Tree-sitter integration for accuracy (future)

---

### 4. Additional File Tools (`tools/filesystem.py`)

#### 4.1 create_file
```python
@tool(
    name="create_file",
    description="Create a new file with content",
    risk=ToolRisk.MEDIUM,
)
async def create_file(path: str, content: str) -> str:
    """Create a new file.

    Args:
        path: Path for the new file.
        content: Initial file content.

    Returns:
        Success message or error.

    Raises:
        FileExistsError: If file already exists.
    """
```

#### 4.2 delete_file
```python
@tool(
    name="delete_file",
    description="Delete a file",
    risk=ToolRisk.HIGH,
)
async def delete_file(path: str) -> str:
    """Delete a file.

    Args:
        path: Path to file to delete.

    Returns:
        Confirmation message.

    Note:
        Directories are not deleted (use shell for rmdir).
    """
```

#### 4.3 move_file
```python
@tool(
    name="move_file",
    description="Move or rename a file",
    risk=ToolRisk.MEDIUM,
)
async def move_file(source: str, destination: str) -> str:
    """Move or rename a file.

    Args:
        source: Current file path.
        destination: New file path.

    Returns:
        Confirmation message.
    """
```

#### 4.4 copy_file
```python
@tool(
    name="copy_file",
    description="Copy a file to a new location",
    risk=ToolRisk.MEDIUM,
)
async def copy_file(source: str, destination: str) -> str:
    """Copy a file.

    Args:
        source: Source file path.
        destination: Destination file path.

    Returns:
        Confirmation message.
    """
```

---

### 5. Tool Categories & Discovery

#### 5.1 Tool Categorization
```python
class ToolCategory(Enum):
    FILESYSTEM = "filesystem"
    GIT = "git"
    SEARCH = "search"
    WEB = "web"
    SHELL = "shell"

@tool(
    name="read_file",
    description="...",
    risk=ToolRisk.LOW,
    category=ToolCategory.FILESYSTEM,  # New field
)
```

#### 5.2 Tool Discovery Command
```python
@cli.command()
@click.option("--category", "-c", help="Filter by category")
def tools(category: str | None):
    """List all available tools."""
```

Output:
```
Filesystem Tools:
  read_file      Read file contents                    [LOW]
  list_files     List directory contents               [LOW]
  edit_file      Edit file via string replacement      [MEDIUM]
  create_file    Create a new file                     [MEDIUM]
  delete_file    Delete a file                         [HIGH]
  move_file      Move or rename a file                 [MEDIUM]
  copy_file      Copy a file                           [MEDIUM]

Git Tools:
  git_status     Show working tree status              [LOW]
  git_diff       Show changes                          [LOW]
  ...
```

---

### 6. TUI Enhancements

#### 6.1 Tool Panel Improvements
- Show tool category badges
- Color-code by risk level (green/yellow/red)
- Collapsible tool output for long results
- Filter tool history by category

#### 6.2 Permission Dialog Enhancements
- Show full tool details in permission prompt
- "Allow this tool for session" checkbox
- "Allow this category for session" option

---

### 7. Testing

#### 7.1 Git Tools Tests
```python
@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo)
    return repo

async def test_git_status_clean(git_repo):
    """Test git_status on clean repo."""

async def test_git_status_with_changes(git_repo):
    """Test git_status with modified files."""

async def test_git_add_and_commit(git_repo):
    """Test staging and committing files."""
```

#### 7.2 Web Tools Tests
```python
@pytest.fixture
def mock_httpx():
    """Mock httpx for web tool tests."""

async def test_web_fetch_json():
    """Test fetching JSON content."""

async def test_web_fetch_html_conversion():
    """Test HTML to markdown conversion."""

async def test_web_fetch_timeout():
    """Test request timeout handling."""
```

#### 7.3 Search Tools Tests
```python
async def test_grep_search_basic(tmp_path):
    """Test basic pattern search."""

async def test_grep_search_with_context(tmp_path):
    """Test search with context lines."""

async def test_find_definition_python(tmp_path):
    """Test finding Python function definitions."""
```

---

## Acceptance Criteria

### Functional
- [ ] All git tools work correctly in valid git repositories
- [ ] Git tools fail gracefully outside of git repos
- [ ] Web fetch handles various content types
- [ ] Web fetch respects size limits
- [ ] Grep search finds patterns accurately
- [ ] File operations (create, delete, move, copy) work correctly
- [ ] Tools categorized and discoverable

### Non-Functional
- [ ] Git operations complete in <1s for typical repos
- [ ] Search operations use ripgrep when available
- [ ] Web fetch has configurable timeout
- [ ] All new tools have comprehensive tests

---

## Implementation Order

1. **Search Tools** (3-4 days)
   - grep_search with ripgrep backend
   - find_files with glob patterns
   - find_definition for common languages

2. **Additional File Tools** (2 days)
   - create_file, delete_file
   - move_file, copy_file

3. **Git Tools** (4-5 days)
   - Read-only tools first (status, diff, log, branch)
   - Write tools (add, commit, checkout)
   - Remote tools (push, pull)

4. **Web Tools** (3 days)
   - web_fetch with content handling
   - HTML to markdown conversion
   - Optional: web_search integration

5. **TUI Enhancements** (2 days)
   - Tool panel improvements
   - Permission dialog enhancements

6. **Testing & Polish** (2-3 days)
   - Comprehensive test coverage
   - Documentation updates

---

*Document Version: 1.0*
*Created: 2026-01-16*
