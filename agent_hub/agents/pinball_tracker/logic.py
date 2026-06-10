from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.pinball_db import connect, init_db, pinball_db_path
from agent_hub.core.slices import utc_now_iso


class PinballDeleteError(Exception):
    def __init__(self, message: str, maintenance_count: int = 0, mod_count: int = 0):
        super().__init__(message)
        self.maintenance_count = maintenance_count
        self.mod_count = mod_count


class PinballValidationError(Exception):
    pass


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(tag) for tag in parsed]
    except json.JSONDecodeError:
        pass
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _dump_tags(tags: list[str] | None) -> str | None:
    if not tags:
        return None
    cleaned = [tag.strip() for tag in tags if tag.strip()]
    return json.dumps(cleaned) if cleaned else None


def ensure_db(config: HubConfig | None = None) -> None:
    init_db(config)


@dataclass
class Machine:
    id: int | None = None
    name: str = ""
    manufacturer: str | None = None
    year: int | None = None
    edition: str | None = None
    ruleset: str | None = None
    description: str | None = None
    location: str | None = None
    notes: str | None = None
    opdb_id: str | None = None
    external_metadata_json: str | None = None
    image_path: str | None = None
    rulesheet_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class MaintenanceEntry:
    id: int | None = None
    machine_id: int = 0
    entry_type: str = "issue"
    title: str = ""
    description: str | None = None
    status: str = "open"
    priority: str = "medium"
    due_date: str | None = None
    completed_at: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Mod:
    id: int | None = None
    machine_id: int = 0
    name: str = ""
    description: str | None = None
    status: str = "planned"
    priority: str = "medium"
    estimated_cost: float | None = None
    parts: str | None = None
    install_notes: str | None = None
    before_after_notes: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Skill:
    id: int | None = None
    name: str = ""
    description: str | None = None
    status: str = "want_to_learn"
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _validate_external_metadata(value: str | None) -> None:
    if value is None or not value.strip():
        return
    json.loads(value)


def list_machines(config: HubConfig | None = None) -> list[Machine]:
    ensure_db(config)
    with connect(config=config) as conn:
        rows = conn.execute("SELECT * FROM machines ORDER BY name COLLATE NOCASE").fetchall()
    return [Machine(**_row_to_dict(row)) for row in rows]


def create_machine(machine: Machine, config: HubConfig | None = None) -> Machine:
    if not machine.name.strip():
        raise PinballValidationError("Machine name is required.")
    _validate_external_metadata(machine.external_metadata_json)
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        cursor = conn.execute(
            """
            INSERT INTO machines (
                name, manufacturer, year, edition, ruleset, description, location, notes,
                opdb_id, external_metadata_json, image_path, rulesheet_url, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                machine.name.strip(),
                machine.manufacturer,
                machine.year,
                machine.edition,
                machine.ruleset,
                machine.description,
                machine.location,
                machine.notes,
                machine.opdb_id,
                machine.external_metadata_json,
                machine.image_path,
                machine.rulesheet_url,
                now,
                now,
            ),
        )
        machine.id = int(cursor.lastrowid)
    machine.created_at = now
    machine.updated_at = now
    return machine


def update_machine(machine: Machine, config: HubConfig | None = None) -> Machine:
    if machine.id is None:
        raise PinballValidationError("Machine id is required for update.")
    if not machine.name.strip():
        raise PinballValidationError("Machine name is required.")
    _validate_external_metadata(machine.external_metadata_json)
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE machines SET
                name = ?, manufacturer = ?, year = ?, edition = ?, ruleset = ?,
                description = ?, location = ?, notes = ?, opdb_id = ?,
                external_metadata_json = ?, image_path = ?, rulesheet_url = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                machine.name.strip(),
                machine.manufacturer,
                machine.year,
                machine.edition,
                machine.ruleset,
                machine.description,
                machine.location,
                machine.notes,
                machine.opdb_id,
                machine.external_metadata_json,
                machine.image_path,
                machine.rulesheet_url,
                now,
                machine.id,
            ),
        )
    machine.updated_at = now
    return machine


def count_active_children(machine_id: int, config: HubConfig | None = None) -> tuple[int, int]:
    ensure_db(config)
    with connect(config=config) as conn:
        maintenance_count = conn.execute(
            """
            SELECT COUNT(*) FROM maintenance_entries
            WHERE machine_id = ? AND status != 'done'
            """,
            (machine_id,),
        ).fetchone()[0]
        mod_count = conn.execute(
            """
            SELECT COUNT(*) FROM mods
            WHERE machine_id = ? AND status != 'done'
            """,
            (machine_id,),
        ).fetchone()[0]
    return int(maintenance_count), int(mod_count)


def delete_machine(machine_id: int, force: bool = False, config: HubConfig | None = None) -> None:
    ensure_db(config)
    maintenance_count, mod_count = count_active_children(machine_id, config)
    if (maintenance_count or mod_count) and not force:
        raise PinballDeleteError(
            f"Machine has {maintenance_count} open maintenance item(s) and {mod_count} active mod(s).",
            maintenance_count=maintenance_count,
            mod_count=mod_count,
        )
    with connect(config=config) as conn:
        conn.execute("DELETE FROM maintenance_entries WHERE machine_id = ?", (machine_id,))
        conn.execute("DELETE FROM mods WHERE machine_id = ?", (machine_id,))
        conn.execute("DELETE FROM machines WHERE id = ?", (machine_id,))


def list_maintenance(
    machine_id: int | None = None,
    entry_type: str | None = None,
    status: str | None = None,
    config: HubConfig | None = None,
) -> list[MaintenanceEntry]:
    ensure_db(config)
    query = "SELECT * FROM maintenance_entries WHERE 1=1"
    params: list[Any] = []
    if machine_id is not None:
        query += " AND machine_id = ?"
        params.append(machine_id)
    if entry_type:
        query += " AND entry_type = ?"
        params.append(entry_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, due_date IS NULL, due_date"
    with connect(config=config) as conn:
        rows = conn.execute(query, params).fetchall()
    return [MaintenanceEntry(**_row_to_dict(row)) for row in rows]


def create_maintenance(entry: MaintenanceEntry, config: HubConfig | None = None) -> MaintenanceEntry:
    if not entry.title.strip():
        raise PinballValidationError("Maintenance title is required.")
    if not entry.machine_id:
        raise PinballValidationError("Machine is required.")
    if entry.entry_type not in {"issue", "scheduled"}:
        raise PinballValidationError("entry_type must be issue or scheduled.")
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        cursor = conn.execute(
            """
            INSERT INTO maintenance_entries (
                machine_id, entry_type, title, description, status, priority,
                due_date, completed_at, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.machine_id,
                entry.entry_type,
                entry.title.strip(),
                entry.description,
                entry.status,
                entry.priority,
                entry.due_date,
                entry.completed_at,
                entry.notes,
                now,
                now,
            ),
        )
        entry.id = int(cursor.lastrowid)
    entry.created_at = now
    entry.updated_at = now
    return entry


def update_maintenance(entry: MaintenanceEntry, config: HubConfig | None = None) -> MaintenanceEntry:
    if entry.id is None:
        raise PinballValidationError("Maintenance id is required for update.")
    if not entry.title.strip():
        raise PinballValidationError("Maintenance title is required.")
    ensure_db(config)
    now = utc_now_iso()
    completed_at = entry.completed_at
    if entry.status == "done" and not completed_at:
        completed_at = now
    if entry.status != "done":
        completed_at = None
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE maintenance_entries SET
                machine_id = ?, entry_type = ?, title = ?, description = ?, status = ?,
                priority = ?, due_date = ?, completed_at = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                entry.machine_id,
                entry.entry_type,
                entry.title.strip(),
                entry.description,
                entry.status,
                entry.priority,
                entry.due_date,
                completed_at,
                entry.notes,
                now,
                entry.id,
            ),
        )
    entry.completed_at = completed_at
    entry.updated_at = now
    return entry


def complete_maintenance(entry_id: int, config: HubConfig | None = None) -> MaintenanceEntry:
    entries = list_maintenance(config=config)
    entry = next((item for item in entries if item.id == entry_id), None)
    if entry is None:
        raise PinballValidationError(f"Maintenance entry {entry_id} not found.")
    entry.status = "done"
    return update_maintenance(entry, config=config)


def list_mods(
    machine_id: int | None = None,
    status: str | None = None,
    config: HubConfig | None = None,
) -> list[Mod]:
    ensure_db(config)
    query = "SELECT * FROM mods WHERE 1=1"
    params: list[Any] = []
    if machine_id is not None:
        query += " AND machine_id = ?"
        params.append(machine_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += """
        ORDER BY CASE status WHEN 'planned' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
        CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
        name COLLATE NOCASE
    """
    with connect(config=config) as conn:
        rows = conn.execute(query, params).fetchall()
    return [Mod(**_row_to_dict(row)) for row in rows]


def create_mod(mod: Mod, config: HubConfig | None = None) -> Mod:
    if not mod.name.strip():
        raise PinballValidationError("Mod name is required.")
    if not mod.machine_id:
        raise PinballValidationError("Machine is required.")
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        cursor = conn.execute(
            """
            INSERT INTO mods (
                machine_id, name, description, status, priority, estimated_cost,
                parts, install_notes, before_after_notes, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mod.machine_id,
                mod.name.strip(),
                mod.description,
                mod.status,
                mod.priority,
                mod.estimated_cost,
                mod.parts,
                mod.install_notes,
                mod.before_after_notes,
                mod.completed_at,
                now,
                now,
            ),
        )
        mod.id = int(cursor.lastrowid)
    mod.created_at = now
    mod.updated_at = now
    return mod


def update_mod(mod: Mod, config: HubConfig | None = None) -> Mod:
    if mod.id is None:
        raise PinballValidationError("Mod id is required for update.")
    if not mod.name.strip():
        raise PinballValidationError("Mod name is required.")
    ensure_db(config)
    now = utc_now_iso()
    completed_at = mod.completed_at
    if mod.status == "done" and not completed_at:
        completed_at = now
    if mod.status != "done":
        completed_at = None
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE mods SET
                machine_id = ?, name = ?, description = ?, status = ?, priority = ?,
                estimated_cost = ?, parts = ?, install_notes = ?, before_after_notes = ?,
                completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                mod.machine_id,
                mod.name.strip(),
                mod.description,
                mod.status,
                mod.priority,
                mod.estimated_cost,
                mod.parts,
                mod.install_notes,
                mod.before_after_notes,
                completed_at,
                now,
                mod.id,
            ),
        )
    mod.completed_at = completed_at
    mod.updated_at = now
    return mod


def complete_mod(mod_id: int, before_after_notes: str | None = None, config: HubConfig | None = None) -> Mod:
    mods = list_mods(config=config)
    mod = next((item for item in mods if item.id == mod_id), None)
    if mod is None:
        raise PinballValidationError(f"Mod {mod_id} not found.")
    mod.status = "done"
    if before_after_notes:
        mod.before_after_notes = before_after_notes
    return update_mod(mod, config=config)


def _skill_from_row(row: Any) -> Skill:
    data = _row_to_dict(row)
    tags = _parse_tags(data.pop("tags", None))
    return Skill(**data, tags=tags)


def list_skills(
    status: str | None = None,
    tag: str | None = None,
    config: HubConfig | None = None,
) -> list[Skill]:
    ensure_db(config)
    query = "SELECT * FROM skills WHERE 1=1"
    params: list[Any] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY CASE status WHEN 'want_to_learn' THEN 0 ELSE 1 END, name COLLATE NOCASE"
    with connect(config=config) as conn:
        rows = conn.execute(query, params).fetchall()
    skills = [_skill_from_row(row) for row in rows]
    if tag:
        tag_lower = tag.lower()
        skills = [skill for skill in skills if any(item.lower() == tag_lower for item in skill.tags)]
    return skills


def create_skill(skill: Skill, config: HubConfig | None = None) -> Skill:
    if not skill.name.strip():
        raise PinballValidationError("Skill name is required.")
    ensure_db(config)
    now = utc_now_iso()
    with connect(config=config) as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (name, description, status, tags, notes, completed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill.name.strip(),
                skill.description,
                skill.status,
                _dump_tags(skill.tags),
                skill.notes,
                skill.completed_at,
                now,
                now,
            ),
        )
        skill.id = int(cursor.lastrowid)
    skill.created_at = now
    skill.updated_at = now
    return skill


def update_skill(skill: Skill, config: HubConfig | None = None) -> Skill:
    if skill.id is None:
        raise PinballValidationError("Skill id is required for update.")
    if not skill.name.strip():
        raise PinballValidationError("Skill name is required.")
    ensure_db(config)
    now = utc_now_iso()
    completed_at = skill.completed_at
    if skill.status == "learned" and not completed_at:
        completed_at = now
    if skill.status != "learned":
        completed_at = None
    with connect(config=config) as conn:
        conn.execute(
            """
            UPDATE skills SET
                name = ?, description = ?, status = ?, tags = ?, notes = ?,
                completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                skill.name.strip(),
                skill.description,
                skill.status,
                _dump_tags(skill.tags),
                skill.notes,
                completed_at,
                now,
                skill.id,
            ),
        )
    skill.completed_at = completed_at
    skill.updated_at = now
    return skill


def mark_skill_learned(skill_id: int, config: HubConfig | None = None) -> Skill:
    skills = list_skills(config=config)
    skill = next((item for item in skills if item.id == skill_id), None)
    if skill is None:
        raise PinballValidationError(f"Skill {skill_id} not found.")
    skill.status = "learned"
    return update_skill(skill, config=config)


def export_status(config: HubConfig | None = None) -> dict[str, Any]:
    ensure_db(config)
    config = config or load_config()
    today = utc_now_iso()[:10]
    machines = list_machines(config)
    open_issues = list_maintenance(entry_type="issue", status="open", config=config)
    open_issues.extend(list_maintenance(entry_type="issue", status="in_progress", config=config))
    scheduled_open = list_maintenance(entry_type="scheduled", status="open", config=config)
    scheduled_open.extend(list_maintenance(entry_type="scheduled", status="in_progress", config=config))
    overdue = [entry for entry in scheduled_open if entry.due_date and entry.due_date < today]
    planned_mods = list_mods(status="planned", config=config)
    in_progress_mods = list_mods(status="in_progress", config=config)
    skills_to_learn = list_skills(status="want_to_learn", config=config)

    return {
        "machine_count": len(machines),
        "open_issue_count": len(open_issues),
        "open_scheduled_count": len(scheduled_open),
        "overdue_scheduled_count": len(overdue),
        "planned_mod_count": len(planned_mods),
        "in_progress_mod_count": len(in_progress_mods),
        "skills_to_learn_count": len(skills_to_learn),
        "db_path": str(pinball_db_path(config)),
    }
