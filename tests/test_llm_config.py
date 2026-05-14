import os

from srezero.llm_config import LLMConfig, load_env_file


def test_load_env_file_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_BASE_URL=https://example.test/v1\n"
        "OPENAI_MODEL=from-file\n"
        "SREZERO_LLM_TIMEOUT_SECONDS=12\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_MODEL", "from-env")

    loaded = load_env_file(env_file)

    assert loaded["OPENAI_MODEL"] == "from-file"
    assert os.environ["OPENAI_MODEL"] == "from-env"


def test_load_env_file_discovers_parent_env_from_subdirectory(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    nested = tmp_path / "eval"
    nested.mkdir()
    env_file.write_text(
        "OPENAI_BASE_URL=https://example.test/v1\n"
        "OPENAI_MODEL=parent-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(nested)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    loaded = load_env_file()

    assert loaded["OPENAI_MODEL"] == "parent-file-model"
    assert os.environ["OPENAI_BASE_URL"] == "https://example.test/v1"


def test_llm_config_uses_profile_model_override(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "fallback-model")
    monkeypatch.setenv("SREZERO_REACT_MODEL", "react-model")

    config = LLMConfig.from_env("react")

    assert config.base_url == "https://example.test/v1"
    assert config.model == "react-model"
