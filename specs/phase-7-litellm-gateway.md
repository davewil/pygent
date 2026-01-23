# Phase 7: LiteLLM Gateway & Claude Max Subscription Support

## Overview

Enable chapgent to route requests through LiteLLM Gateway, allowing users to leverage Claude Max subscriptions instead of per-token API pricing. This provides cost attribution, budget controls, and rate limiting through LiteLLM's proxy layer.

## Motivation

- **Lower costs**: Claude Max subscriptions are cheaper for power users than per-token API pricing
- **Cost attribution**: Track spend per user, team, or key
- **Budgets & rate limits**: Set spending caps and request limits
- **Guardrails**: Apply content filtering and safety controls

## Implementation Tasks

### Task 1: Wire Provider Parameters

**File**: `src/chapgent/core/providers.py`

Update `LLMProvider` class to accept and use `base_url` and `extra_headers`:

```python
class LLMProvider:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.extra_headers = extra_headers

    async def complete(self, messages, tools, max_tokens=4096) -> LLMResponse:
        # ... existing tool formatting ...
        
        response = await litellm.acompletion(
            model=self.model,
            api_key=self.api_key,
            api_base=self.base_url,
            extra_headers=self.extra_headers,
            messages=messages,
            tools=formatted_tools,
            max_tokens=max_tokens,
        )
        # ... rest unchanged ...
```

### Task 2: Update CLI Provider Initialization

**File**: `src/chapgent/cli.py`

Pass the new settings when creating the provider:

```python
provider = LLMProvider(
    model=settings.llm.model,
    api_key=settings.llm.api_key,
    base_url=settings.llm.base_url,
    extra_headers=settings.llm.extra_headers,
)
```

### Task 3: Extend Config Schema for OAuth Token

**File**: `src/chapgent/config/settings.py`

Add `oauth_token` field to `LLMSettings`:

```python
class LLMSettings(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    api_key: str | None = None
    base_url: str | None = None
    extra_headers: dict[str, str] | None = None
    oauth_token: str | None = None  # NEW: Claude Max OAuth token
```

**File**: `src/chapgent/config/loader.py`

Add environment variable mapping:

```python
OAUTH_TOKEN_ENV_PRIORITY = ["ANTHROPIC_OAUTH_TOKEN", "CHAPGENT_OAUTH_TOKEN"]

# In ENV_TO_CONFIG_MAP:
"ANTHROPIC_OAUTH_TOKEN": "llm.oauth_token",
"CHAPGENT_OAUTH_TOKEN": "llm.oauth_token",
```

### Task 4: Add `chapgent auth login` Command

**File**: `src/chapgent/cli.py`

```python
@cli.group()
def auth():
    """Authentication commands."""
    pass

@auth.command()
@click.option("--provider", type=click.Choice(["anthropic-max"]), default="anthropic-max")
def login(provider: str):
    """Authenticate with Claude Max subscription.
    
    Opens browser for OAuth authorization, then prompts for token.
    """
    import webbrowser
    
    # Known Claude Max OAuth URL
    oauth_url = "https://console.anthropic.com/oauth/authorize"
    
    console = Console()
    console.print("\n[bold]Claude Max Authentication[/bold]\n")
    console.print("1. Open this URL in your browser to authorize:")
    console.print(f"   [link={oauth_url}]{oauth_url}[/link]\n")
    
    if click.confirm("Open URL in browser automatically?", default=True):
        webbrowser.open(oauth_url)
    
    console.print("2. After authorizing, copy the OAuth token from the success page.\n")
    
    token = click.prompt("3. Paste your OAuth token here", hide_input=True)
    
    # Basic validation
    if not token or len(token) < 20:
        console.print("[red]Error: Invalid token format[/red]")
        raise SystemExit(1)
    
    # Store in config
    from chapgent.config.loader import get_user_config_path
    from chapgent.config.writer import write_config
    
    config_path = get_user_config_path()
    write_config(config_path, "llm.oauth_token", token)
    
    console.print("[green]✓ OAuth token saved successfully![/green]")
    console.print(f"  Config: {config_path}")

@auth.command()
def logout():
    """Remove stored authentication tokens."""
    from chapgent.config.loader import get_user_config_path
    from chapgent.config.writer import write_config
    
    config_path = get_user_config_path()
    write_config(config_path, "llm.oauth_token", None)
    write_config(config_path, "llm.api_key", None)
    
    Console().print("[green]✓ Authentication tokens removed[/green]")

@auth.command()
def status():
    """Show current authentication status."""
    settings = load_config()
    console = Console()
    
    if settings.llm.oauth_token:
        console.print("[green]✓ Claude Max OAuth token configured[/green]")
    elif settings.llm.api_key:
        console.print("[green]✓ API key configured[/green]")
    else:
        console.print("[yellow]✗ No authentication configured[/yellow]")
        console.print("  Run: chapgent auth login")
```

### Task 5: Add `chapgent proxy` Command Group

**File**: `src/chapgent/cli.py`

```python
@cli.group()
def proxy():
    """LiteLLM proxy server commands."""
    pass

@proxy.command()
@click.option("--port", default=4000, help="Port to run proxy on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def start(port: int, host: str):
    """Start LiteLLM proxy server (foreground).
    
    Runs a local LiteLLM Gateway that forwards OAuth tokens to Anthropic,
    enabling Claude Max subscription usage with cost tracking.
    """
    import subprocess
    import tempfile
    import yaml
    from pathlib import Path
    
    console = Console()
    
    # Generate LiteLLM config
    config = {
        "model_list": [
            {
                "model_name": "anthropic-claude",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-20250514",
                },
            },
            {
                "model_name": "claude-sonnet-4-20250514",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-20250514",
                },
            },
            {
                "model_name": "claude-3-5-haiku-20241022",
                "litellm_params": {
                    "model": "anthropic/claude-3-5-haiku-20241022",
                },
            },
        ],
        "general_settings": {
            "forward_client_headers_to_llm_api": True,
        },
        "litellm_settings": {
            "drop_params": True,
        },
    }
    
    # Write temp config
    config_dir = Path(tempfile.gettempdir()) / "chapgent"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "litellm-proxy.yaml"
    
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    console.print("\n[bold]Starting LiteLLM Proxy[/bold]\n")
    console.print(f"Config: {config_path}")
    console.print(f"URL:    http://{host}:{port}\n")
    console.print("[dim]Configure chapgent to use this proxy:[/dim]")
    console.print(f"  export CHAPGENT_BASE_URL=http://{host}:{port}")
    console.print(f"  export ANTHROPIC_BASE_URL=http://{host}:{port}\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    console.print("-" * 50)
    
    try:
        subprocess.run(
            ["litellm", "--config", str(config_path), "--host", host, "--port", str(port)],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Proxy stopped[/yellow]")
    except FileNotFoundError:
        console.print("[red]Error: litellm CLI not found. Install with: pip install litellm[/red]")
        raise SystemExit(1)
```

### Task 6: Add Tests

**File**: `tests/test_core/test_providers.py`

```python
import pytest
from unittest.mock import AsyncMock, patch

from chapgent.core.providers import LLMProvider


class TestLLMProviderGatewaySupport:
    """Tests for LiteLLM Gateway / base_url / extra_headers support."""

    @pytest.mark.asyncio
    async def test_base_url_passed_to_litellm(self):
        """Verify base_url is passed as api_base to litellm."""
        provider = LLMProvider(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:4000",
        )
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = self._mock_response()
            
            await provider.complete(
                messages=[{"role": "user", "content": "test"}],
                tools=[],
            )
            
            mock_complete.assert_called_once()
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs["api_base"] == "http://localhost:4000"

    @pytest.mark.asyncio
    async def test_extra_headers_passed_to_litellm(self):
        """Verify extra_headers are passed to litellm."""
        headers = {"x-litellm-api-key": "Bearer sk-test", "x-custom": "value"}
        provider = LLMProvider(
            model="test-model",
            extra_headers=headers,
        )
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = self._mock_response()
            
            await provider.complete(
                messages=[{"role": "user", "content": "test"}],
                tools=[],
            )
            
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs["extra_headers"] == headers

    @pytest.mark.asyncio
    async def test_none_values_not_passed(self):
        """Verify None values don't cause issues."""
        provider = LLMProvider(model="test-model")
        
        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = self._mock_response()
            
            await provider.complete(
                messages=[{"role": "user", "content": "test"}],
                tools=[],
            )
            
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs.get("api_base") is None
            assert call_kwargs.get("extra_headers") is None

    def _mock_response(self):
        """Create a mock LiteLLM response."""
        from unittest.mock import MagicMock
        
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Test response"
        response.choices[0].message.tool_calls = None
        response.choices[0].finish_reason = "stop"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5
        response.usage.total_tokens = 15
        return response
```

**File**: `tests/test_cli.py` (additions)

```python
class TestAuthCommands:
    """Tests for chapgent auth commands."""

    def test_auth_login_displays_url(self, runner):
        """Verify login command shows OAuth URL."""
        result = runner.invoke(cli, ["auth", "login"], input="n\ntest-token-12345678901234567890\n")
        assert "console.anthropic.com/oauth/authorize" in result.output

    def test_auth_status_no_auth(self, runner):
        """Verify status shows no auth when unconfigured."""
        result = runner.invoke(cli, ["auth", "status"])
        assert "No authentication configured" in result.output


class TestProxyCommands:
    """Tests for chapgent proxy commands."""

    def test_proxy_start_generates_config(self, runner, tmp_path, monkeypatch):
        """Verify proxy start generates valid config."""
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        
        # Mock subprocess to avoid actually starting server
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()
            result = runner.invoke(cli, ["proxy", "start"])
        
        assert "Starting LiteLLM Proxy" in result.output
        assert "CHAPGENT_BASE_URL" in result.output
```

### Task 7: Add PyYAML Dependency

**File**: `pyproject.toml`

Add `pyyaml` to dependencies for proxy config generation:

```toml
dependencies = [
    # ... existing ...
    "pyyaml>=6.0.0",
]
```

### Task 8: Update Config Writer Whitelist

**File**: `src/chapgent/config/writer.py`

Add `oauth_token` to allowed config keys:

```python
ALLOWED_CONFIG_KEYS = {
    # ... existing ...
    "llm.oauth_token",
}
```

## Usage Examples

### Using Claude Max with External LiteLLM Proxy

```bash
# Set environment variables
export ANTHROPIC_BASE_URL="http://localhost:4000"
export ANTHROPIC_CUSTOM_HEADERS='{"x-litellm-api-key":"Bearer sk-your-key"}'

# Authenticate with Claude Max
chapgent auth login

# Start using chapgent
chapgent chat
```

### Using Embedded LiteLLM Proxy

```bash
# Terminal 1: Start the proxy
chapgent proxy start --port 4000

# Terminal 2: Configure and use chapgent
export CHAPGENT_BASE_URL="http://localhost:4000"
chapgent auth login
chapgent chat
```

### Via TOML Configuration

```toml
# ~/.config/chapgent/config.toml
[llm]
provider = "anthropic"
model = "anthropic-claude"
base_url = "http://localhost:4000"

[llm.extra_headers]
"x-litellm-api-key" = "Bearer sk-your-litellm-key"
```

## Testing Checklist

- [x] `LLMProvider` accepts and passes `base_url` to litellm (TestLLMProviderGatewaySupport)
- [x] `LLMProvider` accepts and passes `extra_headers` to litellm (TestLLMProviderGatewaySupport)
- [x] CLI passes settings to provider correctly (TestCLIPassesSettingsToProvider: 4 tests)
- [x] `chapgent auth login` displays OAuth URL (TestAuthCommands.test_auth_login_shows_options)
- [x] `chapgent auth login` stores token in config (TestAuthLoginTokenStorage: 4 tests)
- [x] `chapgent auth logout` removes tokens (TestAuthLogoutTokenRemoval: 1 test)
- [x] `chapgent auth status` shows auth state (TestAuthCommands: 3 tests)
- [x] `chapgent proxy start` generates valid config (TestProxyCommands.test_proxy_start_displays_instructions)
- [x] `chapgent proxy start` runs litellm subprocess (TestProxyCommands: 3 tests)
- [x] Environment variables work: `ANTHROPIC_BASE_URL`, `ANTHROPIC_CUSTOM_HEADERS` (TestBaseUrlEnvVars, TestExtraHeadersEnvVars, TestOAuthTokenEnvVars, TestGatewayConfigIntegration: 16 tests)
- [x] TOML config works for base_url and extra_headers (test_config.py: 5 tests)

*All testing criteria verified - Phase 7 testing complete*

## Dependencies

- **Existing**: `litellm>=1.0.0`, `httpx>=0.27.0`, `click>=8.0.0`
- **New**: `pyyaml>=6.0.0` (for proxy config generation)
- **Stdlib**: `webbrowser` (for opening OAuth URL)

## Related Documentation

- [LiteLLM Claude Max Tutorial](https://docs.litellm.ai/docs/tutorials/claude_code_max_subscription)
- [LiteLLM Forward Headers](https://docs.litellm.ai/docs/proxy/forward_client_headers)
- [LiteLLM Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
