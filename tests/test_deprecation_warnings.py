"""Deprecation warnings tests for chapgent (Phase 4 Non-Functional Criteria).

These tests verify that chapgent code runs cleanly without deprecation warnings.
Tests are run with warnings treated as errors to catch any issues.
"""

import subprocess
import sys
import warnings

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


class TestNoDeprecationWarnings:
    """Test that no deprecation warnings are emitted during normal operation."""

    def test_import_core_modules_no_warnings(self):
        """Verify importing core modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            # Import all core modules
            import chapgent.core.agent  # noqa: F401
            import chapgent.core.cache  # noqa: F401
            import chapgent.core.logging  # noqa: F401
            import chapgent.core.loop  # noqa: F401
            import chapgent.core.parallel  # noqa: F401
            import chapgent.core.permissions  # noqa: F401
            import chapgent.core.providers  # noqa: F401
            import chapgent.core.recovery  # noqa: F401

            # Filter to only our deprecation warnings (not from dependencies)
            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_tools_no_warnings(self):
        """Verify importing tool modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.tools.base  # noqa: F401
            import chapgent.tools.filesystem  # noqa: F401
            import chapgent.tools.git  # noqa: F401
            import chapgent.tools.registry  # noqa: F401
            import chapgent.tools.scaffold  # noqa: F401
            import chapgent.tools.search  # noqa: F401
            import chapgent.tools.shell  # noqa: F401
            import chapgent.tools.testing  # noqa: F401
            import chapgent.tools.web  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_config_no_warnings(self):
        """Verify importing config modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.config.loader  # noqa: F401
            import chapgent.config.prompt  # noqa: F401
            import chapgent.config.settings  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_tui_no_warnings(self):
        """Verify importing TUI modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.tui.app  # noqa: F401
            import chapgent.tui.widgets  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_session_no_warnings(self):
        """Verify importing session modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.session.models  # noqa: F401
            import chapgent.session.storage  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_context_no_warnings(self):
        """Verify importing context modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.context.detection  # noqa: F401
            import chapgent.context.models  # noqa: F401
            import chapgent.context.prompt  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_ux_no_warnings(self):
        """Verify importing UX modules produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.ux.first_run  # noqa: F401
            import chapgent.ux.help  # noqa: F401
            import chapgent.ux.messages  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))

    def test_import_cli_no_warnings(self):
        """Verify importing CLI module produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            import chapgent.cli  # noqa: F401

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))


class TestSubprocessWarnings:
    """Test CLI invocation with strict warning mode."""

    def test_cli_help_no_deprecation_warnings(self):
        """Verify 'chapgent --help' emits no deprecation warnings."""
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::DeprecationWarning",
                "-m",
                "chapgent.cli",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed without deprecation warnings causing errors
        assert result.returncode == 0, (
            f"CLI failed with deprecation warnings.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_cli_version_no_deprecation_warnings(self):
        """Verify 'chapgent --version' emits no deprecation warnings."""
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::DeprecationWarning",
                "-m",
                "chapgent.cli",
                "--version",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"CLI failed with deprecation warnings.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_cli_tools_no_deprecation_warnings(self):
        """Verify 'chapgent tools' emits no deprecation warnings."""
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::DeprecationWarning",
                "-m",
                "chapgent.cli",
                "tools",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"CLI failed with deprecation warnings.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_cli_config_show_no_deprecation_warnings(self):
        """Verify 'chapgent config show' emits no deprecation warnings."""
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::DeprecationWarning",
                "-m",
                "chapgent.cli",
                "config",
                "show",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"CLI failed with deprecation warnings.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestToolRuntimeWarnings:
    """Test tool execution doesn't produce deprecation warnings."""

    @pytest.mark.asyncio
    async def test_read_file_no_warnings(self, tmp_path):
        """Verify read_file produces no warnings."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.tools.filesystem import read_file

            await read_file(str(test_file))

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0, f"Warnings: {our_warnings}"

    @pytest.mark.asyncio
    async def test_list_files_no_warnings(self, tmp_path):
        """Verify list_files produces no warnings."""
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()

        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.tools.filesystem import list_files

            await list_files(str(tmp_path))

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0, f"Warnings: {our_warnings}"

    @pytest.mark.asyncio
    async def test_shell_no_warnings(self):
        """Verify shell tool produces no warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.tools.shell import shell

            await shell("echo test")

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0, f"Warnings: {our_warnings}"


class TestPydanticModelWarnings:
    """Test Pydantic model operations don't produce deprecation warnings."""

    def test_settings_creation_no_warnings(self):
        """Verify Settings model creation produces no warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.config.settings import Settings

            settings = Settings()
            _ = settings.model_dump()

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0, f"Warnings: {our_warnings}"

    def test_session_model_no_warnings(self):
        """Verify Session model operations produce no warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.session.models import Message, Session

            session = Session(
                id="test",
                messages=[Message(role="user", content="hello")],
            )
            _ = session.model_dump()

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0, f"Warnings: {our_warnings}"


class TestPropertyBased:
    """Property-based tests for deprecation warnings."""

    @given(content=st.text(min_size=1, max_size=100))
    @settings(max_examples=10)
    def test_message_model_no_warnings_with_various_content(self, content):
        """Verify Message model handles various content without warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            from chapgent.session.models import Message

            msg = Message(role="user", content=content)
            _ = msg.model_dump()

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            assert len(our_warnings) == 0


class TestIntegration:
    """Integration tests for warning-free operation."""

    @pytest.mark.asyncio
    async def test_full_import_chain_no_warnings(self):
        """Verify full import chain produces no deprecation warnings."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always", DeprecationWarning)

            # Import the main package

            # Access key components
            from chapgent.tools.registry import ToolRegistry

            # Create instances
            _ = ToolRegistry()

            our_warnings = [w for w in caught_warnings if "chapgent" in str(w.filename).lower()]

            if our_warnings:
                warning_msgs = [f"{w.filename}:{w.lineno}: {w.message}" for w in our_warnings]
                pytest.fail("Deprecation warnings found:\n" + "\n".join(warning_msgs))
