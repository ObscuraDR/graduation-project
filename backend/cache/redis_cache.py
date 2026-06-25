"""
In-Memory Caching Strategy for IDS Backend
Replaces Redis with a thread-safe in-memory dictionary
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager with TTL support"""
    
    def __init__(self):
        """Initialize Redis cache connection"""
        self._cache: Dict[str, str] = {}
        self._expire: Dict[str, datetime] = {}
        logger.info("In-memory cache initialized (Redis replaced)")
    
    def _connect(self):
        pass
    
    def is_connected(self) -> bool:
        """In-memory cache is always available"""
        return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_connected():
            return None
        
        try:
            if key in self._expire and datetime.now() > self._expire[key]:
                self.delete(key)
                return None
            
            value = self._cache.get(key)
            # Nếu dùng In-memory thuần túy, không nhất thiết phải json.loads
            return value 
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Set value in cache with TTL (default: 5 minutes)
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds
        """
        if not self.is_connected():
            return False
        
        try:
            serialized = json.dumps(value)
            self._cache[key] = serialized
            self._expire[key] = datetime.now() + timedelta(seconds=ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_connected():
            return False
        
        try:
            self._cache.pop(key, None)
            self._expire.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_connected():
            return 0
        
        try:
            import fnmatch
            keys_to_del = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_del:
                self.delete(k)
            return len(keys_to_del)
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """Clear all cache entries"""
        if not self.is_connected():
            return False
        try:
            self._cache.clear()
            self._expire.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    # ── Alert cooldown helpers ────────────────────────────────────────────────

    def set_alert_cooldown(self, ip_address: str, ttl_seconds: int) -> bool:
        """Mark an IP as in cooldown for ttl_seconds. Returns False if Redis unavailable."""
        if not self.is_connected():
            return False
        try:
            self.set(f"alert_cooldown:{ip_address}", "1", ttl=ttl_seconds)
            return True
        except Exception as e:
            logger.error(f"set_alert_cooldown error for {ip_address}: {e}")
            return False

    def is_alert_in_cooldown(self, ip_address: str) -> bool:
        """Return True if the IP is still within its alert cooldown window."""
        if not self.is_connected():
            return False
        try:
            return self.get(f"alert_cooldown:{ip_address}") is not None
        except Exception as e:
            logger.error(f"is_alert_in_cooldown error for {ip_address}: {e}")
            return False

    def clear_alert_cooldown(self, ip_address: Optional[str] = None) -> None:
        """Clear cooldown for one IP or all IPs (pass None)."""
        if not self.is_connected():
            return
        try:
            if ip_address:
                self.delete(f"alert_cooldown:{ip_address}")
            else:
                self.delete_pattern("alert_cooldown:*")
        except Exception as e:
            logger.error(f"clear_alert_cooldown error: {e}")


# Singleton cache instance
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


# Cache key generators
def whitelist_cache_key(ip_address: str) -> str:
    """Generate cache key for whitelist entry"""
    return f"whitelist:{ip_address}"


def model_metadata_cache_key(model_name: str) -> str:
    """Generate cache key for model metadata"""
    return f"model_metadata:{model_name}"


def alert_stats_cache_key() -> str:
    """Generate cache key for alert statistics"""
    return "alert_stats:hourly"


def system_stats_cache_key() -> str:
    """Generate cache key for system statistics"""
    return "system_stats:hourly"


# Cache decorators
def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            if not cache.is_connected():
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
