from agent_hub.core.config import load_config


def test_load_config_reads_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('TMDB_API_KEY="dotenv-tmdb-key"\nOMDB_API_KEY=dotenv-omdb-key\n', encoding="utf-8")
    monkeypatch.setenv("TMDB_API_KEY", "")
    monkeypatch.setenv("OMDB_API_KEY", "")
    monkeypatch.setattr("agent_hub.core.config.PROJECT_ROOT", tmp_path)

    config = load_config(tmp_path / "missing-config.yaml")

    assert config.tmdb.api_key == "dotenv-tmdb-key"
    assert config.omdb.api_key == "dotenv-omdb-key"
