from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_PARALLEL_WORKERS = 8


def map_parallel(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int = DEFAULT_PARALLEL_WORKERS,
) -> list[R | None]:
    """Run *fn* over *items* concurrently, preserving order. Failed items become None."""
    if not items:
        return []
    if len(items) == 1:
        try:
            return [fn(items[0])]
        except Exception:
            return [None]

    workers = min(max_workers, len(items))
    results: list[R | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {executor.submit(fn, item): idx for idx, item in enumerate(items)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = None
    return results
