from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agent_hub.core.paths import PROJECT_ROOT


def main() -> None:
    app_path = PROJECT_ROOT / "app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    raise SystemExit(subprocess.run(command, cwd=PROJECT_ROOT).returncode)


if __name__ == "__main__":
    main()
