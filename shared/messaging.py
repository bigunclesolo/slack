"""
Message queue implementation for inter-service communication
Uses Redis for message queuing and pub/sub
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import Redis

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MessageQueue:
    """Async message queue using Redis"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis_client: Optional[Redis] = None
        
    async def connect(self):
        """Initialize Redis connection"""
        if self.redis_client is None:
            self.redis_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True
            )
            self.redis_client = Redis(connection_pool=self.redis_pool)
            
            # Test connection
            try:
                await self.redis_client.ping()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        if self.redis_pool:
            await self.redis_pool.disconnect()
            self.redis_pool = None
    
    async def publish(self, channel: str, message: Dict[str, Any], priority: int = 0):
        """Publish a message to a channel"""
        if not self.redis_client:
            await self.connect()
        
        try:
            message_data = {
                "data": message,
                "priority": priority,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            serialized_message = json.dumps(message_data)
            await self.redis_client.lpush(channel, serialized_message)
            
            logger.debug(f"Published message to {channel}: {len(serialized_message)} bytes")
            
        except Exception as e:
            logger.error(f"Error publishing message to {channel}: {e}")
            raise
    
    async def consume(self, channel: str, timeout: int = 0) -> AsyncGenerator[Dict[str, Any], None]:
        """Consume messages from a channel"""
        if not self.redis_client:
            await self.connect()
        
        while True:
            try:
                # Use BRPOP for blocking right pop with timeout
                result = await self.redis_client.brpop(channel, timeout=timeout or 0)
                
                if result is None:
                    if timeout > 0:
                        break  # Timeout reached
                    continue
                
                _, message_str = result
                message_data = json.loads(message_str)
                
                yield message_data["data"]
                
            except asyncio.CancelledError:
                logger.info(f"Consumer for {channel} cancelled")
                break
            except Exception as e:
                logger.error(f"Error consuming from {channel}: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def get_queue_length(self, channel: str) -> int:
        """Get the number of messages in a queue"""
        if not self.redis_client:
            await self.connect()
        
        return await self.redis_client.llen(channel)
    
    async def publish_notification(self, channel: str, event_type: str, data: Dict[str, Any]):
        """Publish a notification event"""
        notification = {
            "event_type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.publish(f"notifications:{channel}", notification)
    
    async def subscribe_notifications(self, pattern: str = "notifications:*") -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to notification events using pattern matching"""
        if not self.redis_client:
            await self.connect()
        
        pubsub = self.redis_client.pubsub()
        
        try:
            await pubsub.psubscribe(pattern)
            
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding notification message: {e}")
                        
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for Redis transactions"""
        if not self.redis_client:
            await self.connect()
        
        pipe = self.redis_client.pipeline()
        
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            await pipe.reset()
    
    async def set_with_expiry(self, key: str, value: Any, ttl_seconds: int):
        """Set a key-value pair with expiry"""
        if not self.redis_client:
            await self.connect()
        
        serialized_value = json.dumps(value) if not isinstance(value, str) else value
        await self.redis_client.setex(key, ttl_seconds, serialized_value)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key"""
        if not self.redis_client:
            await self.connect()
        
        value = await self.redis_client.get(key)
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value  # Return as string if not JSON
    
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        if not self.redis_client:
            await self.connect()
        
        result = await self.redis_client.delete(key)
        return result > 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis connection"""
        try:
            if not self.redis_client:
                await self.connect()
            
            # Test basic operations
            start_time = asyncio.get_event_loop().time()
            await self.redis_client.ping()
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "version": info.get("redis_version", "unknown")
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


class EventBus:
    """Event bus for application-wide event handling"""
    
    def __init__(self, message_queue: MessageQueue):
        self.message_queue = message_queue
        self.event_handlers = {}
    
    def register_handler(self, event_type: str, handler):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event"""
        # Publish to message queue for inter-service communication
        await self.message_queue.publish(f"events:{event_type}", {
            "event_type": event_type,
            "data": data
        })
        
        # Call local handlers
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
    
    async def listen_for_events(self, event_pattern: str = "*"):
        """Listen for events and dispatch to handlers"""
        async for message in self.message_queue.consume(f"events:{event_pattern}"):
            event_type = message.get("event_type")
            data = message.get("data", {})
            
            if event_type in self.event_handlers:
                for handler in self.event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event_type}: {e}")


# Global instances
_message_queue = None
_event_bus = None


def get_message_queue() -> MessageQueue:
    """Get global message queue instance"""
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueue()
    return _message_queue


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus(get_message_queue())
    return _event_bus


async def cleanup_messaging():
    """Cleanup messaging resources"""
    global _message_queue, _event_bus
    
    if _message_queue:
        await _message_queue.disconnect()
        _message_queue = None
    
    _event_bus = None
