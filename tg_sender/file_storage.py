import pickle
from pathlib import Path
from typing import Any

import aiofiles
from aiogram.fsm.storage.base import StateType, StorageKey
from aiogram.fsm.storage.memory import MemoryStorage


class LocalFileStorage(MemoryStorage):
    """Same as MemoryStorage, but dumps to file on every change."""

    def __init__(self, path: Path):
        super().__init__()
        self._path = path
        if path.exists():
            with open(path, "rb") as f:
                self.storage = pickle.load(f)

    async def _dump_file(self):
        async with aiofiles.open(self._path, "wb") as f:
            await f.write(pickle.dumps(self.storage))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await super().set_state(key, state)
        await self._dump_file()

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        await super().set_data(key, data)
        await self._dump_file()
