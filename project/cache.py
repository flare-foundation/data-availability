import logging
import time

from django.core.cache import caches
from django.core.cache.backends.base import BaseCache
from redis import exceptions

logger = logging.getLogger(__name__)

# initial cooldown after first failure
MIN_COOLDOWN = 2
# cap so we don't wait forever before retrying
MAX_COOLDOWN = 300


class FallbackCache(BaseCache):
    """redis-first cache that falls back to locmem on redis failure.

    uses exponential backoff: after each consecutive failure the cooldown
    doubles (2s -> 4s -> 8s -> ... -> 300s cap). a successful redis call
    resets the backoff immediately.
    """

    def __init__(self, location, params):
        super().__init__(params)
        self._redis = caches["redis"]
        self._fallback = caches["fallback"]
        self._last_fail_time = 0
        self._cooldown = MIN_COOLDOWN

    @property
    def _redis_available(self):
        return time.monotonic() - self._last_fail_time > self._cooldown

    def _mark_failed(self):
        self._last_fail_time = time.monotonic()
        self._cooldown = min(self._cooldown * 2, MAX_COOLDOWN)
        logger.warning("redis unavailable, next retry in %ds", self._cooldown)

    def _mark_ok(self):
        if self._cooldown != MIN_COOLDOWN:
            self._cooldown = MIN_COOLDOWN
            self._last_fail_time = 0

    def _call(self, method, *args, **kwargs):
        if self._redis_available:
            try:
                result = getattr(self._redis, method)(*args, **kwargs)
                self._mark_ok()
                return result
            except exceptions.RedisError:
                self._mark_failed()
        return getattr(self._fallback, method)(*args, **kwargs)

    def get(self, key, default=None, version=None):
        return self._call("get", key, default=default, version=version)

    def set(self, key, value, timeout=None, version=None, **kwargs):
        return self._call("set", key, value, timeout=timeout, version=version)

    def add(self, key, value, timeout=None, version=None):
        return self._call("add", key, value, timeout=timeout, version=version)

    def delete(self, key, version=None):
        return self._call("delete", key, version=version)

    def has_key(self, key, version=None):
        return self._call("has_key", key, version=version)

    def get_many(self, keys, version=None):
        return self._call("get_many", keys, version=version)

    def set_many(self, mapping, timeout=None, version=None):
        return self._call("set_many", mapping, timeout=timeout, version=version)

    def delete_many(self, keys, version=None):
        return self._call("delete_many", keys, version=version)

    def incr(self, key, delta=1, version=None):
        return self._call("incr", key, delta=delta, version=version)

    def decr(self, key, delta=1, version=None):
        return self._call("decr", key, delta=delta, version=version)

    def touch(self, key, timeout=None, version=None):
        return self._call("touch", key, timeout=timeout, version=version)

    def clear(self):
        return self._call("clear")

    def close(self, **kwargs):
        return self._call("close", **kwargs)
