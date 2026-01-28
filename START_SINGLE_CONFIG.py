#!/usr/bin/env python3
"""
Quick start script for SINGLE CONFIG MODE
Uses only the first config from search_config.json
Paginates through ALL pages until last user
"""

import subprocess
import sys

print("="*80)
print("STARTING PIPELINE IN SINGLE CONFIG MODE")
print("="*80)
print()
print("This mode will:")
print("  1. Use ONLY the first config from search_config.json")
print("  2. Paginate through ALL pages (page 1, 2, 3, ...)")
print("  3. Stop when reaching the last user")
print("  4. No cycling back to config 1 or moving to config 2")
print()
print("First config from search_config.json:")
print('  {')
print('    "location": "USA",')
print('    "language": "AI",')
print('    "min_followers": 5,')
print('    "max_results": 50000')
print('  }')
print()
print("="*80)
print()

# Run main.py with --single-config flag
subprocess.run([sys.executable, "main.py", "--single-config"])

