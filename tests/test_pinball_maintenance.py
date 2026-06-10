from agent_hub.agents.pinball_tracker.logic import (
    Machine,
    MaintenanceEntry,
    complete_maintenance,
    create_machine,
    create_maintenance,
    list_maintenance,
)


def test_maintenance_issue_and_scheduled(hub_config):
    machine = create_machine(Machine(name="Jurassic Park"), hub_config)

    issue = create_maintenance(
        MaintenanceEntry(machine_id=machine.id, entry_type="issue", title="Left flipper weak"),
        hub_config,
    )
    scheduled = create_maintenance(
        MaintenanceEntry(
            machine_id=machine.id,
            entry_type="scheduled",
            title="Wax playfield",
            due_date="2026-07-01",
        ),
        hub_config,
    )

    issues = list_maintenance(machine_id=machine.id, entry_type="issue", config=hub_config)
    scheduled_items = list_maintenance(machine_id=machine.id, entry_type="scheduled", config=hub_config)
    assert len(issues) == 1
    assert len(scheduled_items) == 1
    assert issues[0].title == issue.title
    assert scheduled_items[0].due_date == scheduled.due_date


def test_complete_maintenance_sets_done(hub_config):
    machine = create_machine(Machine(name="MM"), hub_config)
    entry = create_maintenance(
        MaintenanceEntry(machine_id=machine.id, entry_type="issue", title="Test lamp"),
        hub_config,
    )

    completed = complete_maintenance(entry.id, hub_config)
    assert completed.status == "done"
    assert completed.completed_at is not None
