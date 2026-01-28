"""
Message Queue System for GitHub Automation

Redis-based message queue system for high performance.

Requires Redis server to be running.

Usage:
    from message_queue import MessageQueueManager
    
    # Initialize (requires Redis server running)
    mq = MessageQueueManager()
    
    # Send tasks
    mq.send_task('queue1', {'username': 'john', 'emails': [...]})
    
    # Process tasks
    task = mq.get_task('queue1')
    if task:
        process_user_data(task['data'])
"""

import json
import time
import logging
from typing import Any, Dict, Optional
from datetime import datetime

try:
    import redis
except ImportError:
    raise ImportError(
        "Redis is required for the message queue system. "
        "Install it with: pip install redis"
    )

logger = logging.getLogger(__name__)


class RedisMessageQueue:
    """Redis-based message queue implementation."""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, password: str = None):
        """
        Initialize Redis connection.
        
        Args:
            host: Redis server host
            port: Redis server port  
            db: Redis database number
            password: Redis password (if required)
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.redis_client = None
        self.connected = False
        self.connect()
    
    def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_timeout=None,  # No timeout for blocking operations
                socket_connect_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            self.connected = True
            logger.info(f"[REDIS] Connected to Redis at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"[REDIS] Connection failed: {e}")
            logger.error(f"[REDIS] Make sure Redis server is running: redis-server")
            self.connected = False
            raise ConnectionError(
                f"Cannot connect to Redis at {self.host}:{self.port}. "
                f"Make sure Redis server is running. Error: {e}"
            )
    
    def send_task(self, queue_name: str, task_data: Any, priority: int = 0) -> bool:
        """
        Send a task to Redis queue.
        
        Args:
            queue_name: Name of the queue (e.g., 'queue1', 'queue2')
            task_data: Data to send (will be JSON serialized)
            priority: Priority level (higher = processed first)
            
        Returns:
            bool: True if successful
        """
        if not self.connected:
            logger.error("[REDIS] Not connected to Redis")
            return False
        
        try:
            message = {
                'data': task_data,
                'priority': priority,
                'timestamp': time.time(),
                'created_at': datetime.now().isoformat()
            }
            
            # Use sorted set for priority queue if priority > 0
            if priority > 0:
                # Lower score = higher priority (processed first)
                score = -priority
                self.redis_client.zadd(f"{queue_name}:priority", {json.dumps(message): score})
            else:
                # Regular FIFO queue (list)
                self.redis_client.lpush(queue_name, json.dumps(message))
            
            return True
            
        except Exception as e:
            logger.error(f"[REDIS] send_task error: {e}")
            return False
    
    def get_task(self, queue_name: str, timeout: int = 5) -> Optional[Dict]:
        """
        Get a task from Redis queue.
        
        Args:
            queue_name: Name of the queue
            timeout: Timeout in seconds for blocking operation
            
        Returns:
            dict: Task message or None if no task available
        """
        if not self.connected:
            logger.error("[REDIS] Not connected to Redis")
            return None
        
        try:
            # Check priority queue first
            priority_result = self.redis_client.zpopmin(f"{queue_name}:priority")
            if priority_result:
                message_json = priority_result[0][0]
                # Handle bytes if necessary
                if isinstance(message_json, bytes):
                    message_json = message_json.decode('utf-8')
                return json.loads(message_json)
            
            # Check regular queue (blocking pop with timeout)
            result = self.redis_client.brpop(queue_name, timeout=timeout)
            if result:
                message_json = result[1]
                # Handle bytes if necessary
                if isinstance(message_json, bytes):
                    message_json = message_json.decode('utf-8')
                return json.loads(message_json)
            
            return None
            
        except Exception as e:
            logger.error(f"[REDIS] get_task error: {e}")
            import traceback
            logger.error(f"[REDIS] Traceback: {traceback.format_exc()}")
            return None
    
    def get_queue_length(self, queue_name: str) -> int:
        """
        Get current queue length.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            int: Number of tasks in queue
        """
        if not self.connected:
            return 0
        
        try:
            regular_length = self.redis_client.llen(queue_name)
            priority_length = self.redis_client.zcard(f"{queue_name}:priority")
            return regular_length + priority_length
        except Exception as e:
            logger.error(f"[REDIS] get_queue_length error: {e}")
            return 0
    
    def clear_queue(self, queue_name: str) -> int:
        """
        Clear all tasks from queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            int: Number of tasks cleared
        """
        if not self.connected:
            return 0
        
        try:
            regular_cleared = self.redis_client.delete(queue_name)
            priority_cleared = self.redis_client.delete(f"{queue_name}:priority")
            return regular_cleared + priority_cleared
        except Exception as e:
            logger.error(f"[REDIS] clear_queue error: {e}")
            return 0
    
    def ping(self) -> bool:
        """Check if Redis connection is alive."""
        try:
            return self.redis_client.ping()
        except:
            return False


class MessageQueueManager:
    """Redis message queue manager."""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, 
                 redis_db: int = 0, redis_password: str = None):
        """
        Initialize Redis message queue manager.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (if required)
            
        Raises:
            ConnectionError: If cannot connect to Redis
        """
        self.queue = RedisMessageQueue(redis_host, redis_port, redis_db, redis_password)
        self.backend_type = "redis"
        
        if not self.queue.connected:
            raise ConnectionError(
                "Failed to connect to Redis. Make sure Redis server is running. "
                "Start it with: redis-server"
            )
    
    def send_task(self, queue_name: str, task_data: Any, priority: int = 0) -> bool:
        """Send a task to the queue."""
        return self.queue.send_task(queue_name, task_data, priority)
    
    def get_task(self, queue_name: str, timeout: int = 5) -> Optional[Dict]:
        """Get a task from the queue."""
        return self.queue.get_task(queue_name, timeout)
    
    def get_queue_length(self, queue_name: str) -> int:
        """Get current queue length."""
        return self.queue.get_queue_length(queue_name)
    
    def clear_queue(self, queue_name: str) -> int:
        """Clear all tasks from queue."""
        return self.queue.clear_queue(queue_name)
    
    def get_info(self) -> Dict[str, Any]:
        """Get queue manager information."""
        return {
            'backend_type': self.backend_type,
            'connected': self.queue.connected,
            'host': self.queue.host,
            'port': self.queue.port
        }
    
    def ping(self) -> bool:
        """Check if Redis is connected."""
        return self.queue.ping()


# Standard queue names for GitHub automation pipeline
class QueueNames:
    """Standard queue names."""
    QUEUE1 = "queue1"  # scraper -> database
    QUEUE2 = "queue2"  # database -> actions
    GITHUB_SEARCH = "github_search"
    EMAIL_SCRAPING = "email_scraping"
    DATABASE_SAVE = "database_save"
    SEND_INVITATIONS = "send_invitations"
    SEND_EMAILS = "send_emails"
    RETRY_FAILED = "retry_failed"


def test_message_queue():
    """Test the message queue system."""
    print("="*60)
    print("REDIS MESSAGE QUEUE TEST")
    print("="*60)
    
    try:
        # Initialize
        mq = MessageQueueManager()
        print(f"[OK] Connected to Redis: {mq.get_info()}")
        
        # Clear test queue
        mq.clear_queue('test_queue')
        
        # Send tasks
        print("\n[TEST] Sending tasks...")
        mq.send_task('test_queue', {'user': 'john', 'action': 'test1'}, priority=1)
        mq.send_task('test_queue', {'user': 'jane', 'action': 'test2'}, priority=2)
        mq.send_task('test_queue', {'user': 'bob', 'action': 'test3'}, priority=0)
        
        print(f"Queue length: {mq.get_queue_length('test_queue')}")
        
        # Get tasks
        print("\n[TEST] Getting tasks (priority order)...")
        while True:
            task = mq.get_task('test_queue', timeout=1)
            if not task:
                break
            print(f"  Got task: {task['data']} (priority={task['priority']})")
        
        print(f"\n[OK] Test completed successfully!")
        print(f"Queue length after processing: {mq.get_queue_length('test_queue')}")
        
    except ConnectionError as e:
        print(f"\n[ERROR] Connection Error: {e}")
        print("\nTo fix this:")
        print("  1. Install Redis: https://redis.io/download")
        print("  2. Start Redis server: redis-server")
        print("  3. Or use Docker: docker run -d -p 6379:6379 redis")
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_message_queue()
