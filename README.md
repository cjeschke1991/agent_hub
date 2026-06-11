# AI Agent Hub

Local-first Streamlit shell for dashboards and agent control. v1 ships the **Daily Briefing** tab using an aggregator pattern: producer agents write JSON slices, and the briefing agent merges them into markdown.

## Quick start

Requires **Python 3.11+**. If system `python3` is older, point venv at a newer interpreter:

```bash
cd /Users/clayjeschke/cursor_projects/agent_hub
/Users/clayjeschke/anaconda3/envs/py314/bin/python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run the morning pipeline manually

```bash
./scripts/morning.sh
cat data/briefings/latest.md
```

### Start Streamlit

From any directory:

```bash
agent_hub
```

The `agent_hub` alias is defined in `~/.zshrc` and launches the dashboard via the project venv. You can also run:

```bash
streamlit run app.py
```

### CLI commands

```bash
priorities write-slice
gmail-stub write-slice
briefing assemble
briefing status
briefing open
pinball init-db
pinball export-status
movie init-db
movie status
movie recommend --year-min 1980 --year-max 1990 --count 5
```

## Movie Recommender

The **Movie Recommender** tab builds a taste profile from movies you like and dislike, then returns ranked TMDB recommendations filtered by year range and genres.

**TMDB API key (required for search/recommendations):**

1. Create a free account at [themoviedb.org](https://www.themoviedb.org/signup)
2. Request an API key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
3. Set it in your shell (recommended):

```bash
export TMDB_API_KEY="your-key-here"
```

Or add to `config.yaml` under `tmdb.api_key` (do not commit real keys).

Data is stored in `data/movies/movies.db`.

## Pinball Tracker

The **Pinball Tracker** tab includes four sub-tabs:

- **Machines** — profiles with ruleset, description, OPDB-ready fields
- **Repairs & Maintenance** — issue and scheduled logbook per machine
- **Mods** — project-style mod tracking (cost, parts, install notes)
- **Skills** — global pinball skills with tags

Data is stored in `data/pinball/pinball.db`. Seed your collection:

```bash
pinball seed-collection
```

## Architecture

- `agent_hub/core/` — config, SQLite, slice I/O, markdown rendering, locks
- `agent_hub/agents/` — producer and assembler agents (`logic.py` + `cli.py`)
- `agent_hub/dashboards/` — Streamlit tab UIs
- `app.py` — tab router (other tabs are placeholders)

Producer slices live at `data/slices/<agent_id>/latest.json`. Briefings are written to `data/briefings/`.

## Automation

### launchd

Update paths in `launchd/*.plist` if your project or venv location differs, then:

```bash
plutil -lint launchd/com.agenthub.producers.plist
plutil -lint launchd/com.agenthub.briefing.plist

cp launchd/com.agenthub.producers.plist ~/Library/LaunchAgents/
cp launchd/com.agenthub.briefing.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.agenthub.producers.plist
launchctl load ~/Library/LaunchAgents/com.agenthub.briefing.plist
```

- **6:25** — `producers.sh` writes priority and gmail stub slices
- **6:30** — `briefing assemble`

### Raycast

Add script commands pointing at:

- `raycast/morning-briefing.sh`
- `raycast/briefing-status.sh`

## Tests

```bash
pytest
```

## Next tabs

Each future tab adds an agent under `agent_hub/agents/<name>/` with `write-slice` (if it feeds the briefing) plus a Streamlit dashboard module.
