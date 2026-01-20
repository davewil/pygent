"""Tests for the testing tools module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.context.models import TestFramework
from chapgent.tools.testing import (
    TestResult,
    TestSummary,
    _build_test_command,
    _format_summary,
    _parse_cargo_test_output,
    _parse_go_test_output,
    _parse_jest_output,
    _parse_pytest_output,
    _parse_unittest_output,
    detect_test_framework,
    parse_test_output,
    run_tests,
)

# ============================================================================
# TestResult and TestSummary Model Tests
# ============================================================================


class TestTestResultModel:
    """Tests for TestResult dataclass."""

    __test__ = True  # Ensure pytest collects this

    def test_create_basic(self):
        """Test creating a basic TestResult."""
        result = TestResult(name="test_foo", status="passed")
        assert result.name == "test_foo"
        assert result.status == "passed"
        assert result.duration is None
        assert result.error_message is None

    def test_create_with_all_fields(self):
        """Test creating TestResult with all fields."""
        result = TestResult(
            name="test_bar",
            status="failed",
            duration=1.23,
            error_message="AssertionError: expected True",
            file_path="tests/test_foo.py",
            line_number=42,
        )
        assert result.name == "test_bar"
        assert result.status == "failed"
        assert result.duration == 1.23
        assert result.error_message == "AssertionError: expected True"
        assert result.file_path == "tests/test_foo.py"
        assert result.line_number == 42


class TestTestSummaryModel:
    """Tests for TestSummary dataclass."""

    __test__ = True  # Ensure pytest collects this

    def test_create_default(self):
        """Test creating TestSummary with defaults."""
        summary = TestSummary()
        assert summary.total == 0
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.skipped == 0
        assert summary.errors == 0
        assert summary.duration == 0.0
        assert summary.results == []
        assert summary.raw_output == ""

    def test_create_with_results(self):
        """Test creating TestSummary with results."""
        results = [
            TestResult(name="test_a", status="passed"),
            TestResult(name="test_b", status="failed"),
        ]
        summary = TestSummary(
            total=2,
            passed=1,
            failed=1,
            duration=2.5,
            results=results,
        )
        assert summary.total == 2
        assert summary.passed == 1
        assert summary.failed == 1
        assert len(summary.results) == 2


# ============================================================================
# Test Framework Detection Tests
# ============================================================================


class TestDetectTestFramework:
    """Tests for detect_test_framework function."""

    __test__ = True

    @pytest.mark.asyncio
    async def test_detect_pytest_from_pyproject(self, tmp_path: Path):
        """Detect pytest from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pytest.ini_options]\naddopts = "-v"')

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_detect_pytest_from_pytest_ini(self, tmp_path: Path):
        """Detect pytest from pytest.ini."""
        pytest_ini = tmp_path / "pytest.ini"
        pytest_ini.write_text("[pytest]\naddopts = -v")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_detect_pytest_from_setup_cfg(self, tmp_path: Path):
        """Detect pytest from setup.cfg."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("[tool:pytest]\naddopts = -v")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_detect_jest(self, tmp_path: Path):
        """Detect Jest from package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text('{"devDependencies": {"jest": "^29.0.0"}}')

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.JEST

    @pytest.mark.asyncio
    async def test_detect_vitest(self, tmp_path: Path):
        """Detect Vitest from package.json (takes precedence over Jest)."""
        package_json = tmp_path / "package.json"
        package_json.write_text('{"devDependencies": {"vitest": "^1.0.0", "jest": "^29.0.0"}}')

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.VITEST

    @pytest.mark.asyncio
    async def test_detect_mocha(self, tmp_path: Path):
        """Detect Mocha from package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text('{"devDependencies": {"mocha": "^10.0.0"}}')

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.MOCHA

    @pytest.mark.asyncio
    async def test_detect_go_test(self, tmp_path: Path):
        """Detect go test from go.mod."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/project")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.GO_TEST

    @pytest.mark.asyncio
    async def test_detect_cargo_test(self, tmp_path: Path):
        """Detect cargo test from Cargo.toml."""
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "myproject"')

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.CARGO_TEST

    @pytest.mark.asyncio
    async def test_detect_pytest_from_test_files(self, tmp_path: Path):
        """Detect pytest from test files in tests/ directory."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_example.py").write_text("def test_foo(): pass")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_detect_pytest_from_root_test_files(self, tmp_path: Path):
        """Detect pytest from test files in root directory."""
        (tmp_path / "test_example.py").write_text("def test_foo(): pass")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_detect_unknown(self, tmp_path: Path):
        """Return UNKNOWN when no framework detected."""
        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_invalid_package_json(self, tmp_path: Path):
        """Handle invalid package.json gracefully."""
        package_json = tmp_path / "package.json"
        package_json.write_text("{invalid json")

        result = await detect_test_framework(tmp_path)
        assert result == TestFramework.UNKNOWN


# ============================================================================
# Pytest Output Parser Tests
# ============================================================================


class TestParsePytestOutput:
    """Tests for pytest output parsing."""

    __test__ = True

    def test_parse_passed_tests(self):
        """Parse pytest output with passed tests."""
        output = """
============================= test session starts ==============================
platform linux -- Python 3.12.0, pytest-8.0.0
collected 3 items

tests/test_foo.py::test_one PASSED
tests/test_foo.py::test_two PASSED
tests/test_bar.py::test_three PASSED

============================== 3 passed in 0.12s ===============================
"""
        summary = _parse_pytest_output(output)

        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.total == 3
        assert summary.duration == 0.12
        assert len(summary.results) == 3

    def test_parse_failed_tests(self):
        """Parse pytest output with failures."""
        output = """
============================= test session starts ==============================
collected 2 items

tests/test_foo.py::test_pass PASSED
tests/test_foo.py::test_fail FAILED

=================================== FAILURES ===================================
___________________________________ test_fail __________________________________

    def test_fail():
>       assert False
E       AssertionError

tests/test_foo.py:5: AssertionError
=========================== short test summary info ============================
FAILED tests/test_foo.py::test_fail - AssertionError
=========================== 1 passed, 1 failed in 0.23s ========================
"""
        summary = _parse_pytest_output(output)

        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2
        assert summary.duration == 0.23

    def test_parse_skipped_tests(self):
        """Parse pytest output with skipped tests."""
        output = """
============================= test session starts ==============================
collected 3 items

tests/test_foo.py::test_one PASSED
tests/test_foo.py::test_two SKIPPED
tests/test_foo.py::test_three PASSED

========================= 2 passed, 1 skipped in 0.05s =========================
"""
        summary = _parse_pytest_output(output)

        assert summary.passed == 2
        assert summary.skipped == 1
        assert summary.total == 3

    def test_parse_with_duration_in_test_names(self):
        """Parse pytest verbose output with test durations."""
        output = """
tests/test_foo.py::test_one PASSED (0.01s)
tests/test_foo.py::test_two PASSED (0.02s)

============================== 2 passed in 0.03s ===============================
"""
        summary = _parse_pytest_output(output)

        assert summary.passed == 2
        assert len(summary.results) == 2
        assert summary.results[0].duration == 0.01
        assert summary.results[1].duration == 0.02

    def test_parse_empty_output(self):
        """Parse empty pytest output."""
        summary = _parse_pytest_output("")

        assert summary.total == 0
        assert summary.passed == 0


# ============================================================================
# Jest Output Parser Tests
# ============================================================================


class TestParseJestOutput:
    """Tests for Jest output parsing."""

    __test__ = True

    def test_parse_passed_tests(self):
        """Parse Jest output with passed tests."""
        output = """
 PASS  src/test.js
  ✓ should do something (5 ms)
  ✓ should do another thing (3 ms)

Tests:  2 passed, 2 total
Time:   1.234s
"""
        summary = _parse_jest_output(output)

        assert summary.passed == 2
        assert summary.total == 2
        assert summary.duration == 1.234

    def test_parse_failed_tests(self):
        """Parse Jest output with failures."""
        output = """
 FAIL  src/test.js
  ✓ should pass (5 ms)
  ✕ should fail (10 ms)

Tests:  1 failed, 1 passed, 2 total
Time:   2.5s
"""
        summary = _parse_jest_output(output)

        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2

    def test_parse_skipped_tests(self):
        """Parse Jest output with skipped tests."""
        output = """
 PASS  src/test.js
  ✓ should pass (5 ms)
  ○ skipped test

Tests:  1 skipped, 1 passed, 2 total
"""
        summary = _parse_jest_output(output)

        assert summary.passed == 1
        assert summary.skipped == 1


# ============================================================================
# Go Test Output Parser Tests
# ============================================================================


class TestParseGoTestOutput:
    """Tests for go test output parsing."""

    __test__ = True

    def test_parse_passed_tests(self):
        """Parse go test output with passed tests."""
        output = """
=== RUN   TestOne
--- PASS: TestOne (0.00s)
=== RUN   TestTwo
--- PASS: TestTwo (0.01s)
PASS
ok      example.com/project     0.02s
"""
        summary = _parse_go_test_output(output)

        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.total == 2
        assert summary.duration == 0.02

    def test_parse_failed_tests(self):
        """Parse go test output with failures."""
        output = """
=== RUN   TestOne
--- PASS: TestOne (0.00s)
=== RUN   TestTwo
    test.go:10: expected true, got false
--- FAIL: TestTwo (0.01s)
FAIL
FAIL    example.com/project     0.02s
"""
        summary = _parse_go_test_output(output)

        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2

    def test_parse_skipped_tests(self):
        """Parse go test output with skipped tests."""
        output = """
=== RUN   TestOne
--- PASS: TestOne (0.00s)
=== RUN   TestSkip
--- SKIP: TestSkip (0.00s)
ok      example.com/project     0.01s
"""
        summary = _parse_go_test_output(output)

        assert summary.passed == 1
        assert summary.skipped == 1


# ============================================================================
# Cargo Test Output Parser Tests
# ============================================================================


class TestParseCargoTestOutput:
    """Tests for cargo test output parsing."""

    __test__ = True

    def test_parse_passed_tests(self):
        """Parse cargo test output with passed tests."""
        output = """
running 2 tests
test module::test_one ... ok
test module::test_two ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; finished in 0.12s
"""
        summary = _parse_cargo_test_output(output)

        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.total == 2
        assert summary.duration == 0.12

    def test_parse_failed_tests(self):
        """Parse cargo test output with failures."""
        output = """
running 2 tests
test module::test_pass ... ok
test module::test_fail ... FAILED

failures:
    module::test_fail

test result: FAILED. 1 passed; 1 failed; 0 ignored; finished in 0.15s
"""
        summary = _parse_cargo_test_output(output)

        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2

    def test_parse_ignored_tests(self):
        """Parse cargo test output with ignored tests."""
        output = """
running 2 tests
test module::test_one ... ok
test module::test_ignored ... ignored

test result: ok. 1 passed; 0 failed; 1 ignored; finished in 0.05s
"""
        summary = _parse_cargo_test_output(output)

        assert summary.passed == 1
        assert summary.skipped == 1


# ============================================================================
# Unittest Output Parser Tests
# ============================================================================


class TestParseUnittestOutput:
    """Tests for unittest output parsing."""

    __test__ = True

    def test_parse_passed_tests(self):
        """Parse unittest output with passed tests."""
        output = """
test_one (test_module.TestClass) ... ok
test_two (test_module.TestClass) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
"""
        summary = _parse_unittest_output(output)

        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.total == 2
        assert summary.duration == 0.001

    def test_parse_failed_tests(self):
        """Parse unittest output with failures."""
        output = """
test_pass (test_module.TestClass) ... ok
test_fail (test_module.TestClass) ... FAIL

======================================================================
FAIL: test_fail (test_module.TestClass)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test.py", line 5, in test_fail
    self.assertTrue(False)
AssertionError: False is not true

----------------------------------------------------------------------
Ran 2 tests in 0.002s

FAILED (failures=1)
"""
        summary = _parse_unittest_output(output)

        assert summary.passed == 1
        assert summary.failed == 1
        assert summary.total == 2

    def test_parse_with_errors(self):
        """Parse unittest output with errors."""
        output = """
test_pass (test_module.TestClass) ... ok
test_error (test_module.TestClass) ... ERROR

----------------------------------------------------------------------
Ran 2 tests in 0.002s

FAILED (failures=0, errors=1)
"""
        summary = _parse_unittest_output(output)

        assert summary.passed == 1
        assert summary.errors == 1

    def test_parse_with_skipped(self):
        """Parse unittest output with skipped tests."""
        output = """
test_one (test_module.TestClass) ... ok
test_skip (test_module.TestClass) ... skipped

----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK (skipped=1)
"""
        summary = _parse_unittest_output(output)

        assert summary.passed == 1
        assert summary.skipped == 1


# ============================================================================
# parse_test_output Dispatcher Tests
# ============================================================================


class TestParseTestOutput:
    """Tests for parse_test_output dispatcher function."""

    __test__ = True

    @pytest.mark.asyncio
    async def test_dispatch_to_pytest(self):
        """Dispatch to pytest parser."""
        output = "============================== 1 passed in 0.01s ==============================="
        summary = await parse_test_output(output, TestFramework.PYTEST)
        assert summary.passed == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_jest(self):
        """Dispatch to Jest parser."""
        output = "Tests:  2 passed, 2 total"
        summary = await parse_test_output(output, TestFramework.JEST)
        assert summary.passed == 2

    @pytest.mark.asyncio
    async def test_dispatch_to_vitest(self):
        """Dispatch to Vitest parser (uses Jest parser)."""
        output = "Tests:  3 passed, 3 total"
        summary = await parse_test_output(output, TestFramework.VITEST)
        assert summary.passed == 3

    @pytest.mark.asyncio
    async def test_dispatch_to_go_test(self):
        """Dispatch to go test parser."""
        output = "--- PASS: TestOne (0.00s)\nok      example.com     0.01s"
        summary = await parse_test_output(output, TestFramework.GO_TEST)
        assert summary.passed == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_cargo_test(self):
        """Dispatch to cargo test parser."""
        output = "test result: ok. 1 passed; 0 failed; 0 ignored;"
        summary = await parse_test_output(output, TestFramework.CARGO_TEST)
        assert summary.passed == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_unittest(self):
        """Dispatch to unittest parser."""
        output = "Ran 2 tests in 0.001s\n\nOK"
        summary = await parse_test_output(output, TestFramework.UNITTEST)
        assert summary.total == 2

    @pytest.mark.asyncio
    async def test_dispatch_unknown_framework(self):
        """Return raw output for unknown framework."""
        output = "some test output"
        summary = await parse_test_output(output, TestFramework.UNKNOWN)
        assert summary.raw_output == output
        assert summary.total == 0


# ============================================================================
# _build_test_command Tests
# ============================================================================


class TestBuildTestCommand:
    """Tests for _build_test_command function."""

    __test__ = True

    def test_build_pytest_basic(self):
        """Build basic pytest command."""
        cmd = _build_test_command(TestFramework.PYTEST)
        assert cmd == ["python", "-m", "pytest"]

    def test_build_pytest_with_options(self):
        """Build pytest command with all options."""
        cmd = _build_test_command(
            TestFramework.PYTEST,
            path="tests/test_foo.py",
            pattern="test_bar",
            verbose=True,
            coverage=True,
            fail_fast=True,
        )
        assert "python" in cmd
        assert "-m" in cmd
        assert "pytest" in cmd
        assert "-v" in cmd
        assert "--cov" in cmd
        assert "-x" in cmd
        assert "-k" in cmd
        assert "test_bar" in cmd
        assert "tests/test_foo.py" in cmd

    def test_build_unittest_basic(self):
        """Build basic unittest command."""
        cmd = _build_test_command(TestFramework.UNITTEST)
        assert cmd == ["python", "-m", "unittest"]

    def test_build_unittest_with_options(self):
        """Build unittest command with options."""
        cmd = _build_test_command(
            TestFramework.UNITTEST,
            verbose=True,
            fail_fast=True,
            path="test_module",
        )
        assert "-v" in cmd
        assert "-f" in cmd
        assert "test_module" in cmd

    def test_build_jest_basic(self):
        """Build basic Jest command."""
        cmd = _build_test_command(TestFramework.JEST)
        assert cmd == ["npx", "jest"]

    def test_build_jest_with_options(self):
        """Build Jest command with options."""
        cmd = _build_test_command(
            TestFramework.JEST,
            verbose=True,
            coverage=True,
            fail_fast=True,
            pattern="test pattern",
            path="src/test.js",
        )
        assert "--verbose" in cmd
        assert "--coverage" in cmd
        assert "--bail" in cmd
        assert "-t" in cmd
        assert "test pattern" in cmd
        assert "src/test.js" in cmd

    def test_build_vitest(self):
        """Build Vitest command."""
        cmd = _build_test_command(TestFramework.VITEST, coverage=True)
        assert cmd == ["npx", "vitest", "run", "--coverage"]

    def test_build_go_test_basic(self):
        """Build basic go test command."""
        cmd = _build_test_command(TestFramework.GO_TEST)
        assert cmd == ["go", "test", "./..."]

    def test_build_go_test_with_options(self):
        """Build go test command with options."""
        cmd = _build_test_command(
            TestFramework.GO_TEST,
            verbose=True,
            coverage=True,
            fail_fast=True,
            pattern="TestFoo",
            path="./pkg/...",
        )
        assert "-v" in cmd
        assert "-cover" in cmd
        assert "-failfast" in cmd
        assert "-run" in cmd
        assert "TestFoo" in cmd
        assert "./pkg/..." in cmd

    def test_build_cargo_test_basic(self):
        """Build basic cargo test command."""
        cmd = _build_test_command(TestFramework.CARGO_TEST)
        assert cmd == ["cargo", "test"]

    def test_build_cargo_test_with_pattern(self):
        """Build cargo test command with pattern."""
        cmd = _build_test_command(TestFramework.CARGO_TEST, pattern="test_foo")
        assert "cargo" in cmd
        assert "test" in cmd
        assert "test_foo" in cmd

    def test_build_mocha(self):
        """Build Mocha command."""
        cmd = _build_test_command(
            TestFramework.MOCHA,
            pattern="test pattern",
            fail_fast=True,
            path="test/",
        )
        assert "npx" in cmd
        assert "mocha" in cmd
        assert "--grep" in cmd
        assert "--bail" in cmd
        assert "test/" in cmd


# ============================================================================
# _format_summary Tests
# ============================================================================


class TestFormatSummary:
    """Tests for _format_summary function."""

    __test__ = True

    def test_format_all_passed(self):
        """Format summary with all tests passed."""
        summary = TestSummary(total=5, passed=5, duration=1.23)
        result = _format_summary(summary)

        assert "PASSED" in result
        assert "5 passed" in result
        assert "1.23s" in result

    def test_format_with_failures(self):
        """Format summary with failures."""
        summary = TestSummary(
            total=3,
            passed=1,
            failed=2,
            duration=2.5,
            results=[
                TestResult(name="test_fail1", status="failed", file_path="test.py"),
                TestResult(name="test_fail2", status="failed", error_message="AssertionError"),
            ],
        )
        result = _format_summary(summary)

        assert "FAILED" in result
        assert "1 passed" in result
        assert "2 failed" in result
        assert "Failed Tests:" in result
        assert "test_fail1" in result
        assert "test_fail2" in result

    def test_format_no_tests(self):
        """Format summary with no tests."""
        summary = TestSummary()
        result = _format_summary(summary)

        assert "NO TESTS" in result

    def test_format_with_skipped(self):
        """Format summary with skipped tests."""
        summary = TestSummary(total=3, passed=2, skipped=1)
        result = _format_summary(summary)

        assert "PASSED" in result
        assert "2 passed" in result
        assert "1 skipped" in result


# ============================================================================
# run_tests Tool Tests
# ============================================================================


class TestRunTestsTool:
    """Tests for run_tests tool."""

    __test__ = True

    @pytest.mark.asyncio
    async def test_run_tests_unknown_framework(self, tmp_path: Path):
        """Error when framework cannot be detected."""
        result = await run_tests(working_dir=str(tmp_path))
        assert "Could not detect test framework" in result

    @pytest.mark.asyncio
    async def test_run_tests_invalid_framework(self, tmp_path: Path):
        """Error when invalid framework specified."""
        result = await run_tests(framework="invalid_framework", working_dir=str(tmp_path))
        assert "Unknown test framework" in result

    @pytest.mark.asyncio
    async def test_run_tests_success(self, tmp_path: Path):
        """Run tests successfully."""
        # Create pytest config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pytest.ini_options]\naddopts = "-v"')

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(
            return_value=(
                b"============================== 2 passed in 0.05s ==============================",
                b"",
            )
        )
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await run_tests(working_dir=str(tmp_path))

        assert "PASSED" in result
        assert "2 passed" in result

    @pytest.mark.asyncio
    async def test_run_tests_with_failures(self, tmp_path: Path):
        """Run tests with failures."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(
            return_value=(
                b"tests/test_foo.py::test_fail FAILED\n=== 1 passed, 1 failed in 0.1s ===",
                b"",
            )
        )
        mock_process.returncode = 1
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await run_tests(working_dir=str(tmp_path))

        assert "FAILED" in result
        assert "1 failed" in result

    @pytest.mark.asyncio
    async def test_run_tests_timeout(self, tmp_path: Path):
        """Handle test timeout."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = None
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)),
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            result = await run_tests(working_dir=str(tmp_path), timeout=1)

        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_run_tests_runner_not_found(self, tmp_path: Path):
        """Handle missing test runner."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await run_tests(working_dir=str(tmp_path))

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_run_tests_execution_error(self, tmp_path: Path):
        """Handle execution error."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("Permission denied")):
            result = await run_tests(working_dir=str(tmp_path))

        assert "Error running tests" in result
        assert "Permission denied" in result

    @pytest.mark.asyncio
    async def test_run_tests_with_specific_framework(self, tmp_path: Path):
        """Specify framework explicitly."""
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Ran 1 tests in 0.001s\n\nOK", b""))
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await run_tests(framework="unittest", working_dir=str(tmp_path))

        assert "PASSED" in result

    @pytest.mark.asyncio
    async def test_run_tests_verbose_mode(self, tmp_path: Path):
        """Run tests in verbose mode includes raw output."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"====== 1 passed in 0.01s ======", b""))
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await run_tests(verbose=True, working_dir=str(tmp_path))

        assert "Raw Output" in result

    @pytest.mark.asyncio
    async def test_run_tests_combines_stderr(self, tmp_path: Path):
        """Combine stdout and stderr in output."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest]")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(
            return_value=(
                b"====== 1 passed in 0.01s ======",
                b"Some warning message",
            )
        )
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await run_tests(working_dir=str(tmp_path))

        # Summary should still be parsed
        assert "PASSED" in result


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    __test__ = True

    @given(
        passed=st.integers(min_value=0, max_value=100),
        failed=st.integers(min_value=0, max_value=100),
        skipped=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=20)
    def test_summary_totals_are_consistent(self, passed: int, failed: int, skipped: int):
        """Total should equal sum of passed, failed, skipped."""
        total = passed + failed + skipped
        summary = TestSummary(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
        )
        assert summary.total == summary.passed + summary.failed + summary.skipped

    @given(name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
    @settings(max_examples=20)
    def test_test_result_preserves_name(self, name: str):
        """TestResult should preserve the test name."""
        result = TestResult(name=name, status="passed")
        assert result.name == name

    @given(duration=st.floats(min_value=0, max_value=1000, allow_nan=False))
    @settings(max_examples=20)
    def test_summary_duration_preserved(self, duration: float):
        """TestSummary should preserve duration."""
        summary = TestSummary(duration=duration)
        assert summary.duration == duration

    @pytest.mark.asyncio
    @given(
        verbose=st.booleans(),
        coverage=st.booleans(),
        fail_fast=st.booleans(),
    )
    @settings(max_examples=10)
    async def test_build_command_returns_list(self, verbose: bool, coverage: bool, fail_fast: bool):
        """Build command should always return a list."""
        cmd = _build_test_command(
            TestFramework.PYTEST,
            verbose=verbose,
            coverage=coverage,
            fail_fast=fail_fast,
        )
        assert isinstance(cmd, list)
        assert len(cmd) >= 3  # At least "python", "-m", "pytest"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for testing tools."""

    __test__ = True

    @pytest.mark.asyncio
    async def test_detect_and_parse_workflow(self, tmp_path: Path):
        """Test full workflow of detection and parsing."""
        # Create a pytest project
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pytest.ini_options]\naddopts = "-v"')

        # Detect framework
        framework = await detect_test_framework(tmp_path)
        assert framework == TestFramework.PYTEST

        # Build command
        cmd = _build_test_command(framework, verbose=True)
        assert "pytest" in cmd
        assert "-v" in cmd

        # Parse sample output
        output = "============================== 5 passed in 0.1s ==============================="
        summary = await parse_test_output(output, framework)
        assert summary.passed == 5
