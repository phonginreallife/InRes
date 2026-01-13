"""
Redis Client for Agent Horizontal Scaling.

Provides Redis-backed state management for:
- Rate limiting (shared across instances)
- Session metadata (for tracking/analytics)
- Distributed locks

Usage:
    from utils.redis_client import get_redis, RateLimiter, SessionStore

    # Rate limiting
    limiter = RateLimiter()
    if await limiter.is_allowed(user_id):
        # Process request
    
    # Session tracking
    sessions = SessionStore()
    await sessions.register(session_id, user_id, metadata)
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[redis.Redis] = None
_redis_lock = asyncio.Lock()


async def get_redis() -> redis.Redis:
    """Get or create Redis connection pool."""
    global _redis_pool
    
    if _redis_pool is None:
        async with _redis_lock:
            if _redis_pool is None:
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                logger.info(f"🔴 Connecting to Redis: {redis_url}")
                _redis_pool = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20
                )
                # Test connection
                try:
                    await _redis_pool.ping()
                    logger.info("✅ Redis connected successfully")
                except Exception as e:
                    logger.error(f"❌ Redis connection failed: {e}")
                    _redis_pool = None
                    raise
    
    return _redis_pool


async def close_redis():
    """Close Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("🔴 Redis connection closed")


class RateLimiter:
    """
    Distributed rate limiter using Redis sliding window.
    
    Uses Redis sorted sets for accurate sliding window rate limiting
    that works across multiple agent instances.
    """
    
    def __init__(
        self,
        requests_per_window: int = None,
        window_seconds: int = 60,
        key_prefix: str = "ratelimit"
    ):
        self.requests_per_window = requests_per_window or int(os.getenv("AI_RATE_LIMIT", "60"))
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
    
    async def is_allowed(self, user_id: str) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Uses sliding window algorithm with Redis sorted sets.
        Returns True if allowed, False if rate limited.
        """
        try:
            r = await get_redis()
            key = f"{self.key_prefix}:{user_id}"
            now = time.time()
            window_start = now - self.window_seconds
            
            # Use pipeline for atomic operations
            pipe = r.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry on key
            pipe.expire(key, self.window_seconds + 1)
            
            results = await pipe.execute()
            current_count = results[1]  # zcard result
            
            if current_count >= self.requests_per_window:
                # Remove the request we just added since it's denied
                await r.zrem(key, str(now))
                logger.warning(f"Rate limit exceeded for user {user_id}: {current_count}/{self.requests_per_window}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis is down
            return True
    
    async def get_remaining(self, user_id: str) -> int:
        """Get remaining requests in current window."""
        try:
            r = await get_redis()
            key = f"{self.key_prefix}:{user_id}"
            now = time.time()
            window_start = now - self.window_seconds
            
            # Count requests in current window
            count = await r.zcount(key, window_start, now)
            return max(0, self.requests_per_window - count)
            
        except Exception as e:
            logger.error(f"Failed to get remaining rate limit: {e}")
            return self.requests_per_window
    
    async def reset(self, user_id: str):
        """Reset rate limit for user (admin function)."""
        try:
            r = await get_redis()
            key = f"{self.key_prefix}:{user_id}"
            await r.delete(key)
            logger.info(f"Rate limit reset for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")


class SessionStore:
    """
    Distributed session metadata store using Redis.
    
    Tracks active sessions across multiple agent instances.
    Note: Actual WebSocket connections remain per-instance,
    this only stores metadata for tracking/analytics.
    """
    
    KEY_PREFIX = "agent:session"
    INSTANCE_KEY = "agent:instances"
    TTL_SECONDS = 3600  # 1 hour default session TTL
    
    def __init__(self):
        self.instance_id = os.getenv("HOSTNAME", f"agent-{os.getpid()}")
    
    async def register(
        self,
        session_id: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new session."""
        try:
            r = await get_redis()
            key = f"{self.KEY_PREFIX}:{session_id}"
            
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "instance_id": self.instance_id,
                "created_at": time.time(),
                "last_activity": time.time(),
                **(metadata or {})
            }
            
            # Store session
            await r.setex(key, self.TTL_SECONDS, json.dumps(session_data))
            
            # Track session in user's session list
            user_sessions_key = f"{self.KEY_PREFIX}:user:{user_id}"
            await r.sadd(user_sessions_key, session_id)
            await r.expire(user_sessions_key, self.TTL_SECONDS)
            
            # Register this instance
            await r.sadd(self.INSTANCE_KEY, self.instance_id)
            await r.expire(self.INSTANCE_KEY, 300)  # 5 min TTL for instance tracking
            
            logger.info(f"Session registered: {session_id} on {self.instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register session: {e}")
            return False
    
    async def update_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp."""
        try:
            r = await get_redis()
            key = f"{self.KEY_PREFIX}:{session_id}"
            
            data = await r.get(key)
            if data:
                session_data = json.loads(data)
                session_data["last_activity"] = time.time()
                await r.setex(key, self.TTL_SECONDS, json.dumps(session_data))
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to update session activity: {e}")
            return False
    
    async def unregister(self, session_id: str) -> bool:
        """Remove a session."""
        try:
            r = await get_redis()
            key = f"{self.KEY_PREFIX}:{session_id}"
            
            # Get session data to find user_id
            data = await r.get(key)
            if data:
                session_data = json.loads(data)
                user_id = session_data.get("user_id")
                
                # Remove from user's session list
                if user_id:
                    user_sessions_key = f"{self.KEY_PREFIX}:user:{user_id}"
                    await r.srem(user_sessions_key, session_id)
            
            # Delete session
            await r.delete(key)
            logger.info(f"Session unregistered: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister session: {e}")
            return False
    
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session metadata."""
        try:
            r = await get_redis()
            key = f"{self.KEY_PREFIX}:{session_id}"
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    async def get_user_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user."""
        try:
            r = await get_redis()
            user_sessions_key = f"{self.KEY_PREFIX}:user:{user_id}"
            session_ids = await r.smembers(user_sessions_key)
            
            sessions = []
            for sid in session_ids:
                session = await self.get(sid)
                if session:
                    sessions.append(session)
            
            return sessions
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get session statistics across all instances."""
        try:
            r = await get_redis()
            
            # Count active sessions
            cursor = 0
            session_count = 0
            while True:
                cursor, keys = await r.scan(cursor, match=f"{self.KEY_PREFIX}:*", count=100)
                # Filter out user session sets
                session_count += len([k for k in keys if ":user:" not in k])
                if cursor == 0:
                    break
            
            # Get active instances
            instances = await r.smembers(self.INSTANCE_KEY)
            
            return {
                "total_sessions": session_count,
                "active_instances": list(instances),
                "instance_count": len(instances),
                "this_instance": self.instance_id
            }
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "error": str(e),
                "this_instance": self.instance_id
            }


# Singleton instances
_rate_limiter: Optional[RateLimiter] = None
_session_store: Optional[SessionStore] = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_session_store() -> SessionStore:
    """Get singleton session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
