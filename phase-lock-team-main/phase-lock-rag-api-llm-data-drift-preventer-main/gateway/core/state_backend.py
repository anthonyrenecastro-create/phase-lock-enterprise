from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable
from urllib.parse import urlparse

from gateway.core.config import GatewaySettings

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


class StateBackend:
    def get_int(self, key: str, default: int = 0) -> int:
        raise NotImplementedError

    def set_int(self, key: str, value: int, ttl_seconds: int | None = None) -> None:
        raise NotImplementedError

    def incr_int(self, key: str, delta: int = 1, ttl_seconds: int | None = None) -> int:
        raise NotImplementedError

    def consume_once(self, key: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    def revoke_session(self, jti: str, ttl_seconds: int) -> None:
        raise NotImplementedError

    def is_session_revoked(self, jti: str) -> bool:
        raise NotImplementedError

    def health(self) -> dict[str, object]:
        raise NotImplementedError


class MemoryStateBackend(StateBackend):
    def __init__(self) -> None:
        self._lock = Lock()
        self._ints: dict[str, tuple[int, float | None]] = {}
        self._revoked: dict[str, float] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_ints = [k for k, (_, exp) in self._ints.items() if exp is not None and exp <= now]
        for key in expired_ints:
            self._ints.pop(key, None)

        expired_revoked = [k for k, exp in self._revoked.items() if exp <= now]
        for key in expired_revoked:
            self._revoked.pop(key, None)

    def get_int(self, key: str, default: int = 0) -> int:
        with self._lock:
            self._cleanup()
            value = self._ints.get(key)
            if value is None:
                return default
            return int(value[0])

    def set_int(self, key: str, value: int, ttl_seconds: int | None = None) -> None:
        with self._lock:
            expiry = None if ttl_seconds is None else time.time() + max(1, ttl_seconds)
            self._ints[key] = (int(value), expiry)

    def incr_int(self, key: str, delta: int = 1, ttl_seconds: int | None = None) -> int:
        with self._lock:
            self._cleanup()
            current = self._ints.get(key)
            current_value = int(current[0]) if current is not None else 0
            updated = current_value + int(delta)
            expiry = None if ttl_seconds is None else time.time() + max(1, ttl_seconds)
            self._ints[key] = (updated, expiry)
            return updated

    def consume_once(self, key: str, ttl_seconds: int) -> bool:
        with self._lock:
            self._cleanup()
            if key in self._ints:
                return False
            self._ints[key] = (1, time.time() + max(1, ttl_seconds))
            return True

    def revoke_session(self, jti: str, ttl_seconds: int) -> None:
        with self._lock:
            self._revoked[jti] = time.time() + max(1, ttl_seconds)

    def is_session_revoked(self, jti: str) -> bool:
        with self._lock:
            self._cleanup()
            return jti in self._revoked

    def health(self) -> dict[str, object]:
        return {
            "backend": "memory",
            "status": "ok",
        }


class RedisStateBackend(StateBackend):
    def __init__(self, urls: tuple[str, ...]) -> None:
        if redis is None:
            raise RuntimeError("redis package is required for STATE_BACKEND=redis")
        if not urls:
            raise RuntimeError("STATE_REDIS_URLS must be configured for STATE_BACKEND=redis")

        self._urls = urls
        self._clients: list[redis.Redis] = [redis.Redis.from_url(url, decode_responses=True) for url in urls]
        self._fallback = MemoryStateBackend()
        self._last_error: str | None = None
        self._last_active_url: str | None = None

    def _with_client(self) -> tuple[redis.Redis, str]:
        last_error: Exception | None = None
        for idx, client in enumerate(self._clients):
            try:
                client.ping()
                self._last_active_url = self._urls[idx]
                self._last_error = None
                return client, self._urls[idx]
            except Exception as exc:  # pragma: no cover
                last_error = exc
                continue
        if last_error is not None:
            self._last_error = str(last_error)
            raise RuntimeError(f"all redis backends unavailable: {last_error}")
        self._last_error = "no redis clients configured"
        raise RuntimeError("no redis clients configured")

    def _with_fallback(self, *, fallback: Callable[[], object], op: Callable[[redis.Redis], object]) -> object:
        try:
            client, _ = self._with_client()
            return op(client)
        except Exception:
            # Fail open to in-process state for continuity during dependency outages.
            return fallback()

    def get_int(self, key: str, default: int = 0) -> int:
        def _read(client: redis.Redis) -> int:
            value = client.get(key)
            if value is None:
                return default
            try:
                return int(value)
            except ValueError:
                return default

        return int(self._with_fallback(fallback=lambda: self._fallback.get_int(key, default), op=_read))

    def set_int(self, key: str, value: int, ttl_seconds: int | None = None) -> None:
        def _write(client: redis.Redis) -> None:
            if ttl_seconds is not None:
                client.setex(key, max(1, ttl_seconds), int(value))
            else:
                client.set(key, int(value))

        self._with_fallback(
            fallback=lambda: self._fallback.set_int(key, int(value), ttl_seconds=ttl_seconds),
            op=_write,
        )

    def incr_int(self, key: str, delta: int = 1, ttl_seconds: int | None = None) -> int:
        def _incr(client: redis.Redis) -> int:
            updated = int(client.incrby(key, int(delta)))
            if ttl_seconds is not None:
                client.expire(key, max(1, ttl_seconds))
            return updated

        return int(
            self._with_fallback(
                fallback=lambda: self._fallback.incr_int(key, delta=delta, ttl_seconds=ttl_seconds),
                op=_incr,
            )
        )

    def consume_once(self, key: str, ttl_seconds: int) -> bool:
        def _consume(client: redis.Redis) -> bool:
            created = client.set(key, "1", nx=True, ex=max(1, ttl_seconds))
            return bool(created)

        return bool(
            self._with_fallback(
                fallback=lambda: self._fallback.consume_once(key, ttl_seconds=ttl_seconds),
                op=_consume,
            )
        )

    def revoke_session(self, jti: str, ttl_seconds: int) -> None:
        key = f"oidc:revoked:{jti}"

        self._with_fallback(
            fallback=lambda: self._fallback.revoke_session(jti, ttl_seconds),
            op=lambda client: client.setex(key, max(1, ttl_seconds), "1"),
        )

    def is_session_revoked(self, jti: str) -> bool:
        key = f"oidc:revoked:{jti}"
        return bool(
            self._with_fallback(
                fallback=lambda: self._fallback.is_session_revoked(jti),
                op=lambda client: client.exists(key) == 1,
            )
        )

    def health(self) -> dict[str, object]:
        try:
            _, url = self._with_client()
            host = urlparse(url).hostname or "unknown"
            return {
                "backend": "redis",
                "status": "ok",
                "active_host": host,
            }
        except Exception:
            active_host = None
            if self._last_active_url:
                active_host = urlparse(self._last_active_url).hostname or "unknown"
            return {
                "backend": "redis",
                "status": "degraded",
                "active_host": active_host,
                "fallback": "memory",
                "last_error": self._last_error,
            }


@dataclass
class _BackendCache:
    backend: StateBackend | None = None
    signature: tuple[str, tuple[str, ...]] | None = None


_CACHE = _BackendCache()
_CACHE_LOCK = Lock()


def get_state_backend(settings: GatewaySettings) -> StateBackend:
    signature = (settings.state_backend, settings.state_redis_urls)
    with _CACHE_LOCK:
        if _CACHE.backend is not None and _CACHE.signature == signature:
            return _CACHE.backend

        if settings.state_backend == "redis":
            backend: StateBackend = RedisStateBackend(settings.state_redis_urls)
        else:
            backend = MemoryStateBackend()

        _CACHE.backend = backend
        _CACHE.signature = signature
        return backend
