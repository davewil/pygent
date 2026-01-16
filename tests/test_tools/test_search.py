"""Tests for search tools (grep_search)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pygent.tools.search import (
    _grep_with_python,
    _grep_with_ripgrep,
    _is_ripgrep_available,
    grep_search,
)

# Unit tests for grep_search


@pytest.mark.asyncio
async def test_grep_search_basic_match(tmp_path):
    """Test basic pattern matching."""
    # Create test files
    (tmp_path / "test.py").write_text("def hello():\n    print('hello')\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("def world():\n    pass\n", encoding="utf-8")

    result = await grep_search("hello", str(tmp_path))
    data = json.loads(result)

    assert data["count"] >= 1
    # Should find "hello" in test.py
    files = [r["file"] for r in data["results"]]
    assert any("test.py" in f for f in files)


@pytest.mark.asyncio
async def test_grep_search_no_matches(tmp_path):
    """Test search with no matches."""
    (tmp_path / "test.txt").write_text("nothing special here", encoding="utf-8")

    result = await grep_search("xyz123", str(tmp_path))
    data = json.loads(result)

    assert data.get("message") == "No matches found"
    assert data["results"] == []


@pytest.mark.asyncio
async def test_grep_search_file_pattern(tmp_path):
    """Test filtering by file pattern."""
    (tmp_path / "code.py").write_text("def func(): pass", encoding="utf-8")
    (tmp_path / "code.txt").write_text("def func(): pass", encoding="utf-8")

    result = await grep_search("def", str(tmp_path), file_pattern="*.py")
    data = json.loads(result)

    # Should only find match in .py file
    for r in data["results"]:
        assert r["file"].endswith(".py")


@pytest.mark.asyncio
async def test_grep_search_ignore_case(tmp_path):
    """Test case-insensitive search."""
    (tmp_path / "test.txt").write_text("Hello World\nhello world", encoding="utf-8")

    result = await grep_search("HELLO", str(tmp_path), ignore_case=True)
    data = json.loads(result)

    # Should find both lines
    assert data["count"] == 2


@pytest.mark.asyncio
async def test_grep_search_case_sensitive(tmp_path):
    """Test case-sensitive search (default)."""
    (tmp_path / "test.txt").write_text("Hello World\nhello world", encoding="utf-8")

    result = await grep_search("Hello", str(tmp_path), ignore_case=False)
    data = json.loads(result)

    # Should find only one line
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_grep_search_max_results(tmp_path):
    """Test max_results limit."""
    content = "\n".join([f"match line {i}" for i in range(20)])
    (tmp_path / "test.txt").write_text(content, encoding="utf-8")

    result = await grep_search("match", str(tmp_path), max_results=5)
    data = json.loads(result)

    assert data["count"] == 5


@pytest.mark.asyncio
async def test_grep_search_single_file(tmp_path):
    """Test searching a single file directly."""
    test_file = tmp_path / "single.py"
    test_file.write_text("line one\nline two\nline three", encoding="utf-8")

    result = await grep_search("two", str(test_file))
    data = json.loads(result)

    assert data["count"] == 1
    assert data["results"][0]["line"] == 2


@pytest.mark.asyncio
async def test_grep_search_regex_pattern(tmp_path):
    """Test regex pattern matching."""
    (tmp_path / "test.py").write_text("def foo_bar():\ndef baz_qux():\n", encoding="utf-8")

    result = await grep_search(r"def \w+_\w+", str(tmp_path))
    data = json.loads(result)

    assert data["count"] == 2


@pytest.mark.asyncio
async def test_grep_search_skips_hidden_dirs(tmp_path):
    """Test that hidden directories are skipped."""
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.txt").write_text("findme", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("findme", encoding="utf-8")

    # Use Python backend to test our filtering
    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        result = await grep_search("findme", str(tmp_path))
        data = json.loads(result)

    # Should only find in visible.txt
    assert data["count"] == 1
    assert ".hidden" not in data["results"][0]["file"]


@pytest.mark.asyncio
async def test_grep_search_skips_node_modules(tmp_path):
    """Test that node_modules is skipped."""
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "lib.js").write_text("findme", encoding="utf-8")
    (tmp_path / "app.js").write_text("findme", encoding="utf-8")

    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        result = await grep_search("findme", str(tmp_path))
        data = json.loads(result)

    # Should only find in app.js
    assert data["count"] == 1
    assert "node_modules" not in data["results"][0]["file"]


# Tests for Python backend


@pytest.mark.asyncio
async def test_grep_python_path_not_found():
    """Test Python backend with non-existent path."""
    with pytest.raises(FileNotFoundError, match="Path not found"):
        await _grep_with_python("pattern", "/nonexistent/path", None, False, 0, 100)


@pytest.mark.asyncio
async def test_grep_python_invalid_regex():
    """Test Python backend with invalid regex."""
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        await _grep_with_python("[invalid", ".", None, False, 0, 100)


@pytest.mark.asyncio
async def test_grep_python_unreadable_file(tmp_path):
    """Test that unreadable files are skipped gracefully."""
    # Create a file that can't be decoded as UTF-8
    binary_file = tmp_path / "binary.dat"
    binary_file.write_bytes(b"\xff\xfe\x00\x00")

    # Create a readable file
    (tmp_path / "text.txt").write_text("findme", encoding="utf-8")

    # Should not crash
    results = await _grep_with_python("findme", str(tmp_path), None, False, 0, 100)
    assert len(results) == 1


# Tests for ripgrep backend


@pytest.mark.asyncio
async def test_grep_ripgrep_not_found():
    """Test ripgrep backend when rg is not found."""
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        results = await _grep_with_ripgrep("pattern", ".", None, False, 0, 100)
        assert results == []


@pytest.mark.asyncio
async def test_grep_ripgrep_json_parsing():
    """Test ripgrep JSON output parsing."""
    # Simulate ripgrep JSON output
    rg_output = (
        b'{"type":"match","data":{"path":{"text":"test.py"},"line_number":5,'
        b'"lines":{"text":"def foo():\\n"},"submatches":[{"match":{"text":"foo"}}]}}\n'
    )

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(rg_output, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        results = await _grep_with_ripgrep("foo", ".", None, False, 0, 100)

    assert len(results) == 1
    assert results[0]["file"] == "test.py"
    assert results[0]["line"] == 5
    assert results[0]["match"] == "foo"


@pytest.mark.asyncio
async def test_grep_ripgrep_invalid_json():
    """Test ripgrep backend handles invalid JSON lines."""
    rg_output = (
        b'not json\n{"type":"match","data":{"path":{"text":"test.py"},'
        b'"line_number":1,"lines":{"text":"x"},"submatches":[{"match":{"text":"x"}}]}}\n'
    )

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(rg_output, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        results = await _grep_with_ripgrep("x", ".", None, False, 0, 100)

    # Should skip invalid line and parse valid one
    assert len(results) == 1


def test_is_ripgrep_available():
    """Test ripgrep availability check."""
    with patch("shutil.which", return_value="/usr/bin/rg"):
        assert _is_ripgrep_available() is True

    with patch("shutil.which", return_value=None):
        assert _is_ripgrep_available() is False


@pytest.mark.asyncio
async def test_grep_search_uses_ripgrep_when_available(tmp_path):
    """Test that grep_search uses ripgrep when available."""
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")

    with patch("pygent.tools.search._is_ripgrep_available", return_value=True):
        with patch("pygent.tools.search._grep_with_ripgrep", return_value=[]) as mock_rg:
            await grep_search("hello", str(tmp_path))
            mock_rg.assert_called_once()


@pytest.mark.asyncio
async def test_grep_search_uses_python_when_ripgrep_unavailable(tmp_path):
    """Test that grep_search falls back to Python when ripgrep unavailable."""
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")

    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        with patch("pygent.tools.search._grep_with_python", return_value=[]) as mock_py:
            await grep_search("hello", str(tmp_path))
            mock_py.assert_called_once()


# Property-based tests


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content=st.text(min_size=10, max_size=200).filter(lambda s: "\r" not in s and "\x00" not in s),
    search_word=st.text(min_size=3, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
)
@pytest.mark.asyncio
async def test_prop_grep_finds_inserted_pattern(tmp_path, content, search_word):
    """Property: if we insert a word into content, grep should find it."""
    # Insert search_word into the content
    full_content = f"{content}\n{search_word}\n"
    test_file = tmp_path / "prop_test.txt"
    test_file.write_text(full_content, encoding="utf-8")

    # Force Python backend for deterministic behavior
    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        result = await grep_search(search_word, str(test_file))
        data = json.loads(result)

    # Should find at least one match
    assert data["count"] >= 1


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    lines=st.lists(st.text(min_size=5, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "), min_size=1, max_size=10),
)
@pytest.mark.asyncio
async def test_prop_grep_respects_max_results(tmp_path, lines):
    """Property: grep should never return more than max_results."""
    # Write lines that all contain "a"
    content_lines = [line + " a" for line in lines]
    test_file = tmp_path / "prop_max.txt"
    test_file.write_text("\n".join(content_lines), encoding="utf-8")

    max_results = 3
    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        result = await grep_search("a", str(test_file), max_results=max_results)
        data = json.loads(result)

    assert data["count"] <= max_results


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    word=st.text(min_size=4, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz"),
)
@pytest.mark.asyncio
async def test_prop_grep_case_insensitive(tmp_path, word):
    """Property: case-insensitive search should find both cases."""
    lower = word.lower()
    upper = word.upper()
    test_file = tmp_path / "prop_case.txt"
    test_file.write_text(f"{lower}\n{upper}\n", encoding="utf-8")

    with patch("pygent.tools.search._is_ripgrep_available", return_value=False):
        result = await grep_search(lower, str(test_file), ignore_case=True)
        data = json.loads(result)

    # Should find both if they're different
    if lower != upper:
        assert data["count"] == 2
    else:
        assert data["count"] >= 1
