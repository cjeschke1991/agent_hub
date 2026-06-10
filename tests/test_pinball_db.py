from agent_hub.core.pinball_db import init_db, pinball_db_path


def test_init_db_idempotent(hub_config):
    first = init_db(hub_config)
    second = init_db(hub_config)
    assert first == second == pinball_db_path(hub_config)
    assert first.exists()
