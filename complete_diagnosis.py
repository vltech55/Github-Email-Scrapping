#!/usr/bin/env python3
"""Complete system diagnosis - check EVERYTHING"""

import sqlite3
from message_queue import MessageQueueManager
import os
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("COMPLETE SYSTEM DIAGNOSIS")
print("="*80)

# 1. Check if main.py is actually running
print("\n1. CHECKING IF PIPELINE IS RUNNING")
print("-"*80)
import psutil
python_processes = [p for p in psutil.process_iter(['pid', 'name', 'cmdline']) 
                   if p.info['name'] and 'python' in p.info['name'].lower()]
main_running = False
for p in python_processes:
    try:
        cmdline = p.info.get('cmdline', [])
        if cmdline and any('main.py' in str(cmd) for cmd in cmdline):
            print(f"[OK] main.py is running (PID: {p.info['pid']})")
            main_running = True
    except:
        pass

if not main_running:
    print("[ERROR] main.py is NOT running!")
    print("        You need to run: python main.py")

# 2. Check queues
print("\n2. CHECKING MESSAGE QUEUES")
print("-"*80)
try:
    mq = MessageQueueManager()
    q1 = mq.get_queue_length('queue1')
    q2 = mq.get_queue_length('queue2')
    print(f"Queue1 (scraper->database): {q1}")
    print(f"Queue2 (database->actions):  {q2}")
    
    if q1 == 0 and q2 == 0:
        print("[WARNING] Both queues are empty - no tasks to process")
except Exception as e:
    print(f"[ERROR] Queue error: {e}")

# 3. Check database
print("\n3. CHECKING DATABASE")
print("-"*80)
conn = sqlite3.connect('automation.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM users')
total_users = cursor.fetchone()[0]
print(f"Total users in database: {total_users}")

cursor.execute('SELECT COUNT(*) FROM emails')
total_emails = cursor.fetchone()[0]
print(f"Total emails in database: {total_emails}")

cursor.execute('SELECT status, COUNT(*) FROM actions GROUP BY status')
print(f"\nActions by status:")
for status, count in cursor.fetchall():
    print(f"  {status}: {count}")

# Check last user added
cursor.execute('SELECT username, created_at FROM users ORDER BY id DESC LIMIT 1')
last_user = cursor.fetchone()
if last_user:
    print(f"\nLast user added: {last_user[0]} at {last_user[1]}")

# 4. Check scraper status
print("\n4. CHECKING SCRAPER")
print("-"*80)
github_token = os.getenv('GITHUB_TOKEN')
if github_token:
    print(f"[OK] GitHub token configured: {github_token[:15]}...")
else:
    print("[ERROR] No GitHub token!")

# Check if scraper is actually scraping
cursor.execute('SELECT username FROM users ORDER BY id DESC LIMIT 5')
recent_users = cursor.fetchall()
print(f"\nLast 5 users scraped:")
for i, (username,) in enumerate(recent_users, 1):
    print(f"  {i}. {username}")

# 5. Check actions worker
print("\n5. CHECKING ACTIONS WORKER")
print("-"*80)

# Check if any actions are being processed
cursor.execute('''
    SELECT email, status, created_at, completed_at 
    FROM actions 
    ORDER BY id DESC LIMIT 5
''')
print("Last 5 actions:")
for email, status, created_at, completed_at in cursor.fetchall():
    print(f"  {email}: {status} (created: {created_at}, completed: {completed_at})")

# Check if there are queued actions
cursor.execute('SELECT COUNT(*) FROM actions WHERE status = "queued"')
queued = cursor.fetchone()[0]
if queued > 0:
    print(f"\n[PROBLEM] {queued} actions stuck in 'queued' status")
    if q2 == 0:
        print("          BUT Queue2 is empty!")
        print("          Actions were never sent to queue2!")

# 6. Check email configuration
print("\n6. CHECKING EMAIL CONFIGURATION")
print("-"*80)
email_configs = []
for i in range(1, 4):
    email = os.getenv(f'EMAIL_{i}_ADDRESS')
    password = os.getenv(f'EMAIL_{i}_PASSWORD')
    if email and password:
        email_configs.append(email)
        print(f"[OK] Email {i}: {email}")

if not email_configs:
    print("[ERROR] No email accounts configured!")
else:
    print(f"\n[OK] {len(email_configs)} email account(s) configured")

# 7. Check action_type issue
print("\n7. CHECKING ACTION_TYPE")
print("-"*80)
cursor.execute('SELECT DISTINCT action_type FROM actions')
action_types = [row[0] for row in cursor.fetchall()]
print(f"Action types in database: {action_types}")

if 'send_invitation' in action_types:
    cursor.execute('SELECT COUNT(*) FROM actions WHERE action_type = "send_invitation"')
    count = cursor.fetchone()[0]
    print(f"[WARNING] {count} old 'send_invitation' actions still exist!")
    print("          These are obsolete and should be removed")

conn.close()

# 8. Summary
print("\n" + "="*80)
print("DIAGNOSIS SUMMARY")
print("="*80)

issues = []
if not main_running:
    issues.append("Pipeline (main.py) is NOT running")
if q1 == 0 and q2 == 0:
    issues.append("Both queues are empty - scraper not producing tasks")
if queued > 0 and q2 == 0:
    issues.append(f"{queued} actions stuck - not sent to queue2")
if not email_configs:
    issues.append("No email accounts configured")
if 'send_invitation' in action_types:
    issues.append("Old 'send_invitation' actions still in database")

if issues:
    print("\n[PROBLEMS FOUND]")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
else:
    print("\n[OK] No major issues found")
    print("     System should be working...")

print("\n" + "="*80)

