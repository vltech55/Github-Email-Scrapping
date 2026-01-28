"""
GitHub Manager - Main class that combines all GitHub operations

This module provides the GitHubManager class that integrates:
- User API operations
- Invitation management  
- Email scraping
- Configuration management
"""

from typing import List, Dict, Any, Optional, Union
import logging

from .config import GitHubConfig, create_github_config
from .user_api import UserAPI, GitHubUserFetcher
from .invitations import InvitationManager, RepositoryPermission, OrganizationRole
from .email_scraper import EmailScraper, PrivacyLevel, EmailSource

logger = logging.getLogger(__name__)


class GitHubManager:
    """
    Main GitHub operations manager that integrates all functionality.
    """
    
    def __init__(self, token: Optional[str] = None, 
                 username: Optional[str] = None,
                 default_org: Optional[str] = None):
        """
        Initialize GitHub manager.
        
        Args:
            token: GitHub Personal Access Token
            username: GitHub username (optional)
            default_org: Default organization name (optional)
        """
        self.config = create_github_config(token, username, default_org)
        
        # Initialize sub-managers
        self.user_api = UserAPI(self.config.token)
        self.invitations = InvitationManager(self.config.token, self.config.username) if self.config.token else None
        self.email_scraper = EmailScraper(self.config.token, PrivacyLevel.COMMITS_ALLOWED)
        
        # Track operations for statistics
        self.stats = {
            'users_fetched': 0,
            'invitations_sent': 0,
            'emails_scraped': 0,
            'api_calls_made': 0
        }
    
    def get_users(self, usernames: List[str], 
                 include_repos: bool = False,
                 include_orgs: bool = False,
                 batch_size: int = 10) -> Dict[str, Any]:
        """
        Get detailed information for multiple GitHub users.
        
        Args:
            usernames: List of GitHub usernames
            include_repos: Include repository information
            include_orgs: Include organization information
            batch_size: Batch size for processing
            
        Returns:
            dict: User information results
        """
        logger.info(f"Fetching information for {len(usernames)} users")
        
        results = self.user_api.batch_get_users(usernames, batch_size)
        
        # Add additional information if requested
        if include_repos or include_orgs:
            for user_data in results['successful_users']:
                username = user_data['username']
                
                if include_repos:
                    user_data['repositories'] = self.user_api.fetcher.get_user_repositories(username)
                
                if include_orgs:
                    user_data['organizations'] = self.user_api.fetcher.get_user_organizations(username)
        
        self.stats['users_fetched'] += results['successful_count']
        return results
    
    def send_repo_invitations(self, owner: str, repo: str, 
                            usernames: List[str],
                            permission: Union[str, RepositoryPermission] = RepositoryPermission.PUSH,
                            batch_size: int = 5,
                            send_email_notification: bool = False) -> Dict[str, Any]:
        """
        Send repository invitations to multiple users.
        
        Args:
            owner: Repository owner
            repo: Repository name
            usernames: List of usernames to invite
            permission: Permission level to grant
            batch_size: Batch size for invitations
            send_email_notification: Whether to send custom email notifications
            
        Returns:
            dict: Invitation results
        """
        if not self.invitations:
            raise ValueError("GitHub token is required for sending invitations")
        
        logger.info(f"Sending repository invitations to {len(usernames)} users")
        
        results = self.invitations.bulk_repository_invitations(
            owner, repo, usernames, permission, batch_size
        )
        
        # Send custom email notifications if requested
        if send_email_notification:
            self._send_invitation_emails(
                results['successful_invitations'],
                'repository',
                f"{owner}/{repo}"
            )
        
        self.stats['invitations_sent'] += len(results['successful_invitations'])
        return results
    
    def send_org_invitations(self, org: str, usernames: List[str],
                           role: Union[str, OrganizationRole] = OrganizationRole.MEMBER,
                           batch_size: int = 3,
                           send_email_notification: bool = False) -> Dict[str, Any]:
        """
        Send organization invitations to multiple users.
        
        Args:
            org: Organization name
            usernames: List of usernames to invite
            role: Role to assign
            batch_size: Batch size for invitations
            send_email_notification: Whether to send custom email notifications
            
        Returns:
            dict: Invitation results
        """
        if not self.invitations:
            raise ValueError("GitHub token is required for sending invitations")
        
        logger.info(f"Sending organization invitations to {len(usernames)} users")
        
        results = self.invitations.bulk_organization_invitations(
            org, usernames, role, batch_size
        )
        
        # Send custom email notifications if requested
        if send_email_notification:
            self._send_invitation_emails(
                results['successful_invitations'],
                'organization',
                org
            )
        
        self.stats['invitations_sent'] += len(results['successful_invitations'])
        return results
    
    def send_repository_invitation(self, owner: str, repo: str, username: str,
                                   permission: Union[str, RepositoryPermission] = RepositoryPermission.PUSH) -> Dict[str, Any]:
        """
        Send repository invitation to a single user.
        
        Args:
            owner: Repository owner
            repo: Repository name
            username: GitHub username to invite
            permission: Permission level to grant
            
        Returns:
            dict: Invitation result
        """
        if not self.invitations:
            raise ValueError("GitHub token is required for sending invitations")
        
        logger.info(f"Sending repository invitation to {username}")
        
        result = self.invitations.send_repository_invitation(owner, repo, username, permission)
        
        if result['success']:
            self.stats['invitations_sent'] += 1
        
        return result
    
    def send_organization_invitation(self, org: str, username: str,
                                    role: Union[str, OrganizationRole] = OrganizationRole.MEMBER) -> Dict[str, Any]:
        """
        Send organization invitation to a single user.
        
        Args:
            org: Organization name
            username: GitHub username to invite
            role: Role to assign
            
        Returns:
            dict: Invitation result
        """
        if not self.invitations:
            raise ValueError("GitHub token is required for sending invitations")
        
        logger.info(f"Sending organization invitation to {username}")
        
        result = self.invitations.send_organization_invitation(org, username, role)
        
        if result['success']:
            self.stats['invitations_sent'] += 1
        
        return result
    
    def scrape_user_email(self, username: str,
                         privacy_level: Optional[PrivacyLevel] = None,
                         sources: Optional[List[EmailSource]] = None) -> Dict[str, Any]:
        """
        Scrape email addresses from a single GitHub user.
        
        Args:
            username: GitHub username
            privacy_level: Privacy level for scraping
            sources: Specific sources to check
            
        Returns:
            dict: Email scraping result
        """
        if privacy_level:
            self.email_scraper.privacy_level = privacy_level
        
        logger.info(f"Scraping emails for user: {username}")
        
        result = self.email_scraper.scrape_user_email(username, sources)
        
        if result.get('success') and result.get('emails'):
            self.stats['emails_scraped'] += 1
        
        return result
    
    def get_repository_status(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get current status of repository collaborators and pending invitations.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            dict: Repository status information
        """
        if not self.invitations:
            raise ValueError("GitHub token is required for repository status")
        
        collaborators = self.invitations.get_repository_collaborators(owner, repo)
        pending_invitations = self.invitations.get_pending_invitations(owner, repo)
        
        return {
            'repository': f"{owner}/{repo}",
            'collaborators': collaborators,
            'pending_invitations': pending_invitations,
            'summary': {
                'total_collaborators': len(collaborators),
                'pending_invitations': len(pending_invitations)
            }
        }
    
    def _send_invitation_emails(self, successful_invitations: List[Dict[str, Any]],
                              invitation_type: str, target_name: str,
                              scraped_emails: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Send custom email notifications for GitHub invitations.
        
        Args:
            successful_invitations: List of successful invitations
            invitation_type: Type of invitation ('repository' or 'organization')
            target_name: Name of repository or organization
            scraped_emails: Optional scraped email information
            
        Returns:
            dict: Email sending results
        """
        try:
            # Try to import and use email module
            from email_module import EmailManager
            
            email_manager = EmailManager.from_environment()
            
            if not email_manager.accounts:
                return {
                    'success': False,
                    'error': 'No email accounts configured',
                    'emails_sent': 0
                }
            
            emails_sent = 0
            failed_emails = []
            
            # Create email-to-username mapping from scraped data
            email_map = {}
            if scraped_emails:
                for user_email in scraped_emails:
                    username = user_email['username']
                    for email in user_email['emails']:
                        email_map[email] = username
            
            # Send emails
            for invitation in successful_invitations:
                username = invitation['username']
                
                # Try to find email for this user
                user_email = None
                for email, mapped_username in email_map.items():
                    if mapped_username == username:
                        user_email = email
                        break
                
                if not user_email:
                    logger.warning(f"No email found for user {username}, skipping email notification")
                    continue
                
                # Send invitation email
                subject = f"Invitation to {invitation_type}: {target_name}"
                
                body = f"""
Hello {username},

You have been invited to collaborate on the {invitation_type}: {target_name}

Please check your GitHub notifications to accept the invitation.

Best regards,
Project Team
                """.strip()
                
                result = email_manager.send_email(
                    to_email=user_email,
                    subject=subject,
                    body=body
                )
                
                if result['success']:
                    emails_sent += 1
                else:
                    failed_emails.append({
                        'username': username,
                        'email': user_email,
                        'error': result['message']
                    })
            
            return {
                'success': True,
                'emails_sent': emails_sent,
                'failed_emails': failed_emails,
                'total_invitations': len(successful_invitations)
            }
            
        except ImportError:
            logger.warning("email_module not available for sending notifications")
            return {
                'success': False,
                'error': 'email_module not available',
                'emails_sent': 0
            }
        except Exception as e:
            logger.error(f"Error sending invitation emails: {e}")
            return {
                'success': False,
                'error': str(e),
                'emails_sent': 0
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about GitHub operations performed.
        
        Returns:
            dict: Operation statistics
        """
        return {
            'operations_performed': self.stats.copy(),
            'rate_limit_status': self.user_api.fetcher.get_rate_limit_status(),
            'configuration': {
                'has_token': self.config.token is not None,
                'has_username': self.config.username is not None,
                'has_default_org': self.config.default_org is not None
            }
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test GitHub API connection and permissions.
        
        Returns:
            dict: Connection test results
        """
        results = {
            'api_connection': False,
            'token_valid': False,
            'user_access': False,
            'repo_access': False,
            'org_access': False,
            'errors': []
        }
        
        try:
            # Test basic API connection
            test_user = self.user_api.get_user_info('octocat')
            if test_user['success']:
                results['api_connection'] = True
                results['token_valid'] = True
            
            # Test user access (if we have our own username)
            if self.config.username:
                own_user = self.user_api.get_user_info(self.config.username)
                if own_user['success']:
                    results['user_access'] = True
            
            # Test repository access (try to get rate limit info)
            rate_limit_status = self.user_api.fetcher.get_rate_limit_status()
            if rate_limit_status:
                results['repo_access'] = True
            
            # Test organization access would require specific org operations
            # which we skip in basic connection test
            
        except Exception as e:
            results['errors'].append(str(e))
        
        return results
