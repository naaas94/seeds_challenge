from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

REQUIRED_PACKAGES = {
    "fastapi",
    "uvicorn[standard]",
    "langchain-core",
    "langchain-openai",
    "pydantic-settings",
    "yfinance",
}

PACKAGE_INIT_FILES = (
    REPO_ROOT / "app" / "__init__.py",
    REPO_ROOT / "app" / "agent" / "__init__.py",
    REPO_ROOT / "app" / "memory" / "__init__.py",
    REPO_ROOT / "tests" / "__init__.py",
)


def _requirements_lines() -> list[str]:
    return [
        line.strip()
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_requirements_contains_required_packages():
    assert REQUIRED_PACKAGES.issubset(set(_requirements_lines()))


def test_requirements_includes_pydantic_settings():
    assert "pydantic-settings" in _requirements_lines()


def test_requirements_rejects_bare_langchain_line():
    packages = _requirements_lines()
    assert "langchain" not in packages
    assert "pydantic-settings" in packages


def test_requirements_rejects_version_pinned_umbrella_langchain():
    allowed_langchain_prefixes = ("langchain-core", "langchain-openai")
    for package in _requirements_lines():
        base = package.split("==")[0].split("[")[0].strip()
        if base == "langchain" or (
            base.startswith("langchain") and not base.startswith(allowed_langchain_prefixes)
        ):
            raise AssertionError(f"forbidden langchain package line: {package}")


def test_package_init_files_exist_and_are_empty():
    for init_file in PACKAGE_INIT_FILES:
        assert init_file.is_file(), f"missing package marker: {init_file}"
        assert init_file.read_text(encoding="utf-8") == ""


def test_env_example_documents_required_keys():
    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=" in content
    assert "MODEL_NAME=" in content


def test_agent_and_memory_packages_are_importable():
    import app.agent  # noqa: F401
    import app.memory  # noqa: F401
