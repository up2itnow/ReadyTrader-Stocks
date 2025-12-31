import pytest
import time
from common.cache import TTLCache

def test_ttl_cache_basics():
    cache = TTLCache(max_items=2)
    cache.set("a", 1, ttl_seconds=10)
    assert cache.get("a") == 1
    
    # Update
    cache.set("a", 2, ttl_seconds=10)
    assert cache.get("a") == 2
    
def test_ttl_expiry():
    cache = TTLCache()
    cache.set("b", 1, ttl_seconds=0.1)
    time.sleep(0.2)
    assert cache.get("b") is None

def test_eviction():
    cache = TTLCache(max_items=2)
    cache.set("k1", 1, ttl_seconds=60)
    time.sleep(0.01) # ensure ts differs
    cache.set("k2", 2, ttl_seconds=60)
    time.sleep(0.01)
    cache.set("k3", 3, ttl_seconds=60)
    
    # k1 should be evicted (oldest)
    assert cache.get("k1") is None
    assert cache.get("k2") == 2
    assert cache.get("k3") == 3

def test_clear_delete():
    cache = TTLCache()
    cache.set("a", 1, 60)
    cache.delete("a")
    assert cache.get("a") is None
    
    cache.set("b", 1, 60)
    cache.clear()
    assert cache.get("b") is None
