import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chapgent.tools.filesystem import (
    copy_file,
    create_file,
    delete_file,
    edit_file,
    list_files,
    move_file,
    read_file,
)


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
async def test_read_file_is_directory(tmp_path):
    """Test that reading a directory raises IsADirectoryError (covers line 35)."""
    with pytest.raises(IsADirectoryError, match="Path is a directory"):
        await read_file(str(tmp_path))


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
async def test_list_files_directory_not_found(tmp_path):
    """Test that listing non-existent directory raises FileNotFoundError (covers line 58)."""
    non_existent = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError, match="Directory not found"):
        await list_files(str(non_existent))


@pytest.mark.asyncio
async def test_edit_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("print('hello')\nprint('world')", encoding="utf-8")

    await edit_file(str(f), "print('world')", "print('universe')")

    content = f.read_text(encoding="utf-8")
    assert content == "print('hello')\nprint('universe')"


@pytest.mark.asyncio
async def test_edit_file_string_not_found(tmp_path):
    """Test that editing with non-existent string raises ValueError."""
    f = tmp_path / "notes.txt"
    f.write_text("foo bar", encoding="utf-8")

    with pytest.raises(ValueError, match="String not found"):
        await edit_file(str(f), "baz", "qux")


@pytest.mark.asyncio
async def test_edit_file_file_not_found(tmp_path):
    """Test that editing non-existent file raises FileNotFoundError (covers line 104)."""
    non_existent = tmp_path / "does_not_exist.txt"
    with pytest.raises(FileNotFoundError, match="File not found"):
        await edit_file(str(non_existent), "old", "new")


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


# ============================================================================
# create_file tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_file(tmp_path):
    """Test creating a new file with content."""
    f = tmp_path / "new_file.txt"
    result = await create_file(str(f), "Hello World")

    assert "Successfully created" in result
    assert f.exists()
    assert f.read_text(encoding="utf-8") == "Hello World"


@pytest.mark.asyncio
async def test_create_file_with_nested_path(tmp_path):
    """Test creating a file in a non-existent directory (auto-creates parents)."""
    f = tmp_path / "nested" / "dir" / "file.txt"
    result = await create_file(str(f), "Nested content")

    assert "Successfully created" in result
    assert f.exists()
    assert f.read_text(encoding="utf-8") == "Nested content"


@pytest.mark.asyncio
async def test_create_file_already_exists(tmp_path):
    """Test that creating an existing file raises FileExistsError."""
    f = tmp_path / "existing.txt"
    f.write_text("existing content", encoding="utf-8")

    with pytest.raises(FileExistsError, match="File already exists"):
        await create_file(str(f), "new content")


@pytest.mark.asyncio
async def test_create_file_empty_content(tmp_path):
    """Test creating a file with empty content."""
    f = tmp_path / "empty.txt"
    result = await create_file(str(f), "")

    assert "Successfully created" in result
    assert f.exists()
    assert f.read_text(encoding="utf-8") == ""


# ============================================================================
# delete_file tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_file(tmp_path):
    """Test deleting an existing file."""
    f = tmp_path / "to_delete.txt"
    f.write_text("delete me", encoding="utf-8")

    result = await delete_file(str(f))

    assert "Successfully deleted" in result
    assert not f.exists()


@pytest.mark.asyncio
async def test_delete_file_not_found(tmp_path):
    """Test that deleting non-existent file raises FileNotFoundError."""
    f = tmp_path / "not_exists.txt"

    with pytest.raises(FileNotFoundError, match="File not found"):
        await delete_file(str(f))


@pytest.mark.asyncio
async def test_delete_file_is_directory(tmp_path):
    """Test that deleting a directory raises IsADirectoryError."""
    d = tmp_path / "a_directory"
    d.mkdir()

    with pytest.raises(IsADirectoryError, match="Cannot delete directory"):
        await delete_file(str(d))


# ============================================================================
# move_file tests
# ============================================================================


@pytest.mark.asyncio
async def test_move_file(tmp_path):
    """Test moving a file to a new location."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "destination.txt"
    src.write_text("content", encoding="utf-8")

    result = await move_file(str(src), str(dst))

    assert "Successfully moved" in result
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "content"


@pytest.mark.asyncio
async def test_move_file_rename(tmp_path):
    """Test renaming a file (move within same directory)."""
    src = tmp_path / "old_name.txt"
    dst = tmp_path / "new_name.txt"
    src.write_text("rename content", encoding="utf-8")

    result = await move_file(str(src), str(dst))

    assert "Successfully moved" in result
    assert not src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_move_file_to_nested_directory(tmp_path):
    """Test moving a file to a non-existent directory (auto-creates parents)."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "nested" / "dir" / "moved.txt"
    src.write_text("nested content", encoding="utf-8")

    result = await move_file(str(src), str(dst))

    assert "Successfully moved" in result
    assert not src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_move_file_source_not_found(tmp_path):
    """Test that moving non-existent file raises FileNotFoundError."""
    src = tmp_path / "not_exists.txt"
    dst = tmp_path / "destination.txt"

    with pytest.raises(FileNotFoundError, match="Source file not found"):
        await move_file(str(src), str(dst))


@pytest.mark.asyncio
async def test_move_file_source_is_directory(tmp_path):
    """Test that moving a directory raises IsADirectoryError."""
    src = tmp_path / "a_directory"
    dst = tmp_path / "destination"
    src.mkdir()

    with pytest.raises(IsADirectoryError, match="Cannot move directory"):
        await move_file(str(src), str(dst))


@pytest.mark.asyncio
async def test_move_file_destination_exists(tmp_path):
    """Test that moving to existing destination raises FileExistsError."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "destination.txt"
    src.write_text("source", encoding="utf-8")
    dst.write_text("destination", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Destination already exists"):
        await move_file(str(src), str(dst))


# ============================================================================
# copy_file tests
# ============================================================================


@pytest.mark.asyncio
async def test_copy_file(tmp_path):
    """Test copying a file to a new location."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "copy.txt"
    src.write_text("copy content", encoding="utf-8")

    result = await copy_file(str(src), str(dst))

    assert "Successfully copied" in result
    assert src.exists()  # Source still exists
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "copy content"


@pytest.mark.asyncio
async def test_copy_file_to_nested_directory(tmp_path):
    """Test copying a file to a non-existent directory (auto-creates parents)."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "nested" / "dir" / "copy.txt"
    src.write_text("nested copy", encoding="utf-8")

    result = await copy_file(str(src), str(dst))

    assert "Successfully copied" in result
    assert src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_copy_file_source_not_found(tmp_path):
    """Test that copying non-existent file raises FileNotFoundError."""
    src = tmp_path / "not_exists.txt"
    dst = tmp_path / "destination.txt"

    with pytest.raises(FileNotFoundError, match="Source file not found"):
        await copy_file(str(src), str(dst))


@pytest.mark.asyncio
async def test_copy_file_source_is_directory(tmp_path):
    """Test that copying a directory raises IsADirectoryError."""
    src = tmp_path / "a_directory"
    dst = tmp_path / "destination"
    src.mkdir()

    with pytest.raises(IsADirectoryError, match="Cannot copy directory"):
        await copy_file(str(src), str(dst))


@pytest.mark.asyncio
async def test_copy_file_destination_exists(tmp_path):
    """Test that copying to existing destination raises FileExistsError."""
    src = tmp_path / "source.txt"
    dst = tmp_path / "destination.txt"
    src.write_text("source", encoding="utf-8")
    dst.write_text("destination", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Destination already exists"):
        await copy_file(str(src), str(dst))


# ============================================================================
# Property-based tests for new tools
# ============================================================================


# Helper strategy for valid filenames
valid_filename = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
    lambda s: s + ".txt"
)


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filename=valid_filename,
    content=st.text(min_size=0, max_size=100).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_create_file(tmp_path, filename, content):
    """Property test: Creating a file writes exact content and makes it readable."""
    import uuid

    # Use unique subdirectory per example to avoid state pollution
    subdir = tmp_path / str(uuid.uuid4())
    subdir.mkdir()
    f = subdir / filename

    await create_file(str(f), content)

    # Verify file exists and content matches
    assert f.exists()
    assert f.read_text(encoding="utf-8") == content

    # Verify it can be read back via read_file
    read_content = await read_file(str(f))
    assert read_content == content


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filename=valid_filename,
    content=st.text(min_size=1, max_size=100).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_delete_file(tmp_path, filename, content):
    """Property test: Deleting a file removes it completely."""
    import uuid

    subdir = tmp_path / str(uuid.uuid4())
    subdir.mkdir()
    f = subdir / filename
    f.write_text(content, encoding="utf-8")

    await delete_file(str(f))

    assert not f.exists()


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    src_filename=valid_filename,
    dst_filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
        lambda s: s + "_moved.txt"
    ),
    content=st.text(min_size=1, max_size=100).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_move_file(tmp_path, src_filename, dst_filename, content):
    """Property test: Moving a file preserves content and removes source."""
    import uuid

    subdir = tmp_path / str(uuid.uuid4())
    subdir.mkdir()
    src = subdir / src_filename
    dst = subdir / dst_filename

    # Skip if src and dst are the same name
    if src_filename == dst_filename.replace("_moved.txt", ".txt"):
        return

    src.write_text(content, encoding="utf-8")

    await move_file(str(src), str(dst))

    assert not src.exists()
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == content


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    src_filename=valid_filename,
    dst_filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
        lambda s: s + "_copy.txt"
    ),
    content=st.text(min_size=1, max_size=100).filter(lambda s: "\r" not in s),
)
@pytest.mark.asyncio
async def test_prop_copy_file(tmp_path, src_filename, dst_filename, content):
    """Property test: Copying a file preserves content and keeps source."""
    import uuid

    subdir = tmp_path / str(uuid.uuid4())
    subdir.mkdir()
    src = subdir / src_filename
    dst = subdir / dst_filename

    # Skip if src and dst are the same name
    if src_filename == dst_filename.replace("_copy.txt", ".txt"):
        return

    src.write_text(content, encoding="utf-8")

    await copy_file(str(src), str(dst))

    # Both should exist with same content
    assert src.exists()
    assert dst.exists()
    assert src.read_text(encoding="utf-8") == content
    assert dst.read_text(encoding="utf-8") == content
