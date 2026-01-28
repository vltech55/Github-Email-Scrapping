#!/usr/bin/env python3
"""
Worker 3: Actions Worker
Takes from queue2 -> sends emails only (no invitations)
"""

import time
import sqlite3
import os
from typing import Dict, Any
import logging
from dotenv import load_dotenv

from message_queue import MessageQueueManager
from email_module import EmailManager

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.WARNING, format='[%(name)s] %(message)s')
logger = logging.getLogger('ACTIONS')
# Create separate logger for main stats that always shows
main_logger = logging.getLogger('MAIN')
main_logger.setLevel(logging.INFO)


class ActionsWorker:
    """Worker that processes queue2 and performs email actions."""
    
    # BLACKLIST: Email domains/patterns to REJECT (spam, invalid, no-reply, etc.)
    BLOCKED_EMAIL_PATTERNS = {
        # No-reply and automated addresses
        'noreply', 'no-reply', 'no_reply', 'donotreply', 'do-not-reply',
        
        # GitHub and code hosting
        'github.com', 'gitlab.com', 'bitbucket.org',
        
        # Invalid/placeholder domains
        'example.com', 'test.com', 'localhost', 'invalid',
        
        # Generic automated
        'mailer-daemon', 'postmaster',
        
        # Bounce addresses
        'bounce', 'bounces',
    }
    
    # BLACKLIST: Specific domain suffixes to reject
    BLOCKED_DOMAIN_SUFFIXES = {
        'users.noreply.github.com',
        'noreply.github.com',
    }
    
    def __init__(self, db_path: str = "automation.db"):
        self.db_path = db_path
        self.queue = MessageQueueManager()
        self.running = False
        
        # Initialize email manager (rotates accounts and templates)
        try:
            self.email_manager = EmailManager()
            logger.info(f"Email manager: {len(self.email_manager.senders)} accounts, 3 templates")
        except Exception as e:
            logger.error(f"Email manager failed: {e}")
            self.email_manager = None
        
        logger.info(f"Actions worker initialized | Queue: {self.queue.backend_type}")
        logger.info(f"Email filter: BLACKLIST mode - blocking {len(self.BLOCKED_EMAIL_PATTERNS)} patterns")
    
    def is_email_domain_allowed(self, email: str) -> bool:
        """
        Check if email should be accepted (NOT in blacklist).
        
        NEW LOGIC: Blacklist approach - accepts ALL emails EXCEPT:
        - No-reply addresses (noreply@, no-reply@, etc.)
        - GitHub emails (@github.com, @users.noreply.github.com)
        - Invalid/test domains (example.com, test.com, localhost, etc.)
        - Automated addresses (mailer-daemon, postmaster, bounce@, etc.)
        
        Args:
            email: Email address to check
            
        Returns:
            bool: True if email is valid and NOT blacklisted, False otherwise
        """
        if not email or '@' not in email:
            return False
        
        email_lower = email.lower()
        
        # Extract local part and domain
        local_part, domain = email_lower.rsplit('@', 1)
        
        # Check if domain matches any blocked suffix (e.g., users.noreply.github.com)
        for blocked_suffix in self.BLOCKED_DOMAIN_SUFFIXES:
            if domain == blocked_suffix or domain.endswith('.' + blocked_suffix):
                return False
        
        # Check if email contains any blocked pattern
        for pattern in self.BLOCKED_EMAIL_PATTERNS:
            if pattern in email_lower:
                return False
        
        # Check basic email validity (must have at least one dot in domain)
        if '.' not in domain:
            return False
        
        # Accept all other emails (personal domains, company domains, etc.)
        return True
    
    def has_already_sent_to_email(self, email: str) -> bool:
        """
        Check if we've already successfully sent an email to this address.
        
        Args:
            email: Email address to check
            
        Returns:
            bool: True if already sent, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if we've already completed sending an email to this address
                cursor.execute('''
                    SELECT COUNT(*) FROM actions 
                    WHERE email = ? AND action_type = 'send_email' AND status = 'completed'
                ''', (email,))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Error checking duplicate email: {e}")
            return False
    
    def send_email(self, to_email: str, username: str, github_url: str, language: str = "Python") -> bool:
        """Send email using email_module with account and template rotation."""
        
        if not self.email_manager:
            logger.info(f"[SIMULATE] Email to {to_email}")
            return True
        
        try:
            result = self.email_manager.send_with_template_rotation(
                to_email=to_email,
                username=username,
                github_url=github_url,
                language=language
            )
            
            if result['success']:
                account = result['account_used'].split('@')[0][:10]
                template = result['template_index'] + 1
                main_logger.info(f"✓ Email sent: {to_email} | Account: {account}... | Template: T{template}")
                return True
            else:
                main_logger.info(f"✗ Email failed: {to_email} - {result.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"Email error: {to_email} - {e}")
            return False
    
    
    def update_action_status(self, user_id: int, email: str, 
                            action_type: str, status: str, error: str = None):
        """Update action status in database."""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if error:
                    cursor.execute('''
                        UPDATE actions 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP, error = ?
                        WHERE user_id = ? AND email = ? AND action_type = ? AND status = 'queued'
                    ''', (status, error, user_id, email, action_type))
                else:
                    cursor.execute('''
                        UPDATE actions 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND email = ? AND action_type = ? AND status = 'queued'
                    ''', (status, user_id, email, action_type))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Database update error: {e}")
    
    def process_queue2(self):
        """Process messages from queue2."""
        
        logger.info("Processing queue2 -> sending emails only")
        
        processed = 0
        
        while self.running:
            try:
                # Get task from queue2
                task = self.queue.get_task('queue2', timeout=5)
                
                if not task:
                    continue
                
                data = task['data']
                user_id = data['user_id']
                username = data['username']
                email = data['email']
                github_id = data['github_id']
                html_url = data['html_url']
                
                logger.info(f"queue2 -> {username} ({email})")
                
                # Filter 1: Check if email is blacklisted (no-reply, github, invalid, etc.)
                if not self.is_email_domain_allowed(email):
                    logger.warning(f"Skipping {email}: blacklisted email (no-reply/invalid/automated)")
                    self.update_action_status(
                        user_id, email, 'send_email',
                        'skipped',
                        'Blacklisted email (no-reply/invalid/automated)'
                    )
                    continue
                
                # Filter 2: Check if we've already sent to this email
                if self.has_already_sent_to_email(email):
                    logger.warning(f"Skipping {email}: already sent to this address (filter 2)")
                    self.update_action_status(
                        user_id, email, 'send_email',
                        'skipped',
                        'Email address already sent to'
                    )
                    continue
                
                # Send email only (no GitHub invitation)
                email_success = self.send_email(email, username, html_url)
                self.update_action_status(
                    user_id, email, 'send_email',
                    'completed' if email_success else 'failed',
                    None if email_success else 'Failed to send email'
                )
                
                processed += 1
                
                # Delay 20 seconds between emails to avoid issues
                main_logger.info(f"Waiting 20 seconds before next email... (Sent: {processed})")
                time.sleep(20)
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                time.sleep(2)
        
        logger.info(f"Processed {processed} actions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get action statistics from database."""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT status, COUNT(*) 
                    FROM actions 
                    GROUP BY status
                ''')
                
                status_counts = dict(cursor.fetchall())
                
                cursor.execute('''
                    SELECT action_type, COUNT(*) 
                    FROM actions 
                    WHERE status = 'completed'
                    GROUP BY action_type
                ''')
                
                completed_counts = dict(cursor.fetchall())
                
                return {
                    'by_status': status_counts,
                    'completed': completed_counts
                }
                
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {'by_status': {}, 'completed': {}}
    
    def run(self):
        """Run the actions worker."""
        
        self.running = True
        
        import threading
        
        # Start processing thread
        thread = threading.Thread(target=self.process_queue2, daemon=True)
        thread.start()
        
        # Monitor stats
        try:
            while self.running:
                time.sleep(15)
                
                stats = self.get_stats()
                q2 = self.queue.get_queue_length('queue2')
                
                logger.info(f"Stats - Queue2: {q2}, Status: {stats['by_status']}")
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.stop()
        
        thread.join(timeout=5)
    
    def stop(self):
        """Stop the worker."""
        logger.info("Stopping actions worker...")
        self.running = False


def main():
    """Main entry point."""
    
    worker = ActionsWorker()
    return
    
    try:
        logger.info("Starting actions worker...")
        worker.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        worker.stop()


if __name__ == "__main__":
    main()
