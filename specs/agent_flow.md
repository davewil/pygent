# Agent Loop: Technical Specification

This document provides a detailed breakdown of how the pygent agent loop works, including all core components, execution flow, and supporting systems.

## Overview

The agent loop follows the classic agentic pattern: **LLM → Parse → Execute Tools → Feedback → Repeat**. It runs until the LLM produces a response with no tool calls.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AGENT LOOP FLOW                               │
└─────────────────────────────────────────────────────────────────────────┘

  User Message
       │
       ▼
┌──────────────┐
│   Agent.run  │  ← Entry point (agent.py)
└──────┬───────┘
       │ Appends user message to session
       ▼
┌──────────────────────┐
│  conversation_loop   │  ← Main loop (loop.py)
└──────────┬───────────┘
           │
           ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    MAIN LOOP (while True)                │
    │                                                          │
    │  1. Convert messages to LLM format                       │
    │  2. Prepend system prompt                                │
    │  3. Call LLM with tools                                  │
    │  4. Parse response (TextBlocks + ToolUseBlocks)          │
    │  5. If no tool calls → break (finished)                  │
    │  6. Execute tools (with parallelization)                 │
    │  7. Append results to messages                           │
    │  8. Loop back to step 1                                  │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
           │
           ▼
    yield LoopEvent(type="finished")
```

---

## Core Components

### 1. Agent Class (`core/agent.py`)

The `Agent` orchestrates all components:

```python
class Agent:
    provider: LLMProvider       # litellm wrapper for LLM calls
    tools: ToolRegistry         # Registry of available tools
    permissions: PermissionManager  # Risk-tiered permission system
    session: Session            # Conversation state + history
    tool_cache: ToolCache       # LRU cache with TTL
    system_prompt: str | None   # Optional system prompt
```

**Entry point** (`run` method):
1. Creates a `Message` from user input
2. Appends it to `session.messages`
3. Delegates to `conversation_loop()`, yielding events back to caller

```python
async def run(self, user_message: str) -> AsyncIterator[LoopEvent]:
    # Add user message to session
    msg = Message(role="user", content=user_message)
    self.session.messages.append(msg)

    # Call conversation_loop with system prompt
    async for event in conversation_loop(self, self.session.messages, self.system_prompt):
        yield event
```

---

### 2. Conversation Loop (`core/loop.py`)

The core loop is implemented in `conversation_loop()`.

#### Step 1: Convert Messages to LLM Format

The `_convert_to_llm_messages()` function transforms the internal `Message` model into the format litellm expects:

```python
# Internal model
Message(
    role="assistant",
    content=[
        TextBlock(text="I'll read that file."),
        ToolUseBlock(id="call_123", name="read_file", input={"path": "foo.py"})
    ]
)

# Converted to LLM format
{
    "role": "assistant",
    "content": "I'll read that file.",
    "tool_calls": [
        {
            "id": "call_123",
            "type": "function",
            "function": {"name": "read_file", "arguments": "{\"path\": \"foo.py\"}"}
        }
    ]
}
```

Tool results are converted to `role: "tool"` messages:
```python
{"role": "tool", "tool_call_id": "call_123", "content": "file contents..."}
```

#### Step 2: Prepend System Prompt

```python
if system_prompt:
    llm_msgs = [{"role": "system", "content": system_prompt}] + llm_msgs
```

#### Step 3: Call LLM Provider

```python
# Build tool list from registry
tool_list = []
for tool_info in agent.tools.list_definitions():
    tool_def = agent.tools.get(tool_info["name"])
    if tool_def:
        tool_list.append(tool_def)

# Call LLM
response: LLMResponse = await agent.provider.complete(
    messages=llm_msgs,
    tools=tool_list,
)
```

#### Step 4: Parse Response & Yield Events

The response contains a mix of `TextBlock` and `ToolUseBlock`:

```python
for block in response.content:
    if isinstance(block, ProvTextBlock):
        yield LoopEvent(type="text", content=block.text)
        assistant_blocks.append(TextBlock(text=block.text))

    elif isinstance(block, ProvToolUseBlock):
        yield LoopEvent(type="tool_call", tool_name=block.name, tool_id=block.id)
        assistant_blocks.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
        tool_invocations.append(block)

# Append assistant message to history
messages.append(Message(role="assistant", content=assistant_blocks))
```

#### Step 5: Check for Completion

```python
if not tool_invocations:
    break  # No tools requested → loop ends
```

#### Step 6: Execute Tools with Parallelization

```python
# Build tool calls with definitions
tool_calls: list[tuple[ProvToolUseBlock, ToolDefinition]] = []
for tool_use in tool_invocations:
    tool_def = agent.tools.get(tool_use.name)
    if not tool_def:
        # Handle unknown tool
        result_blocks.append(ToolResultBlock(
            tool_use_id=tool_use.id,
            content=f"Error: Tool {tool_use.name} not found.",
            is_error=True
        ))
    else:
        tool_calls.append((tool_use, tool_def))

# Execute via parallel execution system
results = await execute_tools_parallel(tool_calls, agent)
```

#### Step 7: Yield Results & Append to Messages

```python
for tool_result in results:
    if "Permission denied" in tool_result.result:
        yield LoopEvent(type="permission_denied", ...)
    else:
        yield LoopEvent(type="tool_result", content=tool_result.result, cached=tool_result.was_cached)

    result_blocks.append(ToolResultBlock(
        tool_use_id=tool_result.tool_use_id,
        content=tool_result.result,
        is_error=tool_result.is_error,
    ))

# Append tool results as a message (converted to "tool" role later)
messages.append(Message(role="user", content=result_blocks))
```

---

### 3. LLM Provider (`core/providers.py`)

The `LLMProvider` wraps **litellm** for multi-provider support:

```python
class LLMProvider:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key

    async def complete(self, messages, tools, max_tokens=4096) -> LLMResponse:
        # Format tools for OpenAI-style function calling
        formatted_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                }
            }
            for tool in tools
        ]

        # Call litellm (supports 100+ providers)
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            tools=formatted_tools,
            max_tokens=max_tokens,
        )

        # Parse response into TextBlock/ToolUseBlock
        content = []
        if message.content:
            content.append(TextBlock(text=message.content))
        if message.tool_calls:
            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments)
                content.append(ToolUseBlock(id=tc.id, name=tc.function.name, input=args))

        return LLMResponse(content=content, stop_reason=choice.finish_reason)
```

#### LiteLLM Supported Providers

LiteLLM supports **100+ LLM providers** through a unified OpenAI-compatible API:

| Category | Providers |
|----------|-----------|
| **Commercial APIs** | OpenAI, Anthropic, Google (Gemini/VertexAI), Azure OpenAI, Cohere, xAI (Grok), Mistral |
| **Cloud Platforms** | AWS Bedrock, AWS Sagemaker, Google VertexAI, Azure, OCI GenAI |
| **Inference Platforms** | HuggingFace, Replicate, Together AI, Anyscale, Fireworks AI, Groq, NVIDIA NIM |
| **Local/Self-hosted** | Ollama, vLLM, Llamafile, text-generation-inference |
| **Aggregators** | OpenRouter, CometAPI (500+ models), Bytez, Clarifai |
| **Enterprise** | SAP Generative AI Hub, Novita AI, Vercel AI Gateway |

**Model string examples:**
- `gpt-4o` (OpenAI)
- `claude-sonnet-4-20250514` (Anthropic)
- `gemini/gemini-pro` (Google)
- `ollama/llama3` (local Ollama)
- `bedrock/anthropic.claude-3` (AWS Bedrock)

---

### 4. Parallel Execution System (`core/parallel.py`)

This is where performance optimization happens.

#### Safety Rules

```python
READ_ONLY_TOOLS = frozenset({
    "read_file", "list_files",           # Filesystem reads
    "grep_search", "find_files", "find_definition",  # Search
    "git_status", "git_diff", "git_log", "git_branch",  # Git reads
    "web_fetch",                          # Network (no local side effects)
    "list_templates", "list_components",  # Listing
})
```

- **Read-only tools** → can run in parallel
- **Write tools** → must run sequentially
- **Same-path operations** → must run sequentially (conflict detection)

#### Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PARALLEL EXECUTION PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────┘

  Tool Calls from LLM
       │
       ▼
┌──────────────────────┐
│ prepare_tool_execution│  For each tool call:
│                      │  - Determine if read-only
│                      │  - Extract affected file paths
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  group_into_batches  │  Group into ExecutionBatch objects:
│                      │  - Read-only tools → parallel batch
│                      │  - Write tools → single-item sequential batch
│                      │  - Path conflicts → force sequential
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    BATCH EXECUTION                           │
│                                                              │
│  For each batch:                                             │
│    if batch.can_parallelize:                                 │
│      asyncio.gather(*[execute_single_tool(t) for t in batch])│
│    else:                                                     │
│      for t in batch: await execute_single_tool(t)            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Path Conflict Detection

```python
PATH_ARGUMENTS = frozenset({
    "path", "file_path", "source", "destination", "src", "dest", "directory", "dir"
})

def paths_conflict(paths1: set[str], paths2: set[str]) -> bool:
    # Direct overlap
    if paths1 & paths2:
        return True

    # Parent-child relationships
    for p1 in paths1:
        for p2 in paths2:
            if p1.startswith(p2 + "/") or p2.startswith(p1 + "/"):
                return True

    return False
```

#### Single Tool Execution

```python
async def execute_single_tool(execution, agent) -> ToolResult:
    # 1. Check permissions
    allowed = await agent.permissions.check(
        tool_name=tool_use.name,
        risk=tool_def.risk,
        args=tool_use.input,
    )
    if not allowed:
        return ToolResult(..., result="Error: Permission denied by user.", is_error=True)

    # 2. Check cache
    cached_result = await agent.tool_cache.get(tool_use.name, tool_use.input)
    if cached_result is not None:
        return ToolResult(..., result=cached_result, was_cached=True)

    # 3. Execute tool function
    try:
        output = await tool_def.function(**tool_use.input)
        result = str(output)

        # 4. Cache the result
        await agent.tool_cache.set(tool_use.name, tool_use.input, result)

        return ToolResult(..., result=result, is_error=False)
    except Exception as e:
        return ToolResult(..., result=f"Error: {e}", is_error=True)
```

---

### 5. Permission System (`core/permissions.py`)

Three-tier risk model:

```python
class ToolRisk(str, Enum):
    LOW = "low"      # Auto-approved (read_file, grep_search, etc.)
    MEDIUM = "medium"  # Prompts unless session_override=True (edit_file, git_commit)
    HIGH = "high"    # Always prompts (delete_file, shell, git_push)
```

Permission check flow:
```python
async def check(self, tool_name, risk, args) -> bool:
    if risk == ToolRisk.LOW:
        return True  # Auto-approve

    if risk == ToolRisk.MEDIUM and self.session_override:
        return True  # User toggled "trust mode"

    # MEDIUM (no override) and HIGH → prompt via callback
    return await self.prompt_callback(tool_name, risk, args)
```

#### Risk Level Examples

| Risk Level | Examples | Behavior |
|------------|----------|----------|
| `LOW` | read_file, list_files, grep_search, git_status, git_diff | Auto-approved |
| `MEDIUM` | edit_file, create_file, copy_file, git_add, git_commit | Prompted (unless override) |
| `HIGH` | delete_file, move_file, shell, git_push, git_pull, web_fetch | Always prompted |

---

### 6. Tool Cache (`core/cache.py`)

LRU cache with TTL to avoid redundant operations.

#### Non-Cacheable Tools

```python
NON_CACHEABLE_TOOLS = frozenset({
    # Filesystem mutation tools
    "edit_file", "create_file", "delete_file", "move_file", "copy_file",
    # Git mutation tools
    "git_add", "git_commit", "git_push", "git_pull", "git_checkout",
    # Shell (unknown side effects)
    "shell",
    # Test runner (may have side effects)
    "run_tests",
    # Scaffolding (creates files)
    "create_project", "add_component",
})
```

#### TTL Configuration

```python
DEFAULT_TOOL_TTL = {
    # Short TTL (changes frequently)
    "git_status": 5,
    "git_diff": 5,
    "git_branch": 10,

    # Medium TTL (stable unless files change)
    "git_log": 60,
    "grep_search": 30,
    "find_files": 30,
    "find_definition": 30,
    "read_file": 30,
    "list_files": 30,

    # Longer TTL (static or expensive)
    "web_fetch": 60,
    "list_templates": 300,
    "list_components": 300,
}
```

#### Cache Operations

| Operation | Description |
|-----------|-------------|
| `get(tool_name, args)` | Returns cached result if exists and not expired (LRU bump) |
| `set(tool_name, args, value)` | Stores result with TTL, evicts oldest if at capacity |
| `invalidate(pattern)` | Pattern-based removal (e.g., `"read_file:*"`) |
| `invalidate_tool(tool_name)` | Invalidate all entries for a tool |
| `clear()` | Clear entire cache |
| `cleanup_expired()` | Remove all expired entries |

#### Cache Key Generation

```python
def _generate_key(self, tool_name: str, args: dict[str, Any]) -> str:
    args_json = json.dumps(args, sort_keys=True, default=str)
    args_hash = hashlib.sha256(args_json.encode()).hexdigest()[:16]
    return f"{tool_name}:{args_hash}"
```

---

### 7. Tool Registry & Decorator (`tools/base.py`, `tools/registry.py`)

#### Tool Definition

```python
@dataclass
class ToolDefinition:
    name: str                           # Unique identifier
    description: str                    # Shown to LLM
    input_schema: dict[str, Any]        # JSON Schema for parameters
    risk: ToolRisk                      # Permission level
    category: ToolCategory              # Organization
    function: Callable[..., Awaitable[Any]]  # The actual function
```

#### Tool Decorator

```python
@tool(
    name="read_file",
    description="Read the contents of a file",
    risk=ToolRisk.LOW,
    category=ToolCategory.FILESYSTEM,
)
async def read_file(path: str) -> str:
    async with aiofiles.open(path, "r") as f:
        return await f.read()
```

The decorator:
1. Generates JSON Schema from type hints using Pydantic's `TypeAdapter`
2. Creates a `ToolDefinition` with name, description, schema, risk, category, function
3. Attaches `_tool_definition` to the wrapper function for registry discovery

#### Tool Registry

```python
class ToolRegistry:
    def register(self, tool: ToolDefinition | ToolFunction) -> None: ...
    def get(self, name: str) -> ToolDefinition | None: ...
    def list_definitions(self) -> list[dict[str, Any]]: ...
    def list_all(self) -> list[ToolDefinition]: ...
    def list_by_category(self, category: ToolCategory) -> list[ToolDefinition]: ...
```

---

## Event System

The loop yields `LoopEvent` objects for the UI to consume:

```python
@dataclass
class LoopEvent:
    type: str                    # Event type
    content: str | None          # Event content
    tool_name: str | None        # Tool involved
    tool_id: str | None          # Unique tool call ID
    cached: bool                 # Whether result came from cache
    timestamp: datetime | None   # When the event occurred
```

| Event Type | When | Content |
|------------|------|---------|
| `text` | LLM produces text | The text content |
| `tool_call` | LLM requests a tool | tool_name, tool_id, timestamp |
| `tool_result` | Tool execution completes | result content, cached flag |
| `permission_denied` | User denies permission | tool_name, tool_id |
| `finished` | Loop ends (no more tool calls) | - |

---

## Complete Sequence Diagram

```
User        Agent         Loop          Provider        Parallel        Permission      Cache
  │           │             │              │               │               │              │
  │──message─▶│             │              │               │               │              │
  │           │──run()─────▶│              │               │               │              │
  │           │             │──convert────▶│               │               │              │
  │           │             │◀─llm_msgs────│               │               │              │
  │           │             │──complete()─▶│               │               │              │
  │           │             │              │──litellm.acompletion()        │              │
  │           │             │◀─LLMResponse─│               │               │              │
  │           │◀──text event│              │               │               │              │
  │◀─display──│             │              │               │               │              │
  │           │◀──tool_call │              │               │               │              │
  │◀─display──│             │              │               │               │              │
  │           │             │──execute_tools_parallel()───▶│               │              │
  │           │             │              │               │──check()─────▶│              │
  │           │             │              │               │◀─allowed──────│              │
  │           │             │              │               │──get()────────┼─────────────▶│
  │           │             │              │               │◀─cache miss───┼──────────────│
  │           │             │              │               │──tool_def.function()         │
  │           │             │              │               │──set()────────┼─────────────▶│
  │           │             │◀─ToolResult[]────────────────│               │              │
  │           │◀──tool_result│             │               │               │              │
  │◀─display──│             │              │               │               │              │
  │           │             │──(loop back to convert)      │               │               │
  │           │             │  ...continues until no tools...              │              │
  │           │◀──finished──│              │               │               │              │
  │◀─done─────│             │              │               │               │              │
```

---

## Data Models

### Message Model (`session/models.py`)

```python
class Message:
    role: str                           # "user" | "assistant"
    content: str | list[ContentBlock]   # Text or structured blocks
    timestamp: datetime | None

ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock

class TextBlock:
    text: str

class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]

class ToolResultBlock:
    tool_use_id: str
    content: str
    is_error: bool
```

### Session Model

```python
class Session:
    id: str
    messages: list[Message]
    created_at: datetime
    updated_at: datetime
    working_directory: str
    metadata: dict[str, Any]
```

---

## Architecture Summary

This architecture cleanly separates concerns:

| Component | Responsibility |
|-----------|---------------|
| **Agent** | Orchestration, wiring components together |
| **Loop** | Iteration logic, message conversion, event emission |
| **Provider** | LLM communication abstraction |
| **Parallel** | Performance optimization, safe batching |
| **Permissions** | Safety, user consent |
| **Cache** | Performance, avoiding redundant operations |
| **Registry** | Tool discovery and management |

The design enables:
- **Extensibility**: Add tools via simple decorator
- **Provider flexibility**: Switch LLMs via config
- **Safety**: Risk-tiered permissions protect users
- **Performance**: Parallel execution + caching
- **Testability**: Clean interfaces for mocking

---

*Document Version: 1.0*
*Created: 2025-01-18*
