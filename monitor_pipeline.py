#!/usr/bin/env python3
"""Monitor pipeline progress in real-time"""

import sqlite3
from message_queue import MessageQueueManager
import time
import os

print("="*80)
print("PIPELINE MONITOR - Press Ctrl+C to stop")
print("="*80)

mq = MessageQueueManager()
last_user_count = 0
last_completed = 0

try:
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("="*80)
        print("LIVE PIPELINE STATUS")
        print("="*80)
        
        # Check queues
        q1 = mq.get_queue_length('queue1')
        q2 = mq.get_queue_length('queue2')
        
        print(f"\nQUEUES:")
        print(f"  Queue1 (scraper->database): {q1}")
        print(f"  Queue2 (database->actions):  {q2}")
        
        # Check database
        conn = sqlite3.connect('automation.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM emails')
        email_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT status, COUNT(*) FROM actions GROUP BY status')
        actions = dict(cursor.fetchall())
        
        completed = actions.get('completed', 0)
        queued = actions.get('queued', 0)
        skipped = actions.get('skipped', 0)
        
        print(f"\nDATABASE:")
        print(f"  Total users:  {user_count} (new: {user_count - last_user_count})")
        print(f"  Total emails: {email_count}")
        
        print(f"\nACTIONS:")
        print(f"  Completed: {completed} (new: {completed - last_completed})")
        print(f"  Queued:    {queued}")
        print(f"  Skipped:   {skipped}")
        
        # Check last user
        cursor.execute('SELECT username, created_at FROM users ORDER BY id DESC LIMIT 1')
        last_user = cursor.fetchone()
        if last_user:
            print(f"\nLAST USER: {last_user[0]} (added: {last_user[1]})")
        
        # Check last action
        cursor.execute('''
            SELECT email, status, completed_at 
            FROM actions 
            WHERE status = "completed"
            ORDER BY id DESC LIMIT 1
        ''')
        last_action = cursor.fetchone()
        if last_action:
            print(f"LAST EMAIL: {last_action[0]} (sent: {last_action[2]})")
        
        conn.close()
        
        # Status
        print(f"\n{'='*80}")
        if q1 > 0:
            print("[ACTIVE] Scraper sending data to database")
        if q2 > 0:
            print("[ACTIVE] Database sending tasks to actions worker")
        if q1 == 0 and q2 == 0:
            print("[IDLE] Waiting for scraper to find new users...")
        
        print(f"\nRefreshing in 5 seconds... (Ctrl+C to stop)")
        print("="*80)
        
        last_user_count = user_count
        last_completed = completed
        
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n\n[STOPPED] Monitoring stopped")

