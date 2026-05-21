"""
Redis Caching Strategy for IDS Backend
Implements caching for frequently accessed data
"""

import json
import logging
from typing import Optional, Any
import redis
from backend.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager with TTL support"""
    
    def __init__(self):
        """Initialize Redis cache connection"""
        self.settings = get_settings()
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            if self.settings.redis_url:
                self.redis_client = redis.Redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            else:
                self.redis_client = redis.Redis(
                    host=self.settings.redis_host,
                    port=self.settings.redis_port,
                    db=self.settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
            self.redis_client.ping()
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.warning(f"Redis cache connection failed: {e}. Cache will be disabled.")
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_connected():
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
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
            self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_connected():
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_connected():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """Clear all cache entries"""
        if not self.is_connected():
            return False
        try:
            self.redis_client.flushdb()
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
            key = f"alert_cooldown:{ip_address}"
            self.redis_client.setex(key, ttl_seconds, "1")
            return True
        except Exception as e:
            logger.error(f"set_alert_cooldown error for {ip_address}: {e}")
            return False

    def is_alert_in_cooldown(self, ip_address: str) -> bool:
        """Return True if the IP is still within its alert cooldown window."""
        if not self.is_connected():
            return False
        try:
            return self.redis_client.exists(f"alert_cooldown:{ip_address}") == 1
        except Exception as e:
            logger.error(f"is_alert_in_cooldown error for {ip_address}: {e}")
            return False

    def clear_alert_cooldown(self, ip_address: Optional[str] = None) -> None:
        """Clear cooldown for one IP or all IPs (pass None)."""
        if not self.is_connected():
            return
        try:
            if ip_address:
                self.redis_client.delete(f"alert_cooldown:{ip_address}")
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
