"""
Configuration management for GitHub module.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class GitHubConfig:
    """Configuration for GitHub API operations."""
    token: Optional[str] = None
    username: Optional[str] = None
    default_org: Optional[str] = None
    rate_limit_buffer: int = 100  # Buffer before hitting rate limit
    request_timeout: int = 30
    max_retries: int = 3
    
    def __post_init__(self):
        """Load configuration from environment if not provided."""
        if self.token is None:
            self.token = os.getenv('GITHUB_TOKEN')
        if self.username is None:
            self.username = os.getenv('GITHUB_USERNAME')
        if self.default_org is None:
            self.default_org = os.getenv('GITHUB_ORG')
    
    def is_valid(self) -> bool:
        """Check if configuration is valid for API operations."""
        return self.token is not None and len(self.token) > 0
    
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for GitHub API requests."""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Module-Python'
        }
        
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        
        return headers


def create_github_config(token: Optional[str] = None,
                        username: Optional[str] = None,
                        default_org: Optional[str] = None) -> GitHubConfig:
    """
    Create a GitHub configuration instance.
    
    Args:
        token: GitHub Personal Access Token
        username: GitHub username
        default_org: Default organization name
        
    Returns:
        GitHubConfig: Configured instance
    """
    return GitHubConfig(
        token=token,
        username=username,
        default_org=default_org
    )


def validate_github_setup() -> Dict[str, Any]:
    """
    Validate GitHub module setup and configuration.
    
    Returns:
        dict: Validation results and setup information
    """
    config = GitHubConfig()
    
    results = {
        'valid': config.is_valid(),
        'token_present': config.token is not None,
        'username_present': config.username is not None,
        'org_present': config.default_org is not None,
        'warnings': [],
        'errors': [],
        'setup_instructions': []
    }
    
    # Check token
    if not config.token:
        results['errors'].append('No GitHub token found')
        results['setup_instructions'].extend([
            '1. Go to https://github.com/settings/tokens',
            '2. Generate a new Personal Access Token',
            '3. Select appropriate scopes:',
            '   - public_repo (for repository operations)',
            '   - read:user (for user information)',
            '   - admin:org (for organization invitations)',
            '4. Set GITHUB_TOKEN environment variable'
        ])
    else:
        # Basic token validation
        if len(config.token) < 20:
            results['warnings'].append('Token seems too short - verify it is correct')
        
        if config.token.startswith('ghp_'):
            results['token_type'] = 'Personal Access Token (Fine-grained)'
        elif config.token.startswith('github_pat_'):
            results['token_type'] = 'Personal Access Token (Classic)'
        else:
            results['warnings'].append('Token format not recognized')
    
    # Check optional settings
    if not config.username:
        results['warnings'].append('No GitHub username set (optional but recommended)')
    
    if not config.default_org:
        results['warnings'].append('No default organization set (optional)')
    
    return results


def get_github_scopes_info() -> Dict[str, Any]:
    """
    Get information about GitHub token scopes needed for different operations.
    
    Returns:
        dict: Scope information and requirements
    """
    return {
        'user_operations': {
            'scopes': ['read:user', 'user:email'],
            'description': 'Read user profile information and public email',
            'required_for': ['user_api.py operations', 'email scraping']
        },
        'repository_operations': {
            'scopes': ['public_repo', 'repo'],
            'description': 'Access and manage repositories',
            'required_for': ['repository invitations', 'collaborator management'],
            'note': 'Use public_repo for public repos only, repo for private repos'
        },
        'organization_operations': {
            'scopes': ['admin:org', 'read:org'],
            'description': 'Manage organization members and settings',
            'required_for': ['organization invitations', 'member management'],
            'note': 'admin:org required for invitations, read:org for listing'
        },
        'minimal_setup': {
            'scopes': ['public_repo', 'read:user'],
            'description': 'Minimal scopes for basic functionality',
            'sufficient_for': ['user information', 'public repo invitations', 'email scraping']
        },
        'full_setup': {
            'scopes': ['repo', 'admin:org', 'user:email', 'read:user'],
            'description': 'Full scopes for all functionality',
            'sufficient_for': ['all module features']
        }
    }
