"""Shared status fetching and optimistic state handling for Panasonic entities.

两个目的：

1. **避免界面回跳**：控制指令下发后，设备是异步生效的，云端短时间内仍会返回旧值；
   我们把刚写入的字段记录下来，在一个"抑制窗口"内以本地写入值为准，等云端真的
   跟上（或窗口超时）再交还给云端数据。
2. **减少重复请求**：一次轮询里每个实体各取一次状态很浪费，这里按设备做短时缓存，
   同批实体共用一次请求，也能少触发几次会话过期。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

# 指令下发后，这段时间内以本地写入值为准（略大于默认轮询间隔）。
OPTIMISTIC_TTL = 45.0
# 同一设备状态的短时缓存时间。
CACHE_TTL = 8.0

_CACHES: dict[str, "StatusCache"] = {}


def _as_int(value: Any) -> int | None:
    """Best-effort int conversion for Panasonic status fields."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_status_cache(entry_id: str) -> "StatusCache":
    """Return the shared per-account-entry status cache."""
    cache = _CACHES.get(entry_id)
    if cache is None:
        cache = StatusCache()
        _CACHES[entry_id] = cache
    return cache


class StatusCache:
    """设备状态短时缓存，避免同一轮轮询里重复请求云端。"""

    def __init__(self, ttl: float = CACHE_TTL) -> None:
        self._ttl = ttl
        self._data: dict[str, tuple[float, dict]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def async_get(self, client, profile, usr_id, device_id, token) -> dict:
        now = time.monotonic()
        cached = self._data.get(device_id)
        if cached and now - cached[0] < self._ttl:
            return cached[1]

        lock = self._locks.get(device_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[device_id] = lock

        async with lock:
            cached = self._data.get(device_id)
            if cached and time.monotonic() - cached[0] < self._ttl:
                return cached[1]
            result = await client.get_device_status(
                profile, usr_id, device_id, token
            )
            self._data[device_id] = (time.monotonic(), result)
            return result

    def invalidate(self, device_id: str) -> None:
        self._data.pop(device_id, None)


class OptimisticState:
    """取状态 + 记录刚下发的写入，在抑制窗口内覆盖云端旧值。"""

    def __init__(
        self,
        client,
        cache: StatusCache | None,
        profile,
        usr_id: str,
        device_id: str,
        token: str,
    ) -> None:
        self._client = client
        self._cache = cache
        self._profile = profile
        self._usr_id = usr_id
        self._device_id = device_id
        self._token = token
        self._pending: dict[str, int] = {}
        self._until = 0.0

    async def async_get(self) -> dict:
        """Fetch the device status and apply any pending optimistic values."""
        if self._cache is not None:
            res = await self._cache.async_get(
                self._client,
                self._profile,
                self._usr_id,
                self._device_id,
                self._token,
            )
        else:
            res = await self._client.get_device_status(
                self._profile, self._usr_id, self._device_id, self._token
            )
        return self.merge(res)

    def mark(self, fields: dict, ttl: float = OPTIMISTIC_TTL) -> None:
        """Remember freshly written field values so polls cannot revert them."""
        now = time.monotonic()
        if now >= self._until:
            self._pending.clear()
        self._pending.update({k: v for k, v in fields.items() if v is not None})
        self._until = now + ttl
        if self._cache is not None:
            # 让后续轮询拿新数据（写入后的旧缓存没有意义）。
            self._cache.invalidate(self._device_id)

    def merge(self, res: dict) -> dict:
        """Overlay pending values on a cloud response."""
        if not self._pending:
            return res
        if time.monotonic() >= self._until:
            self._pending.clear()
            return res

        merged = dict(res)
        for key, value in list(self._pending.items()):
            if _as_int(merged.get(key)) == value:
                # 云端已经跟上，撤销抑制。
                self._pending.pop(key, None)
            else:
                merged[key] = value
        return merged
