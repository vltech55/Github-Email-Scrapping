#!/usr/bin/env python3
"""Quick progress check"""
import sqlite3

conn = sqlite3.connect('automation.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM users')
users = cursor.fetchone()[0]

cursor.execute('SELECT status, COUNT(*) FROM actions GROUP BY status')
actions = dict(cursor.fetchall())

print(f"Users: {users}")
print(f"Completed: {actions.get('completed', 0)}")
print(f"Queued: {actions.get('queued', 0)}")
print(f"Skipped: {actions.get('skipped', 0)}")

cursor.execute('SELECT username FROM users ORDER BY id DESC LIMIT 3')
print(f"\nLast 3 users:")
for (username,) in cursor.fetchall():
    print(f"  - {username}")

conn.close()

