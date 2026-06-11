from agent_hub.core.movie_db import init_db, movie_db_path


def test_init_db_idempotent(hub_config):
    first = init_db(hub_config)
    second = init_db(hub_config)
    assert first == second == movie_db_path(hub_config)
    assert first.exists()
