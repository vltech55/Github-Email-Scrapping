"""
Core email sending functionality with multiple account support.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import logging

from .config import EmailConfig, MultiAccountConfig, get_multi_account_config
from .auth import AuthManager
from .utils import validate_email

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Reduce email module noise


class GmailSender:
    """Enhanced Gmail sender with multiple authentication methods."""
    
    def __init__(self, config: EmailConfig):
        """
        Initialize Gmail sender with configuration.
        
        Args:
            config: EmailConfig instance with account details
        """
        self.config = config
        self.auth_manager = AuthManager(config)
        
    def send_email(self, 
                   to_email: Union[str, List[str]], 
                   subject: str, 
                   body: str, 
                   html_body: Optional[str] = None,
                   attachments: Optional[List[str]] = None,
                   cc: Optional[Union[str, List[str]]] = None,
                   bcc: Optional[Union[str, List[str]]] = None,
                   reply_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Send an email through Gmail SMTP.
        
        Args:
            to_email: Recipient email address(es)
            subject: Email subject
            body: Plain text body of the email
            html_body: Optional HTML body of the email
            attachments: Optional list of file paths to attach
            cc: Optional CC email address(es)
            bcc: Optional BCC email address(es)
            reply_to: Optional reply-to address
            
        Returns:
            dict: Result with success status, message, and details
        """
        result = {
            'success': False,
            'message': '',
            'recipients': [],
            'account_used': self.config.email_address
        }
        
        try:
            # Validate recipients
            all_recipients = self._prepare_recipients(to_email, cc, bcc)
            if not all_recipients['valid']:
                result['message'] = f"Invalid recipients: {all_recipients['errors']}"
                return result
            
            # Create message
            msg = self._create_message(
                to_email, subject, body, html_body, cc, bcc, reply_to
            )
            
            # Add attachments
            if attachments:
                attachment_result = self._add_attachments(msg, attachments)
                if not attachment_result['success']:
                    logger.warning(f"Some attachments failed: {attachment_result['message']}")
            
            # Send email (use SMTP_SSL for port 465, SMTP with starttls for port 587)
            context = ssl.create_default_context()
            
            if self.config.smtp_port == 465:
                # Use SMTP_SSL for port 465
                with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, context=context) as server:
                    # Authenticate using auth manager
                    auth_result = self.auth_manager.authenticate(server)
                    if not auth_result['success']:
                        result['message'] = f"Authentication failed: {auth_result['message']}"
                        return result
                    
                    # Send the email
                    rejected = server.sendmail(
                        self.config.email_address, 
                        all_recipients['addresses'], 
                        msg.as_string()
                    )
            else:
                # Use SMTP with starttls for port 587
                with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    
                    # Authenticate using auth manager
                    auth_result = self.auth_manager.authenticate(server)
                    if not auth_result['success']:
                        result['message'] = f"Authentication failed: {auth_result['message']}"
                        return result
                    
                    # Send the email
                    rejected = server.sendmail(
                        self.config.email_address, 
                        all_recipients['addresses'], 
                        msg.as_string()
                    )
                
                if rejected:
                    result['message'] = f"Some recipients were rejected: {rejected}"
                    result['rejected_recipients'] = rejected
                else:
                    result['success'] = True
                    result['message'] = "Email sent successfully"
                
                result['recipients'] = all_recipients['addresses']
                
            logger.info(f"Email sent from {self.config.email_address} to {len(all_recipients['addresses'])} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            result['message'] = f"Send failed: {str(e)}"
            
        return result
    
    def _prepare_recipients(self, to_email, cc, bcc) -> Dict[str, Any]:
        """Prepare and validate all recipients."""
        result = {'valid': True, 'addresses': [], 'errors': []}
        
        # Process TO addresses
        if isinstance(to_email, str):
            to_email = [to_email]
        
        for email in to_email:
            if validate_email(email):
                result['addresses'].append(email)
            else:
                result['errors'].append(f"Invalid TO email: {email}")
                result['valid'] = False
        
        # Process CC addresses
        if cc:
            if isinstance(cc, str):
                cc = [cc]
            for email in cc:
                if validate_email(email):
                    result['addresses'].append(email)
                else:
                    result['errors'].append(f"Invalid CC email: {email}")
                    result['valid'] = False
        
        # Process BCC addresses
        if bcc:
            if isinstance(bcc, str):
                bcc = [bcc]
            for email in bcc:
                if validate_email(email):
                    result['addresses'].append(email)
                else:
                    result['errors'].append(f"Invalid BCC email: {email}")
                    result['valid'] = False
        
        return result
    
    def _create_message(self, to_email, subject, body, html_body, cc, bcc, reply_to) -> MIMEMultipart:
        """Create the email message."""
        msg = MIMEMultipart('alternative')
        from_header = self.config.email_address
        if self.config.display_name:
            from_header = f"{self.config.display_name} <{self.config.email_address}>"
        msg['From'] = from_header
        msg['Subject'] = subject
        
        # Handle recipients for headers
        if isinstance(to_email, str):
            to_email = [to_email]
        msg['To'] = ', '.join(to_email)
        
        if cc:
            if isinstance(cc, str):
                cc = [cc]
            msg['Cc'] = ', '.join(cc)
        
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Add plain text body
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        # Add HTML body if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        return msg
    
    def _add_attachments(self, msg: MIMEMultipart, attachments: List[str]) -> Dict[str, Any]:
        """Add attachments to the email message."""
        result = {'success': True, 'attached': [], 'failed': []}
        
        for file_path in attachments:
            if not os.path.exists(file_path):
                result['failed'].append(f"File not found: {file_path}")
                continue
                
            try:
                with open(file_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                
                filename = Path(file_path).name
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                
                msg.attach(part)
                result['attached'].append(filename)
                
            except Exception as e:
                result['failed'].append(f"Failed to attach {file_path}: {str(e)}")
        
        if result['failed']:
            result['success'] = False
            result['message'] = f"Some attachments failed: {result['failed']}"
        else:
            result['message'] = f"All {len(result['attached'])} attachments added successfully"
        
        return result
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the email connection and authentication."""
        result = {'success': False, 'message': '', 'auth_method': ''}
        
        try:
            context = ssl.create_default_context()
            
            if self.config.smtp_port == 465:
                # Use SMTP_SSL for port 465
                with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port, context=context) as server:
                    auth_result = self.auth_manager.authenticate(server)
                    result.update(auth_result)
                    
                    if result['success']:
                        logger.info(f"Connection test successful for {self.config.email_address}")
            else:
                # Use SMTP with starttls for port 587
                with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    
                    auth_result = self.auth_manager.authenticate(server)
                    result.update(auth_result)
                    
                    if result['success']:
                        logger.info(f"Connection test successful for {self.config.email_address}")
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            result['message'] = f"Connection failed: {str(e)}"
        
        return result


class EmailManager:
    """Manages multiple Gmail accounts with rotation support and template integration."""
    
    def __init__(self, config: Optional[MultiAccountConfig] = None):
        """
        Initialize email manager with multiple accounts.
        
        Args:
            config: MultiAccountConfig with multiple accounts, or None to load from env
        """
        if config is None:
            # Use unified loader that supports multiple env formats (JSON, GMAIL_ADDRESS_*, single)
            config = get_multi_account_config()
        
        self.config = config
        # Convert dict to list for rotation
        self.account_list = list(config.accounts.values())
        self.senders = {
            account.email_address: GmailSender(account)
            for account in self.account_list
        }
        self.current_index = 0
        self.email_count = 0
        self.template_index = 0
        
        if not self.senders:
            raise ValueError("No email accounts configured")
        
        logger.info(f"Email manager initialized with {len(self.senders)} account(s)")
        try:
            loaded_emails = ", ".join([acc.email_address for acc in self.account_list])
            logger.info(f"Loaded accounts: {loaded_emails}")
        except Exception:
            pass
        
        # Keep old interface for compatibility
        self.accounts: Dict[str, GmailSender] = {}
        self.default_account: Optional[str] = None
    
    def get_current_account(self) -> EmailConfig:
        """Get the currently selected account configuration."""
        return self.account_list[self.current_index]
    
    def rotate_account(self) -> None:
        """Rotate to the next account in the list."""
        self.current_index = (self.current_index + 1) % len(self.account_list)
        self.email_count += 1
        logger.info(f"Rotated to account: {self.account_list[self.current_index].email_address}")
    
    def get_next_template_index(self) -> int:
        """Get next template index for rotation. Currently locked to Template 1 only."""
        # Always return 0 (Template 1) - disabled rotation
        return 0
    
    def send_from_current_account(self,
                                  to_email: Union[str, List[str]],
                                  subject: str,
                                  body: str,
                                  html_body: Optional[str] = None,
                                  **kwargs) -> Dict[str, Any]:
        """
        Send email from the currently selected account.
        
        Args:
            to_email: Recipient email address(es)
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            **kwargs: Additional arguments passed to send_email
            
        Returns:
            dict: Send result
        """
        current_account = self.get_current_account()
        sender = self.senders[current_account.email_address]
        
        result = sender.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body,
            **kwargs
        )
        
        return result
    
    def send_with_template_rotation(self,
                                    to_email: str,
                                    username: str,
                                    github_url: str,
                                    language: str = "Python",
                                    sender_name: str = None,
                                    company_name: str = None,
                                    website_link: str = None) -> Dict[str, Any]:
        """
        Send email with automatic account fallback on failure.
        
        NEW BEHAVIOR: Uses first email account for all sends. Only switches to
        second account if first account fails (due to policy, limit, etc).
        Stays on working account until it fails.
        
        Args:
            to_email: Recipient email address
            username: GitHub username
            github_url: GitHub profile URL
            language: Programming language
            sender_name: Sender name (from env if None)
            company_name: Company name (from env if None)
            website_link: Website link (from env if None)
            
        Returns:
            dict: Send result with account_used and template_index
        """
        from .templates import get_rotating_template
        import os
        
        # Determine sender name for this send based on the current account
        current_account = self.get_current_account()
        account_display_name = current_account.display_name or current_account.email_address.split('@')[0].title()
        default_sender_name = os.getenv('SENDER_NAME', account_display_name)
        sender_name = sender_name or account_display_name or default_sender_name
        company_name = company_name or os.getenv('COMPANY_NAME', 'Developer Collective')
        website_link = website_link or os.getenv('WEBSITE_LINK', 'https://github.com')
        
        # Get template
        template_index = self.get_next_template_index()
        template = get_rotating_template(template_index)
        
        # Prepare variables
        variables = {
            'username': username,
            'github_url': github_url,
            'language': language,
            'sender_name': sender_name,
            'company_name': company_name,
            'website_link': website_link
        }
        
        # Render template
        try:
            subject = template['subject'].format(**variables)
            body = template['body'].format(**variables)
            html_body = template['html_body'].format(**variables)
        except KeyError as e:
            return {
                'success': False,
                'error': f'Template variable error: {e}'
            }
        
        # Try sending with current account
        result = self.send_from_current_account(
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        # If failed, try next account (fallback logic)
        if not result.get('success', False) and len(self.account_list) > 1:
            logger.warning(f"Failed to send with {self.get_current_account().email_address}, trying fallback account...")
            
            # Switch to next account
            self.rotate_account()
            
            # Retry with new account
            result = self.send_from_current_account(
                to_email=to_email,
                subject=subject,
                body=body,
                html_body=html_body
            )
            
            if result.get('success', False):
                logger.info(f"Successfully sent with fallback account: {self.get_current_account().email_address}")
            else:
                logger.error(f"Failed to send with both accounts")
        
        # Add rotation info to result
        result['template_index'] = template_index
        result['email_count'] = self.email_count
        result['account_used'] = self.get_current_account().email_address
        
        # IMPORTANT: Keep using current account (no rotation) until it fails
        # Old behavior rotated on every email, new behavior only rotates on failure
        
        return result
        
    def add_account(self, name: str, email_address: str, password: str, 
                   smtp_server: str = "smtp.gmail.com", smtp_port: int = 587) -> bool:
        """
        Add an email account to the manager.
        
        Args:
            name: Unique name for this account
            email_address: Email address
            password: App password or regular password
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            
        Returns:
            bool: True if account was added successfully
        """
        try:
            config = EmailConfig(
                email_address=email_address,
                password=password,
                smtp_server=smtp_server,
                smtp_port=smtp_port
            )
            
            sender = GmailSender(config)
            self.accounts[name] = sender
            
            # Set as default if it's the first account
            if self.default_account is None:
                self.default_account = name
                
            logger.info(f"Added email account: {name} ({email_address})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add account {name}: {str(e)}")
            return False
    
    def remove_account(self, name: str) -> bool:
        """
        Remove an email account from the manager.
        
        Args:
            name: Name of the account to remove
            
        Returns:
            bool: True if account was removed successfully
        """
        if name in self.accounts:
            del self.accounts[name]
            
            # Update default account if necessary
            if self.default_account == name:
                self.default_account = next(iter(self.accounts)) if self.accounts else None
                
            logger.info(f"Removed email account: {name}")
            return True
        
        return False
    
    def list_accounts(self) -> Dict[str, str]:
        """
        List all configured accounts.
        
        Returns:
            dict: Account names mapped to email addresses
        """
        return {name: sender.config.email_address for name, sender in self.accounts.items()}
    
    def set_default_account(self, name: str) -> bool:
        """
        Set the default account for sending emails.
        
        Args:
            name: Name of the account to set as default
            
        Returns:
            bool: True if default was set successfully
        """
        if name in self.accounts:
            self.default_account = name
            logger.info(f"Set default account to: {name}")
            return True
        return False
    
    def send_email(self, to_email: Union[str, List[str]], subject: str, body: str,
                   account_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Send an email using specified or default account.
        
        Args:
            to_email: Recipient email address(es)
            subject: Email subject
            body: Email body
            account_name: Name of account to use (uses default if None)
            **kwargs: Additional arguments passed to send_email
            
        Returns:
            dict: Result of the email sending operation
        """
        # Determine which account to use
        account_to_use = account_name or self.default_account
        
        if not account_to_use:
            return {
                'success': False,
                'message': 'No account specified and no default account set',
                'account_used': None
            }
        
        if account_to_use not in self.accounts:
            return {
                'success': False,
                'message': f'Account "{account_to_use}" not found',
                'account_used': None
            }
        
        # Send the email
        sender = self.accounts[account_to_use]
        result = sender.send_email(to_email, subject, body, **kwargs)
        result['account_name'] = account_to_use
        
        return result
    
    def test_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """
        Test connection for all configured accounts.
        
        Returns:
            dict: Test results for each account
        """
        results = {}
        
        for name, sender in self.accounts.items():
            results[name] = sender.test_connection()
            results[name]['email_address'] = sender.config.email_address
        
        return results
    
    @classmethod
    def from_environment(cls) -> 'EmailManager':
        """
        Create an EmailManager from environment variables.
        
        Expected environment variables:
        - EMAIL_ACCOUNTS: JSON string with account configurations
        Or individual account variables:
        - GMAIL_ADDRESS_1, GMAIL_PASSWORD_1
        - GMAIL_ADDRESS_2, GMAIL_PASSWORD_2, etc.
        
        Returns:
            EmailManager: Configured email manager
        """
        manager = cls()
        
        try:
            # Try to load from JSON configuration first
            import json
            accounts_json = os.getenv('EMAIL_ACCOUNTS')
            if accounts_json:
                accounts_config = json.loads(accounts_json)
                for name, config in accounts_config.items():
                    manager.add_account(
                        name=name,
                        email_address=config['email'],
                        password=config['password'],
                        smtp_server=config.get('smtp_server', 'smtp.gmail.com'),
                        smtp_port=config.get('smtp_port', 587)
                    )
        except Exception as e:
            logger.debug(f"Failed to load from JSON config: {e}")
        
        # Try individual environment variables
        if not manager.accounts:
            # Try numbered accounts (GMAIL_ADDRESS_1, etc.)
            i = 1
            while True:
                email_var = f'GMAIL_ADDRESS_{i}'
                password_var = f'GMAIL_PASSWORD_{i}'
                
                email = os.getenv(email_var)
                password = os.getenv(password_var)
                
                if not email or not password:
                    break
                    
                account_name = f'account_{i}'
                manager.add_account(account_name, email, password)
                i += 1
            
            # Also try single account variables for backward compatibility
            if not manager.accounts:
                email = os.getenv('GMAIL_ADDRESS')
                password = os.getenv('GMAIL_PASSWORD')
                if email and password:
                    manager.add_account('default', email, password)
        
        return manager
