from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from watchfiles import awatch

from codex_graph.core.languages import _EXTENSION_LANGUAGE_MAP

logger = logging.getLogger(__name__)

# Extensions we can parse
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSION_LANGUAGE_MAP.keys())


def _is_supported_file(path: Path) -> bool:
    return path.suffix in _SUPPORTED_EXTENSIONS


class WatchfilesWatcher:
    """Watch a directory for source-file changes and trigger a callback.

    Implements the ``FileWatcherPort`` protocol.
    """

    def __init__(
        self,
        directory: str | Path,
        on_change: Callable[[set[Path]], Coroutine[Any, Any, None]],
    ) -> None:
        self._directory = Path(directory)
        self._on_change = on_change
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._watch())
        logger.info("Watcher started for %s", self._directory)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("Watcher stopped for %s", self._directory)

    async def _watch(self) -> None:
        async for changes in awatch(self._directory):
            paths = {Path(p) for _, p in changes if _is_supported_file(Path(p))}
            if paths:
                logger.info("Detected changes in %d file(s)", len(paths))
                try:
                    await self._on_change(paths)
                except Exception:
                    logger.exception("Error in watcher callback")
