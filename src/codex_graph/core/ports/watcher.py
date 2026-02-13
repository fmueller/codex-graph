from typing import Protocol


class FileWatcherPort(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...
