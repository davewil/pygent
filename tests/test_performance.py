import time

import pytest
from pygent.tools.filesystem import edit_file, list_files, read_file
from pygent.tools.shell import shell


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
