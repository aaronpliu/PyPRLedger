import logging
from typing import Optional, Any, Dict, List
import json
import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from src.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[Redis] = None
_connection_pool: Optional[ConnectionPool] = None


async def init_redis() -> None:
    """Initialize the Redis connection pool and client"""
    global _redis_client, _connection_pool
    
    try:
        logger.info("Initializing Redis connection...")
        
        # Create connection pool
        _connection_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            encoding="utf-8"
        )
        
        # Create Redis client
        _redis_client = Redis(connection_pool=_connection_pool)
        
        # Test the connection
        await _redis_client.ping()
        
        logger.info("Redis connection initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis connection: {str(e)}", exc_info=True)
        raise


async def close_redis() -> None:
    """Close the Redis connection"""
    global _redis_client, _connection_pool
    
    try:
        if _redis_client is None:
            return
            
        logger.info("Closing Redis connection...")
        
        # Close the client and pool
        await _redis_client.close()
        
        if _connection_pool:
            await _connection_pool.disconnect()
        
        # Reset global variables
        _redis_client = None
        _connection_pool = None
        
        logger.info("Redis connection closed successfully")
        
    except Exception as e:
        logger.error(f"Error closing Redis connection: {str(e)}", exc_info=True)
        raise


def get_redis_client() -> Redis:
    """
    Get the Redis client instance
    
    Returns:
        Redis: The Redis client
        
    Raises:
        RuntimeError: If Redis is not initialized
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


class RedisCache:
    """
    Redis cache utility class providing common cache operations
    """
    
    def __init__(self, redis_client: Redis = None):
        """
        Initialize Redis cache utility
        
        Args:
            redis_client: Optional Redis client. If not provided, uses the global client.
        """
        self.client = redis_client or get_redis_client()
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis cache
        
        Args:
            key: The cache key
            
        Returns:
            The cached value, or None if not found
        """
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed for key {key}: {str(e)}")
            return None
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a JSON value from Redis cache
        
        Args:
            key: The cache key
            
        Returns:
            The cached JSON value, or None if not found
        """
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON for key {key}")
        return None
    
    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set a value in Redis cache
        
        Args:
            key: The cache key
            value: The value to cache
            expire: Optional expiration time in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if expire:
                return await self.client.setex(key, expire, value)
            else:
                return await self.client.set(key, value)
        except Exception as e:
            logger.warning(f"Redis SET failed for key {key}: {str(e)}")
            return False
    
    async def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        expire: Optional[int] = None
    ) -> bool:
        """
        Set a JSON value in Redis cache
        
        Args:
            key: The cache key
            value: The JSON value to cache
            expire: Optional expiration time in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            json_value = json.dumps(value)
            return await self.set(key, json_value, expire)
        except Exception as e:
            logger.warning(f"Redis SET JSON failed for key {key}: {str(e)}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """
        Delete keys from Redis cache
        
        Args:
            *keys: The cache keys to delete
            
        Returns:
            int: Number of keys deleted
        """
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE failed for keys {keys}: {str(e)}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis cache
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if the key exists, False otherwise
        """
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis EXISTS failed for key {key}: {str(e)}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set an expiration time on a key
        
        Args:
            key: The cache key
            seconds: Expiration time in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return await self.client.expire(key, seconds)
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed for key {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """
        Get the remaining time to live of a key
        
        Args:
            key: The cache key
            
        Returns:
            int: TTL in seconds, -1 if the key exists but has no expiry,
                 -2 if the key does not exist
        """
        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.warning(f"Redis TTL failed for key {key}: {str(e)}")
            return -2
    
    async def incr(self, key: str) -> int:
        """
        Increment the value of a key by 1
        
        Args:
            key: The cache key
            
        Returns:
            int: The new value
        """
        try:
            return await self.client.incr(key)
        except Exception as e:
            logger.warning(f"Redis INCR failed for key {key}: {str(e)}")
            return 0
    
    async def decr(self, key: str) -> int:
        """
        Decrement the value of a key by 1
        
        Args:
            key: The cache key
            
        Returns:
            int: The new value
        """
        try:
            return await self.client.decr(key)
        except Exception as e:
            logger.warning(f"Redis DECR failed for key {key}: {str(e)}")
            return 0
    
    async def keys(self, pattern: str) -> List[str]:
        """
        Find all keys matching the given pattern
        
        Args:
            pattern: The pattern to match (e.g., "user:*")
            
        Returns:
            List of matching keys
        """
        try:
            return await self.client.keys(pattern)
        except Exception as e:
            logger.warning(f"Redis KEYS failed for pattern {pattern}: {str(e)}")
            return []
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """
        Get the value of a hash field
        
        Args:
            name: The hash name
            key: The field key
            
        Returns:
            The field value, or None if not found
        """
        try:
            return await self.client.hget(name, key)
        except Exception as e:
            logger.warning(f"Redis HGET failed for {name}.{key}: {str(e)}")
            return None
    
    async def hset(self, name: str, key: str, value: str) -> bool:
        """
        Set the value of a hash field
        
        Args:
            name: The hash name
            key: The field key
            value: The field value
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return await self.client.hset(name, key, value) > 0
        except Exception as e:
            logger.warning(f"Redis HSET failed for {name}.{key}: {str(e)}")
            return False
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """
        Get all fields and values in a hash
        
        Args:
            name: The hash name
            
        Returns:
            Dict of field names and values
        """
        try:
            return await self.client.hgetall(name)
        except Exception as e:
            logger.warning(f"Redis HGETALL failed for {name}: {str(e)}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """
        Delete one or more hash fields
        
        Args:
            name: The hash name
            *keys: The field keys to delete
            
        Returns:
            int: Number of fields deleted
        """
        try:
            return await self.client.hdel(name, *keys)
        except Exception as e:
            logger.warning(f"Redis HDEL failed for {name}: {str(e)}")
            return 0
    
    async def lpush(self, name: str, *values: str) -> int:
        """
        Push values onto the left of a list
        
        Args:
            name: The list name
            *values: The values to push
            
        Returns:
            int: The new length of the list
        """
        try:
            return await self.client.lpush(name, *values)
        except Exception as e:
            logger.warning(f"Redis LPUSH failed for {name}: {str(e)}")
            return 0
    
    async def rpush(self, name: str, *values: str) -> int:
        """
        Push values onto the right of a list
        
        Args:
            name: The list name
            *values: The values to push
            
        Returns:
            int: The new length of the list
        """
        try:
            return await self.client.rpush(name, *values)
        except Exception as e:
            logger.warning(f"Redis RPUSH failed for {name}: {str(e)}")
            return 0
    
    async def lpop(self, name: str) -> Optional[str]:
        """
        Pop a value from the left of a list
        
        Args:
            name: The list name
            
        Returns:
            The popped value, or None if the list is empty
        """
        try:
            return await self.client.lpop(name)
        except Exception as e:
            logger.warning(f"Redis LPOP failed for {name}: {str(e)}")
            return None
    
    async def rpop(self, name: str) -> Optional[str]:
        """
        Pop a value from the right of a list
        
        Args:
            name: The list name
            
        Returns:
            The popped value, or None if the list is empty
        """
        try:
            return await self.client.rpop(name)
        except Exception as e:
            logger.warning(f"Redis RPOP failed for {name}: {str(e)}")
            return None
    
    async def llen(self, name: str) -> int:
        """
        Get the length of a list
        
        Args:
            name: The list name
            
        Returns:
            int: The length of the list
        """
        try:
            return await self.client.llen(name)
        except Exception as e:
            logger.warning(f"Redis LLEN failed for {name}: {str(e)}")
            return 0
    
    async def lrange(self, name: str, start: int = 0, end: int = -1) -> List[str]:
        """
        Get a range of elements from a list
        
        Args:
            name: The list name
            start: The start index
            end: The end index (-1 for the last element)
            
        Returns:
            List of list elements
        """
        try:
            return await self.client.lrange(name, start, end)
        except Exception as e:
            logger.warning(f"Redis LRANGE failed for {name}: {str(e)}")
            return []
    
    async def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """
        Add members to a sorted set
        
        Args:
            name: The sorted set name
            mapping: A dict of member names and scores
            
        Returns:
            int: The number of members added
        """
        try:
            return await self.client.zadd(name, mapping)
        except Exception as e:
            logger.warning(f"Redis ZADD failed for {name}: {str(e)}")
            return 0
    
    async def zrem(self, name: str, *values: str) -> int:
        """
        Remove members from a sorted set
        
        Args:
            name: The sorted set name
            *values: The members to remove
            
        Returns:
            int: The number of members removed
        """
        try:
            return await self.client.zrem(name, *values)
        except Exception as e:
            logger.warning(f"Redis ZREM failed for {name}: {str(e)}")
            return 0
    
    async def zrange(
        self,
        name: str,
        start: int = 0,
        end: int = -1,
        desc: bool = False,
        withscores: bool = False
    ) -> List[Any]:
        """
        Get a range of members from a sorted set
        
        Args:
            name: The sorted set name
            start: The start index
            end: The end index (-1 for the last element)
            desc: Sort in descending order
            withscores: Include scores in the result
            
        Returns:
            List of members (and optionally scores)
        """
        try:
            return await self.client.zrange(name, start, end, desc=desc, withscores=withscores)
        except Exception as e:
            logger.warning(f"Redis ZRANGE failed for {name}: {str(e)}")
            return []
    
    async def zrank(self, name: str, value: str) -> Optional[int]:
        """
        Get the rank of a member in a sorted set
        
        Args:
            name: The sorted set name
            value: The member value
            
        Returns:
            int: The rank of the member, or None if not found
        """
        try:
            return await self.client.zrank(name, value)
        except Exception as e:
            logger.warning(f"Redis ZRANK failed for {name}: {str(e)}")
            return None
    
    async def zscore(self, name: str, value: str) -> Optional[float]:
        """
        Get the score of a member in a sorted set
        
        Args:
            name: The sorted set name
            value: The member value
            
        Returns:
            float: The score of the member, or None if not found
        """
        try:
            return await self.client.zscore(name, value)
        except Exception as e:
            logger.warning(f"Redis ZSCORE failed for {name}: {str(e)}")
            return None


# Global cache instance for convenience
cache = RedisCache()