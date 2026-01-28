#!/usr/bin/env python3
"""
Worker 2: Database Manager
Takes from queue1 -> saves to SQLite -> sends to queue2
"""

import time
import sqlite3
import json
from typing import Dict, Any
import logging

from message_queue import MessageQueueManager

logging.basicConfig(level=logging.WARNING, format='[%(name)s] %(message)s')
logger = logging.getLogger('DATABASE')


class DatabaseWorker:
    """Worker that processes queue1, saves to database, sends to queue2."""
    
    def __init__(self, db_path: str = "automation.db"):
        self.db_path = db_path
        self.queue = MessageQueueManager()
        self.running = False
        
        # Initialize database
        self.init_database()
        
        logger.info(f"Database worker initialized | Queue: {self.queue.backend_type}")
        logger.info(f"Database: {db_path}")
    
    def init_database(self):
        """Initialize SQLite database."""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    github_id INTEGER UNIQUE,
                    avatar_url TEXT,
                    html_url TEXT,
                    scraped_at REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    source TEXT DEFAULT 'scraped',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(email, user_id)
                );
                
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(email, action_type)
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_emails_email ON emails(email);
                CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
                CREATE INDEX IF NOT EXISTS idx_actions_email ON actions(email);
            ''')
        
        logger.info("Database initialized")
    
    def save_user(self, data: Dict[str, Any]) -> int:
        """Save user and emails to database, return user_id."""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert or update user
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (username, github_id, avatar_url, html_url, scraped_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data['username'],
                data['github_id'],
                data['avatar_url'],
                data['html_url'],
                data['scraped_at']
            ))
            
            # Get user_id
            cursor.execute('SELECT id FROM users WHERE username = ?', (data['username'],))
            user_id = cursor.fetchone()[0]
            
            # Save emails
            saved_emails = 0
            for email in data['emails']:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO emails (email, user_id, source)
                        VALUES (?, ?, 'scraped')
                    ''', (email, user_id))
                    
                    if cursor.rowcount > 0:
                        saved_emails += 1
                except sqlite3.Error as e:
                    logger.error(f"Error saving email {email}: {e}")
            
            conn.commit()
            
            logger.info(f"Saved user {data['username']}: {saved_emails} new emails")
            return user_id
    
    def create_action_tasks(self, user_id: int, username: str, email: str, 
                           github_id: int, html_url: str) -> bool:
        """Create action tasks and send to queue2 (only if not already processed)."""
        
        # Check if we already have actions for this email
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if email already has completed or queued actions
            cursor.execute('''
                SELECT COUNT(*) FROM actions 
                WHERE email = ? AND action_type = 'send_email' 
                AND status IN ('queued', 'completed', 'skipped')
            ''', (email,))
            
            existing_count = cursor.fetchone()[0]
            
            if existing_count > 0:
                logger.warning(f"Skipping {email} - already has {existing_count} action(s)")
                return False
        
        # Prepare data for queue2
        action_data = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'github_id': github_id,
            'html_url': html_url
        }
        
        # Send to queue2
        success = self.queue.send_task('queue2', action_data, priority=1)
        
        if success:
            # Record action in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create email action only (removed invitation action)
                cursor.execute('''
                    INSERT INTO actions (user_id, email, action_type, status)
                    VALUES (?, ?, 'send_email', 'queued')
                ''', (user_id, email))
                
                conn.commit()
            
            logger.info(f"-> queue2: {email} ({username})")
            return True
        else:
            logger.error(f"Failed to send to queue2: {email}")
            return False
    
    def process_queue1(self):
        """Process messages from queue1."""
        
        logger.info("Processing queue1 -> database -> queue2")
        
        processed = 0
        
        while self.running:
            try:
                # Get task from queue1
                task = self.queue.get_task('queue1', timeout=5)
                
                if not task:
                    continue
                
                data = task['data']
                username = data['username']
                
                logger.info(f"queue1 -> {username}")
                
                # Save to database
                user_id = self.save_user(data)
                
                # Send each email to queue2
                for email in data['emails']:
                    self.create_action_tasks(
                        user_id, username, email,
                        data['github_id'], data['html_url']
                    )
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                time.sleep(2)
        
        logger.info(f"Processed {processed} users")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM emails')
            emails = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM actions WHERE status = "pending"')
            pending = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM actions WHERE status = "completed"')
            completed = cursor.fetchone()[0]
            
            return {
                'users': users,
                'emails': emails,
                'pending_actions': pending,
                'completed_actions': completed
            }
    
    def run(self):
        """Run the database worker."""
        
        self.running = True
        
        import threading
        
        # Start processing thread
        thread = threading.Thread(target=self.process_queue1, daemon=True)
        thread.start()
        
        # Monitor stats
        try:
            while self.running:
                time.sleep(10)
                
                stats = self.get_stats()
                q1 = self.queue.get_queue_length('queue1')
                q2 = self.queue.get_queue_length('queue2')
                
                logger.info(f"Stats - Users: {stats['users']}, Emails: {stats['emails']}, "
                          f"Queue1: {q1}, Queue2: {q2}")
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.stop()
        
        thread.join(timeout=5)
    
    def stop(self):
        """Stop the worker."""
        logger.info("Stopping database worker...")
        self.running = False


def main():
    """Main entry point."""
    
    worker = DatabaseWorker()
    
    try:
        logger.info("Starting database worker...")
        worker.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        worker.stop()


if __name__ == "__main__":
    main()
