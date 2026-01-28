"""
GitHub Invitations - Send invitations to repositories and organizations

This module provides functionality to:
- Send repository collaborator invitations
- Send organization member invitations
- Manage bulk invitations with proper rate limiting
- Track invitation status and responses
"""

import urllib.request
import urllib.parse
import json
import time
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import logging
from datetime import datetime

from .utils import GitHubRateLimit, validate_username, batch_process

logger = logging.getLogger(__name__)


class InvitationType(Enum):
    """Types of GitHub invitations."""
    REPOSITORY_COLLABORATOR = "repo_collaborator"
    ORGANIZATION_MEMBER = "org_member"
    ORGANIZATION_OUTSIDE_COLLABORATOR = "org_outside_collaborator"


class RepositoryPermission(Enum):
    """Repository permission levels."""
    PULL = "pull"        # Can pull, but not push to or administer this repository
    PUSH = "push"        # Can pull and push, but not administer this repository  
    ADMIN = "admin"      # Can pull, push and administer this repository
    MAINTAIN = "maintain" # Can manage the repository without access to sensitive/destructive actions
    TRIAGE = "triage"    # Can manage issues and pull requests without write access


class OrganizationRole(Enum):
    """Organization role levels."""
    MEMBER = "member"    # Regular organization member
    ADMIN = "admin"      # Organization administrator


class InvitationManager:
    """Manages GitHub invitations for repositories and organizations."""
    
    def __init__(self, token: str, default_username: Optional[str] = None):
        """
        Initialize invitation manager.
        
        Args:
            token: GitHub Personal Access Token with appropriate permissions
            default_username: Default GitHub username for API operations
        """
        if not token:
            raise ValueError("GitHub token is required for invitation management")
        
        self.token = token
        self.default_username = default_username
        self.base_url = "https://api.github.com"
        self.rate_limit = GitHubRateLimit(True)
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Module-Python'
        }
    
    def send_repository_invitation(self, owner: str, repo: str, username: str,
                                 permission: Union[str, RepositoryPermission] = RepositoryPermission.PUSH) -> Dict[str, Any]:
        """
        Send a repository collaborator invitation.
        
        Args:
            owner: Repository owner username or organization name
            repo: Repository name
            username: Username to invite
            permission: Permission level to grant
            
        Returns:
            dict: Invitation result with success status and details
        """
        if not validate_username(username):
            return {
                'success': False,
                'error': f'Invalid username: {username}',
                'username': username,
                'repository': f'{owner}/{repo}'
            }
        
        try:
            # Check rate limit
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                logger.warning(f"Rate limit hit, waiting {wait_time} seconds")
                time.sleep(wait_time)
            
            # Prepare invitation data
            permission_str = permission.value if isinstance(permission, RepositoryPermission) else permission
            
            invitation_data = {
                'permission': permission_str
            }
            
            # Make API request
            url = f"{self.base_url}/repos/{owner}/{repo}/collaborators/{username}"
            data = json.dumps(invitation_data).encode('utf-8')
            
            request = urllib.request.Request(url, data=data, headers=self.headers)
            request.get_method = lambda: 'PUT'
            
            with urllib.request.urlopen(request) as response:
                self.rate_limit.update_from_headers(response.headers)
                
                if response.status == 201:
                    # Invitation sent successfully
                    return {
                        'success': True,
                        'username': username,
                        'repository': f'{owner}/{repo}',
                        'permission': permission_str,
                        'message': 'Repository invitation sent successfully',
                        'invitation_type': InvitationType.REPOSITORY_COLLABORATOR.value
                    }
                elif response.status == 204:
                    # User is already a collaborator
                    return {
                        'success': True,
                        'username': username,
                        'repository': f'{owner}/{repo}',
                        'permission': permission_str,
                        'message': 'User is already a collaborator',
                        'invitation_type': InvitationType.REPOSITORY_COLLABORATOR.value,
                        'already_member': True
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'username': username,
                        'repository': f'{owner}/{repo}'
                    }
                    
        except urllib.error.HTTPError as e:
            error_message = f'HTTP {e.code}: {e.reason}'
            
            if e.code == 403:
                error_message = 'Permission denied - check token permissions and repository access'
            elif e.code == 404:
                error_message = 'Repository not found or user does not exist'
            elif e.code == 422:
                # Try to get more specific error information
                try:
                    error_data = json.loads(e.read().decode())
                    error_message = error_data.get('message', 'Validation failed')
                except:
                    error_message = 'Validation failed - invalid request data'
            
            return {
                'success': False,
                'error': error_message,
                'username': username,
                'repository': f'{owner}/{repo}'
            }
        except Exception as e:
            logger.error(f"Error sending repository invitation: {e}")
            return {
                'success': False,
                'error': str(e),
                'username': username,
                'repository': f'{owner}/{repo}'
            }
    
    def send_organization_invitation(self, org: str, username: str,
                                   role: Union[str, OrganizationRole] = OrganizationRole.MEMBER,
                                   team_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Send an organization member invitation.
        
        Args:
            org: Organization name
            username: Username to invite
            role: Role to assign ('member' or 'admin')
            team_ids: Optional list of team IDs to add user to
            
        Returns:
            dict: Invitation result with success status and details
        """
        if not validate_username(username):
            return {
                'success': False,
                'error': f'Invalid username: {username}',
                'username': username,
                'organization': org
            }
        
        try:
            # Check rate limit
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            # Prepare invitation data
            role_str = role.value if isinstance(role, OrganizationRole) else role
            
            invitation_data = {
                'role': role_str
            }
            
            if team_ids:
                invitation_data['team_ids'] = team_ids
            
            # Make API request
            url = f"{self.base_url}/orgs/{org}/invitations"
            data = json.dumps(invitation_data).encode('utf-8')
            
            # First, try to invite via email/username
            invitation_data['invitee_id'] = None
            
            # We need to get the user ID first
            user_result = self._get_user_id(username)
            if user_result['success']:
                invitation_data['invitee_id'] = user_result['user_id']
            else:
                return {
                    'success': False,
                    'error': f"Could not find user {username}: {user_result['error']}",
                    'username': username,
                    'organization': org
                }
            
            data = json.dumps(invitation_data).encode('utf-8')
            request = urllib.request.Request(url, data=data, headers=self.headers)
            request.get_method = lambda: 'POST'
            
            with urllib.request.urlopen(request) as response:
                self.rate_limit.update_from_headers(response.headers)
                
                if response.status == 201:
                    response_data = json.loads(response.read().decode())
                    return {
                        'success': True,
                        'username': username,
                        'organization': org,
                        'role': role_str,
                        'message': 'Organization invitation sent successfully',
                        'invitation_id': response_data.get('id'),
                        'invitation_type': InvitationType.ORGANIZATION_MEMBER.value
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}',
                        'username': username,
                        'organization': org
                    }
                    
        except urllib.error.HTTPError as e:
            error_message = f'HTTP {e.code}: {e.reason}'
            
            if e.code == 403:
                error_message = 'Permission denied - check token permissions and organization access'
            elif e.code == 404:
                error_message = 'Organization not found'
            elif e.code == 422:
                try:
                    error_data = json.loads(e.read().decode())
                    error_message = error_data.get('message', 'Validation failed')
                except:
                    error_message = 'Validation failed - user may already be a member'
            
            return {
                'success': False,
                'error': error_message,
                'username': username,
                'organization': org
            }
        except Exception as e:
            logger.error(f"Error sending organization invitation: {e}")
            return {
                'success': False,
                'error': str(e),
                'username': username,
                'organization': org
            }
    
    def bulk_repository_invitations(self, owner: str, repo: str, 
                                  usernames: List[str],
                                  permission: Union[str, RepositoryPermission] = RepositoryPermission.PUSH,
                                  batch_size: int = 5,
                                  delay: float = 2.0) -> Dict[str, Any]:
        """
        Send repository invitations to multiple users in batches.
        
        Args:
            owner: Repository owner
            repo: Repository name
            usernames: List of usernames to invite
            permission: Permission level for all invitations
            batch_size: Number of invitations per batch
            delay: Delay between batches in seconds
            
        Returns:
            dict: Bulk invitation results
        """
        logger.info(f"Sending bulk repository invitations to {len(usernames)} users")
        
        successful_invitations = []
        failed_invitations = []
        already_members = []
        
        # Process in batches
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(usernames) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} invitations")
            
            for username in batch:
                result = self.send_repository_invitation(owner, repo, username, permission)
                
                if result['success']:
                    if result.get('already_member'):
                        already_members.append(result)
                    else:
                        successful_invitations.append(result)
                else:
                    failed_invitations.append(result)
                
                # Small delay between individual requests
                time.sleep(0.5)
            
            # Delay between batches
            if i + batch_size < len(usernames):
                logger.info(f"Waiting {delay}s before next batch...")
                time.sleep(delay)
        
        # Summary
        total_sent = len(successful_invitations)
        total_already_members = len(already_members)
        total_failed = len(failed_invitations)
        
        logger.info(f"Bulk invitations complete: {total_sent} sent, {total_already_members} already members, {total_failed} failed")
        
        return {
            'repository': f'{owner}/{repo}',
            'total_requested': len(usernames),
            'successful_invitations': successful_invitations,
            'already_members': already_members,
            'failed_invitations': failed_invitations,
            'summary': {
                'sent': total_sent,
                'already_members': total_already_members,
                'failed': total_failed,
                'success_rate': (total_sent / len(usernames)) * 100 if usernames else 0
            }
        }
    
    def bulk_organization_invitations(self, org: str, usernames: List[str],
                                    role: Union[str, OrganizationRole] = OrganizationRole.MEMBER,
                                    batch_size: int = 3,
                                    delay: float = 3.0) -> Dict[str, Any]:
        """
        Send organization invitations to multiple users in batches.
        
        Args:
            org: Organization name
            usernames: List of usernames to invite
            role: Role to assign to all users
            batch_size: Number of invitations per batch (smaller for orgs)
            delay: Delay between batches in seconds
            
        Returns:
            dict: Bulk invitation results
        """
        logger.info(f"Sending bulk organization invitations to {len(usernames)} users")
        
        successful_invitations = []
        failed_invitations = []
        
        # Process in smaller batches for organization invitations
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(usernames) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} invitations")
            
            for username in batch:
                result = self.send_organization_invitation(org, username, role)
                
                if result['success']:
                    successful_invitations.append(result)
                else:
                    failed_invitations.append(result)
                
                # Longer delay between org invitations
                time.sleep(1.0)
            
            # Longer delay between batches for org invitations
            if i + batch_size < len(usernames):
                logger.info(f"Waiting {delay}s before next batch...")
                time.sleep(delay)
        
        # Summary
        total_sent = len(successful_invitations)
        total_failed = len(failed_invitations)
        
        logger.info(f"Bulk org invitations complete: {total_sent} sent, {total_failed} failed")
        
        return {
            'organization': org,
            'total_requested': len(usernames),
            'successful_invitations': successful_invitations,
            'failed_invitations': failed_invitations,
            'summary': {
                'sent': total_sent,
                'failed': total_failed,
                'success_rate': (total_sent / len(usernames)) * 100 if usernames else 0
            }
        }
    
    def get_repository_collaborators(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Get current repository collaborators.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            list: List of current collaborators
        """
        try:
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            url = f"{self.base_url}/repos/{owner}/{repo}/collaborators"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    collaborators_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    return [
                        {
                            'username': collab['login'],
                            'id': collab['id'],
                            'avatar_url': collab['avatar_url'],
                            'html_url': collab['html_url'],
                            'type': collab['type']
                        }
                        for collab in collaborators_data
                    ]
                else:
                    logger.warning(f"Failed to get collaborators: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching collaborators: {e}")
            return []
    
    def get_pending_invitations(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Get pending repository invitations.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            list: List of pending invitations
        """
        try:
            if not self.rate_limit.can_make_request():
                wait_time = self.rate_limit.get_wait_time()
                time.sleep(wait_time)
            
            url = f"{self.base_url}/repos/{owner}/{repo}/invitations"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    invitations_data = json.loads(response.read().decode())
                    self.rate_limit.update_from_headers(response.headers)
                    
                    return [
                        {
                            'id': inv['id'],
                            'username': inv['invitee']['login'],
                            'permission': inv['permissions'],
                            'created_at': inv['created_at'],
                            'url': inv['url']
                        }
                        for inv in invitations_data
                    ]
                else:
                    logger.warning(f"Failed to get pending invitations: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching pending invitations: {e}")
            return []
    
    def _get_user_id(self, username: str) -> Dict[str, Any]:
        """
        Get GitHub user ID from username.
        
        Args:
            username: GitHub username
            
        Returns:
            dict: Result with user ID or error
        """
        try:
            url = f"{self.base_url}/users/{username}"
            request = urllib.request.Request(url, headers=self.headers)
            
            with urllib.request.urlopen(request) as response:
                if response.status == 200:
                    user_data = json.loads(response.read().decode())
                    return {
                        'success': True,
                        'user_id': user_data['id'],
                        'username': username
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_invitation(self, invitation_url: str) -> Dict[str, Any]:
        """
        Cancel a pending invitation.
        
        Args:
            invitation_url: Full URL of the invitation to cancel
            
        Returns:
            dict: Cancellation result
        """
        try:
            request = urllib.request.Request(invitation_url, headers=self.headers)
            request.get_method = lambda: 'DELETE'
            
            with urllib.request.urlopen(request) as response:
                if response.status == 204:
                    return {
                        'success': True,
                        'message': 'Invitation cancelled successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response.reason}'
                    }
                    
        except Exception as e:
            logger.error(f"Error cancelling invitation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
