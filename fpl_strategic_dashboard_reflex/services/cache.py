"""Thread-safe in-memory TTL cache decorator to replace Streamlit's @st.cache_data."""

import functools
import time
from threading import Lock
from typing import Any, Callable, Dict, Tuple


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Any, Tuple[float, Any]] = {}
        self._lock = Lock()

    def _make_key(self, args: tuple, kwargs: dict) -> tuple:
        clean_args = []
        for a in args:
            if hasattr(a, "cursor") or hasattr(a, "execute"):
                clean_args.append(("__db_conn__", type(a).__name__))
            elif isinstance(a, (list, set)):
                clean_args.append(tuple(a))
            elif isinstance(a, dict):
                clean_args.append(tuple(sorted(a.items())))
            else:
                clean_args.append(a)

        clean_kwargs = []
        for k, v in sorted(kwargs.items()):
            if k.startswith("_"):
                continue
            if hasattr(v, "cursor") or hasattr(v, "execute"):
                clean_kwargs.append((k, ("__db_conn__", type(v).__name__)))
            elif isinstance(v, (list, set)):
                clean_kwargs.append((k, tuple(v)))
            elif isinstance(v, dict):
                clean_kwargs.append((k, tuple(sorted(v.items()))))
            else:
                clean_kwargs.append((k, v))

        return tuple(clean_args), tuple(clean_kwargs)

    def get(self, key: Any) -> Tuple[bool, Any]:
        with self._lock:
            if key in self._cache:
                timestamp, val = self._cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    return True, val
                else:
                    del self._cache[key]
            return False, None

    def set(self, key: Any, value: Any):
        with self._lock:
            self._cache[key] = (time.time(), value)

    def clear(self):
        with self._lock:
            self._cache.clear()


def ttl_cache(ttl_seconds: int = 300, show_spinner: bool = False):
    """Decorator to cache function return values with a TTL expiration."""
    cache = TTLCache(ttl_seconds=ttl_seconds)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = cache._make_key(args, kwargs)
            hit, val = cache.get(key)
            if hit:
                return val
            res = func(*args, **kwargs)
            cache.set(key, res)
            return res

        wrapper.clear_cache = cache.clear
        return wrapper

    return decorator

