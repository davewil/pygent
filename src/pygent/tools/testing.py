"""Test runner integration tools for pygent.

Provides framework-agnostic test execution and result parsing.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pygent.context.models import TestFramework
from pygent.tools.base import ToolCategory, ToolRisk, tool


@dataclass
class TestResult:
    """Individual test result.

    Attributes:
        name: Test name or identifier.
        status: Test outcome (passed, failed, skipped, error).
        duration: Test duration in seconds.
        error_message: Error or failure message if applicable.
        file_path: Path to the test file.
        line_number: Line number of the test.
    """

    __test__ = False  # Prevent pytest from collecting this as a test class

    name: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration: float | None = None
    error_message: str | None = None
    file_path: str | None = None
    line_number: int | None = None


@dataclass
class TestSummary:
    """Summary of test run results.

    Attributes:
        total: Total number of tests run.
        passed: Number of passed tests.
        failed: Number of failed tests.
        skipped: Number of skipped tests.
        errors: Number of tests with errors.
        duration: Total test duration in seconds.
        results: List of individual test results.
        raw_output: Raw output from the test runner.
    """

    __test__ = False  # Prevent pytest from collecting this as a test class

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    results: list[TestResult] = field(default_factory=list)
    raw_output: str = ""


async def detect_test_framework(project_path: Path) -> TestFramework:
    """Auto-detect test framework from project files.

    Args:
        project_path: Path to the project root.

    Returns:
        Detected test framework.
    """
    # Check for Python test frameworks
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if "[tool.pytest" in content or "pytest" in content.lower():
            return TestFramework.PYTEST

    pytest_ini = project_path / "pytest.ini"
    if pytest_ini.exists():
        return TestFramework.PYTEST

    setup_cfg = project_path / "setup.cfg"
    if setup_cfg.exists():
        content = setup_cfg.read_text()
        if "[tool:pytest]" in content:
            return TestFramework.PYTEST

    # Check for Node.js test frameworks
    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            content = json.loads(package_json.read_text())
            deps = {
                **content.get("dependencies", {}),
                **content.get("devDependencies", {}),
            }
            if "vitest" in deps:
                return TestFramework.VITEST
            if "jest" in deps:
                return TestFramework.JEST
            if "mocha" in deps:
                return TestFramework.MOCHA
        except json.JSONDecodeError:
            pass

    # Check for Go test
    go_mod = project_path / "go.mod"
    if go_mod.exists():
        return TestFramework.GO_TEST

    # Check for Rust/Cargo test
    cargo_toml = project_path / "Cargo.toml"
    if cargo_toml.exists():
        return TestFramework.CARGO_TEST

    # Fallback: check for Python test files
    tests_dir = project_path / "tests"
    if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
        return TestFramework.PYTEST

    if any(project_path.glob("test_*.py")):
        return TestFramework.PYTEST

    return TestFramework.UNKNOWN


def _parse_pytest_output(output: str) -> TestSummary:
    """Parse pytest output into TestSummary.

    Args:
        output: Raw pytest output.

    Returns:
        Parsed test summary.
    """
    summary = TestSummary(raw_output=output)
    results: list[TestResult] = []

    # Parse individual test results from verbose output
    # Matches patterns like: tests/test_foo.py::test_bar PASSED
    test_pattern = re.compile(
        r"^([\w/\\._-]+\.py)::(\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)(?:\s+\[.*?\])?(?:\s+\(([\d.]+)s\))?",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        file_path = match.group(1)
        test_name = match.group(2)
        status_str = match.group(3).lower()
        duration_str = match.group(4)

        status: Literal["passed", "failed", "skipped", "error"]
        if status_str == "passed":
            status = "passed"
        elif status_str == "failed":
            status = "failed"
        elif status_str == "skipped":
            status = "skipped"
        else:
            status = "error"

        duration = float(duration_str) if duration_str else None

        results.append(
            TestResult(
                name=test_name,
                status=status,
                duration=duration,
                file_path=file_path,
            )
        )

    # Parse summary line: "5 passed, 2 failed, 1 skipped in 1.23s"
    # The counts can appear in any order, so we use individual patterns
    summary_line_pattern = re.compile(r"=+[^=]+in\s+[\d.]+s\s*=+", re.IGNORECASE)
    summary_match = summary_line_pattern.search(output)

    if summary_match:
        summary_text = summary_match.group(0)
        # Extract individual counts
        passed_match = re.search(r"(\d+)\s+passed", summary_text, re.IGNORECASE)
        failed_match = re.search(r"(\d+)\s+failed", summary_text, re.IGNORECASE)
        skipped_match = re.search(r"(\d+)\s+skipped", summary_text, re.IGNORECASE)
        errors_match = re.search(r"(\d+)\s+errors?", summary_text, re.IGNORECASE)
        duration_match = re.search(r"in\s+([\d.]+)s", summary_text, re.IGNORECASE)

        summary.passed = int(passed_match.group(1)) if passed_match else 0
        summary.failed = int(failed_match.group(1)) if failed_match else 0
        summary.skipped = int(skipped_match.group(1)) if skipped_match else 0
        summary.errors = int(errors_match.group(1)) if errors_match else 0
        summary.duration = float(duration_match.group(1)) if duration_match else 0.0
    else:
        # Fallback: count from individual results
        summary.passed = sum(1 for r in results if r.status == "passed")
        summary.failed = sum(1 for r in results if r.status == "failed")
        summary.skipped = sum(1 for r in results if r.status == "skipped")
        summary.errors = sum(1 for r in results if r.status == "error")

    summary.total = summary.passed + summary.failed + summary.skipped + summary.errors
    summary.results = results

    # Extract failure messages
    failure_pattern = re.compile(
        r"_{3,}\s+(\S+)\s+_{3,}\s*([\s\S]*?)(?=_{3,}|={3,}|$)",
        re.MULTILINE,
    )
    failures = {m.group(1): m.group(2).strip() for m in failure_pattern.finditer(output)}

    for result in summary.results:
        if result.status == "failed" and result.name in failures:
            result.error_message = failures[result.name]

    return summary


def _parse_jest_output(output: str) -> TestSummary:
    """Parse Jest output into TestSummary.

    Args:
        output: Raw Jest output.

    Returns:
        Parsed test summary.
    """
    summary = TestSummary(raw_output=output)
    results: list[TestResult] = []

    # Parse individual test results
    # Matches: ✓ test name (123 ms) or ✕ test name (123 ms)
    test_pattern = re.compile(
        r"^\s*(✓|✕|○|PASS|FAIL|SKIP)\s+(.+?)(?:\s+\((\d+)\s*m?s\))?$",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        status_char = match.group(1)
        test_name = match.group(2).strip()
        duration_str = match.group(3)

        status: Literal["passed", "failed", "skipped", "error"]
        if status_char in ("✓", "PASS"):
            status = "passed"
        elif status_char in ("✕", "FAIL"):
            status = "failed"
        else:
            status = "skipped"

        duration = float(duration_str) / 1000 if duration_str else None

        results.append(
            TestResult(
                name=test_name,
                status=status,
                duration=duration,
            )
        )

    # Parse summary line: "Tests: 2 failed, 1 skipped, 5 passed, 8 total"
    summary_pattern = re.compile(
        r"Tests?:\s*(?:(\d+)\s+failed,?\s*)?(?:(\d+)\s+skipped,?\s*)?" r"(?:(\d+)\s+passed,?\s*)?(?:(\d+)\s+total)?",
        re.IGNORECASE,
    )

    summary_match = summary_pattern.search(output)
    if summary_match:
        summary.failed = int(summary_match.group(1) or 0)
        summary.skipped = int(summary_match.group(2) or 0)
        summary.passed = int(summary_match.group(3) or 0)
        summary.total = int(summary_match.group(4) or 0)
    else:
        summary.passed = sum(1 for r in results if r.status == "passed")
        summary.failed = sum(1 for r in results if r.status == "failed")
        summary.skipped = sum(1 for r in results if r.status == "skipped")
        summary.total = len(results)

    # Parse time
    time_pattern = re.compile(r"Time:\s+([\d.]+)\s*s", re.IGNORECASE)
    time_match = time_pattern.search(output)
    if time_match:
        summary.duration = float(time_match.group(1))

    summary.results = results
    return summary


def _parse_go_test_output(output: str) -> TestSummary:
    """Parse go test output into TestSummary.

    Args:
        output: Raw go test output.

    Returns:
        Parsed test summary.
    """
    summary = TestSummary(raw_output=output)
    results: list[TestResult] = []

    # Parse individual test results
    # Matches: --- PASS: TestName (0.00s) or --- FAIL: TestName (0.00s)
    test_pattern = re.compile(
        r"---\s+(PASS|FAIL|SKIP):\s+(\S+)\s+\(([\d.]+)s\)",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        status_str = match.group(1)
        test_name = match.group(2)
        duration_str = match.group(3)

        status: Literal["passed", "failed", "skipped", "error"]
        if status_str == "PASS":
            status = "passed"
        elif status_str == "FAIL":
            status = "failed"
        else:
            status = "skipped"

        results.append(
            TestResult(
                name=test_name,
                status=status,
                duration=float(duration_str),
            )
        )

    # Also match RUN lines for tests that might not have a result yet
    run_pattern = re.compile(r"===\s+RUN\s+(\S+)")
    completed_tests = {r.name for r in results}

    for match in run_pattern.finditer(output):
        test_name = match.group(1)
        if test_name not in completed_tests:
            # Test started but no result - might have errored
            results.append(
                TestResult(
                    name=test_name,
                    status="error",
                )
            )

    # Parse overall result: ok or FAIL with package name and duration
    ok_pattern = re.compile(r"^ok\s+\S+\s+([\d.]+)s", re.MULTILINE)
    fail_pattern = re.compile(r"^FAIL\s+\S+\s+([\d.]+)s", re.MULTILINE)

    ok_match = ok_pattern.search(output)
    fail_match = fail_pattern.search(output)

    if ok_match:
        summary.duration = float(ok_match.group(1))
    elif fail_match:
        summary.duration = float(fail_match.group(1))

    summary.passed = sum(1 for r in results if r.status == "passed")
    summary.failed = sum(1 for r in results if r.status == "failed")
    summary.skipped = sum(1 for r in results if r.status == "skipped")
    summary.errors = sum(1 for r in results if r.status == "error")
    summary.total = len(results)
    summary.results = results

    return summary


def _parse_cargo_test_output(output: str) -> TestSummary:
    """Parse cargo test output into TestSummary.

    Args:
        output: Raw cargo test output.

    Returns:
        Parsed test summary.
    """
    summary = TestSummary(raw_output=output)
    results: list[TestResult] = []

    # Parse individual test results
    # Matches: test module::test_name ... ok (or FAILED, ignored)
    test_pattern = re.compile(
        r"^test\s+(\S+)\s+\.\.\.\s+(ok|FAILED|ignored)",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        test_name = match.group(1)
        status_str = match.group(2)

        status: Literal["passed", "failed", "skipped", "error"]
        if status_str == "ok":
            status = "passed"
        elif status_str == "FAILED":
            status = "failed"
        else:
            status = "skipped"

        results.append(
            TestResult(
                name=test_name,
                status=status,
            )
        )

    # Parse summary line: "test result: ok. 5 passed; 0 failed; 1 ignored; 0 measured"
    summary_pattern = re.compile(
        r"test result:\s+\w+\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored",
        re.IGNORECASE,
    )

    summary_match = summary_pattern.search(output)
    if summary_match:
        summary.passed = int(summary_match.group(1))
        summary.failed = int(summary_match.group(2))
        summary.skipped = int(summary_match.group(3))
    else:
        summary.passed = sum(1 for r in results if r.status == "passed")
        summary.failed = sum(1 for r in results if r.status == "failed")
        summary.skipped = sum(1 for r in results if r.status == "skipped")

    summary.total = summary.passed + summary.failed + summary.skipped
    summary.results = results

    # Parse duration from "finished in X.XXs"
    time_pattern = re.compile(r"finished in ([\d.]+)s", re.IGNORECASE)
    time_match = time_pattern.search(output)
    if time_match:
        summary.duration = float(time_match.group(1))

    return summary


def _parse_unittest_output(output: str) -> TestSummary:
    """Parse unittest output into TestSummary.

    Args:
        output: Raw unittest output.

    Returns:
        Parsed test summary.
    """
    summary = TestSummary(raw_output=output)
    results: list[TestResult] = []

    # Parse individual test results from verbose output
    # Matches: test_name (module.TestClass) ... ok
    test_pattern = re.compile(
        r"^(\w+)\s+\(([^)]+)\)\s+\.\.\.\s+(ok|FAIL|ERROR|skipped)",
        re.MULTILINE,
    )

    for match in test_pattern.finditer(output):
        test_name = match.group(1)
        module = match.group(2)
        status_str = match.group(3)

        status: Literal["passed", "failed", "skipped", "error"]
        if status_str == "ok":
            status = "passed"
        elif status_str == "FAIL":
            status = "failed"
        elif status_str == "ERROR":
            status = "error"
        else:
            status = "skipped"

        results.append(
            TestResult(
                name=f"{module}.{test_name}",
                status=status,
            )
        )

    # Parse summary: "Ran X tests in Y.YYYs" and "OK" or "FAILED (failures=N, errors=M)"
    ran_pattern = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+([\d.]+)s", re.IGNORECASE)
    ran_match = ran_pattern.search(output)
    if ran_match:
        summary.total = int(ran_match.group(1))
        summary.duration = float(ran_match.group(2))

    fail_pattern = re.compile(
        r"FAILED\s*\((?:failures=(\d+))?[,\s]*(?:errors=(\d+))?[,\s]*(?:skipped=(\d+))?\)",
        re.IGNORECASE,
    )
    fail_match = fail_pattern.search(output)
    if fail_match:
        summary.failed = int(fail_match.group(1) or 0)
        summary.errors = int(fail_match.group(2) or 0)
        summary.skipped = int(fail_match.group(3) or 0)
        summary.passed = summary.total - summary.failed - summary.errors - summary.skipped
    elif "OK" in output:
        # All tests passed
        skip_match = re.search(r"OK\s*\(skipped=(\d+)\)", output)
        if skip_match:
            summary.skipped = int(skip_match.group(1))
        summary.passed = summary.total - summary.skipped
    else:
        summary.passed = sum(1 for r in results if r.status == "passed")
        summary.failed = sum(1 for r in results if r.status == "failed")
        summary.skipped = sum(1 for r in results if r.status == "skipped")
        summary.errors = sum(1 for r in results if r.status == "error")

    summary.results = results
    return summary


async def parse_test_output(output: str, framework: TestFramework) -> TestSummary:
    """Parse test runner output into structured results.

    Args:
        output: Raw test output string.
        framework: The test framework that produced the output.

    Returns:
        Parsed TestSummary with individual results.
    """
    if framework == TestFramework.PYTEST:
        return _parse_pytest_output(output)
    elif framework == TestFramework.JEST or framework == TestFramework.VITEST:
        return _parse_jest_output(output)
    elif framework == TestFramework.GO_TEST:
        return _parse_go_test_output(output)
    elif framework == TestFramework.CARGO_TEST:
        return _parse_cargo_test_output(output)
    elif framework == TestFramework.UNITTEST:
        return _parse_unittest_output(output)
    else:
        # Return raw output with no parsing
        return TestSummary(raw_output=output)


def _build_test_command(
    framework: TestFramework,
    path: str | None = None,
    pattern: str | None = None,
    verbose: bool = False,
    coverage: bool = False,
    fail_fast: bool = False,
) -> list[str]:
    """Build the test command for the given framework.

    Args:
        framework: Test framework to use.
        path: Specific test file or directory.
        pattern: Test name pattern to match.
        verbose: Enable verbose output.
        coverage: Run with coverage reporting.
        fail_fast: Stop on first failure.

    Returns:
        Command as list of strings.
    """
    cmd: list[str] = []

    if framework == TestFramework.PYTEST:
        cmd = ["python", "-m", "pytest"]
        if verbose:
            cmd.append("-v")
        if coverage:
            cmd.extend(["--cov", "--cov-report=term-missing"])
        if fail_fast:
            cmd.append("-x")
        if pattern:
            cmd.extend(["-k", pattern])
        if path:
            cmd.append(path)

    elif framework == TestFramework.UNITTEST:
        cmd = ["python", "-m", "unittest"]
        if verbose:
            cmd.append("-v")
        if fail_fast:
            cmd.append("-f")
        if path:
            cmd.append(path)

    elif framework == TestFramework.JEST:
        cmd = ["npx", "jest"]
        if verbose:
            cmd.append("--verbose")
        if coverage:
            cmd.append("--coverage")
        if fail_fast:
            cmd.append("--bail")
        if pattern:
            cmd.extend(["-t", pattern])
        if path:
            cmd.append(path)

    elif framework == TestFramework.VITEST:
        cmd = ["npx", "vitest", "run"]
        if coverage:
            cmd.append("--coverage")
        if path:
            cmd.append(path)

    elif framework == TestFramework.GO_TEST:
        cmd = ["go", "test"]
        if verbose:
            cmd.append("-v")
        if coverage:
            cmd.append("-cover")
        if fail_fast:
            cmd.append("-failfast")
        if pattern:
            cmd.extend(["-run", pattern])
        if path:
            cmd.append(path)
        else:
            cmd.append("./...")

    elif framework == TestFramework.CARGO_TEST:
        cmd = ["cargo", "test"]
        if pattern:
            cmd.append(pattern)
        if verbose:
            cmd.append("--")
            cmd.append("--nocapture")

    elif framework == TestFramework.MOCHA:
        cmd = ["npx", "mocha"]
        if pattern:
            cmd.extend(["--grep", pattern])
        if fail_fast:
            cmd.append("--bail")
        if path:
            cmd.append(path)

    return cmd


def _format_summary(summary: TestSummary) -> str:
    """Format TestSummary as a human-readable string.

    Args:
        summary: The test summary to format.

    Returns:
        Formatted summary string.
    """
    parts = []

    # Status indicator
    if summary.failed > 0 or summary.errors > 0:
        status = "FAILED"
    elif summary.total == 0:
        status = "NO TESTS"
    else:
        status = "PASSED"

    parts.append(f"Test Run: {status}")
    parts.append("")

    # Summary counts
    counts = []
    if summary.passed:
        counts.append(f"{summary.passed} passed")
    if summary.failed:
        counts.append(f"{summary.failed} failed")
    if summary.skipped:
        counts.append(f"{summary.skipped} skipped")
    if summary.errors:
        counts.append(f"{summary.errors} errors")

    parts.append(f"Results: {', '.join(counts) if counts else '0 tests'}")
    parts.append(f"Duration: {summary.duration:.2f}s")
    parts.append("")

    # Failed tests details
    failed_results = [r for r in summary.results if r.status in ("failed", "error")]
    if failed_results:
        parts.append("Failed Tests:")
        for result in failed_results:
            location = f"{result.file_path}:" if result.file_path else ""
            parts.append(f"  - {location}{result.name}")
            if result.error_message:
                # Indent error message
                for line in result.error_message.split("\n")[:5]:
                    parts.append(f"      {line}")

    return "\n".join(parts)


@tool(
    name="run_tests",
    description="Run project tests using the appropriate test framework",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.TESTING,
)
async def run_tests(
    path: str | None = None,
    pattern: str | None = None,
    verbose: bool = False,
    coverage: bool = False,
    fail_fast: bool = False,
    framework: str | None = None,
    working_dir: str | None = None,
    timeout: int = 300,
) -> str:
    """Run project tests.

    Args:
        path: Specific test file or directory.
        pattern: Test name pattern to match.
        verbose: Enable verbose output.
        coverage: Run with coverage reporting.
        fail_fast: Stop on first failure.
        framework: Force specific framework (auto-detected if not provided).
        working_dir: Working directory for tests (default: current directory).
        timeout: Maximum execution time in seconds (default: 300).

    Returns:
        Test results summary with pass/fail counts.
    """
    work_path = Path(working_dir) if working_dir else Path.cwd()

    # Detect or use specified framework
    if framework:
        try:
            test_framework = TestFramework(framework)
        except ValueError:
            valid_opts = ", ".join(f.value for f in TestFramework if f != TestFramework.UNKNOWN)
            return f"Error: Unknown test framework '{framework}'. Valid options: {valid_opts}"
    else:
        test_framework = await detect_test_framework(work_path)

    if test_framework == TestFramework.UNKNOWN:
        return "Error: Could not detect test framework. Please specify with framework parameter."

    # Build command
    cmd = _build_test_command(
        framework=test_framework,
        path=path,
        pattern=pattern,
        verbose=verbose,
        coverage=coverage,
        fail_fast=fail_fast,
    )

    if not cmd:
        return f"Error: Cannot build test command for framework '{test_framework.value}'"

    # Execute tests
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            if process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
            return f"Error: Test execution timed out after {timeout} seconds"

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Combine output (some test frameworks output to stderr)
        output = stdout
        if stderr:
            output = f"{stdout}\n{stderr}" if stdout else stderr

        # Parse and format results
        summary = await parse_test_output(output, test_framework)
        result = _format_summary(summary)

        # Include raw output for debugging if needed
        if verbose or (summary.failed > 0):
            result += "\n\n--- Raw Output ---\n" + output

        return result

    except FileNotFoundError:
        return f"Error: Test runner not found. Make sure '{cmd[0]}' is installed and in PATH."
    except Exception as e:
        return f"Error running tests: {str(e)}"
