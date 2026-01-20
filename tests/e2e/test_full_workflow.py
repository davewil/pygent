"""End-to-end tests for complete workflows (Section 6.1 of Phase 4).

These tests verify complete multi-step workflows that combine
multiple tools working together.
"""

import json
import string
import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chapgent.session.models import Message, Session, ToolInvocation
from chapgent.session.storage import SessionStorage
from chapgent.tools.filesystem import create_file, edit_file, read_file
from chapgent.tools.git import (
    git_add,
    git_checkout,
    git_commit,
    git_diff,
    git_log,
    git_status,
)
from chapgent.tools.search import find_definition, find_files, grep_search

# =============================================================================
# Section 6.1: E2E Testing - Complete Workflows
# =============================================================================


class TestCreateEditCommitFlow:
    """Test complete workflow: create file, edit, git commit."""

    @pytest.mark.asyncio
    async def test_create_file_workflow(self, tmp_path):
        """Test creating a new file and verifying content."""
        # Step 1: Create a new Python file
        file_path = tmp_path / "hello.py"
        content = '''def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}!"
'''
        await create_file(str(file_path), content)

        # Step 2: Verify file was created
        assert file_path.exists()

        # Step 3: Read back and verify content
        result = await read_file(str(file_path))
        assert "def greet(name: str)" in result
        assert 'return f"Hello, {name}!"' in result

    @pytest.mark.asyncio
    async def test_edit_file_workflow(self, tmp_path):
        """Test editing an existing file."""
        # Step 1: Create initial file
        file_path = tmp_path / "module.py"
        initial_content = """def calculate(x, y):
    return x + y
"""
        file_path.write_text(initial_content)

        # Step 2: Edit to add type hints
        await edit_file(str(file_path), "def calculate(x, y):", "def calculate(x: int, y: int) -> int:")

        # Step 3: Verify edit was applied
        result = await read_file(str(file_path))
        assert "def calculate(x: int, y: int) -> int:" in result

    @pytest.mark.asyncio
    async def test_full_create_edit_git_workflow(self, tmp_path):
        """Test complete workflow: create, edit, stage, and commit."""
        # Initialize a git repository
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        # Step 1: Create a new file
        file_path = tmp_path / "app.py"
        content = """def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
"""
        await create_file(str(file_path), content)

        # Step 2: Check git status - should show untracked file
        status = await git_status(cwd=str(tmp_path))
        assert "app.py" in status
        assert "Untracked files" in status or "untracked" in status.lower()

        # Step 3: Stage the file
        await git_add(["app.py"], cwd=str(tmp_path))

        # Step 4: Commit the file
        await git_commit("Add initial app.py", cwd=str(tmp_path))

        # Step 5: Verify commit in log
        log = await git_log(count=1, cwd=str(tmp_path))
        assert "Add initial app.py" in log

        # Step 6: Edit the file
        await edit_file(str(file_path), 'print("Hello, World!")', 'print("Hello, Chapgent!")')

        # Step 7: Check diff
        diff = await git_diff(cwd=str(tmp_path))
        assert "Hello, Chapgent!" in diff

        # Step 8: Stage and commit the change
        await git_add(["app.py"], cwd=str(tmp_path))
        await git_commit("Update greeting message", cwd=str(tmp_path))

        # Step 9: Verify both commits in log
        log = await git_log(count=2, cwd=str(tmp_path))
        assert "Add initial app.py" in log
        assert "Update greeting message" in log

    @pytest.mark.asyncio
    async def test_multiple_file_workflow(self, tmp_path):
        """Test creating and editing multiple related files."""
        # Create project structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Step 1: Create main module
        main_file = src_dir / "main.py"
        await create_file(
            str(main_file),
            """from .utils import helper

def run():
    helper()
""",
        )

        # Step 2: Create utils module
        utils_file = src_dir / "utils.py"
        await create_file(
            str(utils_file),
            """def helper():
    print("Helper function")
""",
        )

        # Step 3: Create __init__.py
        init_file = src_dir / "__init__.py"
        await create_file(str(init_file), "")

        # Step 4: Verify all files exist
        assert main_file.exists()
        assert utils_file.exists()
        assert init_file.exists()

        # Step 5: Edit utils to add return value
        await edit_file(str(utils_file), 'print("Helper function")', 'return "Helper result"')

        # Step 6: Verify edit
        result = await read_file(str(utils_file))
        assert 'return "Helper result"' in result


class TestSearchAndRefactorFlow:
    """Test searching code and performing edits."""

    @pytest.mark.asyncio
    async def test_find_and_replace_pattern(self, tmp_path):
        """Test finding code patterns and replacing them."""
        # Step 1: Create files with a deprecated pattern
        file1 = tmp_path / "module1.py"
        file2 = tmp_path / "module2.py"

        file1.write_text("""def process():
    old_function()
    return True
""")
        file2.write_text("""def handle():
    old_function()
    old_function()
""")

        # Step 2: Search for the deprecated function
        results_json = await grep_search("old_function", str(tmp_path))
        results_data = json.loads(results_json)
        results_list = results_data.get("results", [])

        # Should find occurrences in both files
        files_with_matches = {r["file"] for r in results_list}
        assert len(files_with_matches) == 2

        # Step 3: Edit file1 to replace single occurrence
        await edit_file(str(file1), "old_function()", "new_function()")

        # Step 4: Read file2 content, do multiple replacements manually
        # Since edit_file replaces only first match
        content2 = await read_file(str(file2))
        content2_updated = content2.replace("old_function()", "new_function()")
        (file2).write_text(content2_updated)

        # Step 5: Verify changes
        content1 = await read_file(str(file1))
        content2_final = await read_file(str(file2))

        assert "new_function()" in content1
        assert "old_function()" not in content1
        assert "new_function()" in content2_final
        assert content2_final.count("new_function()") == 2

    @pytest.mark.asyncio
    async def test_find_definition_and_edit(self, tmp_path):
        """Test finding a function definition and editing it."""
        # Step 1: Create a Python file with functions
        file_path = tmp_path / "calculator.py"
        file_path.write_text("""def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
""")

        # Step 2: Find the multiply function definition
        results_json = await find_definition("multiply", str(file_path))
        results_data = json.loads(results_json)
        # find_definition returns "definitions" key
        definitions_list = results_data.get("definitions", [])

        assert len(definitions_list) > 0
        # Check that we found the multiply definition
        found_multiply = False
        for r in definitions_list:
            context = r.get("context", "")
            if "multiply" in context:
                found_multiply = True
                break
        assert found_multiply, f"Expected to find 'multiply' in definitions: {definitions_list}"

        # Step 3: Edit the multiply function to add type hints
        await edit_file(str(file_path), "def multiply(a, b):", "def multiply(a: int, b: int) -> int:")

        # Step 4: Verify the edit
        content = await read_file(str(file_path))
        assert "def multiply(a: int, b: int) -> int:" in content

    @pytest.mark.asyncio
    async def test_find_files_and_process(self, tmp_path):
        """Test finding files by pattern and processing them."""
        # Step 1: Create test files
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        (test_dir / "test_one.py").write_text("# Test file 1")
        (test_dir / "test_two.py").write_text("# Test file 2")
        (tmp_path / "main.py").write_text("# Main file")

        # Step 2: Find all test files (need ** to search recursively)
        results_json = await find_files("**/test_*.py", str(tmp_path))
        results_data = json.loads(results_json)
        files_list = results_data.get("files", [])

        # Should find exactly 2 test files
        assert len(files_list) == 2
        assert any("test_one.py" in p for p in files_list)
        assert any("test_two.py" in p for p in files_list)

        # Step 3: Find all Python files
        all_py_json = await find_files("**/*.py", str(tmp_path))
        all_py_data = json.loads(all_py_json)
        all_files = all_py_data.get("files", [])

        # Should find all 3 Python files
        assert len(all_files) == 3

    @pytest.mark.asyncio
    async def test_search_and_bulk_edit(self, tmp_path):
        """Test searching across files and making consistent edits."""
        # Create a mini codebase with consistent naming
        (tmp_path / "model.py").write_text("""class UserModel:
    pass

class OrderModel:
    pass
""")

        (tmp_path / "views.py").write_text("""from model import UserModel, OrderModel

def get_user():
    return UserModel()
""")

        # Search for UserModel usage
        results_json = await grep_search("UserModel", str(tmp_path))
        results_data = json.loads(results_json)
        results_list = results_data.get("results", [])

        # Should find references
        assert len(results_list) > 0

        # Rename UserModel to User in model.py
        await edit_file(str(tmp_path / "model.py"), "UserModel", "User")

        # Re-read to verify first edit, then continue
        model_after_first = await read_file(str(tmp_path / "model.py"))
        assert "class User:" in model_after_first

        # For views.py, read content and do bulk replacement
        # (since edit_file only replaces first occurrence)
        views_content = await read_file(str(tmp_path / "views.py"))
        views_updated = views_content.replace("UserModel", "User")
        (tmp_path / "views.py").write_text(views_updated)

        # Verify changes
        model_content = await read_file(str(tmp_path / "model.py"))
        views_content_final = await read_file(str(tmp_path / "views.py"))

        assert "class User:" in model_content
        assert "UserModel" not in model_content
        assert "from model import User" in views_content_final
        assert "User()" in views_content_final


class TestSessionPersistence:
    """Test saving and resuming sessions."""

    @pytest.mark.asyncio
    async def test_save_and_load_session(self, tmp_path):
        """Test basic session save and load."""
        storage = SessionStorage(storage_dir=tmp_path)
        session_id = str(uuid.uuid4())

        # Step 1: Create a session with messages
        session = Session(
            id=session_id,
            messages=[
                Message(role="user", content="Create a function to add numbers"),
                Message(
                    role="assistant", content="Here's a function:\n```python\ndef add(a, b):\n    return a + b\n```"
                ),
            ],
            tool_history=[
                ToolInvocation(
                    tool_name="create_file",
                    arguments={"path": "math.py", "content": "def add(a, b):\n    return a + b\n"},
                    result="File created successfully",
                ),
            ],
            working_directory="/tmp/project",
        )

        # Step 2: Save the session
        await storage.save(session)

        # Step 3: Verify file was created
        session_file = tmp_path / f"{session_id}.json"
        assert session_file.exists()

        # Step 4: Load the session
        loaded = await storage.load(session_id)
        assert loaded is not None

        # Step 5: Verify all data is intact
        assert loaded.id == session_id
        assert len(loaded.messages) == 2
        assert loaded.messages[0].role == "user"
        assert loaded.messages[1].role == "assistant"
        assert len(loaded.tool_history) == 1
        assert loaded.tool_history[0].tool_name == "create_file"
        assert loaded.working_directory == "/tmp/project"

    @pytest.mark.asyncio
    async def test_session_with_complex_messages(self, tmp_path):
        """Test session with complex message content (lists, tool blocks)."""
        from chapgent.session.models import TextBlock, ToolResultBlock, ToolUseBlock

        storage = SessionStorage(storage_dir=tmp_path)
        session_id = str(uuid.uuid4())

        # Create session with complex content
        session = Session(
            id=session_id,
            messages=[
                Message(role="user", content="Read the config file"),
                Message(
                    role="assistant",
                    content=[
                        TextBlock(text="I'll read the config file for you."),
                        ToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "config.toml"},
                        ),
                    ],
                ),
                Message(
                    role="user",
                    content=[
                        ToolResultBlock(
                            tool_use_id="tool_1",
                            content="[settings]\ndebug = true",
                        ),
                    ],
                ),
                Message(
                    role="assistant",
                    content="The config file contains debug = true setting.",
                ),
            ],
        )

        # Save and reload
        await storage.save(session)
        loaded = await storage.load(session_id)

        assert loaded is not None
        assert len(loaded.messages) == 4

        # Verify complex content was preserved
        assistant_msg = loaded.messages[1]
        assert isinstance(assistant_msg.content, list)
        assert len(assistant_msg.content) == 2

    @pytest.mark.asyncio
    async def test_list_and_delete_sessions(self, tmp_path):
        """Test listing and deleting sessions."""
        storage = SessionStorage(storage_dir=tmp_path)

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            sid = str(uuid.uuid4())
            session_ids.append(sid)
            session = Session(
                id=sid,
                messages=[Message(role="user", content=f"Session {i}")],
            )
            await storage.save(session)

        # List sessions
        summaries = await storage.list_sessions()
        assert len(summaries) == 3

        # Delete one session
        result = await storage.delete(session_ids[0])
        assert result is True

        # Verify it's gone
        summaries = await storage.list_sessions()
        assert len(summaries) == 2

        # Try to load deleted session
        loaded = await storage.load(session_ids[0])
        assert loaded is None

    @pytest.mark.asyncio
    async def test_resume_session_flow(self, tmp_path):
        """Test resuming a session and adding new messages."""
        storage = SessionStorage(storage_dir=tmp_path)
        session_id = str(uuid.uuid4())

        # Create and save initial session
        session = Session(
            id=session_id,
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi! How can I help?"),
            ],
        )
        await storage.save(session)

        # Simulate resuming: load the session
        resumed = await storage.load(session_id)
        assert resumed is not None

        # Add new messages (simulating continued conversation)
        resumed.messages.append(Message(role="user", content="Create a file"))
        resumed.messages.append(Message(role="assistant", content="I'll create that file."))

        # Save the updated session
        await storage.save(resumed)

        # Verify the session was updated
        final = await storage.load(session_id)
        assert final is not None
        assert len(final.messages) == 4


# =============================================================================
# Property-Based E2E Tests
# =============================================================================


class TestPropertyBasedE2E:
    """Property-based tests for E2E workflows."""

    @given(content=st.text(min_size=1, max_size=1000).filter(lambda x: x.strip() and "\r" not in x))
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_create_read_roundtrip(self, tmp_path, content):
        """Test that any valid content can be created and read back."""
        unique_dir = tmp_path / str(uuid.uuid4())
        unique_dir.mkdir()

        file_path = unique_dir / "test.txt"
        await create_file(str(file_path), content)

        result = await read_file(str(file_path))
        assert result == content

    @given(
        old=st.text(min_size=1, max_size=50, alphabet=string.ascii_letters + string.digits + " ").filter(
            lambda x: x.strip() and "\r" not in x
        ),
        new=st.text(min_size=1, max_size=50, alphabet=string.ascii_letters + string.digits + " ").filter(
            lambda x: "\r" not in x
        ),
    )
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_edit_replaces_correctly(self, tmp_path, old, new):
        """Test that edit correctly replaces text."""
        # Skip if old == new or if new contains old (would make assertion fail)
        if old == new or old in new:
            return

        unique_dir = tmp_path / str(uuid.uuid4())
        unique_dir.mkdir()

        file_path = unique_dir / "test.txt"
        initial = f"prefix {old} suffix"
        file_path.write_text(initial, encoding="utf-8")

        await edit_file(str(file_path), old, new)

        result = await read_file(str(file_path))
        assert new in result
        assert old not in result

    @given(
        messages=st.lists(
            st.text(min_size=1, max_size=100, alphabet=string.ascii_letters + string.digits + " .,!?").filter(
                lambda x: x.strip()
            ),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_session_preserves_messages(self, tmp_path, messages):
        """Test that session storage preserves all messages."""
        unique_dir = tmp_path / str(uuid.uuid4())
        unique_dir.mkdir()

        storage = SessionStorage(storage_dir=unique_dir)
        session_id = str(uuid.uuid4())

        # Create session with generated messages
        session = Session(
            id=session_id,
            messages=[
                Message(role="user" if i % 2 == 0 else "assistant", content=msg) for i, msg in enumerate(messages)
            ],
        )

        await storage.save(session)
        loaded = await storage.load(session_id)

        assert loaded is not None
        assert len(loaded.messages) == len(messages)
        for original, loaded_msg in zip(messages, loaded.messages, strict=False):
            assert loaded_msg.content == original


# =============================================================================
# Integration Smoke Tests
# =============================================================================


class TestIntegrationSmoke:
    """Quick smoke tests for overall system health."""

    @pytest.mark.asyncio
    async def test_tools_are_importable(self):
        """Verify all tool modules can be imported."""
        # This will fail fast if there are import errors
        from chapgent.tools.filesystem import read_file
        from chapgent.tools.git import git_status
        from chapgent.tools.search import grep_search
        from chapgent.tools.shell import shell
        from chapgent.tools.web import web_fetch

        assert callable(read_file)
        assert callable(git_status)
        assert callable(grep_search)
        assert callable(shell)
        assert callable(web_fetch)

    @pytest.mark.asyncio
    async def test_registry_has_all_tools(self):
        """Verify tool registry can be populated with all tools."""
        from chapgent.tools.base import ToolCategory
        from chapgent.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Import and register all tools
        from chapgent.tools.filesystem import (
            copy_file,
            create_file,
            delete_file,
            edit_file,
            list_files,
            move_file,
            read_file,
        )
        from chapgent.tools.git import (
            git_add,
            git_branch,
            git_commit,
            git_diff,
            git_log,
            git_pull,
            git_push,
            git_status,
        )
        from chapgent.tools.search import find_definition, find_files, grep_search
        from chapgent.tools.shell import shell

        tools = [
            read_file,
            list_files,
            edit_file,
            create_file,
            delete_file,
            move_file,
            copy_file,
            git_status,
            git_diff,
            git_log,
            git_branch,
            git_add,
            git_commit,
            git_checkout,
            git_push,
            git_pull,
            grep_search,
            find_files,
            find_definition,
            shell,
        ]

        for t in tools:
            registry.register(t)

        # Verify categories
        categories = registry.get_categories()
        assert ToolCategory.FILESYSTEM in categories
        assert ToolCategory.GIT in categories
        assert ToolCategory.SEARCH in categories
        assert ToolCategory.SHELL in categories

    @pytest.mark.asyncio
    async def test_config_system_works(self):
        """Verify config loading doesn't crash."""
        from chapgent.config.loader import load_config

        # Should load without errors (uses defaults if no config)
        settings = await load_config()
        assert settings is not None
        assert settings.llm is not None
        assert settings.tui is not None

    @pytest.mark.asyncio
    async def test_context_detection_works(self, tmp_path):
        """Verify project context detection works."""
        from chapgent.context.detection import detect_project_context

        # Create a minimal Python project
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"')
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")

        context = await detect_project_context(tmp_path)

        assert context is not None
        assert context.type.value == "python"
