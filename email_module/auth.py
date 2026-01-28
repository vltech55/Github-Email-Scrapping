"""
Authentication methods for email sending - alternatives to Gmail app passwords.
"""

import smtplib
import base64
import json
from typing import Dict, Any, Optional
import logging

from .config import EmailConfig

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages different authentication methods for email sending."""
    
    def __init__(self, config: EmailConfig):
        """
        Initialize with email configuration.
        
        Args:
            config: EmailConfig instance
        """
        self.config = config
    
    def authenticate(self, server: smtplib.SMTP) -> Dict[str, Any]:
        """
        Authenticate with the SMTP server using the configured method.
        
        Args:
            server: SMTP server instance
            
        Returns:
            dict: Authentication result with success status and details
        """
        if self.config.auth_method == "app_password":
            return self._auth_app_password(server)
        elif self.config.auth_method == "oauth2":
            return self._auth_oauth2(server)
        else:
            return {
                'success': False,
                'message': f"Unsupported authentication method: {self.config.auth_method}",
                'auth_method': self.config.auth_method
            }
    
    def _auth_app_password(self, server: smtplib.SMTP) -> Dict[str, Any]:
        """Authenticate using app password (traditional method)."""
        try:
            server.login(self.config.email_address, self.config.password)
            return {
                'success': True,
                'message': 'App password authentication successful',
                'auth_method': 'app_password'
            }
        except smtplib.SMTPAuthenticationError as e:
            return {
                'success': False,
                'message': f'App password authentication failed: {str(e)}',
                'auth_method': 'app_password',
                'suggestions': [
                    'Verify your app password is correct',
                    'Ensure 2-Factor Authentication is enabled',
                    'Generate a new app password if needed',
                    'Check that the email address is correct'
                ]
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Authentication error: {str(e)}',
                'auth_method': 'app_password'
            }
    
    def _auth_oauth2(self, server: smtplib.SMTP) -> Dict[str, Any]:
        """Authenticate using OAuth2."""
        if not all([self.config.client_id, self.config.client_secret, self.config.refresh_token]):
            return {
                'success': False,
                'message': 'OAuth2 requires client_id, client_secret, and refresh_token',
                'auth_method': 'oauth2',
                'setup_required': True
            }
        
        try:
            # Get access token from refresh token
            oauth_helper = OAuth2Helper(
                self.config.client_id,
                self.config.client_secret,
                self.config.refresh_token
            )
            
            access_token = oauth_helper.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to obtain OAuth2 access token',
                    'auth_method': 'oauth2'
                }
            
            # Create OAuth2 string
            oauth_string = oauth_helper.generate_oauth_string(
                self.config.email_address, 
                access_token
            )
            
            # Authenticate with OAuth2
            server.docmd('AUTH', 'XOAUTH2 ' + oauth_string)
            
            return {
                'success': True,
                'message': 'OAuth2 authentication successful',
                'auth_method': 'oauth2'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'OAuth2 authentication failed: {str(e)}',
                'auth_method': 'oauth2',
                'suggestions': [
                    'Verify your OAuth2 credentials are correct',
                    'Check if refresh token has expired',
                    'Ensure OAuth2 app has Gmail API access',
                    'Consider re-authorizing your application'
                ]
            }


class OAuth2Helper:
    """Helper class for OAuth2 authentication with Gmail."""
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        """
        Initialize OAuth2 helper.
        
        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret  
            refresh_token: OAuth2 refresh token
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
    
    def get_access_token(self) -> Optional[str]:
        """
        Get access token using refresh token.
        
        Returns:
            str: Access token if successful, None otherwise
        """
        try:
            import urllib.request
            import urllib.parse
            
            # Token endpoint
            token_url = 'https://oauth2.googleapis.com/token'
            
            # Request data
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            # Encode data
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            
            # Make request
            request = urllib.request.Request(token_url, encoded_data)
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode())
                return result.get('access_token')
                
        except Exception as e:
            logger.error(f"Failed to get OAuth2 access token: {e}")
            return None
    
    def generate_oauth_string(self, email: str, access_token: str) -> str:
        """
        Generate OAuth2 authentication string for SMTP.
        
        Args:
            email: Email address
            access_token: OAuth2 access token
            
        Returns:
            str: Base64 encoded OAuth2 string
        """
        auth_string = f'user={email}\x01auth=Bearer {access_token}\x01\x01'
        return base64.b64encode(auth_string.encode()).decode()
    
    @staticmethod
    def get_setup_instructions() -> Dict[str, Any]:
        """
        Get instructions for setting up OAuth2 authentication.
        
        Returns:
            dict: Setup instructions and requirements
        """
        return {
            'title': 'OAuth2 Setup for Gmail',
            'overview': 'OAuth2 is more secure than app passwords but requires initial setup.',
            'steps': [
                {
                    'step': 1,
                    'title': 'Create Google Cloud Project',
                    'description': 'Go to Google Cloud Console and create a new project',
                    'url': 'https://console.cloud.google.com/'
                },
                {
                    'step': 2,
                    'title': 'Enable Gmail API',
                    'description': 'Enable the Gmail API for your project',
                    'details': 'Go to APIs & Services > Library > Search for Gmail API > Enable'
                },
                {
                    'step': 3,
                    'title': 'Create OAuth2 Credentials',
                    'description': 'Create OAuth2 client ID and secret',
                    'details': 'Go to APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID'
                },
                {
                    'step': 4,
                    'title': 'Configure OAuth Consent',
                    'description': 'Set up OAuth consent screen with required scopes',
                    'required_scopes': [
                        'https://www.googleapis.com/auth/gmail.send',
                        'https://www.googleapis.com/auth/gmail.compose'
                    ]
                },
                {
                    'step': 5,
                    'title': 'Get Refresh Token',
                    'description': 'Run authorization flow to get refresh token',
                    'note': 'This is a one-time process per user'
                }
            ],
            'environment_variables': {
                'CLIENT_ID': 'Your OAuth2 client ID',
                'CLIENT_SECRET': 'Your OAuth2 client secret',  
                'REFRESH_TOKEN': 'Your OAuth2 refresh token'
            },
            'advantages': [
                'More secure than app passwords',
                'Can be revoked granularly',
                'Supports fine-grained permissions',
                'Industry standard authentication'
            ],
            'disadvantages': [
                'Complex initial setup',
                'Requires Google Cloud project',
                'More moving parts to maintain',
                'Refresh tokens can expire'
            ]
        }


def get_auth_alternatives() -> Dict[str, Any]:
    """
    Get information about alternatives to Gmail app passwords.
    
    Returns:
        dict: Information about different authentication methods and providers
    """
    return {
        'gmail_alternatives': {
            'oauth2': {
                'security': 'High',
                'complexity': 'High',
                'description': 'Industry standard OAuth2 flow',
                'setup_function': OAuth2Helper.get_setup_instructions,
                'recommended_for': 'Production applications, security-conscious users'
            },
            'app_passwords': {
                'security': 'Medium',
                'complexity': 'Low', 
                'description': 'Gmail-specific app passwords (current default)',
                'recommended_for': 'Quick setup, personal projects, testing'
            }
        },
        'alternative_providers': {
            'outlook_com': {
                'provider': 'Microsoft Outlook.com',
                'smtp_server': 'smtp-mail.outlook.com',
                'smtp_port': 587,
                'auth_methods': ['app_password', 'oauth2'],
                'notes': 'Modern authentication preferred over basic auth',
                'setup_url': 'https://support.microsoft.com/office/pop-imap-smtp-settings-8361e398-8af4-4e97-b147-6c6c4ac95353'
            },
            'yahoo': {
                'provider': 'Yahoo Mail',
                'smtp_server': 'smtp.mail.yahoo.com', 
                'smtp_port': 587,
                'auth_methods': ['app_password'],
                'notes': 'Requires app password (called "app-specific password")',
                'setup_url': 'https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html'
            },
            'icloud': {
                'provider': 'Apple iCloud',
                'smtp_server': 'smtp.mail.me.com',
                'smtp_port': 587,
                'auth_methods': ['app_password'],
                'notes': 'Requires app-specific password with 2FA enabled',
                'setup_url': 'https://support.apple.com/102654'
            },
            'custom_smtp': {
                'provider': 'Custom SMTP Server',
                'smtp_server': 'your.server.com',
                'smtp_port': 587,
                'auth_methods': ['password', 'oauth2', 'none'],
                'notes': 'Use your organization or hosting provider SMTP settings',
                'recommended_for': 'Corporate environments, self-hosted solutions'
            }
        },
        'security_considerations': {
            'app_passwords': [
                'Enable 2-Factor Authentication first',
                'Store passwords securely (use environment variables)', 
                'Rotate passwords periodically',
                'Revoke unused app passwords',
                'Monitor for suspicious activity'
            ],
            'oauth2': [
                'Keep client secrets secure',
                'Use HTTPS for redirect URLs',
                'Implement proper token storage',
                'Handle token refresh gracefully',
                'Monitor API usage and quotas'
            ],
            'general': [
                'Never hardcode credentials in source code',
                'Use secure communication (TLS/SSL)',
                'Implement proper error handling',
                'Log authentication attempts',
                'Consider rate limiting'
            ]
        },
        'choosing_method': {
            'use_app_passwords_when': [
                'Quick prototyping or testing',
                'Personal projects',
                'Simple automation scripts',
                'Learning email integration'
            ],
            'use_oauth2_when': [
                'Production applications',
                'Multi-user systems',
                'Commercial software',
                'High security requirements',
                'Long-term maintenance expected'
            ],
            'use_alternative_providers_when': [
                'Gmail not available in your region',
                'Corporate email policies',
                'Existing infrastructure',
                'Cost considerations',
                'Specific feature requirements'
            ]
        }
    }


def print_auth_guide():
    """Print a comprehensive guide for email authentication options."""
    alternatives = get_auth_alternatives()
    
    print("=" * 70)
    print("EMAIL AUTHENTICATION GUIDE")
    print("=" * 70)
    
    print("\n[SECURITY] GMAIL AUTHENTICATION OPTIONS:")
    for method, info in alternatives['gmail_alternatives'].items():
        print(f"\n[EMAIL] {method.upper().replace('_', ' ')}")
        print(f"   Security: {info['security']}")
        print(f"   Complexity: {info['complexity']}")
        print(f"   Description: {info['description']}")
        print(f"   Best for: {info['recommended_for']}")
    
    print("\n[PROVIDERS] ALTERNATIVE EMAIL PROVIDERS:")
    for provider, info in alternatives['alternative_providers'].items():
        if provider != 'custom_smtp':
            print(f"\n[MAIL] {info['provider']}")
            print(f"   SMTP: {info['smtp_server']}:{info['smtp_port']}")
            print(f"   Auth: {', '.join(info['auth_methods'])}")
            print(f"   Notes: {info['notes']}")
    
    print("\n[SECURITY] SECURITY BEST PRACTICES:")
    print("   * Use environment variables for credentials")
    print("   * Enable 2-Factor Authentication")
    print("   * Rotate passwords/tokens regularly")
    print("   * Monitor for suspicious activity")
    print("   * Use HTTPS/TLS for all communications")
    
    print("\n[TIPS] CHOOSING THE RIGHT METHOD:")
    print("   App Passwords: Quick setup, good for personal use")
    print("   OAuth2: Most secure, best for production apps") 
    print("   Alternative Providers: When Gmail isn't suitable")
    
    print("\n" + "=" * 70)
