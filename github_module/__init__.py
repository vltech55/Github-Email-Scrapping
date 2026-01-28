"""
GitHub Module - Professional GitHub Automation Package

A comprehensive GitHub automation module with support for:
- User account name fetching via GitHub API
- Project/repository invitation management
- Email scraping from GitHub profiles
- Integration with email module for notifications

Usage:
    from github_module import GitHubManager, UserAPI, InvitationManager
    
    # Initialize with GitHub token
    github = GitHubManager('your_github_token')
    
    # Get user information
    users = github.get_users(['username1', 'username2'])
    
    # Send repository invitations
    github.send_repo_invitations('my-repo', ['user1', 'user2'])
    
    # Scrape emails from profiles
    emails = github.scrape_user_emails(['user1', 'user2'])
"""

__version__ = "1.0.0"
__author__ = "Your Name"

# Import main classes for easy access
from .user_api import UserAPI, GitHubUserFetcher
from .invitations import InvitationManager, InvitationType
from .email_scraper import EmailScraper, EmailSource
from .config import GitHubConfig, create_github_config
from .utils import GitHubRateLimit, validate_username, batch_process
from .core import GitHubManager

# Define what gets imported with "from github_module import *"
__all__ = [
    'GitHubManager',
    'UserAPI', 
    'GitHubUserFetcher',
    'InvitationManager',
    'InvitationType',
    'EmailScraper',
    'EmailSource',
    'GitHubConfig',
    'create_github_config',
    'GitHubRateLimit',
    'validate_username',
    'batch_process'
]

# Quick access functions
def create_github_manager(token: str = None):
    """
    Create a GitHubManager instance with token from environment or parameter.
    
    Args:
        token: Optional GitHub personal access token
        
    Returns:
        GitHubManager: Configured GitHub manager
    """
    return GitHubManager(token)

def get_github_features():
    """
    List all GitHub module features and their descriptions.
    
    Returns:
        dict: Feature descriptions and capabilities
    """
    return {
        'user_api': {
            'description': 'Fetch GitHub user account information via API',
            'capabilities': [
                'Get user profiles and metadata',
                'Search users by criteria',
                'Batch user information retrieval',
                'Rate limiting and error handling'
            ],
            'authentication': 'GitHub Personal Access Token (optional for public data)'
        },
        'invitations': {
            'description': 'Send invitations to GitHub repositories and organizations',
            'capabilities': [
                'Repository collaborator invitations',
                'Organization member invitations',
                'Bulk invitation sending',
                'Invitation status tracking'
            ],
            'authentication': 'GitHub Personal Access Token (required with repo/org permissions)'
        },
        'email_scraper': {
            'description': 'Extract email addresses from GitHub user profiles',
            'capabilities': [
                'Profile email extraction',
                'Commit history email mining',
                'Public event email discovery',
                'Privacy-compliant scraping'
            ],
            'authentication': 'GitHub Personal Access Token (recommended for better rate limits)'
        },
        'integration': {
            'description': 'Integration with email module for notifications',
            'capabilities': [
                'Send invitation emails via custom SMTP',
                'Automated follow-up messages',
                'Template-based communications',
                'Multi-account email support'
            ],
            'requirements': 'email_module package'
        }
    }

def get_setup_requirements():
    """
    Get setup requirements and instructions for GitHub module.
    
    Returns:
        dict: Setup instructions and requirements
    """
    return {
        'github_token': {
            'required': True,
            'description': 'GitHub Personal Access Token for API access',
            'scopes_needed': [
                'public_repo - for repository invitations',
                'read:user - for user profile access',
                'admin:org - for organization invitations (if needed)',
                'user:email - for email access (if available)'
            ],
            'setup_url': 'https://github.com/settings/tokens'
        },
        'environment_variables': {
            'GITHUB_TOKEN': 'Your GitHub Personal Access Token',
            'GITHUB_USERNAME': 'Your GitHub username (optional)',
            'GITHUB_ORG': 'Default organization name (optional)'
        },
        'rate_limits': {
            'authenticated': '5000 requests per hour',
            'unauthenticated': '60 requests per hour',
            'search_api': '30 requests per minute',
            'note': 'Module includes automatic rate limiting and backoff'
        },
        'privacy_notice': [
            'Email scraping respects user privacy settings',
            'Only publicly available information is accessed',
            'Follows GitHub Terms of Service',
            'Implements respectful scraping practices'
        ]
    }
