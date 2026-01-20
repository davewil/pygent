"""Tests for project scaffolding tools."""

import json
import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chapgent.tools.scaffold import (
    COMPONENTS,
    TEMPLATES,
    ComponentTemplate,
    ProjectTemplate,
    TemplateFile,
    TemplateOption,
    _detect_project_name,
    _evaluate_condition,
    _normalize_project_name,
    _render_template,
    _to_class_name,
    add_component,
    create_project,
    list_components,
    list_templates,
)

# ============================================================================
# Helper Function Tests (Consolidated)
# ============================================================================


@pytest.mark.parametrize(
    "input_name,expected",
    [
        ("myproject", "myproject"),
        ("my-project", "my_project"),
        ("MyProject", "myproject"),
        ("my@project!", "myproject"),
        ("123project", "_123project"),
        ("My-Awesome@Project123", "my_awesomeproject123"),
        ("@@@", ""),
    ],
)
def test_normalize_project_name(input_name: str, expected: str) -> None:
    """Test _normalize_project_name with various inputs."""
    assert _normalize_project_name(input_name) == expected


@pytest.mark.parametrize(
    "input_name,expected",
    [
        ("user", "User"),
        ("user_model", "UserModel"),
        ("user-service", "UserService"),
        ("my-user_model", "MyUserModel"),
        ("UserModel", "Usermodel"),
    ],
)
def test_to_class_name(input_name: str, expected: str) -> None:
    """Test _to_class_name with various inputs."""
    assert _to_class_name(input_name) == expected


@pytest.mark.parametrize(
    "condition,context,expected",
    [
        (None, {}, True),
        ("use_typer", {"use_typer": True}, True),
        ("use_typer", {"use_typer": False}, False),
        ("unknown", {}, False),
        ("not use_typer", {"use_typer": True}, False),
        ("not use_typer", {"use_typer": False}, True),
        ("not unknown", {}, True),
    ],
)
def test_evaluate_condition(condition: str | None, context: dict, expected: bool) -> None:
    """Test _evaluate_condition with various inputs."""
    assert _evaluate_condition(condition, context) is expected


@pytest.mark.parametrize(
    "template,context,expected",
    [
        ("Hello {name}!", {"name": "World"}, "Hello World!"),
        ("{a} and {b}", {"a": "foo", "b": "bar"}, "foo and bar"),
        ("dict = {{'key': {{value}}}}", {"value": "123"}, "dict = {'key': {value}}"),
        ("Hello {name}, use {{braces}}", {"name": "World"}, "Hello World, use {braces}"),
        ("Hello {name}!", {"name": "World", "unused": "foo"}, "Hello World!"),
    ],
)
def test_render_template(template: str, context: dict, expected: str) -> None:
    """Test _render_template with various inputs."""
    assert _render_template(template, context) == expected


class TestDetectProjectName:
    """Tests for _detect_project_name."""

    def test_from_pyproject(self, tmp_path) -> None:
        """Test detection from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-awesome-project"\nversion = "0.1.0"')
        assert _detect_project_name(tmp_path) == "my_awesome_project"

    def test_from_directory(self, tmp_path) -> None:
        """Test fallback to directory name."""
        assert _detect_project_name(tmp_path) is not None

    def test_hyphenated_dir(self, tmp_path) -> None:
        """Test hyphenated directory name."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        assert _detect_project_name(project_dir) == "my_project"


# ============================================================================
# Data Model Tests (Consolidated)
# ============================================================================


class TestDataModels:
    """Tests for scaffold data model dataclasses."""

    def test_template_option_basic(self) -> None:
        """Test TemplateOption creation with basic and choice options."""
        basic_opt = TemplateOption(name="use_docker", option_type="bool", default=False, description="Include Docker")
        assert (basic_opt.name, basic_opt.option_type, basic_opt.default, basic_opt.choices) == (
            "use_docker",
            "bool",
            False,
            None,
        )

        choice_opt = TemplateOption(
            name="database",
            option_type="choice",
            default="postgres",
            description="DB type",
            choices=["postgres", "mysql", "sqlite"],
        )
        assert choice_opt.choices == ["postgres", "mysql", "sqlite"]

    def test_template_file(self) -> None:
        """Test TemplateFile creation with and without condition."""
        basic = TemplateFile(path="src/{name}/__init__.py", content='"""Init."""')
        assert (basic.path, basic.condition) == ("src/{name}/__init__.py", None)

        conditional = TemplateFile(path="Dockerfile", content="FROM python:3.11", condition="include_docker")
        assert conditional.condition == "include_docker"

    def test_project_template(self) -> None:
        """Test ProjectTemplate creation."""
        tmpl = ProjectTemplate(
            name="test-template",
            description="A test template",
            files=[TemplateFile("README.md", "# {name}")],
            options=[],
        )
        assert (tmpl.name, len(tmpl.files), tmpl.post_create_commands, tmpl.next_steps) == ("test-template", 1, [], [])

    def test_component_template(self) -> None:
        """Test ComponentTemplate creation."""
        comp = ComponentTemplate(
            name="model",
            description="Add a model",
            project_types=["python"],
            files=[TemplateFile("models/{name}.py", "class {class_name}: pass")],
        )
        assert (comp.name, comp.project_types, comp.modifications) == ("model", ["python"], {})


# ============================================================================
# Built-in Template & Component Tests (Consolidated)
# ============================================================================


class TestBuiltInTemplatesAndComponents:
    """Tests for built-in templates and components."""

    @pytest.mark.parametrize("template_name", ["python-cli", "python-lib", "fastapi"])
    def test_templates_exist(self, template_name: str) -> None:
        """Test that expected templates exist."""
        assert template_name in TEMPLATES

    def test_python_cli_template_structure(self) -> None:
        """Test python-cli template has expected structure and options."""
        tmpl = TEMPLATES["python-cli"]
        assert tmpl.description == "Python CLI application with Click"
        file_paths = [f.path for f in tmpl.files]
        for expected in ["pyproject.toml", "src/{name}/__init__.py", "README.md", ".gitignore"]:
            assert expected in file_paths
        option_names = [o.name for o in tmpl.options]
        assert "use_typer" in option_names and "include_docker" in option_names

    def test_fastapi_template_structure(self) -> None:
        """Test fastapi template has expected structure."""
        tmpl = TEMPLATES["fastapi"]
        assert tmpl.description == "FastAPI web application"
        file_paths = [f.path for f in tmpl.files]
        for expected in ["src/{name}/main.py", "src/{name}/api/routes.py", "src/{name}/core/config.py"]:
            assert expected in file_paths

    @pytest.mark.parametrize("component_name", ["model", "service", "test", "route", "cli_command"])
    def test_components_exist(self, component_name: str) -> None:
        """Test that expected components exist."""
        assert component_name in COMPONENTS

    def test_component_project_types(self) -> None:
        """Test components have correct project types."""
        assert "python" in COMPONENTS["model"].project_types
        assert len(COMPONENTS["model"].files) == 2  # model file + test file
        assert "fastapi" in COMPONENTS["route"].project_types


# ============================================================================
# list_templates & list_components Tool Tests (Consolidated)
# ============================================================================


class TestListTools:
    """Tests for list_templates and list_components tools."""

    @pytest.mark.asyncio
    async def test_list_templates(self) -> None:
        """Test list_templates returns valid JSON with expected structure."""
        result = await list_templates()
        templates = json.loads(result)
        assert isinstance(templates, list)
        names = [t["name"] for t in templates]
        for expected in ["python-cli", "python-lib", "fastapi"]:
            assert expected in names
        for tmpl in templates:
            assert all(key in tmpl for key in ["name", "description", "options"])

    @pytest.mark.asyncio
    async def test_list_components(self) -> None:
        """Test list_components returns valid JSON with expected structure."""
        result = await list_components()
        components = json.loads(result)
        assert isinstance(components, list)
        names = [c["name"] for c in components]
        for expected in ["model", "service", "route"]:
            assert expected in names
        for comp in components:
            assert all(key in comp for key in ["name", "description", "project_types"])


# ============================================================================
# create_project Tool Tests
# ============================================================================


class TestCreateProject:
    """Tests for create_project tool."""

    @pytest.mark.asyncio
    async def test_create_python_cli(self, tmp_path) -> None:
        """Test creating a python-cli project."""
        result = await create_project(
            name="my-cli-app",
            template="python-cli",
            path=str(tmp_path),
        )

        assert "Created project 'my_cli_app'" in result
        assert "python-cli" in result

        # Check files were created
        project_dir = tmp_path / "my_cli_app"
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "src" / "my_cli_app" / "__init__.py").exists()
        assert (project_dir / "src" / "my_cli_app" / "cli.py").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "tests" / "conftest.py").exists()

    @pytest.mark.asyncio
    async def test_create_with_typer_option(self, tmp_path) -> None:
        """Test creating project with use_typer option."""
        result = await create_project(
            name="typer-app",
            template="python-cli",
            path=str(tmp_path),
            options='{"use_typer": true}',
        )

        assert "Created project 'typer_app'" in result

        # Check typer CLI was created
        cli_file = tmp_path / "typer_app" / "src" / "typer_app" / "cli.py"
        content = cli_file.read_text()
        assert "typer" in content.lower()

        # Check pyproject has typer dependency
        pyproject = tmp_path / "typer_app" / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        assert "typer" in pyproject_content

    @pytest.mark.asyncio
    async def test_create_with_docker_option(self, tmp_path) -> None:
        """Test creating project with include_docker option."""
        result = await create_project(
            name="docker-app",
            template="python-cli",
            path=str(tmp_path),
            options='{"include_docker": true}',
        )

        assert "Created project" in result
        assert (tmp_path / "docker_app" / "Dockerfile").exists()

    @pytest.mark.asyncio
    async def test_create_fastapi(self, tmp_path) -> None:
        """Test creating a FastAPI project."""
        result = await create_project(
            name="my-api",
            template="fastapi",
            path=str(tmp_path),
        )

        assert "Created project 'my_api'" in result
        assert "fastapi" in result

        project_dir = tmp_path / "my_api"
        assert (project_dir / "src" / "my_api" / "main.py").exists()
        assert (project_dir / "src" / "my_api" / "api" / "routes.py").exists()
        assert (project_dir / "src" / "my_api" / "core" / "config.py").exists()

    @pytest.mark.asyncio
    async def test_create_python_lib(self, tmp_path) -> None:
        """Test creating a Python library project."""
        result = await create_project(
            name="my-lib",
            template="python-lib",
            path=str(tmp_path),
        )

        assert "Created project 'my_lib'" in result

        project_dir = tmp_path / "my_lib"
        assert (project_dir / "src" / "my_lib" / "__init__.py").exists()
        assert (project_dir / "tests" / "test_my_lib.py").exists()

    @pytest.mark.asyncio
    async def test_unknown_template(self, tmp_path) -> None:
        """Test error for unknown template."""
        result = await create_project(
            name="test",
            template="nonexistent",
            path=str(tmp_path),
        )

        assert "Error: Unknown template" in result
        assert "nonexistent" in result

    @pytest.mark.asyncio
    async def test_invalid_project_name(self, tmp_path) -> None:
        """Test error for invalid project name."""
        result = await create_project(
            name="@@@",
            template="python-cli",
            path=str(tmp_path),
        )

        assert "Error: Invalid project name" in result

    @pytest.mark.asyncio
    async def test_invalid_options_json(self, tmp_path) -> None:
        """Test error for invalid options JSON."""
        result = await create_project(
            name="test",
            template="python-cli",
            path=str(tmp_path),
            options="not valid json",
        )

        assert "Error: Invalid options JSON" in result

    @pytest.mark.asyncio
    async def test_directory_already_exists(self, tmp_path) -> None:
        """Test error when directory already exists."""
        existing = tmp_path / "existing"
        existing.mkdir()

        result = await create_project(
            name="existing",
            template="python-cli",
            path=str(tmp_path),
        )

        assert "Error: Directory already exists" in result

    @pytest.mark.asyncio
    async def test_next_steps_included(self, tmp_path) -> None:
        """Test that next steps are included in output."""
        result = await create_project(
            name="test-app",
            template="python-cli",
            path=str(tmp_path),
        )

        assert "Next steps:" in result
        assert "pip install" in result

    @pytest.mark.asyncio
    async def test_template_rendering(self, tmp_path) -> None:
        """Test that templates are properly rendered."""
        result = await create_project(
            name="my-app",
            template="python-cli",
            path=str(tmp_path),
            options='{"description": "My awesome app"}',
        )

        assert "Created project" in result

        # Check content was rendered
        init_file = tmp_path / "my_app" / "src" / "my_app" / "__init__.py"
        content = init_file.read_text()
        assert "my_app" in content
        assert "My awesome app" in content


# ============================================================================
# add_component Tool Tests
# ============================================================================


class TestAddComponent:
    """Tests for add_component tool."""

    @pytest.fixture
    def setup_project(self, tmp_path):
        """Set up a basic Python project structure."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create pyproject.toml
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test_project"\nversion = "0.1.0"')

        # Create src structure
        src_dir = project_dir / "src" / "test_project"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").touch()

        # Create tests directory
        tests_dir = project_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()

        return project_dir

    @pytest.mark.asyncio
    async def test_add_model(self, setup_project) -> None:
        """Test adding a model component."""
        result = await add_component(
            component="model",
            name="user",
            path=str(setup_project),
        )

        assert "Added component 'model'" in result
        assert "user" in result

        # Check files were created
        model_file = setup_project / "src" / "test_project" / "models" / "user.py"
        assert model_file.exists()

        content = model_file.read_text()
        assert "class User" in content

    @pytest.mark.asyncio
    async def test_add_service(self, setup_project) -> None:
        """Test adding a service component."""
        result = await add_component(
            component="service",
            name="auth",
            path=str(setup_project),
        )

        assert "Added component 'service'" in result

        service_file = setup_project / "src" / "test_project" / "services" / "auth.py"
        assert service_file.exists()

        content = service_file.read_text()
        assert "class AuthService" in content

    @pytest.mark.asyncio
    async def test_add_test(self, setup_project) -> None:
        """Test adding a test file."""
        result = await add_component(
            component="test",
            name="utils",
            path=str(setup_project),
        )

        assert "Added component 'test'" in result

        test_file = setup_project / "tests" / "test_utils.py"
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_unknown_component(self, setup_project) -> None:
        """Test error for unknown component."""
        result = await add_component(
            component="unknown",
            name="foo",
            path=str(setup_project),
        )

        assert "Error: Unknown component" in result

    @pytest.mark.asyncio
    async def test_invalid_component_name(self, setup_project) -> None:
        """Test error for invalid component name."""
        result = await add_component(
            component="model",
            name="@@@",
            path=str(setup_project),
        )

        assert "Error: Invalid component name" in result

    @pytest.mark.asyncio
    async def test_no_project_detected(self, tmp_path) -> None:
        """Test error when no project is detected."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = await add_component(
            component="model",
            name="test",
            path=str(empty_dir),
        )

        # Should fall back to directory name
        assert "Added component" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_file_already_exists(self, setup_project) -> None:
        """Test that existing files are skipped."""
        # Create the model file first
        models_dir = setup_project / "src" / "test_project" / "models"
        models_dir.mkdir(parents=True)
        existing = models_dir / "user.py"
        existing.write_text("# Existing content")

        result = await add_component(
            component="model",
            name="user",
            path=str(setup_project),
        )

        assert "skipped - exists" in result

        # Verify original content preserved
        assert existing.read_text() == "# Existing content"

    @pytest.mark.asyncio
    async def test_invalid_options_json(self, setup_project) -> None:
        """Test error for invalid options JSON."""
        result = await add_component(
            component="model",
            name="user",
            path=str(setup_project),
            options="invalid json",
        )

        assert "Error: Invalid options JSON" in result


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestPropertyBasedScaffold:
    """Property-based tests for scaffolding."""

    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    def test_prop_normalize_preserves_valid_chars(self, name: str) -> None:
        """Property: normalization preserves alphanumeric chars."""
        normalized = _normalize_project_name(name)
        # All chars in normalized should be alphanumeric or underscore
        assert all(c.isalnum() or c == "_" for c in normalized)

    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        name=st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L",))),
    )
    def test_prop_normalize_lowercase(self, name: str) -> None:
        """Property: normalization produces lowercase output."""
        normalized = _normalize_project_name(name)
        assert normalized == normalized.lower()

    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        name=st.text(min_size=1, max_size=15, alphabet=st.sampled_from("abc_-")),
    )
    def test_prop_to_class_name_capitalizes(self, name: str) -> None:
        """Property: class name has capitalized parts."""
        class_name = _to_class_name(name)
        if class_name:  # Skip empty results
            assert class_name[0].isupper() or not class_name[0].isalpha()

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        template=st.text(min_size=1, max_size=100),
        value=st.text(min_size=1, max_size=20).filter(lambda v: "{name}" not in v),
    )
    def test_prop_render_replaces_placeholder(self, template: str, value: str) -> None:
        """Property: render replaces {name} with value."""
        content = "prefix {name} suffix"
        result = _render_template(content, {"name": value})
        # The placeholder should be replaced (filter excludes values containing {name})
        assert "{name}" not in result
        assert value in result

    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        template=st.sampled_from(list(TEMPLATES.keys())),
    )
    @pytest.mark.asyncio
    async def test_prop_create_project_valid_templates(self, tmp_path, template: str) -> None:
        """Property: all built-in templates create valid projects."""
        # Use UUID to ensure unique directory per example
        unique_id = uuid.uuid4().hex[:8]
        project_name = f"test_{unique_id}"
        test_dir = tmp_path / unique_id
        test_dir.mkdir()

        result = await create_project(
            name=project_name,
            template=template,
            path=str(test_dir),
        )

        assert "Created project" in result
        project_dir = test_dir / project_name
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists() or (project_dir / "README.md").exists()


# ============================================================================
# Integration Tests
# ============================================================================


class TestScaffoldIntegration:
    """Integration tests for scaffolding tools."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path) -> None:
        """Test full workflow: create project, add components."""
        # 1. Create project
        create_result = await create_project(
            name="full-app",
            template="python-cli",
            path=str(tmp_path),
        )
        assert "Created project 'full_app'" in create_result

        project_path = tmp_path / "full_app"

        # 2. Add model
        model_result = await add_component(
            component="model",
            name="user",
            path=str(project_path),
        )
        assert "Added component 'model'" in model_result

        # 3. Add service
        service_result = await add_component(
            component="service",
            name="user",
            path=str(project_path),
        )
        assert "Added component 'service'" in service_result

        # Verify all files exist
        assert (project_path / "src" / "full_app" / "models" / "user.py").exists()
        assert (project_path / "src" / "full_app" / "services" / "user.py").exists()
        assert (project_path / "tests" / "test_user_model.py").exists()
        assert (project_path / "tests" / "test_user_service.py").exists()

    @pytest.mark.asyncio
    async def test_fastapi_workflow(self, tmp_path) -> None:
        """Test FastAPI project workflow."""
        # Create FastAPI project
        create_result = await create_project(
            name="api-app",
            template="fastapi",
            path=str(tmp_path),
        )
        assert "Created project 'api_app'" in create_result

        project_path = tmp_path / "api_app"

        # Add route
        route_result = await add_component(
            component="route",
            name="users",
            path=str(project_path),
        )
        assert "Added component 'route'" in route_result

        # Verify
        assert (project_path / "src" / "api_app" / "api" / "users.py").exists()

    @pytest.mark.asyncio
    async def test_list_then_create(self, tmp_path) -> None:
        """Test listing templates then creating from one."""
        # List available templates
        list_result = await list_templates()
        templates = json.loads(list_result)

        # Pick first template
        template_name = templates[0]["name"]

        # Create project from it
        result = await create_project(
            name="from-list",
            template=template_name,
            path=str(tmp_path),
        )

        assert "Created project" in result


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_deeply_nested_path(self, tmp_path) -> None:
        """Test creating project in deeply nested path."""
        deep_path = tmp_path / "a" / "b" / "c" / "d"
        deep_path.mkdir(parents=True)

        result = await create_project(
            name="deep",
            template="python-cli",
            path=str(deep_path),
        )

        assert "Created project" in result
        assert (deep_path / "deep" / "pyproject.toml").exists()

    @pytest.mark.asyncio
    async def test_unicode_in_description(self, tmp_path) -> None:
        """Test project with unicode in description."""
        result = await create_project(
            name="unicode-test",
            template="python-cli",
            path=str(tmp_path),
            options='{"description": "A project with emojis 🚀 and unicode: こんにちは"}',
        )

        assert "Created project" in result

        readme = tmp_path / "unicode_test" / "README.md"
        content = readme.read_text(encoding="utf-8")
        assert "🚀" in content
        assert "こんにちは" in content

    @pytest.mark.asyncio
    async def test_empty_options(self, tmp_path) -> None:
        """Test project with empty options object."""
        result = await create_project(
            name="empty-opts",
            template="python-cli",
            path=str(tmp_path),
            options="{}",
        )

        assert "Created project" in result

    @pytest.mark.asyncio
    async def test_component_with_numbers(self, tmp_path) -> None:
        """Test component name with numbers."""
        # Set up project
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text('[project]\nname = "test_project"')
        src_dir = project_dir / "src" / "test_project"
        src_dir.mkdir(parents=True)

        result = await add_component(
            component="model",
            name="user123",
            path=str(project_dir),
        )

        assert "Added component" in result
        assert (project_dir / "src" / "test_project" / "models" / "user123.py").exists()
