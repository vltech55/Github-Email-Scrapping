"""
Utility functions for email operations.
"""

import re
from typing import Optional, Union, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if email format is valid
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def validate_email_list(emails: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Validate a list of email addresses.
    
    Args:
        emails: Single email string or list of emails
        
    Returns:
        dict: Validation results with valid/invalid emails
    """
    result = {
        'valid': [],
        'invalid': [],
        'all_valid': True
    }
    
    # Convert single email to list
    if isinstance(emails, str):
        emails = [emails]
    
    for email in emails:
        email = email.strip() if isinstance(email, str) else str(email).strip()
        if validate_email(email):
            result['valid'].append(email)
        else:
            result['invalid'].append(email)
            result['all_valid'] = False
    
    return result


def format_email_list(emails: Union[str, List[str]]) -> List[str]:
    """
    Format and clean a list of email addresses.
    
    Args:
        emails: Single email string or list of emails
        
    Returns:
        list: Cleaned list of valid email addresses
    """
    if isinstance(emails, str):
        # Handle comma-separated emails
        if ',' in emails:
            emails = [email.strip() for email in emails.split(',')]
        else:
            emails = [emails.strip()]
    
    # Filter out invalid emails
    valid_emails = []
    for email in emails:
        email = email.strip() if isinstance(email, str) else str(email).strip()
        if validate_email(email):
            valid_emails.append(email)
        else:
            logger.warning(f"Invalid email address skipped: {email}")
    
    return valid_emails


def send_quick_email(to_email: str, subject: str, message: str, 
                    account_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Quick function to send a simple email using the global email manager.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        message: Email message
        account_name: Optional account name to use
        
    Returns:
        dict: Send result
    """
    try:
        from .core import EmailManager
        from .config import get_multi_account_config
        
        # Create email manager from environment
        manager = EmailManager.from_environment()
        
        if not manager.accounts:
            return {
                'success': False,
                'message': 'No email accounts configured. Check your environment variables.',
                'setup_required': True
            }
        
        # Send email
        result = manager.send_email(
            to_email=to_email,
            subject=subject,
            body=message,
            account_name=account_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Quick send failed: {e}")
        return {
            'success': False,
            'message': f'Quick send failed: {str(e)}',
            'error': str(e)
        }


def test_email_setup() -> Dict[str, Any]:
    """
    Test the email setup and return detailed results.
    
    Returns:
        dict: Test results with account status and recommendations
    """
    try:
        from .core import EmailManager
        from .config import validate_setup
        
        # Validate configuration
        setup_results = validate_setup()
        
        if not setup_results['valid']:
            return {
                'setup_valid': False,
                'message': 'Email configuration is not valid',
                'errors': setup_results['errors'],
                'setup_instructions': setup_results.get('setup_instructions', [])
            }
        
        # Test connections
        manager = EmailManager.from_environment()
        connection_results = manager.test_all_accounts()
        
        # Analyze results
        working_accounts = []
        failed_accounts = []
        
        for account_name, result in connection_results.items():
            if result['success']:
                working_accounts.append({
                    'name': account_name,
                    'email': result['email_address'],
                    'auth_method': result.get('auth_method', 'unknown')
                })
            else:
                failed_accounts.append({
                    'name': account_name,
                    'email': result['email_address'],
                    'error': result['message'],
                    'suggestions': result.get('suggestions', [])
                })
        
        return {
            'setup_valid': True,
            'total_accounts': len(connection_results),
            'working_accounts': working_accounts,
            'failed_accounts': failed_accounts,
            'all_working': len(failed_accounts) == 0,
            'default_account': manager.default_account,
            'recommendations': _generate_recommendations(working_accounts, failed_accounts)
        }
        
    except Exception as e:
        logger.error(f"Email setup test failed: {e}")
        return {
            'setup_valid': False,
            'message': f'Setup test failed: {str(e)}',
            'error': str(e)
        }


def _generate_recommendations(working_accounts: List[Dict], 
                            failed_accounts: List[Dict]) -> List[str]:
    """Generate recommendations based on test results."""
    recommendations = []
    
    if not working_accounts:
        recommendations.append("❌ No working email accounts found - check your configuration")
        recommendations.append("🔧 Review environment variables or configuration file")
        recommendations.append("📖 Check setup instructions for your email provider")
    
    if failed_accounts:
        recommendations.append(f"⚠️  {len(failed_accounts)} account(s) failed connection test")
        for account in failed_accounts:
            recommendations.append(f"   • {account['name']} ({account['email']}): {account['error']}")
    
    if len(working_accounts) == 1:
        recommendations.append("ℹ️  Only one account configured - consider adding backup accounts")
    
    if working_accounts:
        recommendations.append(f"✅ {len(working_accounts)} account(s) working correctly")
        recommendations.append("🚀 Ready to send emails!")
    
    return recommendations


def get_file_size_limit() -> Dict[str, Any]:
    """
    Get information about email attachment size limits.
    
    Returns:
        dict: Size limits and recommendations
    """
    return {
        'limits_mb': {
            'gmail': 25,
            'outlook': 20,
            'yahoo': 20,
            'most_providers': 25
        },
        'recommendations': [
            "Keep total attachments under 20MB for best compatibility",
            "Use file compression (zip) for multiple files",
            "Consider cloud storage links for large files",
            "Test with small files first"
        ],
        'alternatives': [
            "Google Drive sharing links",
            "Dropbox shared links", 
            "OneDrive sharing links",
            "File hosting services"
        ]
    }


def create_html_from_text(text_content: str, title: str = "Email") -> str:
    """
    Create simple HTML email from plain text.
    
    Args:
        text_content: Plain text content
        title: Email title/subject
        
    Returns:
        str: HTML email content
    """
    # Convert newlines to <br> and paragraphs
    html_content = text_content.replace('\n\n', '</p><p>').replace('\n', '<br>')
    
    html_template = f"""
<html>
<head>
    <title>{title}</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <p>{html_content}</p>
</body>
</html>
    """.strip()
    
    return html_template


def extract_email_addresses(text: str) -> List[str]:
    """
    Extract email addresses from text.
    
    Args:
        text: Text containing email addresses
        
    Returns:
        list: Found email addresses
    """
    email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    emails = re.findall(email_pattern, text)
    
    # Validate and return unique emails
    valid_emails = []
    for email in emails:
        if validate_email(email) and email not in valid_emails:
            valid_emails.append(email)
    
    return valid_emails


def format_email_address(email: str, name: Optional[str] = None) -> str:
    """
    Format email address with optional display name.
    
    Args:
        email: Email address
        name: Optional display name
        
    Returns:
        str: Formatted email address
    """
    if not validate_email(email):
        raise ValueError(f"Invalid email address: {email}")
    
    if name:
        # Clean name of potentially problematic characters
        clean_name = re.sub(r'[<>"]', '', name.strip())
        return f'"{clean_name}" <{email}>'
    
    return email


def log_email_attempt(to_emails: Union[str, List[str]], subject: str, 
                     success: bool, account_used: str = "unknown") -> None:
    """
    Log an email sending attempt.
    
    Args:
        to_emails: Recipient email(s)
        subject: Email subject
        success: Whether the send was successful
        account_used: Account that was used
    """
    if isinstance(to_emails, str):
        to_emails = [to_emails]
    
    status = "SUCCESS" if success else "FAILED"
    recipient_count = len(to_emails)
    
    logger.info(f"Email {status}: '{subject}' to {recipient_count} recipient(s) via {account_used}")
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Recipients: {', '.join(to_emails[:3])}{'...' if len(to_emails) > 3 else ''}")


class EmailStats:
    """Simple email statistics tracker."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all statistics."""
        self.sent = 0
        self.failed = 0
        self.accounts_used = {}
        self.recipients = set()
    
    def record_send(self, success: bool, account_name: str, recipients: List[str]):
        """Record an email send attempt."""
        if success:
            self.sent += 1
        else:
            self.failed += 1
        
        # Track account usage
        if account_name not in self.accounts_used:
            self.accounts_used[account_name] = {'sent': 0, 'failed': 0}
        
        if success:
            self.accounts_used[account_name]['sent'] += 1
        else:
            self.accounts_used[account_name]['failed'] += 1
        
        # Track unique recipients
        self.recipients.update(recipients)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary."""
        total_attempts = self.sent + self.failed
        success_rate = (self.sent / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            'total_attempts': total_attempts,
            'sent': self.sent,
            'failed': self.failed,
            'success_rate': round(success_rate, 1),
            'unique_recipients': len(self.recipients),
            'accounts_used': dict(self.accounts_used)
        }


# Global stats instance
email_stats = EmailStats()
