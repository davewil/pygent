"""Tool result caching system for reducing redundant operations.

This module provides a caching layer for tool execution results,
supporting LRU eviction, TTL-based expiration, and pattern-based invalidation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

# Tools that should never be cached (have side effects)
NON_CACHEABLE_TOOLS: frozenset[str] = frozenset(
    {
        # Filesystem mutation tools
        "edit_file",
        "create_file",
        "delete_file",
        "move_file",
        "copy_file",
        # Git mutation tools
        "git_add",
        "git_commit",
        "git_push",
        "git_pull",
        "git_checkout",
        # Shell (unknown side effects)
        "shell",
        # Test runner (may have side effects)
        "run_tests",
        # Scaffolding (creates files)
        "create_project",
        "add_component",
    }
)

# Default TTL values per tool (in seconds)
DEFAULT_TOOL_TTL: dict[str, int] = {
    # Short TTL for git status (changes frequently)
    "git_status": 5,
    "git_diff": 5,
    "git_branch": 10,
    # Medium TTL for git log (historical, fairly stable)
    "git_log": 60,
    # Longer TTL for search operations (stable unless files change)
    "grep_search": 30,
    "find_files": 30,
    "find_definition": 30,
    # File operations (stable unless modified)
    "read_file": 30,
    "list_files": 30,
    # Web fetch (network latency is expensive)
    "web_fetch": 60,
    # Template listing (static)
    "list_templates": 300,
    "list_components": 300,
}


@dataclass
class CacheEntry:
    """A single cached tool result.

    Attributes:
        value: The cached result string.
        expires_at: Unix timestamp when entry expires.
        tool_name: Name of the tool that produced this result.
        args_hash: Hash of the arguments used.
    """

    value: str
    expires_at: float
    tool_name: str
    args_hash: str


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of LRU evictions.
        invalidations: Number of manual invalidations.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0


@dataclass
class ToolCache:
    """LRU cache for tool execution results with TTL support.

    Provides caching for expensive tool operations to reduce redundant
    calls. Supports:
    - LRU eviction when max_size is exceeded
    - TTL-based expiration per entry
    - Pattern-based invalidation
    - Statistics tracking

    Attributes:
        max_size: Maximum number of entries in the cache.
        default_ttl: Default TTL in seconds for entries without tool-specific TTL.
        stats: Cache performance statistics.
    """

    max_size: int = 100
    default_ttl: int = 60
    _cache: OrderedDict[str, CacheEntry] = field(default_factory=OrderedDict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stats: CacheStats = field(default_factory=CacheStats)

    def _generate_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """Generate a cache key from tool name and arguments.

        Args:
            tool_name: Name of the tool.
            args: Dictionary of tool arguments.

        Returns:
            A unique string key for the tool+args combination.
        """
        # Sort args for deterministic key generation
        args_json = json.dumps(args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()[:16]
        return f"{tool_name}:{args_hash}"

    def _is_cacheable(self, tool_name: str) -> bool:
        """Check if a tool's results can be cached.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if the tool can be cached, False otherwise.
        """
        return tool_name not in NON_CACHEABLE_TOOLS

    def _get_ttl(self, tool_name: str) -> int:
        """Get the TTL for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            TTL in seconds.
        """
        return DEFAULT_TOOL_TTL.get(tool_name, self.default_ttl)

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if a cache entry has expired.

        Args:
            entry: The cache entry to check.

        Returns:
            True if expired, False otherwise.
        """
        return time.time() > entry.expires_at

    async def get(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Get a cached result if available and not expired.

        Args:
            tool_name: Name of the tool.
            args: Dictionary of tool arguments.

        Returns:
            Cached result string, or None if not cached or expired.
        """
        if not self._is_cacheable(tool_name):
            self.stats.misses += 1
            return None

        key = self._generate_key(tool_name, args)

        async with self._lock:
            if key not in self._cache:
                self.stats.misses += 1
                return None

            entry = self._cache[key]

            if self._is_expired(entry):
                del self._cache[key]
                self.stats.misses += 1
                return None

            # Move to end for LRU
            self._cache.move_to_end(key)
            self.stats.hits += 1
            return entry.value

    async def set(
        self,
        tool_name: str,
        args: dict[str, Any],
        value: str,
        ttl: int | None = None,
    ) -> None:
        """Cache a tool result.

        Args:
            tool_name: Name of the tool.
            args: Dictionary of tool arguments.
            value: The result to cache.
            ttl: Optional TTL override in seconds.
        """
        if not self._is_cacheable(tool_name):
            return

        key = self._generate_key(tool_name, args)
        effective_ttl = ttl if ttl is not None else self._get_ttl(tool_name)
        args_json = json.dumps(args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()[:16]

        entry = CacheEntry(
            value=value,
            expires_at=time.time() + effective_ttl,
            tool_name=tool_name,
            args_hash=args_hash,
        )

        async with self._lock:
            # Remove if exists to update
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self.stats.evictions += 1

            self._cache[key] = entry

    async def invalidate(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern.

        Supports glob-style patterns (e.g., "read_file:*", "*:abc*").

        Args:
            pattern: Glob pattern to match against cache keys.

        Returns:
            Number of entries invalidated.
        """
        async with self._lock:
            keys_to_delete = [key for key in self._cache if fnmatch(key, pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            self.stats.invalidations += len(keys_to_delete)
            return len(keys_to_delete)

    async def invalidate_tool(self, tool_name: str) -> int:
        """Invalidate all cache entries for a specific tool.

        Args:
            tool_name: Name of the tool to invalidate.

        Returns:
            Number of entries invalidated.
        """
        return await self.invalidate(f"{tool_name}:*")

    async def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self.stats.invalidations += count
            return count

    async def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            Number of entries removed.
        """
        async with self._lock:
            now = time.time()
            keys_to_delete = [key for key, entry in self._cache.items() if now > entry.expires_at]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def size(self) -> int:
        """Get the current number of entries in the cache.

        Returns:
            Number of cached entries.
        """
        return len(self._cache)

    def get_stats(self) -> dict[str, int | float]:
        """Get cache statistics as a dictionary.

        Returns:
            Dictionary with hits, misses, evictions, invalidations, size, and hit_rate.
        """
        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "evictions": self.stats.evictions,
            "invalidations": self.stats.invalidations,
            "size": self.size(),
            "hit_rate": round(self.stats.hits / max(1, self.stats.hits + self.stats.misses), 3),
        }

    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        self.stats = CacheStats()
