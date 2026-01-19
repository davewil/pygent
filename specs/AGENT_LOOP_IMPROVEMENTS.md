# Agent Loop Improvements Plan

## Overview

Four independent improvements to harden the agent loop for production use. Each phase can be implemented and tested independently.

---

## Phase 1: Tool Definition Metadata (read_only, cacheable) ✅ COMPLETED

**Priority:** Highest (foundational refactoring that other improvements may benefit from)

**Goal:** Move `read_only` and `cacheable` properties from hardcoded sets to tool definitions.

**Status:** ✅ Completed 2026-01-19

### Changes Made

1. **`src/pygent/tools/base.py`** ✅
   - Added `read_only: bool = False` field to `ToolDefinition` dataclass
   - Added `cacheable: bool = True` field to `ToolDefinition` dataclass
   - Updated `@tool` decorator to accept `read_only` and `cacheable` parameters
   - Default: `cacheable` defaults to `True` if `read_only=True`, otherwise `False`

2. **`src/pygent/tools/*.py`** (all tool files) ✅
   - Updated each `@tool()` decorator with appropriate `read_only` and `cacheable` values
   - Read-only tools marked with `read_only=True`: `read_file`, `list_files`, `grep_search`, `find_files`, `find_definition`, `git_status`, `git_diff`, `git_log`, `git_branch`, `web_fetch`, `list_templates`, `list_components`
   - Mutation tools marked with `cacheable=False`: `edit_file`, `create_file`, `delete_file`, `move_file`, `copy_file`, `shell`, `git_add`, `git_commit`, `git_checkout`, `git_push`, `git_pull`, `run_tests`, `create_project`, `add_component`

3. **`src/pygent/core/parallel.py`** ✅
   - Removed `READ_ONLY_TOOLS` hardcoded set
   - Updated `is_read_only_tool()` to check `tool_def.read_only` instead of string lookup
   - Updated `execute_single_tool()` to pass `cacheable=tool_def.cacheable` to cache methods

4. **`src/pygent/core/cache.py`** ✅
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

1. **`src/pygent/core/loop.py`** ✅
   - Added `DEFAULT_MAX_ITERATIONS = 50` constant
   - Added `max_iterations: int = DEFAULT_MAX_ITERATIONS` parameter to `conversation_loop()`
   - Added `max_tokens: int | None = None` parameter (None = unlimited)
   - Track iteration count and cumulative token usage per loop
   - Added new `LoopEvent` types: `iteration_limit_reached`, `token_limit_reached`
   - Yield appropriate event and gracefully exit when limits hit
   - Enhanced `LoopEvent` dataclass with: `usage`, `iteration`, `total_tokens` fields
   - All events now include iteration and token tracking info

2. **`src/pygent/core/agent.py`** ✅
   - Added `max_iterations` and `max_tokens` to `Agent.__init__()`
   - Pass limits to `conversation_loop()` via `run()` method

3. **`src/pygent/core/providers.py`** ✅
   - Added `TokenUsage` dataclass with `prompt_tokens`, `completion_tokens`, `total_tokens`
   - Added `usage: TokenUsage | None = None` field to `LLMResponse`
   - Updated `LiteLLMProvider.complete()` to parse token usage from response

4. **`src/pygent/core/mock_provider.py`** ✅
   - Added `_mock_usage()` helper method
   - Added `MOCK_PROMPT_TOKENS` and `MOCK_COMPLETION_TOKENS` constants
   - Updated all `LLMResponse` returns to include `usage=self._mock_usage()`

5. **`src/pygent/config/settings.py`**
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

## Phase 3: LLM Error Handling with Retry Events

**Priority:** Medium (production reliability)

**Goal:** Handle transient LLM errors gracefully, letting the TUI/CLI decide retry behavior.

### Changes

1. **`src/pygent/core/loop.py`**
   - Add new `LoopEvent` types:
     - `llm_error` (with `error_type`, `error_message`, `retryable` fields)
   - Wrap `provider.complete()` in try/except
   - Classify errors:
     - Retryable: rate limits (429), network errors (timeouts, connection)
     - Non-retryable: auth errors (401/403), invalid request (400)
   - Yield `llm_error` event with error details
   - Add mechanism for caller to signal "retry" or "abort"

2. **`src/pygent/core/providers.py`**
   - Create custom exception classes:
     - `LLMError` (base)
     - `RateLimitError`
     - `NetworkError`
     - `AuthError`
   - Wrap litellm exceptions into these typed errors

3. **`src/pygent/core/loop.py`**
   - Add `RetryController` protocol/class that callers can implement
   - Default behavior: yield error event and exit (no auto-retry)

### Tests
- Test rate limit error yields correct event
- Test network error yields correct event
- Test auth error is marked non-retryable
- Test retry mechanism works when controller signals retry

---

## Phase 4: Cancellation Support

**Priority:** Lower (nice to have)

**Goal:** Allow graceful cancellation of agent execution.

### Changes

1. **`src/pygent/core/cancellation.py`** (new file)
   - Create `CancellationToken` class:
     ```python
     class CancellationToken:
         def __init__(self) -> None:
             self._cancelled: bool = False

         def cancel(self) -> None:
             self._cancelled = True

         @property
         def is_cancelled(self) -> bool:
             return self._cancelled
     ```

2. **`src/pygent/core/loop.py`**
   - Add `cancellation_token: CancellationToken | None = None` parameter
   - Check `token.is_cancelled` at start of each iteration
   - Check after tool execution completes (let tools finish)
   - Add `LoopEvent(type="cancelled")` event type
   - Yield cancelled event and exit gracefully

3. **`src/pygent/core/agent.py`**
   - Add `cancellation_token` parameter to `run()`
   - Store reference for external cancellation via `Agent.cancel()`

4. **`src/pygent/core/parallel.py`**
   - Pass cancellation token to batch execution
   - Check between batches (not mid-batch, per Q4.2 decision)

### Tests
- Test cancellation before first iteration
- Test cancellation mid-loop (after tool execution)
- Test running tools complete before cancellation takes effect
- Test cancellation token can be reused after reset

---

## Implementation Order

1. **Phase 1** (Tool Definition Metadata) - ✅ COMPLETED 2026-01-19
2. **Phase 2** (Limits) - ✅ COMPLETED 2026-01-19
3. **Phase 3** (Error Handling) - ⏳ Pending - Production reliability
4. **Phase 4** (Cancellation) - ⏳ Pending - Nice to have

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
