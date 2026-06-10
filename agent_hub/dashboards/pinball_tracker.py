from __future__ import annotations

from pathlib import Path

import streamlit as st

from agent_hub.agents.pinball_tracker.logic import (
    Machine,
    MaintenanceEntry,
    Mod,
    PinballDeleteError,
    PinballValidationError,
    Skill,
    complete_maintenance,
    complete_mod,
    create_machine,
    create_maintenance,
    create_mod,
    create_skill,
    delete_machine,
    ensure_db,
    list_machines,
    list_maintenance,
    list_mods,
    list_skills,
    mark_skill_learned,
    update_machine,
)
from agent_hub.core.config import load_config

PRIORITIES = ["low", "medium", "high", "urgent"]
MAINTENANCE_STATUSES = ["open", "in_progress", "done"]
MOD_STATUSES = ["planned", "in_progress", "done"]
TAG_SUGGESTIONS = ["electrical", "mechanical", "rules", "soldering", "playfield", "software"]


def _rulesheet_link(machine: Machine | None) -> None:
    if machine and machine.rulesheet_url:
        st.link_button("Rulesheet", machine.rulesheet_url, key=f"rulesheet_{machine.id}_detail")


def _view_machine(machine_id: int) -> None:
    st.session_state.pinball_view_machine_id = machine_id
    st.session_state.pinball_machine_id = machine_id


def _render_machine_card(machine: Machine) -> None:
    image_path = _machine_image_path(machine)
    if image_path:
        st.image(str(image_path), use_container_width=True)
        st.button(
            "View",
            key=f"pinball_view_{machine.id}",
            on_click=_view_machine,
            args=(machine.id,),
            use_container_width=True,
        )
    st.button(
        machine.name,
        key=f"pinball_name_{machine.id}",
        on_click=_view_machine,
        args=(machine.id,),
        use_container_width=True,
        type="tertiary",
    )
    st.caption(
        f"{machine.manufacturer or 'Unknown'} · {machine.edition or '—'} · {machine.year or '—'}"
    )


def _machine_image_path(machine: Machine) -> Path | None:
    if not machine.image_path:
        return None
    path = load_config().data_dir / machine.image_path
    return path if path.exists() else None


def _machine_label(machine: Machine) -> str:
    parts = [machine.name]
    if machine.manufacturer:
        parts.append(machine.manufacturer)
    if machine.year:
        parts.append(str(machine.year))
    return " — ".join(parts)


def _init_session_state() -> None:
    if "pinball_machine_id" not in st.session_state:
        st.session_state.pinball_machine_id = None
    if "pinball_view_machine_id" not in st.session_state:
        st.session_state.pinball_view_machine_id = None
    if "pinball_show_add_form" not in st.session_state:
        st.session_state.pinball_show_add_form = False


def _selected_machine_id(machines: list[Machine]) -> int | None:
    if not machines:
        st.session_state.pinball_machine_id = None
        return None
    labels = {_machine_label(machine): machine.id for machine in machines}
    options = list(labels.keys())
    current = st.session_state.pinball_machine_id
    default_index = 0
    if current is not None:
        for index, machine in enumerate(machines):
            if machine.id == current:
                default_index = index
                break
    choice = st.sidebar.selectbox("Machine", options, index=default_index)
    machine_id = labels[choice]
    st.session_state.pinball_machine_id = machine_id
    return machine_id


def _render_machine_list() -> None:
    machines = list_machines()
    st.subheader("Your Machines")

    if not machines:
        st.info("Add your first machine below.")
    else:
        st.markdown(
            """
            <style>
            [class*="st-key-pinball_view_"] button {
                margin-top: -14rem !important;
                height: 14rem !important;
                min-height: 14rem !important;
                opacity: 0 !important;
                border: none !important;
                background: transparent !important;
                margin-bottom: -2.5rem !important;
                cursor: pointer !important;
                position: relative !important;
                z-index: 5 !important;
                font-size: 0 !important;
                color: transparent !important;
            }
            [class*="st-key-pinball_name_"] button {
                font-size: 1.25rem !important;
                font-weight: 600 !important;
                justify-content: flex-start !important;
                padding-left: 0 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(min(len(machines), 3))
        for index, machine in enumerate(machines):
            with cols[index % len(cols)]:
                _render_machine_card(machine)

        view_id = st.session_state.get("pinball_view_machine_id")
        if view_id:
            selected = next((machine for machine in machines if machine.id == view_id), None)
            if selected:
                st.divider()
                detail_col, image_col = st.columns([2, 1])
                with image_col:
                    image_path = _machine_image_path(selected)
                    if image_path:
                        st.image(str(image_path), use_container_width=True)
                with detail_col:
                    st.markdown(f"## {selected.name}")
                    st.markdown(
                        f"**{selected.manufacturer or '—'}** · **{selected.edition or '—'}** · **{selected.year or '—'}**"
                    )
                    st.markdown(f"**Ruleset:** {selected.ruleset or '—'}")
                    _rulesheet_link(selected)
                    st.markdown(f"**Location:** {selected.location or '—'}")
                    if selected.opdb_id:
                        st.markdown(f"**Reference ID:** `{selected.opdb_id}`")
                    if selected.description:
                        st.write(selected.description)
                    if selected.notes:
                        st.info(selected.notes)
                    if st.button("Edit machine", key=f"edit_machine_{selected.id}"):
                        st.session_state.pinball_edit_machine_id = selected.id
                        st.rerun()

    st.divider()
    edit_id = st.session_state.get("pinball_edit_machine_id")
    editing = next((machine for machine in machines if machine.id == edit_id), None)
    show_form = editing is not None or st.session_state.pinball_show_add_form

    if not show_form:
        st.markdown(
            """
            <style>
            .st-key-add_machine_toggle button {
                background-color: #16a34a !important;
                border-color: #16a34a !important;
                color: #ffffff !important;
            }
            .st-key-add_machine_toggle button:hover {
                background-color: #15803d !important;
                border-color: #15803d !important;
                color: #ffffff !important;
            }
            .st-key-add_machine_toggle button:focus {
                box-shadow: 0 0 0 0.2rem rgba(22, 163, 74, 0.35) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Add Machine", type="primary", use_container_width=True, key="add_machine_toggle"):
            st.session_state.pinball_show_add_form = True
            st.rerun()
    else:
        if editing is None:
            if st.button("Cancel", key="cancel_add_machine"):
                st.session_state.pinball_show_add_form = False
                st.rerun()

        with st.form("machine_form", clear_on_submit=not bool(editing)):
            st.markdown("### Add Machine" if editing is None else f"### Edit {editing.name}")
            name = st.text_input("Name *", value=editing.name if editing else "")
            col1, col2 = st.columns(2)
            with col1:
                manufacturer = st.text_input("Manufacturer", value=editing.manufacturer if editing else "")
                year = st.number_input(
                    "Year",
                    min_value=1900,
                    max_value=2100,
                    value=editing.year if editing and editing.year else 1990,
                    step=1,
                )
                edition = st.text_input("Edition", value=editing.edition if editing else "")
            with col2:
                ruleset = st.text_input("Ruleset", value=editing.ruleset if editing else "")
                location = st.text_input("Location", value=editing.location if editing else "")
                opdb_id = st.text_input("OPDB ID (future lookup)", value=editing.opdb_id if editing else "")
            description = st.text_area("Description", value=editing.description if editing else "")
            notes = st.text_area("Notes", value=editing.notes if editing else "")
            submitted = st.form_submit_button("Save Machine" if editing else "Add Machine")

        if submitted:
            payload = Machine(
                id=editing.id if editing else None,
                name=name,
                manufacturer=manufacturer or None,
                year=int(year) if year else None,
                edition=edition or None,
                ruleset=ruleset or None,
                description=description or None,
                location=location or None,
                notes=notes or None,
                opdb_id=opdb_id or None,
                image_path=editing.image_path if editing else None,
                rulesheet_url=editing.rulesheet_url if editing else None,
                external_metadata_json=editing.external_metadata_json if editing else None,
            )
            try:
                if editing:
                    update_machine(payload)
                    st.session_state.pop("pinball_edit_machine_id", None)
                    st.success(f"Updated {payload.name}.")
                else:
                    created = create_machine(payload)
                    st.session_state.pinball_machine_id = created.id
                    st.success(f"Added {created.name}.")
                st.session_state.pinball_show_add_form = False
                st.rerun()
            except PinballValidationError as exc:
                st.error(str(exc))

        if editing:
            st.divider()
            force = st.checkbox("Force delete (removes linked maintenance and mods)", key="force_delete_machine")
            if st.button(f"Delete {editing.name}", type="primary"):
                try:
                    delete_machine(editing.id, force=force)
                    st.session_state.pinball_machine_id = None
                    st.session_state.pop("pinball_edit_machine_id", None)
                    st.session_state.pinball_show_add_form = False
                    st.success("Machine deleted.")
                    st.rerun()
                except PinballDeleteError as exc:
                    st.error(str(exc))


def _render_maintenance(machine_id: int | None) -> None:
    st.subheader("Repairs & Maintenance")
    if machine_id is None:
        st.info("Add a machine first.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.selectbox("Type filter", ["All", "issue", "scheduled"], key="maint_type_filter")
    with col2:
        status_filter = st.selectbox("Status filter", ["All", *MAINTENANCE_STATUSES], key="maint_status_filter")
    with col3:
        st.caption("Log issues and scheduled maintenance for the selected machine.")

    entries = list_maintenance(
        machine_id=machine_id,
        entry_type=None if type_filter == "All" else type_filter,
        status=None if status_filter == "All" else status_filter,
    )

    if not entries:
        st.info("No maintenance entries yet.")
    for entry in entries:
        with st.expander(f"[{entry.entry_type}] {entry.title} — {entry.status}", expanded=False):
            st.write(entry.description or "No description.")
            st.caption(
                f"Priority: {entry.priority}"
                + (f" | Due: {entry.due_date}" if entry.due_date else "")
                + (f" | Completed: {entry.completed_at}" if entry.completed_at else "")
            )
            if entry.notes:
                st.markdown(f"**Notes:** {entry.notes}")
            if entry.status != "done" and st.button("Mark done", key=f"done_maint_{entry.id}"):
                complete_maintenance(entry.id)
                st.rerun()

    with st.form("maintenance_form"):
        st.markdown("### Add Entry")
        entry_type = st.selectbox("Type", ["issue", "scheduled"])
        title = st.text_input("Title *")
        description = st.text_area("Description")
        priority = st.selectbox("Priority", PRIORITIES, index=1)
        status = st.selectbox("Status", MAINTENANCE_STATUSES)
        due_date = st.text_input("Due date (YYYY-MM-DD)", value="")
        notes = st.text_area("Notes")
        if st.form_submit_button("Add Entry"):
            try:
                create_maintenance(
                    MaintenanceEntry(
                        machine_id=machine_id,
                        entry_type=entry_type,
                        title=title,
                        description=description or None,
                        priority=priority,
                        status=status,
                        due_date=due_date or None,
                        notes=notes or None,
                    )
                )
                st.success("Maintenance entry added.")
                st.rerun()
            except PinballValidationError as exc:
                st.error(str(exc))


def _render_mods(machine_id: int | None) -> None:
    st.subheader("Mods")
    if machine_id is None:
        st.info("Add a machine first.")
        return

    status_filter = st.selectbox("Status filter", ["All", *MOD_STATUSES], key="mod_status_filter")
    mods = list_mods(
        machine_id=machine_id,
        status=None if status_filter == "All" else status_filter,
    )

    if not mods:
        st.info("No mods logged yet.")
    for mod in mods:
        with st.expander(f"{mod.name} — {mod.status}", expanded=False):
            st.write(mod.description or "No description.")
            st.caption(
                f"Priority: {mod.priority}"
                + (f" | Est. cost: ${mod.estimated_cost:.2f}" if mod.estimated_cost is not None else "")
            )
            if mod.parts:
                st.markdown(f"**Parts:** {mod.parts}")
            if mod.install_notes:
                st.markdown(f"**Install notes:** {mod.install_notes}")
            if mod.before_after_notes:
                st.markdown(f"**Before/after:** {mod.before_after_notes}")
            if mod.status != "done" and st.button("Mark done", key=f"done_mod_{mod.id}"):
                complete_mod(mod.id)
                st.rerun()

    with st.form("mod_form"):
        st.markdown("### Add Mod")
        name = st.text_input("Name *")
        description = st.text_area("Description")
        priority = st.selectbox("Priority", PRIORITIES, index=1, key="mod_priority")
        status = st.selectbox("Status", MOD_STATUSES, key="mod_status")
        estimated_cost = st.number_input("Estimated cost", min_value=0.0, step=1.0, format="%.2f")
        parts = st.text_area("Parts")
        install_notes = st.text_area("Install notes")
        before_after_notes = st.text_area("Before/after notes")
        if st.form_submit_button("Add Mod"):
            try:
                create_mod(
                    Mod(
                        machine_id=machine_id,
                        name=name,
                        description=description or None,
                        priority=priority,
                        status=status,
                        estimated_cost=estimated_cost if estimated_cost > 0 else None,
                        parts=parts or None,
                        install_notes=install_notes or None,
                        before_after_notes=before_after_notes or None,
                    )
                )
                st.success("Mod added.")
                st.rerun()
            except PinballValidationError as exc:
                st.error(str(exc))


def _render_skills() -> None:
    st.subheader("Skills")
    all_skills = list_skills()
    all_tags = sorted({tag for skill in all_skills for tag in skill.tags})
    tag_options = ["All", *all_tags, *TAG_SUGGESTIONS]
    unique_tags = []
    for tag in tag_options:
        if tag not in unique_tags:
            unique_tags.append(tag)

    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("Status filter", ["All", "want_to_learn", "learned"], key="skill_status_filter")
    with col2:
        tag_filter = st.selectbox("Tag filter", unique_tags, key="skill_tag_filter")

    skills = list_skills(
        status=None if status_filter == "All" else status_filter,
        tag=None if tag_filter == "All" else tag_filter,
    )

    if not skills:
        st.info("Add your first skill below.")
    for skill in skills:
        tags = ", ".join(skill.tags) if skill.tags else "—"
        with st.expander(f"{skill.name} — {skill.status}", expanded=False):
            st.write(skill.description or "No description.")
            st.caption(f"Tags: {tags}")
            if skill.notes:
                st.markdown(f"**Notes:** {skill.notes}")
            if skill.status != "learned" and st.button("Mark learned", key=f"learned_skill_{skill.id}"):
                mark_skill_learned(skill.id)
                st.rerun()

    with st.form("skill_form"):
        st.markdown("### Add Skill")
        name = st.text_input("Name *", key="skill_name")
        description = st.text_area("Description", key="skill_description")
        tags = st.text_input("Tags (comma-separated)", value=", ".join(TAG_SUGGESTIONS[:3]))
        notes = st.text_area("Notes", key="skill_notes")
        if st.form_submit_button("Add Skill"):
            try:
                create_skill(
                    Skill(
                        name=name,
                        description=description or None,
                        tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
                        notes=notes or None,
                    )
                )
                st.success("Skill added.")
                st.rerun()
            except PinballValidationError as exc:
                st.error(str(exc))


def render() -> None:
    ensure_db()
    _init_session_state()
    machines = list_machines()
    st.sidebar.markdown("### Pinball Tracker")
    machine_id = _selected_machine_id(machines)

    sub_tabs = st.tabs(["Machines", "Repairs & Maintenance", "Mods", "Skills"])
    with sub_tabs[0]:
        _render_machine_list()
    with sub_tabs[1]:
        _render_maintenance(machine_id)
    with sub_tabs[2]:
        _render_mods(machine_id)
    with sub_tabs[3]:
        _render_skills()
