import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pygent.tools.filesystem import edit_file, list_files, read_file


@pytest.mark.asyncio
async def test_read_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello World", encoding="utf-8")

    content = await read_file(str(f))
    assert content == "Hello World"


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path):
    # Ensure distinct path
    p = tmp_path / "non_existent_file.txt"
    with pytest.raises(FileNotFoundError):
        await read_file(str(p))


@pytest.mark.asyncio
async def test_list_files(tmp_path):
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").touch()

    # Non-recursive
    result_json = await list_files(str(tmp_path))
    entries = json.loads(result_json)
    names = sorted([e["name"] for e in entries])
    assert names == ["a.txt", "b.txt", "sub"]

    # Recursive
    result_json_rec = await list_files(str(tmp_path), recursive=True)
    entries_rec = json.loads(result_json_rec)

    # Check for presence of deeply nested file
    assert any(e["name"] == "c.txt" for e in entries_rec)
    assert any(e["name"] == "a.txt" for e in entries_rec)


@pytest.mark.asyncio
async def test_edit_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("print('hello')\nprint('world')", encoding="utf-8")

    await edit_file(str(f), "print('world')", "print('universe')")

    content = f.read_text(encoding="utf-8")
    assert content == "print('hello')\nprint('universe')"


@pytest.mark.asyncio
async def test_edit_file_not_found(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("foo bar", encoding="utf-8")

    with pytest.raises(ValueError, match="String not found"):
        await edit_file(str(f), "baz", "qux")


# Property-based tests


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
        lambda s: s + ".txt"
    ),
    content=st.text(min_size=1).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_read_write(tmp_path, filename, content):
    """Property test: Write content, read it back, verify match."""
    f = tmp_path / filename
    # Write using sync standard lib for setup
    f.write_text(content, encoding="utf-8")

    # Read using tool
    read_content = await read_file(str(f))
    assert read_content == content


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
        lambda s: s + ".py"
    ),
    original=st.text(min_size=5, max_size=50).filter(lambda s: "\r" not in s),
    replacement=st.text(min_size=5, max_size=50).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_edit_file(tmp_path, filename, original, replacement):
    """Property test: Create file with content containing 'original', replace with 'replacement'."""
    f = tmp_path / filename
    # Create content that definitely contains 'original'
    # We wrap it to ensure it's not just the whole string, though it could be.
    file_content = f"prefix_{original}_suffix"
    f.write_text(file_content, encoding="utf-8")

    # Perform edit
    await edit_file(str(f), original, replacement)

    # Verify
    new_content = f.read_text(encoding="utf-8")
    expected = f"prefix_{replacement}_suffix"
    assert new_content == expected
