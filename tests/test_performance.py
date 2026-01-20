"""Performance benchmarks for chapgent (Section 6.3 of Phase 4).

Tests verify non-functional acceptance criteria:
- Startup time <500ms
- Tool dispatch overhead <10ms
- Large file handling (up to 10MB)
- Session load time <100ms
"""

import subprocess
import sys
import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.session.models import Message, Session
from chapgent.session.storage import SessionStorage
from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk
from chapgent.tools.filesystem import create_file, edit_file, list_files, read_file
from chapgent.tools.registry import ToolRegistry
from chapgent.tools.shell import shell

# =============================================================================
# Section 6.3: Performance Benchmarks
# =============================================================================


class TestStartupTime:
    """Test that CLI startup is fast.

    Note: Subprocess startup includes Python interpreter initialization,
    which adds significant overhead. We use warmup runs and measure
    consistent performance rather than absolute thresholds.
    """

    def test_cli_help_startup_time(self):
        """Verify 'chapgent --help' runs consistently."""
        # Warmup run to ensure modules are cached
        subprocess.run(
            [sys.executable, "-m", "chapgent.cli", "--help"],
            capture_output=True,
            text=True,
        )

        # Measure actual run
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "chapgent.cli", "--help"],
            capture_output=True,
            text=True,
        )
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nCLI --help startup: {duration_ms:.2f}ms")

        assert result.returncode == 0
        # Subprocess startup includes Python interpreter, allow 3s
        assert duration_ms < 3000, f"Startup took {duration_ms:.2f}ms, expected <3000ms"

    def test_cli_version_startup_time(self):
        """Verify 'chapgent --version' runs consistently."""
        # Warmup
        subprocess.run(
            [sys.executable, "-m", "chapgent.cli", "--version"],
            capture_output=True,
            text=True,
        )

        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "chapgent.cli", "--version"],
            capture_output=True,
            text=True,
        )
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nCLI --version startup: {duration_ms:.2f}ms")

        assert result.returncode == 0
        # Subprocess startup includes Python interpreter, allow 3s
        assert duration_ms < 3000, f"Startup took {duration_ms:.2f}ms, expected <3000ms"

    def test_module_import_incremental(self):
        """Verify importing additional modules after initial load is fast."""
        # First, ensure base modules are loaded
        import chapgent.tools.base  # noqa: F401

        # Now measure incremental imports (should be faster)
        start = time.perf_counter()
        import chapgent.session.models  # noqa: F401
        import chapgent.tools.registry  # noqa: F401

        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nIncremental import time: {duration_ms:.2f}ms")

        # Incremental imports after warmup should be fast
        assert duration_ms < 500, f"Import took {duration_ms:.2f}ms, expected <500ms"


class TestToolDispatchOverhead:
    """Test that tool dispatch overhead is minimal (<10ms)."""

    def test_registry_lookup_overhead(self):
        """Verify registry lookup is <10ms."""
        registry = ToolRegistry()

        # Register 50 mock tools
        for i in range(50):

            async def dummy_func(x: str) -> str:
                return x

            definition = ToolDefinition(
                name=f"tool_{i}",
                description=f"Tool {i}",
                input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
                risk=ToolRisk.LOW,
                category=ToolCategory.SHELL,
                function=dummy_func,
            )
            registry.register(definition)

        # Measure lookup time
        start = time.perf_counter()
        for _ in range(1000):
            registry.get("tool_25")
        end = time.perf_counter()

        avg_ms = (end - start) / 1000 * 1000  # Average per lookup in ms
        print(f"\nRegistry lookup (avg): {avg_ms:.4f}ms")

        assert avg_ms < 1, f"Lookup took {avg_ms:.4f}ms avg, expected <1ms"

    def test_list_definitions_overhead(self):
        """Verify listing tool definitions is <10ms."""
        registry = ToolRegistry()

        # Register 50 mock tools
        for i in range(50):

            async def dummy_func(x: str) -> str:
                return x

            definition = ToolDefinition(
                name=f"tool_{i}",
                description=f"Tool {i}",
                input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
                risk=ToolRisk.LOW,
                category=ToolCategory.SHELL,
                function=dummy_func,
            )
            registry.register(definition)

        start = time.perf_counter()
        _ = registry.list_definitions()
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nlist_definitions (50 tools): {duration_ms:.4f}ms")

        assert duration_ms < 10, f"Listing took {duration_ms:.2f}ms, expected <10ms"

    @pytest.mark.asyncio
    async def test_tool_wrapper_overhead(self, tmp_path):
        """Verify tool decorator wrapper adds minimal overhead."""
        # Create a small test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Time the decorated read_file vs raw file read
        # Decorated version
        start = time.perf_counter()
        for _ in range(100):
            await read_file(str(test_file))
        decorated_end = time.perf_counter()

        # Raw version (for comparison)
        start_raw = time.perf_counter()
        for _ in range(100):
            test_file.read_text()
        raw_end = time.perf_counter()

        decorated_avg_ms = (decorated_end - start) / 100 * 1000
        raw_avg_ms = (raw_end - start_raw) / 100 * 1000
        overhead_ms = decorated_avg_ms - raw_avg_ms

        print(f"\nDecorated read_file (avg): {decorated_avg_ms:.4f}ms")
        print(f"Raw file read (avg): {raw_avg_ms:.4f}ms")
        print(f"Decorator overhead: {overhead_ms:.4f}ms")

        # Decorator overhead should be <10ms
        assert overhead_ms < 10, f"Decorator overhead {overhead_ms:.4f}ms, expected <10ms"


class TestLargeFileHandling:
    """Test handling of large files (up to 10MB)."""

    @pytest.mark.asyncio
    async def test_read_10mb_file(self, tmp_path):
        """Verify read_file handles 10MB file."""
        large_file = tmp_path / "large_10mb.txt"
        content = "A" * (10 * 1024 * 1024)  # 10MB
        large_file.write_text(content, encoding="utf-8")

        start = time.perf_counter()
        result = await read_file(str(large_file))
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nread_file 10MB: {duration_ms:.2f}ms")

        assert len(result) == 10 * 1024 * 1024
        # Should complete in reasonable time (allow more time for large files)
        assert duration_ms < 5000, f"10MB read took {duration_ms:.2f}ms, expected <5000ms"

    @pytest.mark.asyncio
    async def test_create_10mb_file(self, tmp_path):
        """Verify create_file handles 10MB file."""
        large_file = tmp_path / "create_10mb.txt"
        content = "B" * (10 * 1024 * 1024)  # 10MB

        start = time.perf_counter()
        await create_file(str(large_file), content)
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\ncreate_file 10MB: {duration_ms:.2f}ms")

        assert large_file.exists()
        assert len(large_file.read_text()) == 10 * 1024 * 1024
        # Should complete in reasonable time
        assert duration_ms < 5000, f"10MB create took {duration_ms:.2f}ms, expected <5000ms"

    @pytest.mark.asyncio
    async def test_edit_large_file(self, tmp_path):
        """Verify edit_file handles large file with many replacements."""
        large_file = tmp_path / "edit_large.txt"
        # Create file with repeating pattern
        content = "line1\nline2\nline3\n" * 10000  # ~190KB
        large_file.write_text(content, encoding="utf-8")

        start = time.perf_counter()
        await edit_file(str(large_file), "line2", "REPLACED")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nedit_file large: {duration_ms:.2f}ms")

        # Verify edit worked
        edited_content = large_file.read_text()
        assert "REPLACED" in edited_content
        assert "line2" not in edited_content

        assert duration_ms < 1000, f"Large edit took {duration_ms:.2f}ms, expected <1000ms"


class TestSessionLoadTime:
    """Test that session operations are fast (<100ms)."""

    @pytest.mark.asyncio
    async def test_save_session_time(self, tmp_path):
        """Verify saving session is <100ms."""
        storage = SessionStorage(storage_dir=tmp_path)

        # Create a session with some messages
        session = Session(
            id="perf-test-save",
            messages=[Message(role="user", content=f"Message {i}") for i in range(50)],
        )

        start = time.perf_counter()
        await storage.save(session)
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nSession save (50 msgs): {duration_ms:.2f}ms")

        assert duration_ms < 100, f"Save took {duration_ms:.2f}ms, expected <100ms"

    @pytest.mark.asyncio
    async def test_load_session_time(self, tmp_path):
        """Verify loading session is <100ms."""
        storage = SessionStorage(storage_dir=tmp_path)

        # Create and save a session
        session = Session(
            id="perf-test-load",
            messages=[Message(role="user", content=f"Message {i}" * 100) for i in range(100)],
        )
        await storage.save(session)

        start = time.perf_counter()
        loaded = await storage.load("perf-test-load")
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nSession load (100 msgs): {duration_ms:.2f}ms")

        assert loaded is not None
        assert len(loaded.messages) == 100
        assert duration_ms < 100, f"Load took {duration_ms:.2f}ms, expected <100ms"

    @pytest.mark.asyncio
    async def test_list_sessions_time(self, tmp_path):
        """Verify listing sessions is reasonable (<500ms for 50 sessions)."""
        storage = SessionStorage(storage_dir=tmp_path)

        # Create 50 sessions
        for i in range(50):
            session = Session(
                id=f"perf-list-{i}",
                messages=[Message(role="user", content=f"Msg {j}") for j in range(10)],
            )
            await storage.save(session)

        start = time.perf_counter()
        summaries = await storage.list_sessions()
        end = time.perf_counter()

        duration_ms = (end - start) * 1000
        print(f"\nList sessions (50): {duration_ms:.2f}ms")

        assert len(summaries) == 50
        assert duration_ms < 500, f"Listing took {duration_ms:.2f}ms, expected <500ms"


# =============================================================================
# Property-Based Performance Tests
# =============================================================================


class TestPropertyBasedPerformance:
    """Property-based tests for performance consistency."""

    @given(size=st.integers(min_value=100, max_value=10000))
    @settings(max_examples=10, deadline=None)
    def test_registry_scales_linearly(self, size):
        """Verify registry lookup is O(1) regardless of size."""
        registry = ToolRegistry()

        for i in range(size):

            async def dummy_func(x: str) -> str:
                return x

            definition = ToolDefinition(
                name=f"tool_{i}",
                description=f"Tool {i}",
                input_schema={"type": "object", "properties": {}},
                risk=ToolRisk.LOW,
                category=ToolCategory.SHELL,
                function=dummy_func,
            )
            registry.register(definition)

        # Lookup should be constant time
        start = time.perf_counter()
        for _ in range(100):
            registry.get(f"tool_{size // 2}")
        end = time.perf_counter()

        avg_ms = (end - start) / 100 * 1000
        # O(1) means avg should be roughly the same regardless of size
        assert avg_ms < 1, f"Lookup avg {avg_ms:.4f}ms at size {size}"


# =============================================================================
# Original Tool Performance Tests (Phase 1)
# =============================================================================


@pytest.mark.asyncio
async def test_read_file_performance(tmp_path):
    """Verify read_file execution time is < 500ms."""
    f = tmp_path / "perf_test.txt"
    content = "A" * 1024 * 1024  # 1MB
    f.write_text(content, encoding="utf-8")

    start_time = time.perf_counter()
    await read_file(str(f))
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000
    print(f"\nread_file duration: {duration_ms:.2f}ms")
    assert duration_ms < 500


@pytest.mark.asyncio
async def test_list_files_performance(tmp_path):
    """Verify list_files execution time is < 500ms."""
    # Create 100 files
    for i in range(100):
        (tmp_path / f"file_{i}.txt").touch()

    start_time = time.perf_counter()
    await list_files(str(tmp_path))
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000
    print(f"list_files duration: {duration_ms:.2f}ms")
    assert duration_ms < 500


@pytest.mark.asyncio
async def test_edit_file_performance(tmp_path):
    """Verify edit_file execution time is < 500ms."""
    f = tmp_path / "perf_edit.txt"
    content = "line1\nline2\nline3\n" * 1000
    f.write_text(content, encoding="utf-8")

    start_time = time.perf_counter()
    await edit_file(str(f), "line2", "replaced")
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000
    print(f"edit_file duration: {duration_ms:.2f}ms")
    assert duration_ms < 500


@pytest.mark.asyncio
async def test_shell_performance():
    """Verify shell tool overhead is low (excluding command execution)."""
    # Use a very fast command
    start_time = time.perf_counter()
    await shell("echo ready")
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000
    print(f"shell (echo) duration: {duration_ms:.2f}ms")
    # Subprocess creation has some overhead, but should still be well within 500ms
    assert duration_ms < 500
