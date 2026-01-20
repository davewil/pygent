# Agent Loop Improvements Plan

## Overview

Four independent improvements to harden the agent loop for production use. Each phase can be implemented and tested independently.

---

## Phase 1: Tool Definition Metadata (read_only, cacheable) ✅ COMPLETED

**Priority:** Highest (foundational refactoring that other improvements may benefit from)

**Goal:** Move `read_only` and `cacheable` properties from hardcoded sets to tool definitions.

**Status:** ✅ Completed 2026-01-19

### Changes Made

1. **`src/chapgent/tools/base.py`** ✅
   - Added `read_only: bool = False` field to `ToolDefinition` dataclass
   - Added `cacheable: bool = True` field to `ToolDefinition` dataclass
   - Updated `@tool` decorator to accept `read_only` and `cacheable` parameters
   - Default: `cacheable` defaults to `True` if `read_only=True`, otherwise `False`

2. **`src/chapgent/tools/*.py`** (all tool files) ✅
   - Updated each `@tool()` decorator with appropriate `read_only` and `cacheable` values
   - Read-only tools marked with `read_only=True`: `read_file`, `list_files`, `grep_search`, `find_files`, `find_definition`, `git_status`, `git_diff`, `git_log`, `git_branch`, `web_fetch`, `list_templates`, `list_components`
   - Mutation tools marked with `cacheable=False`: `edit_file`, `create_file`, `delete_file`, `move_file`, `copy_file`, `shell`, `git_add`, `git_commit`, `git_checkout`, `git_push`, `git_pull`, `run_tests`, `create_project`, `add_component`

3. **`src/chapgent/core/parallel.py`** ✅
   - Removed `READ_ONLY_TOOLS` hardcoded set
   - Updated `is_read_only_tool()` to check `tool_def.read_only` instead of string lookup
   - Updated `execute_single_tool()` to pass `cacheable=tool_def.cacheable` to cache methods

4. **`src/chapgent/core/cache.py`** ✅
   - Removed `NON_CACHEABLE_TOOLS` hardcoded set
   - Removed `_is_cacheable()` method
   - Updated `get()` and `set()` methods to accept `cacheable: bool = True` parameter

### Tests ✅
- Updated existing tests for new decorator parameters
- Updated mock agent in tests to handle new `cacheable` parameter
- Removed tests for deleted constants

### Learnings
- Adding metadata to tool definitions is cleaner than maintaining separate hardcoded sets
- Default `cacheable=True` when `read_only=True` provides sensible behavior without explicit configuration
- Removing hardcoded sets reduces duplication and keeps tool behavior co-located with definition

---

## Phase 2: Max Iterations & Token Budget Guard ✅ COMPLETED

**Priority:** High (safety feature)

**Goal:** Prevent runaway agents with configurable limits.

**Status:** ✅ Completed 2026-01-19

### Changes Made

1. **`src/chapgent/core/loop.py`** ✅
   - Added `DEFAULT_MAX_ITERATIONS = 50` constant
   - Added `max_iterations: int = DEFAULT_MAX_ITERATIONS` parameter to `conversation_loop()`
   - Added `max_tokens: int | None = None` parameter (None = unlimited)
   - Track iteration count and cumulative token usage per loop
   - Added new `LoopEvent` types: `iteration_limit_reached`, `token_limit_reached`
   - Yield appropriate event and gracefully exit when limits hit
   - Enhanced `LoopEvent` dataclass with: `usage`, `iteration`, `total_tokens` fields
   - All events now include iteration and token tracking info

2. **`src/chapgent/core/agent.py`** ✅
   - Added `max_iterations` and `max_tokens` to `Agent.__init__()`
   - Pass limits to `conversation_loop()` via `run()` method

3. **`src/chapgent/core/providers.py`** ✅
   - Added `TokenUsage` dataclass with `prompt_tokens`, `completion_tokens`, `total_tokens`
   - Added `usage: TokenUsage | None = None` field to `LLMResponse`
   - Updated `LiteLLMProvider.complete()` to parse token usage from response

4. **`src/chapgent/core/mock_provider.py`** ✅
   - Added `_mock_usage()` helper method
   - Added `MOCK_PROMPT_TOKENS` and `MOCK_COMPLETION_TOKENS` constants
   - Updated all `LLMResponse` returns to include `usage=self._mock_usage()`

5. **`src/chapgent/config/settings.py`**
   - ⏳ Deferred: Add `max_iterations` and `max_tokens` to config model (can be done when needed)

### Tests ✅
- Added `TestLoopIterationLimit`: 3 tests for iteration limit functionality
- Added `TestLoopTokenLimit`: 4 tests for token limit functionality
- Added `TestLoopTokenTracking`: 4 tests for usage tracking in events
- All 1323 tests pass

### Learnings
- Token limit check should happen after response (to include that response's tokens) but before processing
- Iteration limit check should happen at start of loop (before making LLM call)
- Events should include both per-iteration usage and cumulative totals for flexibility
- MockLLMProvider needs consistent usage returns for testing limit scenarios
- Graceful exit with descriptive events allows TUI/CLI to inform user appropriately

---

## Phase 3: LLM Error Handling with Retry Events ✅ COMPLETED

**Priority:** Medium (production reliability)

**Goal:** Handle transient LLM errors gracefully, letting the TUI/CLI decide retry behavior.

**Status:** ✅ Completed 2026-01-19

### Changes Made

1. **`src/chapgent/core/providers.py`** ✅
   - Created custom exception class hierarchy:
     - `LLMError` (base) - with message, retryable, status_code, original_error attributes
     - `RateLimitError` - retryable=True, status_code=429, optional retry_after
     - `NetworkError` - retryable=True, status_code=None
     - `AuthenticationError` - retryable=False, status_code=401
     - `InvalidRequestError` - retryable=False, status_code=400
     - `ServiceUnavailableError` - retryable=True, status_code=503
   - Implemented `classify_llm_error()` function:
     - Checks litellm-specific exception types first
     - Falls back to message pattern matching for error classification
     - Patterns include: rate limit, network, auth, service unavailable
     - Preserves original_error for debugging

2. **`src/chapgent/core/loop.py`** ✅
   - Added new `LoopEvent` fields: `error_type`, `error_message`, `retryable`
   - Wrapped `provider.complete()` in try/except block
   - Yields `llm_error` event on exception with:
     - error_type: Exception class name
     - error_message: Human-readable message
     - retryable: Boolean flag for retry decision
     - iteration and total_tokens for context
   - Default behavior: yield error event and exit loop (caller decides retry)

### Tests ✅
- `tests/test_core/test_providers_errors.py` (new file) - 30 tests:
  - TestLLMExceptionClasses: 9 tests for exception hierarchy
  - TestClassifyLLMError: 14 tests for error classification
  - TestPropertyBasedErrors: 4 property-based tests
  - TestEdgeCases: 4 edge case tests
- `tests/test_core/test_loop.py` - 8 new tests added:
  - TestLoopErrorHandling: rate limit, auth, network, invalid request, service unavailable errors
  - Tests for error event fields and retryable flag

### Learnings
- litellm has its own exception types that should be checked first
- Message pattern matching provides fallback classification for generic exceptions
- Preserving original_error allows callers to inspect the underlying cause
- Exit-on-error with retryable flag lets TUI/CLI implement retry UI
- Classification should be case-insensitive for robustness

---

## Phase 4: Cancellation Support ✅ COMPLETED

**Priority:** Lower (nice to have)

**Goal:** Allow graceful cancellation of agent execution.

**Status:** ✅ Completed 2026-01-19

### Changes Made

1. **`src/chapgent/core/cancellation.py`** (new file) ✅
   - Created `CancellationToken` class with:
     - `_cancelled`, `_cancel_time`, `_reason` fields
     - `_event` (asyncio.Event) for async waiting
     - `cancel(reason)` method - idempotent, sets timestamp and reason
     - `is_cancelled`, `cancel_time`, `reason` properties
     - `reset()` method for token reuse
     - `wait_for_cancellation(timeout)` async method
     - `raise_if_cancelled()` method that raises CancellationError
   - Created `CancellationError` exception class

2. **`src/chapgent/core/loop.py`** ✅
   - Added `cancellation_token: CancellationToken | None = None` parameter to `conversation_loop()`
   - Added `cancel_reason: str | None = None` field to `LoopEvent`
   - Check `token.is_cancelled` at start of each iteration
   - Check after tool execution completes (let tools finish)
   - Yield `LoopEvent(type="cancelled")` with cancel_reason on cancellation
   - Pass cancellation_token to `execute_tools_parallel()`

3. **`src/chapgent/core/agent.py`** ✅
   - Added `_cancellation_token` private attribute
   - Added `cancel(reason)` method for external cancellation
   - Added `is_cancelled` property to check cancellation state
   - Create fresh CancellationToken at start of each `run()`
   - Pass token to `conversation_loop()`
   - Clear token in finally block after run completes

4. **`src/chapgent/core/parallel.py`** ✅
   - Added `cancellation_token` parameter to `execute_tools_parallel()`
   - Check cancellation between batches (not mid-batch)
   - Return partial results for completed batches if cancelled

### Tests ✅
- `tests/test_core/test_cancellation.py` (new file) - 32 tests:
  - TestCancellationToken: 7 tests for token state management
  - TestCancellationTokenRaiseIfCancelled: 3 tests for raise_if_cancelled
  - TestCancellationTokenWaitForCancellation: 3 async tests for waiting
  - TestCancellationError: 3 tests for exception class
  - TestCancellationTokenInLoopEvent: 2 tests for LoopEvent fields
  - TestCancellationInConversationLoop: 2 async tests for loop cancellation
  - TestCancellationInAgent: 3 tests for Agent.cancel()
  - TestCancellationInParallel: 2 tests for parallel execution
  - TestPropertyBasedCancellation: 2 hypothesis tests
  - TestEdgeCases: 4 tests for edge cases
  - TestIntegration: 1 full integration test

### Learnings
- asyncio.Event provides clean async coordination for cancellation
- Cancellation should be checked at safe points (iteration start, between batches)
- Let running tools complete before checking cancellation for clean state
- Fresh token per run() prevents stale cancellation state
- Idempotent cancel() prevents race conditions with multiple callers

---

## Implementation Order

1. **Phase 1** (Tool Definition Metadata) - ✅ COMPLETED 2026-01-19
2. **Phase 2** (Limits) - ✅ COMPLETED 2026-01-19
3. **Phase 3** (Error Handling) - ✅ COMPLETED 2026-01-19
4. **Phase 4** (Cancellation) - ✅ COMPLETED 2026-01-19

## Notes

- Each phase should include tests before merging
- Each phase should maintain backward compatibility where possible
- Update README.md code standards section if new patterns emerge

## Summary of Completed Work

### Phase 1 Results
- **Files Modified:** 9 (base.py, parallel.py, cache.py, filesystem.py, git.py, search.py, shell.py, web.py, testing.py, scaffold.py)
- **Tests Updated:** Removed references to deleted constants, updated mock agents
- **Pattern:** Tool metadata lives with tool definition, not in separate hardcoded sets

### Phase 2 Results
- **Files Modified:** 5 (loop.py, agent.py, providers.py, mock_provider.py, test_loop.py)
- **New Features:** Token tracking, iteration limits, graceful exit events
- **Tests Added:** 11 new tests for limits and tracking
- **Pattern:** Limits checked at loop boundaries with descriptive events for UI handling

### Phase 3 Results
- **Files Modified:** 2 (loop.py, providers.py)
- **Files Created:** 1 (tests/test_core/test_providers_errors.py)
- **New Features:** LLM exception hierarchy, error classification, llm_error event type
- **Tests Added:** 38 new tests (30 in test_providers_errors.py, 8 in test_loop.py)
- **Pattern:** Classify errors into typed exceptions with retryable flag, yield event and exit for caller to decide retry

### Phase 4 Results
- **Files Created:** 2 (cancellation.py, tests/test_core/test_cancellation.py)
- **Files Modified:** 3 (loop.py, agent.py, parallel.py)
- **New Features:** CancellationToken class, Agent.cancel() method, "cancelled" LoopEvent type
- **Tests Added:** 32 new tests for cancellation system
- **Pattern:** Check cancellation at safe points (iteration start, between batches), let running operations complete

### Test Coverage Enhancement (2026-01-19)
- **loop.py coverage improved from 96% to 100%**
- **6 new tests added** to test_loop.py:
  - `TestLoopSystemPrompt`: 3 tests for system prompt handling
    - Verifies system prompt prepended to LLM messages
    - Verifies no system message when prompt is None
    - Verifies system prompt preserved across multiple iterations
  - `TestLoopCancellationAfterTools`: 3 tests for post-tool cancellation
    - Verifies cancellation after tools still appends results to messages
    - Verifies cancelled event content message
    - Verifies iteration and token count in cancelled event
- **Total test_loop.py tests:** 36 (up from 30)
- **Learnings:**
  - System prompt must be tested explicitly since it's injected at conversation_loop level
  - Cancellation after tool execution is a distinct code path from cancellation at iteration start
  - Testing message state preservation ensures consistent conversation history
