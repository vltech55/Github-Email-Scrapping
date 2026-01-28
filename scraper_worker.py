#!/usr/bin/env python3
"""
Worker 1: GitHub Email Scraper
Uses github_module to search users and scrape emails -> sends to queue1
"""

import time
import os
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv

from github_module import GitHubManager
from github_module.advanced_search import GitHubAdvancedSearch
from message_queue import MessageQueueManager

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.WARNING, format='[%(name)s] %(message)s')
logger = logging.getLogger('SCRAPER')


class ScraperWorker:
    """Worker that scrapes GitHub for emails and sends to queue1."""
    
    def __init__(self, github_token: str = None, db_path: str = "automation.db"):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.db_path = db_path
        
        # Initialize GitHub modules
        self.github_manager = GitHubManager(token=self.github_token)
        self.github_search = GitHubAdvancedSearch(token=self.github_token)
        
        # Initialize message queue
        self.queue = MessageQueueManager()
        
        self.running = False
        self.scraped_users = set()  # Track already scraped users in this session
        
        # Load already scraped users from database
        self._load_scraped_users()
        
        logger.info(f"Scraper initialized | Queue: {self.queue.backend_type}")
        logger.info(f"Already scraped users in DB: {len(self.scraped_users)}")
        if self.github_token:
            logger.info(f"GitHub token: YES (first 15 chars: {self.github_token[:15]}...)")
        else:
            logger.info(f"GitHub token: NO - Limited to 60 requests/hour!")
    
    def _load_scraped_users(self):
        """Load list of already scraped users from database."""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT username FROM users')
                self.scraped_users = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.warning(f"Could not load scraped users: {e}")
            self.scraped_users = set()
    
    def search_and_scrape(self, search_params: Dict[str, Any]) -> int:
        """Search GitHub and scrape emails from users."""
        
        try:
            logger.info(f"Searching GitHub: {search_params}")
            
            # Search users using advanced search
            results = self.github_search.search_users_advanced(**search_params)
            
            if not results['success']:
                logger.error(f"Search failed: {results.get('error')}")
                return 0
            
            users = results['users']
            logger.info(f"Found {len(users)} users")
        except Exception as e:
            logger.error(f"Critical error in GitHub search: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
        scraped_count = 0
        
        # With token: Use minimal delays, let rate limit tracker control
        # Without token: Must be very conservative
        has_token = self.github_token is not None
        
        logger.info(f"Token: {'yes' if has_token else 'NO'}")
        if has_token:
            logger.info(f"Making requests as fast as possible (dynamic delays)")
        
        for user in users:
            if not self.running:
                break

            try:
                logger.info(f"user {user}")
                
                if not user['type'] == 'User':
                    continue

                username = user['login']
                
                # Skip if already scraped
                if username in self.scraped_users:
                    logger.info(f"Skipping {username} - already scraped")
                    continue
                
                logger.info(f"Processing: {username}")
                
                # Scrape emails for single user
                email_result = self.github_manager.scrape_user_email(username)
                
                # Check if rate limited
                if email_result.get('rate_limited'):
                    logger.error(f"Rate limit hit! Waiting 2 minutes...")
                    time.sleep(120)
                    # Retry once
                    email_result = self.github_manager.scrape_user_email(username)
                    if email_result.get('rate_limited'):
                        logger.error(f"Still rate limited, skipping")
                        continue
                
                # Check if scraping was successful
                if not email_result.get('success'):
                    logger.warning(f"Failed to scrape {username}: {email_result.get('error')}")
                    # Small delay on failure
                    time.sleep(0.3 if has_token else 65.0)
                    continue
                
                user_emails = email_result.get('emails', [])
                logger.info(f"Found {len(user_emails)} emails for {username}")
                
                if user_emails:
                    # Prepare data for queue1
                    data = {
                        'username': username,
                        'github_id': user['id'],
                        'avatar_url': user.get('avatar_url'),
                        'html_url': user.get('html_url'),
                        'emails': user_emails,
                        'scraped_at': time.time()
                    }
                    
                    # Send to queue1
                    success = self.queue.send_task('queue1', data, priority=1)
                    
                    if success:
                        logger.info(f"-> queue1: {username} ({len(user_emails)} emails)")
                        logger.info(f"{user_emails}")
                        scraped_count += 1
                        # Mark as scraped to avoid re-scraping
                        self.scraped_users.add(username)
                    else:
                        logger.error(f"Failed to send {username} to queue1")
                else:
                    logger.warning(f"No emails found for {username}")
                    # Still mark as scraped even if no emails found
                    self.scraped_users.add(username)
                
                # Dynamic delay based on optimization
                # If profile email found (api_calls_saved=3), only 1 API call was made - minimal delay
                # Otherwise, multiple API calls were made - slightly longer delay
                if has_token:
                    if email_result.get('api_calls_saved', 0) == 3:
                        # Profile email found - only 1 API call, no delay needed
                        time.sleep(0.1)
                    else:
                        # Checked commits - multiple API calls, small delay
                        time.sleep(0.3)
                else:
                    # No token - must be very conservative
                    time.sleep(65.0)
                    
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error processing user {user.get('login', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                # Mark as scraped to avoid retry loop
                if 'username' in locals():
                    self.scraped_users.add(username)
                # Continue with next user instead of crashing
                time.sleep(1.0)
                continue
        
        return scraped_count
    
    def run(self, search_configs: List[Dict[str, Any]], continuous: bool = False, single_config_mode: bool = False):
        """
        Run scraping with given search configurations.
        
        Args:
            search_configs: List of search configurations
            continuous: If True, repeat cycles indefinitely
            single_config_mode: If True, only use first config and paginate through all results
        """
        
        try:
            self.running = True
            cycle = 0
            
            # Single config mode: Use ONLY the first config, paginate continuously
            if single_config_mode and search_configs:
                logger.info("="*70)
                logger.info("SINGLE CONFIG MODE: Using first config only")
                logger.info("Will paginate through ALL pages continuously")
                logger.info("="*70)
                
                config = search_configs[0]
                logger.info(f"Config: {config}")
                
                # Keep scraping with same config continuously
                while self.running:
                    try:
                        # Run with this config (pagination handled in search_and_scrape)
                        count = self.search_and_scrape(config)
                        logger.info(f"Completed pass: {count} users sent to queue1")
                        
                        if count == 0:
                            logger.warning("No new users found in this pass")
                            logger.info("Waiting 60 seconds before retry...")
                            time.sleep(60)
                        else:
                            logger.info("Starting next pass...")
                            time.sleep(5)  # Small delay between passes
                            
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user")
                        self.running = False
                        break
                    except Exception as e:
                        logger.error(f"Error in single config mode: {e}")
                        import traceback
                        traceback.print_exc()
                        logger.info("Waiting 30 seconds before retry...")
                        time.sleep(30)
                
                return
            
            # Normal mode: Cycle through all configs
            while self.running:
                cycle += 1
                logger.info(f"======== Cycle {cycle} ========")
                
                total_scraped = 0
                
                for i, config in enumerate(search_configs, 1):
                    if not self.running:
                        break
                    
                    try:
                        logger.info(f"Search config {i}/{len(search_configs)}")
                        count = self.search_and_scrape(config)
                        total_scraped += count
                    except Exception as e:
                        logger.error(f"Error processing config {i}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Continue with next config instead of crashing
                    
                    time.sleep(5)
                
                logger.info(f"Cycle {cycle} complete: {total_scraped} users sent to queue1")
                
                if not continuous:
                    break
                
                logger.info("Waiting 60 seconds before next cycle...")
                time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Scraper interrupted by user")
            self.running = False
        except Exception as e:
            logger.error(f"Critical error in scraper run loop: {e}")
            import traceback
            traceback.print_exc()
            self.running = False
            raise
    
    def stop(self):
        """Stop the worker."""
        logger.info("Stopping scraper worker...")
        self.running = False


def main():
    """Main entry point."""
    
    # Search configurations
    search_configs = [
        {
            'location': 'San Francisco',
            'language': 'python',
            'min_followers': 20,
            'max_results': 30
        },
        {
            'location': 'Seattle',
            'language': 'javascript',
            'min_followers': 15,
            'max_results': 30
        }
    ]
    
    worker = ScraperWorker()
    
    try:
        logger.info("Starting scraper worker...")
        worker.run(search_configs, continuous=False)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        worker.stop()


if __name__ == "__main__":
    main()
