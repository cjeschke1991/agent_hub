import pytest

from agent_hub.agents.pinball_tracker.logic import (
    Machine,
    MaintenanceEntry,
    Mod,
    PinballDeleteError,
    create_machine,
    create_maintenance,
    create_mod,
    delete_machine,
    list_machines,
    update_machine,
)


def test_machine_crud(hub_config):
    created = create_machine(
        Machine(name="Godzilla", manufacturer="Stern", year=2021, ruleset="1.02"),
        hub_config,
    )
    assert created.id is not None

    machines = list_machines(hub_config)
    assert len(machines) == 1
    assert machines[0].name == "Godzilla"

    created.ruleset = "1.03"
    update_machine(created, hub_config)
    refreshed = list_machines(hub_config)[0]
    assert refreshed.ruleset == "1.03"


def test_delete_machine_blocked_with_active_children(hub_config):
    machine = create_machine(Machine(name="Whitewater"), hub_config)
    create_maintenance(
        MaintenanceEntry(machine_id=machine.id, entry_type="issue", title="Broken ramp"),
        hub_config,
    )
    create_mod(Mod(machine_id=machine.id, name="LED kit"), hub_config)

    with pytest.raises(PinballDeleteError) as exc_info:
        delete_machine(machine.id, config=hub_config)

    assert exc_info.value.maintenance_count == 1
    assert exc_info.value.mod_count == 1

    delete_machine(machine.id, force=True, config=hub_config)
    assert list_machines(hub_config) == []
