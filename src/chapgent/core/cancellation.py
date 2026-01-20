"""Cancellation support for agent execution.

This module provides a CancellationToken class that allows graceful
cancellation of long-running agent operations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CancellationToken:
    """Token for signaling cancellation of agent execution.

    The token can be shared across multiple coroutines and checked
    at safe points to determine if cancellation was requested.

    Attributes:
        _cancelled: Internal flag indicating cancellation was requested.
        _cancel_time: When cancellation was requested (None if not cancelled).
        _reason: Optional reason for cancellation.

    Example:
        token = CancellationToken()

        # In one coroutine:
        async def long_running_task(token):
            while not token.is_cancelled:
                await do_work()

        # In another coroutine (or signal handler):
        token.cancel(reason="User requested stop")
    """

    _cancelled: bool = field(default=False, repr=False)
    _cancel_time: datetime | None = field(default=None, repr=False)
    _reason: str | None = field(default=None, repr=False)
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def cancel(self, reason: str | None = None) -> None:
        """Request cancellation.

        This method is idempotent - calling it multiple times has no
        additional effect after the first call.

        Args:
            reason: Optional human-readable reason for cancellation.
        """
        if not self._cancelled:
            self._cancelled = True
            self._cancel_time = datetime.now()
            self._reason = reason
            self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested.

        Returns:
            True if cancel() was called, False otherwise.
        """
        return self._cancelled

    @property
    def cancel_time(self) -> datetime | None:
        """Get the time when cancellation was requested.

        Returns:
            The datetime when cancel() was called, or None if not cancelled.
        """
        return self._cancel_time

    @property
    def reason(self) -> str | None:
        """Get the reason for cancellation.

        Returns:
            The reason string passed to cancel(), or None.
        """
        return self._reason

    def reset(self) -> None:
        """Reset the token for reuse.

        This clears the cancelled state and allows the token to be
        used for a new operation. Use with caution - ensure no
        coroutines are still checking this token.
        """
        self._cancelled = False
        self._cancel_time = None
        self._reason = None
        self._event.clear()

    async def wait_for_cancellation(self, timeout: float | None = None) -> bool:
        """Wait until cancellation is requested.

        This is useful for background tasks that should run until
        explicitly cancelled.

        Args:
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            True if cancelled, False if timeout occurred.
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def raise_if_cancelled(self) -> None:
        """Raise CancellationError if cancellation was requested.

        This provides an alternative to checking is_cancelled manually.

        Raises:
            CancellationError: If cancel() was called.
        """
        if self._cancelled:
            raise CancellationError(self._reason)


class CancellationError(Exception):
    """Exception raised when an operation is cancelled.

    Attributes:
        reason: The reason for cancellation, if provided.
    """

    def __init__(self, reason: str | None = None) -> None:
        """Initialize CancellationError.

        Args:
            reason: Optional reason for the cancellation.
        """
        self.reason = reason
        message = f"Operation cancelled: {reason}" if reason else "Operation cancelled"
        super().__init__(message)
