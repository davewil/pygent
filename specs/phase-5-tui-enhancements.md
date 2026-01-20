# Phase 5: TUI Enhancements - Move CLI Features Into TUI

## Overview

Migrate external CLI configuration and commands into the TUI for a better user experience. Users will be able to access all features via:
1. **Command Palette** (Ctrl+Shift+P) - Extended with new commands
2. **Slash Commands** - Type `/command` in the message input

All configuration changes will persist to `~/.config/chapgent/config.toml`.

---

## Architecture

### New Files
- `src/chapgent/tui/commands.py` - Slash command registry and dispatch
- `src/chapgent/tui/screens.py` - Modal screens (settings, help, tools, theme)
- `src/chapgent/config/writer.py` - Config persistence (extracted from cli.py)

### Modified Files
- `src/chapgent/tui/app.py` - Add slash command interception, new action methods
- `src/chapgent/tui/widgets.py` - Add new commands to DEFAULT_COMMANDS
- `src/chapgent/tui/styles.tcss` - Styles for new modal screens
- `src/chapgent/cli.py` - Import writer helpers instead of defining locally

---

## Implementation Phases

### Phase 1: Infrastructure

#### 1.1 Create Config Writer Module
**File:** `src/chapgent/config/writer.py`

Extract from `cli.py` (lines 302-450):
- `VALID_CONFIG_KEYS` set
- `_convert_value()` - type conversion
- `_format_toml_value()` - TOML formatting
- `_write_toml()` / `_write_toml_section()` - file writing
- New: `save_config_value(key, value, project=False)` - main entry point

#### 1.2 Create Slash Command System
**File:** `src/chapgent/tui/commands.py`

```python
@dataclass
class SlashCommand:
    name: str                    # e.g., "config"
    aliases: list[str]           # e.g., ["settings", "cfg"]
    description: str
    action: str                  # action method name (e.g., "show_config")
    args_pattern: str | None     # e.g., "<key> [value]" for help display

SLASH_COMMANDS: list[SlashCommand] = [
    SlashCommand("help", ["h", "?"], "Show help", "show_help", "[topic]"),
    SlashCommand("theme", [], "Change theme", "show_theme_picker"),
    SlashCommand("model", ["llm"], "LLM settings", "show_llm_settings"),
    # ... etc
]

def parse_slash_command(input: str) -> tuple[SlashCommand | None, list[str]]:
    """Parse input into command and args."""
```

#### 1.3 Add Slash Command Interception
**File:** `src/chapgent/tui/app.py` (modify `on_input_submitted`, line 71)

```python
async def on_input_submitted(self, message: MessageInput.Submitted) -> None:
    user_input = message.value
    if not user_input.strip():
        return
    message.input.value = ""

    # NEW: Check for slash commands
    if user_input.strip().startswith("/"):
        await self._handle_slash_command(user_input.strip())
        return

    # ... existing agent flow
```

---

### Phase 2: Settings Screens

**File:** `src/chapgent/tui/screens.py`

All screens follow the `ModalScreen[T]` pattern (like existing `PermissionPrompt`).

#### 2.1 ThemePickerScreen
**Command:** `/theme` | **Palette:** "Change Theme"

```python
class ThemePickerScreen(ModalScreen[str | None]):
    # Grid of theme buttons (11 themes from VALID_THEMES)
    # Click applies theme immediately via self.app.theme = theme_name
    # "Save" persists to config, "Cancel" reverts
```

#### 2.2 LLMSettingsScreen
**Command:** `/model` or `/llm` | **Palette:** "LLM Settings"

```python
class LLMSettingsScreen(ModalScreen[dict | None]):
    # Select widget for provider (from VALID_PROVIDERS)
    # Input for model name
    # Input for max_tokens (validated 1-100000)
    # Returns {"provider": str, "model": str, "max_tokens": int} or None
```

#### 2.3 TUISettingsScreen
**Command:** `/tui` | **Palette:** "TUI Settings"

```python
class TUISettingsScreen(ModalScreen[dict | None]):
    # Checkbox: Show sidebar
    # Checkbox: Show tool panel
    # Theme picker button (opens ThemePickerScreen)
```

#### 2.4 SystemPromptScreen
**Command:** `/prompt` | **Palette:** "System Prompt"

```python
class SystemPromptScreen(ModalScreen[dict | None]):
    # TextArea for content
    # RadioSet for mode (replace/append)
    # Input for file path (optional)
```

#### 2.5 ConfigShowScreen
**Command:** `/config show` | **Palette:** "Show Config"

```python
class ConfigShowScreen(ModalScreen[None]):
    # Read-only display of current Settings as formatted text
    # Single "Close" button
```

---

### Phase 3: Help & Documentation

#### 3.1 HelpScreen
**Command:** `/help [topic]` | **Palette:** "Help"

```python
class HelpScreen(ModalScreen[None]):
    def __init__(self, topic: str | None = None):
        # If topic provided, show that topic
        # Otherwise show topic list with clickable items
    # Topics: quickstart, tools, config, shortcuts, permissions, sessions, prompts
    # Content from existing HELP_TOPICS dict in cli.py
```

#### 3.2 ToolsScreen
**Command:** `/tools [category]` | **Palette:** "View Tools"

```python
class ToolsScreen(ModalScreen[None]):
    def __init__(self, category: str | None = None):
        # Filter by category if provided
    # List tools with: name, description, risk level badge
    # Categories: filesystem, git, search, web, shell, testing, project
    # Search/filter input at top
```

---

### Phase 4: Utility & Alias Commands

These reuse existing `action_*` methods - just wire up slash commands:

| Slash Command | Maps To | Notes |
|---------------|---------|-------|
| `/new` | `action_new_session` | Alias for Ctrl+N |
| `/save` | `action_save_session` | Alias for Ctrl+S |
| `/clear` | `action_clear` | Alias for Ctrl+L |
| `/quit`, `/exit` | `action_quit` | Alias for Ctrl+Q |
| `/sidebar` | `action_toggle_sidebar` | Alias for Ctrl+B |
| `/toolpanel` | `action_toggle_tools` | Alias for Ctrl+T |
| `/config set <k> <v>` | Direct config write | No screen, inline |

---

## Command Summary

| Slash Command | Palette Command | Action |
|---------------|-----------------|--------|
| `/help [topic]` | Help | `action_show_help` |
| `/tools [cat]` | View Tools | `action_show_tools` |
| `/model`, `/llm` | LLM Settings | `action_show_llm_settings` |
| `/theme` | Change Theme | `action_show_theme_picker` |
| `/tui` | TUI Settings | `action_show_tui_settings` |
| `/prompt` | System Prompt | `action_show_prompt_settings` |
| `/config show` | Show Config | `action_show_config` |
| `/config set <k> <v>` | - | inline handler |
| `/new` | New Session | `action_new_session` |
| `/save` | Save Session | `action_save_session` |
| `/clear` | Clear | `action_clear` |
| `/quit`, `/exit` | Quit | `action_quit` |
| `/sidebar` | Toggle Sidebar | `action_toggle_sidebar` |
| `/toolpanel` | Toggle Tools | `action_toggle_tools` |

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `src/chapgent/config/writer.py` | Config persistence helpers |
| `src/chapgent/tui/commands.py` | Slash command registry |
| `src/chapgent/tui/screens.py` | Modal screens for settings/help |

### Modified Files
| File | Changes |
|------|---------|
| `src/chapgent/tui/app.py` | Add `_handle_slash_command()`, new `action_*` methods |
| `src/chapgent/tui/widgets.py` | Extend `DEFAULT_COMMANDS` list (lines 101-144) |
| `src/chapgent/tui/styles.tcss` | Styles for new modal screens |
| `src/chapgent/cli.py` | Import from `config/writer.py` instead of local defs |

---

## Verification

1. **Manual testing:**
   - `chapgent chat` → type `/theme` → select theme → verify it persists
   - `chapgent chat` → type `/model` → change model → verify next message uses new model
   - `chapgent chat` → type `/help tools` → verify help displays
   - Ctrl+Shift+P → search "theme" → verify command appears

2. **Unit tests** (new file `tests/test_tui/test_commands.py`):
   - `parse_slash_command()` returns correct command and args
   - Config writer round-trips values correctly

3. **Integration tests** (extend `tests/test_integration/test_tui_actions.py`):
   - Slash command via pilot input triggers correct action
   - Modal screens dismiss with expected values

---

## Implementation Order

1. **Phase 1**: Infrastructure ✅ COMPLETE
   - Create `config/writer.py` (extract from cli.py) ✅
   - Create `tui/commands.py` (slash command registry) ✅
   - Add interception in `app.py` ✅
   - Unit tests for new modules ✅
   - **Files created:**
     - `src/chapgent/config/writer.py`
     - `src/chapgent/tui/commands.py`
     - `tests/test_config_writer.py`
     - `tests/test_tui/test_commands.py`
   - **Files modified:**
     - `src/chapgent/config/__init__.py` (exports)
     - `src/chapgent/tui/__init__.py` (exports)
     - `src/chapgent/tui/app.py` (slash command handling)
     - `src/chapgent/cli.py` (imports from writer.py)
     - `tests/test_config_cli.py` (updated imports)
     - `tests/test_logging.py` (updated imports)

2. **Phase 2.1**: Theme Picker (high visibility, validates pattern) ✅ COMPLETE
   - Create `ThemePickerScreen` in `screens.py` ✅
   - Add `action_show_theme_picker` in `app.py` ✅
   - Wire up `/theme` command ✅
   - Add "Change Theme" to command palette ✅
   - **Files created:**
     - `src/chapgent/tui/screens.py`
     - `tests/test_tui/test_screens.py` (27 tests)
   - **Files modified:**
     - `src/chapgent/tui/__init__.py` (exports)
     - `src/chapgent/tui/app.py` (action_show_theme_picker, import ThemePickerScreen)
     - `src/chapgent/tui/widgets.py` (added "Change Theme" to DEFAULT_COMMANDS)

3. **Phase 2.2**: LLM Settings (core functionality) ✅ COMPLETE
   - Create `LLMSettingsScreen` ✅
   - Wire up `/model` command ✅
   - Add "LLM Settings" to command palette ✅
   - **Files modified:**
     - `src/chapgent/tui/screens.py` (added LLMSettingsScreen class)
     - `src/chapgent/tui/__init__.py` (exports)
     - `src/chapgent/tui/app.py` (action_show_llm_settings, import LLMSettingsScreen)
     - `src/chapgent/tui/widgets.py` (added "LLM Settings" to DEFAULT_COMMANDS)
     - `tests/test_tui/test_screens.py` (added 26 tests for LLMSettingsScreen)

4. **Phase 3**: Help & Tools
   - Create `HelpScreen` and `ToolsScreen`
   - Wire up `/help` and `/tools` commands

5. **Phase 4**: Remaining
   - TUI settings, system prompt, config show
   - Utility aliases (/new, /save, /clear, etc.)

6. **Phase 5**: Polish
   - Update `DEFAULT_COMMANDS` in widgets.py
   - Add styles to styles.tcss
   - Write tests
