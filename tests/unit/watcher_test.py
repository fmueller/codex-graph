"""Tests for the watchfiles watcher adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from codex_graph.watcher.watchfiles_adapter import (
    WatchfilesWatcher,
    _is_supported_file,
)


class TestIsSupportedFile:
    def test_python_file(self) -> None:
        assert _is_supported_file(Path("foo.py")) is True

    def test_javascript_file(self) -> None:
        assert _is_supported_file(Path("bar.js")) is True

    def test_typescript_file(self) -> None:
        assert _is_supported_file(Path("baz.ts")) is True

    def test_go_file(self) -> None:
        assert _is_supported_file(Path("main.go")) is True

    def test_unsupported_txt(self) -> None:
        assert _is_supported_file(Path("readme.txt")) is False

    def test_unsupported_no_extension(self) -> None:
        assert _is_supported_file(Path("Makefile")) is False

    def test_unsupported_image(self) -> None:
        assert _is_supported_file(Path("photo.png")) is False


class TestWatchfilesWatcher:
    def test_implements_protocol(self) -> None:
        from codex_graph.core.ports.watcher import FileWatcherPort

        callback = AsyncMock()
        watcher: FileWatcherPort = WatchfilesWatcher("/tmp", callback)
        assert hasattr(watcher, "start")
        assert hasattr(watcher, "stop")

    @pytest.mark.asyncio
    async def test_start_creates_task(self) -> None:
        callback = AsyncMock()
        watcher = WatchfilesWatcher("/tmp", callback)

        with patch("codex_graph.watcher.watchfiles_adapter.awatch") as mock_awatch:
            # Make awatch return an empty async iterator
            mock_awatch.return_value = _empty_async_iter()
            await watcher.start()
            assert watcher._task is not None
            await watcher.stop()
            assert watcher._task is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self) -> None:
        callback = AsyncMock()
        watcher = WatchfilesWatcher("/tmp", callback)
        await watcher.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self) -> None:
        callback = AsyncMock()
        watcher = WatchfilesWatcher("/tmp", callback)

        with patch("codex_graph.watcher.watchfiles_adapter.awatch") as mock_awatch:
            mock_awatch.return_value = _empty_async_iter()
            await watcher.start()
            task1 = watcher._task
            await watcher.start()
            assert watcher._task is task1  # same task
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_callback_receives_supported_files(self) -> None:
        callback = AsyncMock()
        watcher = WatchfilesWatcher("/tmp", callback)

        changes = {(1, "/tmp/foo.py"), (2, "/tmp/bar.txt"), (1, "/tmp/baz.js")}

        with patch("codex_graph.watcher.watchfiles_adapter.awatch") as mock_awatch:
            mock_awatch.return_value = _single_change_iter(changes)
            await watcher.start()
            # Let the watch loop process the changes
            await asyncio.sleep(0.05)
            await watcher.stop()

        callback.assert_called_once()
        paths = callback.call_args[0][0]
        assert paths == {Path("/tmp/foo.py"), Path("/tmp/baz.js")}

    @pytest.mark.asyncio
    async def test_callback_not_called_for_unsupported_only(self) -> None:
        callback = AsyncMock()
        watcher = WatchfilesWatcher("/tmp", callback)

        changes = {(1, "/tmp/readme.txt"), (2, "/tmp/Makefile")}

        with patch("codex_graph.watcher.watchfiles_adapter.awatch") as mock_awatch:
            mock_awatch.return_value = _single_change_iter(changes)
            await watcher.start()
            await asyncio.sleep(0.05)
            await watcher.stop()

        callback.assert_not_called()


async def _empty_async_iter() -> AsyncIterator[Any]:
    """Async iterator that never yields, just blocks until cancelled."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        return
    yield  # make it an async generator  # pragma: no cover


async def _single_change_iter(changes: set[tuple[int, str]]) -> AsyncIterator[set[tuple[int, str]]]:
    """Async iterator that yields one set of changes then blocks."""
    yield changes
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        return
