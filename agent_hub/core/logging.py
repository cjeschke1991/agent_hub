import logging
from pathlib import Path

from agent_hub.core.paths import logs_dir


def get_logger(agent_id: str, data_dir: Path) -> logging.Logger:
    log_root = logs_dir(data_dir)
    log_root.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"agent_hub.{agent_id}")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_root / f"{agent_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
