import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pygent.tools.shell import shell


@pytest.mark.asyncio
async def test_shell_success():
    # Mock process and communicate return values
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"hello\n", b"")
    mock_process.returncode = 0
    mock_process.wait.return_value = None

    with patch("asyncio.create_subprocess_shell", return_value=mock_process) as mock_create:
        result = await shell(command="echo hello")

        mock_create.assert_called_once_with(
            "echo hello",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert "hello" in result
        assert "Exit Code: 0" in result


@pytest.mark.asyncio
async def test_shell_stderr():
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"error details\n")
    mock_process.returncode = 1

    with patch("asyncio.create_subprocess_shell", return_value=mock_process):
        result = await shell(command="bad_command")

        assert "STDERR" in result
        assert "error details" in result
        assert "Exit Code: 1" in result


@pytest.mark.asyncio
async def test_shell_timeout():
    mock_process = AsyncMock()
    mock_process.kill = MagicMock()  # kill is not async
    # Mock communicate to raise TimeoutError
    mock_process.communicate.side_effect = asyncio.TimeoutError
    mock_process.returncode = None

    with (
        patch("asyncio.create_subprocess_shell", return_value=mock_process),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
    ):
        result = await shell(command="sleep 10", timeout=1)

        assert "timed out" in result
        assert mock_process.kill.called


@pytest.mark.asyncio
async def test_shell_timeout_process_already_finished():
    """Test timeout when process exits before kill() is called.

    Covers the ProcessLookupError exception path (lines 36-37).
    """
    mock_process = AsyncMock()
    mock_process.kill = MagicMock(side_effect=ProcessLookupError)
    mock_process.returncode = None  # Triggers the kill path

    with (
        patch("asyncio.create_subprocess_shell", return_value=mock_process),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
    ):
        result = await shell(command="sleep 10", timeout=1)

        assert "timed out" in result
        mock_process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_shell_subprocess_creation_error():
    """Test handling when subprocess creation fails entirely.

    Covers the generic exception handler (lines 53-54).
    """
    with patch("asyncio.create_subprocess_shell", side_effect=OSError("No shell available")):
        result = await shell(command="any_command")

        assert "Error executing command" in result
        assert "No shell available" in result


@given(st.text(min_size=1), st.text(), st.text(), st.integers(min_value=0, max_value=127))
@pytest.mark.asyncio
async def test_shell_property_output_handling(command, stdout_content, stderr_content, exit_code):
    """Property check: verify handling of stdout/stderr.

    Ensures that whatever bytes are returned from stdout/stderr are present in
    the final output string.
    """

    mock_process = AsyncMock()
    mock_process.kill = MagicMock()
    stdout_bytes = stdout_content.encode("utf-8", errors="replace")
    stderr_bytes = stderr_content.encode("utf-8", errors="replace")

    mock_process.communicate.return_value = (stdout_bytes, stderr_bytes)
    mock_process.returncode = exit_code

    with patch("asyncio.create_subprocess_shell", return_value=mock_process):
        try:
            result = await shell(command=command)

            # If stdout is non-empty, it should be in the result
            if stdout_content:
                # We expect the decoded content to be in the result
                expected_stdout = stdout_bytes.decode("utf-8", errors="replace")
                assert expected_stdout.strip() in result

            # If stderr is non-empty, it should be in the result (with STDERR prefix)
            if stderr_content:
                expected_stderr = stderr_bytes.decode("utf-8", errors="replace")
                assert expected_stderr.strip() in result
                assert "STDERR" in result

            assert f"Exit Code: {exit_code}" in result

        except Exception:
            # If any exception occurs (e.g. invalid arguments during mocking
            # which shouldn't happen here but good to be safe),
            # we consider it a test failure unless it's explicitly handled.
            # In this mocked scenario, we expect success.
            raise
