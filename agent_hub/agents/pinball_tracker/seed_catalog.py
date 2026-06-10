from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineSeed:
    slug: str
    name: str
    manufacturer: str
    year: int
    edition: str
    ruleset: str
    description: str
    designer: str
    platform: str
    latest_software: str
    opdb_id: str | None
    image_url: str
    rulesheet_url: str
    notes: str | None = None


COLLECTION_SEEDS: list[MachineSeed] = [
    MachineSeed(
        slug="godzilla-premium",
        name="Godzilla",
        manufacturer="Stern Pinball",
        year=2021,
        edition="Premium",
        ruleset="v2.3+ (Keith Elwin)",
        description=(
            "Destroy cities, battle Kaiju, and conquer Mechagodzilla to become King of the Monsters. "
            "Premium adds a motorized collapsing skyscraper, animated bridge ramp, motorized Mechagodzilla "
            "target bank, magnetic ball catch, and Magna Grab newton ball."
        ),
        designer="Keith Elwin",
        platform="SPIKE 2",
        latest_software="v2.3+",
        opdb_id="IPDB-2986",
        image_url=(
            "https://images.pinside.com/7/56/7569c14eb90ce31497b70dd5917d5bb30246a5ef/polaroid/"
            "476f647a696c6c6120285072656d69756d2920283230323129/"
            "270a7368b958337c8d37583d038af01d/1024/7569c14eb90ce31497b70dd5917d5bb30246a5ef.png"
        ),
        rulesheet_url="https://tiltforums.com/t/stern-godzilla-rulesheet/7210",
        notes="Art by Zombie Yeti. Features Blue Öyster Cult title track and Toho film clips.",
    ),
    MachineSeed(
        slug="foo-fighters-pro",
        name="Foo Fighters",
        manufacturer="Stern Pinball",
        year=2023,
        edition="Pro",
        ruleset="v1.03.0 (Jack Danger)",
        description=(
            "Join the Foo Fighters in their tour van to save rock and roll from the alien Overlord. "
            "Features 15 licensed Foo Fighters songs and the fictional 'Saturday Morning Action Time' show. "
            "Pro model is a fast flow layout without the Premium upper playfield and Expression Lighting."
        ),
        designer="Jack Danger",
        platform="SPIKE 2",
        latest_software="v1.03.0",
        opdb_id="IPDB-3099",
        image_url=(
            "https://images.pinside.com/a/9b/a9b79adff95c08a745877f10c94785ecfc65bcd9/polaroid/"
            "466f6f204669676874657273202850726f2920283230323329/"
            "9aa36455e9038a6af5df9b16e2923000/1024/a9b79adff95c08a745877f10c94785ecfc65bcd9.jpg.png"
        ),
        rulesheet_url="https://tiltforums.com/t/foo-fighters-rulesheet/8162",
        notes="Band collaboration includes Dave Grohl and the full Foo Fighters lineup.",
    ),
    MachineSeed(
        slug="jaws-premium",
        name="Jaws",
        manufacturer="Stern Pinball",
        year=2024,
        edition="Premium",
        ruleset="v1.x (George Gomez team)",
        description=(
            "Relive all four Jaws films with shark encounters, bounty hunts, beach rescues, and Jaws multiball. "
            "Premium features a motorized shark bash toy on Quint's boat, brass powder-coated wireforms, "
            "and a 'Lookout Tower' upper playfield area."
        ),
        designer="George Gomez",
        platform="SPIKE 2",
        latest_software="v1.x",
        opdb_id="IPDB-3193",
        image_url=(
            "https://images.pinside.com/9/8a/98afb6602558e3cec7a9c2f6b1b4bc343c85f9ad/polaroid/"
            "4a61777320285072656d69756d2920283230323429/"
            "d07d01ac46e7b3bc620c5bba6eab1262/1024/98afb6602558e3cec7a9c2f6b1b4bc343c85f9ad.jpg.png"
        ),
        rulesheet_url="https://tiltforums.com/t/jaws-rulesheet/8781",
        notes="50th Anniversary Premium Edition variant available with glitter playfield art.",
    ),
    MachineSeed(
        slug="jurassic-park-pro",
        name="Jurassic Park",
        manufacturer="Stern Pinball",
        year=2019,
        edition="Pro",
        ruleset="v1.15.0 (Keith Elwin)",
        description=(
            "Rescue park staff and recapture escaped dinosaurs on Isla Nublar. "
            "Pro uses static T. rex and raptor pen sculptures (no animatronic T. rex or motorized raptor gate). "
            "Features spinning Jungle Explorer newton ball, four ramps, and paddock progression."
        ),
        designer="Keith Elwin",
        platform="SPIKE 2",
        latest_software="v1.15.0",
        opdb_id="IPDB-6573",
        image_url=(
            "https://images.pinside.com/4/84/48466f0ed54576698f5e34c5a34e400f6d15c62b/polaroid/"
            "4a75726173736963205061726b202850726f2920283230313929/"
            "a09fb3583134ef03658398a267e56327/1024/48466f0ed54576698f5e34c5a34e400f6d15c62b.jpg.png"
        ),
        rulesheet_url="https://tiltforums.com/t/stern-jurassic-park-rulesheet/5644",
        notes="Licensed from Universal Pictures and Amblin Entertainment.",
    ),
    MachineSeed(
        slug="pokemon-premium",
        name="Pokémon",
        manufacturer="Stern Pinball",
        year=2026,
        edition="Premium",
        ruleset="v0.82.0 (George Gomez / Jack Danger)",
        description=(
            "Catch Pokémon across four habitats, build your team, battle rivals, and face Team Rocket. "
            "Premium adds an interactive battle arena electromagnet, animatronic Pikachu, animated Poké Ball, "
            "and Meowth balloon toy."
        ),
        designer="George Gomez & Jack Danger",
        platform="SPIKE 3",
        latest_software="v0.82.0",
        opdb_id="IPDB-3369",
        image_url=(
            "https://images.pinside.com/8/d6/8d6713c9b501e0aa908990e9ab80fcfb1cde304f/polaroid/"
            "506f6bc3a96d6f6e20285072656d69756d2920283230323629/"
            "80319a2b0ce10c7e9b6c3c51029108a4/1024/8d6713c9b501e0aa908990e9ab80fcfb1cde304f.jpeg.png"
        ),
        rulesheet_url="https://tiltforums.com/t/pokemon-rulesheet/10092",
        notes="Collaboration with The Pokémon Company International. Includes Pokémon Theme song.",
    ),
    MachineSeed(
        slug="elton-john-platinum",
        name="Elton John",
        manufacturer="Jersey Jack Pinball",
        year=2023,
        edition="Platinum Edition",
        ruleset="v1.x (Bill Grupp)",
        description=(
            "Tribute to Elton John's legendary career with Rocket Man, Tiny Dancer, Bennie and the Jets, and more. "
            "Features a piano-playing Elton sculpture, motorized Tiny Dancer, and Crocodile Rock physical ball lock. "
            "Platinum Edition is JJP's standard collector tier (user-listed as Premium Edition)."
        ),
        designer="Steve Ritchie",
        platform="JJP Platform",
        latest_software="v1.x",
        opdb_id="IPDB-3208",
        image_url=(
            "https://jerseyjackpinball.com/cdn/shop/articles/"
            "Elton_John_Pinball_0344565e-9030-4adb-9ae0-ca3f6ac44012.jpg?width=1200"
        ),
        rulesheet_url="https://tiltforums.com/t/elton-john-rulesheet/8664",
        notes="Rules/software by Bill Grupp. Also available as Collector's Edition (1,000 units).",
    ),
    MachineSeed(
        slug="pulp-fiction-se",
        name="Pulp Fiction",
        manufacturer="Chicago Gaming Company",
        year=2023,
        edition="Special Edition",
        ruleset="v1.02 (Josh Sharpe)",
        description=(
            "Retro-inspired tribute to Quentin Tarantino's cult classic with 250+ dialogue lines, "
            "five licensed soundtrack songs, and classic pinball flow. "
            "Special Edition is CGC's standard home model (user-listed as Standard Edition)."
        ),
        designer="Mark Ritchie",
        platform="CGC / Williams-style",
        latest_software="v1.02",
        opdb_id="IPDB-3111",
        image_url=(
            "https://images.pinside.com/7/95/795ff067b71bc7b8cde9e2882001383f7e69bc29/polaroid/"
            "50756c702046696374696f6e202853452920283230323329/"
            "609c4f84978f58d566daa9ff0d2a750e/1024/795ff067b71bc7b8cde9e2882001383f7e69bc29.png"
        ),
        rulesheet_url="https://tiltforums.com/t/pulp-fiction-rulesheet/8471",
        notes="Developed with Play Mechanix. Audio by David Thiel. Mirrored backglass on all models.",
    ),
]
