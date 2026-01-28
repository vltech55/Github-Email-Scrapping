"""
Email Module - Professional Email Sending Package

A comprehensive email sending module with support for:
- Multiple Gmail accounts
- OAuth2 and App Password authentication
- HTML emails with templates
- Attachments and CC/BCC
- Email provider alternatives

Usage:
    from email_module import EmailManager, GmailSender
    
    # Initialize with multiple accounts
    manager = EmailManager()
    manager.add_account('work', 'work@gmail.com', 'app_password')
    manager.add_account('personal', 'personal@gmail.com', 'app_password')
    
    # Send email using specific account
    manager.send_email(
        account_name='work',
        to_email='recipient@example.com',
        subject='Hello from work email',
        body='This is sent from my work Gmail account'
    )
"""

__version__ = "1.0.0"
__author__ = "Your Name"

# Import main classes for easy access
from .core import GmailSender, EmailManager
from .config import EmailConfig, MultiAccountConfig
from .auth import AuthManager, OAuth2Helper
from .templates import EmailTemplateManager
from .utils import validate_email, send_quick_email

# Define what gets imported with "from email_module import *"
__all__ = [
    'GmailSender',
    'EmailManager', 
    'EmailConfig',
    'MultiAccountConfig',
    'AuthManager',
    'OAuth2Helper',
    'EmailTemplateManager',
    'validate_email',
    'send_quick_email'
]

# Quick access functions
def create_email_manager():
    """
    Create an EmailManager instance with configuration from environment.
    
    Returns:
        EmailManager: Configured email manager
    """
    return EmailManager.from_environment()

def list_providers():
    """
    List supported email providers and their configuration.
    
    Returns:
        dict: Provider configurations
    """
    return {
        'gmail': {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'auth_methods': ['app_password', 'oauth2'],
            'setup_url': 'https://support.google.com/accounts/answer/185833'
        },
        'outlook': {
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'auth_methods': ['app_password', 'oauth2'],
            'setup_url': 'https://support.microsoft.com/en-us/office/pop-imap-and-smtp-settings-for-outlook-com-d088b986-291d-42b8-9564-9c329cda5e82'
        },
        'yahoo': {
            'smtp_server': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'auth_methods': ['app_password'],
            'setup_url': 'https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html'
        }
    }
