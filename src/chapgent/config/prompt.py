"""System prompt loading and template variable resolution."""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

from chapgent.config.settings import DEFAULT_SYSTEM_PROMPT, SystemPromptSettings
from chapgent.context.models import ProjectContext

# Template variables that can be used in system prompts
TEMPLATE_VARIABLES = {
    "project_name": "Name of current project",
    "project_type": "Detected project type (python, node, go, rust, unknown)",
    "current_dir": "Current working directory",
    "git_branch": "Current git branch (or 'N/A' if not a git repo)",
    "date": "Current date in YYYY-MM-DD format",
    "os": "Operating system name",
}


class PromptLoadError(Exception):
    """Error loading system prompt from file."""

    pass


def get_template_variables(context: ProjectContext | None = None) -> dict[str, str]:
    """Get template variable values for prompt substitution.

    Args:
        context: Optional project context for project-specific variables.

    Returns:
        Dictionary mapping variable names to their resolved values.
    """
    variables: dict[str, str] = {
        "current_dir": str(Path.cwd()),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "os": platform.system(),
    }

    if context:
        variables["project_name"] = context.name or Path(context.root).name
        variables["project_type"] = context.type.value
        if context.git_info and context.git_info.branch:
            variables["git_branch"] = context.git_info.branch
        else:
            variables["git_branch"] = "N/A"
    else:
        variables["project_name"] = Path.cwd().name
        variables["project_type"] = "unknown"
        variables["git_branch"] = "N/A"

    return variables


def resolve_template_variables(
    content: str,
    variables: dict[str, str] | None = None,
    context: ProjectContext | None = None,
) -> str:
    """Resolve template variables in prompt content.

    Supports {variable_name} syntax for substitution. Unknown variables
    are left as-is (not replaced).

    Args:
        content: The prompt content with potential template variables.
        variables: Optional dictionary of additional/override variables.
        context: Optional project context for default variable values.

    Returns:
        Content with template variables resolved.
    """
    # Get default variables
    resolved = get_template_variables(context)

    # Apply overrides
    if variables:
        resolved.update(variables)

    # Use safe string formatting - only replace known variables
    result = content
    for name, value in resolved.items():
        result = result.replace("{" + name + "}", value)

    return result


def load_prompt_file(file_path: str) -> str:
    """Load prompt content from a file.

    Supports ~ expansion for home directory.

    Args:
        file_path: Path to the prompt file.

    Returns:
        Content of the file.

    Raises:
        PromptLoadError: If the file cannot be read.
    """
    path = Path(file_path).expanduser()

    if not path.exists():
        raise PromptLoadError(f"Prompt file not found: {path}")

    if not path.is_file():
        raise PromptLoadError(f"Prompt path is not a file: {path}")

    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise PromptLoadError(f"Cannot read prompt file {path}: {e}") from e


def get_effective_prompt(
    settings: SystemPromptSettings,
    context: ProjectContext | None = None,
    additional_variables: dict[str, str] | None = None,
) -> str:
    """Get the effective system prompt after applying all customizations.

    Resolves the prompt based on settings configuration:
    1. Load content from file if specified, otherwise use content field
    2. Apply mode (replace or append) to combine with base prompt
    3. Add any append content
    4. Resolve template variables

    Args:
        settings: The system prompt settings.
        context: Optional project context for template variables.
        additional_variables: Optional extra template variables.

    Returns:
        The fully resolved system prompt.

    Raises:
        PromptLoadError: If a prompt file cannot be loaded.
    """
    # Step 1: Determine the custom content
    custom_content: str | None = None

    if settings.file:
        custom_content = load_prompt_file(settings.file)
    elif settings.content:
        custom_content = settings.content

    # Step 2: Apply mode to combine with base prompt
    if custom_content:
        if settings.mode == "replace":
            base_prompt = custom_content
        else:  # append mode
            base_prompt = DEFAULT_SYSTEM_PROMPT + "\n\n" + custom_content
    else:
        base_prompt = DEFAULT_SYSTEM_PROMPT

    # Step 3: Add any additional append content
    if settings.append:
        base_prompt = base_prompt + "\n\n" + settings.append

    # Step 4: Resolve template variables
    return resolve_template_variables(base_prompt, additional_variables, context)


def build_full_system_prompt(
    settings: SystemPromptSettings,
    context: ProjectContext | None = None,
    additional_variables: dict[str, str] | None = None,
) -> str:
    """Build the complete system prompt with context injection.

    This combines user customization from settings with automatic
    project context detection. Uses the existing build_system_prompt
    function from context/prompt.py for context injection.

    Args:
        settings: The system prompt settings.
        context: Optional detected project context.
        additional_variables: Optional extra template variables.

    Returns:
        The complete system prompt with context injected.
    """
    from chapgent.context.prompt import build_system_prompt

    # Get effective base prompt from settings
    effective_prompt = get_effective_prompt(settings, context, additional_variables)

    # If we have project context, inject it
    if context:
        return build_system_prompt(effective_prompt, context)

    return effective_prompt
