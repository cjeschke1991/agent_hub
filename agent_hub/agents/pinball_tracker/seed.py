from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from agent_hub.agents.pinball_tracker.logic import Machine, create_machine, list_machines, update_machine
from agent_hub.agents.pinball_tracker.seed_catalog import COLLECTION_SEEDS, MachineSeed
from agent_hub.core.config import HubConfig, load_config
from agent_hub.core.pinball_db import images_dir, init_db


@dataclass
class SeedResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    images_downloaded: int = 0


def _download_image(url: str, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/*,*/*;q=0.8",
    }
    if "pinside.com" in url:
        headers["Referer"] = "https://pinside.com/"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    except Exception:
        return False
    if not data:
        return False
    destination.write_bytes(data)
    return True


def _image_extension(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def _machine_key(name: str, edition: str | None, manufacturer: str | None) -> tuple[str, str, str]:
    return (
        name.strip().lower(),
        (edition or "").strip().lower(),
        (manufacturer or "").strip().lower(),
    )


def _find_existing(machines: list[Machine], seed: MachineSeed) -> Machine | None:
    key = _machine_key(seed.name, seed.edition, seed.manufacturer)
    for machine in machines:
        if _machine_key(machine.name, machine.edition, machine.manufacturer) == key:
            return machine
    return None


def _seed_to_machine(seed: MachineSeed, image_path: str | None) -> Machine:
    metadata = {
        "slug": seed.slug,
        "designer": seed.designer,
        "platform": seed.platform,
        "latest_software": seed.latest_software,
        "image_source_url": seed.image_url,
        "rulesheet_source": "tiltforums",
    }
    return Machine(
        name=seed.name,
        manufacturer=seed.manufacturer,
        year=seed.year,
        edition=seed.edition,
        ruleset=seed.ruleset,
        description=seed.description,
        notes=seed.notes,
        opdb_id=seed.opdb_id,
        external_metadata_json=json.dumps(metadata, indent=2),
        image_path=image_path,
        rulesheet_url=seed.rulesheet_url,
    )


def seed_collection(
    config: HubConfig | None = None,
    force_refresh_images: bool = False,
) -> SeedResult:
    config = config or load_config()
    init_db(config)
    result = SeedResult()
    image_root = images_dir(config)
    machines = list_machines(config)

    for seed in COLLECTION_SEEDS:
        ext = _image_extension(seed.image_url)
        image_file = image_root / f"{seed.slug}{ext}"
        relative_image_path = f"pinball/images/{seed.slug}{ext}"

        if force_refresh_images or not image_file.exists():
            if _download_image(seed.image_url, image_file):
                result.images_downloaded += 1

        image_path = relative_image_path if image_file.exists() else None
        existing = _find_existing(machines, seed)
        payload = _seed_to_machine(seed, image_path)

        if existing is None:
            created = create_machine(payload, config)
            machines.append(created)
            result.created += 1
            continue

        if (
            existing.image_path == image_path
            and existing.ruleset == payload.ruleset
            and existing.rulesheet_url == payload.rulesheet_url
        ):
            result.skipped += 1
            continue

        payload.id = existing.id
        payload.location = existing.location
        update_machine(payload, config)
        result.updated += 1

    return result
