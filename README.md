# GitHub Email Automation System

A comprehensive automation pipeline for discovering GitHub developers and conducting professional email outreach at scale.

## 🎯 Overview

This system automates the entire workflow of finding developers on GitHub, extracting their contact information, and sending personalized outreach emails. Built with Python, Redis, and SQLite, it handles thousands of users efficiently while respecting API rate limits and email sending best practices.

## ✨ Features

- **Automated GitHub Scraping** - Search users by location, language, followers, and more
- **Smart Email Extraction** - Finds emails from profiles and commit history across multiple repositories
- **Fork Filtering** - Prioritizes user's own repositories over forks for accurate email discovery
- **Redis Queue System** - High-performance message queuing with fault tolerance
- **Multi-Account Email Sending** - Automatic failover between email accounts
- **Duplicate Prevention** - Never contacts the same person twice
- **Email Filtering** - Blacklist approach blocks only spam/invalid addresses
- **Auto-Restart Capability** - Self-healing workers that automatically recover from crashes
- **Single Config Mode** - Deep pagination through one search query for maximum coverage
- **Comprehensive Logging** - Full visibility into pipeline operations

## 🏗️ Architecture

```
┌──────────────┐      ┌────────┐      ┌──────────────┐      ┌────────┐      ┌─────────────┐
│   GitHub     │      │        │      │   Database   │      │        │      │   Actions   │
│   Scraper    │─────▶│ Queue1 │─────▶│    Worker    │─────▶│ Queue2 │─────▶│   Worker    │
│              │      │(Redis) │      │              │      │(Redis) │      │  (Emails)   │
└──────────────┘      └────────┘      └──────────────┘      └────────┘      └─────────────┘
```

### Workers

1. **Scraper Worker** - Searches GitHub, extracts emails, sends to Queue1
2. **Database Worker** - Processes Queue1, saves to SQLite, sends to Queue2
3. **Actions Worker** - Processes Queue2, sends emails with account rotation

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Redis server
- GitHub Personal Access Token
- Gmail accounts with App Passwords

### Installation

```bash
# Clone repository
git clone https://github.com/phantomdev0826/Github-Email-Scrapping.git
cd Github-Email-Scrapping

# Install dependencies
pip install -r requirements.txt

# Start Redis (if not already running)
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis
```

### Configuration

Create a `.env` file in the project root:

```env
# GitHub API Token (required)
GITHUB_TOKEN=ghp_your_github_token_here

# Email Account 1 (required)
EMAIL_1_ADDRESS=youremail1@gmail.com
EMAIL_1_PASSWORD=your_app_password_here

# Email Account 2 (optional - for failover)
EMAIL_2_ADDRESS=youremail2@gmail.com
EMAIL_2_PASSWORD=your_app_password_here

# Sender Details (optional)
SENDER_NAME_1=Your Name
SENDER_NAME_2=Alternative Name
```

**Getting Gmail App Passwords:**
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create password for "Mail"
5. Copy the 16-character password to `.env`

### Configure Search

Edit `search_config.json`:

```json
{
  "search_configurations": [
    {
      "location": "United States",
      "language": "python",
      "min_followers": 10,
      "max_results": 5000
    }
  ]
}
```

### Run

```bash
# Start the full pipeline
python main.py --single-config

# Or start in normal multi-config mode
python main.py
```

## 📖 Usage

### Running Modes

**Single Config Mode** (Recommended for deep scraping):
```bash
python main.py --single-config
```
- Uses only the first search configuration
- Paginates through all results (up to `max_results`)
- Continuous operation with automatic retry

**Normal Mode** (For diverse searches):
```bash
python main.py
```
- Cycles through all search configurations
- Repeats indefinitely
- Good for ongoing discovery

### Monitoring

```bash
# Quick progress check
python check_progress.py

# Full system diagnosis
python complete_diagnosis.py

# Live monitoring
python monitor_pipeline.py
```

### Standalone Email Extraction

Extract emails from a specific GitHub user:

```bash
python extract_github_emails.py
```
- Interactive prompts
- Checks profile and commit history
- Saves results to file
- No database required

## 🛠️ Configuration Options

### Search Parameters

- `location` - Geographic location (e.g., "San Francisco", "United Kingdom")
- `language` - Programming language (e.g., "python", "javascript")
- `min_followers` - Minimum follower count
- `max_followers` - Maximum follower count
- `min_repos` - Minimum repository count
- `max_results` - Maximum users to scrape (pagination limit)

### Email Settings

**Account Rotation:**
- Primary account used for all emails
- Automatic failover to secondary account on failure
- Stays on working account until it fails

**Rate Limiting:**
- 60 seconds between emails (configurable)
- Respects Gmail sending limits
- Prevents spam detection

**Template:**
- Simple, direct text-based message
- No rotation (same template for all)
- Customizable in `email_module/templates.py`

## 📊 Performance

### API Usage

- **Average:** 3.6 API calls per user
- **Hourly Capacity:** ~1,400 users (within 5,000 call/hour limit)
- **Daily Capacity:** ~1,000 users (recommended for sustainability)

### Email Sending

- **Rate:** 1 email per minute per account
- **Daily Capacity:** ~1,400 emails (with 1 account)
- **With 2 Accounts:** ~2,800 emails per day

### Success Rates

- **Email Discovery:** 60-70% of users have findable emails
- **Email Delivery:** ~85% success rate (rest filtered as spam/invalid)
- **Overall Reach:** ~50-60% of searched users receive emails

## 🔧 Advanced Features

### Auto-Restart

Workers automatically restart on crash:
- Detection within 5 seconds
- Up to 3 restart attempts
- Prevents infinite restart loops

### Error Handling

Comprehensive exception handling at 3 levels:
- Search-level (GitHub API failures)
- User-level (individual processing errors)
- Run-level (configuration and system errors)

### Email Filtering

Blacklist approach:
- **Accepts:** All emails except blacklisted patterns
- **Rejects:** No-reply, GitHub, invalid, automated addresses
- **Coverage:** ~95% of legitimate emails (vs 5% with whitelist)

### Fork Filtering

- Automatically filters out forked repositories
- Checks up to 3 user's own repositories for commits
- Maximizes email discovery accuracy

## 📁 Project Structure

```
Github-Email-Scrapping/
├── main.py                      # Main pipeline controller
├── scraper_worker.py            # GitHub user scraper
├── database_worker.py           # Database processor
├── actions_worker.py            # Email sender
├── message_queue.py             # Redis queue manager
├── extract_github_emails.py     # Standalone email extractor
├── search_config.json           # Search configuration
├── requirements.txt             # Python dependencies
├── check_progress.py            # Progress monitoring
├── complete_diagnosis.py        # System health check
├── github_module/               # GitHub API integration
│   ├── core.py
│   ├── advanced_search.py
│   ├── email_scraper.py
│   └── ...
└── email_module/                # Email sending system
    ├── core.py
    ├── templates.py
    ├── config.py
    └── ...
```

## 🔒 Security & Privacy

### Credentials

- Never commit `.env` file (included in `.gitignore`)
- Use App Passwords, not account passwords
- Token permissions: `read:user`, `user:email`

### Data Storage

- SQLite database stores user information locally
- Duplicate detection prevents re-contacting users
- All data stored locally, not shared externally

### Email Compliance

- Respects user privacy and email preferences
- Filters corporate and work emails appropriately
- Implements rate limiting to prevent spam detection
- Provides clear sender information in emails

## 📝 Database Schema

### Tables

**users:**
- username, github_id, avatar_url, html_url, scraped_at

**emails:**
- email, user_id, source (with unique constraints)

**actions:**
- user_id, email, action_type, status, completed_at, error

## 🐛 Troubleshooting

### Scraper Not Finding Users

**Check:**
- GitHub token is valid: `echo $GITHUB_TOKEN`
- Rate limit status: Check with `complete_diagnosis.py`
- Search criteria not exhausted: Change location/language

### Email Sending Failures

**Check:**
- App Passwords (not account passwords) in `.env`
- 2-Step Verification enabled on Gmail accounts
- Internet connectivity
- Gmail account not blocked/suspended

### Workers Dying

**Solution:**
- Auto-restart feature handles most crashes
- Check `complete_diagnosis.py` for specific issues
- Monitor with `monitor_pipeline.py`

### Redis Connection Error

**Check:**
- Redis server running: `redis-cli ping` should return `PONG`
- Port 6379 available
- No firewall blocking connection

## 🎓 Use Cases

- **Recruitment** - Find and contact developers with specific skills
- **Product Outreach** - Reach developers who might be interested in your tool/service
- **Collaboration** - Find potential partners or contributors
- **Market Research** - Build targeted contact lists
- **Network Building** - Connect with developers in your niche

## ⚙️ Customization

### Email Template

Edit `email_module/templates.py` line 430+ to customize message:

```python
GITHUB_TEMPLATES = [
    {
        'subject': 'Your Subject Here',
        'body': '''Your message content here...''',
        'html_body': '''<html>Your HTML version...</html>'''
    }
]
```

### Search Criteria

Edit `search_config.json` to target different users:

```json
{
  "location": "San Francisco",
  "language": "python",
  "min_followers": 20,
  "max_results": 1000
}
```

## 📈 Scaling

### Increase Capacity

1. **Add More Email Accounts** - Up to 5 accounts for 5x capacity
2. **Add More Search Configs** - Diverse searches for broader coverage
3. **Reduce Email Delays** - Faster sending (with caution)
4. **Deploy on Server** - Run 24/7 for continuous operation

### API Limits

- **GitHub:** 5,000 calls/hour with token
- **Gmail:** ~500 emails/day per account
- **Recommended:** 1,000 users/day for sustainability

## 🤝 Contributing

This project is maintained for personal use. Feel free to fork and customize for your needs.

## ⚠️ Disclaimer

This tool is for legitimate outreach purposes only. Users are responsible for:

- Complying with CAN-SPAM Act and GDPR regulations
- Respecting recipients' privacy and preferences
- Using appropriate, valuable email content
- Honoring unsubscribe requests
- Following GitHub's Terms of Service
- Following Gmail's Terms of Service

Automated scraping should be done responsibly and ethically. This tool respects GitHub's rate limits and only accesses publicly available information.

## 📄 License

This project is provided as-is for educational and personal use.

## 🔗 Links

- **Repository:** [https://github.com/phantomdev0826/Github-Email-Scrapping](https://github.com/phantomdev0826/Github-Email-Scrapping)
- **GitHub API Documentation:** [https://docs.github.com/en/rest](https://docs.github.com/en/rest)
- **Redis Documentation:** [https://redis.io/documentation](https://redis.io/documentation)

---

**Built with Python, Redis, and determination.** 🚀
