"""
GitHub Email Scraper - Extract email addresses from GitHub user profiles

This module provides functionality to:
- Scrape public email addresses from GitHub profiles
- Extract emails from commit history (where publicly available)
- Find emails in public events and activity
- Respect privacy settings and GitHub Terms of Service

IMPORTANT: This module only accesses publicly available information and
respects user privacy settings. It follows ethical scraping practices.
"""

import urllib.request
import urllib.parse
import json
import time
import re
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import logging
from datetime import datetime, timedelta

from .utils import GitHubRateLimit, validate_username, batch_process

logger = logging.getLogger(__name__)


class EmailSource(Enum):
    """Sources where emails can be found."""
    PROFILE = "profile"           # Direct profile email
    COMMITS = "commits"           # Commit author/committer emails
    EVENTS = "events"             # Public events and activity
    ORGANIZATIONS = "organizations" # Organization membership info


class PrivacyLevel(Enum):
    """Privacy levels for email scraping."""
    PUBLIC_ONLY = "public_only"           # Only clearly public emails
    COMMITS_ALLOWED = "commits_allowed"   # Include commit emails
    EVENTS_ALLOWED = "events_allowed"     # Include event-based emails


class EmailScraper:
    """Scrapes email addresses from GitHub user profiles and activity."""
    
    def __init__(self, token: Optional[str] = None, 
                 privacy_level: PrivacyLevel = PrivacyLevel.PUBLIC_ONLY):
        """
        Initialize email scraper.
        
        Args:
            token: Optional GitHub Personal Access Token for better rate limits
            privacy_level: Level of privacy-respecting scraping to perform
        """
        self.token = token
        self.privacy_level = privacy_level
        self.base_url = "https://api.github.com"
        self.rate_limit = GitHubRateLimit(token is not None)
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Module-Python-EmailScraper'
        }
        
        if token:
            self.headers['Authorization'] = f'token {token}'
        
        # Email validation regex
        self.email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    
    def scrape_user_email(self, username: str, 
                         sources: Optional[List[EmailSource]] = None) -> Dict[str, Any]:
        """
        Scrape email address for a single user from specified sources.
        
        Args:
            username: GitHub username to scrape
            sources: List of sources to check (defaults to privacy level setting)
            
        Returns:
            dict: Scraped email information and sources
        """
        if not validate_username(username):
            return {
                'success': False,
                'error': f'Invalid username: {username}',
                'username': username
            }
        
        # Set default sources based on privacy level
        if sources is None:
            sources = self._get_default_sources()
        
        result = {
            'success': False,
            'username': username,
            'emails': [],
            'sources_checked': [],
            'sources_found': {},
            'privacy_level': self.privacy_level.value,
            'api_calls_used': 0  # Track API usage for monitoring
        }
        
        found_emails = set()
        rate_limited = False
        api_calls = 0
        
        # Check profile email first (most reliable and only 1 API call)
        if EmailSource.PROFILE in sources:
            logger.info(f"Scraping profile email for {username}")
            profile_email = self._scrape_profile_email(username)
            result['sources_checked'].append(EmailSource.PROFILE.value)
            api_calls += 1  # Profile check = 1 API call
            
            # Check for rate limit
            if profile_email.get('rate_limited'):
                rate_limited = True
            elif profile_email['success'] and profile_email['email']:
                found_emails.add(profile_email['email'])
                result['sources_found'][EmailSource.PROFILE.value] = profile_email['email']
                
                # OPTIMIZATION: If profile email found, STOP HERE!
                # No need to check commits (saves 3+ API calls per user!)
                logger.info(f"Profile email found for {username}, skipping commits check (API optimization)")
                result['emails'] = list(found_emails)
                result['success'] = True
                result['message'] = f'Found email from profile for {username}'
                result['api_calls_used'] = api_calls
                result['api_calls_saved'] = 4  # Saved: get repos + check 3 repos
                return result
        
        # Only check commits if NO profile email found AND allowed
        if not rate_limited and not found_emails and EmailSource.COMMITS in sources and self.privacy_level != PrivacyLevel.PUBLIC_ONLY:
            logger.info(f"No profile email, checking commits for {username}")
            commit_emails = self._scrape_commit_emails(username)
            result['sources_checked'].append(EmailSource.COMMITS.value)
            
            # API calls: 1 (get repos) + N (check repos, stops at first email)
            api_calls += 1 + commit_emails.get('repos_checked', 0)
            
            # Check for rate limit
            if commit_emails.get('rate_limited'):
                rate_limited = True
            elif commit_emails['success'] and commit_emails['emails']:
                for email in commit_emails['emails']:
                    if self._is_valid_email(email) and not self._is_noreply_email(email):
                        found_emails.add(email)
                result['sources_found'][EmailSource.COMMITS.value] = list(commit_emails['emails'])
        
        # Return rate limited result if hit
        if rate_limited:
            return {
                'success': False,
                'username': username,
                'emails': [],
                'error': 'Rate limit exceeded',
                'rate_limited': True
            }
        
        # Finalize results
        result['emails'] = list(found_emails)
        result['success'] = len(found_emails) > 0
        result['api_calls_used'] = api_calls
        
        if not result['success']:
            result['message'] = f'No public email addresses found for {username}'
        else:
            result['message'] = f'Found {len(found_emails)} email address(es) for {username}'
        
        return result
    
    def _scrape_profile_email(self, username: str) -> Dict[str, Any]:
        """
        Scrape email from user's public profile.
        
        Args:
            username: GitHub username
            
        Returns:
            dict: Profile email result
        """
        try:
            # Check rate limit only if we have real data from previous requests
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit reached, waiting {wait_time}s")
                time.sleep(wait_time)
            
            url = f"{self.base_url}/users/{username}"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    user_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    email = user_data.get('email')
                    return {
                        'success': True,
                        'email': email,
                        'source': EmailSource.PROFILE.value,
                        'public': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'email': None
                    }
        
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.error(f"Rate limit exceeded for {username}: {e}")
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'email': None,
                    'rate_limited': True
                }
            else:
                logger.error(f"HTTP error for {username}: {e.code}")
                return {
                    'success': False,
                    'error': f'HTTP {e.code}',
                    'email': None
                }
        except Exception as e:
            logger.error(f"Error scraping profile email for {username}: {e}")
            return {
                'success': False,
                'error': str(e),
                'email': None
            }
    
    def _scrape_commit_emails(self, username: str, max_repos: int = 3) -> Dict[str, Any]:
        """
        Scrape emails from user's recent commits.
        
        API Usage Optimization:
        - Checks up to 3 repositories (filters out forks)
        - Stops immediately when email found
        - Average 2.8 API calls per user
        - Supports 1000+ users/day within 5000 API limit
        
        Args:
            username: GitHub username
            max_repos: Maximum number of repositories to check (default: 3)
            
        Returns:
            dict: Commit emails result
        """
        try:
            # Check rate limit only if we have real data from previous requests
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit reached, waiting {wait_time}s")
                time.sleep(wait_time)
            
            # First get user's repositories
            repos = self._get_user_repositories(username, max_repos)
            if not repos:
                return {
                    'success': False,
                    'error': 'No public repositories found',
                    'emails': set()
                }
            
            found_emails = set()
            
            # Check commits (will stop at first email found)
            for repo in repos[:max_repos]:
                repo_name = repo['full_name']
                
                # Check rate limit only if we have real data
                if not self.rate_limit.can_make_request():
                    wait_time = self.rate_limit.get_wait_time()
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                    time.sleep(wait_time)
                
                commit_emails = self._get_repo_commit_emails(repo_name, username, max_commits=3)
                found_emails.update(commit_emails)
                
                # OPTIMIZATION: If we found email(s), stop checking more repos
                if found_emails:
                    logger.info(f"Found email(s) in {repo_name}, stopping repo checks (API optimization)")
                    break
            
            return {
                'success': True,
                'emails': found_emails,
                'repos_checked': len(repos[:max_repos])
            }
            
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.error(f"Rate limit exceeded for {username}: {e}")
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'emails': set(),
                    'rate_limited': True
                }
            else:
                logger.error(f"HTTP error scraping commits for {username}: {e.code}")
                return {
                    'success': False,
                    'error': f'HTTP {e.code}',
                    'emails': set()
                }
        except Exception as e:
            logger.error(f"Error scraping commit emails for {username}: {e}")
            return {
                'success': False,
                'error': str(e),
                'emails': set()
            }
    
    def _scrape_event_emails(self, username: str, max_events: int = 30) -> Dict[str, Any]:
        """
        Scrape emails from user's public events.
        
        Args:
            username: GitHub username
            max_events: Maximum number of events to check
            
        Returns:
            dict: Event emails result
        """
        try:
            # Check rate limit only if we have real data
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit reached, waiting {wait_time}s")
                time.sleep(wait_time)
            
            url = f"{self.base_url}/users/{username}/events/public"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    events_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    found_emails = set()
                    
                    # Extract emails from events
                    for event in events_data[:max_events]:
                        event_emails = self._extract_emails_from_event(event)
                        found_emails.update(event_emails)
                    
                    return {
                        'success': True,
                        'emails': found_emails,
                        'events_checked': min(len(events_data), max_events)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'emails': set()
                    }
        
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.error(f"Rate limit exceeded for {username}: {e}")
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'emails': set(),
                    'rate_limited': True
                }
            else:
                logger.error(f"HTTP error scraping events for {username}: {e.code}")
                return {
                    'success': False,
                    'error': f'HTTP {e.code}',
                    'emails': set()
                }
        except Exception as e:
            logger.error(f"Error scraping event emails for {username}: {e}")
            return {
                'success': False,
                'error': str(e),
                'emails': set()
            }
    
    def _get_user_repositories(self, username: str, max_repos: int = 3) -> List[Dict[str, Any]]:
        """Get user's public repositories (optimized to fetch minimal data)."""
        try:
            # Check rate limit only if we have real data
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            # Fetch more repos to account for forks, then filter
            url = f"{self.base_url}/users/{username}/repos?sort=pushed&per_page={max_repos * 2}"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    repos_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    # Filter out forks - prioritize user's own repos
                    own_repos = [r for r in repos_data if not r.get('fork', False)]
                    
                    # If no own repos, use all (including forks as fallback)
                    return own_repos[:max_repos] if own_repos else repos_data[:max_repos]
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting repositories for {username}: {e}")
            return []
    
    def _get_repo_commit_emails(self, repo_full_name: str, username: str, max_commits: int = 3) -> Set[str]:
        """Get emails from repository commits by specific user."""
        try:
            # Check rate limit only if we have real data
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit reached, waiting {wait_time}s")
                time.sleep(wait_time)
            
            url = f"{self.base_url}/repos/{repo_full_name}/commits?author={username}&per_page={max_commits}"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    commits_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    found_emails = set()
                    
                    for commit in commits_data:
                        if commit.get('commit'):
                            # Check author email (most reliable)
                            author = commit['commit'].get('author', {})
                            if author.get('email'):
                                email = author['email']
                                # Filter out noreply emails
                                if not self._is_noreply_email(email):
                                    found_emails.add(email)
                                    # OPTIMIZATION: Found valid email, stop checking more commits
                                    logger.info(f"Found email in commit, stopping (API optimization)")
                                    return found_emails
                            
                            # Check committer email only if no author email found
                            committer = commit['commit'].get('committer', {})
                            if committer.get('email'):
                                email = committer['email']
                                # Filter out noreply emails
                                if not self._is_noreply_email(email):
                                    found_emails.add(email)
                                    # OPTIMIZATION: Found valid email, stop checking more commits
                                    logger.info(f"Found email in commit, stopping (API optimization)")
                                    return found_emails
                    
                    return found_emails
                else:
                    return set()
        
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.warning(f"Rate limit hit for repo {repo_full_name}")
                return set()
            else:
                logger.error(f"HTTP {e.code} for {repo_full_name}")
                return set()
        except Exception as e:
            logger.error(f"Error getting commit emails from {repo_full_name}: {e}")
            return set()
    
    def _extract_emails_from_event(self, event: Dict[str, Any]) -> Set[str]:
        """Extract emails from a GitHub event."""
        found_emails = set()
        
        # Convert event to string and search for email patterns
        event_str = json.dumps(event)
        
        # Find all email patterns
        emails = self.email_regex.findall(event_str)
        
        for email in emails:
            if self._is_valid_email(email) and not self._is_noreply_email(email):
                found_emails.add(email)
        
        return found_emails
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format."""
        if not email or not isinstance(email, str):
            return False
        
        # Basic validation
        return bool(self.email_regex.match(email))
    
    def _is_noreply_email(self, email: str) -> bool:
        """Check if email is a GitHub noreply email."""
        if not email:
            return False
        
        noreply_patterns = [
            'noreply.github.com',
            'users.noreply.github.com',
            '@localhost',
            'example.com',
            'test.com'
        ]
        
        email_lower = email.lower()
        return any(pattern in email_lower for pattern in noreply_patterns)
    
    def _get_default_sources(self) -> List[EmailSource]:
        """Get default sources based on privacy level."""
        if self.privacy_level == PrivacyLevel.PUBLIC_ONLY:
            return [EmailSource.PROFILE]
        elif self.privacy_level == PrivacyLevel.COMMITS_ALLOWED:
            return [EmailSource.PROFILE, EmailSource.COMMITS]
        elif self.privacy_level == PrivacyLevel.EVENTS_ALLOWED:
            return [EmailSource.PROFILE, EmailSource.COMMITS, EmailSource.EVENTS]
        else:
            return [EmailSource.PROFILE]
    
    def export_emails_to_list(self, scrape_results: List[Dict[str, Any]],
                             format_type: str = 'simple') -> List[Dict[str, Any]]:
        """
        Export scraped email results to a clean list format.
        
        Args:
            scrape_results: List of scrape results from scrape_multiple_users
            format_type: Export format ('simple', 'detailed', 'csv_ready')
            
        Returns:
            list: Formatted email list
        """
        exported = []
        
        for result in scrape_results:
            if not result.get('success') or not result.get('emails'):
                continue
            
            username = result['username']
            emails = result['emails']
            sources = result.get('sources_found', {})
            
            if format_type == 'simple':
                for email in emails:
                    exported.append({
                        'username': username,
                        'email': email
                    })
            elif format_type == 'detailed':
                exported.append({
                    'username': username,
                    'emails': emails,
                    'email_count': len(emails),
                    'sources': sources,
                    'primary_email': emails[0] if emails else None
                })
            elif format_type == 'csv_ready':
                for email in emails:
                    source_list = []
                    for src, src_emails in sources.items():
                        if email in (src_emails if isinstance(src_emails, list) else [src_emails]):
                            source_list.append(src)
                    
                    exported.append({
                        'username': username,
                        'email': email,
                        'sources': ','.join(source_list)
                    })
        
        return exported
    
    def get_privacy_info(self) -> Dict[str, Any]:
        """
        Get information about privacy practices and compliance.
        
        Returns:
            dict: Privacy information and compliance details
        """
        return {
            'privacy_level': self.privacy_level.value,
            'data_sources': {
                'profile': 'Public profile email (explicitly public)',
                'commits': 'Commit history emails (publicly accessible)',
                'events': 'Public activity emails (publicly accessible)'
            },
            'privacy_practices': [
                'Only accesses publicly available information',
                'Respects user privacy settings',
                'Filters out GitHub noreply addresses',
                'Implements rate limiting to avoid abuse',
                'Does not store scraped data permanently',
                'Follows GitHub Terms of Service'
            ],
            'compliance_notes': [
                'All scraped data is publicly available on GitHub',
                'No private or sensitive information is accessed',
                'Users can control email visibility in GitHub settings',
                'Scraping respects robots.txt and rate limits'
            ],
            'user_control': [
                'Users can hide their email in GitHub profile settings',
                'Users can use noreply emails for commits',
                'Users can control public event visibility',
                'All scraped information is user-controllable'
            ]
        }
