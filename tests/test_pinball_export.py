from agent_hub.agents.pinball_tracker.logic import (
    Machine,
    MaintenanceEntry,
    Mod,
    Skill,
    create_machine,
    create_maintenance,
    create_mod,
    create_skill,
    export_status,
)


def test_export_status_counts(hub_config):
    machine = create_machine(Machine(name="GOT"), hub_config)
    create_maintenance(
        MaintenanceEntry(machine_id=machine.id, entry_type="issue", title="Switch error"),
        hub_config,
    )
    create_maintenance(
        MaintenanceEntry(
            machine_id=machine.id,
            entry_type="scheduled",
            title="Rebuild flippers",
            due_date="2020-01-01",
        ),
        hub_config,
    )
    create_mod(Mod(machine_id=machine.id, name="Custom topper"), hub_config)
    create_skill(Skill(name="Multimeter basics", tags=["electrical"]), hub_config)

    status = export_status(hub_config)
    assert status["machine_count"] == 1
    assert status["open_issue_count"] == 1
    assert status["open_scheduled_count"] == 1
    assert status["overdue_scheduled_count"] == 1
    assert status["planned_mod_count"] == 1
    assert status["skills_to_learn_count"] == 1
