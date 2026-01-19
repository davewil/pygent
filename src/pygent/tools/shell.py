import asyncio

from pygent.tools.base import ToolCategory, ToolRisk, tool


@tool(
    name="shell",
    description="Execute a shell command and return output. Returns stdout and stderr combined.",
    risk=ToolRisk.HIGH,
    category=ToolCategory.SHELL,
    cacheable=False,
)
async def shell(command: str, timeout: int = 60) -> str:
    """Execute shell command.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        Combined stdout and stderr, plus exit code.
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            if process.returncode is None:
                try:
                    process.kill()
                    # Wait for process to actually terminate to avoid zombies
                    await process.wait()
                except ProcessLookupError:
                    pass  # Process already finished
            return f"Error: Command timed out after {timeout} seconds"

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        output = []
        if stdout:
            output.append(stdout)
        if stderr:
            output.append(f"STDERR:\n{stderr}")

        output.append(f"\nExit Code: {process.returncode}")

        return "\n".join(output).strip()

    except Exception as e:
        return f"Error executing command: {str(e)}"
