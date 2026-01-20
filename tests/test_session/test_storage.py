import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import datetimes

from chapgent.session.models import Message, Session, TextBlock, ToolInvocation, ToolResultBlock, ToolUseBlock
from chapgent.session.storage import SessionStorage

# ASCII-safe text strategy for cross-platform compatibility
safe_text = st.text(alphabet=string.ascii_letters + string.digits + " .,!?-_")

# Strategies for generating Session objects
text_block_strategy = st.builds(TextBlock, text=safe_text)
tool_use_block_strategy = st.builds(
    ToolUseBlock,
    id=safe_text,
    name=safe_text,
    input=st.dictionaries(keys=safe_text, values=safe_text),  # Simple dict for now
)
tool_result_block_strategy = st.builds(
    ToolResultBlock, tool_use_id=safe_text, content=safe_text, is_error=st.booleans()
)

content_block_strategy = st.one_of(text_block_strategy, tool_use_block_strategy, tool_result_block_strategy)

message_strategy = st.builds(
    Message,
    role=st.sampled_from(["user", "assistant", "system"]),
    content=st.one_of(safe_text, st.lists(content_block_strategy)),
    timestamp=datetimes(),
)

tool_invocation_strategy = st.builds(
    ToolInvocation,
    tool_name=safe_text,
    arguments=st.dictionaries(keys=safe_text, values=safe_text),
    result=safe_text,
    timestamp=datetimes(),
)

session_strategy = st.builds(
    Session,
    id=st.text(min_size=1, alphabet=string.ascii_letters + string.digits + "-_"),  # Ensure non-empty ID
    messages=st.lists(message_strategy),
    tool_history=st.lists(tool_invocation_strategy),
    working_directory=safe_text,
    metadata=st.dictionaries(keys=safe_text, values=safe_text),
)


@pytest.fixture
def storage(tmp_path):
    return SessionStorage(storage_dir=tmp_path)


@pytest.mark.asyncio
async def test_save_and_load_roundtrip(storage):
    # Manual roundtrip test
    session = Session(id="test-session", working_directory="/tmp")
    await storage.save(session)

    loaded = await storage.load("test-session")
    assert loaded == session


@pytest.mark.asyncio
@given(session=session_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_save_load(tmp_path, session):
    # Avoid reserved characters in filenames if session.id is used directly
    # For this test, we might want to sanitize or force a safe ID,
    # but let's assume the session ID generator handles safety or storage handles it.
    # For simplicity in property test, let's fix the ID to be safe
    session.id = "safe-id-" + str(hash(session.id))

    storage = SessionStorage(storage_dir=tmp_path)
    await storage.save(session)
    loaded = await storage.load(session.id)

    # Pydantic models should be equal
    assert loaded.model_dump() == session.model_dump()


@pytest.mark.asyncio
async def test_list_sessions(storage):
    s1 = Session(id="s1")
    s2 = Session(id="s2")

    await storage.save(s1)
    await storage.save(s2)

    sessions = await storage.list_sessions()
    assert len(sessions) == 2
    ids = {s.id for s in sessions}
    assert "s1" in ids
    assert "s2" in ids


@pytest.mark.asyncio
async def test_delete_session(storage):
    s1 = Session(id="s1")
    await storage.save(s1)

    assert await storage.load("s1") is not None

    await storage.delete("s1")

    assert await storage.load("s1") is None


@pytest.mark.asyncio
async def test_persistence_across_instances(tmp_path):
    storage1 = SessionStorage(storage_dir=tmp_path)
    s1 = Session(id="s1")
    await storage1.save(s1)

    storage2 = SessionStorage(storage_dir=tmp_path)
    loaded = await storage2.load("s1")
    assert loaded == s1


@pytest.mark.asyncio
async def test_load_corrupted_file_raises(storage, tmp_path):
    """Verify that loading a corrupted session file raises an exception."""
    from pydantic import ValidationError

    # Write invalid JSON to a session file
    corrupted_path = tmp_path / "corrupted.json"
    corrupted_path.write_text("{ invalid json content")

    with pytest.raises((ValidationError, ValueError)):
        await storage.load("corrupted")


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(storage):
    """Verify that deleting a non-existent session returns False."""
    result = await storage.delete("does-not-exist")
    assert result is False


@pytest.mark.asyncio
async def test_list_sessions_skips_index_json(storage, tmp_path):
    """Verify that list_sessions ignores index.json file."""
    # Create a valid session
    s1 = Session(id="s1")
    await storage.save(s1)

    # Create an index.json file (should be ignored)
    index_path = tmp_path / "index.json"
    index_path.write_text('{"sessions": []}')

    sessions = await storage.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == "s1"


@pytest.mark.asyncio
async def test_list_sessions_skips_corrupted_files(storage, tmp_path):
    """Verify that list_sessions skips corrupted session files gracefully."""
    # Create a valid session
    s1 = Session(id="s1")
    await storage.save(s1)

    # Create a corrupted JSON file
    corrupted_path = tmp_path / "corrupted.json"
    corrupted_path.write_text("{ invalid json }")

    sessions = await storage.list_sessions()
    # Should only return the valid session
    assert len(sessions) == 1
    assert sessions[0].id == "s1"
