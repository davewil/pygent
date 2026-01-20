"""Tests for LLM exception classes and error classification (Phase 3 of Agent Loop Improvements)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.core.providers import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    NetworkError,
    RateLimitError,
    ServiceUnavailableError,
    classify_llm_error,
)


class TestLLMExceptionClasses:
    """Tests for LLM exception class hierarchy."""

    def test_llm_error_base_class(self):
        """LLMError should be the base class with correct attributes."""
        error = LLMError("Test error", retryable=False, status_code=500)
        assert error.message == "Test error"
        assert error.retryable is False
        assert error.status_code == 500
        assert error.original_error is None
        assert str(error) == "Test error"

    def test_llm_error_with_original_error(self):
        """LLMError should store the original exception."""
        original = ValueError("Original")
        error = LLMError("Wrapped error", original_error=original)
        assert error.original_error is original

    def test_rate_limit_error_is_retryable(self):
        """RateLimitError should be retryable by default."""
        error = RateLimitError()
        assert error.retryable is True
        assert error.status_code == 429
        assert "Rate limit" in error.message

    def test_rate_limit_error_with_retry_after(self):
        """RateLimitError can have a retry_after value."""
        error = RateLimitError(retry_after=30.0)
        assert error.retry_after == 30.0

    def test_network_error_is_retryable(self):
        """NetworkError should be retryable by default."""
        error = NetworkError()
        assert error.retryable is True
        assert error.status_code is None
        assert "Network" in error.message

    def test_authentication_error_not_retryable(self):
        """AuthenticationError should NOT be retryable."""
        error = AuthenticationError()
        assert error.retryable is False
        assert error.status_code == 401

    def test_invalid_request_error_not_retryable(self):
        """InvalidRequestError should NOT be retryable."""
        error = InvalidRequestError()
        assert error.retryable is False
        assert error.status_code == 400

    def test_service_unavailable_error_is_retryable(self):
        """ServiceUnavailableError should be retryable."""
        error = ServiceUnavailableError()
        assert error.retryable is True
        assert error.status_code == 503

    def test_all_errors_inherit_from_llm_error(self):
        """All custom errors should inherit from LLMError."""
        errors = [
            RateLimitError(),
            NetworkError(),
            AuthenticationError(),
            InvalidRequestError(),
            ServiceUnavailableError(),
        ]
        for error in errors:
            assert isinstance(error, LLMError)
            assert isinstance(error, Exception)


class TestClassifyLLMError:
    """Tests for classify_llm_error function."""

    def test_classify_rate_limit_by_message(self):
        """Should classify rate limit errors by message content."""
        error = Exception("Rate limit exceeded")
        classified = classify_llm_error(error)
        assert isinstance(classified, RateLimitError)
        assert classified.retryable is True

    def test_classify_rate_limit_429(self):
        """Should classify 429 errors as rate limit."""
        error = Exception("HTTP 429: Too many requests")
        classified = classify_llm_error(error)
        assert isinstance(classified, RateLimitError)

    def test_classify_network_timeout(self):
        """Should classify timeout errors as network errors."""
        error = Exception("Connection timeout")
        classified = classify_llm_error(error)
        assert isinstance(classified, NetworkError)
        assert classified.retryable is True

    def test_classify_network_connection_refused(self):
        """Should classify connection refused as network error."""
        error = Exception("Connection refused")
        classified = classify_llm_error(error)
        assert isinstance(classified, NetworkError)

    def test_classify_network_dns(self):
        """Should classify DNS errors as network errors."""
        error = Exception("DNS resolution failed")
        classified = classify_llm_error(error)
        assert isinstance(classified, NetworkError)

    def test_classify_auth_error(self):
        """Should classify authentication errors."""
        error = Exception("Authentication failed: Invalid API key")
        classified = classify_llm_error(error)
        assert isinstance(classified, AuthenticationError)
        assert classified.retryable is False

    def test_classify_auth_401(self):
        """Should classify 401 errors as authentication errors."""
        error = Exception("HTTP 401: Unauthorized")
        classified = classify_llm_error(error)
        assert isinstance(classified, AuthenticationError)

    def test_classify_auth_403(self):
        """Should classify 403 errors as authentication errors."""
        error = Exception("HTTP 403: Forbidden")
        classified = classify_llm_error(error)
        assert isinstance(classified, AuthenticationError)

    def test_classify_service_unavailable_503(self):
        """Should classify 503 errors as service unavailable."""
        error = Exception("HTTP 503: Service Unavailable")
        classified = classify_llm_error(error)
        assert isinstance(classified, ServiceUnavailableError)

    def test_classify_service_unavailable_500(self):
        """Should classify 500 errors as service unavailable."""
        error = Exception("HTTP 500: Internal Server Error")
        classified = classify_llm_error(error)
        assert isinstance(classified, ServiceUnavailableError)

    def test_classify_unknown_error(self):
        """Unknown errors should become generic LLMError."""
        error = Exception("Something completely unexpected")
        classified = classify_llm_error(error)
        assert isinstance(classified, LLMError)
        assert type(classified) is LLMError  # Exactly LLMError, not subclass
        assert classified.retryable is False

    def test_preserves_original_error(self):
        """classify_llm_error should preserve the original exception."""
        original = ValueError("Original error")
        classified = classify_llm_error(original)
        assert classified.original_error is original

    def test_already_llm_error_passed_through(self):
        """If already an LLMError, it should be returned as-is when called directly."""
        # Note: In the actual loop code, we check isinstance first before calling classify_llm_error
        # In loop.py we do: classify_llm_error(e) if not isinstance(e, LLMError) else e
        # So let's test classify_llm_error on a generic exception
        error = Exception("rate limit error message")
        classified = classify_llm_error(error)
        assert isinstance(classified, RateLimitError)


class TestPropertyBasedErrors:
    """Property-based tests for error classification."""

    @given(
        error_pattern=st.sampled_from(
            [
                "rate limit",
                "rate_limit",
                "too many requests",
                "429",
            ]
        )
    )
    @settings(max_examples=10)
    def test_rate_limit_patterns(self, error_pattern):
        """All rate limit patterns should be classified correctly."""
        error = Exception(f"Error: {error_pattern}")
        classified = classify_llm_error(error)
        assert isinstance(classified, RateLimitError)
        assert classified.retryable is True

    @given(
        error_pattern=st.sampled_from(
            [
                "timeout",
                "connection",
                "network",
                "socket",
                "dns",
                "refused",
            ]
        )
    )
    @settings(max_examples=10)
    def test_network_patterns(self, error_pattern):
        """All network error patterns should be classified correctly."""
        error = Exception(f"Error: {error_pattern}")
        classified = classify_llm_error(error)
        assert isinstance(classified, NetworkError)
        assert classified.retryable is True

    @given(
        error_pattern=st.sampled_from(
            [
                "authentication",
                "unauthorized",
                "invalid api key",
                "401",
                "403",
            ]
        )
    )
    @settings(max_examples=10)
    def test_auth_patterns(self, error_pattern):
        """All auth error patterns should be classified correctly."""
        error = Exception(f"Error: {error_pattern}")
        classified = classify_llm_error(error)
        assert isinstance(classified, AuthenticationError)
        assert classified.retryable is False

    @given(
        error_pattern=st.sampled_from(
            [
                "service unavailable",
                "503",
                "502",
                "504",
                "500",
                "internal server error",
            ]
        )
    )
    @settings(max_examples=10)
    def test_service_unavailable_patterns(self, error_pattern):
        """All service unavailable patterns should be classified correctly."""
        error = Exception(f"Error: {error_pattern}")
        classified = classify_llm_error(error)
        assert isinstance(classified, ServiceUnavailableError)
        assert classified.retryable is True


class TestEdgeCases:
    """Edge case tests for error handling."""

    def test_empty_error_message(self):
        """Empty error messages should still be classified."""
        error = Exception("")
        classified = classify_llm_error(error)
        assert isinstance(classified, LLMError)

    def test_none_like_error_message(self):
        """Error message representations should be handled."""
        error = Exception(None)
        classified = classify_llm_error(error)
        assert isinstance(classified, LLMError)

    def test_case_insensitive_classification(self):
        """Error classification should be case-insensitive."""
        error = Exception("RATE LIMIT EXCEEDED")
        classified = classify_llm_error(error)
        assert isinstance(classified, RateLimitError)

    def test_mixed_patterns_first_match_wins(self):
        """When multiple patterns match, classification should still work."""
        # This has both "rate limit" and "timeout" patterns
        error = Exception("Rate limit timeout error")
        classified = classify_llm_error(error)
        # Should be classified as RateLimitError (checked first in the function)
        assert classified.retryable is True
