from agent_hub.agents.pinball_tracker.logic import (
    Machine,
    Mod,
    complete_mod,
    create_machine,
    create_mod,
    list_mods,
)


def test_mod_project_fields(hub_config):
    machine = create_machine(Machine(name="AFM"), hub_config)
    mod = create_mod(
        Mod(
            machine_id=machine.id,
            name="Shaker motor",
            description="Add shaker",
            priority="high",
            estimated_cost=125.50,
            parts="Motor, bracket",
            install_notes="Mount under cabinet",
        ),
        hub_config,
    )

    mods = list_mods(machine_id=machine.id, status="planned", config=hub_config)
    assert len(mods) == 1
    assert mods[0].estimated_cost == 125.50
    assert mods[0].name == mod.name


def test_complete_mod(hub_config):
    machine = create_machine(Machine(name="TAF"), hub_config)
    mod = create_mod(Mod(machine_id=machine.id, name="Mirror blades"), hub_config)

    completed = complete_mod(mod.id, before_after_notes="Much brighter playfield", config=hub_config)
    assert completed.status == "done"
    assert completed.before_after_notes == "Much brighter playfield"
    assert completed.completed_at is not None
