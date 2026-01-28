"""
Utility functions for GitHub operations.
"""

import time
import re
from typing import List, Dict, Any, Optional, Callable, TypeVar, Iterator
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


class GitHubRateLimit:
    """Manages GitHub API rate limiting."""
    
    def __init__(self, authenticated: bool = True):
        """
        Initialize rate limit manager.
        
        Args:
            authenticated: Whether using authenticated requests
        """
        self.authenticated = authenticated
        
        # Rate limits (per hour)
        self.core_limit = 5000 if authenticated else 60
        self.search_limit = 30  # per minute for search API
        
        # Current status (start optimistic, will update from real API responses)
        self.core_remaining = self.core_limit
        self.core_reset_time = datetime.now() + timedelta(hours=1)
        
        self.search_remaining = self.search_limit
        self.search_reset_time = datetime.now() + timedelta(minutes=1)
        
        # Buffers to avoid hitting limits (reduced for better throughput)
        self.core_buffer = 10 if authenticated else 3
        self.search_buffer = 2
        
        # Track if we've gotten real data from API
        self.has_real_data = False
    
    def can_make_request(self) -> bool:
        """Check if we can make a core API request."""
        # If we don't have real data yet, be optimistic and allow request
        if not self.has_real_data:
            return True
        
        if datetime.now() > self.core_reset_time:
            self.core_remaining = self.core_limit
            self.core_reset_time = datetime.now() + timedelta(hours=1)
        
        return self.core_remaining > self.core_buffer
    
    def can_make_search_request(self) -> bool:
        """Check if we can make a search API request."""
        # If we don't have real data yet, be optimistic and allow request
        if not self.has_real_data:
            return True
            
        if datetime.now() > self.search_reset_time:
            self.search_remaining = self.search_limit
            self.search_reset_time = datetime.now() + timedelta(minutes=1)
        
        return self.search_remaining > self.search_buffer
    
    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Update rate limit info from API response headers."""
        try:
            if 'x-ratelimit-remaining' in headers:
                self.core_remaining = int(headers['x-ratelimit-remaining'])
                self.has_real_data = True
            
            if 'x-ratelimit-reset' in headers:
                reset_timestamp = int(headers['x-ratelimit-reset'])
                self.core_reset_time = datetime.fromtimestamp(reset_timestamp)
        except (ValueError, KeyError) as e:
            logger.warning(f"Could not parse rate limit headers: {e}")
    
    def update_search_from_headers(self, headers: Dict[str, str]) -> None:
        """Update search rate limit info from API response headers."""
        try:
            # Search API uses different headers
            if 'x-ratelimit-remaining' in headers:
                self.search_remaining = int(headers['x-ratelimit-remaining'])
            
            if 'x-ratelimit-reset' in headers:
                reset_timestamp = int(headers['x-ratelimit-reset'])
                # Search API resets every minute
                self.search_reset_time = datetime.fromtimestamp(reset_timestamp)
        except (ValueError, KeyError) as e:
            logger.warning(f"Could not parse search rate limit headers: {e}")
    
    def get_wait_time(self) -> float:
        """Get time to wait before next core API request."""
        if self.core_remaining > self.core_buffer:
            return 0.0
        
        wait_time = (self.core_reset_time - datetime.now()).total_seconds()
        return max(0.0, wait_time)
    
    def get_search_wait_time(self) -> float:
        """Get time to wait before next search API request."""
        if self.search_remaining > self.search_buffer:
            return 2.0  # Minimum delay for search API
        
        wait_time = (self.search_reset_time - datetime.now()).total_seconds()
        return max(2.0, wait_time)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return {
            'core_api': {
                'limit': self.core_limit,
                'remaining': self.core_remaining,
                'reset_time': self.core_reset_time.isoformat(),
                'can_request': self.can_make_request()
            },
            'search_api': {
                'limit': self.search_limit,
                'remaining': self.search_remaining,
                'reset_time': self.search_reset_time.isoformat(),
                'can_request': self.can_make_search_request()
            },
            'authenticated': self.authenticated
        }


def validate_username(username: str) -> bool:
    """
    Validate GitHub username format.
    
    Args:
        username: GitHub username to validate
        
    Returns:
        bool: True if valid format
    """
    if not username or not isinstance(username, str):
        return False
    
    # GitHub username rules:
    # - May only contain alphanumeric characters or hyphens
    # - Cannot have multiple consecutive hyphens
    # - Cannot begin or end with a hyphen
    # - Maximum 39 characters
    
    if len(username) > 39 or len(username) == 0:
        return False
    
    if username.startswith('-') or username.endswith('-'):
        return False
    
    if '--' in username:
        return False
    
    # Only alphanumeric and hyphens allowed
    if not re.match(r'^[a-zA-Z0-9-]+$', username):
        return False
    
    return True


def validate_repo_name(repo_name: str) -> bool:
    """
    Validate GitHub repository name format.
    
    Args:
        repo_name: Repository name to validate
        
    Returns:
        bool: True if valid format
    """
    if not repo_name or not isinstance(repo_name, str):
        return False
    
    # Repository name rules are more flexible than usernames
    # Generally allow alphanumeric, hyphens, underscores, and dots
    if len(repo_name) > 100 or len(repo_name) == 0:
        return False
    
    # Basic pattern check
    if not re.match(r'^[a-zA-Z0-9._-]+$', repo_name):
        return False
    
    return True


def batch_process(items: List[T], 
                 processor: Callable[[T], Any],
                 batch_size: int = 10,
                 delay: float = 1.0,
                 on_batch_complete: Optional[Callable[[int, int], None]] = None) -> List[Any]:
    """
    Process items in batches with delays.
    
    Args:
        items: List of items to process
        processor: Function to process each item
        batch_size: Number of items per batch
        delay: Delay between batches in seconds
        on_batch_complete: Optional callback after each batch
        
    Returns:
        list: Results from processing all items
    """
    results = []
    total_items = len(items)
    
    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_items + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} items")
        
        # Process batch
        batch_results = []
        for item in batch:
            result = processor(item)
            batch_results.append(result)
            results.append(result)
        
        # Callback
        if on_batch_complete:
            on_batch_complete(batch_num, total_batches)
        
        # Delay between batches (except after last batch)
        if i + batch_size < total_items:
            logger.debug(f"Waiting {delay}s before next batch...")
            time.sleep(delay)
    
    return results


def chunk_list(items: List[T], chunk_size: int) -> Iterator[List[T]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: List to chunk
        chunk_size: Maximum size of each chunk
        
    Yields:
        List chunks of the specified size
    """
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def safe_get_nested(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary values.
    
    Args:
        data: Dictionary to search
        *keys: Nested keys to follow
        default: Default value if key not found
        
    Returns:
        Value at nested key path or default
    """
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def format_github_url(username: str, repo: Optional[str] = None) -> str:
    """
    Format a GitHub URL for a user or repository.
    
    Args:
        username: GitHub username
        repo: Optional repository name
        
    Returns:
        str: Formatted GitHub URL
    """
    base_url = "https://github.com"
    
    if repo:
        return f"{base_url}/{username}/{repo}"
    else:
        return f"{base_url}/{username}"


def parse_github_url(url: str) -> Dict[str, Optional[str]]:
    """
    Parse a GitHub URL to extract username and repository.
    
    Args:
        url: GitHub URL to parse
        
    Returns:
        dict: Parsed components (username, repo)
    """
    # Clean URL
    url = url.strip().rstrip('/')
    
    # Remove protocol
    if url.startswith('http://') or url.startswith('https://'):
        url = url.split('://', 1)[1]
    
    # Remove github.com
    if url.startswith('github.com/'):
        url = url[11:]
    elif url.startswith('www.github.com/'):
        url = url[15:]
    
    # Split path
    parts = url.split('/')
    
    result = {
        'username': parts[0] if len(parts) > 0 else None,
        'repo': parts[1] if len(parts) > 1 else None
    }
    
    # Validate extracted components
    if result['username'] and not validate_username(result['username']):
        result['username'] = None
    
    if result['repo'] and not validate_repo_name(result['repo']):
        result['repo'] = None
    
    return result


def estimate_api_calls(operations: Dict[str, int]) -> Dict[str, Any]:
    """
    Estimate GitHub API calls needed for operations.
    
    Args:
        operations: Dictionary of operation types and counts
        
    Returns:
        dict: Estimated API usage and time
    """
    # API call estimates per operation
    call_estimates = {
        'get_user': 1,
        'search_users': 1,
        'get_user_repos': 1,
        'get_user_orgs': 1,
        'send_repo_invite': 1,
        'send_org_invite': 2,  # Need user ID first
        'get_commits': 1,
        'get_events': 1
    }
    
    total_calls = 0
    breakdown = {}
    
    for operation, count in operations.items():
        calls_per_op = call_estimates.get(operation, 1)
        calls_needed = count * calls_per_op
        total_calls += calls_needed
        breakdown[operation] = {
            'count': count,
            'calls_per_operation': calls_per_op,
            'total_calls': calls_needed
        }
    
    # Estimate time (with conservative delays)
    estimated_minutes = total_calls * 0.5  # 0.5 seconds per call average
    
    return {
        'total_api_calls': total_calls,
        'breakdown': breakdown,
        'estimated_time_minutes': estimated_minutes,
        'rate_limit_considerations': {
            'authenticated_limit': 5000,
            'unauthenticated_limit': 60,
            'search_limit_per_minute': 30,
            'recommendation': 'Use authenticated requests for better limits'
        }
    }


def create_progress_reporter(total_items: int) -> Callable[[int], None]:
    """
    Create a progress reporting function.
    
    Args:
        total_items: Total number of items to process
        
    Returns:
        Function that reports progress when called with current count
    """
    def report_progress(current: int) -> None:
        percentage = (current / total_items) * 100 if total_items > 0 else 0
        logger.info(f"Progress: {current}/{total_items} ({percentage:.1f}%)")
    
    return report_progress


def retry_on_rate_limit(func: Callable[..., T], 
                       max_retries: int = 3,
                       initial_delay: float = 60.0) -> Callable[..., T]:
    """
    Decorator to retry function calls on rate limit errors.
    
    Args:
        func: Function to wrap
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        
    Returns:
        Wrapped function with retry logic
    """
    def wrapper(*args, **kwargs) -> T:
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    raise
                
                # Check if it's a rate limit error
                error_str = str(e).lower()
                if 'rate limit' in error_str or '403' in error_str:
                    logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise
        
        return func(*args, **kwargs)
    
    return wrapper
