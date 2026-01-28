"""
GitHub User API - Fetch user account information from GitHub API

This module provides functionality to:
- Get GitHub user profiles and metadata
- Search for users by various criteria
- Batch process multiple user requests
- Handle rate limiting and API errors
"""

import urllib.request
import urllib.parse
import json
import time
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime, timedelta

from .utils import GitHubRateLimit, validate_username, batch_process

logger = logging.getLogger(__name__)


class GitHubUserFetcher:
    """Handles fetching user information from GitHub API."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub user fetcher.
        
        Args:
            token: Optional GitHub Personal Access Token for higher rate limits
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.rate_limit = GitHubRateLimit(token is not None)
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Module-Python'
        }
        
        if token:
            self.headers['Authorization'] = f'token {token}'
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """
        Get detailed information for a single GitHub user.
        
        Args:
            username: GitHub username to fetch
            
        Returns:
            dict: User information or error details
        """
        if not validate_username(username):
            return {
                'success': False,
                'error': f'Invalid username format: {username}',
                'username': username
            }
        
        try:
            # Check rate limit
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit hit, waiting {wait_time} seconds")
                time.sleep(wait_time)
            
            # Make API request
            url = f"{self.base_url}/users/{username}"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    user_data = json.loads(response.read().decode())
                    
                    # Track rate limit
                    self.rate_limit.update_from_headers(response.headers)
                    
                    # Process and return user data
                    return {
                        'success': True,
                        'username': username,
                        'data': self._process_user_data(user_data)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'username': username
                    }
                    
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    'success': False,
                    'error': 'User not found',
                    'username': username
                }
            elif e.code == 403:
                return {
                    'success': False,
                    'error': 'API rate limit exceeded or access denied',
                    'username': username
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {e.code}: {e.reason}',
                    'username': username
                }
        except Exception as e:
            logger.error(f"Error fetching user {username}: {e}")
            return {
                'success': False,
                'error': str(e),
                'username': username
            }
    
    def get_users_batch(self, usernames: List[str], 
                       batch_size: int = 10, 
                       delay: float = 1.0) -> List[Dict[str, Any]]:
        """
        Get information for multiple users in batches.
        
        Args:
            usernames: List of GitHub usernames to fetch
            batch_size: Number of users to process in each batch
            delay: Delay between batches in seconds
            
        Returns:
            list: List of user information dictionaries
        """
        results = []
        total_users = len(usernames)
        
        logger.info(f"Fetching {total_users} users in batches of {batch_size}")
        
        # Process in batches
        for i in range(0, total_users, batch_size):
            batch = usernames[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_users + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} users")
            
            # Process each user in the batch
            for username in batch:
                user_result = self.get_user(username)
                results.append(user_result)
                
                # Small delay between requests to be respectful
                if username != batch[-1]:  # Don't delay after last user in batch
                    time.sleep(0.1)
            
            # Delay between batches
            if i + batch_size < total_users:
                logger.info(f"Waiting {delay}s before next batch...")
                time.sleep(delay)
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        logger.info(f"Batch complete: {successful} successful, {failed} failed")
        
        return results
    
    def search_users(self, query: str, 
                    sort: str = 'best-match',
                    order: str = 'desc',
                    per_page: int = 30,
                    page: int = 1) -> Dict[str, Any]:
        """
        Search for GitHub users by query.
        
        Args:
            query: Search query (can include qualifiers like 'location:seattle')
            sort: Sort by 'followers', 'repositories', 'joined', or 'best-match'
            order: Sort order 'asc' or 'desc'
            per_page: Results per page (max 100)
            page: Page number to fetch
            
        Returns:
            dict: Search results with users and metadata
        """
        try:
            # Check search API rate limit (more restrictive)
            if not self.rate_limit.can_make_search_request():
                wait_time = self.rate_limit.get_search_wait_time()
                logger.warning(f"Search rate limit hit, waiting {wait_time} seconds")
                time.sleep(wait_time)
            
            # Build search URL
            params = {
                'q': query,
                'sort': sort,
                'order': order,
                'per_page': min(per_page, 100),
                'page': page
            }
            
            url = f"{self.base_url}/search/users?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    search_data = json.loads(response.read().decode())
                    
                    # Track search rate limit
                    self.rate_limit.update_search_from_headers(response.headers)
                    
                    # Process search results
                    users = []
                    for user_item in search_data.get('items', []):
                        users.append(self._process_user_data(user_item))
                    
                    return {
                        'success': True,
                        'query': query,
                        'total_count': search_data.get('total_count', 0),
                        'users': users,
                        'page': page,
                        'per_page': per_page
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'query': query
                    }
                    
        except Exception as e:
            logger.error(f"Error searching users with query '{query}': {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query
            }
    
    def get_user_organizations(self, username: str) -> List[Dict[str, Any]]:
        """
        Get organizations that a user belongs to.
        
        Args:
            username: GitHub username
            
        Returns:
            list: List of organization information
        """
        try:
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            url = f"{self.base_url}/users/{username}/orgs"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    orgs_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    return [
                        {
                            'login': org['login'],
                            'name': org.get('name'),
                            'description': org.get('description'),
                            'url': org['html_url'],
                            'avatar_url': org['avatar_url']
                        }
                        for org in orgs_data
                    ]
                else:
                    logger.warning(f"Failed to get organizations for {username}: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching organizations for {username}: {e}")
            return []
    
    def get_user_repositories(self, username: str, 
                            repo_type: str = 'owner',
                            per_page: int = 30) -> List[Dict[str, Any]]:
        """
        Get repositories for a user.
        
        Args:
            username: GitHub username
            repo_type: Type of repos ('all', 'owner', 'member')
            per_page: Number of repos per page (max 100)
            
        Returns:
            list: List of repository information
        """
        try:
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            params = {
                'type': repo_type,
                'per_page': min(per_page, 100),
                'sort': 'updated'
            }
            
            url = f"{self.base_url}/users/{username}/repos?" + urllib.parse.urlencode(params)
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    repos_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    return [
                        {
                            'name': repo['name'],
                            'full_name': repo['full_name'],
                            'description': repo.get('description'),
                            'language': repo.get('language'),
                            'stars': repo['stargazers_count'],
                            'forks': repo['forks_count'],
                            'url': repo['html_url'],
                            'private': repo['private'],
                            'updated_at': repo['updated_at']
                        }
                        for repo in repos_data
                    ]
                else:
                    logger.warning(f"Failed to get repositories for {username}: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching repositories for {username}: {e}")
            return []
    
    def _process_user_data(self, raw_user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and clean raw user data from GitHub API.
        
        Args:
            raw_user_data: Raw user data from GitHub API
            
        Returns:
            dict: Processed user data
        """
        return {
            'username': raw_user_data.get('login'),
            'id': raw_user_data.get('id'),
            'name': raw_user_data.get('name'),
            'email': raw_user_data.get('email'),
            'bio': raw_user_data.get('bio'),
            'company': raw_user_data.get('company'),
            'location': raw_user_data.get('location'),
            'blog': raw_user_data.get('blog'),
            'twitter_username': raw_user_data.get('twitter_username'),
            'public_repos': raw_user_data.get('public_repos', 0),
            'public_gists': raw_user_data.get('public_gists', 0),
            'followers': raw_user_data.get('followers', 0),
            'following': raw_user_data.get('following', 0),
            'created_at': raw_user_data.get('created_at'),
            'updated_at': raw_user_data.get('updated_at'),
            'avatar_url': raw_user_data.get('avatar_url'),
            'html_url': raw_user_data.get('html_url'),
            'type': raw_user_data.get('type', 'User'),
            'hireable': raw_user_data.get('hireable')
        }
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            dict: Rate limit information
        """
        return self.rate_limit.get_status()


class UserAPI:
    """High-level interface for GitHub user operations."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize UserAPI.
        
        Args:
            token: Optional GitHub Personal Access Token
        """
        self.fetcher = GitHubUserFetcher(token)
    
    def get_user_info(self, username: str, include_repos: bool = False,
                     include_orgs: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive user information.
        
        Args:
            username: GitHub username
            include_repos: Whether to include repository information
            include_orgs: Whether to include organization information
            
        Returns:
            dict: Comprehensive user information
        """
        # Get basic user info
        result = self.fetcher.get_user(username)
        
        if not result['success']:
            return result
        
        user_info = result['data']
        
        # Add additional information if requested
        if include_repos:
            user_info['repositories'] = self.fetcher.get_user_repositories(username)
        
        if include_orgs:
            user_info['organizations'] = self.fetcher.get_user_organizations(username)
        
        return {
            'success': True,
            'username': username,
            'data': user_info
        }
    
    def find_users_by_criteria(self, criteria: Dict[str, str],
                              limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find users by various criteria.
        
        Args:
            criteria: Search criteria (location, company, language, etc.)
            limit: Maximum number of users to return
            
        Returns:
            list: List of matching users
        """
        # Build search query
        query_parts = []
        
        for key, value in criteria.items():
            if key == 'location':
                query_parts.append(f'location:"{value}"')
            elif key == 'company':
                query_parts.append(f'company:"{value}"')
            elif key == 'language':
                query_parts.append(f'language:{value}')
            elif key == 'followers':
                query_parts.append(f'followers:{value}')
            elif key == 'repos':
                query_parts.append(f'repos:{value}')
            elif key == 'created':
                query_parts.append(f'created:{value}')
            else:
                # Generic search in name, bio, etc.
                query_parts.append(value)
        
        query = ' '.join(query_parts)
        
        # Search users
        all_users = []
        page = 1
        per_page = min(limit, 100)
        
        while len(all_users) < limit:
            remaining = limit - len(all_users)
            current_per_page = min(per_page, remaining)
            
            result = self.fetcher.search_users(
                query=query,
                per_page=current_per_page,
                page=page
            )
            
            if not result['success'] or not result['users']:
                break
            
            all_users.extend(result['users'])
            
            # If we got fewer results than requested, we're done
            if len(result['users']) < current_per_page:
                break
            
            page += 1
        
        return all_users[:limit]
    
    def batch_get_users(self, usernames: List[str],
                       batch_size: int = 10) -> Dict[str, Any]:
        """
        Get information for multiple users efficiently.
        
        Args:
            usernames: List of GitHub usernames
            batch_size: Size of each batch for processing
            
        Returns:
            dict: Batch results with successful and failed users
        """
        results = self.fetcher.get_users_batch(usernames, batch_size)
        
        successful_users = []
        failed_users = []
        
        for result in results:
            if result['success']:
                successful_users.append(result['data'])
            else:
                failed_users.append({
                    'username': result['username'],
                    'error': result['error']
                })
        
        return {
            'total_requested': len(usernames),
            'successful_count': len(successful_users),
            'failed_count': len(failed_users),
            'successful_users': successful_users,
            'failed_users': failed_users,
            'rate_limit_status': self.fetcher.get_rate_limit_status()
        }
    
    def export_users_to_list(self, users_data: List[Dict[str, Any]],
                            fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Export user data to a simplified list format.
        
        Args:
            users_data: List of user data dictionaries
            fields: Optional list of fields to include
            
        Returns:
            list: Simplified user data list
        """
        if fields is None:
            fields = ['username', 'name', 'email', 'company', 'location', 'public_repos', 'followers']
        
        export_list = []
        
        for user in users_data:
            exported_user = {}
            for field in fields:
                exported_user[field] = user.get(field)
            export_list.append(exported_user)
        
        return export_list
