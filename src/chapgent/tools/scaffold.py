"""Project scaffolding tools for chapgent.

Provides template-based project creation and component generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles

from chapgent.tools.base import ToolCategory, ToolRisk, tool


@dataclass
class TemplateOption:
    """Configuration option for a template.

    Attributes:
        name: Option name.
        option_type: Option type ("bool", "str", "choice").
        default: Default value.
        description: Human-readable description.
        choices: Valid choices for "choice" type.
    """

    name: str
    option_type: str  # "bool", "str", "choice"
    default: Any
    description: str
    choices: list[str] | None = None


@dataclass
class TemplateFile:
    """A file to be created from a template.

    Attributes:
        path: Relative path with {placeholders}.
        content: File content with {placeholders}.
        condition: Optional condition for including this file.
    """

    path: str
    content: str
    condition: str | None = None


@dataclass
class ProjectTemplate:
    """A project template definition.

    Attributes:
        name: Template identifier.
        description: Human-readable description.
        files: List of template files.
        options: Available configuration options.
        post_create_commands: Shell commands to run after creation.
        next_steps: Instructions to show after creation.
    """

    name: str
    description: str
    files: list[TemplateFile] = field(default_factory=list)
    options: list[TemplateOption] = field(default_factory=list)
    post_create_commands: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


@dataclass
class ComponentTemplate:
    """A component that can be added to existing projects.

    Attributes:
        name: Component identifier.
        description: Human-readable description.
        project_types: Project types this component applies to.
        files: Files to create.
        modifications: Files to modify (path -> content to append/insert).
    """

    name: str
    description: str
    project_types: list[str]
    files: list[TemplateFile] = field(default_factory=list)
    modifications: dict[str, str] = field(default_factory=dict)


# ============================================================================
# Built-in Project Templates
# ============================================================================

_PYTHON_CLI_PYPROJECT = """[build-system]
requires = ["setuptools>=64", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.10"
license = {{text = "MIT"}}
authors = [
    {{name = "{author}", email = "{email}"}}
]
dependencies = [
{dependencies}]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]

[project.scripts]
{name} = "{name}.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov={name} --cov-report=term-missing"

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
"""

_PYTHON_CLI_INIT = '''"""{name} - {description}"""

__version__ = "0.1.0"
'''

_PYTHON_CLI_CLI_CLICK = '''"""Command-line interface for {name}."""

import click

from {name} import __version__


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """{description}"""
    pass


@main.command()
@click.argument("name", default="World")
def hello(name: str) -> None:
    """Say hello."""
    click.echo(f"Hello, {{name}}!")


if __name__ == "__main__":
    main()
'''

_PYTHON_CLI_CLI_TYPER = '''"""Command-line interface for {name}."""

import typer

from {name} import __version__

app = typer.Typer(help="{description}")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"{name} version {{__version__}}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True
    ),
) -> None:
    """Main entry point."""
    pass


@app.command()
def hello(name: str = "World") -> None:
    """Say hello."""
    typer.echo(f"Hello, {{name}}!")


if __name__ == "__main__":
    app()
'''

_PYTHON_CLI_MAIN = '''"""{name} main module."""


def greet(name: str) -> str:
    """Return a greeting.

    Args:
        name: Name to greet.

    Returns:
        Greeting message.
    """
    return f"Hello, {{name}}!"
'''

_PYTHON_CLI_CONFTEST = '''"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_name() -> str:
    """Provide a sample name for testing."""
    return "Test"
'''

_PYTHON_CLI_TEST_MAIN = '''"""Tests for main module."""

from {name}.main import greet


def test_greet() -> None:
    """Test greeting function."""
    assert greet("World") == "Hello, World!"


def test_greet_custom_name(sample_name: str) -> None:
    """Test greeting with custom name."""
    assert greet(sample_name) == f"Hello, {{sample_name}}!"
'''

_PYTHON_GITIGNORE = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
dist/
build/
*.egg-info/
.eggs/

# Virtual environments
venv/
.venv/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.coverage
htmlcov/
.pytest_cache/

# mypy
.mypy_cache/

# ruff
.ruff_cache/
"""

_PYTHON_README = """# {name}

{description}

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
{name} --help
{name} hello World
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests
ruff format src tests

# Type check
mypy src
```

## License

MIT
"""

_DOCKERFILE = """FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

ENTRYPOINT ["{name}"]
"""

_PYTHON_LIB_PYPROJECT = """[build-system]
requires = ["setuptools>=64", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.10"
license = {{text = "MIT"}}
authors = [
    {{name = "{author}", email = "{email}"}}
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]

[project.urls]
"Homepage" = "https://github.com/{author}/{name}"
"Bug Tracker" = "https://github.com/{author}/{name}/issues"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov={name} --cov-report=term-missing"

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
"""

_PYTHON_LIB_INIT = '''"""{name} - {description}

Example usage:
    >>> from {name} import hello
    >>> hello("World")
    'Hello, World!'
"""

__version__ = "0.1.0"


def hello(name: str) -> str:
    """Return a greeting.

    Args:
        name: Name to greet.

    Returns:
        Greeting message.

    Example:
        >>> hello("World")
        'Hello, World!'
    """
    return f"Hello, {{name}}!"
'''

_PYTHON_LIB_TEST = '''"""Tests for {name}."""

import pytest

from {name} import __version__, hello


def test_version() -> None:
    """Test version is set."""
    assert __version__ == "0.1.0"


def test_hello() -> None:
    """Test hello function."""
    assert hello("World") == "Hello, World!"


@pytest.mark.parametrize("name,expected", [
    ("Alice", "Hello, Alice!"),
    ("Bob", "Hello, Bob!"),
    ("", "Hello, !"),
])
def test_hello_parametrized(name: str, expected: str) -> None:
    """Test hello with various inputs."""
    assert hello(name) == expected
'''

_PYTHON_LIB_README = """# {name}

{description}

## Installation

```bash
pip install {name}
```

## Usage

```python
from {name} import hello

print(hello("World"))  # "Hello, World!"
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check src tests
ruff format src tests

# Type check
mypy src
```

## License

MIT
"""

_FASTAPI_PYPROJECT = """[build-system]
requires = ["setuptools>=64", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.10"
license = {{text = "MIT"}}
authors = [
    {{name = "{author}", email = "{email}"}}
]
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0",
    "httpx>=0.24.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov={name} --cov-report=term-missing"
asyncio_mode = "auto"

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.10"
strict = true
plugins = ["pydantic.mypy"]
"""

_FASTAPI_INIT = '''"""{name} - {description}"""

__version__ = "0.1.0"
'''

_FASTAPI_MAIN = '''"""FastAPI application entry point."""

from fastapi import FastAPI

from {name}.api.routes import router
from {name}.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="{description}",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {{"status": "healthy"}}
'''

_FASTAPI_CONFIG = '''"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "{name}"
    debug: bool = False
    api_key: str = ""

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
'''

_FASTAPI_ROUTES = '''"""API routes."""

from fastapi import APIRouter

from {name}.api.schemas import GreetRequest, GreetResponse

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {{"message": "Welcome to {name} API"}}


@router.post("/greet", response_model=GreetResponse)
async def greet(request: GreetRequest) -> GreetResponse:
    """Greet a user."""
    return GreetResponse(message=f"Hello, {{request.name}}!")
'''

_FASTAPI_SCHEMAS = '''"""API schemas."""

from pydantic import BaseModel


class GreetRequest(BaseModel):
    """Greet request schema."""

    name: str


class GreetResponse(BaseModel):
    """Greet response schema."""

    message: str
'''

_FASTAPI_CONFTEST = '''"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from {name}.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)
'''

_FASTAPI_TEST_API = '''"""API tests."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {{"status": "healthy"}}


def test_root(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/api/v1/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_greet(client: TestClient) -> None:
    """Test greet endpoint."""
    response = client.post("/api/v1/greet", json={{"name": "World"}})
    assert response.status_code == 200
    assert response.json() == {{"message": "Hello, World!"}}
'''

_FASTAPI_README = """# {name}

{description}

## Installation

```bash
pip install -e ".[dev]"
```

## Running

```bash
# Development server
uvicorn {name}.main:app --reload

# Production
uvicorn {name}.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests
ruff format src tests

# Type check
mypy src
```

## License

MIT
"""

# ============================================================================
# Template Registry
# ============================================================================

TEMPLATES: dict[str, ProjectTemplate] = {
    "python-cli": ProjectTemplate(
        name="python-cli",
        description="Python CLI application with Click",
        files=[
            TemplateFile("pyproject.toml", _PYTHON_CLI_PYPROJECT),
            TemplateFile("src/{name}/__init__.py", _PYTHON_CLI_INIT),
            TemplateFile("src/{name}/cli.py", _PYTHON_CLI_CLI_CLICK, condition="not use_typer"),
            TemplateFile("src/{name}/cli.py", _PYTHON_CLI_CLI_TYPER, condition="use_typer"),
            TemplateFile("src/{name}/main.py", _PYTHON_CLI_MAIN),
            TemplateFile("tests/__init__.py", ""),
            TemplateFile("tests/conftest.py", _PYTHON_CLI_CONFTEST),
            TemplateFile("tests/test_main.py", _PYTHON_CLI_TEST_MAIN),
            TemplateFile(".gitignore", _PYTHON_GITIGNORE),
            TemplateFile("README.md", _PYTHON_README),
            TemplateFile("Dockerfile", _DOCKERFILE, condition="include_docker"),
        ],
        options=[
            TemplateOption("use_typer", "bool", False, "Use Typer instead of Click"),
            TemplateOption("include_docker", "bool", False, "Include Dockerfile"),
            TemplateOption("description", "str", "A Python CLI application", "Project description"),
            TemplateOption("author", "str", "Author", "Author name"),
            TemplateOption("email", "str", "author@example.com", "Author email"),
        ],
        post_create_commands=["pip install -e '.[dev]'"],
        next_steps=[
            "cd {name}",
            "pip install -e '.[dev]'",
            "pytest  # Run tests",
            "{name} --help  # Run the CLI",
        ],
    ),
    "python-lib": ProjectTemplate(
        name="python-lib",
        description="Python library for PyPI distribution",
        files=[
            TemplateFile("pyproject.toml", _PYTHON_LIB_PYPROJECT),
            TemplateFile("src/{name}/__init__.py", _PYTHON_LIB_INIT),
            TemplateFile("tests/__init__.py", ""),
            TemplateFile("tests/test_{name}.py", _PYTHON_LIB_TEST),
            TemplateFile(".gitignore", _PYTHON_GITIGNORE),
            TemplateFile("README.md", _PYTHON_LIB_README),
        ],
        options=[
            TemplateOption("description", "str", "A Python library", "Project description"),
            TemplateOption("author", "str", "Author", "Author name"),
            TemplateOption("email", "str", "author@example.com", "Author email"),
        ],
        post_create_commands=["pip install -e '.[dev]'"],
        next_steps=[
            "cd {name}",
            "pip install -e '.[dev]'",
            "pytest  # Run tests",
        ],
    ),
    "fastapi": ProjectTemplate(
        name="fastapi",
        description="FastAPI web application",
        files=[
            TemplateFile("pyproject.toml", _FASTAPI_PYPROJECT),
            TemplateFile("src/{name}/__init__.py", _FASTAPI_INIT),
            TemplateFile("src/{name}/main.py", _FASTAPI_MAIN),
            TemplateFile("src/{name}/core/__init__.py", ""),
            TemplateFile("src/{name}/core/config.py", _FASTAPI_CONFIG),
            TemplateFile("src/{name}/api/__init__.py", ""),
            TemplateFile("src/{name}/api/routes.py", _FASTAPI_ROUTES),
            TemplateFile("src/{name}/api/schemas.py", _FASTAPI_SCHEMAS),
            TemplateFile("tests/__init__.py", ""),
            TemplateFile("tests/conftest.py", _FASTAPI_CONFTEST),
            TemplateFile("tests/test_api.py", _FASTAPI_TEST_API),
            TemplateFile(".gitignore", _PYTHON_GITIGNORE),
            TemplateFile("README.md", _FASTAPI_README),
            TemplateFile(".env.example", "APP_NAME={name}\nDEBUG=true\nAPI_KEY="),
        ],
        options=[
            TemplateOption("description", "str", "A FastAPI web application", "Project description"),
            TemplateOption("author", "str", "Author", "Author name"),
            TemplateOption("email", "str", "author@example.com", "Author email"),
        ],
        post_create_commands=["pip install -e '.[dev]'"],
        next_steps=[
            "cd {name}",
            "pip install -e '.[dev]'",
            "uvicorn {name}.main:app --reload  # Start dev server",
            "Open http://localhost:8000/docs  # View API docs",
        ],
    ),
}

# ============================================================================
# Component Templates
# ============================================================================

_COMPONENT_MODEL = '''"""Model: {name}"""

from dataclasses import dataclass


@dataclass
class {class_name}:
    """A {name} model.

    Attributes:
        id: Unique identifier.
        name: Display name.
    """

    id: int
    name: str
'''

_COMPONENT_SERVICE = '''"""Service: {name}"""

from typing import Any


class {class_name}Service:
    """Service for {name} operations."""

    def __init__(self) -> None:
        """Initialize service."""
        self._items: dict[int, Any] = {{}}

    def get(self, item_id: int) -> Any | None:
        """Get an item by ID."""
        return self._items.get(item_id)

    def create(self, item: Any) -> Any:
        """Create a new item."""
        self._items[item.id] = item
        return item

    def delete(self, item_id: int) -> bool:
        """Delete an item."""
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False
'''

_COMPONENT_CLI_COMMAND = '''"""CLI command: {name}"""

import click


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def {name}(verbose: bool) -> None:
    """The {name} command."""
    if verbose:
        click.echo("Running {name} in verbose mode...")
    click.echo("{name} executed successfully!")
'''

_COMPONENT_FASTAPI_ROUTE = '''"""Route: {name}"""

from fastapi import APIRouter

router = APIRouter(prefix="/{name}", tags=["{name}"])


@router.get("/")
async def list_{name}s() -> dict[str, list]:
    """List all {name}s."""
    return {{"{name}s": []}}


@router.get("/{{item_id}}")
async def get_{name}(item_id: int) -> dict[str, int | str]:
    """Get a {name} by ID."""
    return {{"id": item_id, "name": "Sample {name}"}}
'''

_COMPONENT_TEST = '''"""Tests for {name}."""

import pytest


def test_{name}_exists() -> None:
    """Test that {name} is defined."""
    # TODO: Add real tests
    assert True
'''

COMPONENTS: dict[str, ComponentTemplate] = {
    "model": ComponentTemplate(
        name="model",
        description="Add a data model class",
        project_types=["python", "python-cli", "python-lib", "fastapi"],
        files=[
            TemplateFile("src/{project}/models/{name}.py", _COMPONENT_MODEL),
            TemplateFile("tests/test_{name}_model.py", _COMPONENT_TEST),
        ],
    ),
    "service": ComponentTemplate(
        name="service",
        description="Add a service class",
        project_types=["python", "python-cli", "python-lib", "fastapi"],
        files=[
            TemplateFile("src/{project}/services/{name}.py", _COMPONENT_SERVICE),
            TemplateFile("tests/test_{name}_service.py", _COMPONENT_TEST),
        ],
    ),
    "test": ComponentTemplate(
        name="test",
        description="Add a test file",
        project_types=["python", "python-cli", "python-lib", "fastapi"],
        files=[
            TemplateFile("tests/test_{name}.py", _COMPONENT_TEST),
        ],
    ),
    "cli_command": ComponentTemplate(
        name="cli_command",
        description="Add a CLI command",
        project_types=["python-cli"],
        files=[
            TemplateFile("src/{project}/commands/{name}.py", _COMPONENT_CLI_COMMAND),
        ],
    ),
    "route": ComponentTemplate(
        name="route",
        description="Add a FastAPI route",
        project_types=["fastapi"],
        files=[
            TemplateFile("src/{project}/api/{name}.py", _COMPONENT_FASTAPI_ROUTE),
            TemplateFile("tests/test_{name}_api.py", _COMPONENT_TEST),
        ],
    ),
}


# ============================================================================
# Helper Functions
# ============================================================================


def _normalize_project_name(name: str) -> str:
    """Normalize a project name to a valid Python identifier.

    Args:
        name: Raw project name.

    Returns:
        Normalized name (lowercase, underscores instead of hyphens).
    """
    # Replace hyphens with underscores
    normalized = name.replace("-", "_")
    # Remove invalid characters
    normalized = re.sub(r"[^a-zA-Z0-9_]", "", normalized)
    # Ensure starts with letter
    if normalized and normalized[0].isdigit():
        normalized = "_" + normalized
    return normalized.lower()


def _to_class_name(name: str) -> str:
    """Convert a name to PascalCase class name.

    Args:
        name: Name to convert.

    Returns:
        PascalCase name.
    """
    # Split on underscore or hyphen
    parts = re.split(r"[_-]", name)
    return "".join(part.capitalize() for part in parts if part)


def _evaluate_condition(condition: str | None, options: dict[str, Any]) -> bool:
    """Evaluate a template file condition.

    Args:
        condition: Condition string (e.g., "use_typer", "not include_docker").
        options: Option values.

    Returns:
        Whether the condition is met.
    """
    if not condition:
        return True

    # Handle "not X"
    if condition.startswith("not "):
        var_name = condition[4:].strip()
        return not options.get(var_name, False)

    # Handle simple variable
    return bool(options.get(condition, False))


def _render_template(content: str, context: dict[str, Any]) -> str:
    """Render a template string with context variables.

    Uses simple {variable} replacement. Double braces {{ }} are escaped.

    Args:
        content: Template content.
        context: Variable values.

    Returns:
        Rendered content.
    """
    # Temporarily replace {{ and }} with placeholders
    content = content.replace("{{", "\x00LBRACE\x00")
    content = content.replace("}}", "\x00RBRACE\x00")

    # Replace {variable} patterns
    for key, value in context.items():
        content = content.replace(f"{{{key}}}", str(value))

    # Restore escaped braces as single braces
    content = content.replace("\x00LBRACE\x00", "{")
    content = content.replace("\x00RBRACE\x00", "}")

    return content


async def _create_file(path: Path, content: str) -> None:
    """Create a file with content, creating parent directories as needed.

    Args:
        path: File path.
        content: File content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)


def _detect_project_name(path: Path) -> str | None:
    """Detect project name from pyproject.toml or directory name.

    Args:
        path: Project path.

    Returns:
        Detected project name or None.
    """
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        # Simple regex to find name in pyproject.toml
        match = re.search(r'name\s*=\s*"([^"]+)"', content)
        if match:
            return _normalize_project_name(match.group(1))

    # Fall back to directory name
    return _normalize_project_name(path.name)


# ============================================================================
# Tools
# ============================================================================


@tool(
    name="list_templates",
    description="List available project templates",
    risk=ToolRisk.LOW,
    category=ToolCategory.PROJECT,
    read_only=True,
)
async def list_templates() -> str:
    """List available project templates.

    Returns:
        JSON array of templates with descriptions.
    """
    result = []
    for name, template in TEMPLATES.items():
        options = [
            {
                "name": opt.name,
                "type": opt.option_type,
                "default": opt.default,
                "description": opt.description,
            }
            for opt in template.options
        ]
        result.append(
            {
                "name": name,
                "description": template.description,
                "options": options,
            }
        )

    return json.dumps(result, indent=2)


@tool(
    name="create_project",
    description="Create a new project from a template",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.PROJECT,
    cacheable=False,
)
async def create_project(
    name: str,
    template: str,
    path: str = ".",
    options: str | None = None,
) -> str:
    """Create a new project.

    Args:
        name: Project name (will be normalized to valid Python identifier).
        template: Template identifier (e.g., "python-cli", "fastapi").
        path: Parent directory for new project (default: current directory).
        options: JSON string of template-specific options.

    Returns:
        Summary of created files and next steps.
    """
    # Validate template
    if template not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        return f"Error: Unknown template '{template}'. Available: {available}"

    tmpl = TEMPLATES[template]
    normalized_name = _normalize_project_name(name)

    if not normalized_name:
        return f"Error: Invalid project name '{name}'"

    # Parse options
    opts: dict[str, Any] = {}
    if options:
        try:
            opts = json.loads(options)
        except json.JSONDecodeError as e:
            return f"Error: Invalid options JSON: {e}"

    # Apply defaults
    for opt in tmpl.options:
        if opt.name not in opts:
            opts[opt.name] = opt.default

    # Create project directory
    base_path = Path(path).resolve()
    project_path = base_path / normalized_name

    if project_path.exists():
        return f"Error: Directory already exists: {project_path}"

    project_path.mkdir(parents=True)

    # Build context
    context = {
        "name": normalized_name,
        "class_name": _to_class_name(normalized_name),
        **opts,
    }

    # Handle dependencies based on options
    deps = []
    if opts.get("use_typer"):
        deps.append('    "typer>=0.9.0",')
    else:
        deps.append('    "click>=8.0",')
    context["dependencies"] = "\n".join(deps)

    # Create files
    created_files = []
    for file_tmpl in tmpl.files:
        # Check condition
        if not _evaluate_condition(file_tmpl.condition, opts):
            continue

        # Render path and content
        file_path = _render_template(file_tmpl.path, context)
        file_content = _render_template(file_tmpl.content, context)

        # Create file
        full_path = project_path / file_path
        await _create_file(full_path, file_content)
        created_files.append(file_path)

    # Build result
    result_lines = [
        f"Created project '{normalized_name}' using template '{template}'",
        "",
        f"Location: {project_path}",
        "",
        "Files created:",
    ]
    for f in sorted(created_files):
        result_lines.append(f"  - {f}")

    if tmpl.next_steps:
        result_lines.append("")
        result_lines.append("Next steps:")
        for step in tmpl.next_steps:
            rendered_step = _render_template(step, context)
            result_lines.append(f"  $ {rendered_step}")

    return "\n".join(result_lines)


@tool(
    name="add_component",
    description="Add a component or feature to an existing project",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.PROJECT,
    cacheable=False,
)
async def add_component(
    component: str,
    name: str,
    path: str = ".",
    options: str | None = None,
) -> str:
    """Add a component to current project.

    Args:
        component: Component type (e.g., "model", "service", "route", "test", "cli_command").
        name: Component name (e.g., "user", "product").
        path: Project root directory (default: current directory).
        options: JSON string of component-specific options.

    Returns:
        Summary of created/modified files.
    """
    # Validate component
    if component not in COMPONENTS:
        available = ", ".join(COMPONENTS.keys())
        return f"Error: Unknown component '{component}'. Available: {available}"

    comp = COMPONENTS[component]
    normalized_name = _normalize_project_name(name)

    if not normalized_name:
        return f"Error: Invalid component name '{name}'"

    # Detect project
    project_path = Path(path).resolve()
    project_name = _detect_project_name(project_path)

    if not project_name:
        return f"Error: Could not detect project name in '{path}'"

    # Parse options
    opts: dict[str, Any] = {}
    if options:
        try:
            opts = json.loads(options)
        except json.JSONDecodeError as e:
            return f"Error: Invalid options JSON: {e}"

    # Build context
    context = {
        "name": normalized_name,
        "class_name": _to_class_name(normalized_name),
        "project": project_name,
        **opts,
    }

    # Create files
    created_files = []
    for file_tmpl in comp.files:
        # Render path and content
        file_path = _render_template(file_tmpl.path, context)
        file_content = _render_template(file_tmpl.content, context)

        # Create file
        full_path = project_path / file_path
        if full_path.exists():
            created_files.append(f"{file_path} (skipped - exists)")
            continue

        await _create_file(full_path, file_content)
        created_files.append(file_path)

    # Build result
    result_lines = [
        f"Added component '{component}' named '{normalized_name}' to project '{project_name}'",
        "",
        "Files created:",
    ]
    for f in sorted(created_files):
        result_lines.append(f"  - {f}")

    return "\n".join(result_lines)


@tool(
    name="list_components",
    description="List available components that can be added to projects",
    risk=ToolRisk.LOW,
    category=ToolCategory.PROJECT,
    read_only=True,
)
async def list_components() -> str:
    """List available components.

    Returns:
        JSON array of components with descriptions.
    """
    result = []
    for name, comp in COMPONENTS.items():
        result.append(
            {
                "name": name,
                "description": comp.description,
                "project_types": comp.project_types,
            }
        )

    return json.dumps(result, indent=2)
