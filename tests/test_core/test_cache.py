"""Tests for the tool result caching system."""

from __future__ import annotations

import asyncio
import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.core.cache import (
    DEFAULT_TOOL_TTL,
    CacheEntry,
    CacheStats,
    ToolCache,
)


class TestCacheDataclasses:
    """Tests for CacheEntry and CacheStats dataclasses."""

    def test_cache_entry(self) -> None:
        """Test CacheEntry creation and fields."""
        now = time.time()
        entry = CacheEntry(value="test result", expires_at=now + 60, tool_name="read_file", args_hash="abc123")
        assert (entry.value, entry.tool_name, entry.args_hash) == ("test result", "read_file", "abc123")
        assert entry.expires_at > now

    def test_cache_stats(self) -> None:
        """Test CacheStats defaults and incrementing."""
        stats = CacheStats()
        assert (stats.hits, stats.misses, stats.evictions, stats.invalidations) == (0, 0, 0, 0)
        stats.hits, stats.misses, stats.evictions, stats.invalidations = 1, 2, 3, 4
        assert (stats.hits, stats.misses, stats.evictions, stats.invalidations) == (1, 2, 3, 4)


class TestDefaultToolTTL:
    """Tests for DEFAULT_TOOL_TTL constant."""

    @pytest.mark.parametrize(
        "tool_name,min_ttl,max_ttl",
        [
            ("git_status", 1, 10),
            ("git_diff", 1, 10),
            ("grep_search", 20, 60),
            ("find_files", 20, 60),
            ("list_templates", 300, 3600),
        ],
    )
    def test_tool_ttl_ranges(self, tool_name: str, min_ttl: int, max_ttl: int) -> None:
        """Test that tools have expected TTL ranges."""
        assert min_ttl <= DEFAULT_TOOL_TTL[tool_name] <= max_ttl


class TestToolCache:
    """Tests for ToolCache class."""

    @pytest.fixture
    def cache(self) -> ToolCache:
        """Create a ToolCache instance."""
        return ToolCache(max_size=10, default_ttl=60)

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache: ToolCache) -> None:
        """Test basic set and get operations."""
        await cache.set("read_file", {"path": "/test.txt"}, "file content")
        result = await cache.get("read_file", {"path": "/test.txt"})
        assert result == "file content"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache: ToolCache) -> None:
        """Test cache miss returns None."""
        result = await cache.get("read_file", {"path": "/nonexistent.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_different_args(self, cache: ToolCache) -> None:
        """Test that different args produce different cache entries."""
        await cache.set("read_file", {"path": "/a.txt"}, "content a")
        await cache.set("read_file", {"path": "/b.txt"}, "content b")

        result_a = await cache.get("read_file", {"path": "/a.txt"})
        result_b = await cache.get("read_file", {"path": "/b.txt"})

        assert result_a == "content a"
        assert result_b == "content b"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache: ToolCache) -> None:
        """Test that expired entries are not returned."""
        # Set with very short TTL
        await cache.set("read_file", {"path": "/test.txt"}, "content", ttl=0)

        # Small delay to ensure expiration
        await asyncio.sleep(0.01)

        result = await cache.get("read_file", {"path": "/test.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_non_cacheable_tool_not_stored(self, cache: ToolCache) -> None:
        """Test that non-cacheable tools (cacheable=False) are not cached."""
        await cache.set("shell", {"command": "ls"}, "output", cacheable=False)
        result = await cache.get("shell", {"command": "ls"}, cacheable=False)
        assert result is None
        assert cache.size() == 0

    @pytest.mark.asyncio
    async def test_non_cacheable_tool_counts_miss(self, cache: ToolCache) -> None:
        """Test that non-cacheable tools (cacheable=False) count as miss."""
        await cache.get("shell", {"command": "ls"}, cacheable=False)
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache: ToolCache) -> None:
        """Test LRU eviction when cache is full."""
        # Fill cache to max_size (10)
        for i in range(10):
            await cache.set("read_file", {"path": f"/file{i}.txt"}, f"content{i}")

        # Add one more, should evict oldest
        await cache.set("read_file", {"path": "/new.txt"}, "new content")

        # First entry should be evicted
        result = await cache.get("read_file", {"path": "/file0.txt"})
        assert result is None

        # New entry should exist
        result = await cache.get("read_file", {"path": "/new.txt"})
        assert result == "new content"

    @pytest.mark.asyncio
    async def test_lru_order_update(self, cache: ToolCache) -> None:
        """Test that accessing an entry moves it to the end."""
        # Fill cache
        for i in range(10):
            await cache.set("read_file", {"path": f"/file{i}.txt"}, f"content{i}")

        # Access first entry (moves to end)
        await cache.get("read_file", {"path": "/file0.txt"})

        # Add new entry, should evict file1 instead of file0
        await cache.set("read_file", {"path": "/new.txt"}, "new content")

        # file0 should still exist (was accessed)
        result = await cache.get("read_file", {"path": "/file0.txt"})
        assert result == "content0"

        # file1 should be evicted
        result = await cache.get("read_file", {"path": "/file1.txt"})
        assert result is None

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache: ToolCache) -> None:
        """Test statistics tracking."""
        await cache.set("read_file", {"path": "/test.txt"}, "content")

        # Hit
        await cache.get("read_file", {"path": "/test.txt"})
        assert cache.stats.hits == 1

        # Miss
        await cache.get("read_file", {"path": "/other.txt"})
        assert cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, cache: ToolCache) -> None:
        """Test get_stats returns correct dictionary."""
        await cache.set("read_file", {"path": "/test.txt"}, "content")
        await cache.get("read_file", {"path": "/test.txt"})
        await cache.get("read_file", {"path": "/other.txt"})

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert "hit_rate" in stats
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_reset_stats(self, cache: ToolCache) -> None:
        """Test resetting statistics."""
        await cache.set("read_file", {"path": "/test.txt"}, "content")
        await cache.get("read_file", {"path": "/test.txt"})

        cache.reset_stats()

        assert cache.stats.hits == 0
        assert cache.stats.misses == 0

    @pytest.mark.asyncio
    async def test_size(self, cache: ToolCache) -> None:
        """Test size tracking."""
        assert cache.size() == 0

        await cache.set("read_file", {"path": "/a.txt"}, "a")
        assert cache.size() == 1

        await cache.set("read_file", {"path": "/b.txt"}, "b")
        assert cache.size() == 2


class TestToolCacheInvalidation:
    """Tests for cache invalidation methods."""

    @pytest.fixture
    def cache(self) -> ToolCache:
        """Create a ToolCache instance."""
        return ToolCache(max_size=100, default_ttl=60)

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern(self, cache: ToolCache) -> None:
        """Test pattern-based invalidation."""
        await cache.set("read_file", {"path": "/a.txt"}, "a")
        await cache.set("read_file", {"path": "/b.txt"}, "b")
        await cache.set("list_files", {"path": "/"}, "files")

        # Invalidate all read_file entries
        count = await cache.invalidate("read_file:*")
        assert count == 2

        # read_file entries should be gone
        assert await cache.get("read_file", {"path": "/a.txt"}) is None
        assert await cache.get("read_file", {"path": "/b.txt"}) is None

        # list_files should remain
        assert await cache.get("list_files", {"path": "/"}) == "files"

    @pytest.mark.asyncio
    async def test_invalidate_tool(self, cache: ToolCache) -> None:
        """Test invalidating all entries for a tool."""
        await cache.set("grep_search", {"pattern": "foo"}, "result1")
        await cache.set("grep_search", {"pattern": "bar"}, "result2")
        await cache.set("find_files", {"pattern": "*.py"}, "files")

        count = await cache.invalidate_tool("grep_search")
        assert count == 2

        assert await cache.get("grep_search", {"pattern": "foo"}) is None
        assert await cache.get("find_files", {"pattern": "*.py"}) == "files"

    @pytest.mark.asyncio
    async def test_clear(self, cache: ToolCache) -> None:
        """Test clearing all entries."""
        await cache.set("read_file", {"path": "/a.txt"}, "a")
        await cache.set("list_files", {"path": "/"}, "files")

        count = await cache.clear()
        assert count == 2
        assert cache.size() == 0

    @pytest.mark.asyncio
    async def test_invalidation_updates_stats(self, cache: ToolCache) -> None:
        """Test that invalidation updates statistics."""
        await cache.set("read_file", {"path": "/a.txt"}, "a")
        await cache.set("read_file", {"path": "/b.txt"}, "b")

        await cache.invalidate("read_file:*")
        assert cache.stats.invalidations == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache: ToolCache) -> None:
        """Test cleaning up expired entries."""
        # Set entries with different TTLs
        await cache.set("read_file", {"path": "/short.txt"}, "short", ttl=0)
        await cache.set("read_file", {"path": "/long.txt"}, "long", ttl=300)

        await asyncio.sleep(0.01)

        count = await cache.cleanup_expired()
        assert count == 1

        # Expired entry should be gone
        assert await cache.get("read_file", {"path": "/short.txt"}) is None
        # Non-expired should remain
        assert await cache.get("read_file", {"path": "/long.txt"}) == "long"


class TestToolCacheKeyGenerationAndTTL:
    """Tests for cache key generation and TTL handling."""

    @pytest.fixture
    def cache(self) -> ToolCache:
        """Create a ToolCache instance."""
        return ToolCache(default_ttl=60)

    def test_key_generation_deterministic_and_order_independent(self, cache: ToolCache) -> None:
        """Test key generation is deterministic and argument order independent."""
        args1, args2 = {"path": "/test.txt", "encoding": "utf-8"}, {"encoding": "utf-8", "path": "/test.txt"}
        assert cache._generate_key("read_file", args1) == cache._generate_key("read_file", args2)

    def test_key_generation_differs_for_different_inputs(self, cache: ToolCache) -> None:
        """Test different tools/args produce different keys."""
        args = {"path": "/test.txt"}
        assert cache._generate_key("read_file", args) != cache._generate_key("list_files", args)
        assert cache._generate_key("read_file", {"path": "/a.txt"}) != cache._generate_key(
            "read_file", {"path": "/b.txt"}
        )

    def test_ttl_handling(self, cache: ToolCache) -> None:
        """Test TTL uses default for unknown tools, configured for known."""
        assert cache._get_ttl("unknown_tool") == 60
        assert cache._get_ttl("git_status") == DEFAULT_TOOL_TTL["git_status"]


class TestToolCacheConcurrency:
    """Tests for concurrent access."""

    @pytest.fixture
    def cache(self) -> ToolCache:
        """Create a ToolCache instance."""
        return ToolCache(max_size=100, default_ttl=60)

    @pytest.mark.asyncio
    async def test_concurrent_set_operations(self, cache: ToolCache) -> None:
        """Test concurrent set operations are safe."""

        async def set_entry(i: int) -> None:
            await cache.set("read_file", {"path": f"/file{i}.txt"}, f"content{i}")

        # Run concurrent sets
        await asyncio.gather(*[set_entry(i) for i in range(20)])

        # Should have all entries (max_size is 100)
        assert cache.size() == 20

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self, cache: ToolCache) -> None:
        """Test concurrent get operations are safe."""
        await cache.set("read_file", {"path": "/test.txt"}, "content")

        async def get_entry() -> str | None:
            return await cache.get("read_file", {"path": "/test.txt"})

        # Run concurrent gets
        results = await asyncio.gather(*[get_entry() for _ in range(20)])

        # All should return the same result
        assert all(r == "content" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, cache: ToolCache) -> None:
        """Test concurrent mixed operations are safe."""

        async def operation(i: int) -> None:
            if i % 3 == 0:
                await cache.set("read_file", {"path": f"/file{i}.txt"}, f"content{i}")
            elif i % 3 == 1:
                await cache.get("read_file", {"path": f"/file{i - 1}.txt"})
            else:
                await cache.invalidate_tool("read_file")

        # Run concurrent mixed operations
        await asyncio.gather(*[operation(i) for i in range(30)])

        # Should complete without errors (exact state depends on timing)
        assert cache.size() >= 0


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @settings(max_examples=50)
    @given(
        tool_name=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,29}", fullmatch=True),
        path=st.from_regex(r"/[a-zA-Z0-9_/]{1,50}", fullmatch=True),
        content=st.text(min_size=0, max_size=1000),
    )
    @pytest.mark.asyncio
    async def test_set_get_roundtrip(self, tool_name: str, path: str, content: str) -> None:
        """Test that set followed by get returns the same value (cacheable=True)."""
        cache = ToolCache(max_size=100, default_ttl=300)
        args = {"path": path}

        # With cacheable=True, should cache and retrieve
        await cache.set(tool_name, args, content, cacheable=True)
        result = await cache.get(tool_name, args, cacheable=True)

        assert result == content

    @settings(max_examples=50)
    @given(
        args=st.dictionaries(
            keys=st.from_regex(r"[a-z_]{1,10}", fullmatch=True),
            values=st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
            min_size=1,
            max_size=5,
        )
    )
    def test_key_generation_always_deterministic(self, args: dict) -> None:
        """Test key generation is always deterministic."""
        cache = ToolCache()
        key1 = cache._generate_key("test_tool", args)
        key2 = cache._generate_key("test_tool", args)
        assert key1 == key2

    @settings(max_examples=30)
    @given(max_size=st.integers(min_value=1, max_value=20), num_entries=st.integers(min_value=0, max_value=50))
    @pytest.mark.asyncio
    async def test_size_bounded(self, max_size: int, num_entries: int) -> None:
        """Test that cache size never exceeds max_size."""
        cache = ToolCache(max_size=max_size, default_ttl=300)

        for i in range(num_entries):
            await cache.set("read_file", {"path": f"/file{i}.txt"}, f"content{i}")

        assert cache.size() <= max_size

    @settings(max_examples=30)
    @given(ttl=st.integers(min_value=0, max_value=10))
    @pytest.mark.asyncio
    async def test_expiration_respected(self, ttl: int) -> None:
        """Test that TTL is respected."""
        cache = ToolCache(max_size=100, default_ttl=300)

        await cache.set("read_file", {"path": "/test.txt"}, "content", ttl=ttl)

        # If TTL is 0, should expire immediately
        if ttl == 0:
            await asyncio.sleep(0.01)
            result = await cache.get("read_file", {"path": "/test.txt"})
            assert result is None
        else:
            # Should still be valid immediately
            result = await cache.get("read_file", {"path": "/test.txt"})
            assert result == "content"


class TestIntegration:
    """Integration tests for cache in realistic scenarios."""

    @pytest.fixture
    def cache(self) -> ToolCache:
        """Create a ToolCache instance."""
        return ToolCache(max_size=100, default_ttl=60)

    @pytest.mark.asyncio
    async def test_file_read_caching_scenario(self, cache: ToolCache) -> None:
        """Test realistic file read caching scenario."""
        # First read
        result1 = await cache.get("read_file", {"path": "/project/main.py"})
        assert result1 is None  # Cache miss

        # Simulate read
        await cache.set("read_file", {"path": "/project/main.py"}, "def main(): pass")

        # Second read (cache hit)
        result2 = await cache.get("read_file", {"path": "/project/main.py"})
        assert result2 == "def main(): pass"

        # Check stats
        assert cache.stats.misses == 1
        assert cache.stats.hits == 1

    @pytest.mark.asyncio
    async def test_search_caching_scenario(self, cache: ToolCache) -> None:
        """Test realistic search caching scenario."""
        search_args = {"pattern": "def main", "path": "/project"}
        search_result = '[{"file": "main.py", "line": 1}]'

        # First search
        await cache.set("grep_search", search_args, search_result)

        # Same search again (cache hit)
        result = await cache.get("grep_search", search_args)
        assert result == search_result

        # Different search (cache miss)
        result = await cache.get("grep_search", {"pattern": "class", "path": "/project"})
        assert result is None

    @pytest.mark.asyncio
    async def test_git_status_short_ttl(self, cache: ToolCache) -> None:
        """Test that git_status uses short TTL."""
        await cache.set("git_status", {"path": "/project"}, "clean")

        # Immediate get should work
        result = await cache.get("git_status", {"path": "/project"})
        assert result == "clean"

        # TTL should be short
        assert cache._get_ttl("git_status") <= 10

    @pytest.mark.asyncio
    async def test_invalidation_on_file_change(self, cache: ToolCache) -> None:
        """Test cache invalidation when files change."""
        # Cache some file reads
        await cache.set("read_file", {"path": "/a.txt"}, "content a")
        await cache.set("read_file", {"path": "/b.txt"}, "content b")

        # Simulate file edit (should invalidate read cache)
        await cache.invalidate_tool("read_file")

        # Both should be invalidated
        assert await cache.get("read_file", {"path": "/a.txt"}) is None
        assert await cache.get("read_file", {"path": "/b.txt"}) is None

    @pytest.mark.asyncio
    async def test_web_fetch_caching(self, cache: ToolCache) -> None:
        """Test web fetch caching."""
        url_args = {"url": "https://example.com/api"}
        response = '{"status": "ok"}'

        await cache.set("web_fetch", url_args, response)
        result = await cache.get("web_fetch", url_args)
        assert result == response

        # TTL should be reasonable
        assert cache._get_ttl("web_fetch") >= 30
