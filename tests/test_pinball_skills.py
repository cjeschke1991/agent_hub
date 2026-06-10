from agent_hub.agents.pinball_tracker.logic import (
    Skill,
    create_skill,
    list_skills,
    mark_skill_learned,
)


def test_skill_tags_and_learned(hub_config):
    skill = create_skill(
        Skill(
            name="Coil replacement",
            description="Replace stuck coils",
            tags=["electrical", "mechanical"],
        ),
        hub_config,
    )

    filtered = list_skills(tag="electrical", config=hub_config)
    assert len(filtered) == 1
    assert filtered[0].name == skill.name

    learned = mark_skill_learned(skill.id, hub_config)
    assert learned.status == "learned"
    assert learned.completed_at is not None
