"""
Configuration management for multiple email accounts with various authentication methods.
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class EmailConfig:
    """Configuration for a single email account."""
    email_address: str
    password: str
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    timeout: int = 30
    auth_method: str = "app_password"  # "app_password" or "oauth2"
    display_name: Optional[str] = None
    
    # OAuth2 specific settings
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.email_address:
            raise ValueError("Email address is required")
        if not self.password and self.auth_method == "app_password":
            raise ValueError("Password is required for app_password authentication")
        if '@' not in self.email_address:
            raise ValueError("Invalid email address format")
            
        if self.display_name is None:
            self.display_name = self.email_address.split('@')[0].title()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary (excluding sensitive data)."""
        return {
            'email_address': self.email_address,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'use_tls': self.use_tls,
            'timeout': self.timeout,
            'auth_method': self.auth_method,
            'display_name': self.display_name
        }


@dataclass
class MultiAccountConfig:
    """Configuration for multiple email accounts."""
    accounts: Dict[str, EmailConfig] = field(default_factory=dict)
    default_account: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'MultiAccountConfig':
        """Load multiple accounts from environment variables (EMAIL_1, EMAIL_2, EMAIL_3)."""
        config = cls()
        
        # Try to load EMAIL_1, EMAIL_2, EMAIL_3 from .env
        for i in range(1, 4):
            email = os.getenv(f'EMAIL_{i}_ADDRESS')
            password = os.getenv(f'EMAIL_{i}_PASSWORD')
            
            if email and password:
                email_config = EmailConfig(
                    email_address=email,
                    password=password,
                    smtp_server='smtp.gmail.com',
                    smtp_port=465,  # Try port 465 (SSL) instead of 587 (TLS)
                    use_tls=True
                )
                config.add_account(f'account_{i}', email_config)
        
        if not config.accounts:
            raise ValueError("No email accounts found in .env. Add EMAIL_1_ADDRESS and EMAIL_1_PASSWORD")
        
        return config
    
    def add_account(self, name: str, config: EmailConfig) -> None:
        """Add an email account configuration."""
        self.accounts[name] = config
        if self.default_account is None:
            self.default_account = name
    
    def remove_account(self, name: str) -> bool:
        """Remove an email account configuration."""
        if name in self.accounts:
            del self.accounts[name]
            if self.default_account == name:
                self.default_account = next(iter(self.accounts)) if self.accounts else None
            return True
        return False
    
    def get_account(self, name: str) -> Optional[EmailConfig]:
        """Get account configuration by name."""
        return self.accounts.get(name)
    
    def get_default_account(self) -> Optional[EmailConfig]:
        """Get the default account configuration."""
        if self.default_account and self.default_account in self.accounts:
            return self.accounts[self.default_account]
        return None
    
    def list_accounts(self) -> Dict[str, str]:
        """List all account names and their email addresses."""
        return {name: config.email_address for name, config in self.accounts.items()}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'accounts': {name: config.to_dict() for name, config in self.accounts.items()},
            'default_account': self.default_account
        }


class ConfigManager:
    """Manages email configuration from various sources."""
    
    def __init__(self):
        self._config: Optional[MultiAccountConfig] = None
    
    def load_from_env(self) -> MultiAccountConfig:
        """
        Load configuration from environment variables.
        
        Supports multiple formats:
        1. JSON format in EMAIL_ACCOUNTS variable
        2. Individual numbered accounts (GMAIL_ADDRESS_1, GMAIL_PASSWORD_1, etc.)
        3. Single account (GMAIL_ADDRESS, GMAIL_PASSWORD)
        
        Returns:
            MultiAccountConfig: Configuration object with all accounts
        """
        config = MultiAccountConfig()
        
        # Try JSON format first
        if self._load_from_json_env(config):
            self._config = config
            return config
        
        # Try numbered accounts
        if self._load_numbered_accounts(config):
            self._config = config
            return config
        
        # Try single account format
        if self._load_single_account(config):
            self._config = config
            return config
        
        raise ValueError("No valid email configuration found in environment variables")
    
    def _load_from_json_env(self, config: MultiAccountConfig) -> bool:
        """Load from EMAIL_ACCOUNTS JSON environment variable."""
        try:
            accounts_json = os.getenv('EMAIL_ACCOUNTS')
            if not accounts_json:
                return False
            
            accounts_data = json.loads(accounts_json)
            
            for name, account_data in accounts_data.items():
                email_config = EmailConfig(
                    email_address=account_data['email_address'],
                    password=account_data['password'],
                    smtp_server=account_data.get('smtp_server', 'smtp.gmail.com'),
                    smtp_port=account_data.get('smtp_port', 587),
                    auth_method=account_data.get('auth_method', 'app_password'),
                    display_name=account_data.get('display_name'),
                    client_id=account_data.get('client_id'),
                    client_secret=account_data.get('client_secret'),
                    refresh_token=account_data.get('refresh_token')
                )
                config.add_account(name, email_config)
            
            if accounts_data:
                # Set default account from config or use first one
                default_name = accounts_data.get('_default') or next(iter(accounts_data))
                config.default_account = default_name
                return True
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error loading JSON config: {e}")
        
        return False
    
    def _load_numbered_accounts(self, config: MultiAccountConfig) -> bool:
        """Load numbered accounts.
        Supports both:
          - GMAIL_ADDRESS_1 / GMAIL_PASSWORD_1 (preferred)
          - EMAIL_1_ADDRESS / EMAIL_1_PASSWORD (legacy)
        Scans indices 1..10 so a missing index doesn't stop loading others.
        """
        found_accounts = False
        for i in range(1, 11):
            email = os.getenv(f'GMAIL_ADDRESS_{i}') or os.getenv(f'EMAIL_{i}_ADDRESS')
            password = os.getenv(f'GMAIL_PASSWORD_{i}') or os.getenv(f'EMAIL_{i}_PASSWORD')
            
            if not email or not password:
                continue
            
            try:
                # Get optional settings for this account
                smtp_server = os.getenv(f'SMTP_SERVER_{i}', 'smtp.gmail.com')
                smtp_port = int(os.getenv(f'SMTP_PORT_{i}', '587'))
                auth_method = os.getenv(f'AUTH_METHOD_{i}', 'app_password')
                display_name = os.getenv(f'EMAIL_{i}_NAME') or os.getenv(f'DISPLAY_NAME_{i}')
                
                email_config = EmailConfig(
                    email_address=email,
                    password=password,
                    smtp_server=smtp_server,
                    smtp_port=smtp_port,
                    auth_method=auth_method,
                    display_name=display_name
                )
                
                account_name = f'account_{i}'
                config.add_account(account_name, email_config)
                found_accounts = True
                
            except ValueError as e:
                print(f"Error configuring account {i}: {e}")
                continue
        
        return found_accounts
    
    def _load_single_account(self, config: MultiAccountConfig) -> bool:
        """Load single account format (backward compatibility)."""
        email = os.getenv('GMAIL_ADDRESS')
        password = os.getenv('GMAIL_PASSWORD')
        
        if not email or not password:
            return False
        
        try:
            email_config = EmailConfig(
                email_address=email,
                password=password,
                smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                smtp_port=int(os.getenv('SMTP_PORT', '587')),
                auth_method=os.getenv('AUTH_METHOD', 'app_password'),
                display_name=os.getenv('DISPLAY_NAME')
            )
            
            config.add_account('default', email_config)
            return True
            
        except ValueError:
            return False
    
    def load_from_file(self, file_path: str) -> MultiAccountConfig:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            MultiAccountConfig: Loaded configuration
        """
        config = MultiAccountConfig()
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            for name, account_data in data.get('accounts', {}).items():
                email_config = EmailConfig(**account_data)
                config.add_account(name, email_config)
            
            config.default_account = data.get('default_account')
            
            self._config = config
            return config
            
        except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Failed to load config from file: {e}")
    
    def save_to_file(self, file_path: str, exclude_passwords: bool = True) -> None:
        """
        Save current configuration to a JSON file.
        
        Args:
            file_path: Path to save the configuration
            exclude_passwords: Whether to exclude sensitive data
        """
        if not self._config:
            raise ValueError("No configuration loaded")
        
        data = {
            'default_account': self._config.default_account,
            'accounts': {}
        }
        
        for name, config in self._config.accounts.items():
            account_data = config.to_dict()
            if not exclude_passwords:
                account_data['password'] = config.password
                if config.client_secret:
                    account_data['client_secret'] = config.client_secret
                if config.refresh_token:
                    account_data['refresh_token'] = config.refresh_token
            
            data['accounts'][name] = account_data
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_config(self) -> Optional[MultiAccountConfig]:
        """Get the current configuration."""
        return self._config


# Global configuration manager
config_manager = ConfigManager()


def get_multi_account_config() -> MultiAccountConfig:
    """
    Get email configuration, loading from environment if not already loaded.
    
    Returns:
        MultiAccountConfig: Email configuration with all accounts
    """
    config = config_manager.get_config()
    if config is None:
        config = config_manager.load_from_env()
    return config


def validate_setup() -> Dict[str, Any]:
    """
    Validate email setup and provide helpful information.
    
    Returns:
        dict: Validation results with setup information
    """
    results = {
        'valid': False,
        'accounts': {},
        'errors': [],
        'warnings': [],
        'setup_instructions': []
    }
    
    try:
        config = get_multi_account_config()
        results['valid'] = True
        results['default_account'] = config.default_account
        
        # Validate each account
        for name, account_config in config.accounts.items():
            account_result = {
                'email': account_config.email_address,
                'auth_method': account_config.auth_method,
                'valid': True,
                'warnings': []
            }
            
            # Check for potential issues
            if not account_config.email_address.endswith('@gmail.com'):
                account_result['warnings'].append(
                    f"Email {account_config.email_address} is not Gmail - may need different SMTP settings"
                )
            
            if (account_config.auth_method == "app_password" and 
                len(account_config.password) < 16):
                account_result['warnings'].append(
                    "Password may not be an app password (too short)"
                )
            
            results['accounts'][name] = account_result
            
    except ValueError as e:
        results['errors'].append(str(e))
        results['setup_instructions'] = get_setup_instructions()
    
    return results


def get_setup_instructions() -> List[str]:
    """Get setup instructions for email configuration."""
    return [
        "EMAIL SETUP OPTIONS:",
        "",
        "OPTION 1: Multiple accounts via environment variables",
        "Set these in your .env file:",
        "  GMAIL_ADDRESS_1=work@gmail.com",
        "  GMAIL_PASSWORD_1=work_app_password",
        "  GMAIL_ADDRESS_2=personal@gmail.com", 
        "  GMAIL_PASSWORD_2=personal_app_password",
        "",
        "OPTION 2: JSON configuration",
        "Set EMAIL_ACCOUNTS environment variable to JSON:",
        "  EMAIL_ACCOUNTS='{\"work\":{\"email_address\":\"work@gmail.com\",\"password\":\"app_pass\"}, \"personal\":{\"email_address\":\"personal@gmail.com\",\"password\":\"app_pass\"}}'",
        "",
        "OPTION 3: Single account (backward compatibility)",
        "  GMAIL_ADDRESS=your@gmail.com",
        "  GMAIL_PASSWORD=your_app_password",
        "",
        "GMAIL APP PASSWORD SETUP:",
        "1. Enable 2-Factor Authentication on Gmail",
        "2. Go to Google Account Settings > Security > App passwords",
        "3. Generate password for 'Mail' application",
        "4. Use the 16-character password (remove spaces)",
        "",
        "ALTERNATIVES TO GMAIL APP PASSWORDS:",
        "- OAuth2 authentication (more secure, complex setup)",
        "- Other email providers (Outlook, Yahoo, etc.)",
        "- Custom SMTP servers"
    ]


# Email provider configurations
EMAIL_PROVIDERS = {
    'gmail': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'auth_methods': ['app_password', 'oauth2'],
        'setup_url': 'https://support.google.com/accounts/answer/185833',
        'notes': 'Requires 2FA and app password or OAuth2'
    },
    'outlook': {
        'smtp_server': 'smtp-mail.outlook.com',
        'smtp_port': 587,
        'auth_methods': ['app_password', 'oauth2'],
        'setup_url': 'https://support.microsoft.com/office/pop-imap-smtp-settings-for-outlook-com-d088b986-291d-42b8-9564-9c329cda5e82',
        'notes': 'Modern authentication preferred'
    },
    'yahoo': {
        'smtp_server': 'smtp.mail.yahoo.com',
        'smtp_port': 587,
        'auth_methods': ['app_password'],
        'setup_url': 'https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html',
        'notes': 'Requires app password'
    },
    'custom': {
        'smtp_server': 'custom.server.com',
        'smtp_port': 587,
        'auth_methods': ['password', 'oauth2'],
        'setup_url': 'Contact your email provider',
        'notes': 'Use your provider specific settings'
    }
}


def get_provider_config(provider: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration template for an email provider.
    
    Args:
        provider: Provider name ('gmail', 'outlook', 'yahoo', 'custom')
        
    Returns:
        dict: Provider configuration template
    """
    return EMAIL_PROVIDERS.get(provider.lower())


def list_providers() -> Dict[str, Dict[str, Any]]:
    """
    List all supported email providers.
    
    Returns:
        dict: All provider configurations
    """
    return EMAIL_PROVIDERS.copy()
