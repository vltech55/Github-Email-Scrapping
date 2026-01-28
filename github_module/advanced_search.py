"""
Advanced GitHub User Search - Complete implementation

This module provides advanced GitHub user search functionality with all available parameters.
"""

import urllib.request
import urllib.parse
import json
import time
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime, timedelta

from .utils import GitHubRateLimit, validate_username

logger = logging.getLogger(__name__)


class GitHubAdvancedSearch:
    """Advanced GitHub user search with all available parameters."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize with optional GitHub token."""
        self.token = token
        self.base_url = "https://api.github.com"
        self.rate_limit = GitHubRateLimit(token is not None)
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Module-Python-AdvancedSearch'
        }
        
        if token:
            self.headers['Authorization'] = f'token {token}'
    
    def search_users_advanced(self, 
                             location: Optional[str] = None,
                             company: Optional[str] = None,
                             language: Optional[str] = None,
                             min_followers: Optional[int] = None,
                             max_followers: Optional[int] = None,
                             min_repos: Optional[int] = None,
                             max_repos: Optional[int] = None,
                             created_after: Optional[str] = None,
                             created_before: Optional[str] = None,
                             account_type: str = 'user',
                             organization: Optional[str] = None,
                             search_in: Optional[List[str]] = None,
                             fullname: Optional[str] = None,
                             sort: str = 'best-match',
                             order: str = 'desc',
                             per_page: int = 50,
                             max_results: int = 1000) -> Dict[str, Any]:
        """
        Advanced GitHub user search with all available parameters.
        
        Args:
            location: User location (e.g., "San Francisco", "London")
            company: Company name (e.g., "Google", "Microsoft") 
            language: Programming language (e.g., "python", "javascript")
            min_followers: Minimum number of followers
            max_followers: Maximum number of followers
            min_repos: Minimum number of repositories
            max_repos: Maximum number of repositories
            created_after: Account created after date (YYYY-MM-DD)
            created_before: Account created before date (YYYY-MM-DD)
            account_type: 'user' or 'org'
            organization: GitHub organization name
            search_in: Fields to search in ['login', 'name', 'email']
            fullname: Full name to search for
            sort: Sort by 'followers', 'repositories', 'joined', 'best-match'
            order: 'asc' or 'desc'
            per_page: Results per page (max 100)
            max_results: Maximum total results to return
            
        Returns:
            dict: Search results with users and metadata
        """
        
        # Build search query
        query_parts = []
        
        # Location search
        if location:
            if ' ' in location:
                query_parts.append(f'location:"{location}"')
            else:
                query_parts.append(f'location:{location}')
        
        # Company search
        if company:
            if ' ' in company:
                query_parts.append(f'company:"{company}"')
            else:
                query_parts.append(f'company:{company}')
        
        # Language search
        if language:
            query_parts.append(f'language:{language}')
        
        # Followers range
        if min_followers is not None or max_followers is not None:
            if min_followers is not None and max_followers is not None:
                query_parts.append(f'followers:{min_followers}..{max_followers}')
            elif min_followers is not None:
                query_parts.append(f'followers:>={min_followers}')
            elif max_followers is not None:
                query_parts.append(f'followers:<={max_followers}')
        
        # Repositories range
        if min_repos is not None or max_repos is not None:
            if min_repos is not None and max_repos is not None:
                query_parts.append(f'repos:{min_repos}..{max_repos}')
            elif min_repos is not None:
                query_parts.append(f'repos:>={min_repos}')
            elif max_repos is not None:
                query_parts.append(f'repos:<={max_repos}')
        
        # Date range
        if created_after or created_before:
            if created_after and created_before:
                query_parts.append(f'created:{created_after}..{created_before}')
            elif created_after:
                query_parts.append(f'created:>{created_after}')
            elif created_before:
                query_parts.append(f'created:<{created_before}')
        
        # Account type
        if account_type:
            query_parts.append(f'type:{account_type}')
        
        # Organization
        if organization:
            query_parts.append(f'org:{organization}')
        
        # Search in specific fields
        if search_in:
            for field in search_in:
                if field in ['login', 'name', 'email']:
                    query_parts.append(f'in:{field}')
        
        # Full name search
        if fullname:
            if ' ' in fullname:
                query_parts.append(f'fullname:"{fullname}"')
            else:
                query_parts.append(f'fullname:{fullname}')
        
        # Build final query
        query = ' '.join(query_parts)
        
        if not query.strip():
            query = 'type:user'  # Default query
        
        logger.info(f"GitHub search query: {query}")
        
        # Execute paginated search
        all_users = []
        page = 1
        total_count = 0
        
        while len(all_users) < max_results:
            # Calculate remaining results needed
            remaining = max_results - len(all_users)
            current_per_page = min(per_page, remaining, 100)  # GitHub limit: 100/page
            
            # Make search request
            page_result = self._search_users_page(
                query, sort, order, current_per_page, page
            )
            
            if not page_result['success']:
                break
            
            # Update total count from first page
            if page == 1:
                total_count = page_result['total_count']
                logger.info(f"Found {total_count} total users matching criteria")

            
            # Add users from this page
            page_users = page_result['users']
            # logger.info(f"Fetched {len(page_users)} users from page {page}")
            all_users.extend(page_users)
            
            # Check if we should continue
            if len(page_users) < current_per_page or len(page_users) == 0:
                break  # No more results

            # logger.info(f"{len(all_users)}")
            
            if len(all_users) >= max_results:
                all_users = all_users[:max_results]  # Trim to exact limit
                break

            # logger.info("aaaaaaaaa")
            
            page += 1
            
            # Respectful delay between pages
            time.sleep(1.0)
        
        return {
            'success': True,
            'query': query,
            'total_found': total_count,
            'total_returned': len(all_users),
            'users': all_users,
            'pages_fetched': page,
            'search_parameters': {
                'location': location,
                'company': company,
                'language': language,
                'followers_range': f"{min_followers or '?'}-{max_followers or '?'}",
                'repos_range': f"{min_repos or '?'}-{max_repos or '?'}",
                'created_after': created_after,
                'created_before': created_before,
                'account_type': account_type,
                'organization': organization
            }
        }
    
    def _search_users_page(self, query: str, sort: str, order: str, 
                          per_page: int, page: int) -> Dict[str, Any]:
        """Search single page of users."""
        try:
            # Check search rate limit (more restrictive: 30/minute)
            if not self.rate_limit.can_make_search_request():
                wait_time = self.rate_limit.get_search_wait_time()
                logger.warning(f"Search rate limit hit, waiting {wait_time} seconds")
                time.sleep(wait_time)
            
            # Build URL
            params = {
                'q': query,
                'sort': sort,
                'order': order,
                'per_page': per_page,
                'page': page
            }
            
            url = f"{self.base_url}/search/users?" + urllib.parse.urlencode(params)
            logger.info(f"url {url}")
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    
                    # Update rate limit info
                    self.rate_limit.update_search_from_headers(response.headers)
                    
                    # Process users
                    users = []
                    for item in data.get('items', []):
                        user = {
                            'login': item['login'],
                            'id': item['id'],
                            'avatar_url': item['avatar_url'],
                            'html_url': item['html_url'],
                            'type': item['type'],
                            'score': item.get('score', 0.0)
                        }
                        users.append(user)
                    
                    return {
                        'success': True,
                        'users': users,
                        'total_count': data.get('total_count', 0),
                        'page': page
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'users': [],
                        'total_count': 0
                    }
                    
        except Exception as e:
            logger.error(f"Search page {page} failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'users': [],
                'total_count': 0
            }
